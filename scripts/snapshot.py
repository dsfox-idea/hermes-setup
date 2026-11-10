#!/usr/bin/env python3
"""Export the active Hermes setup without credentials or conversation data."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from artifact_policy import ArtifactPolicy


class SetupSnapshot:
    INVENTORY = "snapshot-inventory.json"
    # The repository is public: personal rules (SOUL.md), memory deployment notes and the
    # skill references that describe one owner's machines are never exported.
    MANAGED_FILES = {"config.example.json", "skins/dsfox-skin.yaml", "upstream.json", "patches/hermes-tui.patch"}
    MANAGED_FILES.add("patches/response-review-host.patch")
    HOST_PATCH_FILES = (
        "agent/response_review.py", "agent/turn_stop_gates.py", "gateway/local_viewer_events.py",
        "hermes_cli/plugins.py", "locales/en.yaml", "locales/ru.yaml", "tui_gateway/contracts/events.py",
        "tui_gateway/tool_progress.py", "apps/shared/src/gateway-contract.generated.ts",
        "apps/shared/src/gateway-contract.openrpc.json", "tests/agent/test_response_review.py",
        "tests/gateway/test_response_review_events.py",
    )
    MANAGED_PREFIXES = ("plugins/honcho/", "skills/autonomous-ai-agents/hermes-agent/", "skills/autonomous-ai-agents/heretic/", "skills/autonomous-ai-agents/local-spark/")
    PRIVATE_SKILL_FILES = {"references/multi-machine.md", "references/memory-providers.md",
                           "scripts/a2a-token-check.py", "scripts/honcho_recall_check.py"}
    MANAGED_PREFIXES += ("skills/creative/local-image-studio/",)
    MANAGED_PREFIXES += ("plugins/heretic-reviewer/",)
    EXCLUDED = {
        ".git", ".venv", "__pycache__", "node_modules", "secrets",
        "credentials", "docker-config", "logs", "backups", "cache",
    }
    TEXT_SUFFIXES = {".py", ".md", ".patch", ".sh", ".yaml", ".yml", ".toml", ".conf", ".filter", ".sb", ".mjs", ".js", ".swift", ".json"}

    def __init__(self, repository, profile, source, memory_source, check=False):
        self.repository = repository.resolve()
        self.profile = profile.resolve()
        self.source = source.resolve()
        self.memory_source = memory_source.resolve()
        self.check = check
        self.files = {}
        self.profile_config = {}

    @staticmethod
    def command(arguments, cwd=None, accepted=(0,), environment=None):
        result = subprocess.run(arguments, cwd=cwd, env=environment, capture_output=True, check=False)
        if result.returncode not in accepted:
            raise RuntimeError(f"Command failed: {arguments[0]} (exit {result.returncode})")
        return result.stdout

    def target(self, relative):
        ArtifactPolicy.require_public(relative)
        target = self.repository / relative
        current = target
        while current != self.repository:
            if current.is_symlink():
                raise ValueError(f"Symlink in snapshot target: {relative!r}")
            current = current.parent
        if not target.resolve().is_relative_to(self.repository):
            raise ValueError(f"Export target escapes repository: {relative}")
        return target

    def add(self, relative, data):
        self.target(relative)
        self.files[relative] = data.encode() if isinstance(data, str) else data

    def copy_file(self, source, relative):
        if source.is_symlink():
            source = source.resolve(strict=True)
        self.add(relative, source.read_bytes())

    def copy_tree(self, source, relative, required=True):
        if not source.is_dir():
            if required:
                raise FileNotFoundError(f"Required snapshot source is missing: {source}")
            return
        for path in sorted(source.rglob("*")):
            parts = path.relative_to(source).parts
            if any(part in self.EXCLUDED for part in parts):
                continue
            if not path.is_file() or path.is_symlink():
                continue
            if not ArtifactPolicy.is_public(path.relative_to(source).as_posix()):
                continue
            if relative.startswith("skills/") and path.relative_to(source).as_posix() in self.PRIVATE_SKILL_FILES:
                continue
            if path.suffix not in self.TEXT_SUFFIXES and path.name not in {"LICENSE", ".gitignore", "Dockerfile", "primary.enabled"}:
                continue
            self.copy_file(path, str(Path(relative) / path.relative_to(source)))

    def configuration(self):
        command = json.loads(self.command(["hermes", "--print-runtime-command"]))
        prefix, separator, _ = command[-1].rpartition("runpy.run_module(")
        if not separator:
            raise RuntimeError("Unsupported Hermes runtime bootstrap; inspect it before exporting")
        code = '''
import json
from hermes_cli.config_effective import load_user_config_effective
config = load_user_config_effective(fail_closed=True)
fields = {
    "model": {"provider", "default", "context_length"},
    "agent": {"reasoning_effort"},
    "approvals": {"mode"},
    "auth": {"adopt_external_logins", "codex_login_flow"},
    "display": {"skin", "interface", "tui_compact", "tui_theme", "tui_status_indicator", "show_reasoning", "show_cost", "timestamps", "streaming", "details_mode", "sections", "tui_statusbar", "inline_diffs", "status_bar"},
    "memory": {"provider"},
    "plugins": {"enabled", "disabled"},
}
result = {section: {key: value for key, value in config.get(section, {}).items() if key in allowed} for section, allowed in fields.items() if section in config}
result["timezone"] = config.get("timezone", "")
result["telemetry"] = {"shared_metrics": {key: value for key, value in config.get("telemetry", {}).get("shared_metrics", {}).items() if key in {"enabled", "send"}}}
result["compression"] = {"model_thresholds": config.get("compression", {}).get("model_thresholds", {})}
result["model_overrides"] = {provider: {model: {key: value for key, value in settings.items() if key == "context_window"} for model, settings in models.items()} for provider, models in config.get("model_overrides", {}).items()}
print(json.dumps(result, indent=2, sort_keys=True))
'''
        command[-1] = prefix + code
        data = json.loads(self.command(command, environment={**os.environ, "HERMES_HOME": str(self.profile)}))
        self.profile_config = data
        self.add("config.example.json", json.dumps(data, indent=2, sort_keys=True) + "\n")

    def source_patch(self):
        manifest = json.loads((self.repository / "upstream.json").read_text())
        revision = manifest["hermes"]["commit"]
        self.command(["git", "cat-file", "-e", revision + "^{commit}"], self.source)
        changed = self.command(["git", "diff", "--name-only", "-z", revision, "--"], self.source)
        untracked = self.command(["git", "ls-files", "--others", "--exclude-standard", "-z"], self.source)
        new_files = [name.decode() for name in untracked.split(b"\0") if name]
        for encoded in changed.split(b"\0"):
            if encoded:
                ArtifactPolicy.require_public(encoded.decode())
        for name in new_files:
            ArtifactPolicy.require_public(name)
            path = Path(name)
            if path.suffix not in {".py", ".ts", ".tsx", ".js", ".mjs", ".md", ".json", ".yaml", ".toml", ".sh"}:
                raise ValueError(f"Review untracked upstream artifact before export: {name}")
            if any(part in self.EXCLUDED for part in path.parts) or path.name.startswith(".env"):
                raise ValueError(f"Refusing private upstream artifact: {name}")
        self.command(["git", "diff", "--check", revision, "--"], self.source)
        patch = self.command(["git", "diff", "--binary", revision, "--"], self.source)
        for name in new_files:
            patch += self.command(["git", "diff", "--no-index", "--binary", "--", "/dev/null", name], self.source, accepted=(0, 1))
        self.add("patches/hermes-tui.patch", patch)
        host_patch = self.command(["git", "diff", "--binary", revision, "--", *self.HOST_PATCH_FILES], self.source)
        for name in new_files:
            if name in self.HOST_PATCH_FILES:
                host_patch += self.command(["git", "diff", "--no-index", "--binary", "--", "/dev/null", name], self.source, accepted=(0, 1))
        self.add("patches/response-review-host.patch", host_patch)
        manifest["response_review"] = {
            "path": "patches/response-review-host.patch",
            "patch_sha256": hashlib.sha256(host_patch).hexdigest(),
        }
        manifest["patch"] = {
            "path": "patches/hermes-tui.patch",
            "sha256": hashlib.sha256(patch).hexdigest(),
        }
        self.add("upstream.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    def memory(self):
        required = self.profile_config.get("memory", {}).get("provider") == "honcho"
        self.copy_tree(self.profile / "plugins/honcho", "plugins/honcho", required=required)

    def collect(self):
        self.configuration()
        self.copy_file(self.profile / "skins/dsfox-skin.yaml", "skins/dsfox-skin.yaml")
        self.copy_tree(self.profile / "skills/autonomous-ai-agents/hermes-agent", "skills/autonomous-ai-agents/hermes-agent")
        self.copy_tree(self.profile / "skills/autonomous-ai-agents/heretic", "skills/autonomous-ai-agents/heretic", required=False)
        self.copy_tree(self.profile / "skills/autonomous-ai-agents/local-spark", "skills/autonomous-ai-agents/local-spark", required=False)
        self.copy_tree(self.profile / "skills/creative/local-image-studio", "skills/creative/local-image-studio", required=False)
        self.copy_tree(self.profile / "plugins/heretic-reviewer", "plugins/heretic-reviewer", required=False)
        self.source_patch()
        self.memory()

    def previous_inventory(self):
        path = self.target(self.INVENTORY)
        if not path.exists():
            return {}
        data = json.loads(path.read_text())
        if data.get("format") not in {1, 2} or not isinstance(data.get("files"), dict):
            raise ValueError("Unrecognized snapshot inventory; inspect it before refreshing")
        previous = {}
        for name, entry in data["files"].items():
            if data["format"] == 2:
                if not isinstance(entry, dict) or set(entry) != {"sha256"}:
                    raise ValueError(f"Invalid inventory entry: {name}")
                digest = entry["sha256"]
            else:
                digest = entry
            ArtifactPolicy.require_public(name)
            if name not in self.MANAGED_FILES and not name.startswith(self.MANAGED_PREFIXES):
                raise ValueError(f"Inventory includes an unmanaged target: {name}")
            if not isinstance(digest, str) or len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
                raise ValueError(f"Invalid inventory digest: {name}")
            previous[name] = digest
        return previous

    def stale_files(self, previous):
        stale = sorted(set(previous) - set(self.files))
        for name in stale:
            path = self.target(name)
            if path.exists() and (not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != previous[name]):
                raise ValueError(f"Stale snapshot target was independently modified: {name}")
        return stale

    def run(self):
        previous = self.previous_inventory()
        self.collect()
        stale = self.stale_files(previous)
        inventory = {"format": 2, "files": {name: {"sha256": hashlib.sha256(content).hexdigest()} for name, content in sorted(self.files.items())}}
        self.add(self.INVENTORY, json.dumps(inventory, indent=2, sort_keys=True) + "\n")
        changed = []
        for relative, content in sorted(self.files.items()):
            path = self.target(relative)
            if path.is_file() and path.read_bytes() == content:
                continue
            changed.append(relative)
            if not self.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        if not self.check:
            for name in stale:
                self.target(name).unlink(missing_ok=True)
        print(json.dumps({"checked_files": len(self.files), "changed_files": changed, "removed_files": stale, "check_only": self.check}, indent=2))
        return 1 if self.check and (changed or stale) else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--memory-source", type=Path, default=Path.home() / "dev/honcho-local")
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    snapshot = SetupSnapshot(repository, arguments.profile, arguments.source or repository / "hermes-agent", arguments.memory_source, arguments.check)
    return snapshot.run()


if __name__ == "__main__":
    sys.exit(main())
