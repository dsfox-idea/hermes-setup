#!/usr/bin/env python3
"""Install or remove this repository's Hermes customization in every profile.

    python3 scripts/setup.py install [--skill] [--timezone Area/City]
    python3 scripts/setup.py status
    python3 scripts/setup.py uninstall

`install` copies the skin into every profile, selects it with the TUI interface and
compact transcript, builds the patched TUI overlay (scripts/tui_overlay.py) and
installs its gateway hook, then installs and enables the refusal-retry and
repo-guard plugins.
`--skill` also replaces the profile's hermes-agent skill after backing it up.
Every step goes through the Hermes CLI or plain file copies; the Hermes checkout
is never modified.
"""

import argparse
from datetime import datetime
import logging
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tui_overlay import HermesInstall, StartupHook, TuiOverlay  # noqa: E402

log = logging.getLogger("setup")
REPOSITORY = Path(__file__).resolve().parent.parent
SKIN = "dsfox-skin"
SKILL = Path("skills/autonomous-ai-agents/hermes-agent")
# Plugins installed in every profile, each with the test that proves it fits this Hermes (or None).
PLUGINS = {"refusal-retry": "test_this_hermes_fits", "repo-guard": None}
PLUGIN_SKIP = ("__pycache__", "tests")


class Profile:
    """One Hermes profile: its name for `hermes -p` and its home directory."""

    def __init__(self, install: HermesInstall, name):
        self.name = name or "default"
        self.home = install.home if name is None else install.home / "profiles" / name

    def backup(self, relative: Path, stamp: str) -> None:
        source = self.home / relative
        if not source.exists():
            return
        target = self.home / "backups" / f"hermes-setup-{stamp}" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if source.is_dir() else shutil.copyfile)(source, target)
        log.info("backed up %s to %s", source, target)


class SetupInstaller:
    def __init__(self, install: HermesInstall, repository: Path = REPOSITORY, run=subprocess.run):
        self.install = install
        self.repository = repository
        self.run = run
        self.stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.profiles = [Profile(install, name) for name in install.profiles()]

    def hermes(self, profile: Profile, *arguments: str) -> None:
        executable = shutil.which("hermes")
        if not executable:
            raise RuntimeError("hermes CLI not found on PATH")
        self.run([executable, "-p", profile.name, *arguments], check=True, capture_output=True, text=True)

    def install_skin(self) -> None:
        for profile in self.profiles:
            (profile.home / "skins").mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.repository / "skins" / f"{SKIN}.yaml", profile.home / "skins" / f"{SKIN}.yaml")
            self.hermes(profile, "skin", "use", SKIN)
            self.hermes(profile, "config", "set", "display.interface", "tui")
            self.hermes(profile, "config", "set", "display.tui_compact", "true")
            log.info("skin %s active in profile %s", SKIN, profile.name)

    def install_overlay(self) -> bool:
        StartupHook(self.install, self.repository).install()
        if TuiOverlay(self.install, self.repository / "patches" / "hermes-tui.patch").ensure() != 0:
            log.error("patched TUI not built; colors and branding still apply, the stock TUI stays")
            return False
        for profile in self.profiles:
            self.hermes(profile, "config", "set", "display.tui_status_indicator", "activity")
        return True

    def plugin_files(self, name: str) -> dict:
        source = self.repository / "plugins" / name
        return {path.relative_to(source): path.read_bytes() for path in sorted(source.rglob("*"))
                if path.is_file() and not set(path.relative_to(source).parts) & set(PLUGIN_SKIP)}

    def plugin_current(self, profile: Profile, name: str) -> bool:
        target = profile.home / "plugins" / name
        return all((target / relative).is_file() and (target / relative).read_bytes() == data
                   for relative, data in self.plugin_files(name).items())

    def plugin_fits(self, name: str, test: str) -> bool:
        """Run the plugin's own compatibility test against this Hermes, in Hermes' interpreter."""
        executable = shutil.which("hermes")
        if not executable:
            raise RuntimeError("hermes CLI not found on PATH")
        result = self.run([executable, "--run-module", "unittest", "discover", "-s",
                           str(self.repository / "plugins" / name / "tests"), "-k", test],
                          capture_output=True, text=True)
        if result.returncode != 0:
            log.error("%s does not fit this Hermes version:\n%s", name, (result.stderr or result.stdout or "").strip())
        return result.returncode == 0

    def install_plugins(self) -> bool:
        ok = True
        for name, test in PLUGINS.items():
            source = self.repository / "plugins" / name
            for profile in self.profiles:
                target = profile.home / "plugins" / name
                shutil.rmtree(target, ignore_errors=True)
                shutil.copytree(source, target, ignore=shutil.ignore_patterns(*PLUGIN_SKIP))
                self.hermes(profile, "plugins", "enable", name, "--no-allow-tool-override")
                log.info("plugin %s enabled in profile %s", name, profile.name)
            if test and not self.plugin_fits(name, test):
                ok = False
        return ok

    def install_skill(self) -> None:
        for profile in self.profiles:
            profile.backup(SKILL, self.stamp)
            target = profile.home / SKILL
            shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(self.repository / SKILL, target)
            log.info("hermes-agent skill replaced in profile %s", profile.name)

    def set_timezone(self, zone: str) -> None:
        for profile in self.profiles:
            self.hermes(profile, "config", "set", "timezone", zone)

    def uninstall(self) -> None:
        self.install.set_env("")
        shutil.rmtree(self.install.home / "hooks" / "tui-overlay", ignore_errors=True)
        for profile in self.profiles:
            for name in PLUGINS:
                self.hermes(profile, "plugins", "disable", name)
                shutil.rmtree(profile.home / "plugins" / name, ignore_errors=True)
            self.hermes(profile, "config", "set", "display.skin", "default")
            self.hermes(profile, "config", "set", "display.tui_status_indicator", "kaomoji")
        log.info("stock skin and TUI restored; skill backups stay under <profile>/backups/")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("install", "status", "uninstall"))
    parser.add_argument("--skill", action="store_true", help="also replace the hermes-agent skill (backed up)")
    parser.add_argument("--timezone", help="also set the timezone, e.g. Europe/Berlin")
    parser.add_argument("--hermes-home")
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    install = HermesInstall.detect(arguments.hermes_home)
    installer = SetupInstaller(install)
    if arguments.action == "status":
        overlay = TuiOverlay(install, REPOSITORY / "patches" / "hermes-tui.patch")
        print(f"profiles: {', '.join(p.name for p in installer.profiles)}")
        print(f"patched TUI current: {overlay.current()}")
        for name in PLUGINS:
            print(f"{name} plugin current: {all(installer.plugin_current(p, name) for p in installer.profiles)}")
        return 0
    if arguments.action == "uninstall":
        installer.uninstall()
        return 0
    installer.install_skin()
    overlay_ok = installer.install_overlay()
    plugin_ok = installer.install_plugins()
    if arguments.skill:
        installer.install_skill()
    if arguments.timezone:
        installer.set_timezone(arguments.timezone)
    return 0 if overlay_ok and plugin_ok else 1


if __name__ == "__main__":
    sys.exit(main())
