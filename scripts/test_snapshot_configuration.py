import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from snapshot import SetupSnapshot


class ConfigurationExportTests(unittest.TestCase):
    def test_isolated_snapshot_cli_resolves_its_own_support_module(self):
        result = subprocess.run([sys.executable, '-I', str(Path(__file__).with_name('snapshot.py')), '--help'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--profile', result.stdout)

    def test_optional_reviewer_excludes_runtime_cache(self):
        with tempfile.TemporaryDirectory(prefix='snapshot-review-') as temporary:
            directory = Path(temporary)
            profile = directory / 'profile'
            for name in ('skins/dsfox-skin.yaml', 'skills/autonomous-ai-agents/hermes-agent/SKILL.md',
                         'plugins/heretic-reviewer/plugin.yaml', 'plugins/heretic-reviewer/runtime.py',
                         'plugins/heretic-reviewer/cache/private.json'):
                target = profile / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('Fixture content\n')
            snapshot = SetupSnapshot(directory / 'repository', profile, directory, directory)
            with patch.object(snapshot, 'configuration'), patch.object(snapshot, 'source_patch'), patch.object(snapshot, 'memory'):
                snapshot.collect()
            self.assertEqual(snapshot.files.get('plugins/heretic-reviewer/runtime.py'), b'Fixture content\n')
            self.assertNotIn('plugins/heretic-reviewer/cache/private.json', snapshot.files)

    def test_generated_evaluation_data_is_not_publishable(self):
        from artifact_policy import ArtifactPolicy
        self.assertFalse(ArtifactPolicy.is_public('evaluation-runs/inventory.json'))

    def test_optional_image_skill_and_references_are_included(self):
        with tempfile.TemporaryDirectory(prefix='snapshot-skill-') as temporary:
            directory = Path(temporary)
            profile = directory/'profile'
            for name in ('SOUL.md','skins/dsfox-skin.yaml','skills/autonomous-ai-agents/hermes-agent/SKILL.md',
                         'skills/creative/local-image-studio/SKILL.md','skills/creative/local-image-studio/references/mode.md'):
                target = profile/name
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text('Fixture content\n')
            snapshot = SetupSnapshot(directory/'repository',profile,directory,directory)
            with patch.object(snapshot,'configuration'), patch.object(snapshot,'source_patch'), patch.object(snapshot,'memory'):
                snapshot.collect()
            self.assertEqual(snapshot.files.get('skills/creative/local-image-studio/references/mode.md'),b'Fixture content\n')

    @unittest.skipUnless(shutil.which('hermes'), 'Hermes launcher is required')
    def test_approval_mode_is_exported_from_the_selected_profile(self):
        with tempfile.TemporaryDirectory(prefix='snapshot-profile-') as temporary:
            directory = Path(temporary)
            profile = directory/'profile'
            profile.mkdir()
            repository = directory/'repository'
            repository.mkdir()
            (profile/'config.yaml').write_text(json.dumps({
                'model': {'provider': 'custom', 'default': 'snapshot-fixture-model'},
                'approvals': {'mode': 'off', 'private_field': 'not-for-export'},
            }))
            snapshot = SetupSnapshot(repository, profile, directory, directory)
            snapshot.configuration()
            exported = json.loads(snapshot.files['config.example.json'])
            self.assertEqual(exported['model']['default'], 'snapshot-fixture-model')
            self.assertEqual(exported['approvals'], {'mode': 'off'})


if __name__ == '__main__':
    unittest.main()
