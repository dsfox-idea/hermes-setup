"""Behavior of the /heretic command (run with ``hermes --run-module unittest``)."""

import importlib.util
import inspect
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("heretic_route_under_test", PACKAGE / "route.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


route = _load()


class FakeOllama:
    def __init__(self, answers=None, error=None):
        self.answers = list(answers or [])
        self.error = error
        self.calls = []

    def __call__(self, url, body, timeout):
        self.calls.append((url, body))
        if self.error:
            raise self.error
        content = self.answers.pop(0) if self.answers else "ok"
        return {"message": {"role": "assistant", "content": content}, "eval_count": 50, "eval_duration": 1e9}


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.ollama = FakeOllama(["first answer", "second answer"])
        self.command = route.HereticRoute(route.History(self.directory, pairs=2), transport=self.ollama)

    def test_answer_comes_from_ollama_with_a_footer(self):
        output = self.command("hello", session_id="s1")
        self.assertTrue(output.startswith("first answer"))
        self.assertIn("heretic · 50 tok · 50 tok/s", output)
        url, body = self.ollama.calls[0]
        self.assertEqual(url, "http://127.0.0.1:11434/api/chat")
        self.assertEqual(body["model"], "qwen36-35b-heretic:q5km")
        self.assertFalse(body["think"])
        self.assertEqual(body["messages"], [{"role": "user", "content": "hello"}])

    def test_the_session_keeps_its_own_history(self):
        self.command("one", session_id="s1")
        self.command("two", session_id="s1")
        messages = self.ollama.calls[1][1]["messages"]
        self.assertEqual([m["content"] for m in messages], ["one", "first answer", "two"])

    def test_sessions_do_not_share_history(self):
        self.command("one", session_id="s1")
        self.command("two", session_id="s2")
        self.assertEqual(len(self.ollama.calls[1][1]["messages"]), 1)

    def test_history_keeps_only_the_last_pairs(self):
        self.ollama.answers = ["a1", "a2", "a3", "a4"]
        for text in ("q1", "q2", "q3", "q4"):
            self.command(text, session_id="s1")
        sent = [m["content"] for m in self.ollama.calls[-1][1]["messages"]]
        self.assertEqual(sent, ["q2", "a2", "q3", "a3", "q4"])

    def test_think_flag_turns_thinking_on_and_is_not_sent_as_text(self):
        output = self.command("--think why", session_id="s1")
        body = self.ollama.calls[0][1]
        self.assertTrue(body["think"])
        self.assertEqual(body["messages"][-1]["content"], "why")
        self.assertIn("thinking", output)

    def test_reset_clears_history(self):
        self.command("one", session_id="s1")
        self.assertEqual(self.command("--reset", session_id="s1"), "heretic: history cleared")
        self.command("two", session_id="s1")
        self.assertEqual(len(self.ollama.calls[-1][1]["messages"]), 1)

    def test_empty_text_makes_no_call(self):
        self.assertIn("empty message", self.command("   ", session_id="s1"))
        self.assertEqual(self.ollama.calls, [])

    def test_unreachable_ollama_is_reported_and_not_remembered(self):
        command = route.HereticRoute(route.History(self.directory),
                                     transport=FakeOllama(error=urllib.error.URLError("refused")))
        output = command("hello", session_id="s1")
        self.assertIn("local model unavailable", output)
        self.assertIn("nothing was sent to the cloud", output)
        self.assertEqual(route.History(self.directory).load("s1"), [])

    def test_empty_answer_is_not_remembered(self):
        self.ollama.answers = [""]
        self.assertIn("empty answer", self.command("hello", session_id="s1"))
        self.assertEqual(route.History(self.directory).load("s1"), [])

    def test_russian_text_round_trips_through_history(self):
        self.ollama.answers = ["Привет"]
        self.command("Здравствуй", session_id="s1")
        stored = route.History(self.directory).load("s1")
        self.assertEqual([m["content"] for m in stored], ["Здравствуй", "Привет"])


class CompatibilityTests(unittest.TestCase):
    def test_this_hermes_fits(self):
        """The command API this plugin relies on: register_command with args_hint, session context."""
        from hermes_cli.plugin_command_dispatch import invoke_plugin_command
        from hermes_cli.plugins import PluginContext

        self.assertIn("args_hint", inspect.signature(PluginContext.register_command).parameters)
        seen = {}

        def handler(raw_args="", session_id="", **_context):
            seen.update(raw=raw_args, session=session_id)
            return "done"

        self.assertEqual(invoke_plugin_command(handler, "hi", session_id="abc", session_key="k",
                                               source=None, platform="tui"), "done")
        self.assertEqual(seen, {"raw": "hi", "session": "abc"})


if __name__ == "__main__":
    unittest.main()
