"""Local-only publication policy checks, using disposable Git repositories."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import shlex
import sys
import tempfile
import unittest


class PublicationGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.environment = {**os.environ, "GIT_AUTHOR_NAME": "Test Author",
                            "GIT_AUTHOR_EMAIL": "test@example.invalid", "GIT_COMMITTER_NAME": "Test Author",
                            "GIT_COMMITTER_EMAIL": "test@example.invalid"}
        self.git("init", "-q", "-b", "main")
        self.policy = self.root / "policy.json"
        self.rules = {"format": 1, "deny_paths": ["private/*", "*.bundle"],
                      "deny_patterns": ["PRIVATE_ONLY_SENTINEL"], "deny_commits": [], "deny_blobs": []}
        self.commit("README.md", "Public setup\n")

    def git(self, *arguments, check=True):
        return subprocess.run(["git", *arguments], cwd=self.repo, env=self.environment,
                              text=True, capture_output=True, check=check)

    def commit(self, name, content, message="Update fixture"):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        self.git("add", "--", name)
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD").stdout.strip()

    def guard(self):
        self.assertIsNotNone(importlib.util.find_spec("local_publication_guard"), "Publication history guard is missing")
        from local_publication_guard import PublicationGuard
        self.policy.write_text(json.dumps(self.rules))
        return PublicationGuard(self.repo, self.policy)

    def test_removed_private_content_still_blocks_history(self):
        self.commit("temporary.txt", "PRIVATE_ONLY_SENTINEL\n")
        self.git("rm", "-q", "temporary.txt")
        self.git("commit", "-q", "-m", "Remove fixture content")
        with self.assertRaises(ValueError):
            self.guard().check_revision(self.git("rev-parse", "HEAD").stdout.strip())

    def test_forbidden_commit_blocks_otherwise_clean_content(self):
        revision = self.git("rev-parse", "HEAD").stdout.strip()
        self.rules["deny_commits"] = [revision]
        with self.assertRaises(ValueError):
            self.guard().check_revision(revision)

    def test_private_path_blocks_innocuous_content(self):
        revision = self.commit("private/notes.txt", "Ordinary text\n")
        with self.assertRaises(ValueError):
            self.guard().check_revision(revision)

    def test_known_private_blob_is_blocked_under_another_name(self):
        revision = self.commit("renamed.txt", "Known restricted bytes\n")
        self.rules["deny_blobs"] = [self.git("rev-parse", "HEAD:renamed.txt").stdout.strip()]
        with self.assertRaises(ValueError):
            self.guard().check_revision(revision)

    def install_hook(self):
        self.guard()
        hook = self.repo / ".git/hooks/pre-push"
        command = [sys.executable, str(Path(__file__).with_name("local_publication_guard.py")),
                   "--policy", str(self.policy)]
        hook.write_text("#!/bin/sh\nexec " + shlex.join(command) + ' "$@"\n')
        hook.chmod(0o755)
        self.git("config", "--local", "core.hooksPath", str(hook.parent))
        remote = self.root / "remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True, capture_output=True)
        return remote

    def test_real_push_is_rejected_before_objects_reach_remote(self):
        revision = self.commit("payload.txt", "PRIVATE_ONLY_SENTINEL\n")
        remote = self.install_hook()
        pushed = self.git("push", str(remote), "main", check=False)
        self.assertNotEqual(pushed.returncode, 0, pushed.stderr)
        present = subprocess.run(["git", "cat-file", "-e", revision], cwd=remote, capture_output=True)
        self.assertNotEqual(present.returncode, 0)

    def test_clean_history_can_be_pushed_to_an_owned_local_remote(self):
        remote = self.install_hook()
        result = self.git("push", str(remote), "main", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        present = subprocess.check_output(["git", "rev-parse", "refs/heads/main"], cwd=remote, text=True).strip()
        self.assertEqual(present, self.git("rev-parse", "HEAD").stdout.strip())

    def test_missing_policy_blocks_a_clean_push(self):
        remote = self.install_hook()
        self.policy.unlink()
        self.assertNotEqual(self.git("push", str(remote), "main", check=False).returncode, 0)

    def test_required_wrapper_does_not_fall_back_when_configuration_is_missing(self):
        source = Path(__file__).with_name("publication-pre-push.sh")
        self.assertTrue(source.is_file(), "Publication wrapper is missing")
        hook = self.repo / ".git/hooks/pre-push"
        hook.write_bytes(source.read_bytes())
        hook.chmod(0o755)
        delegate = hook.with_name("publication-checks")
        delegate.write_text("#!/bin/sh\nexit 77\n")
        delegate.chmod(0o755)
        self.git("config", "--local", "localPublication.required", "true")
        result = subprocess.run([str(hook), "origin", "local-test"], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Required local publication policy is unavailable", result.stderr)

    def test_invalid_policy_is_not_silently_accepted(self):
        original = self.rules.copy()
        invalid = [dict(format=1, deny_paths=[], deny_patterns=[], deny_commits=[], deny_blobs=[]),
                   {**original, "deny_commits": ["malformed"]},
                   {**original, "deny_blobs": ["--option"]},
                   {**original, "format": True}]
        for policy in invalid:
            with self.subTest(policy=policy):
                self.rules = policy
                with self.assertRaises(ValueError):
                    self.guard()


if __name__ == "__main__":
    unittest.main()
