import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch


class InstalledImagePresets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path.home() / '.local/share/local-image-studio/app/server.py'
        spec = importlib.util.spec_from_file_location('paint_presets', path)
        assert spec is not None and spec.loader is not None
        cls.server = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {'PATH': '/usr/bin:/bin'}):
            spec.loader.exec_module(cls.server)

    def test_picker_exposes_only_installed_models(self):
        self.assertEqual(set(self.server.MODELS), {'qwen-t2i', 'qwen-edit'})
        for model in self.server.MODELS.values():
            self.assertTrue(Path(model['model']).is_dir())
            self.assertTrue(Path(model['bin']).is_file())

    def test_generation_uses_local_weights_and_memory_saving(self):
        spec = self.server.MODELS['qwen-t2i']
        command = self.server.build_cmd(spec, 'test prompt', 30, 3.5, [42], '', None, 1024, 1024, 'test.png')
        self.assertIn('--low-ram', command)
        self.assertIn('qwen-image', command)
        self.assertTrue(any(value.endswith('/qwen-image-2512-mflux-q6') for value in command))
        self.assertNotIn('--quantize', command)

    def test_edit_uses_verified_2509_architecture_and_reference(self):
        spec = self.server.MODELS['qwen-edit']
        self.assertEqual(spec['steps'], 4)
        self.assertEqual(spec['guidance'], 1.0)
        self.assertFalse(spec['neg'])
        command = self.server.build_cmd(spec, 'make it blue', spec['steps'], spec['guidance'], [42], '', None, 1024, 1024, 'test.png', 'input.png')
        self.assertEqual(command[command.index('--base-model') + 1], 'qwen-image-edit')
        self.assertTrue(command[command.index('-m') + 1].endswith('/qwen-image-edit-2511-mflux-q8'))
        self.assertIn('2509', spec['label'])
        self.assertIn('--low-ram', command)
        self.assertIn('--no-bake-lora', command)
        self.assertEqual(command[command.index('--scheduler') + 1], 'lightning_scheduler.LightningScheduler')
        self.assertTrue(Path(command[command.index('--lora-paths') + 1]).is_file())
        self.assertEqual(command[command.index('--image-paths') + 1], 'input.png')


if __name__ == '__main__':
    unittest.main()
