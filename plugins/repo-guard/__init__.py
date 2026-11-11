"""Ask the owner before a tool call leaves the session's git repository. See ``guard.py``.

Extra roots that never count as foreign: ``plugins.entries.repo-guard.settings.allow``
(a list of directories).
"""

from .guard import RepoGuard


def _session_cwd() -> str:
    from hermes_cli.plugin_session import session_cwd
    return session_cwd()


def register(ctx) -> None:
    manager = getattr(ctx, "_manager", None)

    def cwd() -> str:
        # The classic CLI process keeps its launch directory; gateway sessions record theirs.
        if manager is not None and getattr(manager, "_cli_ref", None) is not None:
            import os
            return os.getcwd()
        return _session_cwd()

    guard = RepoGuard(cwd, allowed=lambda: ctx.get_config("allow", []) or [])
    ctx.register_hook("pre_tool_call", guard.on_pre_tool_call)
