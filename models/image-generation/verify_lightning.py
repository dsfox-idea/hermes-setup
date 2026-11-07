import unittest

import numpy as np
from mflux.models.common.config.config import Config
from mflux.models.common.config.model_config import ModelConfig
from lightning_scheduler import LightningScheduler


class LightningChecks(unittest.TestCase):
    def test_four_step_schedule_matches_author_recipe(self):
        base = ModelConfig.qwen_image_edit()
        original_shift = base.sigma_base_shift
        config = Config(width=1024, height=1024, num_inference_steps=4,
                        guidance=1.0, model_config=base)
        scheduler = LightningScheduler(config)
        np.testing.assert_allclose(np.array(scheduler.sigmas), [1.0, .9, .75, .5, 0], atol=1e-6)
        self.assertEqual(base.sigma_base_shift, original_shift)

    def test_incompatible_step_count_is_rejected(self):
        config = Config(width=512, height=512, num_inference_steps=30,
                        guidance=1.0, model_config=ModelConfig.qwen_image_edit())
        with self.assertRaises(ValueError):
            LightningScheduler(config)

    def test_incompatible_guidance_is_rejected(self):
        config = Config(width=512, height=512, num_inference_steps=4,
                        guidance=2.5, model_config=ModelConfig.qwen_image_edit())
        with self.assertRaises(ValueError):
            LightningScheduler(config)


if __name__ == '__main__':
    unittest.main()
