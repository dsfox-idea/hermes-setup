import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from shared_rules import SharedRules


class RuleDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            dir=Path.home() / ".hermes/cache/scratch", prefix="rules-test-"
        )
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        (self.home / ".hermes").mkdir()
        self.soul = self.home / ".hermes/SOUL.md"
        self.soul.write_text("Shared rules\n", encoding="utf-8")
        self.project = self.home / "project"
        self.project.mkdir()
        (self.project / ".git").mkdir()

    def test_parent_to_child_order_and_repository_boundary(self):
        (self.home / "AGENTS.md").write_text("Outside repository")
        (self.project / "AGENTS.md").write_text("Root rules")
        child = self.project / "package"
        child.mkdir()
        (child / "AGENTS.md").write_text("Child rules")
        texts = [text for _, text in SharedRules(self.home, child).load()]
        self.assertEqual(texts, ["Shared rules\n", "Root rules", "Child rules"])

    def test_outside_repository_checks_current_directory_only(self):
        child = self.home / "outside"
        child.mkdir()
        (self.home / "AGENTS.md").write_text("Do not load")
        self.assertEqual(len(SharedRules(self.home, child).load()), 1)

    def test_override_then_empty_override_fallback(self):
        override = self.project / "AGENTS.override.md"
        override.write_text("Override rules")
        (self.project / "AGENTS.md").write_text("Normal rules")
        rules = SharedRules(self.home, self.project)
        self.assertEqual(rules.load()[-1][1], "Override rules")
        override.write_text("")
        self.assertEqual(rules.load()[-1][1], "Normal rules")

    def test_repeated_rules_are_not_duplicated(self):
        (self.project / "AGENTS.md").write_text("Repeated rules")
        child = self.project / "child"
        child.mkdir()
        (child / "AGENTS.md").write_text("Repeated rules")
        self.assertEqual(len(SharedRules(self.home, child).load()), 2)

    def test_missing_or_empty_soul_fails_instead_of_silently_skipping(self):
        self.soul.write_text("")
        with self.assertRaises(ValueError):
            SharedRules(self.home, self.project).load()
        self.soul.unlink()
        with self.assertRaises(FileNotFoundError):
            SharedRules(self.home, self.project).load()

    def test_updates_unicode_and_long_content_are_preserved(self):
        rules = SharedRules(self.home, self.project)
        original = rules.prompt()
        content = "\u041f\u0440\u0430\u0432\u0438\u043b\u0430\n" + "x" * 50000 + "\n__INPUT__\n"
        self.soul.write_text(content, encoding="utf-8")
        self.assertNotEqual(rules.prompt(), original)
        self.assertIn(content, rules.prompt())

    def test_lowercase_agents_and_git_worktree_marker(self):
        (self.project / ".git").rmdir()
        (self.project / ".git").write_text("gitdir: elsewhere\n")
        (self.project / "agents.md").write_text("Lowercase rules")
        self.assertEqual(SharedRules(self.home, self.project).load()[-1][1], "Lowercase rules")


class InstalledRulesTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("aichat"), "AIChat is required")
    def test_both_commands_include_complete_default_rules(self):
        root = Path(__file__).resolve().parents[2]
        soul = (Path.home() / ".hermes/SOUL.md").read_text(encoding="utf-8-sig")
        agents = (root / "AGENTS.md").read_text(encoding="utf-8-sig")
        for name in ("spark", "heretic"):
            with self.subTest(command=name):
                result = subprocess.run(
                    [str(root / "models/terminal" / name), "--dry-run", "RULES_PROBE"],
                    cwd=root, capture_output=True, text=True, timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                body = "\n".join(
                    line[4:] if line.startswith("    ") else line
                    for line in result.stdout.split("\n")
                )
                self.assertTrue(soul in body, "Complete SOUL.md was not loaded")
                self.assertTrue(agents in body, "Complete AGENTS.md was not loaded")


if __name__ == "__main__":
    unittest.main()
