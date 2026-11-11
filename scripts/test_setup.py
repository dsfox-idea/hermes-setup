from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from setup import SKILL, SetupInstaller
from tui_overlay import HermesInstall


class SetupInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="setup-test-")
        root = Path(self.temporary.name)
        self.home, self.repository = root / "home", root / "repository"
        (self.home / "profiles" / "work").mkdir(parents=True)
        (self.home / "profiles" / "work" / "config.yaml").write_text("{}\n")
        (self.home / "profiles" / ".deleted" / "old").mkdir(parents=True)
        (self.repository / SKILL).mkdir(parents=True)
        (self.repository / SKILL / "SKILL.md").write_text("new skill\n")
        (self.repository / "skins").mkdir()
        (self.repository / "skins" / "dsfox-skin.yaml").write_text("name: dsfox-skin\n")
        plugin = self.repository / "plugins" / "refusal-retry"
        (plugin / "tests").mkdir(parents=True)
        (plugin / "__init__.py").write_text("def register(ctx): pass\n")
        (plugin / "plugin.yaml").write_text("name: refusal-retry\n")
        (plugin / "tests" / "test_retry.py").write_text("")
        self.calls = []
        self.check_exit = 0

        def run(command, **_):
            self.calls.append(command[1:] if command[1] == "--run-module" else command[2:])
            return SimpleNamespace(returncode=self.check_exit if command[1] == "--run-module" else 0,
                                   stdout="", stderr="FAILED: changed shape")

        self.installer = SetupInstaller(HermesInstall(self.home, root / "checkout"), self.repository, run=run)

    def tearDown(self):
        self.temporary.cleanup()

    def test_tombstone_directories_are_not_profiles(self):
        self.assertEqual([p.name for p in self.installer.profiles], ["default", "work"])

    def test_skin_reaches_every_profile_through_the_cli(self):
        with patch("setup.shutil.which", return_value="hermes"):
            self.installer.install_skin()
        self.assertTrue((self.home / "profiles" / "work" / "skins" / "dsfox-skin.yaml").is_file())
        self.assertIn(["work", "skin", "use", "dsfox-skin"], self.calls)
        self.assertIn(["default", "config", "set", "display.tui_compact", "true"], self.calls)

    def test_plugin_reaches_every_profile_without_its_tests(self):
        with patch("setup.shutil.which", return_value="hermes"):
            self.assertTrue(self.installer.install_plugin())
        for profile in self.installer.profiles:
            target = profile.home / "plugins" / "refusal-retry"
            self.assertTrue((target / "__init__.py").is_file())
            self.assertFalse((target / "tests").exists())
            self.assertTrue(self.installer.plugin_current(profile))
        self.assertIn(["work", "plugins", "enable", "refusal-retry", "--no-allow-tool-override"], self.calls)
        self.assertIn("test_this_hermes_fits", self.calls[-1])

    def test_plugin_that_does_not_fit_fails_the_install(self):
        self.check_exit = 1
        with patch("setup.shutil.which", return_value="hermes"), self.assertLogs("setup", "ERROR"):
            self.assertFalse(self.installer.install_plugin())

    def test_skill_is_backed_up_before_it_is_replaced(self):
        old = self.home / "profiles" / "work" / SKILL
        old.mkdir(parents=True)
        (old / "SKILL.md").write_text("my own notes\n")
        self.installer.install_skill()
        self.assertEqual((old / "SKILL.md").read_text(), "new skill\n")
        backups = list((self.home / "profiles" / "work" / "backups").glob(f"hermes-setup-*/{SKILL.as_posix()}/SKILL.md"))
        self.assertEqual([b.read_text() for b in backups], ["my own notes\n"])


    def test_uninstall_restores_stock_skin_and_drops_the_hook(self):
        hook = self.home / "hooks" / "tui-overlay"
        hook.mkdir(parents=True)
        (hook / "handler.py").write_text("")
        with patch("setup.shutil.which", return_value="hermes"), \
                patch.object(HermesInstall, "set_env") as set_env:
            self.installer.uninstall()
        set_env.assert_called_once_with("")
        self.assertFalse(hook.exists())
        self.assertIn(["work", "config", "set", "display.skin", "default"], self.calls)


if __name__ == "__main__":
    unittest.main()
