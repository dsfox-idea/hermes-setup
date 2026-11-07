from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tui_overlay import HermesInstall, TuiOverlay

WANTED = {"hermes_commit": "a" * 40, "patch_sha256": "b" * 64}


class TuiOverlayProductTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="overlay-test-")
        home = Path(self.temporary.name)
        self.overlay = TuiOverlay(HermesInstall(home, home / "checkout"), home / "hermes-tui.patch")
        self.overlay.root.mkdir()
        patcher = patch.object(TuiOverlay, "wanted", return_value=WANTED)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.temporary.cleanup()

    def test_each_build_gets_its_own_directory(self):
        self.assertEqual(self.overlay.product.name, "ui-tui-aaaaaaaaaa-bbbbbbbbbb")

    def test_prune_keeps_the_current_product_and_removes_older_ones(self):
        self.overlay.product.mkdir()
        old = self.overlay.root / "ui-tui"
        (old / "dist").mkdir(parents=True)
        self.overlay.prune()
        self.assertTrue(self.overlay.product.is_dir())
        self.assertFalse(old.exists())
        self.assertEqual(list(self.overlay.root.glob(".trash-*")), [])

    def test_prune_keeps_a_product_it_cannot_move(self):
        old = self.overlay.root / "ui-tui-old"
        old.mkdir()
        with patch.object(Path, "rename", side_effect=PermissionError("in use")):
            self.overlay.prune()
        self.assertTrue(old.is_dir())


if __name__ == "__main__":
    unittest.main()
