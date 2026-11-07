import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

import mlx.core as mx
import numpy as np
from mflux.models.qwen.model.qwen_text_encoder.qwen_attention import QwenAttention
from mflux.models.qwen.model.qwen_text_encoder.qwen_encoder import QwenEncoder
from mflux.models.qwen.qwen_initializer import QwenImageInitializer
from mflux.models.common.config.model_config import ModelConfig


class PositionRecorder:
    def __call__(self, hidden, positions):
        self.positions = np.array(positions)
        return None


class TinyEncoder(QwenEncoder):
    def __init__(self):
        super().__init__(vocab_size=32, hidden_size=28, num_hidden_layers=0)
        self.image_token_id = 9

    def get_image_features(self, pixels, grids):
        return [mx.zeros((int(np.prod(grid)) // 4, 28)) for grid in grids.tolist()]


class ConditioningChecks(unittest.TestCase):
    def positions(self, tokens, grids, mask=None):
        encoder = TinyEncoder()
        recorder = PositionRecorder()
        encoder.rotary_emb = recorder
        ids = mx.array([tokens])
        encoder(ids, mx.array([mask]) if mask is not None else mx.ones_like(ids),
                mx.zeros((1,)) if grids is not None else None,
                mx.array(grids) if grids is not None else None)
        return recorder.positions[:, 0]

    def test_image_tokens_receive_spatial_positions(self):
        actual = self.positions([1, 2, 9, 9, 9, 9, 3, 4], [[1, 4, 4]])
        expected = [[0, 1, 2, 2, 2, 2, 4, 5],
                    [0, 1, 2, 2, 3, 3, 4, 5],
                    [0, 1, 2, 3, 2, 3, 4, 5]]
        np.testing.assert_array_equal(actual, expected)

    def test_text_only_positions_are_unchanged(self):
        np.testing.assert_array_equal(self.positions([1, 2, 3], None), [[0, 1, 2]] * 3)

    def test_positions_ignore_padding(self):
        expected = self.positions([1, 2, 9, 9, 9, 9, 3, 4], [[1, 4, 4]])
        actual = self.positions([0, 1, 2, 9, 9, 9, 9, 3, 4, 0], [[1, 4, 4]], [0] + [1] * 8 + [0])
        np.testing.assert_array_equal(actual[:, 1:-1], expected)
        np.testing.assert_array_equal(actual[:, [0, -1]], np.ones((3, 2)))

    def test_multiple_images_use_independent_spatial_grids(self):
        actual = self.positions([1, 9, 9, 9, 9, 2, 9, 9, 3], [[1, 4, 4], [1, 2, 4]])
        expected = [[0, 1, 1, 1, 1, 3, 4, 4, 6],
                    [0, 1, 1, 2, 2, 3, 4, 4, 6],
                    [0, 1, 2, 1, 2, 3, 4, 5, 6]]
        np.testing.assert_array_equal(actual, expected)

    def test_mismatched_image_grid_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'token count'):
            self.positions([1, 9, 9, 3], [[1, 4, 4]])

    def test_edit_initializer_uses_picture_prefix(self):
        tokenizer = SimpleNamespace(image_token_id=9, video_token_id=10)
        model = SimpleNamespace(tokenizers={'qwen': SimpleNamespace(tokenizer=tokenizer)},
                                text_encoder=SimpleNamespace(encoder=TinyEncoder()))
        with ExitStack() as stack:
            for method in ('_load_weights', '_init_tokenizers', '_init_edit_models', '_apply_weights', '_apply_lora'):
                stack.enter_context(patch.object(QwenImageInitializer, method))
            QwenImageInitializer.init_edit(model, ModelConfig.qwen_image_edit(), None, 'unused')
        self.assertTrue(model.tokenizers['qwen_vl'].use_picture_prefix)

    def test_rotary_channels_repeat_temporal_height_width(self):
        query = mx.ones((1, 1, 2, 128))
        cosine = mx.stack([mx.full((1, 2, 128), value) for value in (1, 2, 3)])
        result, _ = QwenAttention._apply_multimodal_rotary_pos_emb(
            query, query, (cosine, mx.zeros_like(cosine)), [16, 24, 24]
        )
        expected = np.array(([1] * 16 + [2] * 24 + [3] * 24) * 2)
        np.testing.assert_array_equal(np.array(result[0, 0, 0]), expected)

    def test_rotary_text_only_axes_remain_identical(self):
        query = mx.ones((1, 1, 2, 128))
        cosine = mx.ones((3, 1, 2, 128))
        result, _ = QwenAttention._apply_multimodal_rotary_pos_emb(
            query, query, (cosine, mx.zeros_like(cosine)), [16, 24, 24]
        )
        np.testing.assert_array_equal(np.array(result), np.array(query))


if __name__ == '__main__':
    unittest.main()
