"""Retry a provider safety-filter refusal a bounded number of times before the turn ends.

Delays come from ``plugins.entries.refusal-retry.settings.delays`` (seconds, default
``[10, 60]``); an empty list restores Hermes' stock behavior. See ``retry.py``.
"""

from .retry import DEFAULT_DELAYS, RefusalRetry, install


def register(ctx) -> None:
    install(RefusalRetry(lambda: ctx.get_config("delays", list(DEFAULT_DELAYS))))
