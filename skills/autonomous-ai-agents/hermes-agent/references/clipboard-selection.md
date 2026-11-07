# Mouse selection and clipboard feedback

## Scope and implementation

- For local macOS TUI copy-on-select, follow both selection paths: the transcript uses Ink selection notifications, while the composer uses `TextInput` mouse capture. A passing test for one path does not prove the other.
- Observe the transition from dragging to released. Later selection notifications and drag movements must not start another copy or restart its confirmation timer.
- Reuse `writeClipboardText` through the shared `ClipboardFeedback` controller. Serialize writes, skip empty selections, and show success only after the native writer returns true. Failed or rejected writes must not poison later copies.
- Keep feedback in the existing status row: reserve the right label, use bold `statusGood`, and restart the two-second expiry after each successful copy. Test narrow and normal widths.
- The optional skin branding key `copy_notice` overrides only this label. Preserve the configured interface language when a user requests a specific label. Without a skin override, use the normal localized `status.copied` value.
- Preserve the existing SSH OSC copy route without presenting an unverified remote clipboard receipt as native success. Terminal-owned selection that bypasses application mouse reporting is outside this route.
- When extending Ink hooks, update the implementation and the app's ambient `src/types/hermes-ink.d.ts`; rebuild Ink before validating its consumers.

## Live acceptance

1. Guard the target frontend PID, session, bundle digest and unsent composer draft before a targeted reload. Do not restart a shared gateway merely to load frontend code.
2. Keep the canonical probe source in private scratch storage and install a small temporary widget loader. Prefer an isolated TUI for layout-changing fixtures; do not add test rails to the user's active conversation. Register widget definitions synchronously inside `register(sdk)`: definitions created after an `await` can lose source ownership. Deleting the loader or failing to find a matching React component does not establish cleanup: explicitly remove only owned IDs from the ambient state, read that state back, verify both rail widths and the transcript's computed position/width, then request a full repaint. Distinguish verified renderer state from a verified physical-window capture.
3. Place a synthetic selectable sample away from viewport scroll edges and check its actual screen coordinates and `noSelect` mask. A stale fixture or auto-scroll boundary can invalidate a pointer probe.
4. Feed real SGR press, drag and release records through the running terminal input parser. Assert that the system clipboard is unchanged before release and equals the known fixture afterward. Repeat for the composer; its endpoint coordinates differ from inclusive transcript selection.
5. Inspect the actual rendered confirmation label, right alignment, success color and expiry. A store value or a compiled translation key alone does not prove the visible language or paint.
6. Preserve every original pasteboard item and format in memory. Restore only while the pasteboard still belongs to the probe, then compare original format bytes on readback. Never print, persist or publish the user's clipboard contents, transcript or draft.
7. Remove only owned fixtures and restore only the probe's own draft. Publish curated code and a content-free acceptance receipt, not live trace files.

## Publication

Reconstruct the generic delta on the clean publication source, test that source independently, and snapshot the skin, patch, pin and skill reference. Apply the repository's history/privacy and secret gates, then verify the remote revision and exact artifact bytes. A verified live feature and a verified publication are separate completion checks.
