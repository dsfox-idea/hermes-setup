---
name: hermes-agent
description: "Use, configure, theme, extend, and orchestrate Hermes Agent."
version: 3.2.0
author: Hermes Agent + Teknium
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, setup, configuration, multi-agent, spawning, cli, gateway, bots, bot-mode, features, themes, skins, desktop-plugins, tui-widgets, petdex, development]
    homepage: https://github.com/NousResearch/hermes-agent
    related_skills: [claude-code, codex, opencode]
---

# Hermes Agent

Hermes Agent is an open-source AI agent framework by Nous Research that runs in your terminal, a native desktop app, messaging platforms, and IDEs. It's in the same category as Claude Code (Anthropic), Codex (OpenAI), and OpenClaw — autonomous coding and task-execution agents that use tool calling to interact with your system. Hermes works with any LLM provider (OpenRouter, Anthropic, OpenAI, Google, DeepSeek, xAI, local models, and 20+ others) and runs on Linux, macOS, Windows, and WSL.

What makes Hermes different:

- **Self-improving through skills** — Hermes learns from experience by saving reusable procedures as skills that load into future sessions.
- **Persistent memory across sessions** — remembers who you are, your preferences, environment details, and lessons learned. Pluggable memory backends.
- **Multi-platform gateway** — the same agent runs on Telegram, Discord, Slack, WhatsApp, iMessage, Signal, Matrix, Teams, Email, and a dozen more platforms with full tool access, not just chat.
- **Many surfaces** — the same agent core drives the CLI, the Ink TUI, a native Electron desktop app, a web dashboard, and an ACP server for IDEs (VS Code / Zed / JetBrains).
- **Provider-agnostic** — swap models and providers mid-workflow; credential pools rotate across multiple API keys automatically.
- **Profiles** — run multiple independent Hermes instances with isolated configs, sessions, skills, and memory.
- **Extensible & themeable** — plugins, MCP servers, custom tools, webhook triggers, cron scheduling, skins that theme every surface, desktop UI plugins, TUI widgets, and pet mascots.

**This skill is a hub.** The body covers identity, quick start, spawning/orchestration, and hard invariants. Everything else lives in reference files — **load the matching reference (below) before answering**; do not answer detail questions from the body alone.

**Docs:** https://hermes-agent.nousresearch.com/docs/

## Scope & Verification

This skill is a concise operating guide, not the complete source of truth for every Hermes feature. If a Hermes feature, command, or setting is not mentioned here or in a reference, do not treat that absence as evidence that it does not exist. Check the live repository and official docs before giving a negative answer.

Good verification targets, cheapest first:

- **Every shipped feature, one line each: https://hermes-agent.nousresearch.com/docs/llms.txt.** Start here for any "can Hermes do X?" or "how do I do X?" — it indexes the entire documentation set with a link to the page that answers. It is generated from the docs tree on every build, so it is never behind the product. Fetch it with `web_extract`, or `curl -s https://hermes-agent.nousresearch.com/docs/llms.txt` when web tools are off. The whole documentation set in one file is at `/docs/llms-full.txt`.
- CLI commands: `hermes --help`, `hermes <command> --help`, and `hermes_cli/main.py`
- Source tree: https://github.com/NousResearch/hermes-agent

Never answer "Hermes can't do that" from memory. Hermes ships far more than this skill body describes, and the index exists so a negative answer is always checkable.

## Setup workflow and acceptance for this user

- Prefer supported configuration, official SDKs and existing integrations before proposing custom code or a weaker substitute. Trace the active call path: a prompt definition, documented option or missing native adapter does not establish actual behavior or the limits of other supported routes.
- Keep the requested outcome explicit. For primary memory, distinguish configured provider, actual message accumulation, cross-session recall and accuracy in the user's languages; do not report the first milestone as completion of all four. Treat empty profile/context responses as evidence only about that lookup, not proof of an empty backend. Separate retrieval budgets from total storage capacity when answering memory-size questions; use the live inspection procedure in `references/configuration.md`. Store identity and working rules deterministically in their designated instruction files, independently of semantic recall.
- Give a concise, plain-language bottom line first: what works now, what remains unverified and what needs the user's action. Keep research chronology and source-level detail in a linked local report; the user should not need to reconstruct readiness from progress messages.
- Complete agent-runnable preparation and safety checks before asking for personal sign-in or consent. Report a pending browser step as pending until the real authorization flow is ready; do not make the user supply keys, run diagnostics or test the setup when the agent can do that work.
- For launch and appearance requests, inspect effective `display.interface` and `display.skin` first, preserve the selected skin unless a replacement is requested, and configure ordinary `hermes` startup rather than requiring a repeated flag. If a referenced image/name is missing, complete the independently specified launch change and ask only which skin was intended. Verify saved settings separately from observing an actual launch or repaint.
- For this user's terminal branding, preserve the accepted Braille-style red Cyrillic `Я` with one empty rendered row below it, unless a different design is requested. Prefer the active skin's `banner_hero` over renderer changes; preserve the rest of the palette and transcript spacing. Follow the artwork procedure in `references/themes.md`.
- Complete approved Hermes setup changes through the project's documented snapshot, verification, commit and publication workflow without waiting for a separate push reminder when publication is already authorized for that project in the current session. Treat local application and remote publication as separate acceptance checks; read back the exact remote revision and changed artifacts before reporting completion. Keep this user's automatic-publication preference scoped to the Hermes setup project; it does not authorize another repository or private runtime data.
- For returning to a topic after restart, lead with the user's preferred routes: resume by an existing session title or select from a session list. Read actual titles before giving a personalized command; preserve them exactly and do not rename or switch the current conversation merely to demonstrate. Distinguish resuming persisted conversation state from recalling a summary into a new conversation. Follow the Sessions workflow in `references/cli-reference.md` and verify TUI-specific slash behavior in its handler before borrowing classic CLI instructions.

- Resolve source filenames from a scoped inventory before searching them; guessed paths and unmatched shell globs produce misleading missing-path failures. If the file-search tool itself fails, use a bounded local file inventory and then exact paths.
- Anchor each V4A hunk with unique context inside the target method, especially repeated exception handlers and cleanup loops. A separate function-heading hunk does not disambiguate a later hunk. After an ambiguous match, reread the target and include adjacent method-specific statements before retrying.
- Finish verified, publication-eligible Hermes changes by publishing them to the configured setup repository and reading the remote revision back. A local commit alone is not delivery. Exclude confidential workplace integrations, private data and their history; curate shared patches in a separate clean publication checkout rather than merging a mixed private branch.

## Quick Start

```bash
# Install (shell installer — bootstraps PM, Python, dependencies, and the launcher)
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash

# Interactive chat (default surface; set display.interface: tui to launch the Ink TUI instead)
hermes

# Single query
hermes chat -q "What is the capital of France?"

# Setup wizard  /  pick model+provider  /  health check
hermes setup
hermes model
hermes doctor

# Other surfaces
hermes desktop                 # launch the native desktop app (alias: hermes gui)
hermes dashboard               # web admin panel + embedded chat
hermes proxy                   # OpenAI-compatible local proxy backed by your OAuth provider
```

## Key Paths

```
~/.hermes/config.yaml       Main configuration (settings — never secrets)
~/.hermes/.env              API keys and secrets ONLY (under $HERMES_HOME if set)
$HERMES_HOME/skills/        Installed skills
~/.hermes/skins/            Custom themes (see references/themes.md)
~/.hermes/desktop-plugins/  Desktop app UI plugins (see references/desktop-plugins.md)
~/.hermes/tui-widgets/      TUI widget apps (see references/tui-widgets.md)
~/.hermes/pets/             Installed pet mascots (see references/petdex.md)
~/.hermes/state.db          Canonical session store (SQLite + FTS5)
~/.hermes/sessions/         Gateway routing index, request dumps, *.jsonl transcripts
~/.hermes/logs/             Gateway and error logs
~/.hermes/auth.json         OAuth tokens and credential pools
~/.hermes/hermes-agent/     Source code (if git-installed)
```

Profiles use `~/.hermes/profiles/<name>/` with the same layout. When a profile is active, resolve the real home from `$HERMES_HOME` — never hardcode `~/.hermes`.

## Routing Table — load the reference for the task

| User wants... | Load |
|---|---|
| **Anything not listed below — "can Hermes do X?", "how do I set up X?"** | **https://hermes-agent.nousresearch.com/docs/llms.txt** |
| Bots that chat, run routines, or message each other; the Bots tab | docs: `/user-guide/bot-mode` |
| CLI commands, subcommands, flags, "how do I run X" | `references/cli-reference.md` |
| In-session slash commands | `references/slash-commands.md` |
| Provider setup, API keys, OAuth | `references/providers-and-models.md` |
| `spark` / `heretic` shell commands for the local models, independently of Hermes | `references/direct-local-cli.md` |
| Honcho memory, self-hosted prerequisites, private-data egress | `references/honcho-self-hosting.md` + current official docs |
| Existing ChatGPT subscription for a standalone memory backend | `references/honcho-openai-plan-usage.md` |
| config.yaml sections, toolsets, voice/STT/TTS, reasoning effort | `references/configuration.md` |
| AGENTS.md / .hermes.md / CLAUDE.md project rules; global rules (SOUL.md), migrating ~/.claude/CLAUDE.md | `references/project-context-files.md` |
| Switched from Claude Code: port plugins (MCP, skills, hooks), effort, permissions | `references/migrate-from-claude-code.md` |
| Secret redaction, PII, approval modes, "reset permissions", keeping long runs from stalling on approval prompts | `references/security-privacy.md` |
| Delegation, cron, curator, kanban | `references/background-systems.md` |
| A2A between Hermes instances on several machines (Tailscale, tokens, verification), auditing inbound A2A tasks, approvals for peer requests, showing A2A traffic in chat | `references/a2a-peering.md` + `scripts/tailscale-safe-up.sh` |
| A2A: linking Hermes instances across machines/Tailscale, peer tokens, agent cards; serving a peer's relayed task (`session_reply`), plugin update + `gateway_restart` and the post-restart check | `references/a2a-peers.md` |
| MCP servers (add, catalog, `hermes mcp`) | `references/native-mcp.md` |
| Webhook routes and event-driven runs | `references/webhooks.md` |
| A custom theme/skin ("synthwave theme", "change the gold ●"); installing dsfox-skin with its TUI patch | `references/themes.md` + `templates/skin.yaml` |
| "Can I customize the UI?" (general) | Answer in three layers: skin (`hermes skin list/use/set`, `references/themes.md`), surface (`display.interface cli/tui`, `hermes desktop`, `hermes dashboard`), chat display keys (`display.show_reasoning`, `show_cost`, `language`, `pet`). Check current `display.skin`/`display.interface` first and offer to apply |
| A desktop app UI element (pane, widget, ⌘K command, page) | `references/desktop-plugins.md` + `templates/plugin.js` |
| A live TUI panel or modal widget (ticker, clock, dashboard) | `references/tui-widgets.md` + `templates/clock.mjs` |
| Mouse selection, clipboard copy and temporary status feedback | `references/clipboard-selection.md` |
| The custom `activity` status indicator (requires the TUI patch from `hermes-setup`; not in stock Hermes) | `references/activity-status.md` |
| Pet mascots — install, select, scale, diagnose | `references/petdex.md` |
| Windows-specific issues (keybinds, WinError 10106, BOM) | `references/windows-quirks.md` |
| Debugging: voice, tools missing, gateway, aux models, "what are the N sessions in the status bar", `hermes update` fetch failures/timeouts, stuck TUI turn / which process serves a session, old chat won't resume (invalid_params), probing Hermes internals read-only | `references/troubleshooting.md` |
| Contributing code: adding tools, slash commands, tests; writing/enabling/testing a local user plugin in `~/.hermes/plugins/` | `references/contributor-guide.md` |
| delegate_task "capped at N" reports | `references/delegate-task-concurrency-diagnosis.md` |
| "Can app X use my Nous Portal subscription/OAuth?" | `references/portal-auth-for-third-party-apps.md` |
| Connecting a messaging platform (Telegram, Discord, Slack, WhatsApp, …) | docs: `/user-guide/messaging` |

The reference list above is not the feature list — it is the set of topics that
need more than their docs page. For everything else Hermes ships, fetch
`llms.txt` and it maps the question to the page that answers it.

Two theming rules that hold even without loading the reference: **you apply skins yourself** (`hermes config set display.skin <name>` — every surface repaints live within ~a second; don't tell the user to run `/skin`), and **to tweak one color, edit the ACTIVE skin** (`hermes skin set <key> <hex>`, after checking anchor preservation) — never fork `default`, which drops the palette and resets the background.

## Spawning Additional Hermes Instances

Run additional Hermes processes as fully independent subprocesses — separate sessions, tools, and environments.

### When to Use This vs delegate_task

| | `delegate_task` | Spawning `hermes` process |
|-|-----------------|--------------------------|
| Isolation | Separate conversation, shared process | Fully independent process |
| Duration | Minutes (bounded by parent loop) | Hours/days |
| Tool access | Subset of parent's tools | Full tool access |
| Interactive | No | Yes (PTY mode) |
| Use case | Quick parallel subtasks | Long autonomous missions |

### One-Shot Mode

```
terminal(command="hermes chat -q 'Research GRPO papers and write summary to ~/research/grpo.md'", timeout=300)

# Background for long tasks:
terminal(command="hermes chat -q 'Set up CI/CD for ~/myapp'", background=true)
```

### Interactive PTY Mode (via tmux)

Hermes uses prompt_toolkit, which requires a real terminal. Use tmux for interactive spawning:

```
# Start
terminal(command="tmux new-session -d -s agent1 -x 120 -y 40 'hermes'", timeout=10)

# Wait for startup, then send a message
terminal(command="sleep 8 && tmux send-keys -t agent1 'Build a FastAPI auth service' Enter", timeout=15)

# Read output
terminal(command="sleep 20 && tmux capture-pane -t agent1 -p", timeout=5)

# Send follow-up
terminal(command="tmux send-keys -t agent1 'Add rate limiting middleware' Enter", timeout=5)

# Exit
terminal(command="tmux send-keys -t agent1 '/exit' Enter && sleep 2 && tmux kill-session -t agent1", timeout=10)
```

### Multi-Agent Coordination

```
# Agent A: backend
terminal(command="tmux new-session -d -s backend -x 120 -y 40 'hermes -w'", timeout=10)
terminal(command="sleep 8 && tmux send-keys -t backend 'Build REST API for user management' Enter", timeout=15)

# Agent B: frontend
terminal(command="tmux new-session -d -s frontend -x 120 -y 40 'hermes -w'", timeout=10)
terminal(command="sleep 8 && tmux send-keys -t frontend 'Build React dashboard for user management' Enter", timeout=15)

# Check progress, relay context between them
terminal(command="tmux capture-pane -t backend -p | tail -30", timeout=5)
terminal(command="tmux send-keys -t frontend 'Here is the API schema from the backend agent: ...' Enter", timeout=5)
```

### Session Resume

```
# Resume most recent session
terminal(command="tmux new-session -d -s resumed 'hermes --continue'", timeout=10)

# Resume specific session
terminal(command="tmux new-session -d -s resumed 'hermes --resume 20260225_143052_a1b2c3'", timeout=10)
```

### Tips

- **Prefer `delegate_task` for quick subtasks** — less overhead than spawning a full process
- **Use `-w` (worktree mode)** when spawning agents that edit code — prevents git conflicts
- **Set timeouts** for one-shot mode — complex tasks can take 5-10 minutes
- **Use `hermes chat -q` for fire-and-forget** — no PTY needed. The answer box comes BEFORE the session/resume footer, so read the output with `head -30` or in full; `tail` shows only the footer. Prefix `env -u NODE_ENV` if the agent's shell exports it.
- **Run Python that imports Hermes modules with `hermes --run-module <module> ...`** (e.g. `unittest discover`), not with the bundled bare `python3`, which lacks Hermes' dependencies. See `references/contributor-guide.md` → Testing.
- **Pass `--in DIR` to a one-shot session that must work in a project** — `hermes chat --oneshot -Q -q ...` started from a shell `cd`'d into a repo still gets the home directory as its session cwd, so cwd-scoped tools (a plugin that resolves "this session's project") refuse; `--in <repo>` fixes it. This is also the way to live-test such a tool end to end without the user opening a chat.
- **Use tmux for interactive sessions** — raw PTY mode has `\r` vs `\n` issues with prompt_toolkit
- **For scheduled tasks**, use the `cronjob` tool instead of spawning — handles delivery and retry
- **"delegate_task is capped at N" reports** — see `references/delegate-task-concurrency-diagnosis.md`. Three real cap paths in Hermes; if none fired, the model is self-limiting and rationalising it as "the runtime caps."
- **"Can $external_app use my Nous Portal subscription / OAuth?"** — see `references/portal-auth-for-third-party-apps.md`. Walk the user through three layers (plugin-vs-app, what Portal actually exposes, local-broker-proxy option).

## Surfaces (quick orientation)

- **Desktop app** (`hermes desktop` / `hermes gui`) — native Electron app for macOS/Linux/Windows: streaming chat, session list, Cmd+K palette, drag-and-drop files, native notifications, per-profile remote-gateway login. Extend it with UI plugins — `references/desktop-plugins.md`.
- **Web dashboard** (`hermes dashboard`) — full admin panel: messaging channels, MCP catalog, webhooks, memory, profile builder, plus an embedded `hermes --tui` chat. Secured behind an OAuth/token gate.
- **Ink TUI** (`hermes --tui` or `display.interface: tui`) — terminal UI with docked widget apps — `references/tui-widgets.md`.
- **OpenAI-compatible proxy** (`hermes proxy`) — a local OpenAI API backed by whichever OAuth provider you're signed into. Point Codex CLI, Aider, Cline, or any script at it — no API key.

## What takes effect mid-session (say it precisely)

The system prompt and toolset are frozen per session for prompt caching, but not everything waits for a new session:
- **Skills**: usable now via `skill_view(name)`. Only the index line in the prompt is stale; `/reload-skills` rescans it. Never tell the user a new skill "loads in new sessions".
- **Memory**: written to disk at once; changes arrive as in-turn notes.
- **`.env`**: `/reload`. **MCP servers**: `/reload-mcp`.
- **Toolsets** (e.g. `a2a_*` after `hermes tools enable`): only after `/new`. Meanwhile do the same work with what you have, e.g. raw JSON-RPC over `curl` for A2A.

## Hard Invariants (never violate, regardless of what you loaded)

- **Never break prompt caching** — don't change past context, toolsets, or the system prompt mid-conversation. The only exception is context compression.
- **Message role alternation** — never two assistant or two user messages in a row; only `tool` results can repeat.
- **Secrets in `.env`, settings in `config.yaml`** — never tell a user to put a non-credential setting in `.env`.
- **Profile-safe paths** — `get_hermes_home()` in code, `$HERMES_HOME` when resolving paths in a session.
- **Never hand-edit `config.yaml` for the user** — use `hermes config set KEY VAL`; a stray indent can corrupt the file and break the live gateway.
