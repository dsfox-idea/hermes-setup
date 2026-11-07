# Event-backed activity status

Use for this user's custom `activity` indicator. Requires the owner's TUI patch (`hermes-setup`); stock Hermes `INDICATOR_STYLES` has no `activity`. Preserve the standing appearance preferences in SKILL.md; keep legacy styles selectable.

The activity text, rectangle and phase clock use `statusGood` below 10 minutes, `statusWarn` from 10 minutes up to one hour, and `statusCritical` starting at one hour. Measure the current observed phase, not the entire turn; a new phase returns to green. Animate one full-block character inside the unchanged eight-cell track. Verify both threshold boundaries and phase reset in the actual renderer with a controlled clock.

## Procedure

1. Trace the event handler, activity store, phase selector and status-width reservation before editing. Observe events only after session and execution-generation filtering. Treat decorative `thinking.delta` text as decoration, not reasoning evidence. Preserve the phase start across repeated tokens; reset it for a new request or actual phase change.
2. Give open user prompts priority over compaction, active tools and model phases. Use the active-tool collection for parallel counts; do not expose raw arguments. When no specific event exists, show model waiting rather than inferred queueing, prefill or internal reasoning.
3. Test the real renderer as well as pure transitions. Through `terminal`, run from `ui-tui`:
   ```sh
   npm test -- src/__tests__/activityStatus.test.ts src/__tests__/activityTicker.test.tsx src/__tests__/appChromeBlockedTimers.test.tsx src/__tests__/appChromeStatusRule.test.tsx src/__tests__/busyStatusColor.test.tsx src/__tests__/statusBarTicker.test.ts src/__tests__/useConfigSync.test.ts
   npm test -- src/__tests__/createGatewayEventHandler.test.ts -t 'tracks real activity'
   npm run typecheck
   npm run build
   ```
   Cover hidden reasoning, foreign/stale events, repeated tokens, parallel tools, compaction, prompts, narrow columns and timer suspension under covering overlays. Keep animation cadence independent from phase transitions.
4. Run the full suite and compare failing test identities against an isolated checkout with only the previously published source patch. Materialize the baseline's dependencies and matching renderer build before interpreting failures; shared dependency symlinks can resolve modules against the wrong checkout. Distinguish collection/setup failures from reproduced behavioral failures. Rerun timing-sensitive cases in isolation and report them separately; do not repair unrelated failures in an appearance change.
5. Save the style through `terminal` with `hermes config set display.tui_status_indicator activity`. Verify frontend adoption separately from backend command validation: a frontend reload does not reload enum constants in a long-running gateway. Test newly added validation in a fresh runtime; do not restart the gateway merely to repaint.
6. For a frontend-only reload, test `process.execve` using the exact running Node executable. Parse the active-session hint as JSON and inspect `session_id`. Guard the exact PID, entrypoint and session, use an exclusive one-shot marker, and preserve the session through `HERMES_TUI_RESUME`.
7. Verify the live status with a temporary zero-height widget. Select the status node by its text shape and expected duration color; matching pixel text alone can capture a transcript code example. Observe changing single-cell frames and increasing phase time, confirm the same session, the correct duration color and no dim styling. Record only status text/style and process/session identity locally.
8. Remove temporary widgets and verify that sampling stops. Keep diagnostics private. Follow the setup publication workflow, checking shared staging ownership before transferring artifacts. Report live activation and remote publication as separate outcomes; an isolated snapshot check does not certify excluded profile drift.
