"""Behavior checks for the explicit local request helper; no model calls."""

import unittest
from unittest.mock import patch
import copy
from pathlib import Path
import subprocess

from request import HereticRequest


class RequestTests(unittest.TestCase):
    def test_tokenizer_uses_the_requested_profile_home(self):
        completed = subprocess.CompletedProcess([], 0, stdout='{"input_tokens": 1}')
        with patch.dict("os.environ", {"HERMES_HOME": "/launch-profile"}), patch(
            "request.subprocess.run", return_value=completed
        ) as child:
            HereticRequest.count_tokens(Path("/served-profile"), {})
        self.assertEqual(child.call_args.kwargs["env"]["HERMES_HOME"], "/served-profile")

    def test_response_is_verbatim_and_failures_are_not_answers(self):

        response = {"choices": [{"finish_reason": "stop", "message": {
            "content": "  Exact answer\n", "reasoning": "Considered"}}]}
        self.assertEqual(HereticRequest.accept_response(response), ("  Exact answer\n", 10))
        for mutation in ("length", "empty", "tool", "no_reasoning"):
            invalid = copy.deepcopy(response)
            choice = invalid["choices"][0]
            if mutation == "length":
                choice["finish_reason"] = "length"
            elif mutation == "empty":
                choice["message"]["content"] = ""
            elif mutation == "tool":
                choice["message"]["tool_calls"] = [{"function": {"name": "terminal"}}]
            else:
                choice["message"].pop("reasoning")
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                HereticRequest.accept_response(invalid)

    def test_context_limit_refuses_instead_of_truncating(self):

        boundary = HereticRequest.CONTEXT_WINDOW - HereticRequest.MAX_TOKENS
        HereticRequest.check_budget(boundary)
        with self.assertRaises(ValueError):
            HereticRequest.check_budget(boundary + 1)

    def test_unavailable_server_has_no_fallback(self):

        with patch("http.client.HTTPConnection") as connection:
            connection.return_value.request.side_effect = ConnectionRefusedError("Unavailable")
            with self.assertRaises(ConnectionRefusedError):
                HereticRequest.local_call(HereticRequest.payload("System", "Task", ""))
            connection.assert_called_once_with("127.0.0.1", 18319, timeout=300)

    def test_exact_system_and_context_survive_request(self):

        system = "  Exact system\n\n"
        payload = HereticRequest.payload(system, "Task", "Prior answer\n")
        self.assertEqual(payload["messages"][0], {"role": "system", "content": system})
        self.assertIn("Task", payload["messages"][1]["content"])
        self.assertIn("Prior answer\n", payload["messages"][1]["content"])
        self.assertTrue(payload["chat_template_kwargs"]["enable_thinking"])
        self.assertNotIn("tools", payload)
        with self.assertRaises(ValueError):
            HereticRequest.payload("", "Task", "")

    def test_only_explicit_leading_marker_is_accepted(self):

        self.assertEqual(HereticRequest.parse("@heretic Write a function."), "Write a function.")
        self.assertEqual(HereticRequest.parse(" \n@heretic\nTask"), "Task")
        for message in ("Task", "Explain @heretic", "> @heretic Task", "`@heretic Task`",
                        "```\n@heretic Task\n```", "@hereticx Task", "@Heretic Task", "@heretic", "@heretic \n"):
            with self.subTest(message=message), self.assertRaises(ValueError):
                HereticRequest.parse(message)


if __name__ == "__main__":
    unittest.main()
