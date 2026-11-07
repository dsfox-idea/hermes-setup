# Migrating a Claude Code setup to Hermes

Use when the user moves from Claude Code (`~/.claude`) to Hermes and asks what else to carry over. Inspect first, then port each piece by its Hermes equivalent; report what still needs a user action (consent prompts, app restarts).

## 1. Inventory (one batched read)

- `~/.claude/CLAUDE.md` (global rules), `~/.claude/settings.json` (`enabledPlugins`, `extraKnownMarketplaces`, `modelSettings.<model>.effortLevel`, `permissions.allow/deny`), `~/.claude/plugins/installed_plugins.json`.
- MCP servers: `~/.claude.json` top-level and per-project `mcpServers` (parse with Python; `rg` on that file only proves the key exists).
- `git config --global user.name/user.email` vs. the identity the user's rules require: a mismatch affects both harnesses and is worth flagging.
- `hermes import-agent claude-code --dry-run`: covers CLAUDE.md, allow/deny lists, MCP servers, skills with SKILL.md. It does NOT read plugin-bundled MCP servers/skills/hooks, and it maps CLAUDE.md into `memories/MEMORY.md` (tiny hard budget). If the global rules already went to SOUL.md (see `project-context-files.md`), do not run the real import.

## 2. Map each piece

| Claude Code | Hermes |
|---|---|
| `~/.claude/CLAUDE.md` | `$HERMES_HOME/SOUL.md` (append) - `project-context-files.md` |
| `modelSettings.<model>.effortLevel` | `hermes config set agent.reasoning_effort <lvl>` or `agent.reasoning_overrides` - `configuration.md` |
| Plugin `.mcp.json` server | `echo y \| hermes mcp add <name> --command node --args <abs path>` - `native-mcp.md` |
| Plugin `skills/` dir | `hermes config set skills.external_dirs '["<abs path>/skills"]'` (read-only, no copy, edits in the repo apply live); check `hermes skills list` shows it as `external` |
| Plugin `hooks/hooks.json` PreToolUse | shell hook under `hooks.pre_tool_call` - section 3 |
| `claude remote-control` between machines | no 1:1 command; A2A + Telegram hub over an encrypted mesh - `a2a-peering.md` |
| Harness-integration plugins (e.g. terminal-app glue) | nothing to port; say so |
| `skipDangerousModePermissionPrompt` | `approvals.mode` (smart/manual/off) - mention, do not change unasked |

`${CLAUDE_PLUGIN_ROOT}` does not exist in Hermes: substitute the absolute plugin path when porting commands.

## 3. Porting a PreToolUse hook

A Claude Code hook script cannot be wired in unchanged:
- Tool names differ (`WebSearch`/`WebFetch` vs Hermes `web_search`/`web_extract`; MCP tools are `mcp__<server>__<tool>`), and inputs differ (`web_extract` takes `urls: []`, not `url`).
- Hermes reads `{"action":"block","message":...}` or the Claude dialect `{"decision":"block","reason":...}` (source: `agent/shell_hooks.py::_parse_pre_tool_call`). Claude's `hookSpecificOutput.permissionDecision: "deny"` is NOT parsed, so the hook would silently allow.
- Empty stdout = no decision (tool proceeds).

Procedure:
1. Write a small adapter in `$HERMES_HOME/agent-hooks/`, importing shared logic from the original repo by absolute `file:///` URL (Node 24 runs `.ts` directly) so the gate rules stay single-sourced.
2. Make it return nothing for tools it does not gate; the `matcher` is a fullmatch regex, but a defensive early return keeps a broad matcher harmless. Block on unparseable stdin (fail closed).
3. For multi-URL inputs, allow only if every URL passes.
4. Register: `hermes config set hooks.pre_tool_call '[{"matcher": "web_search|web_extract", "command": "node <abs path>", "timeout": 10}]'`.
5. Verify: pipe sample payloads into the script directly (blocked, allowed, mixed, garbage, unrelated tool), then `hermes hooks test pre_tool_call --for-tool <tool> --payload-file p.json` to confirm Hermes parses the output, then `hermes hooks doctor`.
6. Shell hooks need first-use consent and do NOT fire until allowlisted. Do not self-approve; tell the user to run `hermes --accept-hooks` once or answer the TTY prompt.

## 4. Smoke-test the MCP server for real

`hermes mcp test` only proves connect + discovery. Drive one real `tools/call` over stdio (newline-delimited JSON-RPC: `initialize`, `notifications/initialized`, `tools/call`) from a throwaway Node script in `$TMPDIR` and report the actual result, including environment errors the server returns (e.g. a browser not running with its debugging port).

## 5. Making a user-owned plugin harness-neutral (when asked)

Ported MCP servers keep Claude-specific text that misleads a Hermes model (e.g. `mcp__plugin_<plugin>_<server>__<tool>` names, "load with ToolSearch", `WebSearch`/`WebFetch`). Edit in the plugin repo:

1. Inventory: `rg -n -i "claude|mcp__|ToolSearch|WebSearch|WebFetch"` over the server, skills and generator scripts; skip `node_modules`, generated reports and the Claude-only `hooks/` dir (it stays Claude-specific by definition).
2. Rewrite model-facing text by role, not by name: MCP `instructions` ("this server's web_search tool", "the client's built-in web search and page fetch tools"), tool descriptions, and error/fallback messages. Map internal enum values to neutral display names in one place (a static lookup) instead of interpolating the enum into the message.
3. Keep shared persistence keys unchanged (e.g. a grant file's `tool: 'WebSearch'`): both the Claude hook and the Hermes adapter read them, so renaming breaks the gate silently.
4. If a skill file is generated (a `build-guides`-style script), edit the generator AND the generated file, or the next regeneration reverts the text.
5. Grep the WHOLE test tree for each changed phrase before running tests — exact-message assertions live in specs of callers (fetcher/search specs), not only the spec of the edited class. Add a negative assertion (`not.toMatch(/mcp__|ToolSearch|WebSearch|WebFetch/)`) so the coupling cannot return.
6. Follow the repo's own release rules (its CLAUDE.md/AGENTS.md): e.g. bump the plugin version in every manifest that carries it, run its static tests and its plugin validator, then `hermes mcp test <name>`. Commit to the current branch; no push unless asked.
7. Report behavioural couplings left in place (e.g. a server that shells out to `claude -p`) as follow-ups instead of changing behaviour under a wording task.

## 6. Report

List: what was ported and how it was verified, what the user must do (hook consent, restart an app), dependencies on external paths (external skill dirs and hooks break if the repo moves), and leftover Claude-specific wording in ported server instructions or skill descriptions as optional follow-ups (procedure in section 5).