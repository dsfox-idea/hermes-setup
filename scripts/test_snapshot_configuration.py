import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from snapshot import SetupSnapshot


class ConfigurationExportTests(unittest.TestCase):
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
