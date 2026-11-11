"""Refusal retries against the real Hermes turn loop (run with ``hermes --run-module unittest``)."""

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

PACKAGE = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("refusal_retry_under_test", PACKAGE / "retry.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


retry = _load()


class FakeClock:
    """Stands in for ``time`` inside ``agent.turn_recovery`` so backoff waits take no real time."""

    def __init__(self):
        self.now = 1000.0
        self.slept = 0.0

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds
        self.slept += seconds


def _refusal(text="Cyber safeguards flagged this message."):
    message = SimpleNamespace(content=None, tool_calls=None, reasoning=None, reasoning_content=None, refusal=text)
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")],
                           model="test/model", usage=None, id="refused")


def _answer(text="Done."):
    message = SimpleNamespace(content=text, tool_calls=None, reasoning=None, reasoning_content=None, refusal=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")],
                           model="test/model", usage=None, id="answer")


class _Blocked(Exception):
    status_code = 400

    def __init__(self):
        super().__init__("Error code: 400 - Your request was flagged by our safety system (content_filter)")


class CompatibilityTests(unittest.TestCase):
    def test_this_hermes_fits(self):
        self.assertEqual(retry.compatibility(), [])

    def test_delays_are_validated(self):
        self.assertEqual(retry.normalize_delays(None), (10.0, 60.0))
        self.assertEqual(retry.normalize_delays([1, 2.5]), (1.0, 2.5))
        self.assertEqual(retry.normalize_delays([]), ())
        for bad in ("10", [-1], [True], [10] * 6, [601]):
            with self.assertLogs("refusal-retry", "WARNING"):
                self.assertEqual(retry.normalize_delays(bad), (10.0, 60.0))


class TurnLoopTests(unittest.TestCase):
    """A whole ``AIAgent.run_conversation`` with a mocked provider client."""

    def setUp(self):
        from run_agent import AIAgent

        with patch("model_tools.get_tool_definitions", return_value=[]), \
                patch("model_tools.check_toolset_requirements", return_value={}), \
                patch("agent.process_bootstrap.OpenAI"):
            self.agent = AIAgent(api_key="placeholder", base_url="https://openrouter.ai/api/v1",
                                 quiet_mode=True, skip_context_files=True, skip_memory=True)
        self.agent.client = MagicMock()
        self.agent._cached_system_prompt = "You are helpful."
        self.agent._use_prompt_caching = False
        self.agent.compression_enabled = False
        self.agent.save_trajectories = False
        self.notices = []
        self.agent._emit_diagnostic_status = self.notices.append
        self.delays = [10, 60]
        retry.install(retry.RefusalRetry(lambda: self.delays))
        self.addCleanup(retry.uninstall)
        self.clock = FakeClock()

    def run_turn(self, *outcomes):
        self.agent.client.chat.completions.create.side_effect = list(outcomes)
        with patch.object(self.agent, "_persist_session"), patch.object(self.agent, "_save_trajectory"), \
                patch.object(self.agent, "_cleanup_task_resources"), \
                patch("agent.turn_recovery.time", self.clock):
            return self.agent.run_conversation("scan my own server for the CVE")

    def calls(self):
        return self.agent.client.chat.completions.create.call_count

    def test_two_refusals_then_an_answer(self):
        result = self.run_turn(_refusal(), _refusal(), _answer("Patched."))
        self.assertEqual(result.get("final_response"), "Patched.")
        self.assertFalse(result.get("failed"))
        self.assertEqual(self.calls(), 3)
        self.assertAlmostEqual(self.clock.slept, 70.0, places=6)
        self.assertEqual(len([n for n in self.notices if "retrying automatically in 10 s (retry 1/2)" in n]), 1)
        self.assertEqual(len([n for n in self.notices if "retrying automatically in 60 s (retry 2/2)" in n]), 1)

    def test_third_refusal_ends_the_turn(self):
        result = self.run_turn(_refusal(), _refusal(), _refusal(), _answer("never sent"))
        self.assertTrue(result.get("failed"))
        self.assertIn("content_policy_blocked", result.get("error", ""))
        self.assertIn("Cyber safeguards flagged", result.get("final_response", ""))
        self.assertIn("Retried 2 times (after 10 s, 60 s)", result.get("final_response", ""))
        self.assertEqual(self.calls(), 3)
        self.assertAlmostEqual(self.clock.slept, 70.0, places=6)

    def test_count_restarts_after_a_good_answer(self):
        self.run_turn(_refusal(), _refusal(), _answer("first"))
        self.notices.clear()
        self.clock.slept = 0.0
        result = self.run_turn(_refusal(), _refusal(), _answer("second"))
        self.assertEqual(result.get("final_response"), "second")
        self.assertAlmostEqual(self.clock.slept, 70.0, places=6)

    def test_blocked_api_error_is_retried_the_same_way(self):
        result = self.run_turn(_Blocked(), _Blocked(), _answer("Through."))
        self.assertEqual(result.get("final_response"), "Through.")
        self.assertEqual(self.calls(), 3)
        self.assertAlmostEqual(self.clock.slept, 70.0, places=6)

    def test_blocked_api_error_ends_after_the_last_retry(self):
        result = self.run_turn(_Blocked(), _Blocked(), _Blocked(), _answer("never sent"))
        self.assertTrue(result.get("failed"))
        self.assertEqual(result.get("failure_reason"), "content_policy_blocked")
        self.assertIn("Retried 2 times", result.get("final_response", ""))
        self.assertEqual(self.calls(), 3)

    def test_interrupt_during_the_wait_stops_the_turn(self):
        def interrupt_on_sleep(seconds):
            self.agent._interrupt_requested = True
            FakeClock.sleep(self.clock, seconds)

        self.clock.sleep = interrupt_on_sleep
        result = self.run_turn(_refusal(), _answer("never sent"))
        self.assertTrue(result.get("interrupted"))
        self.assertEqual(self.calls(), 1)

    def test_empty_delays_keep_stock_behavior(self):
        self.delays = []
        result = self.run_turn(_refusal(), _answer("never sent"))
        self.assertTrue(result.get("failed"))
        self.assertNotIn("Retried", result.get("final_response", ""))
        self.assertEqual(self.calls(), 1)
        self.assertEqual(self.clock.slept, 0.0)

    def test_configured_fallback_still_goes_first(self):
        with patch.object(self.agent, "_has_pending_fallback", return_value=True), \
                patch.object(self.agent, "_try_activate_fallback", return_value=False):
            result = self.run_turn(_refusal(), _answer("never sent"))
        self.assertTrue(result.get("failed"))
        self.assertEqual(self.clock.slept, 0.0)


if __name__ == "__main__":
    unittest.main()
