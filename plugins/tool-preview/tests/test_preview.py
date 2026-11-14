"""Tool-row preview length against the real Hermes modules (run with ``hermes --run-module unittest``)."""

import importlib.util
from pathlib import Path
import sys
import unittest

PACKAGE = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("tool_preview_under_test", PACKAGE / "preview.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


preview = _load()
COMMAND = "PY=../installs/844109ed257dabf0/environments/0ab708392d764744b7b12a48e16ec4da/venv/Scripts/python.exe -c 'print(1)'"


class CompatibilityTests(unittest.TestCase):
    def test_this_hermes_fits(self):
        self.assertEqual(preview.compatibility(), [])


class WrapperTests(unittest.TestCase):
    def setUp(self):
        import agent.display as display

        self.display = display
        self.length = 0
        self.assertTrue(preview.install(lambda: self.length))
        self.addCleanup(preview.uninstall)

    def test_the_hard_coded_80_follows_the_setting(self):
        from agent.display import build_tool_preview

        self.assertIn("python.exe -c", build_tool_preview("terminal", {"command": COMMAND}, max_len=80))
        self.length = 40
        self.assertLessEqual(len(build_tool_preview("terminal", {"command": COMMAND}, max_len=80)), 40)

    def test_other_limits_are_left_alone(self):
        from agent.display import build_tool_preview

        self.assertLessEqual(len(build_tool_preview("terminal", {"command": COMMAND}, max_len=64)), 64)

    def test_gateway_turn_payload_gets_the_full_command(self):
        from gateway.run_turn_progress import _tool_lifecycle_payload

        payload = _tool_lifecycle_payload("call-1", "terminal", {"command": COMMAND})
        self.assertIn("python.exe -c", payload["context"])

    def test_install_twice_wraps_once_and_uninstall_restores(self):
        self.assertTrue(preview.install(lambda: self.length))
        original = getattr(self.display.build_tool_preview, preview._MARK)
        self.assertFalse(hasattr(original, preview._MARK))
        preview.uninstall()
        self.assertIs(self.display.build_tool_preview, original)

    def test_bad_setting_means_no_limit(self):
        self.assertEqual(preview.normalize_length("x"), 0)
        self.assertEqual(preview.normalize_length(-5), 0)
        self.assertEqual(preview.normalize_length("120"), 120)
        self.assertEqual(preview.normalize_length(None), 0)


if __name__ == "__main__":
    unittest.main()
