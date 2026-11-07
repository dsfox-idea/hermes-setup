"""Validate explicit Spark marker and endpoint boundaries without inference."""

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch


class SparkRoutingTests(unittest.TestCase):
    def module(self):
        path = Path(__file__).with_name("spark_call.py")
        if not path.is_file():
            self.fail("Spark dispatch helper is not installed")
        spec = importlib.util.spec_from_file_location("spark_call", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_leading_marker_preserves_task(self):
        module = self.module()
        self.assertEqual(module.SparkRequest("@spark Run script --key 'A.B'").task,
                         "Run script --key 'A.B'")
        self.assertEqual(module.SparkRequest(" \n@SPARK\nRead the log").task, "Read the log")

    def test_quoted_embedded_and_empty_markers_are_rejected(self):
        module = self.module()
        for value in ["@spark", "@spark   ", "@sparkle run", "Text @spark run", "> @spark run",
                      "`@spark run`", "```\n@spark run\n```", "@heretic run", "@spark: run"]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    module.SparkRequest(value)

    def test_native_request_factory_is_guarded_before_creation(self):
        module = self.module()
        route = type("Route", (), {"model": "spark-x2.6-4b", "base_url": module.SparkRoute.BASE_URL})()
        factory = Mock(return_value="request-client")
        guard = module.LocalRequestGuard(factory, route, "Complete parent system")
        payload = {"model": route.model, "messages": [{"role": "system", "content": "Complete parent system"},
                                                       {"role": "user", "content": "Task"}], "max_tokens": 4096}
        with patch.object(guard, "post", side_effect=[{"prompt": "rendered"}, {"tokens": [1, 2, 3]}]):
            self.assertEqual(guard(reason="chat_completion_stream_request", api_kwargs=payload), "request-client")
        factory.assert_called_once()
        self.assertEqual(len(guard.requests), 1)
        self.assertEqual(guard.requests[0]["model"], route.model)
        rejected = module.LocalRequestGuard(Mock(), route, "Different parent system")
        with patch.object(rejected, "post") as post, self.assertRaises(ValueError):
            rejected(reason="chat_completion_stream_request", api_kwargs=payload)
        post.assert_not_called()
        rejected.factory.assert_not_called()
        oversized = module.LocalRequestGuard(Mock(), route, "Complete parent system")
        with patch.object(oversized, "post", side_effect=[{"prompt": "large"}, {"tokens": [0] * 65536}]), self.assertRaises(ValueError):
            oversized(reason="chat_completion_stream_request", api_kwargs=payload)
        oversized.factory.assert_not_called()

    def run_invocation_with_native_result(self, result):
        module = self.module()
        scratch = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))) / "cache/scratch"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="spark-result-test-", dir=scratch) as directory:
            route = SimpleNamespace(model="spark-x2.6-4b", provider="custom",
                                    base_url="http://127.0.0.1:18320/v1", reasoning={"enabled": False})
            parent_info = {"system_prompt": "Complete parent system", "model": "cloud",
                           "provider": "openai-codex", "cwd": directory}
            parent = SimpleNamespace(read=AsyncMock(return_value=parent_info), session_id="test-parent")
            agent = Mock(provider="custom", _fallback_chain=[], _last_turn_usage={})
            agent.run_conversation.return_value = result
            guard = Mock(requests=[{"model": route.model}])
            modules = {"run_agent": SimpleNamespace(AIAgent=Mock(return_value=agent)),
                       "hermes_constants": SimpleNamespace(get_hermes_home=lambda: Path(directory))}
            with patch.dict(sys.modules, modules), patch.object(module, "SparkRoute", return_value=route), patch.object(module, "LocalRequestGuard", return_value=guard):
                return module.SparkInvocation(module.SparkRequest("@spark Task"), parent, "").run()

    def test_incomplete_native_results_are_not_successful_answers(self):
        results = [
            {"completed": False, "partial": True, "error": "Response remained truncated after 4 continuation attempts", "final_response": "partial text"},
            {"completed": False, "turn_exit_reason": "max_iterations_reached(8/8)", "final_response": "interim summary"},
            {"completed": False, "interrupted": True, "error": "interrupted", "final_response": "partial text"},
            {"completed": True, "partial": True, "final_response": "partial text"},
            {"completed": True, "failed": True, "final_response": "failure text"},
            {"final_response": "missing completion state"},
        ]
        for result in results:
            with self.subTest(result=result), self.assertRaises(RuntimeError) as failure:
                self.run_invocation_with_native_result(result)
            reason = result.get("error") or result.get("turn_exit_reason")
            if reason:
                self.assertIn(reason, str(failure.exception))

    def test_completed_native_answer_is_returned_verbatim(self):
        result = self.run_invocation_with_native_result({"completed": True, "failed": False,
                                                        "interrupted": False, "final_response": "  Exact answer\n"})
        self.assertEqual(result["response"], "  Exact answer\n")
        self.assertIs(result.get("completed"), True)

    def test_only_the_installed_local_route_is_accepted(self):
        module = self.module()
        module.SparkRoute.validate("spark-x2.6-4b", "custom", "http://127.0.0.1:18320/v1")
        for arguments in [("gpt-6.1-sol", "openai-codex", "https://api.openai.com/v1"),
                          ("spark-x2.6-4b", "custom", "https://example.org/v1"),
                          ("another-model", "custom", "http://127.0.0.1:18320/v1")]:
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    module.SparkRoute.validate(*arguments)


if __name__ == "__main__":
    unittest.main(verbosity=2)
