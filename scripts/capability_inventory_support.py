"""Metadata projection and offline guard reused from the local doctor collector."""

from pathlib import Path
import traceback


class NativeFacts:
    @staticmethod
    def public_config(config, normalize, enabled):
        servers = config.get("mcp_servers") or {}
        if not isinstance(servers, dict):
            raise ValueError("Invalid MCP configuration shape")
        mcp = []
        for name, entry in sorted(servers.items()):
            if not isinstance(entry, dict):
                raise ValueError("Invalid MCP entry shape")
            mcp.append({"name": name, "prefix": "mcp__" + normalize(name) + "__", "enabled": enabled(entry)})
        curator = config.get("curator") or {}
        hooks = config.get("hooks") or {}
        plugins = config.get("plugins") or {}
        curator_keys = ("enabled", "interval_hours", "stale_after_days", "archive_after_days", "consolidate", "prune_builtins")
        if not isinstance(curator, dict) or not isinstance(plugins, dict) or not isinstance(hooks, dict):
            raise ValueError("Invalid configuration section shape")
        if any(not isinstance(curator[key], (bool, int, float)) for key in curator_keys if key in curator):
            raise ValueError("Invalid curator scalar")
        if any(not isinstance(plugins[key], list) or not all(isinstance(name, str) for name in plugins[key]) for key in ("enabled", "disabled") if key in plugins):
            raise ValueError("Invalid plugin names")
        return {"mcp": mcp,
                "curator": {key: curator[key] for key in curator_keys if key in curator},
                "hooks": [{"event": event, "configured_entries": len(entries) if isinstance(entries, list) else 1,
                           "timing": "unmeasured"} for event, entries in sorted(hooks.items())] if isinstance(hooks, dict) else [],
                "plugins": {key: plugins[key] for key in ("enabled", "disabled") if key in plugins}}

    @staticmethod
    def curator():
        from agent import curator
        from tools.skill_usage import curated_report, unmanaged_report
        return {"enabled": curator.is_enabled(), "paused": curator.is_paused(),
                "interval_hours": curator.get_interval_hours(), "stale_after_days": curator.get_stale_after_days(),
                "archive_after_days": curator.get_archive_after_days(), "consolidate": curator.get_consolidate(),
                "managed_count": len(curated_report()), "unmanaged_count": len(unmanaged_report())}


class OfflineBoundary:
    def __init__(self):
        self.blocked_connections = 0
        self.sources = []

    def check(self, event, arguments):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "socket.sendto", "socket.sendmsg"}:
            self.blocked_connections += 1
            if len(self.sources) < 3:
                self.sources.append([Path(frame.filename).name + ":" + frame.name for frame in traceback.extract_stack(limit=20)[:-1]])
            raise PermissionError("Doctor collection is offline")
