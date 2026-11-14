"""Tool-row argument previews follow ``display.tool_preview_length`` (0 = no limit). See ``preview.py``."""

from .preview import install, normalize_length


def _configured_length() -> int:
    from hermes_cli.config import load_config_readonly

    display = (load_config_readonly() or {}).get("display") or {}
    return normalize_length(display.get("tool_preview_length"))


def register(ctx) -> None:
    install(_configured_length)
