"""Let display.tool_preview_length reach the tool-row previews of the TUI and gateway turns.

Hermes reads ``display.tool_preview_length`` only in the classic CLI and messaging platforms.
The TUI tool rows get their argument preview from ``tui_gateway.server._tool_ctx`` and
``gateway.run_turn_progress._tool_lifecycle_payload``, which both call
``agent.display.build_tool_preview(name, args, max_len=80)`` with a hard-coded 80. Both import
the function at call time, so wrapping it in ``agent.display`` covers every copy of those
callers (``tui_gateway`` rebinds ``_tool_ctx`` into several modules at startup). Only calls with
exactly that hard-coded length are changed; every other caller keeps its own limit.
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
from pathlib import Path
from typing import Callable

log = logging.getLogger("tool-preview")

HARD_CODED = 80
CALLERS = (("tui_gateway.server", "_tool_ctx"), ("gateway.run_turn_progress", "_tool_lifecycle_payload"))
_MARK = "__tool_preview_original__"


def _source_of(module: str, function: str) -> str:
    spec = importlib.util.find_spec(module)
    if spec is None or not spec.origin:
        return ""
    text = Path(spec.origin).read_text(encoding="utf-8")
    start = text.find(f"def {function}(")
    if start < 0:
        return ""
    end = text.find("\ndef ", start + 1)
    return text[start:end if end > 0 else None]


def compatibility() -> list:
    """Problems that keep the wrapper from working on this Hermes; empty when it fits."""
    try:
        import agent.display as display
    except ImportError as error:
        return [f"Hermes module missing: {error}"]
    problems = []
    function = getattr(display, "build_tool_preview", None)
    if not callable(function):
        return ["agent.display.build_tool_preview is gone"]
    if "max_len" not in inspect.signature(getattr(function, _MARK, function)).parameters:
        problems.append("agent.display.build_tool_preview lost its max_len parameter")
    for module, name in CALLERS:
        body = _source_of(module, name)
        if not body:
            problems.append(f"{module}.{name} is gone")
        elif "from agent.display import" not in body or f"max_len={HARD_CODED}" not in body:
            problems.append(f"{module}.{name} no longer imports build_tool_preview with max_len={HARD_CODED}")
    return problems


def normalize_length(value) -> int:
    """display.tool_preview_length: 0 (or unset) means no limit, like the rest of Hermes."""
    try:
        length = int(value or 0)
    except (TypeError, ValueError):
        log.warning("display.tool_preview_length %r is not a number; using no limit", value)
        return 0
    return max(length, 0)


def wrap(original: Callable, length: Callable[[], int]) -> Callable:
    def build_tool_preview(tool_name, args, max_len=None):
        if max_len == HARD_CODED:
            max_len = length()
        return original(tool_name, args, max_len=max_len)

    setattr(build_tool_preview, _MARK, original)
    build_tool_preview.__doc__ = original.__doc__
    return build_tool_preview


def install(length: Callable[[], int]) -> bool:
    """Wrap once per process. False (Hermes untouched) when this Hermes does not fit."""
    problems = compatibility()
    if problems:
        log.warning("tool-preview inactive, this Hermes version does not fit: %s", "; ".join(problems))
        return False
    import agent.display as display

    original = getattr(display.build_tool_preview, _MARK, display.build_tool_preview)
    display.build_tool_preview = wrap(original, length)
    log.info("tool-preview active: tool rows use display.tool_preview_length (now %s)", length() or "no limit")
    return True


def uninstall() -> None:
    import agent.display as display

    display.build_tool_preview = getattr(display.build_tool_preview, _MARK, display.build_tool_preview)
