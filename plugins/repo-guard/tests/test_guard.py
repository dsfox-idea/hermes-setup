"""repo-guard: which tool calls leave the session's repository (plain ``python3 -m unittest``)."""

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("repo_guard_under_test", PACKAGE / "guard.py")
guard = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = guard
spec.loader.exec_module(guard)


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="repo-guard-")
        root = Path(self.temporary.name).resolve()
        self.home = root / "home"
        self.mine = self.home / "dev" / "humans.top"
        self.other = self.home / "dev" / "dirty.news"
        self.service = self.home / "dev" / "hermes"
        self.nested = self.mine / "vendor" / "lib"
        for repo in (self.mine, self.other, self.nested):
            (repo / ".git").mkdir(parents=True)
        (self.mine / "src").mkdir()
        (self.other / "docs").mkdir()
        self.service.mkdir(parents=True)
        self.cwd = str(self.mine)
        self.guard = guard.RepoGuard(lambda: self.cwd, guard.Repositories(self.home))

    def tearDown(self):
        self.temporary.cleanup()

    def hit(self, tool, **args):
        return self.guard.on_pre_tool_call(tool_name=tool, args=args)

    def test_own_repository_passes(self):
        self.assertIsNone(self.hit("read_file", path=str(self.mine / "src" / "a.py")))
        self.assertIsNone(self.hit("write_file", path="src/new.py"))
        self.assertIsNone(self.hit("terminal", command=f"cd {self.mine} && git status"))
        self.assertIsNone(self.hit("search_files", pattern="x", path="."))

    def test_other_repository_asks_the_owner(self):
        for tool, args in (
            ("read_file", {"path": str(self.other / "docs" / "style.md")}),
            ("write_file", {"path": str(self.other / "new.py")}),
            ("patch", {"path": "../dirty.news/x.py"}),
            ("search_files", {"pattern": "x", "path": str(self.other)}),
            ("terminal", {"command": "ls", "workdir": str(self.other)}),
            ("terminal", {"command": f"cd {self.other} && ls"}),
            ("terminal", {"command": f"git -C {self.other} log -1"}),
            ("terminal", {"command": f"cat '{self.other}/docs/style.md'"}),
            ("terminal", {"command": "ls ../dirty.news"}),
            ("execute_code", {"code": f"open('{self.other}/x').read()"}),
        ):
            with self.subTest(tool=tool, args=args):
                directive = self.hit(tool, **args)
                self.assertEqual(directive["action"], "approve")
                self.assertIn("dirty.news", directive["message"])
                self.assertIn("humans.top", directive["message"])

    def test_home_relative_paths(self):
        real_home = guard.Path.home
        guard.Path.home = staticmethod(lambda: self.home)
        try:
            self.assertEqual(self.hit("terminal", command="cat ~/dev/dirty.news/a")["action"], "approve")
            self.assertEqual(self.hit("terminal", command="ls $HOME/dev/dirty.news")["action"], "approve")
            self.assertIsNone(self.hit("terminal", command="ls ~/dev/humans.top/src"))
        finally:
            guard.Path.home = real_home

    def test_rule_key_names_the_pair(self):
        directive = self.hit("read_file", path=str(self.other / "a"))
        self.assertEqual(directive["rule_key"], f"repo-guard:{self.mine}->{self.other}")

    def test_paths_outside_repositories_pass(self):
        self.assertIsNone(self.hit("read_file", path="/etc/hosts"))
        self.assertIsNone(self.hit("terminal", command=f"ls {self.home}/dev"))
        self.assertIsNone(self.hit("terminal", command="curl -s https://example.com/a/b"))
        self.assertIsNone(self.hit("terminal", command="ls /tmp/x && grep -rn foo src"))

    def test_nested_repository_counts_as_own(self):
        self.assertIsNone(self.hit("read_file", path=str(self.nested / "a.py")))

    def test_service_and_projectless_chats_are_not_checked(self):
        for cwd in (str(self.service), str(self.home), ""):
            self.cwd = cwd
            with self.subTest(cwd=cwd):
                self.assertIsNone(self.hit("read_file", path=str(self.other / "a")))

    def test_allowed_roots(self):
        allowed = guard.RepoGuard(lambda: self.cwd, guard.Repositories(self.home), allowed=lambda: [str(self.other)])
        self.assertIsNone(allowed.on_pre_tool_call(tool_name="read_file", args={"path": str(self.other / "a")}))

    def test_bad_input_never_raises(self):
        self.assertIsNone(self.guard.on_pre_tool_call(tool_name="terminal", args=None))
        self.assertIsNone(self.hit("terminal", command="echo 'unterminated"))


if __name__ == "__main__":
    unittest.main()
