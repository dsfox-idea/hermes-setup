"""Behavior contracts for answer-only independent reviews."""

import importlib.util
from pathlib import Path
import sys
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("local_review_test_module", PACKAGE / "reviewer.py")
assert spec is not None and spec.loader is not None


class IndependentReviewTests(unittest.TestCase):
    def test_context_omits_tools_reviews_notifications_and_older_turns(self):
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        history = [
            {"role": "system", "content": "SYSTEM"},
            {"role": "user", "content": "OLD"},
            {"role": "assistant", "content": "OLD ANSWER"},
            {"role": "user", "content": "First request"},
            {"role": "assistant", "content": "Progress"},
            {"role": "assistant", "content": "TOOL CALL", "tool_calls": [{"id": "one"}]},
            {"role": "tool", "content": "LARGE LOG"},
            {"role": "assistant", "content": "First answer"},
            {"role": "user", "content": "REVIEW", "display_kind": "response_review"},
            {"role": "assistant", "content": "Review assessment"},
            {"role": "user", "content": "NOTICE", "display_kind": "internal_notification"},
            {"role": "assistant", "content": "Notice acknowledgment"},
            {"role": "user", "content": "Second request"},
            {"role": "assistant", "content": "Second answer"},
            {"role": "user", "content": "And?"},
        ]
        result = module.ReviewContext.collect(history)
        self.assertEqual([row["content"] for row in result],
                         ["First request", "First answer", "Second request", "Second answer"])
        self.assertEqual(history[-1]["content"], "And?")
        self.assertEqual(module.ReviewContext.collect([]), [])

    def test_context_bounds_excerpts_and_omits_memory_and_image_payloads(self):
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        context = module.ReviewContext
        content = [{"type": "text", "text": "Requirement<memory-context>PRIVATE MEMORY</memory-context>"},
                   {"type": "image_url", "image_url": {"url": "data:image/png;base64,PRIVATE_IMAGE"}}]
        history = [{"role": "user", "content": content},
                   {"role": "assistant", "content": "START" + "x" * 10000 + "END"},
                   {"role": "user", "content": "And?"}]
        result = context.collect(history)
        self.assertEqual(result[0]["content"], "Requirement\n[Non-text attachment omitted]")
        self.assertLessEqual(len(result[1]["content"]), context.MAX_MESSAGE_CHARACTERS)
        self.assertIn("[Excerpt shortened]", result[1]["content"])
        self.assertTrue(result[1]["content"].startswith("START"))
        self.assertTrue(result[1]["content"].endswith("END"))
        self.assertIn("PRIVATE MEMORY", history[0]["content"][0]["text"])

    def test_followup_includes_the_previous_request_and_answer(self):
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        calls = []

        class Client:
            model = "test-local-model"

            def generate(self, task, answer, system, conversation_context=None):
                calls.append((task, conversation_context))
                return "No supported finding."

        history = [
            {"role": "user", "content": "Keep the response label outside the time column."},
            {"role": "assistant", "content": "The label is in the wrong column."},
            {"role": "user", "content": "And?"},
        ]
        reviewer = module.HereticReviewer(client=Client())
        reviewer.capture(session_id="one", turn_id="followup", user_message="And?", conversation_history=history)
        reviewer.review(session_id="one", turn_id="followup", final_response="Fixed the label alignment.",
                        system_prompt="SYSTEM", changed_paths=["label.tsx"])
        self.assertEqual(calls, [("And?", history[:-1])])

    def test_code_review_keeps_original_task_answer_and_system(self):
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        calls = []

        class Client:
            model = "test-local-model"

            def generate(self, task, answer, system, conversation_context=None):
                calls.append((task, answer, system))
                return "  A tentative finding.\n"

        reviewer = module.HereticReviewer(client=Client())
        reviewer.capture(session_id="one", turn_id="turn-one", user_message="Fix the zero boundary.")
        result = reviewer.review(session_id="one", turn_id="turn-one", final_response="Proposed answer.",
                                 system_prompt="EXACT APPLICATION SYSTEM", changed_paths=["boundary.py"])

        self.assertEqual(calls, [("Fix the zero boundary.", "Proposed answer.", "EXACT APPLICATION SYSTEM")])
        self.assertEqual(result["text"], "  A tentative finding.\n")
        self.assertEqual(result["label"], "Heretic")
        self.assertEqual(result["status"], "completed")

    def test_direct_worker_assignment_is_not_reviewed_again(self):
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        class Client:
            model = "test-local-model"

            def generate(self, *args):
                raise AssertionError("A direct worker answer must not be reviewed again")

        reviewer = module.HereticReviewer(client=Client())
        reviewer.capture(session_id="one", turn_id="one", user_message="@heretic Explain the algorithm.")
        self.assertIsNone(reviewer.review(session_id="one", turn_id="one", final_response="Long answer. " * 200,
                                          system_prompt="System", changed_paths=[]))

    def test_review_retains_the_task_when_compaction_rotates_the_session(self):
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        class Client:
            model = "test-local-model"

            def generate(self, task, answer, system, conversation_context=None):
                return "Preserved task: " + task

        reviewer = module.HereticReviewer(client=Client())
        reviewer.capture(session_id="before", turn_id="stable-turn", user_message="Original requirement.")
        result = reviewer.review(session_id="after", turn_id="stable-turn", final_response="Candidate.",
                                 system_prompt="System", changed_paths=["code.py"])
        self.assertIsNotNone(result)
        self.assertEqual(result["text"], "Preserved task: Original requirement.")


if __name__ == "__main__":
    unittest.main()
