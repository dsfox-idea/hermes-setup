from pathlib import Path
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
        self.calls = []
        self.installer = SetupInstaller(HermesInstall(self.home, root / "checkout"), self.repository,
                                        run=lambda command, **_: self.calls.append(command[2:]))

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
