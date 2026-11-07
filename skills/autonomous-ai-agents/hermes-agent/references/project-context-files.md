# Project Context Files

Hermes injects project-level instructions into the system prompt by reading context files from the working directory. The discovery order is **first match wins** — only one project context source is loaded per session.

| File (in priority order) | Discovery | Use when |
|---|---|---|
| `.hermes.md` / `HERMES.md` | Walks parents up to the git root, stops at git root | You want hierarchical project rules (root + per-package overrides) |
| `AGENTS.md` / `agents.md` | Check the installed loader: current implementations collect the git-root-to-cwd chain, with deeper files taking precedence; older versions were cwd-only | You want portable agent instructions that work the same in Hermes, Claude Code, Codex, etc. |
| `CLAUDE.md` / `claude.md` | Cwd only | Same as AGENTS.md, Claude-flavored |
| `.cursorrules` / `.cursor/rules/*.mdc` | Cwd only | Migrating from Cursor |

`SOUL.md` (in `$HERMES_HOME`) is loaded independently when present. Use it for identity and, when explicitly requested, the user's cross-project working agreement; retain repository-specific rules in project context files. Neither role should depend on retrieving generated Honcho conclusions.

### Pick the right one

- **Use `.hermes.md`** when you want Hermes-specific behavior that lives above the cwd (root + subtree), or when you want rules to inherit from a parent directory. The parent walk stops at the git root, so a home-level `.hermes.md` won't leak into every project (a git repo's root is the boundary).
- **Use `AGENTS.md`** when the same project will also be worked on by other agents (Codex, Claude Code, OpenCode). Check `agent/prompt_builder.py::_agents_md_directory_chain` and the callers in the installed revision before describing parent inheritance; tool versions can differ. A global `~/.codex/AGENTS.md` is not automatically a global Hermes source.
- When the user explicitly requests migrating global Codex rules into `SOUL.md`, retain the existing identity, back up the target, copy the requested rules verbatim and measure characters against the installed loader budget. Exercise `load_soul_md` through the actual Hermes runtime and verify that the complete source text survives scanning and truncation. Do not rewrite the active conversation's cached system prompt or confuse the file import with Honcho ingestion.
- **Don't assume a home-level `AGENTS.md` is a global Hermes instruction source.** Check the installed discovery rules before choosing its location. Use `$HERMES_HOME/SOUL.md` for identity and an explicitly requested cross-project working agreement, skills for reusable procedures, and project context files for repository-specific rules.

### Migrating a global ~/.claude/CLAUDE.md (or Codex global rules)

Hermes has no home-level CLAUDE.md equivalent; the only file loaded in every session regardless of cwd is `$HERMES_HOME/SOUL.md` (on Windows `%LOCALAPPDATA%\hermes\SOUL.md`, not `~/.hermes`). Procedure:

1. Check sizes first: SOUL.md + rules must stay under 20,000 chars or the middle is silently dropped.
2. Back up SOUL.md (`SOUL.md.bak`), then APPEND the rules under a heading after the existing identity paragraph. Do not replace or symlink: the identity line and Claude-Code-specific references would be wrong for Hermes.
3. Rewrite harness-specific lines: `CLAUDE.md (in project)` → project `AGENTS.md` or a skill; drop clauses that override another harness's system prompt ("this overrides the system prompt rule ...", superpowers, OpenAI memory approach) but keep the rule itself; rule-source lists become `SOUL.md, AGENTS.md, SKILL.md, memory, hook`.
4. Do replacements by exact-match with a count==1 assert so a drifted phrase fails loudly; afterwards `rg -i 'claude|superpowers|system prompt'` to catch leftovers.
5. Tell the user it takes effect next session (system prompt is already built).

Split guidance if the user wants it thinner: behaviour/style → SOUL.md, procedures → skills, short facts → memory.

Hermes never reads `~/.claude/CLAUDE.md` (CLAUDE.md is cwd-only). Split the rules by kind instead of copying the file:
| Rule kind | Destination |
|---|---|
| Thinking/communication principles that apply to every session (verify facts, conciseness, how to ask the user) | `$HERMES_HOME/SOUL.md` — read it first, keep the existing persona paragraph, append sections |
| Facts about the user (identity, chat language) | memory, target `user` |
| Coding/procedure rules (git, tests, logging, secrets, style) | a class-level skill (e.g. `dev-workflow`) so it loads only for coding |
| "Write a lesson into project CLAUDE.md" | project `AGENTS.md` (read by Hermes, Claude Code, Codex) |
| "Do X daily without reminders" | needs a cronjob — text alone cannot trigger between sessions |
| Rules enforceable by code (commit author, no `.env` commits) | git config / hooks, not prose |

Present the mapping as a plan first, then apply. Verify SOUL.md loads unblocked via `agent.prompt_builder.load_soul_md()` using the Hermes venv python (`~/.hermes/installs/*/environments/*/venv/bin/python`); system `python3` may be too old/new to import the package.

### Editing a context file is gated

A write to an agent-instruction file (`CLAUDE.md`, `AGENTS.md`, `.hermes.md`, `SOUL.md`) by `patch`/`write_file` raises its own approval prompt even in smart mode. If nobody answers, it times out as a denial, and retrying it by another path is forbidden. Make that edit the last step of a task: commit everything else first, tell the owner in the same message that an approval prompt for the instruction file is coming, and then make the edit. A timed-out edit goes in the report as "pending your approval", not silently dropped.

### Size and truncation

Measure characters, not file bytes, and inspect the installed loader's effective budget. The baseline is 20,000 characters; some implementations adjust it for the model's context length. Content beyond the effective budget is **head + tail** truncated, dropping the middle with a truncation marker. After an authorized rules import, exercise `load_soul_md` and assert that the complete requested source text survives, rather than checking only the resulting file size.

### Security

All context files pass through the threat-pattern scanner before reaching the system prompt. Patterns matching prompt injection or promptware are replaced with a `[BLOCKED: ...]` placeholder. This means an `AGENTS.md` containing obvious injection attempts won't reach the model — the scanner blocks the content, not the file, so the rest of the file still loads.

### Disable for one session

Check the installed `hermes --help` before choosing an isolation flag. `--ignore-rules` skips instruction-file, memory and preloaded-skill injection; do not assume it also disables user configuration, plugins or MCP. `--safe-mode` is the broader customization-isolation mode and implies ignoring user configuration and rules. Choose the narrowest mode that preserves the component under test; a provider-lifecycle test must not disable that provider while claiming to verify it.

### Example: a small `.hermes.md`

```markdown
# My Project

Hermes: when working in this repo, follow these rules.

## Build
- Always run `make test` before declaring a change done.
- Use `uv run` for Python, not `pip install`.

## Style
- Prefer `pathlib.Path` over `os.path`.
- No `print()` in production code — use the `logger`.
```

That file at `/home/me/projects/myrepo/.hermes.md` is auto-loaded when Hermes runs in any subdirectory of `/home/me/projects/myrepo`, but not when it runs in `/home/me/other-project`.
