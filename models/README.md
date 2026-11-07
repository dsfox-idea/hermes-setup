# Additional local Heretic model

This setup adds `qwen36-35b-heretic` without replacing the subscription-backed
Hermes default. It uses a separate MLX environment and a loopback-only server.
Ollama and the existing Honcho deployment are not modified.

## Selected artifact

- Repository: `froggeric/Qwen3.6-35B-A3B-Uncensored-Heretic-MLX-4bit`.
- Revision: `32939a6cef2750f18ccf352443f22f2e4dfe3613`.
- Source derivative: `llmfan46/Qwen3.6-35B-A3B-uncensored-heretic`.
- Format: MLX affine 4-bit, group size 64, with 8-bit routing gates.
- Weight files: 20,402,204,301 bytes, excluding tokenizer/configuration files.
- Runtime: MLX LM 0.32.2, MLX 0.32.4, Python 3.14.9.

The user selected the Heretic family using the exact label above; the Apple
Silicon artifact and quantization were resolved during installation. Do not
substitute another derivative or revision silently.

The runtime is for Apple Silicon macOS. `requirements-mlx.lock` records the
installed package versions. Model weights, package environments and caches are
not included in Git.

## Restore on another Apple Silicon Mac

Choose the destination profile explicitly and preserve its existing settings:

```sh
profile=${HERMES_HOME:-$HOME/.hermes}
uv venv --python 3.14 "$profile/local-models/venv"
uv pip install --python "$profile/local-models/venv/bin/python" -r models/requirements-mlx.lock
HF_HUB_DISABLE_IMPLICIT_TOKEN=1 "$profile/local-models/venv/bin/hf" download \
  froggeric/Qwen3.6-35B-A3B-Uncensored-Heretic-MLX-4bit \
  --revision 32939a6cef2750f18ccf352443f22f2e4dfe3613 \
  --local-dir "$profile/local-models/models/qwen36-35b-heretic" \
  --include '*.safetensors' --include '*.json' --include '*.jinja'
```

Verify the pinned files before loading them. From this repository's root:

```sh
checksums="$PWD/models/artifact.sha256"
(cd "$profile/local-models/models/qwen36-35b-heretic" && shasum -a 256 -c "$checksums")
```

The main weight SHA-256 values are published by the model repository. For this
machine all downloaded files are
also checked against the pinned Hub metadata: SHA-256 for LFS files and Git blob
identities for ordinary configuration/template files.

`local-heretic.plist.example` is the exact launchd configuration for the source
machine. Replace **all** absolute home/profile paths before using it elsewhere.
Create the configured log, scratch and Hugging Face cache directories, validate
with `plutil -lint`, and install it into the current user's LaunchAgents domain.
Do not overwrite another user's service or an unrelated profile.

The service binds only `127.0.0.1:18319`. Runtime Hub downloads are disabled.
It starts without a model loaded and loads the local folder on the first
inference request. The weights stay resident afterwards until service restart;
there is no idle-unload timer. The explicit Hermes alias identifies the local
folder even when `/v1/models` does not enumerate it.

Apply the additional alias with the supported configuration writer:

```sh
hermes config set model_aliases.qwen36-35b-heretic '{"model":"qwen36-35b-heretic","provider":"custom","base_url":"http://127.0.0.1:18319/v1"}'
hermes config set model_overrides.custom.qwen36-35b-heretic.context_window 65536
```

`hermes-alias.example.json` contains the same additive settings. Do not replace
the whole main configuration with that fragment. The 65,536-token value is a
conservative client context setting, not a verified maximum-input benchmark.

## Select the local model

In Hermes:

```text
/model qwen36-35b-heretic --session
```

For a new conversation:

```sh
hermes chat --model qwen36-35b-heretic
```

The explicit `--session` flag keeps the saved cloud default unchanged. Return to
the subscription-backed model with:

```text
/model gpt-6.1-sol-900k --provider openai-codex --session
```

Local generation does not reconfigure auxiliary tools or the Honcho memory
backend. Those integrations retain their existing routes.

## Acceptance

`acceptance.json` records the 2026-11-03 checks on an Apple M4 Pro:

- All 13 pinned artifact files passed integrity verification.
- Generated Python passed seven cases, including unhashable values and input
  preservation.
- Generated Bash passed macOS filename cases with spaces, newlines, Cyrillic and
  hidden files, plus missing/invalid arguments and an empty directory.
- Russian logic produced the correct final answer with separate reasoning.
- A structured tool round trip returned a newly generated local fixture value.
- The real Hermes tool loop executed `printf LOCAL_HERETIC_OK` and returned its
  actual successful result, using a synthetic query without user rules/memory.
- Three warm 512-token streams measured 74.9--76.3 tokens/s, median 76.0, against
  the user's approximately 50 tokens/s target. These short-prompt samples exclude
  prefill and thinking.

Small synthetic checks establish basic behavior, not a comprehensive coding or
Russian-language benchmark. Maximum context capacity was not exercised.

## Comparison with reasoning enabled

`reasoning-comparison.json` records a controlled comparison with a short synthetic
system prompt, not the complete working Hermes prompt. Both routes received
byte-identical Russian system/user input and the same JSON, code and
final-explanation constraints. Local thinking was explicitly enabled and cloud
high effort was present in the actual request. Reasoning was confirmed in every
measured response; separate warmups were excluded and request order alternated.

| Median result, three repetitions of one coding task | Local Heretic | Cloud GPT-6.1 Sol |
| --- | --- | --- |
| Full response time | 49.4 s | 25.1 s |
| First final-answer text | 47.1 s | 24.4 s |
| Correct answers, each checked on seven cases | 3/3 | 3/3 |

For this task, the cloud route completed the correct reasoning-enabled answer
sooner. The earlier no-thinking throughput number must not be used to claim that
local reasoning-enabled work finishes faster. This remains one task, not a broad
quality ranking. The two routes have different native reasoning controls and
token accounting; all answers completed naturally without truncation.

## Comparison with the complete working system prompt

`full-system-comparison.json` replays one frozen system-prompt snapshot obtained
read-only from the active cloud session. It contains 35,861 characters instead
of the earlier synthetic prompt's 181. The same text was sent through both
routes, and the native local tokenizer/template was checked to preserve the
system text exactly. Only its hash and measurements are published; the private
prompt body remains outside this repository.

| Median result, three repetitions | Local Heretic, thinking on | Cloud GPT-6.1 Sol, high |
| --- | --- | --- |
| Full response time | 38.7 s | 24.5 s |
| First final-answer text | 34.7 s | 21.4 s |
| Functional checks passed | 3/3 | 3/3 |

History and executable tools were omitted equally; this is generation under the
full system snapshot, not a full agent-workflow benchmark. Both models completed
naturally with verified reasoning. The safety validator initially omitted safe
hash/exception builtins; all unchanged stored responses were rechecked, without
repeating inference or changing timings. The original evaluation is retained
locally for audit.

Normal Hermes prompt assembly has model-gated guidance and runtime metadata.
This benchmark does not change that builder or force every ordinary session's
prompt to be byte-identical. Equal timing is not evidence of equal prompts, and
different timing does not establish different prompts.

## Follow-up after switching to GPT-6 Astra

`astra-comparison.json` repeats the same task after read-only session discovery
confirmed `gpt-6-astra-900k`, provider `openai-codex`, and high reasoning effort.
Provider responses identify the wire model as `gpt-6-astra`. Both routes received
the same new full system snapshot (36,044 characters), with local template
preservation verified. No model settings or active-session cache were changed.

| Median result, three repetitions | Local Heretic, thinking on | GPT-6 Astra, high |
| --- | --- | --- |
| Full response time | 36.7 s | 17.3 s |
| First final-answer text | 33.9 s | 13.1 s |
| Functional checks passed | 3/3 | 3/3 |

Warmups are excluded; history and executable tools are absent equally. Actual
reasoning is confirmed in all measured answers. The earlier Sol measurement is
historical, not part of a simultaneous three-model comparison. This single task
does not establish general relative quality.
