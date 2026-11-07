# Backlog

- [ ] Windows: `test_local_publication_guard` runs the bash hook directly
  (`subprocess.run([hook, ...])`), which fails with WinError 193; and
  `test_snapshot_configuration.test_optional_image_skill_and_references_are_included`
  fails on Windows. Both fail on the unchanged tree too (checked 2026-11-07).

Setup review: 2026-11-03 against the installed stable release v0.22.5.
Dependency observations below remain dated 2026-10-30; they were not rerun for
the separate local-model environment.

- [x] Authenticate the ChatGPT subscription and select `gpt-6.1-sol`.
  Live model discovery, a real response, and terminal execution passed.
  Default reasoning is now high; effective runtime configuration verified.
- [x] Install the selected Heretic model as an additional local route.
  Pinned MLX weights, a separate environment and loopback server are installed;
  code, shell, Russian reasoning, structured tool calling and speed were checked.
  The cloud default and Honcho stack remain unchanged.
- [ ] Recheck upstream dependency fixes before updating this installation.
  `hermes doctor` reports one high vulnerability in the root runtime tree,
  one high in the web workspace, and one high plus one moderate in the TUI
  workspace. These counts can overlap across trees. The local npm reports
  identify `zod` (GHSA-mrhx-c7xc-m3w5) and `undici` (multiple advisories),
  with `jsdom` affected transitively. Dependencies are installed from upstream
  lockfiles; no local dependency changes have been made.
- [ ] Recheck the upstream stale-channel diagnostic. In v0.22.5,
  `hermes_cli/update_channel.py:379` checks for `installs/<id>/install.json`,
  while this installation's PM writes `facts.json`. The current source tree
  has no production writer of `install.json`. The source path and installation
  ID match, and `hermes --version` confirms the stable channel. Keep the valid
  channel record; no fabricated receipt or local source patch has been added.
- [ ] Recheck the upstream configuration-key warning: `hermes config set
  agent.reasoning_effort medium` warns that the key is unrecognized, although
  `hermes_constants.resolve_reasoning_config` reads it and resolves to enabled
  medium reasoning. Keep the working setting; no source patch has been added.
  The same notice occurs for `model_aliases.qwen36-35b-heretic`, although the
  native startup resolver loads the correct local route without cloud credentials.
- [ ] Align canonical CLI option validation with `hermes chat --help`.
  The help advertises `--run-budget`, but the gateway-backed CLI rejects it
  before inference as unsupported. Omit it for the local smoke test; do not
  change the main profile's run policy just to work around the warning.
- [ ] Investigate malformed `tui-theme-boot.json` with concurrent TUI frontends.
  The live profile cache fails JSON parsing with `Extra data`. The writer uses
  the shared temporary name `tui-theme-boot.json.tmp`; verify concurrent writes
  in isolation and use process-unique staging if the race is confirmed.
- [ ] Preserve blank rows inside fenced code blocks in the TUI Markdown renderer.
  Empty source lines currently render as empty `Text` elements with zero height
  in both layout densities. Keep this separate from service-spacing changes.
- [ ] Stabilize the daemon-exit timing test in `execFileNoThrow.test.ts`.
  Its unchanged 500 ms wall-clock assertion fails in the full TUI suite but
  passes in isolation. Investigate scheduling/process-startup interference;
  do not hide the issue by increasing the timeout in an appearance change.
- [ ] Investigate the six baseline TUI failures reproduced during activity-status verification.
  The same failures occur in an isolated checkout with only the previously
  published TUI patch: canonical slash usage totals, canonical usage totals,
  two cold-pending recovery cases, paired-palette selection, and queued
  submission settlement. The usage tests also report missing `ruamel` in
  their Python subprocess. Keep these separate from activity rendering.
  On 2026-11-06, the current full TUI suite passed with live session environment
  variables removed; do not assume those older failures remain source defects.
- [ ] Isolate TUI tests from inherited live-session environment variables.
  Tests can overwrite `HERMES_TUI_ACTIVE_SESSION_FILE` with fixture IDs and
  `HERMES_TUI_RESUME` changes cold-recovery expectations. The notification checks
  run with both variables unset; the live marker was restored from actual UI state.
  Harden the upstream test harness separately, without changing production resume behavior.
