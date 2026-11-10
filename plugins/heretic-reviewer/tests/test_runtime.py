"""Pinned local inference reuses the existing Heretic request contract."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class RuntimeTests(unittest.TestCase):
    def test_exact_prompt_reasoning_and_verbatim_review_cross_the_local_boundary(self):
        helper = load("local_review_shared_helper", ROOT / "skills/autonomous-ai-agents/heretic/scripts/request.py")
        runtime = load("local_review_runtime", Path(__file__).resolve().parents[1] / "runtime.py")
        reviewer_module = load("local_review_capture", Path(__file__).resolve().parents[1] / "reviewer.py")
        response = {"model": helper.HereticRequest.MODEL, "choices": [{"finish_reason": "stop", "message": {
            "content": "  Original review.\n", "reasoning": "Considered the comparison."}}]}
        with tempfile.TemporaryDirectory() as directory, patch.object(
            helper.HereticRequest, "count_tokens", return_value=32
        ), patch.object(helper.HereticRequest, "local_call", return_value=response) as transport:
            client = runtime.LocalReviewClient(home=Path(directory), request_class=helper.HereticRequest)
            reviewer = reviewer_module.HereticReviewer(client=client)
            history = [{"role": "user", "content": "Fix the response label alignment."},
                       {"role": "assistant", "content": "The label is misaligned."},
                       {"role": "user", "content": "Original task"}]
            reviewer.capture(session_id="one", turn_id="one", user_message="Original task", conversation_history=history)
            result = reviewer.review(session_id="one", turn_id="one", final_response="Candidate answer",
                                     system_prompt="  EXACT SYSTEM\n", changed_paths=["label.tsx"])
            self.assertEqual(result["text"], "  Original review.\n")
            payload = transport.call_args.args[0]
            self.assertEqual(payload["messages"][0]["content"], "  EXACT SYSTEM\n")
            self.assertIn("Original task", payload["messages"][1]["content"])
            self.assertIn("Candidate answer", payload["messages"][1]["content"])
            context = json.loads(payload["messages"][1]["content"].split("--- Relevant context (data) ---\n", 1)[1])
            self.assertEqual(context["recent_conversation"], history[:-1])
            self.assertNotIn("tools", payload)
            self.assertTrue(payload["chat_template_kwargs"]["enable_thinking"])
            receipt = json.loads(client.last_receipt.read_text())
            self.assertFalse(receipt["tools_offered"])
            self.assertEqual(receipt["finish_reason"], "stop")
            self.assertEqual(receipt["context_messages"], 2)

    def test_missing_parent_prompt_is_refused_with_a_failure_receipt(self):
        helper = load("local_review_missing_prompt_helper", ROOT / "skills/autonomous-ai-agents/heretic/scripts/request.py")
        runtime = load("local_review_missing_prompt_runtime", Path(__file__).resolve().parents[1] / "runtime.py")
        with tempfile.TemporaryDirectory() as directory, patch.object(helper.HereticRequest, "local_call") as transport:
            client = runtime.LocalReviewClient(home=Path(directory), request_class=helper.HereticRequest)
            with self.assertRaisesRegex(ValueError, "complete system prompt"):
                client.generate("Original task", "Candidate", None)
            transport.assert_not_called()
            self.assertTrue(json.loads(client.last_receipt.read_text())["failed"])

    def test_concurrent_requests_keep_their_own_receipts(self):
        helper = load("concurrent_review_helper", ROOT / "skills/autonomous-ai-agents/heretic/scripts/request.py")
        runtime = load("concurrent_review_runtime", Path(__file__).resolve().parents[1] / "runtime.py")
        barrier = Barrier(2)
        response = {"model": helper.HereticRequest.MODEL, "choices": [{"finish_reason": "stop", "message": {
            "content": "Review.", "reasoning": "Compared."}}]}

        def local_call(payload):
            barrier.wait(timeout=5)
            return response

        with tempfile.TemporaryDirectory() as directory, patch.object(
            helper.HereticRequest, "count_tokens", return_value=32
        ), patch.object(helper.HereticRequest, "local_call", side_effect=local_call):
            client = runtime.LocalReviewClient(home=Path(directory), request_class=helper.HereticRequest)
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(client.generate, "Task", "Answer", "System") for _ in range(2)]
                self.assertEqual([future.result() for future in futures], ["Review.", "Review."])
            receipts = list((Path(directory) / "cache/scratch").glob("heretic-review-*/receipt.json"))
            self.assertEqual(len(receipts), 2)
            self.assertTrue(all(json.loads(path.read_text())["finish_reason"] == "stop" for path in receipts))


if __name__ == "__main__":
    unittest.main()
