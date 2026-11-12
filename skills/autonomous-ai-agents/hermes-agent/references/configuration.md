# Configuration, Toolsets & Voice

Edit with `hermes config edit` or `hermes config set section.key value`.
Full reference: https://hermes-agent.nousresearch.com/docs/user-guide/configuration

### Config Sections (most-used keys)

| Section | Key options |
|---------|-------------|
| `model` | `default`, `provider`, `base_url`, `api_key`, `context_length`, `aliases` |
| `agent` | `max_turns` (90), `tool_use_enforcement`, `service_tier`, `verify_on_stop` |
| `terminal` | `backend` (local/docker/ssh/modal/daytona/singularity), `cwd`, `timeout` (180) |
| `compression` | `enabled`, `threshold` (0.50), `target_ratio` (0.20) |
| `display` | `skin`, `interface` (cli/tui), `language`, `show_reasoning`, `show_cost`, `pet` |
| `approvals` | `mode` (smart/manual/off), `timeout`, `cron_mode` |
| `stt` | `enabled`, `provider` (local/groq/openai/mistral/elevenlabs/deepinfra) |
| `tts` | `provider` (edge/elevenlabs/openai/minimax/mistral/neutts/gemini/piper/kittentts/deepinfra/xai) |
| `memory` | `memory_enabled`, `user_profile_enabled`, `provider`, `write_approval` |
| `security` | `redact_secrets`, `website_blocklist` |
| `delegation` | `model`, `provider`, `max_concurrent_children`, `max_iterations` (50), `max_spawn_depth` |
| `checkpoints` | `enabled`, `max_snapshots` (50) |
| `curator` | `enabled`, `consolidate` (false, opt-in aux-model consolidation), `interval_hours`, `stale_after_days` |

`hermes config check` reports sections missing from an older config.

### Reasoning effort

Levels: none, minimal, low, medium, high, xhigh.

- Per run: `hermes chat --reasoning high`
- Live in session: `/reasoning high` (`/reasoning show|hide` toggles display)
- Persistent: `hermes config set agent.reasoning_effort high`
- Per model: `agent.reasoning_overrides` dict, YAML-edit only (no `config set` support).

`hermes config get/set agent.reasoning_effort` prints "not a recognized config key" (it is missing from DEFAULT_CONFIG's `agent` block), but the value is saved and read: `hermes_constants.resolve_reasoning_config` is the single chokepoint for every surface and reads `agent.reasoning_effort` after per-model overrides. Tell the user the warning is false; `--force` silences it. Whether a provider honours the level is provider-dependent: grep the provider/plugin for `effort` (the claude-subscription directsdk plugin forwards it as `--effort` to Claude Code), or toggle low/high with `/reasoning show` and compare thinking length.

### Default launch and appearance

1. Read effective values with `hermes config get display.interface` and `hermes config get display.skin`; enumerate candidates with `hermes skin list` only when needed. Use `config get` for one key rather than guessing that `config show` accepts a key argument.
2. Set default terminal startup with `hermes config set display.interface tui`. Preserve an already selected skin when only the interface changes; otherwise apply the confirmed choice with `hermes config set display.skin <name>`.
3. Read both keys back and confirm the configuration path reported by the writer belongs to the active profile. A similarly named repository config is not necessarily the effective profile config.
4. Report saved defaults as verified configuration. Claim an observed default launch or live appearance only after exercising that path; a config readback alone does not establish either.

### Dense TUI transcript spacing

- Use the existing TUI preference `display.tui_compact`, exposed by native `config.set(key='density', value='on')`; `display.compact` is not the TUI density flag. Read back `config.get(key='full').config.display.tui_compact`.
- Inspect `MessageLine` before assuming density removes tool spacing. The native compact flag originally reached Markdown only; group-leading gaps and the margins below detail/response headers ignored it. Gate those margins with `compact`, mirror the change in `estimatedMsgHeight`, and preserve user-turn separators. The virtual-height cache already keys on `ui.compact`.
- Reproduce the user's exact block sequence with the real renderer. Prefer `renderToScreen` for row-count assertions: a PassThrough can accumulate several repaints and overcount rows. Test settled/live output, hidden details, unchanged visible content, and unchanged user/code-block layout. Record pre-existing code-block whitespace defects separately instead of broadening a service-spacing fix.
- For live acceptance, a temporary zero-height SDK widget can use a Box ref to reach the current Ink root and inspect ancestor `marginTop`/`marginBottom` around fixed `Tool calls` and `Response` labels. Persist only aggregate layout metadata, not transcript text; scope diagnostics to the current PID, skip VITEST/non-TTY imports, and remove the widget afterward. Use the verified frontend-resume workflow in `references/themes.md` when adopting a rebuilt bundle.

### Portable setup snapshots and publication

- Compare the active profile's effective configuration with any settings repository before exporting. A project-level config.yaml can be an old snapshot after the live profile stops using its symlink. Export a curated non-secret example; do not overwrite or publish the legacy host file implicitly.
- Preserve the skin's bytes/aliases and pair custom TUI behavior with an exact upstream revision, a source patch and its regression tests. Replay the patch against isolated baseline files and byte-compare the result; a palette alone does not reproduce renderer fixes.
- Exclude credentials, OAuth grants, chats, sessions, memories, DBs, caches and logs by a shared artifact policy before reading source diffs. Secret-pattern scanning is a separate gate, not a classifier for private conversation data. Example suffixes never exempt private directories; inspect every outgoing commit, including files deleted from its tip.
- Track exporter-owned paths and hashes. Detect stale generated files in check mode, remove only unchanged owned copies, and reject symlink components throughout destination paths before writes or deletion. Missing required sources must fail rather than silently preserve stale exports.
- Prepare and verify the payload before requesting personal GitHub browser authorization. Use the native credential store, explicitly create the intended private repository, and keep publication permission scoped to the user-approved destination and active session requirements.
- Verify publication by reading back the exact branch commit, complete remote tree and important file bytes. Store project-specific commit/push preferences in that project's existing rules; do not install an unconditional background publisher.

### Inspect active memory and its size

1. Read `hermes config get memory.provider`. For Honcho, run `hermes honcho status` and `hermes honcho tokens` to obtain the effective connection identity, recall mode and retrieval budgets without dumping configuration or credentials. Keep masked authentication details out of the user-facing report.
2. Query `honcho_context` and `honcho_profile` when checking what the current conversation can actually recall. Compare workspace, user peer and session identities with CLI diagnostics before combining their results; different runtime identities can inspect different records.
3. Distinguish three quantities: stored data size, raw-context retrieval budget, and synthesized-answer budget. Preserve the units printed by the installed CLI: context may be measured in tokens while the dialectic answer limit is measured in characters. Re-read live values instead of treating example numbers as product defaults.
4. Measure stored size or capacity at the configured backend if that is the user's question and read access is available. An empty local `memories/` directory does not measure Honcho storage, and an empty peer card/context does not prove that no raw messages exist. If backend size was not measured, say so instead of calling memory empty or unlimited.
5. Separate injected project instructions from recalled memory when explaining what the assistant knows; seeing working rules in the prompt does not establish cross-session retrieval.

### Batched question wizard

- Prepare all known independent decisions before calling `clarify`. Send a coherent
  batch in one call, using `multi_select` for independent choices and single-select
  for alternatives. Do not spend a model turn on each known question or checkbox.
- The patched Ink TUI provides Back/Next, retained drafts, an editable review page,
  and a separate Submit answers action. Navigation is local; one aggregate result
  resumes the model. Do not put navigation or exit in the question's answer choices.
- Keep the existing tool contract: 1-5 questions, at most four supplied choices per
  question. A later batch is appropriate for dependent follow-ups or a larger set.
- Leave open does not select a default. Exit preserves partial answers with a
  cancelled outcome; do not treat them as a completed decision.
- Verify the active Ink renderer and request-handler path. Classic CLI callbacks,
  source edits and a successful build do not prove an existing window adopted it.

### Toolsets

Enable/disable via `hermes tools` (interactive) or `hermes tools enable/disable NAME`.
Full enumeration: `TOOLSETS` dict in `toolsets.py` (`_HERMES_CORE_TOOLS` is the default bundle most platforms inherit).

| Toolset | What it provides |
|---------|-----------------|
| `web` / `search` | Web search + extraction / search-only subset |
| `browser` | Browser automation (Browserbase, Camofox, or local Chromium) |
| `terminal` | Shell commands and process management |
| `file` | File read/write/search/patch |
| `code_execution` | Sandboxed Python execution |
| `coding` | Code-editing helpers (LSP-backed) |
| `computer_use` | Desktop GUI control (cua-driver) |
| `vision` | Image analysis |
| `image_gen` | Image generation and image-to-image editing |
| `video` / `video_gen` | Video analysis / video generation |
| `x_search` | X (Twitter) search (X OAuth or API key) |
| `tts` | Text-to-speech |
| `skills` | Skill browsing and management |
| `memory` | Persistent cross-session memory |
| `session_search` | Search past conversations |
| `context_engine` | Pluggable context-engine hooks |
| `project` | Named multi-folder workspace tools |
| `delegation` | Subagent task delegation |
| `cronjob` | Scheduled task management |
| `clarify` | Ask user clarifying questions |
| `todo` | In-session task planning |
| `kanban` | Multi-agent work-queue tools (gated to workers) |
| `debugging` | Extra introspection tools (off by default) |
| `safe` | Minimal low-risk toolset for locked-down sessions |
| `discord`, `discord_admin`, `feishu_doc`, `feishu_drive`, `yuanbao` | Service integrations (gated on their credentials). `homeassistant` (`ha_*` tools) and `spotify` (`spotify_*` tools) are not built in: they come from the `homeassistant` / `spotify` catalog plugins (`hermes plugins install <name>`) |

Tool changes take effect on `/reset` (new session) — never mid-conversation, to preserve prompt caching.

## Voice

### STT (Voice → Text)

Voice messages from messaging platforms are auto-transcribed.

```yaml
stt:
  enabled: true
  provider: local   # local (faster-whisper, free) | groq | openai | mistral | elevenlabs | deepinfra
  local:
    model: base     # tiny, base, small, medium, large-v3, turbo
```

Auto-detect priority: local faster-whisper (`python -c "import pm; pm.sync_venv(['stt-whisper'], explicit=True)"`) → Groq (`GROQ_API_KEY`, free tier) → OpenAI (`VOICE_TOOLS_OPENAI_KEY`) → Mistral Voxtral (`MISTRAL_API_KEY`).

### TTS (Text → Voice)

| Provider | Env var | Free? |
|----------|---------|-------|
| Edge TTS (default) | None | Yes |
| ElevenLabs | `ELEVENLABS_API_KEY` | Free tier |
| OpenAI | `VOICE_TOOLS_OPENAI_KEY` | Paid |
| MiniMax | `MINIMAX_API_KEY` | Paid |
| Mistral | `MISTRAL_API_KEY` | Paid |
| Gemini | `GOOGLE_API_KEY` | Free tier |
| NeuTTS / Piper / KittenTTS (local) | None | Free |

Voice commands: `/voice on` (voice-to-voice), `/voice tts` (always voice), `/voice off`.
