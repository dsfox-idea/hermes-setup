# A2A peers across machines (Tailscale / LAN)

Use this when the user wants this Hermes to talk to another Hermes (or any A2A agent) on a different machine. Docs: `/user-guide/messaging/a2a` (full text in `llms-full.txt`, section "A2A (Agent-to-Agent)").

## Procedure

1. **Find the peers.** Run `tailscale status`. On macOS the CLI may only exist at `/Applications/Tailscale.app/Contents/MacOS/Tailscale`. Note this host's own tailnet IP too.
2. **Probe each peer.** Run `curl -m 4 http://<ip>:9900/.well-known/agent-card.json`. No answer while `tailscale ping` works means the peer's A2A server is still bound to localhost or its firewall blocks 9900. That gets fixed on the peer, not here.
3. **Ask which peer is the main/hub agent and how it names hosts.** The hub usually hands out names and tokens, e.g. `hub` for the hub and `mac1`/`mac2` for the others. Follow its scheme.
4. **Enable the platform and the client toolset.**
   ```bash
   hermes config set gateway.platforms.a2a.enabled true   # saved as platforms.a2a.enabled (that block outranks gateway.platforms)
   hermes tools enable a2a --platform cli
   ```
   The `a2a_*` tools only show up in a NEW session, because the toolset is frozen per session.
5. **Register the peer in config, with the token as an env ref.**
   ```bash
   hermes config set a2a_agents.<peer>.url http://<peer-ip>:9900
   hermes config set a2a_agents.<peer>.auth.type bearer
   hermes config set a2a_agents.<peer>.auth.token '${env:A2A_<PEER>_TOKEN}'
   hermes config set a2a_agents.<peer>.timeout 300
   ```
   You will see the warning "`a2a_agents` is not a recognized config key". Ignore it, because the A2A plugin (`plugins/platforms/a2a/tools.py`) reads that key. The "`${env:…}` not set" notices go away once the variable is in `.env`.
6. **Write the `.env` block for THIS host.** It holds no secrets you type yourself.
   ```
   A2A_AGENT_NAME=<this host's name>
   A2A_HOST=<this host's tailnet IP>
   A2A_PORT=9900
   A2A_TRUSTED_PEERS=<peer>
   A2A_PEER_TOKENS="<peer>:<token the peer presents to us>"
   A2A_<PEER>_TOKEN=<token we present to the peer>
   ```
   The user pastes the token values. Never ask for them in chat.
7. **Start the gateway.** Use `hermes gateway install`, which creates a launchd/systemd service. Check `hermes gateway status`, then confirm the bind with `lsof -nP -iTCP:9900 -sTCP:LISTEN`. It should show the tailnet IP, not 127.0.0.1.
8. **Verify in this order.** Each step isolates one layer.
   - Our own card: `curl http://<own-ip>:9900/.well-known/agent-card.json` should show the right `name`.
   - Inbound self-test: send `SendMessage` to our own IP using the token from `A2A_PEER_TOKENS`. The task should end `TASK_STATE_COMPLETED`. With a wrong token you should get HTTP 401.
   - Outbound: send `SendMessage` to the peer with `A2A_<PEER>_TOKEN`.
   Load tokens from `.env` into a shell variable inside the command so they never show up in the output.

## Pushing the same change to every machine in the fleet

Use this for things like installing a skill on every host.

1. Do it locally first.
2. Send the full artifact to the hub in one `SendMessage`. Give the exact `SKILL.md` text plus the tool to use (`skill_manage create`), and ask the hub to forward it to the peers this host has no token for. Tell those peers not to forward it any further. Ask for a one-line reply per host with the install path.
3. **Verify the install yourself.** A peer's "installed" is only its own report. Ask each host for the SHA-256 of the file and compare. Windows files get CRLF line endings, so the raw hash will differ. Ask for a hash of the bytes with the BOM stripped and `\r\n` replaced by `\n` before you call it a mismatch.
4. Use `urllib` in a `python3 -I` heredoc for the request, with the token read from `.env` inside the script. Set `timeout_s`/`timeout` close to 600 because the peer runs a whole agent turn.

## Serving a peer's task delivered by a2a-relay mail (`session_reply`)

A relayed task names an id (`mail-…`) and usually a fixed command list. The procedure:

1. Run the commands exactly as given, each as its own terminal call. Honour stop conditions, e.g. "stop if `git status --short` prints anything".
2. If a step comes back `BLOCKED: … timed out without user response`, don't retry or rephrase it. Run the remaining independent steps, then report per step: what ran and what was blocked. Give the shape the blocked commands share (e.g. all end in `| cut`) only as a hypothesis.
3. Send the result with ONE `session_reply(id=…)`: the outputs verbatim, cut to size, plus anything you saw that answers an open question of the sender (e.g. "the old chats now show as open sessions").
4. Then write a short report to the owner, in the owner's language, in this chat: what changed, what was verified, what is pending.

Rules for the content of such tasks:
- **Gated writes in a task NOT marked preapproved** (`hermes config set …`, writes under `~/.hermes`) prompt in the owner's chat every time and time out if he is away. Say in the chat, before the call, that it will ask, so he can answer. A task whose header says the owner already approved it on the sender's machine runs the same commands with no prompt. So when a gated step times out twice, ask the sender to resend it as an owner-approved batch instead of resending it bare.
- **A later owner-approved batch that says it replaces queued tasks wins:** run only the batch and skip the replaced ones.
- **The pinned commit is not what `pull` gave you:** check `git merge-base --is-ancestor <pinned> HEAD` and `git diff --stat <pinned> HEAD`, compare against HEAD, and report both commits. When the diff between them is empty or only a mode change, a correction that names the other commit does not need a re-run: reply that the earlier result stands, and say why.
- **A checksum in the task that is one character off** (truncated in copying) matches if the real 64-char hash starts with all of it. Proceed, and point out the length in the reply.
- **"Replace my copy only if it has nothing the merged copy lacks"** (skills, configs): for every file that differs or exists only locally, count `diff -u "$R/f" "$D/f" | rg -c '^\+[^+]'` in one loop. Report the counts per file plus a short summary of the real local-only sections. Put the full dump in a scratch file and give its path; a 13 KB paste does not fit a reply. Make no backup and do not replace when any count is non-zero.
- **A key the warning calls unrecognised** (`… is not a recognized config key — saved anyway`) is expected when the task says so: an overlay or plugin reads it. Report the warning verbatim and don't switch to the suggested key.

**Gateway restart for a plugin update** (via the a2a-relay `gateway_restart` tool):
- First call `sessions_list machine=<self>`. Any chat other than this one that is `working` means no restart; name that chat in the reply.
- Send `session_reply` BEFORE `gateway_restart`. The turn ends with the restart, and a reply sent after it may be lost.
- Call `gateway_restart` without `force`, then end the turn.
- Plugin code on disk (`git pull`) does nothing until the restart. A behaviour the update promises (e.g. fewer approval prompts) is only testable afterwards. Say so instead of reporting the old behaviour as a bug.

**After the "gateway restarted" notice**, check in one call:
- `grep '^version' ~/.hermes/plugins/a2a-relay/plugin.yaml`;
- `lsof -nP -iTCP -sTCP:LISTEN | grep -E ':990[01]'` (A2A on 9900 plus the relay's session service on 9901, both on the tailnet IP and owned by the new pid);
- `curl http://<tailnet-ip>:9900/.well-known/agent.json` should give 200. A curl to 127.0.0.1 fails by design, because the server binds the tailnet IP;
- new lines in `errors.log`, ignoring the standing wake-word / unknown-toolset warnings.

**Counting past approval timeouts in state.db:** a `content LIKE '%without user response%'` query over `messages` also matches tool outputs that merely echo the phrase. That includes the output of an earlier query of the same task, once it is persisted. Mark those rows as false hits rather than counting them.

## Tailscale next to another full-tunnel VPN (WireGuard-based or similar)

- The other VPN takes `0/1` + `128.0/1` and its own DNS. Tailscale only needs `100.64/10`, and that more specific route wins for peers.
- The breakage comes from DNS: with MagicDNS on (`CorpDNS: true`), the two VPNs fight over the system resolver after a reboot.
- Bring Tailscale up with automatic rollback:
  1. Check the baseline (an HTTPS fetch plus a DNS lookup).
  2. Run `tailscale set --accept-dns=false`, then `tailscale up --accept-dns=false --timeout=30s`.
  3. Re-check up to 3 times. If the checks fail, run `tailscale down`.
  4. Verify with `route -n get <peer-ip>` (it should show the Tailscale utun), `tailscale ping`, and the peer card returning 200.
- Afterwards MagicDNS names don't resolve, so address peers by IP.
- To diagnose VPN slowness, compare the tunnel with the raw uplink:
  - `curl --interface en0` vs the default route against `speed.cloudflare.com/__down?bytes=25000000`;
  - `ping` loss through the tunnel vs `ping -b en0`;
  - DF pings (`ping -D -s N`) to rule out MTU.
  Loss inside the tunnel while en0 shows none points at the tunnel protocol or server, not at Tailscale.

## Pitfalls

- **Inbound A2A tasks run in a hidden gateway session.** The peer's user doesn't see your request in their chat unless a relay plugin forwards it. Before sending anything that makes a peer do work, show the request to your user, even if it only reads.
- **Serving an inbound A2A request: approval-gated commands run LAST.** Commands that trigger a dangerous-command approval (symlinks into `~/.hermes`, `cp` over config, `hermes plugins enable`, `hermes config set` …) prompt nobody in the hidden gateway session. They wait `approvals.timeout` (300 s by default) and are then denied as BLOCKED, and the peer's own A2A timeout keeps running meanwhile. So run every read-only or ungated step first (clone, tests, `config get`, probes), then the gated one, and split chained `&&` commands so the safe parts don't get stuck behind a gated part. After a BLOCKED result, don't retry or rephrase it, and don't make other config changes in that session. Reply with the exact command for the user to run, and say what was and wasn't changed on disk. The a2a-relay plugin (github.com/dsfox-idea/a2a-relay) forwards these prompts to the user's TUI chat once it is installed.
- **`TASK_STATE_FAILED` / `[agent did not reply in time]`** means the peer's agent turn ran past its `A2A_REPLY_TIMEOUT`. Keep remote asks small and concrete, or raise the timeout on the peer. Don't resend the same big request.

- **Tokens go in opposite directions, so map them explicitly.** The hub's `A2A_PEER_TOKENS` entry `<node>:<X>` is what *<node> presents to the hub*, so it becomes our `A2A_<HUB>_TOKEN`. The hub's `A2A_PEER_<NODE>_TOKEN` is what *the hub presents to <node>*, so it goes into our `A2A_PEER_TOKENS="<hub>:…"`. If you swap them, you get 401s in both directions.
- **Re-check `.env` after the user edits it.** Users often paste the hub's whole A2A block, including its `A2A_AGENT_NAME`, `A2A_HOST`, `A2A_TRUSTED_PEERS` and other hosts' tokens. Print only the key names and the non-secret values to check. If the block came from the hub, rewrite it for this host: derive the two tokens with a small `python3 -I` script, delete tokens that belong to other hosts, and `chmod 600` the file.
- **A non-localhost bind needs a token.** Without `A2A_PEER_TOKENS`/`A2A_BEARER_TOKEN`, `A2A_HOST` is ignored and the server binds to 127.0.0.1.
- **HTTP 200 with `TASK_STATE_FAILED` / `[agent processing failed]` means network and auth passed.** The remote agent failed while running the task. Point the user at the PEER's gateway logs (`logs/gateway.log`, `errors.log` under its Hermes home; on Windows that is `%LOCALAPPDATA%\hermes`). Don't keep changing local config.
- **Back up before touching secrets.** Copy `.env` and `config.yaml` to the scratch directory before editing them. Delete any `.env` backup that holds tokens once you're done.
