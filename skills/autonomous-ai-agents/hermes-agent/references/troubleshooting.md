# Troubleshooting

### Voice not working
1. Check `stt.enabled: true` in config.yaml
2. Verify provider: `python -c "import pm; pm.sync_venv(['stt-whisper'], explicit=True)"` or set API key
3. In gateway: `/restart`. In CLI: exit and relaunch.

### Tool not available
1. `hermes tools` — check if toolset is enabled for your platform
2. Some tools need env vars (check `.env`)
3. `/reset` after enabling tools

### Model/provider issues
1. `hermes doctor` — check config and dependencies
2. `hermes auth` — re-authenticate OAuth providers (or `hermes auth add <provider>`)
3. Check `.env` has the right API key
4. **Copilot 403**: `gh auth login` tokens do NOT work for Copilot API. You must use the Copilot-specific OAuth device code flow via `hermes model` → GitHub Copilot.

### Changes not taking effect
- **Tools/skills:** `/reset` starts a new session with updated toolset
- **Config changes:** In gateway: `/restart`. In CLI: exit and relaunch.
- **Code changes:** Restart the CLI or gateway process
- **Newly enabled user plugin (`hermes plugins enable <name>`):** the running gateway re-wires it at once (log: `Re-wired plugin handlers`), but an already-open TUI/CLI chat process does NOT load it — its hooks and `/commands` appear only in a new TUI session. Confirm which process loaded it by grepping the plugin's own register log line in `~/.hermes/logs/agent.log` vs `gateway.log` before telling the user it is live in their chat.
- **Plugin injecting into chats:** `ctx.inject_message(..., session_key=...)` is refused (warning `gateway injection denied`) until `hermes config set plugins.entries.<plugin_id>.allow_gateway_injection true`.

### web_extract shows a stale page (result caching)
`web_search`/`web_extract` cache results for 20 minutes (PR #94618) — a
repeat fetch of the same URL within the TTL is served from cache, which
can look like "my website changes aren't showing up."

Automatic carveouts (always fetched live, never cached):
- localhost / 127.0.0.1 / `*.local` / `*.localhost` / single-label LAN
  hostnames / private + link-local IP ranges (dev servers, hot-reload
  builds, chat-GUI artifact previews)
- URLs matched by `security.website_blocklist`
- failed responses and keyless-rescue-served responses

Developing a site tested over the PUBLIC internet (Vercel/Netlify
preview, ngrok/cloudflared tunnel, staging domain)? Public DNS isn't
auto-carved-out — list the host in config.yaml:

```yaml
web:
  cache_exempt_hosts:      # always fetched live; effective immediately
    - mysite.vercel.app
    - "*.ngrok-free.app"
    - mysite.dev           # suffix match: also covers preview.mysite.dev
```

Blunt instruments: `web.cache_ttl_minutes: 1` (min) or
`web.cache_enabled: false` disables both caches entirely.

### "N sessions" in the TUI status bar
The count is `liveSessionCount`: the TUI polls the gateway RPC
`session.active_list` every 1.5 s (`ui-tui/src/app/useMainApp.ts`), which
returns the live session records in the gateway PROCESS memory
(`tui_gateway/methods_session.py`). So it counts:
- every TUI/desktop/local session open in this gateway, for EVERY profile it
  serves (`served_profiles` in `$HERMES_HOME/gateway_state.json`);
- detached sessions (a TUI that disconnected/reconnected) until the grace
  reaper finalizes them;
- only this machine (peers' chats are not in it; `sessions_list` lists those).
It is not a DB count: `state.db` rows with `ended_at IS NULL` and
`runtime/active_sessions.json` will not match it. The list with titles and
status is `/sessions` in the TUI. A gateway restart log line
"Reclaimed N orphaned active-session lease(s)" means reconnect leftovers.

To see what ANOTHER chat on this machine is doing: `sessions_list`, then
read its last messages from `$HERMES_HOME/state.db` (`select
role,content,timestamp from messages where session_id=? order by id desc`)
from a scratch python file.

### write_file refuses "stale" / "partial view"
`write_file` overwrites an existing file only when the LAST `read_file` of it in this task was a full read. Any read that passed `offset`/`limit` counts as partial even if it returned the whole file (`offset=1, limit=2000` included), and a partial read issued in the same parallel batch as the full read can land last. Rule: before a wholesale rewrite, make one sequential `read_file(path)` with no offset/limit and nothing else touching that file, then write; for small changes use `patch`. If the file is git-tracked and the rewrite is total, deleting it in the terminal (`git status` first) and creating it fresh with `write_file` also works. Never retry the same refused `write_file` (the loop guard fires after 3).

### Skills not showing
1. `hermes skills list` — verify installed
2. `hermes skills config` — check platform enablement
3. Load explicitly: `hermes -s name` (or the skill's own `/<name>` slash command)

### Gateway issues
Check logs first:
```bash
grep -i "failed to send\|error" ~/.hermes/logs/gateway.log | tail -20
```

Common gateway problems:
- **Gateway dies on SSH logout**: Enable linger: `sudo loginctl enable-linger $USER`
- **Gateway dies on WSL2 close**: WSL2 requires `systemd=true` in `/etc/wsl.conf` for systemd services to work. Without it, gateway falls back to `nohup` (dies when session closes).
- **Gateway crash loop**: Reset the failed state: `systemctl --user reset-failed hermes-gateway`
- **"Blocked: launchctl submit/bootstrap is restricted inside a supervised gateway"** (macOS, agent running under the launchd gateway): this is intended. Write and lint the plist yourself, then give the user the exact `launchctl bootstrap gui/$(id -u) <plist>` + `launchctl print ...` commands to run in a normal Terminal, and mark them unverified. Never switch verbs or wrap the call to get past the guard. It matches command text, so a heredoc that only contains the phrase is blocked too: write such text with write_file. Recipe: dev-workflow `references/scheduled-git-jobs-macos.md`.


### `hermes update` fails to fetch (timeout, "remove the file manually")
Diagnose before retrying: every retry starts the pack download over, because git fetch does not resume.
1. **Leftover locks or garbage from a killed update.** Run `ls ~/.hermes/hermes-agent/.git/*.lock .git/objects/pack/tmp_pack_*`. The warning "Could not fetch the missing commit history (... remove the file manually ...)" means a stale `.git/shallow.lock`. First confirm no git process is using that repo (`lsof`, `pgrep -fl 'git.*fetch'`). A `hermes update` the user is running in his terminal also matches; wait for it to exit. Then `rm .git/shallow.lock .git/objects/pack/tmp_pack_*`. Leave `hermes-update.lock` and `hermes-pack-tidy.lock` alone: Hermes manages them itself.
2. **Why it times out.** Installer checkouts are depth-1 and may sit on a release tag far behind `main` (check with `cat .git/shallow` and `git log -1`). The update runs two fetches:
   - First it unshallows the whole commit graph: `git fetch --unshallow --filter=blob:none --no-tags origin 'refs/tags/v*:refs/tags/v*' main`. This step has a 900 s cap, and its failure is non-fatal.
   - Then it runs the main fetch with a hard 300 s cap (`NETWORK_GIT_TIMEOUT_SECONDS` in `hermes_cli/update_cmd.py`, with no override).
   The blobless commit graph of `main` is ~330k objects / ~110 MB; at 100-250 KB/s with GitHub resetting long transfers (`curl 92 HTTP/2 stream ... CANCEL`, `early EOF`, `invalid index-pack output`) neither cap is reachable, and the user's every retry fails the same way.
3. **Measure GitHub speed, not general speed.** "The browser works" and a fast Cloudflare test prove nothing, because GitHub can be slow while other hosts are fast. Compare `curl -sL -o /dev/null -w '%{speed_download}\n' --max-time 25 <a GitHub release asset URL>` with `https://speed.cloudflare.com/__down?bytes=25000000`. On macOS, add `--interface en0` to test bypassing a VPN without touching routes. Ping loss through a VPN tunnel is a weak signal on its own: do not send the user to reconnect the VPN on ICMP loss alone, because a GitHub-only slowdown survives a reconnect and even a VPN-off run. Tailscale without an exit node does not carry GitHub traffic (`tailscale debug prefs`: `ExitNodeID` empty, `RouteAll: false`).
4. **Workaround for a slow link:** run the same unshallow fetch yourself, with no time cap, in the background (`terminal(background=true, notify=true)`). Use `--progress`, write the output to a log, and wrap it in a retry loop that deletes `.git/shallow.lock` between attempts. The fetch only adds objects and tags; it does not touch the working tree or the gateway. Expect several attempts on a flaky link (each restarts from zero). When it finishes, check `git rev-parse --is-shallow-repository` is `false` and time a bounded `git fetch origin +refs/heads/main:refs/remotes/origin/main` (seconds = the update will pass). Then the user reruns `hermes update`, and its 300 s fetch only has to download a small remainder. Do not run `hermes update` from inside the agent: it restarts the gateway.

### "Is this TUI turn stuck?" / which process serves a session (read-only)
Work from logs and the process table; change nothing.

1. **Turn state from `~/.hermes/logs/agent.log`** (timestamps are host-local time; convert if the asker wants another zone):
   - start: `tui prompt accepted: ui_session=<ui> ... agent_session_id=<sid> kind=user|process_complete`
   - end: `[<sid>] agent.conversation_loop: Turn ended: reason=...` followed by `tui_gateway.server: tui turn finished ... status=complete duration=Ns`
   - `grep -h "<sid>" agent.log | grep -E "prompt accepted|Turn ended|tui turn finished" | tail` answers "did it end?". Background-review turns (`budget=N/16`, `interrupted_by_system(background_review_superseded)`) interleave with the user turn — don't mistake them for the user turn's end.
   - The last line *tagged* `[<sid>]` and the last line *mentioning* the id differ: untagged lines like `Cleaned up inactive environment for task: session:<sid>` come later. Report both when asked for "the last line".
   - A turn that logged `Turn ended` but the user sees as running is a display issue in that TUI window, not a hung agent.
2. **Who owns the session.** TUI windows either attach to the shared gateway or run their own backend:
   - Shared: `~/.hermes/logs/tui_gateway_crash.log` has `attached shared gateway ... url=ws://127.0.0.1:<port>/api/ws`. `lsof -nP -iTCP:<port> -sTCP:LISTEN` gives the gateway worker pid; `-sTCP:ESTABLISHED` lists the attached `node .../ui-tui/dist/entry.js` pids. Its `tui_gateway.server` lines land in the shared `agent.log`.
   - Standalone: `node entry.js` with a child `python3 -m tui_gateway.entry` (one pair per tty). These may log elsewhere — their session ids can be absent from `agent.log` and `state.db`.
   - Map provider subprocesses to sessions: `for c in $(pgrep -f "claude -p"); do echo $c $(ps -o ppid= -p $c) $(ps eww -o command= -p $c | grep -oE 'HERMES_SESSION_ID=[^ ]+'); done` — the parent pid is the backend serving that session. Sample a few times; the subprocess is per API call.
   - `hermes gateway status` (launchd) reports the supervisor pid (an `osascript` wrapper); the real worker is its grandchild (`gateway run --external-supervisor`). Verify the agent's own shell lineage with a ppid walk from `$$` if needed.
3. **Readable `ps`.** Hermes launchers embed a ~5 KB `python3 -I -c` script, so raw `ps ... | grep hermes` is ~70 KB. Use `ps -axo pid,ppid,lstart,etime,tty,command | grep -i hermes | grep -v grep | cut -c1-200 | sed -E 's/-I -c import os.*$/-I -c <launcher>/'`; if the asker wants it verbatim, give the full-output file path and say what was collapsed.
4. `sqlite3 -readonly ~/.hermes/state.db "select id,source,started_at from sessions where id in (...)"` confirms which ids the main home knows.

### Old chat won't resume on the shared gateway (`session.resume refused ... invalid_params`)
The TUI shows 'internal error' / invalid_params, and `errors.log` has `gateway.session_controls: session.resume refused for profile=<p>: invalid_params field=<f> detail=...`. New chats work. These are usually legacy rows (created by standalone TUI windows) being adopted on first resume.

1. **Path** (read it in the host's own checkout; it changes between commits): `gateway/session_controls.py` resume → `gateway/session_local_migration.py` `resolve_local_target` (a row with a `state_meta` policy/legacy binding goes to `restore_local_session`, otherwise `adopt_legacy_session`) → `legacy_launch_params(row)` → `build_policy` → `gateway/session_policy.py` `_apply_launch_overrides`, which refuses any `base_url` that is not http(s).
2. **Where `base_url` comes from in a legacy row:** `model_config.gateway_runtime`, else top-level `provider`/`base_url` in `model_config`, else `billing_provider` + the `billing_base_url` usage stamp. A provider served as a local process (`process://<provider>`) stamps a non-http URL. The profile config has no `base_url` for it, so `same_route` compares `process://...` with `''`, returns False and keeps the URL. Then the policy check refuses it. The usage-stamp heal (`_route_is_usage_stamp`) covers only `billing_provider='custom'`.
3. **Check before writing anything:**
   - Read the full `model_config` of the rows (`sqlite3 -readonly ~/.hermes/state.db "select id, model_config, quote(billing_base_url) from sessions where id in (...)"`). If you only see its first 200 chars, a `gateway_runtime` or `base_url` key further on can be missed.
   - List the bindings: `select key from state_meta where key like '%<id>'`.
   - Run the real code on the live rows without writing (see the probe recipe below). Run `legacy_launch_params` + `same_route` + `build_policy`, once with the stored row and once with the field you plan to change. Do not run a real resume as a test: adoption writes the session.
4. **Fix (owner approval and a backup first):** clear the stamp on legacy rows, `UPDATE sessions SET billing_base_url=NULL WHERE billing_base_url LIKE 'process://%'`. Resume then uses the profile's route. Rows that the gateway created itself (a2a, `local-*`) get the stamp again and are not affected.
   - Back up with `sqlite3 ~/.hermes/state.db ".backup <file>"`. Then verify it with `sqlite3 "file:<file>?immutable=1" "pragma quick_check"`. `-readonly` cannot open a WAL-mode copy that has no `-shm`.
5. **A refusal logged after the fix may still be older than the fix.** Compare the refusal's timestamp with the time the write ran: take the write's tool-call times from the session that ran it (`messages` table or `agent.log` `[<sid>] tool terminal completed`). Then check that no refusal was logged after the write. Only then go looking for another source of the bad value.
6. **A title clash on rename** ("title already in use") means an old session holds that title. Opening the old chat is cleaner than renaming the new one.

**Probe recipe: run Hermes internals read-only from a scratch script.** Bare `python3 -I script.py` fails on missing deps (e.g. `ruamel`), because the deps come from `hermes_bootstrap`. Put this at the top of the script:
```python
import sys
sys.path.insert(0, '/Users/<user>/.hermes/hermes-agent')   # the checkout
sys._hermes_pin_default_home = True
import hermes_bootstrap  # noqa: F401
```
Run it with the launcher's interpreter (the path after `exec` in `$(which hermes)`): `env -u PYTHONPATH -u PYTHONHOME HERMES_HOME=$HOME/.hermes <that python3> -I script.py`. Open state.db as `sqlite3.connect('file:...state.db?mode=ro', uri=True)`. For a module that already exists, `hermes --run-module <module>` is simpler.

### Platform-specific issues
- **Discord bot silent**: Must enable **Message Content Intent** in Bot → Privileged Gateway Intents.
- **Slack bot only works in DMs**: Must subscribe to `message.channels` event. Without it, the bot ignores public channels.
- **Windows-specific issues** (`Alt+Enter` newline, WinError 10106, UTF-8 BOM config, line endings): see `references/windows-quirks.md`.

### English state summaries after internal completion notices

- Inspect the actual provider output, persisted role, `display_kind`, `_compressed_summary` and preceding turn before blaming translation, locale settings, memory loss or compaction. A normal assistant `output_text` is not a tagged compaction artifact merely because it reads like a handoff summary.
- An already-handled process notification may finish silently using the existing `NO_REPLY` marker when no pending user outcome requires further work. Verify `gateway.response_filters.silence_allowed` for its machinery kind. A blank/analysis-only response is deliberately NOT intentional silence: Codex can classify it incomplete and `continue_codex_incomplete` can add a forced-final nudge. Never substitute a long technical state inventory for the notification outcome.
- Preserve the user's conversational language in user-visible status and final replies. English source code, documentation and machine control text do not authorize an English chat reply. Do not claim a language rule was missing from historical provider input merely because `sessions.system_prompt` is empty; that column is not an audit of every request.
- Distinguish reproducing a retry path from proving the model's internal language-selection cause. Keep diagnostic transcripts outside publication. Use the existing silence protocol before inventing a new response-filtering mechanism, and do not alter cached prompts, reset sessions or disable all notifications to mask the issue.

### Auxiliary models not working
If `auxiliary` tasks (vision, compression, session_search) fail silently, the `auto` provider can't find a backend. Either set `OPENROUTER_API_KEY` or `GOOGLE_API_KEY`, or explicitly configure each auxiliary task's provider:
```bash
hermes config set auxiliary.vision.provider <your_provider>
hermes config set auxiliary.vision.model <model_name>
```

### "Reset permissions" / auto-approving everything
See `references/security-privacy.md` — wipe the "Always allow" stores, don't touch yolo mode.

