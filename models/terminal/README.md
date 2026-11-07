# Direct local-model terminal commands

The `spark` and `heretic` launchers use AIChat directly against the existing
loopback inference servers. They do not start Hermes, import its code, access
its gateway, forward its complete generated system prompt, load its memory, or
expose its tools. They share the user's instruction files as described below.
The model files and LaunchAgents remain in their existing locations; relocating
or restarting the services is not required.

## Installed interface

```sh
spark
heretic
spark 'Reply in one sentence.'
heretic --no-stream 'Explain this code.'
printf '%s\n' 'Reply with OK.' | spark --no-stream
```

With no arguments, each command opens an interactive, temporary conversation.
Use `.exit` or Ctrl-D to leave and `.help` for the client's built-in help.
Context is retained within that running conversation. Automatic message and
session saving, automatic context summarization, and function calling are
turned off. Normal shell command-history settings remain outside AIChat.
Shared rules are supplied as the initial system message.

## Shared rules by default

Each launch reads the current `$HOME/.hermes/SOUL.md` and the applicable
`AGENTS.md` files without shortening their contents. SOUL already contains the
imported global working agreement; the separate Codex source is not reread.

Within a Git repository, project rules are loaded from its root down to the
launch directory. In each directory, the first nonempty file wins in this order:
`AGENTS.override.md`, `AGENTS.md`, `agents.md`. Identical content is included
only once. Outside Git, only the current directory is checked for project rules.
Missing project rules are allowed; missing, empty or unreadable SOUL prevents
startup rather than silently dropping the common rules. Other Hermes context
file types and the full Hermes runtime prompt are outside this loader's scope.

The launcher creates a private, per-process native AIChat session containing the
system message. This avoids exposing rule contents in process arguments or
interpreting them as AIChat role templates. The temporary file is removed on
normal exit, and separate launches cannot overwrite each other's project rules.
Running chats keep their starting rules; restart to pick up file edits.
Explicit AIChat context choices such as `--prompt`, `--role` or `--session`
replace this default context. Rules do not add agent tools to these plain chats.

Heretic keeps thinking enabled. AIChat may print its separate reasoning inside
`<think>` blocks, including with `--no-stream`; that option controls streaming,
not reasoning. Spark keeps its configured thinking-disabled mode. These are
plain model chats, not the `@spark` / `@heretic` agent workflows.

## Dependencies and paths

Verified client: Homebrew `aichat` 0.30.0. The shared-rule loader uses Python 3
and its standard library, independently of the Hermes Python environment.

| Command | Model | Endpoint |
| --- | --- | --- |
| `spark` | `spark-x2.6-4b` | `http://127.0.0.1:18320/v1` |
| `heretic` | `qwen36-35b-heretic` | `http://127.0.0.1:18319/v1` |

Launchers are installed in `$HOME/.local/bin`. Each selects its own
`$HOME/.config/local-model-chat/<name>/config.yaml`; no existing AIChat profile
is changed. The wrappers bypass HTTP proxies for loopback destinations. They
require `aichat` and `python3` to be on PATH. The loader is installed at
`$HOME/.local/share/local-model-chat/shared_rules.py`. Models are not downloaded
again, and the original instruction files are not copied or modified.

## Restore on another configured machine

Install AIChat and the separately documented model services first. Check that
`spark` and `heretic` do not already name other commands before installing:

```sh
brew install aichat
mkdir -p "$HOME/.local/bin"
install -d -m 755 "$HOME/.local/share/local-model-chat"
install -m 644 models/terminal/shared_rules.py "$HOME/.local/share/local-model-chat/shared_rules.py"
install -d -m 700 "$HOME/.config/local-model-chat/spark" "$HOME/.config/local-model-chat/heretic"
install -m 755 models/terminal/spark "$HOME/.local/bin/spark"
install -m 755 models/terminal/heretic "$HOME/.local/bin/heretic"
install -m 600 models/terminal/spark.yaml "$HOME/.config/local-model-chat/spark/config.yaml"
install -m 600 models/terminal/heretic.yaml "$HOME/.config/local-model-chat/heretic/config.yaml"
```

Ensure `$HOME/.local/bin` and the Homebrew binary directory are on the shell's
PATH. On the current machine they already are; no shell startup file was edited.
If a model service is unavailable, the client reports the connection error; the
configuration contains no cloud destination or fallback.

After installation, run `python3 -m unittest discover -s models/terminal -p
'test_*.py' -v` to check discovery boundaries, overrides, rereading, missing rules
and complete rule inclusion through the real client's dry-run mode. Real
loopback requests and interactive launches were also exercised for both models.
