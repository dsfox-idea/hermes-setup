"""Answer a chat message with the local Heretic model through Ollama, without the cloud model.

The TUI patch turns a message that starts with ``_`` into ``/heretic <text>`` and one that starts
with ``__`` into ``/heretic --think <text>``. The command keeps its own short history per session
(the last ``HISTORY_PAIRS`` exchanges), never the cloud conversation.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("heretic-route")

DEFAULT_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen36-35b-heretic:q5km"
HISTORY_PAIRS = 10
REQUEST_TIMEOUT = 600
THINK_FLAG = "--think"
RESET_WORDS = {"--reset", "--new"}

Transport = Callable[[str, dict, float], dict]


def post_json(url: str, body: dict, timeout: float) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data, {"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


@dataclass
class Request:
    text: str
    think: bool = False
    reset: bool = False

    @classmethod
    def parse(cls, raw: str) -> "Request":
        words = (raw or "").strip()
        think = reset = False
        while True:
            head, _, rest = words.partition(" ")
            if head == THINK_FLAG:
                think, words = True, rest.strip()
            elif head in RESET_WORDS:
                reset, words = True, rest.strip()
            else:
                return cls(words, think, reset)


class History:
    """Last exchanges of one session, stored as JSON next to the profile's other state."""

    def __init__(self, directory: Path, pairs: int = HISTORY_PAIRS):
        self.directory = directory
        self.pairs = pairs

    def _path(self, session: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session or "default")[:120]
        return self.directory / f"{safe}.json"

    def load(self, session: str) -> list[dict]:
        try:
            messages = json.loads(self._path(session).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return [m for m in messages if isinstance(m, dict) and m.get("role") in {"user", "assistant"}]

    def save(self, session: str, messages: list[dict]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        kept = messages[-2 * self.pairs:]
        target = self._path(session)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(kept, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, target)

    def clear(self, session: str) -> None:
        try:
            self._path(session).unlink()
        except OSError:
            pass


class HereticRoute:
    """The ``/heretic`` command: one local chat turn, answered entirely by Ollama."""

    def __init__(self, history: History, url: str = DEFAULT_URL, model: str = DEFAULT_MODEL,
                 transport: Transport = post_json, clock: Callable[[], float] = time.monotonic):
        self.history = history
        self.url = url.rstrip("/")
        self.model = model
        self.transport = transport
        self.clock = clock

    def __call__(self, raw_args: str = "", session_id: str = "", session_key: str = "", **_context) -> str:
        session = session_id or session_key or "default"
        request = Request.parse(raw_args)
        if request.reset:
            self.history.clear(session)
            if not request.text:
                return "heretic: history cleared"
        if not request.text:
            return "heretic: empty message (usage: _text, __text for thinking, /heretic --reset)"
        return self.answer(session, request)

    def answer(self, session: str, request: Request) -> str:
        messages = self.history.load(session) + [{"role": "user", "content": request.text}]
        body = {"model": self.model, "messages": messages, "stream": False, "think": request.think}
        started = self.clock()
        try:
            result = self.transport(f"{self.url}/api/chat", body, REQUEST_TIMEOUT)
        except (urllib.error.URLError, OSError, ValueError) as error:
            logger.warning("heretic-route: Ollama call failed: %s", error)
            return f"heretic: local model unavailable at {self.url} ({error}); nothing was sent to the cloud"
        message = result.get("message") or {}
        content = (message.get("content") or "").strip()
        if not content:
            logger.warning("heretic-route: empty answer: %s", str(result)[:300])
            return "heretic: the local model returned an empty answer"
        self.history.save(session, messages + [{"role": "assistant", "content": content}])
        return f"{content}\n\n{self.footer(result, self.clock() - started, request.think)}"

    def footer(self, result: dict, elapsed: float, think: bool) -> str:
        tokens = int(result.get("eval_count") or 0)
        seconds = (result.get("eval_duration") or 0) / 1e9
        rate = f" · {tokens / seconds:.0f} tok/s" if tokens and seconds else ""
        mode = " · thinking" if think else ""
        return f"— heretic · {tokens} tok{rate} · {elapsed:.1f} s{mode}"


def history_directory(home: Optional[Path] = None) -> Path:
    if home is None:
        from hermes_constants import get_hermes_home

        home = Path(get_hermes_home())
    return Path(home) / "heretic-route"
