# Optional local response review

This component adds an independent Heretic review before a substantive answer is finalized. The primary agent stays in charge: it receives the review as untrusted observations and must verify claims before accepting them. Raw review text and the primary agent's assessment remain separate in both storage and the terminal transcript.

## Scope and prerequisites

- This is optional. The ordinary `scripts/setup.py install` command does not enable reviews.
- The reference runtime uses the existing `qwen36-35b-heretic` model at loopback port `18319`, with reasoning enabled and no executable tools. There is no cloud fallback.
- The request helper currently uses an MLX tokenizer from `<profile>/local-models/venv/bin/python` and `<profile>/local-models/models/qwen36-35b-heretic`. This deployment is for Apple Silicon/macOS; Linux and Windows inference are not verified by these scripts. See [local model options](local-model-options.md) before preparing that runtime.
- The complete current application system prompt, current task and candidate answer go to that local endpoint. Up to two earlier human turns and their final assistant replies are included as bounded excerpts. Tool results, previous review blocks and non-text attachments are not included. Decisions present only in omitted tool results may be missing from the reviewer context; the primary agent must reconcile them itself.
- Review output currently requests Russian. This is not a configurable multilingual reviewer.
- The helper refuses requests exceeding its local context budget rather than truncating the full application prompt. Missing dependencies, unavailable inference or incomplete responses produce an unavailable-review result.

No installer command downloads model weights, starts an inference service or sends a model request. A loopback URL specifies the client route; the operator remains responsible for the service running there.

## Check without changing a profile

Use explicit paths to the Hermes source checkout and the one profile being configured:

```sh
python3 scripts/install_review.py check \
  --checkout /path/to/hermes-source \
  --profile-home /path/to/profile
```

`check` verifies the packaged host-patch checksum, patch presence, package bytes and the presence of the expected local-model directories. `model_execution_verified` remains false: file presence is not a working model test.

## Install and enable explicitly

```sh
python3 scripts/install_review.py install --enable --apply-host-patch \
  --checkout /path/to/hermes-source \
  --profile-home /path/to/profile
```

Unlike the default theme installer, **this opt-in command modifies the specified Python source checkout**. The host patch adds the `pre_response` hook, one-review-per-turn stop gate, attributed event and transcript handling. It checks applicability before changing files and reads back the installed state. It does not change branches, commit the upstream checkout, rewrite history or restart services.

The command copies the reviewer plugin and its request helper into only the selected profile, then enables that plugin through the native Hermes CLI. It does not replace the manual Heretic skill's instruction body or another profile's settings. Differing existing files are refused unless `--replace` is supplied; that flag first backs up only the conflicting owned package files beneath the selected profile's `backups/` directory. Symlink destinations are refused.

The normal theme/TUI installer supplies the matching separate review block and `ui_review` color token. Refresh that overlay using the main installation instructions. The Python host and already-open TUI adopt their new code separately at their next normal start; the optional installer does not claim live activation.

## Disable and update

Disable the plugin through the native CLI for the intended profile:

```sh
hermes -p PROFILE plugins disable heretic-reviewer
```

The inert host hook and presentation support may remain installed. Do not reverse a source patch blindly over unrelated edits. After `hermes update`, rerun `check`; an update may have removed local host modifications. Reapply only when the reviewed patch passes its compatibility check. The known source revision and patch checksums are recorded in `upstream.json`.

## Verification and limitations

The package includes tests for context selection, omitted attachments, full-prompt preservation, unavailable responses, concurrent receipts and explicit profile-scoped installation. The host patch includes native turn-loop and event-relay tests; the TUI patch includes attributed rendering and transcript lifecycle tests. Mocked provider responses in those tests are orchestration checks, not evidence of model quality.

Review selection is heuristic, based on mutations, research activity, tool activity and answer length. It is not an independent proof that a task is important or that a review is correct. Private receipts and raw reviews stay beneath the profile's scratch directory and must not be published.
