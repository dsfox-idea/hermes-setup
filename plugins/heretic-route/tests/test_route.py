"""Behavior of the /heretic command (run with ``hermes --run-module unittest``)."""

import importlib.util
import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("heretic_route_under_test", PACKAGE / "route.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


route = _load()


def user(text, at):
    return {"role": "user", "content": text, "timestamp": at, "_db_persisted": True}


def answer(text, at):
    return {"role": "assistant", "content": text, "timestamp": at}


class FakeRunner:
    """Stands in for the agent: records what Heretic was given and replies like a finished turn."""

    def __init__(self, cloud=None, replies=None, error=None):
        self.cloud = list(cloud or [])
        self.replies = list(replies or [])
        self.error = error
        self.calls = []

    def cloud_history(self, session):
        return list(self.cloud)

    def run(self, text, history, think):
        self.calls.append((text, list(history), think))
        if self.error:
            raise self.error
        reply = self.replies.pop(0) if self.replies else "ok"
        tool_call = {"id": "c1", "function": {"name": "terminal", "arguments": json.dumps({"command": "ls"})}}
        messages = list(history) + [{"role": "user", "content": text},
                                    {"role": "assistant", "content": "", "tool_calls": [tool_call]},
                                    {"role": "tool", "content": "a b", "tool_call_id": "c1"},
                                    {"role": "assistant", "content": reply}]
        return route.TurnResult(reply, messages, [route.ToolCall("terminal", "ls")], seconds=2.0, tokens=40)


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.store = route.ViewStore(Path(tempfile.mkdtemp()))
        self.cloud = [user("cloud question", 10.0), answer("cloud answer", 11.0)]
        self.runner = FakeRunner(self.cloud, ["first", "second"])
        self.command = route.HereticRoute(self.store, self.runner)

    def test_heretic_sees_the_cloud_conversation(self):
        self.command("what did we discuss", session_id="s1")
        text, history, think = self.runner.calls[0]
        self.assertEqual(text, "what did we discuss")
        self.assertEqual([m["content"] for m in history], ["cloud question", "cloud answer"])
        self.assertFalse(think)
        self.assertNotIn("_db_persisted", history[0])

    def test_heretic_remembers_its_own_turns_including_tools(self):
        self.command("one", session_id="s1")
        self.command("two", session_id="s1")
        history = self.runner.calls[1][1]
        self.assertEqual([m["role"] for m in history],
                         ["user", "assistant", "user", "assistant", "tool", "assistant"])
        self.assertEqual(history[-1]["content"], "first")

    def test_cloud_messages_are_appended_once(self):
        self.command("one", session_id="s1")
        self.runner.cloud += [user("later question", 20.0), answer("later answer", 21.0)]
        self.command("two", session_id="s1")
        contents = [m["content"] for m in self.runner.calls[1][1]]
        self.assertEqual(contents.count("cloud question"), 1)
        self.assertEqual(contents[-2:], ["later question", "later answer"])

    def test_an_unfinished_cloud_turn_waits_for_the_next_heretic_turn(self):
        self.runner.cloud.append(user("still running", 12.0))
        self.command("one", session_id="s1")
        self.assertNotIn("still running", [m["content"] for m in self.runner.calls[0][1]])
        self.runner.cloud.append(answer("done now", 13.0))
        self.command("two", session_id="s1")
        self.assertEqual([m["content"] for m in self.runner.calls[1][1]][-2:], ["still running", "done now"])

    def test_chats_do_not_share_views(self):
        self.command("one", session_id="s1")
        self.runner.cloud = []
        self.command("two", session_id="s2")
        self.assertEqual(self.runner.calls[1][1], [])

    def test_json_reply_carries_text_tools_and_footer(self):
        reply = json.loads(self.command("--json hello", session_id="s1"))
        self.assertEqual(reply["text"], "first")
        self.assertEqual(reply["tools"], [{"name": "terminal", "preview": "ls"}])
        self.assertIn("heretic · 40 tok · 2.0 s · 1 tools", reply["footer"])

    def test_plain_reply_for_other_surfaces(self):
        reply = self.command("hello", session_id="s1")
        self.assertIn("terminal ls", reply)
        self.assertIn("first", reply)

    def test_think_flag_is_passed_and_not_sent_as_text(self):
        self.command("--think --json why", session_id="s1")
        text, _, think = self.runner.calls[0]
        self.assertEqual(text, "why")
        self.assertTrue(think)

    def test_reset_clears_the_view(self):
        self.command("one", session_id="s1")
        self.assertIn("chat view cleared", self.command("--reset", session_id="s1"))
        self.runner.cloud = []
        self.command("two", session_id="s1")
        self.assertEqual(self.runner.calls[-1][1], [])

    def test_empty_text_makes_no_call(self):
        self.assertIn("empty message", self.command("  --json ", session_id="s1"))
        self.assertEqual(self.runner.calls, [])

    def test_a_failed_turn_is_reported_and_not_remembered(self):
        command = route.HereticRoute(self.store, FakeRunner(self.cloud, error=RuntimeError("connection refused")))
        reply = command("hello", session_id="s1")
        self.assertIn("connection refused", reply)
        self.assertIn("nothing was sent to the cloud", reply)
        self.assertEqual(self.store.load("s1").messages, [])

    def test_an_unreadable_chat_still_runs_the_turn(self):
        class NoStore(FakeRunner):
            def cloud_history(self, session):
                raise OSError("locked")

        runner = NoStore()
        route.HereticRoute(self.store, runner)("hello", session_id="s1")
        self.assertEqual(runner.calls[0][1], [])

    def test_empty_answer_is_not_remembered(self):
        self.runner.replies = [""]
        self.assertIn("empty answer", self.command("hello", session_id="s1"))
        self.assertEqual(self.store.load("s1").messages, [])

    def test_a_corrupt_view_file_starts_fresh(self):
        self.store.directory.mkdir(parents=True, exist_ok=True)
        (self.store.directory / "s1.view.json").write_text("{not json", encoding="utf-8")
        self.command("hello", session_id="s1")
        self.assertEqual(len(self.runner.calls[0][1]), 2)

    def test_russian_text_round_trips_through_the_view(self):
        self.runner.replies = ["Привет"]
        self.command("Здравствуй", session_id="s1")
        stored = self.store.load("s1").messages
        self.assertEqual(stored[-1]["content"], "Привет")


class MergeTests(unittest.TestCase):
    def test_a_slice_never_starts_with_a_tool_result(self):
        cloud = [{"role": "tool", "content": "x", "timestamp": 5.0}, user("q", 6.0), answer("a", 7.0)]
        view = route.ChatView().merged(cloud)
        self.assertEqual([m["role"] for m in view.messages], ["user", "assistant"])
        self.assertEqual(view.cloud_seen, 7.0)

    def test_nothing_new_keeps_the_mark(self):
        view = route.ChatView([], 9.0).merged([user("old", 5.0), answer("old", 6.0)])
        self.assertEqual((view.messages, view.cloud_seen), ([], 9.0))


class CompatibilityTests(unittest.TestCase):
    def test_this_hermes_fits(self):
        """The Hermes APIs this plugin relies on."""
        from agent.display import build_tool_preview
        from hermes_cli.oneshot import _oneshot_clarify_callback, _resolve_model_and_provider
        from hermes_cli.plugin_command_dispatch import invoke_plugin_command
        from hermes_cli.plugins import PluginContext
        from hermes_cli.runtime_provider import resolve_runtime_provider
        from hermes_state import SessionDB
        from hermes_state_registry import acquire, release
        from run_agent import AIAgent

        self.assertIn("args_hint", inspect.signature(PluginContext.register_command).parameters)
        self.assertIn("repair_alternation", inspect.signature(SessionDB.get_messages_as_conversation).parameters)
        for name in ("session_db", "clarify_callback", "reasoning_config", "enabled_toolsets"):
            self.assertIn(name, inspect.signature(AIAgent.__init__).parameters)
        self.assertIn("max_len", inspect.signature(build_tool_preview).parameters)
        self.assertTrue(all(callable(f) for f in (_oneshot_clarify_callback, _resolve_model_and_provider,
                                                  resolve_runtime_provider, acquire, release)))
        seen = {}

        def handler(raw_args="", session_id="", **_context):
            seen.update(raw=raw_args, session=session_id)
            return "done"

        self.assertEqual(invoke_plugin_command(handler, "hi", session_id="abc", session_key="k",
                                               source=None, platform="tui"), "done")
        self.assertEqual(seen, {"raw": "hi", "session": "abc"})


if __name__ == "__main__":
    unittest.main()
