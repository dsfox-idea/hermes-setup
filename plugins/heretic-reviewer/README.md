# Independent Heretic response review

This is an optional public component of `hermes-setup`. Installation, privacy
boundaries, supported runtime and disable/update instructions are in
[`docs/response-review.md`](../../docs/response-review.md). The default theme
installer does not enable this plugin; use the explicit single-profile installer.

This plugin keeps the cloud agent as the conversation leader. Before substantive
work is finalized, it compares the original request with the candidate answer
using the existing answer-only local Heretic client. The complete current
application system prompt is preserved, reasoning is enabled, executable tools
are absent, and inference is pinned to the loopback Heretic endpoint. There is
no cloud fallback and an oversized full request is refused without truncation.
The review receives up to two preceding human turns and their last assistant
answers, captured through the native `pre_llm_call` history. Each excerpt is capped
at 1500 characters with an explicit shortening marker. Tool calls/results,
service notices, prior reviews and injected memory blocks are omitted. Non-text
attachments are marked as omitted; their bytes are never serialized into text.
The current request and candidate answer are preserved in full.

The native `pre_response` hook is required. It presents an attributed raw review
and returns control to the main model with explicit instructions to verify each
claim. Suggestions do not execute tools, approve permissions, rewrite the main
answer, or change its route. A corrected answer requires the main model's own
assessment and evidence. Unsupported suggestions may be rejected.

## Automatic scope

Selection is deliberately deterministic and heuristic: edited paths, file-write
or patch calls, recognized native configuration writes, two research tool calls,
an answer of at least 1200 characters, or at least three tool calls with an
answer of at least 300 characters. Short casual replies, direct `@heretic` and
`@spark` assignments, delegated children, and interrupted turns are excluded.
Each primary-agent turn is reviewed at most once. A task must have passed the
`pre_llm_call` capture point; enabling during an already-running turn does not
reconstruct its request from unrelated history.

## Presentation and failure

The host stores the original review independently from its model-facing advisory
framing. The TUI shows a separate `Heretic` block in light red (`#ff8a80`, skin
token `ui_review`). The standard Markdown renderer displays emphasis, headings,
lists and code; terminal control sequences are removed only for rendering.
The main model's assessment follows in its normal style. Failed reviews are
shown as unavailable; no response or verification is invented.

Private generation receipts and raw replies live under the owning profile's
`cache/scratch/heretic-review-*`; they are not setup artifacts. Registration
is lazy and does not load the model or contact its server. The plugin declares
no executable tools and needs no additional Python dependencies.

## Verification

Run `hermes --run-module unittest discover -s plugins/heretic-reviewer/tests -v` from the
setup repository. The host patch has native turn-loop, event-relay, transcript,
and rendered-color tests. The real-model acceptance uses a labelled synthetic
function defect with the live application's complete prompt, then independently
executes its boundary cases. A running gateway and already-open TUI must adopt
the host changes separately; successful installation is not live UI acceptance.
