"""Bounded retries for provider safety-filter refusals.

Hermes treats a safety-filter refusal as deterministic: one try on a configured fallback
provider, otherwise the turn ends. Anthropic's classifiers are not fully deterministic, so the
same request often passes on a later attempt. With no fallback left, this module waits and
re-sends the same request: after the first refusal in ``delays[0]`` seconds, after the second in
``delays[1]`` seconds, and lets the next refusal end the turn as before.

Two Hermes paths report a refusal, and both are wrapped:

* an HTTP 200 answer with ``finish_reason == "content_filter"`` (Anthropic ``stop_reason:
  refusal``, the Claude subscription plugin): ``agent.turn_truncation.handle_content_policy_refusal``,
  called from ``agent.turn_response_check``;
* an API error classified as ``content_policy_blocked`` (a 4xx block):
  ``agent.turn_api_error.settle_unrecovered_error``.

The refusal count is kept per model request (``agent._current_api_request_id``), so a normal
answer starts the next request at zero. The Hermes source checkout is not modified; when the
wrapped functions change shape the module leaves Hermes untouched and logs why.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Callable, Iterable, Optional

log = logging.getLogger("refusal-retry")

DEFAULT_DELAYS = (10.0, 60.0)
MAX_RETRIES = 5
MAX_DELAY_SECONDS = 600.0
_MARK = "_refusal_retry_original"
_STATE = "_refusal_retry_state"

_REFUSAL_PARAMS = {"agent", "response", "_retry", "thinking_spinner", "messages",
                   "active_system_prompt", "conversation_history", "api_call_count"}
_UNRECOVERED_PARAMS = {"agent", "api_error", "classified", "_retry", "messages",
                       "active_system_prompt", "conversation_history", "retry_count",
                       "compression_attempts", "api_call_count"}


def normalize_delays(value: Any) -> tuple:
    """The configured wait before each retry, in seconds; the defaults for anything invalid."""
    if value is None:
        return DEFAULT_DELAYS
    if not isinstance(value, (list, tuple)) or len(value) > MAX_RETRIES:
        log.warning("refusal-retry: delays must be a list of at most %d numbers; using %s",
                    MAX_RETRIES, list(DEFAULT_DELAYS))
        return DEFAULT_DELAYS
    delays = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not 0 <= item <= MAX_DELAY_SECONDS:
            log.warning("refusal-retry: invalid delay %r (0..%s s); using %s",
                        item, MAX_DELAY_SECONDS, list(DEFAULT_DELAYS))
            return DEFAULT_DELAYS
        delays.append(float(item))
    return tuple(delays)


def _seconds(value: float) -> str:
    return f"{value:g} s"


def _stop_hint(agent: Any) -> str:
    try:
        from agent.turn_recovery_autorecover import _DEFAULT_STOP_HINT, _STOP_HINTS
    except ImportError:
        return "press Esc to stop"
    return _STOP_HINTS.get(str(getattr(agent, "platform", "") or "").lower(), _DEFAULT_STOP_HINT)


class RefusalRetry:
    """Decides, per model request, whether a refusal is retried and after how long."""

    def __init__(self, delays: Callable[[], Iterable[float]] = lambda: DEFAULT_DELAYS):
        self._delays = delays

    def delays(self) -> tuple:
        try:
            return normalize_delays(self._delays())
        except Exception:
            log.warning("refusal-retry: could not read the configured delays", exc_info=True)
            return DEFAULT_DELAYS

    @staticmethod
    def _request_key(agent: Any) -> str:
        return str(getattr(agent, "_current_api_request_id", "") or "")

    def next_refusal(self, agent: Any) -> int:
        """Count one more refusal for the current request and return the count (1 = first)."""
        key = self._request_key(agent)
        state = getattr(agent, _STATE, None)
        if not isinstance(state, dict) or state.get("request") != key:
            state = {"request": key, "count": 0}
        state["count"] += 1
        setattr(agent, _STATE, state)
        return state["count"]

    @staticmethod
    def forget(agent: Any) -> None:
        setattr(agent, _STATE, None)

    def wait(self, agent: Any, _retry: Any, attempt: int, delays: tuple, *, messages: Any,
             conversation_history: Any, api_call_count: int, detail: str) -> Optional[dict]:
        """Announce and sleep before retry ``attempt``. Returns the interrupted turn result when
        the user stopped the wait, else None (a steering correction leaves
        ``_retry.restart_with_redirected_messages`` armed for the caller)."""
        from agent.turn_recovery import interruptible_backoff_sleep

        delay = delays[attempt - 1]
        notice = (f"⏳ The provider's safety filter refused the request — retrying automatically in "
                  f"{_seconds(delay)} (retry {attempt}/{len(delays)})")
        hint = _stop_hint(agent)
        notice = f"{notice}; {hint}" if hint else notice
        log.warning("%sSafety-filter refusal on %s (%s); retry %d/%d in %s",
                    getattr(agent, "log_prefix", ""), self._request_key(agent) or "?",
                    (detail or "no detail")[:300], attempt, len(delays), _seconds(delay))
        agent._emit_diagnostic_status(notice)
        agent._emit_diagnostic_wait(notice)
        return interruptible_backoff_sleep(
            agent, delay, _retry, messages=messages, conversation_history=conversation_history,
            api_call_count=api_call_count,
            abort_message="Interrupt detected while waiting to retry a safety-filter refusal, aborting.",
            interrupt_text=f"Operation interrupted: waiting to retry a safety-filter refusal "
                           f"(retry {attempt}/{len(delays)}).",
            activity_label=f"safety-filter refusal retry wait ({attempt}/{len(delays)})",
        )

    @staticmethod
    def gave_up_note(delays: tuple) -> str:
        waits = ", ".join(_seconds(d) for d in delays)
        times = "time" if len(delays) == 1 else "times"
        return f"Retried {len(delays)} {times} (after {waits}); the filter refused every attempt."

    def give_up(self, outcome: Any, delays: tuple) -> Any:
        """Hermes' own terminal verdict, with a note that the retries were spent."""
        result = getattr(outcome, "result", None)
        if delays and getattr(outcome, "action", None) == "return" and isinstance(result, dict):
            text = result.get("final_response") or ""
            result["final_response"] = f"{text}\n\n{self.gave_up_note(delays)}".strip()
            result["refusal_retries"] = len(delays)
        return outcome

    # -- HTTP 200 refusal (finish_reason content_filter) ------------------------------------

    def wrap_refusal(self, original: Callable) -> Callable:
        signature = inspect.signature(original)

        def handle_content_policy_refusal(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            agent, _retry = bound.arguments["agent"], bound.arguments["_retry"]
            if agent._has_pending_fallback():
                return original(*args, **kwargs)
            delays = self.delays()
            attempt = self.next_refusal(agent)
            if attempt > len(delays):
                self.forget(agent)
                return self.give_up(original(*args, **kwargs), delays)
            from agent.turn_api_call import stop_thinking_spinner
            from agent.turn_truncation import RefusalVerdict

            stop_thinking_spinner(agent, bound.arguments.get("thinking_spinner"))
            active_system_prompt = bound.arguments["active_system_prompt"]
            interrupted = self.wait(
                agent, _retry, attempt, delays, messages=bound.arguments["messages"],
                conversation_history=bound.arguments["conversation_history"],
                api_call_count=bound.arguments["api_call_count"], detail=_refusal_detail(bound.arguments["response"]),
            )
            if interrupted is not None:
                self.forget(agent)
                return RefusalVerdict("return", interrupted, active_system_prompt)
            if not _retry.restart_with_redirected_messages:
                # Same restart the fallback activation uses: the loop refunds the iteration and
                # re-sends this request; its restart bound still applies.
                _retry.restart_with_rebuilt_messages = True
            return RefusalVerdict("break", None, active_system_prompt)

        setattr(handle_content_policy_refusal, _MARK, original)
        handle_content_policy_refusal.__doc__ = original.__doc__
        return handle_content_policy_refusal

    # -- refusal reported as an API error (content_policy_blocked) --------------------------

    def wrap_unrecovered(self, original: Callable) -> Callable:
        signature = inspect.signature(original)

        def settle_unrecovered_error(*args, **kwargs):
            from agent.error_classifier import FailoverReason

            bound = signature.bind(*args, **kwargs)
            agent, classified = bound.arguments["agent"], bound.arguments["classified"]
            if getattr(classified, "reason", None) != FailoverReason.content_policy_blocked or agent._has_pending_fallback():
                return original(*args, **kwargs)
            delays = self.delays()
            attempt = self.next_refusal(agent)
            if attempt > len(delays):
                self.forget(agent)
                return self.give_up(original(*args, **kwargs), delays)
            from agent.turn_api_error import UnrecoveredErrorVerdict

            _retry = bound.arguments["_retry"]
            arguments = bound.arguments

            def outcome(action: str, result: Optional[dict] = None):
                # handle_api_error already counted this attempt; a refusal retry does not spend
                # the transport retry budget.
                return UnrecoveredErrorVerdict(
                    action=action, active_system_prompt=arguments["active_system_prompt"],
                    retry_count=max(0, arguments["retry_count"] - 1),
                    compression_attempts=arguments["compression_attempts"], result=result,
                )

            interrupted = self.wait(
                agent, _retry, attempt, delays, messages=arguments["messages"],
                conversation_history=arguments["conversation_history"],
                api_call_count=arguments["api_call_count"], detail=str(arguments["api_error"]),
            )
            if interrupted is not None:
                self.forget(agent)
                return outcome("return", interrupted)
            if _retry.restart_with_redirected_messages:
                return outcome("break")
            return outcome("continue")

        setattr(settle_unrecovered_error, _MARK, original)
        settle_unrecovered_error.__doc__ = original.__doc__
        return settle_unrecovered_error


def _refusal_detail(response: Any) -> str:
    try:
        choice = (getattr(response, "choices", None) or [None])[0]
        message = getattr(choice, "message", None)
        return str(getattr(message, "refusal", None) or getattr(response, "stop_details", None) or "")
    except Exception:
        return ""


def _unwrapped(function: Callable) -> Callable:
    return getattr(function, _MARK, function)


def compatibility() -> list:
    """Problems that keep the retry from installing on this Hermes; empty when it fits."""
    problems = []
    try:
        import agent.turn_api_error as api_error
        import agent.turn_response_check as response_check
        import agent.turn_truncation as truncation
        from agent.error_classifier import FailoverReason
        from agent.turn_retry_state import TurnRetryState
        from agent.turn_api_call import stop_thinking_spinner  # noqa: F401
        from agent.turn_recovery import interruptible_backoff_sleep  # noqa: F401
    except ImportError as error:
        return [f"Hermes module missing: {error}"]
    if not hasattr(FailoverReason, "content_policy_blocked"):
        problems.append("FailoverReason.content_policy_blocked is gone")
    fields = getattr(TurnRetryState, "__dataclass_fields__", {})
    for name in ("restart_with_rebuilt_messages", "restart_with_redirected_messages"):
        if name not in fields:
            problems.append(f"TurnRetryState.{name} is gone")
    checks = (
        (truncation, "handle_content_policy_refusal", _REFUSAL_PARAMS),
        (api_error, "settle_unrecovered_error", _UNRECOVERED_PARAMS),
    )
    for module, name, required in checks:
        function = getattr(module, name, None)
        if not callable(function):
            problems.append(f"{module.__name__}.{name} is gone")
            continue
        missing = required - set(inspect.signature(_unwrapped(function)).parameters)
        if missing:
            problems.append(f"{module.__name__}.{name} lost parameters {sorted(missing)}")
    if getattr(response_check, "handle_content_policy_refusal", None) is None:
        problems.append("agent.turn_response_check no longer imports handle_content_policy_refusal")
    for cls, module, fields_needed in (("RefusalVerdict", truncation, {"action", "result", "active_system_prompt"}),
                                       ("UnrecoveredErrorVerdict", api_error,
                                        {"action", "active_system_prompt", "retry_count", "compression_attempts", "result"})):
        verdict = getattr(module, cls, None)
        if verdict is None or not fields_needed <= set(getattr(verdict, "__dataclass_fields__", {})):
            problems.append(f"{module.__name__}.{cls} changed shape")
    return problems


def install(retry: RefusalRetry) -> bool:
    """Wrap both refusal paths once per process. False (Hermes untouched) when they do not fit."""
    problems = compatibility()
    if problems:
        log.warning("refusal-retry inactive, this Hermes version does not fit: %s", "; ".join(problems))
        return False
    import agent.turn_api_error as api_error
    import agent.turn_response_check as response_check
    import agent.turn_truncation as truncation

    refusal = retry.wrap_refusal(_unwrapped(truncation.handle_content_policy_refusal))
    truncation.handle_content_policy_refusal = refusal
    response_check.handle_content_policy_refusal = refusal
    api_error.settle_unrecovered_error = retry.wrap_unrecovered(_unwrapped(api_error.settle_unrecovered_error))
    log.info("refusal-retry active: delays %s s", list(retry.delays()))
    return True


def uninstall() -> None:
    import agent.turn_api_error as api_error
    import agent.turn_response_check as response_check
    import agent.turn_truncation as truncation

    original = _unwrapped(truncation.handle_content_policy_refusal)
    truncation.handle_content_policy_refusal = original
    response_check.handle_content_policy_refusal = original
    api_error.settle_unrecovered_error = _unwrapped(api_error.settle_unrecovered_error)
