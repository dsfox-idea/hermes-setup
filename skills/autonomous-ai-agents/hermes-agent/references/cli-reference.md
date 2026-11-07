# Hermes CLI Reference

Live sources when anything looks stale: `hermes --help`, `hermes <command> --help`,
https://hermes-agent.nousresearch.com/docs/reference/cli-commands

### Global Flags

```
hermes [flags] [command]        (no subcommand = interactive chat)

  --version, -V             Show version
  -z, --oneshot PROMPT      One-shot: print ONLY the final response (for scripts/pipes)
  -m MODEL  --provider P    Model/provider override for this invocation
  -t, --toolsets LIST       Comma-separated toolsets for this invocation
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode (parallel agents)
  --skills, -s SKILL        Preload skills (comma-separate or repeat)
  --profile, -p NAME        Use a named profile
  --yolo                    Skip dangerous command approval
  --tui / --cli             Force the Ink TUI / classic REPL
  --ignore-rules            Skip AGENTS.md/SOUL.md/memory/skill injection
  --safe-mode               Disable ALL customizations (troubleshooting)
  --pass-session-id         Include session ID in system prompt
```

### Chat

```
hermes chat [flags]
  -q, --query TEXT          Single query, non-interactive
  --image PATH              Attach a local image to a single query
  -Q, --quiet               Suppress banner, spinner, tool previews
  --checkpoints             Enable filesystem checkpoints (/rollback)
  --max-turns N             Cap tool-calling iterations
  --source TAG              Session source tag (default: cli)
```
(plus the global flags above)

### Configuration

```
hermes setup [section]      Wizard (model|tts|terminal|gateway|tools|agent)
hermes model                Interactive model/provider picker
hermes fallback [add|remove|list]  Fallback provider chain
hermes config [show|edit|get|set|unset|path|env-path|check|migrate]
hermes login / logout       OAuth sign-in / clear stored auth
hermes doctor [--fix]       Check dependencies and config
hermes status [--full]      Component summary (--full: every section)
```

### Tools & Skills

```
hermes tools [list|enable NAME|disable NAME]   Per-platform toolsets (curses UI with no args)

hermes skills list|browse|search QUERY|inspect ID
hermes skills install ID    Hub identifier OR a direct https://…/SKILL.md URL
hermes skills config        Enable/disable skills per platform
hermes skills check|update|uninstall|publish PATH
hermes skills tap add REPO  Add a GitHub repo as a skill source
hermes bundles              Skill bundles (one /<name> alias loads several skills)
```

### MCP Servers

```
hermes mcp add NAME (--url or --command) | remove | list | test NAME
hermes mcp catalog | install NAME     Curated catalog install
hermes mcp configure NAME             Toggle tool selection
hermes mcp serve                      Run Hermes as an MCP server
```
Details (transport, tool discovery, catalog): `references/native-mcp.md`.

### Gateway (Messaging Platforms)

```
hermes gateway run|install|start|stop|restart|status|setup
```

20+ platforms: Telegram, Discord, Slack, WhatsApp (Baileys + Business Cloud API), iMessage (Photon — `hermes photon setup`), Signal, Email, SMS, Matrix, Mattermost, Teams, LINE, SimpleX, ntfy, Google Chat, Home Assistant, DingTalk, Feishu, WeCom, Weixin, API Server, Webhooks. Open WebUI connects via the API Server adapter. Most adapters ship under `plugins/platforms/`.
Docs: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/

### Sessions

```
hermes sessions list|browse|rename ID TITLE|delete ID|export OUT|prune|stats
```

#### Returning to a topic after restart

1. Check `hermes --help`, `hermes sessions browse --help`, and `hermes config get display.interface`. Use `--tui` as a launch flag; do not assume a `hermes tui` subcommand. Keep an already-configured TUI default rather than changing settings for this question.
2. Read `hermes sessions list --limit 10` before supplying an actual title. Use `hermes sessions list --workspace <path-or-name>` when the list needs narrowing. Stay within the active profile unless the user identifies another one. Preserve titles exactly, including apparent typos; use the durable ID when the name is ambiguous.
3. Lead with the two requested entry points:

   ```bash
   hermes -c "topic-name"
   hermes sessions browse
   ```

   `hermes --resume "topic-name"` also accepts a title or ID. The standalone browser supports interactive selection and search, then relaunches Hermes with the selected session ID. Explain that the browser belongs in the shell, not in the chat input.
4. Offer `hermes -c` or `hermes --resume latest` only as the latest-session shortcut. Verify workspace scoping in the installed help rather than calling it the globally latest session. Where supported, `hermes --tui --resume latest --in /path/to/project` selects that workspace and stays in the specified directory; ordinary resume may restore the recorded working directory.
5. For an already-running TUI, inspect `ui-tui/src/app/slash/commands/session.ts` and the session switcher before describing controls. In the inspected implementation, bare `/sessions` and `/resume` open the same list of live and stored sessions; arrow keys and Enter select a row, and `/resume <id-or-title>` resumes a saved session. Do not infer that this list has the standalone browser's search controls without checking its implementation. See `references/slash-commands.md`.
6. Explain naming with `/title topic-name`; rename a stored session with `hermes sessions rename ID "topic-name"` only when requested. A how-to question does not require changing session state or opening a second interactive process. Report command/help and code inspection as inspection, not as an exercised end-to-end restart.

Resuming uses persisted conversation state, which may include prior compression. Recalling an old discussion into a new session reconstructs context but does not attach that original session. Do not promise an uncompressed transcript or complete original model context merely because resume is supported.

### Cron / Webhooks

```
hermes cron list|create SCHED|edit ID|pause|resume|run ID|remove|status
    Schedules: '30m', 'every 2h', '0 9 * * *', ISO timestamp
hermes webhook subscribe NAME|list|remove NAME|test NAME
```
Webhook payloads/routes: `references/webhooks.md`.

### Profiles

```
hermes profile list|create NAME (--clone|--clone-all|--clone-from)|use|show|delete
hermes profile rename A B | alias NAME | export NAME | import FILE
hermes profile migrate-identity A B   Retry a completed rename's session/routing identity migration
```

### Credentials & Pools

```
hermes auth                 Interactive credential manager
hermes auth add [PROVIDER]  Add OAuth or API-key credential (nous, openai-codex, qwen-oauth, …)
hermes auth list|remove P IDX|reset PROVIDER|status
```
Multiple credentials per provider form a pool that rotates automatically and skips exhausted keys.

### Other

```
hermes desktop / gui        Native desktop app
hermes dashboard            Web admin panel + embedded chat (--stop / --status)
hermes proxy                OpenAI-compatible local proxy backed by an OAuth provider
hermes portal               Quick setup / sign in via Nous Portal
hermes kanban <verb>        Multi-agent work-queue board
hermes project              Named multi-folder workspaces
hermes skin list|use|set    Switch/tweak skins (see references/themes.md)
hermes pets <verb>          Pet mascots (see references/petdex.md)
hermes memory setup|status|off|reset   Memory provider
hermes secrets bitwarden|onepassword   External secret stores
hermes moa                  Mixture-of-Agents slots
hermes hooks / security / backup / import / checkpoints / console
hermes logs [-f] [errors]   View agent/error logs
hermes send                 One-off message through a gateway platform
hermes pairing / plugins / insights / journey / computer-use
hermes acp                  ACP server (IDE integration)
hermes completion bash|zsh|fish
hermes update / uninstall / claw migrate
```

Plugin- and provider-supplied subcommands (e.g. `hermes photon setup`) only appear once their plugin is installed/active.

### Where to Find Things

| Looking for... | Location |
|---|---|
| Config options | `hermes config edit` · [Configuration docs](https://hermes-agent.nousresearch.com/docs/user-guide/configuration) |
| Tools / toolsets | `hermes tools list` · [Tools reference](https://hermes-agent.nousresearch.com/docs/reference/tools-reference) |
| Skills catalog | `hermes skills browse` · [Skills catalog](https://hermes-agent.nousresearch.com/docs/reference/skills-catalog) |
| Provider setup | `hermes model` · [Providers guide](https://hermes-agent.nousresearch.com/docs/integrations/providers) |
| Env variables | `hermes config env-path` · [Env vars reference](https://hermes-agent.nousresearch.com/docs/reference/environment-variables) |
| Gateway logs | `~/.hermes/logs/gateway.log` (or `hermes logs`) |
| Sessions | `hermes sessions browse` (reads state.db) |
