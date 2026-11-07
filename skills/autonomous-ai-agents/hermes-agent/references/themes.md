# Themes / Skins — Author a Hermes Color Theme

Author a Hermes **skin** — one YAML file that themes the CLI, the TUI, and the
desktop GUI at once. The skin engine (`hermes_cli/skin_engine.py`) resolves the
active skin and the gateway pushes it to every surface, so a file dropped in
`~/.hermes/skins/` is the theme analogue of a plugin: no code, all surfaces. This
skill covers writing a good skin and activating it; it does not build GUI theme
editors or ship built-in presets.

## When to Use

- The user asks for a custom look ("make me a synthwave theme", "dark forest
  vibes", "match my brand colors") for Hermes itself.
- The user wants the CLI/TUI/desktop to share one coordinated palette.
- The user wants to iterate live ("that coral is too loud, make it teal") — edit
  the active skin's YAML and every surface repaints as your tool finishes.

## Prerequisites

- Write access to the Hermes home dir — `~/.hermes` by default, or `$HERMES_HOME`
  / the active profile's dir. Skins live in `<hermes-home>/skins/`.
- Native tools: `write_file` (create the YAML), `read_file` / `search_files`
  (inspect existing skins), `terminal` (activate via `hermes config set`).

## How to Run

1. Pick a lowercase, hyphen-safe `name` (e.g. `synthwave`).
2. Copy `templates/skin.yaml` and fill in the palette (keep every key — missing
   keys inherit the `default` skin).
3. `write_file` it to `<hermes-home>/skins/<name>.yaml`.
4. Activate it (see Procedure). Confirm the change landed.

## Quick Reference — element → key

Hex (`#rrggbb`). Theming is **semantic**: one key colors every element that plays
that role, so match the element to its key. To recolor a specific element, set the
key in its row (element-specific keys fall back to the shared one when unset).

| Visible element | Key to set | Falls back to |
|---|---|---|
| App background (whole TUI + GUI) | `background` | terminal default |
| **Tool-call marker** (`●`, tool spinner) | `ui_tool` | `ui_accent` |
| **Thinking / reasoning text** | `ui_thinking` | `banner_dim` |
| Accent — headings, links, chevrons, `Σ` | `ui_accent` / `banner_accent` | — |
| Heading / primary text | `banner_title` / `ui_primary` | — |
| Body / label text, user messages | `ui_text` / `banner_text`, `ui_label` | — |
| Muted / secondary, tree connectors | `banner_dim` | — |
| Borders, rules, gutters | `ui_border` / `banner_border` | — |
| Prompt symbol color | `prompt` | `banner_text` |
| Success / warn / error | `ui_ok` / `ui_warn` / `ui_error` | — |
| Status bar text + usage | `status_bar_text`, `status_bar_good/warn/bad/critical` | — |
| Diff added/removed line backgrounds (TUI) | `diff_added` / `diff_removed` | built-in |
| Diff added/removed text foregrounds (TUI) | `diff_added_word` / `diff_removed_word` | built-in |
| Code syntax (string/number/keyword/comment) | `syntax_string` / `syntax_number` / `syntax_keyword` / `syntax_comment` | accent/text/border/muted |
| Completion menu | `completion_menu_bg` / `completion_menu_current_bg` / `…_meta_bg` | — |

Note the sharing: `ui_accent` colors tool markers **and** headings/links/chevrons,
so to recolor *only* tool calls (the classic "change the gold `●`") set `ui_tool`.
`branding` (`agent_name`, `prompt_symbol`, `welcome`, `goodbye`, `help_header`),
`spinner`, and `tool_prefix` are optional flavor; full schema in
`hermes_cli/skin_engine.py`.

## Procedure

1. **Design the palette.** Choose a `background` first, then an `ui_accent` that
   clears WCAG AA against it (~4.5:1) so labels stay legible — the GUI enforces
   contrast but a low-contrast accent still looks washed out. Keep
   `ui_ok`/`ui_warn`/`ui_error` recognizably green/amber/red.
2. **Write the file** to `<hermes-home>/skins/<name>.yaml`. Every top-level
   `colors` key from the template should be present.
3. **Apply it yourself — never hand-edit `config.yaml`.** Run the safe writer via
   `terminal`:
   ```
   hermes config set display.skin <name>
   ```
   The gateway's skin watcher notices the change and **repaints every surface live
   within ~a second** — CLI, TUI, and desktop — and the skin appears in
   Appearance / `Cmd-K` / `/skin`. You apply it; do NOT tell the user to run
   `/skin` (they still can, but it's your job). The writer emits valid YAML — a
   hand-edit can corrupt the file and break the live gateway (including `/`).
4. **Confirm the new look landed** and tell the user how to revert: run
   `hermes config set display.skin default` (or they can `/skin default`).

## Fork an existing skin into a standalone file

- Resolve the source with `load_skin(source_name)` and preserve its complete resolved palette and other skin sections; change only `name`, `description`, and the requested overrides. The YAML field for `SkinConfig.custom_css` is `customCSS`.
- Preserve an absent `background` when the user wants the existing terminal canvas unchanged. Choosing a new background while forking changes more than the requested element.
- In the TUI renderer, `diff_added` and `diff_removed` are line backgrounds, while `diff_added_word` and `diff_removed_word` are text foregrounds. When darkening the backgrounds, verify the foreground/background contrast and adjust the text if necessary.
- Verify that loading the new name resolves the custom file, that untouched fields match the source, and that unrelated configuration survives activation. Distinguish these checks from observing a live repaint.

## Replace startup artwork without changing Hermes code

1. Identify the requested element: use `banner_hero` for the side illustration, `banner_logo` for the large wordmark, and `branding.agent_name` for compact/narrow text branding. Resolve the active skin file's symlink before editing so its backing setup repository is accounted for. Do not change chat text colors to recolor one illustration.
2. Preserve an accepted drawing exactly when the request changes only color or spacing. For a new block-letter wordmark, match the shipped ANSI Shadow font: a disposable `uv run --no-project --with pyfiglet` environment can generate text without installing dependencies into Hermes. Compare its `HERMES-AGENT` rows with `LOGO_ART` before choosing the font.
3. Store one complete Rich hex-color span per artwork row. Use YAML `|-` for no additional blank row; change it to `|` for exactly one empty rendered row below the drawing. The native parser splits a terminal newline into a final blank row, so do not add a dummy glyph, global margin, or renderer change for this spacing request. Preserve YAML anchors and unrelated values.
4. Load the edited skin through `hermes_cli.skin_engine.load_skin` and test the actual `caduceus`/`logo` and `parseRichMarkup` exports in `ui-tui/src/banner.ts`. On a Node version supporting native type stripping, `node --experimental-strip-types --input-type=module` can import this type-only-dependent module directly without installing test infrastructure. Assert unchanged graphic rows, requested row colors, the exact added blank row and a width within the layout budget; measure width instead of guessing it from a visual preview.
5. Verify the final terminal palette conversion with the shipped `richEightBitColorNumber` when ANSI-256 is required; pure red `#FF0000` maps to index 196. Apply through the canonical live-skin procedure in Verification, then compare `runtime.describe().skin.banner_hero` with the loaded YAML value and `<hermes-home>/tui-theme-boot.json`'s `theme.bannerHero` byte-for-byte. Use `bannerLogo` for wordmark checks. Distinguish configuration adoption and parser checks from observed screen pixels.

For Python verification and gateway RPCs, discover the managed runtime with `hermes --print-runtime-command`. Parse the returned argument array and preserve its bootstrap prefix when substituting a diagnostic for its final `runpy.run_module(...)`; do not guess a virtualenv path or copy a machine-specific launcher.

## User's dsfox-skin preferences

- Preserve the terminal's 256-color restriction; do not enable truecolor. For visual tuning, start from the unchanged slate baseline and adjust one color at a time by one available brightness level while keeping its hue family. Report the emitted ANSI-256 index, not just the requested RGB value, and show a small diff sample after changes.

- Keep added/removed line fills very dark and clearly green/red. Avoid rose or magenta in removed-line backgrounds. Use light-green text on additions and light-red text on removals; do not substitute neutral text when adjusting the backgrounds.
- Minimize distinct colors and new color tokens. Reuse existing semantic palette colors for diff text (success green and critical red) before introducing another shade. Use YAML anchors/aliases when the values should stay linked, preserve them during edits, and validate through Hermes's YAML/skin loader rather than a regex-only scalar parser.

## Working status visibility

Requires the owner's TUI patch (`hermes-setup`); stock Hermes has no `activity` indicator style. For the installed custom `activity` mode and its verification workflow, load `references/activity-status.md`. The FaceTicker notes below remain applicable to legacy styles.

- Match the active `FaceTicker` directly to `t.color.statusGood`, the same token `ctxBarColor` uses below 50% context. Do not feed it the current context-bar color, which becomes amber/red at higher occupancy, or change global muted/text colors. Keep the idle `statusColor` path and error/warning notices unchanged.
- Verify rendered status spans against a below-50% context-bar reference at low and high occupancy, including the ordinary rotating verb and compaction override. Assert no dim styling. A zero-height SDK probe can verify the running status node's `textStyles.color` and `dim` under the one-row status container; remove it after adoption.
- The unchanged `execFileNoThrow` daemon-exit test has a load-sensitive 500 ms assertion. If it alone fails the full suite, inspect the failure and run it in isolation, record the limitation in the project backlog, and do not alter its timeout while changing appearance.

## Choice-prompt appearance

Requires the owner's TUI patch (`patches/hermes-tui.patch` in `hermes-setup`); stock Hermes has no `clarify_*` skin keys.

- Scope choice-card overrides to `ClarifyPrompt`: `clarify_bg`, `clarify_text`, and `clarify_selected_bg` resolve into optional `Theme.clarify`. Build a local palette for the prompt so shared menu, approval and chat colors stay unchanged. Compare the scoped fields in theme equality for live redraws.
- The accepted dsfox-skin choice card uses background `#262626` (xterm gray 235), white `#ffffff`, and a dark-green selected row sharing the existing `diff_added` YAML anchor. Read the active skin before subsequent changes; do not assume stored preferences override current file values.
- Set an explicit Box background for the whole card and white ink for questions, inactive choices, input and hints. Reuse `chipRowProps` for the active row. Avoid SGR dim on content the user must read, and verify white/green contrast after actual ANSI-256 conversion, not only against the source RGB.
- Reuse the native `termio.Parser` in renderer tests to inspect per-span foreground/background/dim state. Interactive fixtures must implement `isTTY`, `setRawMode`, `ref`, `unref`, and readable-stream methods; copy a complete existing fixture instead of patching missing methods one at a time. Raw-mode fixture exceptions are not a valid red test for appearance.
- Show a real `clarify` prompt after the new frontend is loaded when the user asks for a preview. A temporary stdout probe can count only the requested panel/white/selection color codes without recording text; stop and remove it afterward. Treat a user-confirmed preview as appearance feedback, not a substitute for agent-run rendering tests.

## Tweak the active look (change one thing)

When the user wants to adjust the CURRENT look ("make the tool `●` cyan", "warmer
background"), use the one deterministic command — it edits the ACTIVE skin's ONE
key in place, so everything else (background included) is untouched:

```
hermes skin set <key> <hex>      # e.g. hermes skin set ui_tool "#00FFFF"
```

It edits the active skin's file (a built-in is forked into an editable copy that
keeps its full palette), the watcher repaints live, and nothing else moves. Check
anchor preservation before using this writer.
Do NOT hand-write a new skin from `default` for a tweak — that drops the current
palette and resets the background. `hermes skin set background "#08201f"` changes
only the background; `hermes skin use <name>` / `hermes skin list` switch and
enumerate.

## Installing this skin with the TUI patch

Use the `hermes-setup` repository's installer; it covers every profile and keeps the Hermes checkout clean:

1. `python3 -I scripts/setup.py install` (Windows: `py -3 -I scripts\setup.py install`). It copies the skin into each profile's `skins/`, runs `hermes skin use dsfox-skin`, sets `display.interface tui` and `display.tui_compact true`, builds the patched TUI and sets `display.tui_status_indicator activity`.
2. The "not a recognized config key" warning on `display.tui_compact` is expected: the TUI reads it (`ui-tui/src/app/useConfigSync.ts`); do not switch to `display.compact`.
3. `python3 -I scripts/setup.py status` must print `patched TUI current: True`; a new TUI window shows the `DSFOX-AGENT` wordmark. No gateway restart.

### How the patched TUI is installed (overlay, checkout stays clean)

`patches/hermes-tui.patch` is gated by `git apply --check` on the live HEAD, not by the base sha in `upstream.json`. `scripts/tui_overlay.py` clones the live checkout `--shared` at its exact HEAD, applies the patch, links `node_modules` from the checkout (an NTFS junction on Windows), builds `scripts/build/tui.mjs --out <home>/tui-overlay/ui-tui`, runs `node --check` and sets `HERMES_TUI_DIR` in every profile's `.env`.

Why this path: on Windows Hermes refuses git writes in its own running checkout (`tools/self_repo_guard.py`, NTFS locks loaded files), and a gateway-run `hermes update` stashes local edits and does not restore them by default. The `tui-overlay` gateway hook re-runs `ensure` on every `gateway:startup` (i.e. after `hermes update`): on a changed HEAD or patch it first clears `HERMES_TUI_DIR`, then rebuilds; if the patch no longer applies the stock TUI stays and the reason is in `<home>/hooks/tui-overlay/last-run.log`.

- Gateway hook `handler.py` may import only stdlib and Hermes modules: it loads in the gateway's interpreter, which may lack PyYAML. Keep per-machine data in a sidecar file (`setup-repo.txt`), not in `HOOK.yaml`. Test a hook without a restart: `gateway.hooks.HookRegistry().discover_and_load()` then `asyncio.run(r.emit('gateway:startup', {'platforms': []}))`.
- Before changing the patch, prove it on a scratch `git clone --shared` of the live checkout: `git apply --check`, `npm run typecheck` in `ui-tui`, vitest with a scratch config aliasing `@hermes/ink` to `packages/hermes-ink/src/entry-exports.ts` (the package's `dist/` is not built in launcher installs, so most suites fail on import otherwise).
- Prove adoption: start `hermes --tui` and check that the new node process runs `tui-overlay/ui-tui/dist/entry.js`; already-open windows keep the old bundle.

## Pitfalls

- **Don't hardcode `~/.hermes`** when a profile is active — resolve the real home
  from `$HERMES_HOME` first, falling back to `~/.hermes`.
- **Keep `#rrggbb` hex.** Shorthand `#rgb`, `rgb()`, and named colors are not
  guaranteed to parse on every surface.
- **Set `background`.** Without it the GUI has to guess a base surface from text
  luminance — usable, but you lose control of the app background.
- **Name collisions**: a skin named like a desktop built-in (`mono`, `slate`,
  `cyberpunk`, `nous`, `midnight`, `ember`) won't override that built-in on the
  GUI. Pick a fresh name.
- **Never hand-edit `config.yaml` to activate.** Use `hermes config set
  display.skin <name>` — a stray indent in a manual edit corrupts the file and
  can break the live gateway (including `/`). One command, always valid.
- **You apply it, not the user.** `hermes config set display.skin <name>` is
  enough — the gateway's watcher repaints every surface within ~a second. Don't
  defer to "type /skin yourself"; that's the old behavior.
- **To change one color, edit the ACTIVE skin — never fork `default`.** Forking
  `default` for a tweak drops the current palette: a skin with no `background`
  resets the terminal to its own default (often black). Patch the active skin's
  file in place so `background` and everything else survive.

## Verification

- `read_file` the written `<hermes-home>/skins/<name>.yaml` and confirm valid
  YAML with the intended `name` and `colors`.
- Run `hermes config get display.skin` and confirm it reports `<name>`.
- The repaint lands as this turn ends — ask the user to confirm the new look.
- Verify delivery independently of the YAML loader: the running Ink TUI persists its resolved palette in `<hermes-home>/tui-theme-boot.json`. Check `theme.color` for palette tokens, but do not interpret the top-level `background` as the skin's authored background: `commitTheme` writes the detected `HERMES_TUI_BACKGROUND` there, while `paintTerminalDefaults` separately applies `lastSkin.colors.background` through OSC-11. An unchanged cached physical background does not prove failed application.
- On the canonical gateway, use its supported `config.set` RPC with `key='skin'` and the existing skin name to broadcast the resolved skin to attached sessions. Use `hermes_cli.gateway_client.connect_gateway` in the PM-managed runtime; read back `config.get(key='skin')` and `runtime.describe().skin.colors.background`. Do not restart the gateway or inject a conversation merely to repaint a skin.
- For invisible background changes, treat OSC-11 query/reply only as terminal color-metadata verification, never as visible-pixel verification. A temporary hot-loaded widget can send `\x1b]11;?\x07` and record only matching OSC-11 replies to PID-specific scratch files; remove its input listener and widget afterward. Inspect allowlisted variables from the live Node process: tool-shell `TERM_PROGRAM` can disagree with the actual TUI's terminal. Capture aggregate background SGR counts without transcript text to distinguish explicit-black cells from named-default backgrounds before proposing another shade.
- (Canvas background fix: the next two bullets describe the owner's TUI patch, `patches/hermes-tui.patch` in `hermes-setup`; stock Hermes has no `Theme.background` on the root `AppLayout`.)
- Warp's `TerminalModel.set_color` stores OSC-11 in `override_colors`, and `dynamic_color_sequence` echoes it back. Its `grid_renderer/cell_type.rs::background_color` nevertheless sets alpha=0 for `Color::Named(NamedColor::Background)`, exposing Warp's own canvas. Hermes's OSC-only skin application therefore can report the requested RGB while the visible canvas stays black. Trace the installed Warp version and final cells; use an explicit opaque background on the TUI canvas when fixing Hermes, preserving 256-color output and unrelated highlight backgrounds. Do not declare the problem a too-subtle shade from a successful OSC reply alone.
- A minimal TUI canvas fix carries validated authored `skinBg` into optional `Theme.background`, sets the root `AppLayout` Box's `backgroundColor`, and compares `background` in theme equality so background-only changes force a redraw. Leave missing/invalid authored backgrounds transparent. Test real root blank cells and emitted ANSI-256 bytes, plus child-highlight preservation; do not substitute an OSC echo test.
- When a production TUI bundle must be adopted without losing the chat, inspect and test the installed Node's `process.execve` first. A temporary one-shot widget can replace only the exact current frontend PID, guarded by the expected session ID read from `HERMES_TUI_ACTIVE_SESSION_FILE` and an exclusive scratch marker. Preserve argv/environment and set `HERMES_TUI_RESUME` to that same ID; never restart the gateway or a different chat. Afterward verify the same session and nonzero actual canvas SGR emissions from the rebuilt frontend, then remove the widgets and wait for diagnostic listeners to stop. Guard diagnostic widgets against VITEST/non-TTY imports, since the test suite imports the widget loader.
- Preserve YAML anchors when making a surgical skin edit. Inspect the installed `skin_cmd._skin_set` writer before relying on it: a safe-load/dump round trip may discard scalar anchor syntax. If so, patch only the requested skin key, then apply through the supported live skin RPC; keep config.yaml writes on the native writer.
- When a requested dark color looks black or changes in visible steps, trace the final `packages/hermes-ink/src/ink/colorize.ts` stage. Legacy Apple Terminal's ANSI-256 conversion can map distinct RGB values to one palette entry; an unchanged boot-cache RGB value does not rule out this conversion. Capture only allowlisted terminal variables and `stdout.getColorDepth()` from the live TUI, using a temporary hot-loaded widget if needed; remove the diagnostic file afterward. Execute the shipped `richEightBitColorNumber` with that environment to verify the emitted palette index. Do not enable truecolor or change the terminal setup merely to hide a theme mismatch without establishing terminal support and the requested scope.
- When matching another installed application's theme, inspect its actual palette rather than inventing approximate shades. Keep backgrounds and text foregrounds separate; copy a background into a background token only.
- For an agent-runnable renderer check without installed TS development dependencies, the shipped unminified `ui-tui/dist/entry.js` contains the compiled color and theme modules. Execute those exact modules with their bundle initializer in an isolated Node VM, then call `fromSkin`; do not modify the product bundle. Native Node type stripping alone cannot load TypeScript parameter properties.

## User-message and composer backgrounds (custom TUI)

- The local frontend supports optional `colors.user_message_bg` and `colors.input_bg`, resolved to `Theme.userMessageBg` and `Theme.inputBg`. Missing or invalid values remain transparent. Apply the former only after service/event message branches, and the latter to live and buffered input rows; preserve status, overlays, transcript spacing and other message backgrounds.
- Include scoped backgrounds in theme equality so changes schedule the normal full repaint. Test multiline messages, narrow/wide layouts, empty input, buffered lines and unchanged assistant/service rendering.
- For a preview that needs a new frontend bundle, guard targeted replacement by PID, session and bundle digest; inspect the actual composer draft before replacement and refuse to discard unsent input. Keep the gateway and other frontends running.
- A zero count from a late stdout probe does not establish that a color was never painted. Inspect the current renderer frame's cell styles without recording transcript text. Keep logical frame colors distinct from final terminal color encoding.
- When the user makes publication conditional on appearance approval, apply and verify the preview locally, then wait for that approval before pushing.
