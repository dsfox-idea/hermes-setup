---
name: local-image-studio
description: Use when generating or editing images locally on Mac.
version: 0.1.0
platforms: [macos]
---

# Local image studio

Use the installed MFLUX/MLX environment for local image generation and reference
editing. Do not replace the main conversation model or silently use cloud image APIs.

## When to Use

Use for local text-to-image generation, reference edits and painted-mask workflows.
Do not use it to certify arbitrary prompts or untested precision/resolution settings.

## Installed setup

- Runtime: `~/.local/share/uv/tools/mflux/bin/python`, MFLUX 0.24.0.
- Commands: `~/.local/bin/mflux-generate-qwen` and `mflux-generate-qwen-edit`.
- Model directories under `~/.local/share/local-image-studio/models/`:
  `qwen-image-2512-mflux-q6` and `qwen-image-edit-2511-mflux-q8`.
  The editor contains 2509-family weights despite the directory label.
- GUI: `~/Applications/MFLUX Paint.app`; source under
  `~/.local/share/local-image-studio/app`; output under `~/Pictures/Local Image Studio`.
- Read the installed `LOCAL_SETUP.md` for tested commands and limitations. The
  setup repository retains `models/image-generation/models.lock.json` and verifiers.

## Procedure

1. Inspect existing jobs and saved acceptance records before starting another GPU
   job. Use `terminal` and `read_file`; serialize inference on this 48 GB Mac.
   Correlate completion notices with the exact job and previously reviewed output;
   stale notices do not justify another run, another status reply, or polling other
   pending jobs. Do not restart a job merely because a browser tab or an agent
   response was lost. Gate dependent inference on a verified installation receipt,
   not merely the download process exiting or a model directory existing.
2. Run with `HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1`, local model paths and
   `--low-ram`. Set an explicit seed and unique output path; preserve `--make-conf`
   metadata. Start with a draft when speed matters; 30-step 1024-pixel jobs take
   minutes and editing may take substantially longer.
3. Match checkpoint contents, not directory labels: generation uses
   `--base-model qwen-image`; the installed Q8 editor uses
   `--base-model qwen-image-edit` (verified 2509 contents) and `--image-paths`.
   Apply `models/image-generation/apply_runtime_patch.py`; it checks MFLUX 0.24.0,
   fixes conditioning and installs `lightning_scheduler.LightningScheduler`.
   The accepted fast editor requires the pinned 2509 Lightning 4-step BF16 adapter,
   `--steps 4 --guidance 1.0 --lora-scales 1.0 --no-bake-lora` and that scheduler.
   Its sigmas are [1, .9, .75, .5, 0], with shift 3 and no terminal rescaling.
   Read `lightning-setup.json` and the installed `LOCAL_SETUP.md` for exact paths.
   Base-model four/eight-step failures are not evidence against the distilled mode;
   do not retry those settings or silently raise the distilled step count.
   The accepted unmasked 1024-pixel trial took 5.81 minutes and 40.27 GB peak MLX;
   the live 512-pixel application mask/save check took 77.15 seconds. These are
   measured fixtures, not universal performance or quality guarantees.
4. In the GUI, select the corresponding installed model, load the source, paint
   a mask if needed, and describe the change. Use a named `browser_exec` session
   for nonintrusive local-page checks. Do not reopen desktop windows the user closed.
5. Verify a real saved output, dimensions, requested change and preservation of
   relevant regions at the intended delivery resolution. Separate execution,
   pixel-preservation, visual-quality and GUI-interaction verdicts. Keep overall
   acceptance pending until the required layers pass; exit code zero is only an
   execution result. If visual review invalidates a numerical pass, correct the
   receipt and readiness documentation before trying another setting. Follow
   `references/image-acceptance.md` for matched comparisons and evidence handling.
   Read `/progress?job=ID` at loopback port 7866; filter image data URIs out of logs.
   Read and save a finished job before terminating a temporary test server.
6. Save successful results and report actual timings plus limitations. Stop only
   temporary servers owned by the task, after checking that no job is running;
   the native launcher cannot create its window while a headless server owns 7866.

## Pitfalls and verification

- GUI masks feather and composite the generated image onto its original; they are
  not native mask-conditioned diffusion. Check pixels well beyond the soft edge.
- The GUI accepts one source; multiple references work through the CLI.
- Q6 describes the transformer, not the BF16 text encoder and VAE. Do not assume
  successful low-resolution edits establish quality at larger sizes: Qwen edit
  quantization is sensitive, and flat backgrounds reveal accumulated noise.
  Compare the same source, prompt, seed and dimensions when changing precision.
- Automated recoloring and outside-mask checks are technical gates only. Keep
  acceptance pending until visual review confirms the selected area is intact.
- Check the browser's current URL and application state before continuing a
  multi-call test; a session name is not proof that the intended page is still
  active. Preserve job IDs outside the page and recover actual results from the
  local backend. Keep backend save verification separate from browser interaction
  verification when recovering a lost page; one does not establish the other.
- Private company references, prompts and outputs stay local. Cloud visual
  inspection requires explicit permission for those contents and that recipient.
- Use actual UI effects, not only successful mouse-call responses. After a timed-out
  pointer action, inspect `drawing` and mask state before retrying; finish an active
  drag rather than starting another one. Undo/redo refer to masks; revert restores
  the previous generated image.
- For macOS process-exit monitoring, `select.kqueue()` lacks context-manager
  methods. Wrap it with `contextlib.closing`; test against a real short-lived child
  before waiting on a long inference. Do not fabricate progress or completion.
- When the installer is under task control, chain verification and inference with
  successful exit status (`installer && comparison`), rather than merely observing
  installer termination. A failed download must not start inference.
- Resume interrupted aria2 downloads from their existing control files. A file
  with its full expected size can still be incomplete while its `.aria2` file
  exists. Keep such files in the resume list, and verify hashes before acceptance.
