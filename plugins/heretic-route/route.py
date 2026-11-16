"""Run one full Hermes agent turn on the local Heretic model inside the current chat.

The TUI patch turns a message that starts with ``_`` into ``/heretic --json <text>`` (``__`` adds
``--think``). The command builds a regular ``AIAgent`` on the ``heretic`` model alias: the same
tools, SOUL.md, memory, skills and plugins as the cloud model. Heretic sees the whole chat: the
cloud conversation is read from the session store and merged into Heretic's own view.

Heretic's turns are never written to the session store, so the cloud model never sees them and
its prompt cache stays intact. Heretic keeps its own view per chat (``ChatView``): its previous
messages, already compressed by its own context compressor when the chat outgrew its window, plus
the timestamp of the newest cloud message it has seen. The next turn appends only the cloud
messages written since then.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("heretic-route")

DEFAULT_ALIAS = "heretic"
THINK_FLAG = "--think"
JSON_FLAG = "--json"
RESET_WORDS = {"--reset", "--new"}
CONVERSATION_ROLES = {"user", "assistant", "tool"}
PREVIEW_LENGTH = 120


@dataclass
class Request:
    text: str = ""
    think: bool = False
    reset: bool = False
    as_json: bool = False

    @classmethod
    def parse(cls, raw: str) -> "Request":
        words = (raw or "").strip()
        request = cls()
        while True:
            head, _, rest = words.partition(" ")
            if head == THINK_FLAG:
                request.think = True
            elif head == JSON_FLAG:
                request.as_json = True
            elif head in RESET_WORDS:
                request.reset = True
            else:
                request.text = words
                return request
            words = rest.strip()


def public_message(message: dict) -> dict:
    """A message without the store's private bookkeeping keys (``_db_persisted`` and the like)."""
    return {key: value for key, value in message.items() if not key.startswith("_")}


def timestamp_of(message: dict) -> float:
    try:
        return float(message.get("timestamp") or 0)
    except (TypeError, ValueError):
        return 0.0


def complete_prefix(messages: list[dict]) -> list[dict]:
    """Drop trailing messages until the list ends with a finished assistant answer.

    A cloud turn still in progress leaves a user message, a tool call or a tool result at the
    tail; the next Heretic turn picks those up once the cloud turn has finished."""
    kept = list(messages)
    while kept and not (kept[-1].get("role") == "assistant" and not kept[-1].get("tool_calls")):
        kept.pop()
    return kept


def from_first_user(messages: list[dict]) -> list[dict]:
    """Messages from the first user message on, so an appended slice never starts mid-turn."""
    for index, message in enumerate(messages):
        if message.get("role") == "user":
            return messages[index:]
    return []


@dataclass
class ChatView:
    """Heretic's own conversation for one chat and the newest cloud message it already contains."""

    messages: list[dict] = field(default_factory=list)
    cloud_seen: float = 0.0

    def merged(self, cloud: list[dict]) -> "ChatView":
        """This view plus the finished cloud messages written after ``cloud_seen``."""
        fresh = from_first_user(complete_prefix([m for m in cloud if timestamp_of(m) > self.cloud_seen]))
        seen = max([self.cloud_seen] + [timestamp_of(m) for m in fresh])
        return ChatView(self.messages + [public_message(m) for m in fresh], seen)


class ViewStore:
    """One JSON file per chat next to the profile's other state."""

    def __init__(self, directory: Path):
        self.directory = directory

    def _path(self, session: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session or "default")[:120]
        return self.directory / f"{safe}.view.json"

    def load(self, session: str) -> ChatView:
        try:
            data = json.loads(self._path(session).read_text(encoding="utf-8"))
            messages = [m for m in data["messages"] if isinstance(m, dict) and m.get("role") in CONVERSATION_ROLES]
            return ChatView(messages, float(data.get("cloud_seen") or 0))
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return ChatView()

    def save(self, session: str, view: ChatView) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self._path(session)
        temporary = target.with_suffix(".tmp")
        payload = {"cloud_seen": view.cloud_seen, "messages": [public_message(m) for m in view.messages]}
        temporary.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
        os.replace(temporary, target)

    def clear(self, session: str) -> None:
        try:
            self._path(session).unlink()
        except OSError:
            pass


@dataclass
class ToolCall:
    name: str
    preview: str = ""


@dataclass
class TurnResult:
    text: str
    messages: list[dict]
    tools: list[ToolCall] = field(default_factory=list)
    seconds: float = 0.0
    tokens: int = 0


def tool_calls(messages: list[dict], preview: Callable[[str, dict], str]) -> list[ToolCall]:
    calls = []
    for message in messages:
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except (TypeError, ValueError):
                arguments = {}
            name = function.get("name") or "tool"
            calls.append(ToolCall(name, preview(name, arguments) if isinstance(arguments, dict) else ""))
    return calls


def turn_text(messages: list[dict]) -> str:
    """Everything the model said in the turn: the text before its tool calls as well as the final answer."""
    parts = [m.get("content") for m in messages if m.get("role") == "assistant"]
    return "\n\n".join(part.strip() for part in parts if isinstance(part, str) and part.strip())


def turn_start(messages: list[dict], text: str) -> int:
    """Index of this turn's user message (compression may have rewritten what came before it)."""
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].get("role") == "user" and messages[index].get("content") == text:
            return index
    return len(messages)


class HereticRunner:
    """Reads the chat and runs the agent: the only part that needs a live Hermes."""

    def __init__(self, alias: str = DEFAULT_ALIAS):
        self.alias = alias

    def cloud_history(self, session: str) -> list[dict]:
        from hermes_state_registry import acquire, release

        database = acquire()
        try:
            rows = database.get_messages_as_conversation(session, repair_alternation=True)
        finally:
            release(database)
        return [m for m in rows if m.get("role") in CONVERSATION_ROLES]

    def run(self, text: str, history: list[dict], think: bool) -> TurnResult:
        from agent.display import build_tool_preview
        from hermes_cli.config import load_config
        from hermes_cli.oneshot import _oneshot_clarify_callback, _resolve_model_and_provider
        from hermes_cli.runtime_provider import resolve_runtime_provider
        from hermes_cli.tools_config import _get_platform_tools
        from hermes_constants import resolve_reasoning_config
        from run_agent import AIAgent

        config = load_config()
        choice = _resolve_model_and_provider(config, self.alias, None)
        if not choice.base_url:
            raise RuntimeError(f"model alias '{self.alias}' is not configured (model_aliases.{self.alias})")
        runtime = resolve_runtime_provider(requested=choice.provider, target_model=choice.model,
                                           explicit_base_url=choice.base_url, explicit_api_key=choice.api_key)
        started = time.monotonic()
        # session_db=None: nothing of this turn reaches the chat's stored transcript.
        agent = AIAgent(
            api_key=runtime.get("api_key"), base_url=runtime.get("base_url"), provider=runtime.get("provider"),
            requested_provider=runtime.get("requested_provider"), api_mode=runtime.get("api_mode"),
            model=choice.model, enabled_toolsets=sorted(_get_platform_tools(config, "cli")),
            quiet_mode=True, platform="cli", session_db=None,
            reasoning_config=resolve_reasoning_config(config, choice.model) if think else {"enabled": False},
            request_overrides=runtime.get("request_overrides"), clarify_callback=_oneshot_clarify_callback,
        )
        # The reply goes back through the command result; nothing may print into the gateway's stdout.
        agent.suppress_status_output = True
        agent.stream_delta_callback = None
        agent.tool_gen_callback = None
        try:
            result = agent.run_conversation(text, conversation_history=history or None)
        finally:
            for step in (agent.shutdown_memory_provider, agent.close):
                try:
                    step()
                except Exception:
                    logger.debug("heretic-route: agent cleanup step failed", exc_info=True)
        if result.get("failed"):
            raise RuntimeError(str(result.get("error") or "the agent turn failed"))
        messages = list(result.get("messages") or [])
        turn = messages[turn_start(messages, text):]
        return TurnResult(
            text=turn_text(turn) or (result.get("final_response") or "").strip(), messages=messages,
            tools=tool_calls(turn,
                             lambda name, args: build_tool_preview(name, args, max_len=PREVIEW_LENGTH) or ""),
            seconds=time.monotonic() - started,
            tokens=int(getattr(agent, "session_completion_tokens", 0) or 0),
        )


class HereticRoute:
    """The ``/heretic`` command."""

    def __init__(self, store: ViewStore, runner: Optional[HereticRunner] = None):
        self.store = store
        self.runner = runner or HereticRunner()

    def __call__(self, raw_args: str = "", session_id: str = "", session_key: str = "", **_context) -> str:
        session = session_id or session_key or "default"
        request = Request.parse(raw_args)
        if request.reset:
            self.store.clear(session)
            if not request.text:
                return self.reply(request, "heretic: chat view cleared")
        if not request.text:
            return self.reply(request, "heretic: empty message (usage: _text, __text for thinking, /heretic --reset)")
        return self.answer(session, request)

    def answer(self, session: str, request: Request) -> str:
        try:
            cloud = self.runner.cloud_history(session)
        except Exception as error:
            logger.warning("heretic-route: cannot read chat %s: %s", session, error)
            cloud = []
        view = self.store.load(session).merged(cloud)
        logger.info("heretic-route: turn start session=%s view=%d think=%s", session, len(view.messages), request.think)
        try:
            result = self.runner.run(request.text, view.messages, request.think)
        except Exception as error:
            logger.warning("heretic-route: turn failed session=%s: %s", session, error, exc_info=True)
            return self.reply(request, f"heretic: the turn failed ({error}); nothing was sent to the cloud")
        logger.info("heretic-route: turn end session=%s tools=%d seconds=%.1f", session, len(result.tools), result.seconds)
        if not result.text:
            return self.reply(request, "heretic: the local model returned an empty answer", result)
        self.store.save(session, ChatView(result.messages, view.cloud_seen))
        return self.reply(request, result.text, result)

    def reply(self, request: Request, text: str, result: Optional[TurnResult] = None) -> str:
        footer = self.footer(result, request.think) if result else ""
        tools = [{"name": call.name, "preview": call.preview} for call in (result.tools if result else [])]
        if request.as_json:
            return json.dumps({"text": text, "footer": footer, "tools": tools}, ensure_ascii=False)
        trail = "\n".join(f"  {tool['name']} {tool['preview']}".rstrip() for tool in tools)
        return "\n\n".join(part for part in (trail, text, footer) if part)

    @staticmethod
    def footer(result: TurnResult, think: bool) -> str:
        tools = f" · {len(result.tools)} tools" if result.tools else ""
        mode = " · thinking" if think else ""
        return f"— heretic · {result.tokens} tok · {result.seconds:.1f} s{tools}{mode}"


def view_directory(home: Optional[Path] = None) -> Path:
    if home is None:
        from hermes_constants import get_hermes_home

        home = Path(get_hermes_home())
    return Path(home) / "heretic-route"
