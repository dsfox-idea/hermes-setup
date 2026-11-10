"""Select substantive tasks and request one advisory local review."""

from collections import OrderedDict
from dataclasses import dataclass, field
import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class ReviewContext:
    MAX_TURNS = 2
    MAX_MESSAGE_CHARACTERS = 1500

    @classmethod
    def text(cls, content: Any) -> str:
        if isinstance(content, list):
            content = "\n".join(
                part.get("text", "") if part.get("type") in {"text", "input_text"}
                else "[Non-text attachment omitted]"
                for part in content if isinstance(part, dict)
            )
        if not isinstance(content, str):
            return ""
        content = re.sub(r"<memory-context>.*?</memory-context>", "", content, flags=re.DOTALL).strip()
        if len(content) > cls.MAX_MESSAGE_CHARACTERS:
            marker = "\n[Excerpt shortened]\n"
            head = cls.MAX_MESSAGE_CHARACTERS - len(marker) - 400
            content = content[:head] + marker + content[-400:]
        return content

    @classmethod
    def collect(cls, history: list[dict[str, Any]] | None) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        answer = None
        turns = 0
        # pre_llm_call includes the current user message as its last row.
        for message in reversed((history or [])[:-1]):
            role = message.get("role")
            if role not in {"user", "assistant"}:
                continue
            if message.get("display_kind") or message.get("tool_calls"):
                if role == "user":
                    answer = None
                continue
            text = cls.text(message.get("content"))
            if not text:
                continue
            entry = {"role": role, "content": text}
            if role == "assistant":
                if answer is None:
                    answer = entry
                continue
            result[0:0] = [entry, answer] if answer else [entry]
            answer = None
            turns += 1
            if turns == cls.MAX_TURNS:
                break
        return result


@dataclass
class ReviewTask:
    request: str
    session_id: str
    conversation_context: list[dict[str, str]] = field(default_factory=list)
    tools: int = 0
    mutation: bool = False
    research: int = 0

    def substantive(self, answer: str, changed_paths: list[str]) -> bool:
        return bool(changed_paths or self.mutation or len(answer) >= 1200
                    or self.research >= 2 or self.tools >= 3 and len(answer) >= 300)


class HereticReviewer:
    MODEL = "qwen36-35b-heretic"
    MUTATIONS = frozenset({"write_file", "patch"})
    RESEARCH = frozenset({"web_search", "web_extract", "web_run", "arxiv_search"})

    def __init__(self, client: Any = None):
        self.client = client
        self.tasks: OrderedDict[str, ReviewTask] = OrderedDict()
        self.current: dict[str, str] = {}

    def capture(self, *, session_id: str, turn_id: str, user_message: Any,
                conversation_history: list[dict[str, Any]] | None = None,
                parent_session_id: str = "", **kwargs: Any) -> None:
        if parent_session_id or not session_id or not turn_id:
            return
        task = user_message if isinstance(user_message, str) else json.dumps(user_message, ensure_ascii=False)
        if re.match(r"\A\s*@(heretic|spark)(?=\s|$)", task):
            return
        self.current[session_id] = turn_id
        self.tasks[turn_id] = ReviewTask(
            request=task, session_id=session_id,
            conversation_context=ReviewContext.collect(conversation_history),
        )
        while len(self.tasks) > 256:
            old_turn, old_task = self.tasks.popitem(last=False)
            if self.current.get(old_task.session_id) == old_turn:
                self.current.pop(old_task.session_id, None)

    def tool_completed(self, *, session_id: str = "", turn_id: str = "", tool_name: str = "",
                       args: Any = None, **kwargs: Any) -> None:
        state = self.tasks.get(turn_id or self.current.get(session_id, ""))
        if state is None:
            return
        state.tools += 1
        state.mutation = state.mutation or tool_name in self.MUTATIONS
        state.research += tool_name in self.RESEARCH
        if tool_name == "terminal" and isinstance(args, dict):
            command = str(args.get("command") or "")
            state.mutation = state.mutation or any(
                marker in command for marker in ("hermes config set ", "hermes config unset ",
                                                "hermes skin set ", "defaults write ", "launchctl bootstrap ")
            )

    def review(self, *, session_id: str, turn_id: str, final_response: str,
               system_prompt: str, changed_paths: list[str], **kwargs: Any) -> dict[str, str] | None:
        state = self.tasks.pop(turn_id, None)
        if state is not None and self.current.get(state.session_id) == turn_id:
            self.current.pop(state.session_id, None)
        if state is None or not state.substantive(final_response, changed_paths):
            return None
        try:
            if self.client is None:
                from .runtime import LocalReviewClient
                self.client = LocalReviewClient()
            text = self.client.generate(state.request, final_response, system_prompt,
                                        conversation_context=state.conversation_context)
            return {"label": "Heretic", "model": self.client.model, "text": text, "status": "completed"}
        except Exception as error:
            logger.warning("Local response review failed (%s)", type(error).__name__, exc_info=True)
            return {"label": "Heretic", "model": getattr(self.client, "model", self.MODEL),
                    "text": type(error).__name__, "status": "failed", "language": "ru"}

    def forget(self, *, session_id: str, **kwargs: Any) -> None:
        self.current.pop(session_id, None)
        for key in [key for key, state in self.tasks.items() if state.session_id == session_id]:
            self.tasks.pop(key, None)
