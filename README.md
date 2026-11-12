# hermes-setup

A Hermes Agent customization: the `dsfox-skin` theme, a patched terminal UI,
optional independent response review, and capability-evaluation preparation tools.
The default installer installs the visual customization without modifying the
Hermes source checkout and rebuilds it after each `hermes update`. The optional
reviewer has a separate explicit host-patch step; evaluation runs only on request.

| Part | What you get |
| --- | --- |
| Skin (`skins/dsfox-skin.yaml`) | Muted green ANSI-256 palette, high-contrast diffs, `DSFOX-AGENT` wordmark |
| TUI patch (`patches/hermes-tui.patch`) | Chat canvas `#1c1c1c`, black user messages and composer, compact transcript, themed choice cards, `activity` status indicator with elapsed-time colors, copy confirmation on mouse selection, a bright-green stats line after each final reply (time without and with waiting for your answers, tokens/s for the task and for the model, estimated cost `≈$` at API prices) |
| Refusal retry (`plugins/refusal-retry/`) | When the provider's safety filter refuses a request and no fallback provider is configured, the same request is sent again after 10 s and after 60 s; the third refusal ends the turn as before |
| Repo guard (`plugins/repo-guard/`) | A chat working inside one git repository asks you before any tool call reaches another repository (each project keeps its own chat) |
| Optional skill notes | Extended `hermes-agent` skill notes |
| Question wizard | Batched selectors and checkboxes, Back/Next, editable review, one final submission; see [question wizard](docs/question-wizard.md) |
| Optional response review | Local Heretic review, separate attributed output, independent primary-agent assessment; see [response review](docs/response-review.md) |
| Capability evaluation (preparation stage) | Metadata inventory, synthetic comparison inputs and typed outcome checks; no automatic model runs, rankings or archival; see [capability evaluation](docs/capability-evaluation.md) |

Without the patch the skin still applies colors and branding; the canvas,
message backgrounds, choice cards and `activity` indicator need the patch.

## Requirements

- Hermes Agent installed with the official installer (a git checkout under the
  Hermes home), started at least once in TUI mode (`hermes --tui`) so its Node
  dependencies exist.
- `hermes` on `PATH` (the installer calls `hermes skin use` and `hermes config set`).
- `git` and Python 3.9+ (the macOS system `/usr/bin/python3` is enough).

| Platform | Hermes home | Python command |
| --- | --- | --- |
| macOS, Linux | `~/.hermes` | `python3` |
| Windows | `%LOCALAPPDATA%\hermes` | `py -3` (Python launcher) |

`HERMES_HOME`, when set, overrides the Hermes home.

## Install

macOS / Linux:

```sh
git clone https://github.com/dsfox-idea/hermes-setup.git
cd hermes-setup
python3 -I scripts/setup.py install
```

Windows (PowerShell):

```powershell
git clone https://github.com/dsfox-idea/hermes-setup.git
cd hermes-setup
py -3 -I scripts\setup.py install
```

For every profile (`default` and each one under `profiles/`) the script:

1. copies the skin into `<profile>/skins/` and runs `hermes skin use dsfox-skin`;
2. sets `display.interface tui` and `display.tui_compact true`;
3. builds the patched TUI into `<Hermes home>/tui-overlay/ui-tui-<version>` and points
   Hermes at it with `HERMES_TUI_DIR` in the profile's `.env`;
4. sets `display.tui_status_indicator activity`;
5. installs the `tui-overlay` gateway hook into `<Hermes home>/hooks/`;
6. copies `plugins/refusal-retry` and `plugins/repo-guard` into `<profile>/plugins/`,
   enables them and checks that refusal-retry fits the installed Hermes version.

Options, combinable:

| Option | Effect |
| --- | --- |
| `--timezone Europe/Berlin` | Sets `timezone` in every profile |
| `--skill` | Replaces the `hermes-agent` skill with `skills/autonomous-ai-agents/hermes-agent` |

`--skill` first backs up the replaced skill to
`<profile>/backups/hermes-setup-<timestamp>/`.

Exit code 1 means the patch or the refusal-retry plugin does not fit your Hermes
version: the skin is installed, the stock TUI stays (or the plugin leaves Hermes
unchanged and logs `refusal-retry inactive`), and the reason is in the output.

Two lines in the output look like errors and are not: `HERMES_TUI_DIR='' in
profile ...` (the old build is switched off before the new one is made; the path
is filled in a few seconds later) and the esbuild size warning `entry.js 3.9mb`.

The gateway hook starts working after the next gateway start. Run
`hermes gateway restart` once, or let the next `hermes update` do it; until then
an update is not followed by a rebuild.

### Refusal retry

The provider's safety filter sometimes refuses an ordinary request (for example
Anthropic's "Cyber safeguards flagged this message"). Hermes treats a refusal as
final: it tries a configured fallback provider once, otherwise the turn ends. The
`refusal-retry` plugin keeps the fallback step and, with no fallback left, waits
and sends the same request again. While it waits the chat shows
`⏳ The provider's safety filter refused the request — retrying automatically in 10 s (retry 1/2)`;
Esc stops the wait. If every retry is refused, the usual error message ends with
`Retried 2 times (after 10 s, 60 s); the filter refused every attempt.`

The count is per model request, so a normal answer starts the next one at zero.
Both ways Hermes reports a refusal are covered: an answer that stops with a
refusal and an API error classified as a content-policy block. To change the
waits (seconds, at most 5 retries of up to 600 s; an empty list turns retries off):

```sh
hermes config set plugins.entries.refusal-retry.settings.delays '[10, 60]'
```

The plugin wraps two internal Hermes functions at load time and does not modify
the source checkout. After `hermes update`, `scripts/setup.py install` reruns its
compatibility test. It takes effect in sessions started after installation: new
TUI windows and the gateway after its next start.

## Check

```sh
python3 -I scripts/setup.py status    # Windows: py -3 -I scripts\setup.py status
```

It must print `patched TUI current: True`. Then open a new TUI window
(`hermes`): the canvas is dark gray and the wordmark reads `DSFOX-AGENT`.
Windows that were already open keep the old interface until restarted.

`hermes config get display.tui_compact` warns that the key is not recognized.
That is expected: the TUI reads this key, the configuration validator does not
know it.

## After `hermes update`

Nothing to do. The update restarts the gateway; the `tui-overlay` hook then
compares the Hermes version with the last build and rebuilds in the background
(about 15 s). Until the rebuild finishes, and permanently if the patch no longer
fits, Hermes uses its stock TUI. The last run is logged in
`<Hermes home>/hooks/tui-overlay/last-run.log`.

To take a newer version of this customization:

```sh
git pull
python3 -I scripts/setup.py install    # Windows: py -3 -I scripts\setup.py install
```

## Uninstall

```sh
python3 -I scripts/setup.py uninstall  # Windows: py -3 -I scripts\setup.py uninstall
```

This restores the `default` skin and the stock TUI in every profile and removes
the hook. Backups from `--skill` stay in `<profile>/backups/`.

## Platform notes

| Platform | Note |
| --- | --- |
| Windows | Hermes refuses to modify its own running checkout; this setup never does. The build links Node dependencies with NTFS junctions. |
| Warp | Shift+Enter inserts a newline (Warp sends it as LF; the patch treats LF as newline under `TERM_PROGRAM=WarpTerminal`). |
| macOS | Terminals inside IDEs or agents may export `PYTHONPATH` or `NODE_ENV`; `-I` keeps `PYTHONPATH` out of the run, and Terminal.app or iTerm avoids both. |
| Linux | Same commands as macOS. Not yet exercised on Linux. |

### Repo guard

When a chat's working directory is inside a git repository, every tool call is
checked before it runs: the `path`/`workdir` arguments of any tool, and the paths
a terminal command or `execute_code` source names (absolute, `~/`, `$HOME/`,
`../`, and the targets of `cd`, `pushd`, `git -C`). If one of them lies in a
different repository, Hermes' normal approval prompt appears, naming both
repositories. "Once" or "session" continues in this chat; "deny" stops the step
and tells the agent to name the mismatch and offer to hand the work to that
project's chat. A chat without a repository (a service chat, a chat in the home
directory) is not checked. Paths outside any repository, the Hermes home and
repositories nested inside the session's own pass. Runs without anyone to answer
(`hermes chat -q`, cron) follow `approvals.single_query_mode` / `approvals.cron_mode`;
the default `deny` blocks the step.

Directories that never count as foreign:

```sh
hermes config set plugins.entries.repo-guard.settings.allow '["/path/to/shared-repo"]'
```

The command parsing is a heuristic: a path assembled at run time (`D=x; cd $D`)
is not seen.

## Other contents

| Path | Purpose |
| --- | --- |
| `scripts/setup.py`, `scripts/tui_overlay.py` | Installer and patched-TUI builder (`tui_overlay.py status/ensure/disable` handles the TUI alone) |
| `hooks/tui-overlay/` | Gateway hook that rebuilds the TUI after updates |
| `config.example.json` | Non-secret configuration example; set single keys with `hermes config set`, never copy it over a profile |
| `upstream.json` | Hermes revision the patch was cut from, and the patch checksum |
| `plugins/repo-guard/` | Repo-guard plugin and its tests (`python3 -m unittest discover -s plugins/repo-guard/tests`) |
| `plugins/refusal-retry/` | Refusal-retry plugin and its tests (`hermes --run-module unittest discover -s plugins/refusal-retry/tests`) |
| `plugins/heretic-reviewer/`, `scripts/install_review.py` | Explicit, single-profile installation of local response review |
| `patches/response-review-host.patch` | Optional Python-host support; unlike the default TUI overlay, applying this modifies the selected source checkout |
| `scripts/skill_evaluation.py`, `scripts/prepare_skill_trials.py`, `evaluations/skill-selection/` | Portable capability inventory and preparation-only evaluation inputs |
| `skills/` | Skill snapshots, including optional local-model skills |
| `models/`, `plugins/honcho/` | Reference material for optional local models and the Honcho memory plugin; read their own README before use |
| `docs/maintaining.md` | Updating and publishing this repository |
