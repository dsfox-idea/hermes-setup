# TUI chronology and event timestamps

## Behavior

Settled questions and replies stay between the actions that preceded and followed
them. Mid-turn prompt answers are recorded in the ordered live segments, then
archived with that turn. Cancellation, timeout, completion and failure preserve
settled human input. Restored history flushes pending tool rows before a new
user/system/display event and retains an unfinished tool tail.

Event rows show local `HH:MM:SS.mmm` on the first content line. The timestamp is
captured at the event boundary and remains stable through redraws. Separate tool
calls retain separate times when grouped. Missing historical times use
`--:--:--.---`, not the replay clock. Timestamp text uses the same gray as the
main status-bar text; question and choice text retain their own palette.

Restored in-flight text and replayed prompts without an original time retain an
explicit unavailable-time marker. Repeated approval and clarification deliveries
preserve the first observed time, including a previously unknown time. Regression
tests first reproduced these replay/redelivery defects, then passed after their
correction in both canonical-event and legacy-request paths.

The existing public timing/cost summary, waiting-time accounting, bright-green
statistics row, Shift+Enter behavior and collapsed service notifications remain
in place. An integration fixture verifies questions and actions before the final
reply, with exactly one timing summary afterward.

## Verification

The candidate was reconstructed from the public patch on the pinned upstream
revision. Its full-suite result was compared against a separately reconstructed
copy of the preceding public patch, using identical test commands and environment
isolation. No live session or profile was restarted or replaced.

| Check | Result |
| --- | --- |
| Focused chronology, timestamps and preserved-feature tests | 88 passed |
| Full candidate TUI suite | 1,992 passed, 3 failed, 30 skipped |
| Full preceding public TUI suite | 1,947 passed, 3 failed, 30 skipped |
| Newly failing full-suite tests | 0; the failure identities match |
| TypeScript typecheck | Passed |
| Changed-source ESLint errors | 5 existing in both versions; 0 new |
| Installer, exporter and publication-guard tests | 18 passed |
| Production bundle and isolated installer overlay build | Passed |
| Public-only snapshot and inventory check | 70 artifacts checked without drift |

The overlay build used the real `TuiOverlay.build` path with disposable state:
patch application, compilation, JavaScript validation, revision/checksum metadata
and temporary-source cleanup. Profile activation is deliberately separate from
this build check.

## Deferred baseline work

- [ ] Investigate the two `coldPendingRenderer.test.tsx` failures where the
  restored queue is empty instead of containing its durable pending records.
- [ ] Investigate the `submissionDestinationRenderer.test.tsx` failure where
  the queued input remains after the matching receipt.
- [ ] Resolve the five pre-existing import/JSX ordering errors in
  `createGatewayEventHandler.ts`, `useMainApp.ts`, `appLayout.tsx` and
  `messageLine.tsx` without mixing that cleanup into the chronology correction.

These failures were reproduced before the port. The full suite is not reported
as green, and unrelated source was left unchanged.
