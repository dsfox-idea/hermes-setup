# Windows-Specific Quirks

Hermes runs natively on Windows (PowerShell, cmd, Windows Terminal, git-bash
mintty, VS Code integrated terminal). Most of it just works, but a handful
of differences between Win32 and POSIX have bitten us — document new ones
here as you hit them so the next person (or the next session) doesn't
rediscover them from scratch.

### Input / Keybindings

**Alt+Enter doesn't insert a newline** — Windows Terminal (and mintty) grab it
for fullscreen before prompt_toolkit sees it. Use **Ctrl+Enter** instead (the
CLI binds it to newline on Windows; raw Ctrl+J does the same, harmlessly).
To inspect how your terminal reports a keystroke, run
`python scripts/keystroke_diagnostic.py` from the repo root.

### Config / Files

**HTTP 400 "No models provided" on first run** — `config.yaml` was saved with
a UTF-8 BOM (Notepad does this). Re-save as UTF-8 without BOM;
`hermes config edit` writes correctly.

### `execute_code` / Sandbox

**WinError 10106** from the sandbox child process — it can't create an
`AF_INET` socket. Root cause is usually Hermes's env scrubber dropping
`SYSTEMROOT`/`WINDIR`/`COMSPEC` (Python's `socket` needs `SYSTEMROOT` to find
`mswsock.dll`), not a broken Winsock LSP. The `_WINDOWS_ESSENTIAL_ENV_VARS`
allowlist in `tools/code_execution_env.py` covers it; if you still hit it,
echo `os.environ` inside an `execute_code` block to confirm `SYSTEMROOT` is set.

### Running PowerShell from the `terminal` tool (bash)

- Do not put PowerShell with `$_`/`$var` inside `powershell -Command "..."` from bash: bash expands `$_`, `$_.Name` etc. first and the command breaks (and floods output with errors). Write a `.ps1` to the scratch dir and run `powershell -NoProfile -ExecutionPolicy Bypass -File <path>`.
- Console output is OEM codepage (Russian text garbles). Start the script with `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`, or write results to a file with `Out-File -Encoding utf8` and read it with `read_file`/`cat`.
- Admin-only actions (`sc config`, service start) fail with access denied (error 5). Put them in a `.ps1` that logs to a file, run via `Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',<ps1>` (the user approves UAC), then read the log. Get the user's go-ahead before changing a service.

### Long jobs that must outlive the turn or a gateway restart

- Terminal `background=true` jobs and `Start-Process` children stay in the gateway's process tree and can die with it. Start long jobs (downloads, servers) through WMI from a `.ps1`: `Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = $dir }`, which returns at once with `ProcessId`/`ReturnValue` (0 = started). This was used for multi-hour jobs; it has not yet been tested through a real gateway restart.
- Keep the job's scripts and logs outside the scratch dir (for example `A:\<job>-scripts\logs`): scratch entries are pruned after 24 h idle.
- Inside a `.ps1`, never name a variable `$args` (it is automatic; `Start-Process -ArgumentList $args` silently passes the wrong list). After `Start-Process -PassThru`, touch `$p.Handle` once, otherwise `ExitCode` is empty after `WaitForExit()`.
- The terminal tool masks digit runs that look like secrets in its output (`python-3.14.7+202****0901`). Never copy a path from tool output into a script: resolve it in the script (`Get-ChildItem <dir> -Filter 'python-3.14*'`) and check it with `Test-Path`.
- Bandwidth check without extra tools: `du -cb <files> | tail -1` twice, 60 s apart.

### Running Hermes's own Python for probes

The `hermes` launcher is an exe/cmd wrapper, not a venv; Hermes runs on the bundled interpreter `$HERMES_HOME/tools/python-3.14*/python.exe`. To call Hermes internals (e.g. `hermes_cli.commands_platforms.telegram_menu_commands`), write the probe to the scratch dir, `sys.path.insert(0, <hermes-agent dir>)`, `import hermes_bootstrap` first, and run `"$PY" -I 'C:/Users/.../scratch/probe.py'` with `PYTHONIOENCODING=utf-8`. To run a probe that imports a plugin package (relative imports) with Hermes' own deps, without a venv path: put the script in its own scratch dir and run `hermes --run-module unittest discover -s <that dir> -p <file>.py` from the hermes-agent dir; module-level code runs at import (output ends with "NO TESTS RAN", ignore it). `hermes --run-module runpy <path>` and a `PYTHONPATH` pointing at scratch do not find the file. Load the plugin with `importlib.util.spec_from_file_location(name, <plugin>/__init__.py, submodule_search_locations=[<plugin>])`. Pass the script as a literal `C:/...` path: in the terminal tool `$TMPDIR` can resolve to `/tmp`, which native programs cannot open, so a stale file elsewhere gets run instead. The same holds for any file a native tool (`hermes`, `rg`, python) writes or reads, including output redirects meant for it: always spell `C:/Users/<user>/AppData/Local/hermes/cache/scratch/...` literally.

### Running commands in WSL from the terminal tool

- Never inline a command with `$var`, loops or nested quotes into `wsl -d <distro> -- bash -c '...'`: the text passes through more than one shell and variables arrive empty (`ollama pull $m` ran with no argument). Write a `.sh` to the scratch dir and run `wsl -d <distro> [-u root] -- bash /mnt/c/Users/<user>/AppData/Local/hermes/cache/scratch/<dir>/<file>.sh`.
- Pipe WSL output through `tr -d '\0'` (wsl.exe output can carry NUL bytes).
- Read and search files inside the distro with `read_file`/`search_files`/`write_file` on `\\wsl.localhost\<distro>\home\<user>\...`; Windows tools such as `rg` need not exist inside the distro.

### Hardline blocklist false positives

The terminal tool hard-blocks any command whose TEXT looks like a system shutdown/reboot, including a search pattern that merely contains such a word (an `rg` regex over Hermes source). No approval mode overrides it. Search with the `search_files` tool instead, or split the word out of the pattern.

### Installer failures (winget/MSI)

A silent `winget install` shows no progress. Check it instead of re-waiting: the newest `$LOCALAPPDATA/Packages/Microsoft.DesktopAppInstaller_8wekyb3d8bbwe/LocalState/DiagOutputDir/WinGet-*.log` names the download URL and temp path; compare the temp file size under `$LOCALAPPDATA/Temp/WinGet/<pkg>/` with the URL's `Content-Length` (`curl -sI -L`).


Exit code 1603 is generic. The log path is printed by winget (`...DiagOutputDir\<pkg>.log`); `search_files` it for `Return value 3` and the lines just above it. Example cause: Tailscale's MSI requires the IP Helper service `iphlpsvc`, and refuses to install when it is Disabled; fix with `sc config iphlpsvc start= demand` + `sc start iphlpsvc` (elevated), then rerun the install.

### Testing on Windows

Prepare the checkout through PM first. With its Python 3.14, build an independent
test environment at a fresh path:

```powershell
python -m pm.build_env --source . --out .venv --group dev --group test
```

The output must not exist. Before regeneration, stop its processes and explicitly
remove only that disposable environment. Do not install into the application
payload or modify a selected dependency generation.

Run the canonical runner through Git Bash:

```bash
scripts/run_tests.sh tests/foo/test_bar.py -v --tb=short
```

The runner discovers `.venv/Scripts/python.exe`, clears credentials and
`PYTHONPATH`, and isolates each test file. For an external test environment,
set `HERMES_PYTHON` to its Python executable. PM shell activation alone does
not supply pytest after the runner clears `PYTHONPATH`.

### Gateway self-restart (agent running inside the gateway)

**Never stop or restart the gateway you are running in** — `hermes gateway restart`,
`hermes gateway stop`, `hermes gateway uninstall`, killing the gateway python
process, or any script doing these. The agent's `terminal` command dies with the
gateway shutdown, so the "start" half of a restart never runs; the TUI then loops
on "scheduling gateway reconnect" and does NOT bring the gateway back by itself.
Smart-approval auto-approves these commands — do not rely on it as a guard.

Safe restart from inside: the `/restart` chat command path (`GatewayRunner.request_restart`)
refuses new turns, waits for running ones (the calling turn included), then a detached
watcher (Windows) or launchd/systemd (exit 75) starts the new process. a2a-relay exposes
it as the `gateway_restart` tool and has the new process post a notice into the asking
chat; another machine is restarted by asking its agent over A2A to call the tool. It is
live-verified on this PC (PID changes, notice arrives ~45 s later): use it instead of
asking the user; the user wants restarts automated. Plugin code must not
`import gateway.run` to find the runner (importing it sets `_HERMES_GATEWAY=1`); read
`sys.modules.get("gateway.run")._gateway_runner_ref()` instead. Plugins register a few
seconds BEFORE the gateway creates its runner, so anything a plugin does "once the gateway
is up" must poll for the runner in a thread, not check once at `register()`. After a
restart, check `logs/gateway-exit-diag.log`: more than one `gateway.start` per restart
means a duplicate gateway was spawned. Mechanism (traced on this PC): when the old
gateway exits, the open TUI clients find no gateway and auto-start
`gateway run --quiet --idle-exit` (two at once; one loses with "Another gateway instance
is already running"); meanwhile the detached restart watcher runs `hermes gateway
restart`, which stops that client-started gateway (SIGKILL after 30 s if a turn is
running) and starts the final one (`gateway run` without `--idle-exit`). So anything the
FIRST new gateway does can die with it: a plugin's "back" notice delivered there starts a
turn that gets killed (the chat shows "An automated delivery was interrupted and was not
run again"); one restart can kill two client-started gateways in a row. Working fix
(live-verified, a2a-relay `gateway_restart`): on Windows do NOT use Hermes' watcher
(`request_restart(detached=False)`), and spawn Hermes' own watcher script
(`gateway.run_shutdown._WINDOWS_RESTART_WATCHER` via `hermes_cli._launchers.runtime_command`,
env from `GatewayShutdownMixin._restart_watcher_env()`) with `gateway start` instead of
`gateway restart`: `start` is a no-op when a client already brought a gateway up, and starts
one when no client is open. Fall back to the Hermes watcher if the spawn fails; kill the
spawned watcher if the restart is refused; leave service-managed gateways (exit 75) alone.
A plugin that announces after restart must also keep its marker until the announcing
gateway has survived a grace period (record the announcer's pid; check liveness with
`hermes_cli._subprocess_compat.pid_exists_stdlib`), and re-announce from a later gateway if
the announcer died. The "took N s" in a restart notice includes the drain wait for the
calling turn; the stop-start itself is ~30 s.

Before judging a live test of plugin code that runs at restart, check that the gateway being
restarted had loaded that code: compare the last `a2a-relay: registered` time in `agent.log`
with the commit time. The restart that loads new code still runs the OLD restart path, so a
fix to the restart path itself needs one restart to load and a second one to test.

When a restart notice turn ends interrupted, or the user asks why work did not resume,
read `gateway-exit-diag.log` (`gateway.start`/`exit_*`/`previous_unclean_exit` per pid)
and `errors.log` ("did not exit within 30s") first, then resume the pending work in the
same turn: do not wait for another notice.

Fallback when the tool is not available or not yet verified: finish the turn, then ask
the user to run in a SEPARATE terminal:

```
hermes gateway restart
hermes gateway status
```

If `status` says "No gateway process detected": `hermes gateway ensure` (verified
to bring it to `"state":"ready"`; the open TUI reattaches within ~30 s). Then verify
with `hermes gateway status` and, for A2A, `a2a connected` in `logs/gateway.log`.

Batch restarts: when two pending changes both need a restart (a plugin release and an
A2A token change), say so and propose doing both before one restart on every machine.
New plugin tools may still reach a running session through the deferred tool catalog:
run `tool_search` for them after the restart before telling the user to open a new
session (`/new`).

Verify a reported restart per machine instead of trusting "restarted everywhere": on this
PC the PID in `hermes gateway status` must differ from the one noted before (also
`(Get-Process -Id <pid>).StartTime` and the last `gateway.start` in
`logs/gateway-exit-diag.log`); on Macs ask the peer for `ps -o lstart= -p <launchd pid>`.
Note the old PID in the restart request so the user can check it too.

After the user reports a restart (or the session reconnects), the first action is to
re-check everything pending before answering anything else: the change that needed the
restart (log line, route/card URL), own background processes and in-flight edits,
peer tasks. Ask the user only for what those checks show is still needed. A peer's config
change that needs ITS gateway restart is likewise checkable (route 404 vs 200).

### Hermes updates

`hermes update` restarts the gateway, so it falls under the self-restart rule above: the user runs it in a separate terminal. `hermes update --check` (channel + commits behind), `hermes update --plan` (install, profiles, services to restart and the code version each runs) and `hermes update --list-venv-holders` (`[]` = nothing locks the venv on Windows) change nothing and are safe to run yourself.

Procedure on this PC (verified: plain `hermes update` brought the gateway back by itself with a new PID):
1. Baseline before: `--plan`, `--list-venv-holders`, `hermes a2a-relay doctor`, plugin tests (`hermes --run-module unittest discover -s <plugin checkout>/tests`). A baseline makes a post-update failure attributable.
2. Scan `git log --oneline HEAD..origin/main` for `a2a|plugin|gateway|revert|leaving core` before recommending; a2a-relay rides on Hermes internals, so say its compatibility is proven only by running it.
3. User runs `hermes update` in a separate terminal.
4. After: `git rev-list --count HEAD..origin/main` (0), `hermes gateway status` (new PID), `a2a connected` and no new errors in `logs/gateway.log`/`errors.log`, doctor, plugin tests, `a2a_call` ping to every peer. Inbound directions are proven only by peers pinging this host. Before recommending an update, compare the reported channel with the user's stated channel preference (stored in memory); if they differ, raise the discrepancy instead of recommending the jump. To learn whether a needed upstream fix is in a release, use `git merge-base --is-ancestor <sha> HEAD|origin/main` locally and `gh api repos/NousResearch/hermes-agent/compare/<tag>...<sha>` (status `behind`/`identical` = included).

Moving the fleet to one channel: the channel is per install (`hermes config get update` -> `installs.<id>.channel`; `--install-id` prints the id). On a stable install the user runs, in a separate terminal, `hermes update --set-channel main` (only writes the record and exits) then `hermes update`; macOS gateways under launchd come back by themselves. Update this PC first and verify it before giving the peers their commands. `main` moves constantly, so machines updated an hour apart differ by dozens of commits: verify that the needed fix is in each machine's HEAD (`git merge-base --is-ancestor`) instead of chasing identical SHAs. Machines updated within the same few hours count as in sync for the user: never propose re-updating one of them to catch up a handful of newer commits (it only splits the fleet again); mention a security-relevant commit in that gap as "next routine update" instead. Before sending any peer an update task, ask it read-only for `git -C <hermes-agent dir> log -1 --format='%h %cd'` and compare locally with `git merge-base --is-ancestor <peer-sha> HEAD` / `git rev-list --count`: peers are often updated separately and can already be AHEAD of this PC, making the task pointless. Ask for version info with `hermes --version` / `git rev-parse` only: any A2A command containing `hermes update` (even `--plan`/`--check`) goes to the peer owner's approval prompt, also with a2a-relay installed, and with nobody at that machine it is denied after the approval timeout and the peer is told not to retry. A peer update is therefore the user's action at that machine, or needs him present to answer the prompt; say so up front.

A task that ends with the peer calling `gateway_restart` cannot also contain post-restart checks: the restart waits for the calling turn to finish, so the reply goes out first, and the restart notice goes only to owner chats, never to the A2A session that asked. Leave post-restart steps out of the task text entirely (a peer told to "re-run doctor after the notice" promises a second reply that never comes). Do the post-restart checks yourself: curl each peer's agent card until 200, then ask for `doctor --no-network` in a new task.

### A2A on this host (verified)

- Inbound A2A needs `A2A_ALLOWED_USERS=<peer names>` (e.g. `mac1,mac2`) in `.env`.
  The adapter declares `authorization_is_upstream`, but session admission
  (`gateway/session_envelope.py` `_validate_native`) checks the allowlist with
  `allow_adapter_delegation=False`, so without it every inbound message fails
  with `RuntimeStoreError: permission_denied` (audit shows `[agent processing
  failed]`). Peer name = sender `user_id` from the bearer token. A wrong token
  still gets HTTP 401, so the allowlist does not weaken auth.
- `A2A_HOST` is the Tailscale address. If Tailscale is down the bind fails with
  `WinError 10049` and a2a retries every 60 s. Check `tailscale status`;
  `tailscale up` restores without a new login. Never `tailscale down`.
- Peer tokens are asymmetric: `A2A_PEER_TOKENS="mac1:X,mac2:Y"` is what peers must
  present to us; `A2A_PEER_MAC1_TOKEN` (used in `a2a_agents.mac1.auth.token`) is what
  we present to mac1. On the Mac side these are mirrored.
- A config change made after session start does not add the `a2a_*` tools to the
  running session; a new session is needed. Inbound A2A sessions use
  `platform_toolsets.a2a` (enable with `hermes tools enable a2a --platform a2a`).

### git push hangs from the terminal tool

The bundled Hermes git (`$HERMES_HOME/tools/git-*/etc/gitconfig`) sets `credential.helper=helper-selector`, which waits on a GUI picker and hangs `fetch`/`push`/`ls-remote` forever (curl to github.com still answers 200, so it looks like a network outage). Reset the helper list for the call: `GIT_TERMINAL_PROMPT=0 git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push origin main` (gh is logged in; verified). Wrap each network git call in `timeout 60` so a hang fails instead of eating the tool's whole timeout. Diagnose with `GIT_TRACE=1`: the last line before the stall names the helper being run.

### `hermes config set` prints only "(Use --force to skip this notice.)"

Some keys (for example `a2a_agents.<peer>.timeout`, `.capabilities`) print just that notice. Always confirm with `hermes config get <key>`. If the value is missing, rerun with `--force` (verified to set it).

### tar and sed in git-bash

- GNU `tar -f C:/path/x.tgz` treats `C:` as a remote host (`Cannot connect to C: resolve failed`). `cd` into the directory and use a relative archive name, or add `--force-local`.
- Do not edit source code with `sed -i` when the replacement holds an escape like `\n`: sed turns it into a real newline and breaks the string literal. Use the `patch` tool for code edits.
- Python on Windows writes CRLF in text mode. Files shipped to Macs/Linux (skills, scripts) need `write_text(..., newline="\n")`; check with `rg -l $'\r' <dir>` (exit 1 = clean).

### Porting POSIX plugin code to Windows

Review these before you enable a plugin written on a Mac/Linux, because some failures are destructive rather than loud:

- `os.kill(pid, 0)` used as a liveness probe is dangerous on Windows. Signal 0 equals `signal.CTRL_C_EVENT`, so the call sends Ctrl+C to the target instead of probing it. Use ctypes with no extra dependency: `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION=0x1000)`. A NULL handle with error 5 means the process is alive but you lack access; any other NULL means dead. Then `GetExitCodeProcess == STILL_ACTIVE (259)`. Psutil exists in the Hermes venv on this PC but is not guaranteed on peers. Test the probe this way: spawn a sleeping child, probe it, then assert `proc.poll() is None`.
- `fcntl` does not exist on Windows. For a cross-process lock, use `msvcrt.locking` on a 1-byte region, as Hermes' own memory store does. Open the lock file with `"a+"` and `seek(0)` before locking and before unlocking, because the lock covers bytes from the current position. `LK_LOCK` raises after about 10 s, so loop on `OSError` to get blocking `flock` semantics. Branch on `os.name == "nt"`. Test with a child process that holds the lock while the parent waits.
- `os.replace` onto a file that another process holds open fails with PermissionError (winerror 5) on Windows. Shared state files read by both the gateway and the TUI need a short retry loop. Remove the tmp file if the last attempt fails.
- Installing a plugin by `ln -s` needs Developer Mode or admin rights on Windows. A directory junction works without either (verified): put `New-Item -ItemType Junction -Path $Link -Target $Target` in a `.ps1` and run it with `-File`. `cmd //c mklink /J` run from the bash terminal tool opens an interactive cmd and creates nothing. Hermes loads plugins through the junction, and `git pull` in the clone updates the plugin.

### Path / Filesystem

**Line endings.** Git may warn `LF will be replaced by CRLF`. Cosmetic — the
repo's `.gitattributes` normalizes. Don't let editors auto-convert committed
POSIX-newline files to CRLF.

**Forward slashes work almost everywhere.** `C:/Users/...` is accepted by
every Hermes tool and most Windows APIs. Prefer forward slashes in code
and logs — avoids shell-escaping backslashes in bash.

