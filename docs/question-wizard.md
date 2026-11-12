# Question wizard

The Ink TUI collects a prepared batch of questions in one interaction. The agent
calls `clarify` once with the complete independent question set; the user moves
between questions locally and sends one aggregate answer after reviewing it.
Question navigation does not request another model completion or run a response
reviewer. A genuinely new question that depends on an answer may need a later
batch.

## Interaction

- Single-choice questions use selectors; choosing an option advances locally.
- Multiple-choice questions use independent checkboxes. Space or a number toggles
  a choice. Next advances without sending a tool result.
- Other accepts a custom answer. Free-text questions are supported too.
- Back, Left/Right and Tab/Shift+Tab navigate without losing edited answers.
- Leave open records an unanswered question instead of accepting the highlighted
  option as a default.
- Review answers shows the whole batch. Select a question to edit it, or choose
  Submit answers to return one result frame.
- Exit and keep partial answers returns the saved choices with a `cancelled`
  outcome. A partial or cancelled set is not a completed decision.
- A single-question prompt retains its compact layout and a separate Continue
  action for multiple selection.

The existing Hermes tool limits remain unchanged: one call accepts 1-5 questions,
with at most four supplied choices per question and an additional Other entry.
Do not add navigation or exit as ordinary answer choices: the wizard provides
those controls itself. For an independent batch, do not ask each known question
in a separate tool call. Larger sets must be divided into coherent batches within
that tool contract, not into one call per checkbox.

The source patch is included in the normal TUI overlay. Existing windows need to
load the rebuilt frontend; a successful build alone does not update an open one.
No gateway restart or model change is required for the frontend behavior.

## Reference behavior

The interaction follows Claude Code's `AskUserQuestion` pattern: a questions
array, single- and multiple-choice options, optional custom text, and an aggregate
answers mapping. Claude Code's documented tool limit is 1-4 questions with 2-4
options each; Hermes retains its own existing limits.

Primary documentation:

- [Handle approvals and user input](https://code.claude.com/docs/en/agent-sdk/user-input)
- [Tools reference](https://code.claude.com/docs/en/tools-reference)

A [CLI user report](https://github.com/anthropics/claude-code/issues/106114)
describes checkbox selection followed by a review page and submission. This is
reported UI behavior, not a specification of every Claude Code version.

## Verification

Renderer and request-handler tests cover mixed input types, retained selections,
editing after review, unanswered questions, explicit exit, stale requests and
exactly one final response frame. Existing single-question behavior is also
covered. Terminal acceptance uses synthetic questions only; no conversation
contents or user answers are packaged in this repository.
