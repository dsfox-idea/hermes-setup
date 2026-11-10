"""Optional reviewer installation uses explicit, bounded targets."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace

from install_review import ReviewInstaller


class ReviewInstallationTests(unittest.TestCase):
    def fixture(self, root):
        repository = root / 'setup'
        checkout = root / 'source'
        home = root / 'profile'
        checkout.mkdir()
        subprocess.run(['git', 'init', '-q', str(checkout)], check=True)
        (checkout / 'example.txt').write_text('before\n')
        patch = 'diff --git a/example.txt b/example.txt\n--- a/example.txt\n+++ b/example.txt\n@@ -1 +1 @@\n-before\n+after\n'
        (repository / 'patches').mkdir(parents=True)
        (repository / 'patches/response-review-host.patch').write_text(patch)
        (repository / 'upstream.json').write_text(json.dumps({'response_review': {'patch_sha256': hashlib.sha256(patch.encode()).hexdigest()}}))
        for relative in ('plugins/heretic-reviewer/plugin.yaml', 'plugins/heretic-reviewer/__init__.py',
                         'skills/autonomous-ai-agents/heretic/scripts/request.py'):
            target = repository / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('fixture\n')
        calls = []
        def cli(arguments, **kwargs):
            calls.append((arguments, kwargs['env']['HERMES_HOME']))
            return SimpleNamespace(stdout=json.dumps([{'name': 'heretic-reviewer', 'status': 'enabled'}]), returncode=0)
        return ReviewInstaller(repository, checkout, home, run_cli=cli), calls

    def test_install_requires_explicit_host_patch_permission(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            installer, calls = self.fixture(Path(directory))
            with self.assertRaises(RuntimeError):
                installer.install(apply_host_patch=False)
            self.assertEqual((installer.checkout / 'example.txt').read_text(), 'before\n')
            self.assertFalse(installer.home.exists())
            self.assertFalse(calls)

    def test_incomplete_plugin_is_refused_before_host_changes(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            installer, calls = self.fixture(Path(directory))
            (installer.repository / 'plugins/heretic-reviewer/__init__.py').unlink()
            with self.assertRaises(ValueError):
                installer.install(apply_host_patch=True)
            self.assertEqual((installer.checkout / 'example.txt').read_text(), 'before\n')
            self.assertFalse(calls)

    def test_replace_backs_up_only_conflicting_owned_files(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            installer, _ = self.fixture(Path(directory))
            target = installer.home / 'plugins/heretic-reviewer/plugin.yaml'
            target.parent.mkdir(parents=True)
            target.write_text('previous owned file\n')
            unrelated = target.parent / 'operator-notes.txt'
            unrelated.write_text('keep\n')
            result = installer.install(apply_host_patch=True, replace=True)
            self.assertEqual((Path(result['backup']) / target.relative_to(installer.home)).read_text(), 'previous owned file\n')
            self.assertEqual(unrelated.read_text(), 'keep\n')
            self.assertEqual(target.read_text(), 'fixture\n')

    def test_install_applies_patch_and_enables_only_selected_profile(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            installer, calls = self.fixture(Path(directory))
            result = installer.install(apply_host_patch=True)
            self.assertEqual((installer.checkout / 'example.txt').read_text(), 'after\n')
            self.assertTrue(result['host_patch_present'])
            self.assertTrue((installer.home / 'plugins/heretic-reviewer/plugin.yaml').is_file())
            self.assertTrue(all(home == str(installer.home) for _, home in calls))
            installer.install(apply_host_patch=False)
            self.assertEqual((installer.checkout / 'example.txt').read_text(), 'after\n')

    def test_conflicting_plugin_is_preserved_before_host_changes(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            installer, calls = self.fixture(Path(directory))
            target = installer.home / 'plugins/heretic-reviewer/plugin.yaml'
            target.parent.mkdir(parents=True)
            target.write_text('owned changes\n')
            with self.assertRaises(FileExistsError):
                installer.install(apply_host_patch=True)
            self.assertEqual(target.read_text(), 'owned changes\n')
            self.assertEqual((installer.checkout / 'example.txt').read_text(), 'before\n')
            self.assertFalse(calls)

    def test_symlink_destination_cannot_escape_profile(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            root = Path(directory)
            installer, calls = self.fixture(root)
            installer.home.mkdir()
            (root / 'outside').mkdir()
            (installer.home / 'plugins').symlink_to(root / 'outside', target_is_directory=True)
            with self.assertRaises(ValueError):
                installer.install(apply_host_patch=True)
            self.assertEqual(list((root / 'outside').iterdir()), [])
            self.assertFalse(calls)


if __name__ == '__main__':
    unittest.main()
