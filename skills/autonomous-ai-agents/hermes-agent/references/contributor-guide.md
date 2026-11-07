# Contributor Quick Reference

For occasional contributors and PR authors. Full developer docs: https://hermes-agent.nousresearch.com/docs/developer-guide/

### Project Layout

```
hermes-agent/
├── run_agent.py          # AIAgent — core conversation loop
├── model_tools.py        # Tool discovery and dispatch
├── toolsets.py           # Toolset definitions
├── cli.py                # Interactive CLI (HermesCLI)
├── hermes_state.py       # SQLite session store
├── agent/                # Prompt builder, context compression, memory, model routing, credential pooling, skill dispatch
├── hermes_cli/           # CLI subcommands, config, setup, commands
│   ├── commands.py       # Slash command registry (CommandDef)
│   ├── config.py         # DEFAULT_CONFIG, env var definitions
│   └── main.py           # CLI entry point and argparse
├── tools/                # One file per tool
│   └── registry.py       # Central tool registry
├── gateway/              # Messaging gateway
│   └── platforms/        # Platform adapters (telegram, discord, etc.)
├── cron/                 # Job scheduler
├── tests/                # Extensive pytest suite (run via scripts/run_tests.sh)
└── website/              # Docusaurus docs site
```

Config: `~/.hermes/config.yaml` (settings), `~/.hermes/.env` (API keys) — both under `$HERMES_HOME` when it is set.

### Adding a Tool

Two files. Auto-discovery imports any `tools/*.py` with a top-level
`registry.register()` call, but a tool is only *exposed* to an agent once
its name appears in a toolset.

**1. Create `tools/your_tool.py`:**
```python
import json, os
from tools.registry import registry

def check_requirements() -> bool:
    return bool(os.getenv("EXAMPLE_API_KEY"))

def example_tool(param: str, task_id: str = None) -> str:
    return json.dumps({"success": True, "data": "..."})

registry.register(
    name="example_tool",
    toolset="example",
    schema={"name": "example_tool", "description": "...", "parameters": {...}},
    handler=lambda args, **kw: example_tool(
        param=args.get("param", ""), task_id=kw.get("task_id")),
    check_fn=check_requirements,
    requires_env=["EXAMPLE_API_KEY"],
)
```

**2. Wire it into a toolset in `toolsets.py`** — add the name to
`_HERMES_CORE_TOOLS` (every platform) or to a specific toolset.

All handlers must return JSON strings. Use `get_hermes_home()` for paths,
never hardcode `~/.hermes`. For custom/local-only tools, write a plugin in
`~/.hermes/plugins/` instead of editing core — see the developer docs.

### Local user plugins (`~/.hermes/plugins/<name>/`) — preferred over core edits

A plugin worth keeping is its own git repo in the user's projects dir (see `dev-workflow`), linked in with `ln -s ~/dev/<name> ~/.hermes/plugins/<name>`; discovery follows the symlink (`hermes plugins list` shows it as `user`, enabled state is kept). Move an existing copy aside rather than deleting it before linking.

1. Files: `plugin.yaml` (`name`, `version`, `description`, `provides_hooks`), `__init__.py` with `register(ctx)`; split logic into sibling modules imported relatively (`from .store import ...`). Find the API by reading `hermes_cli/plugins.py` (`PluginContext.register_hook/register_command/register_tool/inject_message/register_approval_transport`) and `VALID_HOOKS`; a bundled example is `plugins/disk-cleanup/`.
2. Enable: `hermes plugins enable <name> --no-allow-tool-override` (non-interactive). Extra grants go in `plugins.entries.<name>.*` via `hermes config set` (e.g. `allow_gateway_injection true` for `ctx.inject_message` into gateway/TUI sessions).
3. Activation scope: `enable` reloads the running messaging gateway live (log: `Re-wired plugin handlers`), but an already-running TUI/CLI chat process does NOT load it — hooks and `/commands` appear only in a new session. Before claiming a plugin is live in a process, match `a2a_relay`-style `registered` lines in `~/.hermes/logs/agent.log` against process start times (`ps -o pid,lstart`).
4. One plugin module is loaded in EVERY Hermes process (gateway, TUI, each profile); branch on the process role inside the plugin (e.g. `ctx._manager.has_tui_message_injector` is true only in the TUI host) and keep cross-process state in files under `get_hermes_home()` with a file lock. Plugins can land on Windows nodes too: `fcntl` does not exist there (use `msvcrt.locking`), and `os.kill(pid, 0)` is not a liveness probe on Windows — signal 0 is `CTRL_C_EVENT` there and interrupts/kills the target (probe with `OpenProcess` + `GetExitCodeProcess` via ctypes; `ERROR_ACCESS_DENIED` means alive). Gate POSIX-only code by `os.name` and test both branches before installing on Windows.
5. Per-machine facts for every session: `ctx.register_system_prompt_section(section_id, render_fn)` — `render_fn(session)` is rendered fresh per session, so it can state host-derived facts (hostname, env vars) that shared memory must not carry. It reaches only sessions started after the plugin loaded: verify with a fresh `hermes chat -q "Answer from your system prompt only, no tools: what does the '<section>' line say? NONE if absent."`; gateway sessions get it only after a gateway restart (done by the user, never from inside the agent).
6. Session context inside handlers: read `gateway.session_context.get_session_env("HERMES_SESSION_KEY")`. The TUI binds `HERMES_SESSION_SOURCE` (tui/desktop) around slash-command handlers but leaves `HERMES_SESSION_PLATFORM` empty — fall back to SOURCE; turn hooks (`pre_llm_call`) get `platform=` directly.
7. Test without touching the user's home: `cd ~/.hermes/hermes-agent && HERMES_HOME=$(mktemp -d) hermes --run-module unittest discover -s ~/.hermes/plugins/<name>/tests -v`. "<hermes python>" means `hermes --run-module`, NOT the bare `~/.hermes/tools/python-*/bin/python3` named in the launcher's shebang: a launcher install has no venv, the bare interpreter lacks Hermes deps (`No module named 'ruamel'` → every test importing `hermes_cli` errors), and `--run-module` runs the module after Hermes' bootstrap sets up `sys.path`. Redirect output to a scratch log and grep `^(Ran|OK|FAILED)` rather than piping to `tail` (the pipe hides the exit code). There is no pytest in that environment; load the plugin package in tests via `importlib.util.spec_from_file_location(..., submodule_search_locations=[dir])`). Prefer driving real host functions (e.g. `tools.approval_gateway_wait._await_gateway_decision`) over mocks.
8. Back up first: `cp ~/.hermes/config.yaml ~/.hermes/config.yaml.bak-<name>` before enabling/granting.

### Adding a Slash Command

1. Add `CommandDef` to `COMMAND_REGISTRY` in `hermes_cli/commands.py`
2. Add handler in `cli.py` → `process_command()`
3. (Optional) Add gateway handler in `gateway/run.py`

All consumers (help text, autocomplete, Telegram menu, Slack mapping) derive from the central registry automatically.

### Agent Loop (High Level)

```
run_conversation():
  1. Build system prompt
  2. Loop while iterations < max:
     a. Call LLM (OpenAI-format messages + tool schemas)
     b. If tool_calls → dispatch each via handle_function_call() → append results → continue
     c. If text response → return
  3. Context compression triggers automatically near token limit
```

### Testing

Use `scripts/run_tests.sh` for CI parity. It clears credentials, sets
`TZ=UTC`, and runs each test file in a separate subprocess through
`scripts/run_tests_parallel.py` on every platform. It does not use xdist.

```bash
scripts/run_tests.sh                          # full suite
scripts/run_tests.sh tests/tools/             # one directory
scripts/run_tests.sh tests/tools/test_x.py    # one file
scripts/run_tests.sh -v --tb=long             # pass-through pytest flags
```

- Tests auto-redirect `HERMES_HOME` to temp dirs — never touch real `~/.hermes/`.
- Prepare Python through the PM developer workflow before building a test environment.
- Run `python -m pm.build_env --source . --out .venv --group dev --group test`.
  The output must not exist. Stop its processes and intentionally remove only
  that disposable environment before regeneration.
- The runner probes repository `.venv`, `venv`, and the standard source-install
  venv before falling back to `HERMES_PYTHON`. Each candidate must contain pytest.
- **Windows:** run the same wrapper through Git Bash. See `references/windows-quirks.md`.
- After editing `pyproject.toml`, run `hermes pm lock`, re-source `./activate`, and
  commit `pyproject.toml` with `uv.lock`.
  Do not mutate Hermes environments with raw pip or uv commands.

**Plugin or out-of-tree tests that import Hermes modules** (`hermes_cli.plugins`, `gateway.*` …): run them through the launcher, from the checkout:

```bash
cd ~/.hermes/hermes-agent && hermes --run-module unittest discover -s <plugin>/tests -v
```

The bare interpreter under `~/.hermes/tools/python-*/bin/python3` has no Hermes dependencies, so it fails with `ModuleNotFoundError` (e.g. `ruamel`). The `hermes` launcher adds them at bootstrap, and `--run-module` runs any module with that environment. Use this form in plugin READMEs too, not `<hermes python> -m unittest`.

Host-specific tests run on the real host. Use one `@pytest.mark.platforms(...)`
marker per test, such as `@pytest.mark.platforms("windows", arch="arm64")`.
Do not fake the host by patching `sys.platform` or platform probes.

### System prompt's execution-environment block

Factual host/backend guidance (OS, `$HOME`, cwd, terminal backend, shell)
is emitted by `agent/prompt_builder.py::build_environment_hints()`. The key
invariant for prompt authors: with a **remote** terminal backend
(`docker, singularity, modal, daytona, ssh, managed_modal`), host info is
suppressed and *every* file tool runs inside the backend container — the
prompt must never describe the host the agent can't touch.

### Commit Conventions

```
type: concise subject line

Optional body.
```

Types: `fix:`, `feat:`, `refactor:`, `docs:`, `chore:`

### Key Rules

- **Never break prompt caching** — don't change context, tools, or system prompt mid-conversation
- **Message role alternation** — never two assistant or two user messages in a row
- Use `get_hermes_home()` from `hermes_constants` for all paths (profile-safe)
- Config values go in `config.yaml`, secrets go in `.env`
- New tools need a `check_fn` so they only appear when requirements are met
