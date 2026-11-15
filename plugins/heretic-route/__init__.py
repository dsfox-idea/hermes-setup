"""``/heretic``: answer a message with the local Heretic model (Ollama), not the cloud. See ``route.py``."""

from .route import DEFAULT_MODEL, DEFAULT_URL, HereticRoute, History, history_directory


def _settings() -> dict:
    from hermes_cli.config import load_config_readonly

    return (load_config_readonly() or {}).get("heretic_route") or {}


def register(ctx) -> None:
    settings = _settings()
    route = HereticRoute(
        History(history_directory()),
        url=str(settings.get("url") or DEFAULT_URL),
        model=str(settings.get("model") or DEFAULT_MODEL),
    )
    ctx.register_command(
        "heretic", route,
        description="Ask the local Heretic model (free, no cloud). In the TUI: _text, or __text with thinking",
        args_hint="[--think] [--reset] <text>",
    )
