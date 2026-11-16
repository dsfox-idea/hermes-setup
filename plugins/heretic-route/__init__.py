"""``/heretic``: one full agent turn on the local Heretic model, hidden from the cloud model. See ``route.py``."""

from .route import DEFAULT_ALIAS, HereticRoute, HereticRunner, ViewStore, view_directory


def _settings() -> dict:
    from hermes_cli.config import load_config_readonly

    return (load_config_readonly() or {}).get("heretic_route") or {}


def register(ctx) -> None:
    alias = str(_settings().get("alias") or DEFAULT_ALIAS)
    route = HereticRoute(ViewStore(view_directory()), HereticRunner(alias))
    ctx.register_command(
        "heretic", route,
        description="Run this turn on the local Heretic model, hidden from the cloud. In the TUI: _text, or __text with thinking",
        args_hint="[--think] [--reset] <text>",
    )
