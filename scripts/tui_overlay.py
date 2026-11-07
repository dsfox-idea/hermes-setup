#!/usr/bin/env python3
"""Build the patched TUI outside the live Hermes checkout and point Hermes at it.

Hermes on Windows refuses to rewrite its own running checkout, and `hermes update`
stashes local edits. This keeps the checkout clean: the patch is applied to a
shared clone at the checkout's exact HEAD, the TUI is compiled into
<hermes home>/tui-overlay/ui-tui, and HERMES_TUI_DIR is written to every profile's
.env through `hermes config set`. When the patch no longer applies, HERMES_TUI_DIR
is cleared so Hermes falls back to its stock TUI instead of a stale bundle.

    python tui_overlay.py status   # is the overlay current for the checkout HEAD?
    python tui_overlay.py ensure   # rebuild when stale, then enable it
    python tui_overlay.py disable  # clear HERMES_TUI_DIR everywhere
    python tui_overlay.py install  # ensure + install the gateway:startup hook that re-runs ensure
"""

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys

log = logging.getLogger("tui-overlay")
ENV_KEY = "HERMES_TUI_DIR"


class HermesInstall:
    """The live Hermes home, its checkout and its profiles."""

    def __init__(self, home: Path, checkout: Path):
        self.home = home
        self.checkout = checkout

    @classmethod
    def detect(cls, home=None, checkout=None):
        if home is None:
            configured = os.environ.get("HERMES_HOME", "").strip()
            if configured:
                home = Path(configured)
            elif os.name == "nt":
                home = Path(os.environ["LOCALAPPDATA"]) / "hermes"
            else:
                home = Path.home() / ".hermes"
        home = Path(home)
        return cls(home, Path(checkout) if checkout else home / "hermes-agent")

    def head(self) -> str:
        return subprocess.check_output(["git", "-C", str(self.checkout), "rev-parse", "HEAD"], text=True).strip()

    def profiles(self) -> list:
        root = self.home / "profiles"
        names = sorted(p.name for p in root.iterdir() if (p / "config.yaml").is_file()) if root.is_dir() else []
        return [None, *names]

    def node(self) -> str:
        explicit = os.environ.get("HERMES_NODE", "").strip()
        if explicit and Path(explicit).is_file():
            return explicit
        suffix = "node.exe" if os.name == "nt" else "bin/node"
        for candidate in sorted((self.home / "tools").glob("node-*"), reverse=True):
            if (candidate / suffix).is_file():
                return str(candidate / suffix)
        found = shutil.which("node")
        if not found:
            raise RuntimeError("node not found")
        return found

    def set_env(self, value: str) -> None:
        hermes = shutil.which("hermes")
        if not hermes:
            raise RuntimeError("hermes CLI not found on PATH")
        for profile in self.profiles():
            command = [hermes, *(["-p", profile] if profile else []), "config", "set", ENV_KEY, value]
            subprocess.run(command, check=True, capture_output=True, text=True)
            log.info("%s=%r in profile %s", ENV_KEY, value, profile or "default")


class TuiOverlay:
    """Patched TUI product for one checkout HEAD plus one patch file."""

    def __init__(self, install: HermesInstall, patch: Path):
        self.install = install
        self.patch = patch
        self.root = install.home / "tui-overlay"
        self.product = self.root / "ui-tui"
        self.source = self.root / "source"
        self.state_file = self.root / "overlay.json"

    def wanted(self) -> dict:
        return {"hermes_commit": self.install.head(),
                "patch_sha256": hashlib.sha256(self.patch.read_bytes()).hexdigest()}

    def current(self) -> bool:
        try:
            saved = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return saved == self.wanted() and (self.product / "dist" / "entry.js").is_file()

    def ensure(self) -> int:
        if self.current():
            log.info("overlay is current for %s", self.wanted()["hermes_commit"][:10])
            self.install.set_env(str(self.product))
            return 0
        # A stale bundle must never run against a newer gateway: fall back first.
        self.install.set_env("")
        try:
            self.build()
        except Exception:
            log.exception("overlay build failed; Hermes stays on its stock TUI")
            return 1
        self.install.set_env(str(self.product))
        return 0

    def build(self) -> None:
        wanted = self.wanted()
        self.remove_source()
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            self.compile(wanted)
        finally:
            self.remove_source()

    def compile(self, wanted: dict) -> None:
        self.git("clone", "-q", "--shared", "--no-checkout", str(self.install.checkout), str(self.source))
        self.git("-C", str(self.source), "checkout", "-q", "--detach", wanted["hermes_commit"])
        self.git("-C", str(self.source), "apply", "--check", str(self.patch))
        self.git("-C", str(self.source), "apply", str(self.patch))
        for relative in ("node_modules", "ui-tui/node_modules"):
            self.link(self.install.checkout / relative, self.source / relative)
        node = self.install.node()
        subprocess.run([node, str(self.source / "scripts/build/tui.mjs"), "--source", str(self.source),
                        "--out", str(self.product)], check=True, cwd=self.source,
                       env={**os.environ, "NODE_ENV": "production"})
        subprocess.run([node, "--check", str(self.product / "dist" / "entry.js")], check=True)
        self.state_file.write_text(json.dumps(wanted, indent=2) + "\n", encoding="utf-8")
        log.info("built overlay for %s at %s", wanted["hermes_commit"][:10], self.product)

    def remove_source(self) -> None:
        if not self.source.exists():
            return
        # Unlink the dependency links first so no tree walk can reach the live node_modules.
        for relative in ("node_modules", "ui-tui/node_modules"):
            link = self.source / relative
            if link.is_symlink() or self.is_junction(link):
                os.unlink(link) if link.is_symlink() else os.rmdir(link)
        shutil.rmtree(self.source)

    @staticmethod
    def is_junction(path: Path) -> bool:
        return hasattr(os.path, "isjunction") and os.path.isjunction(path)

    @staticmethod
    def link(target: Path, link: Path) -> None:
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
        else:
            link.symlink_to(target, target_is_directory=True)

    @staticmethod
    def git(*arguments: str) -> None:
        subprocess.run(["git", *arguments], check=True)


class StartupHook:
    """Copies hooks/tui-overlay into the default profile and records this clone's path in it."""

    def __init__(self, install: HermesInstall, repository: Path):
        self.source = repository / "hooks" / "tui-overlay"
        self.target = install.home / "hooks" / "tui-overlay"
        self.repository = repository

    def install(self) -> None:
        self.target.mkdir(parents=True, exist_ok=True)
        for name in ("HOOK.yaml", "handler.py"):
            shutil.copyfile(self.source / name, self.target / name)
        (self.target / "setup-repo.txt").write_text(str(self.repository) + "\n", encoding="utf-8")
        log.info("installed gateway hook %s (active after the next gateway start)", self.target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("status", "ensure", "disable", "install"))
    parser.add_argument("--hermes-home")
    parser.add_argument("--checkout")
    parser.add_argument("--patch", default=str(Path(__file__).resolve().parent.parent / "patches/hermes-tui.patch"))
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    install = HermesInstall.detect(arguments.hermes_home, arguments.checkout)
    overlay = TuiOverlay(install, Path(arguments.patch))
    if arguments.action == "status":
        print(json.dumps({"current": overlay.current(), **overlay.wanted(), "product": str(overlay.product)}))
        return 0
    if arguments.action == "disable":
        install.set_env("")
        return 0
    if arguments.action == "install":
        StartupHook(install, Path(__file__).resolve().parent.parent).install()
    return overlay.ensure()


if __name__ == "__main__":
    sys.exit(main())
