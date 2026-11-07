# Providers & Model Aliases

Set via `hermes model` (picker) or `hermes setup`. 35+ provider profiles ship as
plugins under `plugins/model-providers/`; user plugins of the same name override.
Full docs: https://hermes-agent.nousresearch.com/docs/integrations/providers

### Providers

| Provider | Auth | Key env var(s) |
|----------|------|----------------|
| openrouter | API key | `OPENROUTER_API_KEY` |
| anthropic | API key | `ANTHROPIC_API_KEY` (also `CLAUDE_CODE_OAUTH_TOKEN`) |
| nous | OAuth device code | `hermes auth add nous` (or `NOUS_API_KEY`) |
| openai-codex | OAuth | `hermes auth add openai-codex` |
| qwen-oauth | OAuth | `hermes auth add qwen-oauth` |
| minimax-oauth | OAuth | `hermes auth add minimax-oauth` |
| copilot | Token | `COPILOT_GITHUB_TOKEN` / `GH_TOKEN` (Copilot device flow — `gh auth login` tokens do NOT work) |
| copilot-acp | External CLI | Copilot CLI on PATH or `COPILOT_CLI_PATH` |
| gemini | API key | `GOOGLE_API_KEY` or `GEMINI_API_KEY` |
| xai | API key | `XAI_API_KEY` (SuperGrok OAuth also supported) |
| deepseek | API key | `DEEPSEEK_API_KEY` |
| zai (GLM) | API key | `GLM_API_KEY` / `ZAI_API_KEY` |
| minimax / minimax-cn | API key | `MINIMAX_API_KEY` / `MINIMAX_CN_API_KEY` |
| kimi-coding / -cn | API key | `KIMI_API_KEY` / `KIMI_CN_API_KEY` |
| alibaba (+coding-plan) | API key | `DASHSCOPE_API_KEY` / `ALIBABA_CODING_PLAN_API_KEY` |
| xiaomi | API key | `XIAOMI_API_KEY` |
| huggingface | Token | `HF_TOKEN` |
| fireworks / novita / nvidia / deepinfra / gmi / arcee / stepfun / upstage / kilocode / ai-gateway / opencode-zen / opencode-go / ollama-cloud | API key | `<NAME>_API_KEY` |
| bedrock / vertex / azure-foundry | Cloud SDK / key | AWS SDK creds / Vertex ADC / `AZURE_FOUNDRY_API_KEY` |
| custom | Config | `model.base_url` + `model.api_key` in config.yaml |

Multiple credentials per provider pool and rotate automatically (`hermes auth`).
Fallback chain when the primary fails: `hermes fallback add|remove|list`.

### Compare local models for Apple Silicon

- Read live chip, CPU/GPU cores, physical unified memory, swap and existing runners before ranking models; filter serial numbers and UUIDs from hardware output. Research-only requests do not authorize weight downloads, installs or runner changes.
- Verify exact model IDs and current author cards, then check quantization artifacts through the Hugging Face API (`?blobs=true`) and pin the returned revision. Distinguish decimal file GB, physical-memory GiB and total runtime memory. A MoE's active parameters do not determine its resident weight footprint; include cache and application headroom in planning.
- Keep base-model author benchmarks separate from quantizer quality checks, modified/uncensored weights and measurements on the user's Mac. Attribute author results and harness differences; do not transfer a strong base-model score to a refusal-removal derivative without a matching evaluation.
- Prefer published measurements matching the actual chip and RAM, but retain runtime, quantization, prompt/context length, decoding settings and whether prefill is excluded. MTP/speculative results for one MLX runtime are not promised Ollama or Russian-prompt throughput.
- Evaluate Russian prose/reasoning independently of multilingual programming benchmarks. Report missing comparable evidence plainly, and label model-discussion reports about names/paths as user reports rather than population-level findings. Preserve exact identifiers in the eventual local acceptance set.
- Keep public-source evidence and the hardware-specific shortlist in profile scratch, outside the project, with an isolated citation ledger so concurrent research does not overwrite source IDs. Re-read current artifacts instead of retaining a volatile ranking in procedural memory.

### Add an Apple Silicon local model without replacing the cloud default

- Treat an additional-model choice as permission for that local installation, not a global default switch. Capture the effective default model/provider, reasoning and memory provider before changes and compare them afterwards. Use the native configuration writer for a direct alias and a model-scoped context override; document `/model <alias> --session`.
- Use a separate runtime environment outside Hermes PM and the source checkout. Pin the actual MLX LM/MLX/Python versions and test a real Metal computation before downloading or loading weights. Prefer `python -m mlx_lm server` over the deprecated module entry point.
- Pin the Hub artifact revision. Verify LFS files against their SHA-256 and ordinary files against their Git blob IDs. Native Hub downloads are the first choice; if that network path is throttled, use resumable segmented transfers against the same pinned URLs. Avoid exact curl artifact-size limits across redirects: a redirect body can exceed a small JSON file.
- Inspect installed loader definitions before importing helpers. For MLX LM 0.32.2, `load_tokenizer` is in `mlx_lm.utils`; the tokenizer module itself exposes `load`. Check cache-size parsing too: that server accepts decimal M/MB/G/GB suffixes or raw byte integers, not GiB.
- A loopback MLX server can start without `--model` and lazily load a local folder named by the request relative to its working directory. Register that exact folder name in the Hermes alias. The cache-scanning `/v1/models` catalog need not enumerate such a folder; verify the explicit alias route and actual inference rather than inventing a discovery failure. This setup has no automatic idle unload; restart to release resident weights.
- Keep runtime Hub access offline, restrict the listener to loopback, and preserve existing Ollama/Honcho services. Use synthetic prompts without user rules, memory or private history for acceptance. Test generated code on edge cases, macOS shell filenames, Russian reasoning, structured tool round trips and the real Hermes tool loop. Distinguish configured context from exercised capacity and warm generation throughput from first-token latency; never promise a target speed before measuring it. MLX LM 0.32.2 exposes separate reasoning as `message.reasoning`; inspect actual responses instead of assuming `reasoning_content`. The gateway-backed Hermes CLI can reject `--run-budget` even when `hermes chat --help` advertises it; omit that smoke-test flag rather than changing the main profile's policy. A config-key warning also does not prove an alias is ignored: verify its actual startup route and credential isolation.

### Compare thinking-enabled local and cloud inference

- For a working-Hermes comparison, capture one complete cached application prompt through read-only `session.info` and reuse that frozen snapshot. A matching hash of a tiny synthetic system message does not establish a representative Hermes workload. Verify actual cloud `instructions` and preservation by the native local chat template, not only a hash computed from the input variable. Keep private prompt bodies out of Git and reports; publish hashes and measurements only. State explicitly whether history and tool schemas/execution are included. Normal model-gated guidance and runtime metadata can differ in independently assembled prompts; never claim a benchmark changed production routing.

- Use identical explicit system/user input and final-answer constraints on both routes; hash the input pairs, exclude history/memory/tools, warm up separately, alternate request order and keep every measured attempt. Confirm actual local `enable_thinking: true` and accepted cloud `reasoning.effort`, not just saved config values.
- Establish reasoning in every measured answer: a separate local reasoning stream and tokenizer count, or provider-reported cloud reasoning tokens. Keep raw reasoning out of user reports. A request to disable reasoning does not establish that a provider actually disabled it.
- With the OpenAI SDK, backend-specific parameters such as MLX `top_k` belong in `extra_body`; bind kwargs against the installed SDK signatures before a timed run. Use supported native provider routing/credentials without printing them.
- Record real wire limits: the Codex subscription transport omits `max_output_tokens`, while local serving accepts `max_tokens`. Do not describe internal compute budgets as identical. Require natural, non-truncated completion and the same independent answer checks.
- Prefer full time to a correct final answer and time to first final text for the operational comparison. Streaming text may arrive in bursts; a short visible-token delivery window is not a direct measurement of hidden model computation. Different token accounting and reasoning lengths also prevent equating a raw tokens/s number with task-completion speed.

### Diagnose context-label mismatches

- Trace the TUI denominator from `Usage.context_max` to the running compressor's `context_length`; do not assume it is the compaction threshold. Read the renderer and usage projection for the active transport.
- Treat `-900k` as a Hermes-side picker alias, not a provider model ID or guaranteed context size. Compare the authenticated route's current `context_window`, `max_context_window`, and `_resolve_codex_oauth_context_length_with_source` results for both the base model and alias. Inspect the exact bump guard: an advertised value outside the guarded stale value can leave the alias label unchanged while resolving a smaller window.
- A Codex catalog `max_context_window` is not by itself an observed server-refusal boundary. Inspect the curated `codex-truly` entry and its pinned source/evidence before treating it as a physical limit. Its core mechanism is the existing scoped `model_overrides.<provider>.<model_id>.context_window` setting, so a single-model change may not require installing a plugin or adding tools. Separate author-reported capacity measurements from tests on this user's account, and do not run a quota-consuming capacity probe merely to answer a configuration question.
- Initialize `agent.ssl_verify.install_truststore()` before standalone HTTPS diagnostics. Use the native read-only credential resolver and print only model IDs, numeric context fields, and provenance; never credentials. Distinguish published maximum capacity from capacity actually exercised by the session.

### Validate a real million-token input requirement

- The user accepts approximately 922K input instead of a full million, prioritizing the existing ChatGPT subscription and no additional API billing. Do not route this setup to paid OpenAI API access without a new request. A model label or advertised total context window still does not establish usable input capacity.
- Read the official model page's `Maximum input tokens` separately from total context and maximum output. Never assume reducing requested output increases an independently published input cap. Fetch OpenAI developer pages as Markdown by appending `.md` when needed.
- Distinguish the ChatGPT/Codex subscription route from direct `openai-api` access and its separate billing. Check model/route limits before recommending a switch.
- Inspect automatic compaction and truncation before a capacity test: a default ratio trigger can summarize well before a large model's advertised window. Completion requires an actual accepted request with provider-reported input usage at or above the requested size and no prior compression/truncation; do not claim a paid capacity test was run when only documentation or metadata was checked.

### Apply and verify a scoped Codex context change

- Use native `hermes config set` with backslash-escaped dots in literal model IDs, for example `'model_overrides.openai-codex.gpt-6\.1-sol-900k.context_window'`; scope the ratio similarly with `'compression.model_thresholds.openai-codex:gpt-6\.1-sol-900k'`. Preserve other model/provider settings and read both mappings back.
- Set `model.default` to the selected alias when the change must survive new sessions. Distinguish standalone TUI hot-reload helpers from the active canonical gateway route: `LocalSessionPolicy` can retain frozen context/compression configuration, while resume refreshes only selected fields. A working `_apply_live_compression_config` test does not prove that the active session calls it or reads the edited profile. Do not promise next-turn adoption or recommend restarts from that isolated result. Verify `session.stats.context_length` and `config_context_length` after a real subsequent turn; inspect `session_policy_refresh` and `restore_local_session` before deciding whether resume or a gateway restart can refresh a stored policy. Fresh session creation reads the current profile. Avoid a gratuitous model re-pick, prompt rebuild, history edit, or plugin/tool installation merely to refresh context metadata.
- Verify the real `ContextCompressor.context_length`, `threshold_percent`, and `threshold_tokens`, not just YAML or a model label. The ratio uses the input budget after any output reservation, and an absolute `threshold_tokens` cap can still lower it. Check a base-model negative match and a different-provider threshold match.
- Smoke-test using `AIAgent` with `enabled_toolsets=[]`, `skip_context_files=True`, `skip_memory=True`, and `skip_background_review=True` and a synthetic one-line prompt; never forward private history for this test. Assert provider identity and compressor limits before and after the actual response. Treat this as a connectivity/configuration test, not a large-input capacity measurement.
- For PM-managed diagnostics, resolve the executable from the JSON list emitted by `hermes --print-runtime-command`, run the scratch script with that interpreter, add the discovered checkout to `sys.path`, and initialize `hermes_bootstrap` before project imports. `--module runpy` expects a module name, not an absolute script path. TUI helper modules are rebound into `tui_gateway.server`; exercise the bound server facade, not raw helpers with unresolved server globals. Test native hot reload offline and distinguish that result from settings already adopted by the live session.

### Direct terminal access outside Hermes

For standalone `spark` and `heretic` shell commands using the existing local servers, load `references/direct-local-cli.md`. These commands use a separate client and do not invoke the Hermes agent or its per-message worker adapters.

### User-defined model aliases

Work with `/model <name>` in CLI and every gateway platform. Resolved by
`hermes_cli/model_switch.py::resolve_alias()`; user aliases are checked BEFORE
the built-in table, so a user `sonnet`/`grok` shadows the built-in.

```yaml
# Full form
model_aliases:
  fav:
    model: claude-sonnet-4.6
    provider: anthropic
  local-qwen:
    model: qwen3.5:397b
    provider: custom
    base_url: "https://ollama.com/v1"
  theta:
    model: theta-1
    provider: custom
    base_url: "https://theta.example.com/v1"
    key_env: THETA_API_KEY        # or: api_key: "${THETA_API_KEY}"

# Short form ("provider/model"), also via CLI:
#   hermes config set model.aliases.fav openrouter/anthropic/claude-sonnet-4.6
model:
  aliases:
    fav: openrouter/anthropic/claude-sonnet-4.6
```

`/model fav` — session-scoped; add `--global` to persist as default.

An alias with its own `base_url` authenticates with its own credential
(`api_key`, which also accepts a `"${VAR}"` reference, or `key_env`). With
neither set the key is resolved from the alias HOST, never carried over from
the provider that was active before the switch.

Built-in aliases (catalog-resolved against the active provider): `sonnet`,
`opus`, `haiku`, `claude`, `gpt5`, `gpt`, `codex`, `o3`, `o4`, `gemini`,
`deepseek`, `grok`, `llama`, `qwen`, `minimax`, `nemotron`, `kimi`, `glm`,
`step`, `mimo`, `trinity`.
