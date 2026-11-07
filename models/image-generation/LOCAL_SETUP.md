# Local image setup on this Mac

This installation uses MFLUX 0.24.0 with native MLX inference on Apple Silicon.
It is independent of Hermes and does not use an image-generation cloud API.

## Validation status

Generation passed a 1024x1024, 30-step visual check. The selected editor uses the
2509-family Q8 checkpoint with its Lightning 4-step adapter, guidance 1.0 and the
author's shift-3 schedule without terminal rescaling. A real 1024x1024 recoloring
test passed visual review without a mask. Earlier base-model trials and the
incorrect 2511 architecture failed; their records are retained separately.
The runtime also corrects image position IDs, M-RoPE sections and the EditPlus
template. Exact preservation still requires a mask; this is not a universal
quality guarantee for every prompt. See the acceptance records for measured limits.

## Models

- Generation: `Qwen/Qwen-Image-2512`, MFlux community Q6 conversion.
- Reference editing: Qwen-Image-Edit-2509 family, community Q8 conversion.
  The download directory remains named `qwen-image-edit-2511-mflux-q8` to preserve
  the original repository identifier. Eight sampled biases match official 2509
  exactly; sampled dequantized matrices also match 2509 most closely. Do not infer
  the architecture from this misleading directory label.
- Fast editing adapter: LightX2V Qwen-Image-Edit-2509-Lightning-4steps-V1.0 BF16,
  applied at scale 1.0 without baking or modifying the base weight files.
- Both original model cards declare Apache-2.0. The Qwen-Image-2.1 release is a
  different model with different licensing and is not installed here.
- The transformer weights are quantized. The inspected text encoder and VAE
  remain BF16; the advertised quantization does not cover every component.

The exact revisions and weight checksums are retained in the setup repository's
`models/image-generation/` artifacts. Weights are under
`$HOME/.local/share/local-image-studio/models/` and are not committed to Git.

## Application

Launch `$HOME/Applications/MFLUX Paint.app`.

The picker exposes only the two installed models. Generation is selected first.
The launch path also resolves MFLUX when Finder supplies a minimal PATH.
Low-memory mode is enabled for every generation. The backend binds only to
`127.0.0.1:7866`; inference subprocesses set `HF_HUB_OFFLINE=1`.

1. For a new image, choose **Qwen-Image-2512 Q6**, enter a prompt and press Run.
2. For an edit, choose **Qwen-Image-Edit-2509 Q8 Lightning 4-step** and drop in the source image.
3. Paint or box-select an area to preserve the rest of the original, then describe
   the desired change. Without a selection, the whole image can be edited.
4. Use Compare, Undo and Save. The folder button saves under
   `$HOME/Pictures/Local Image Studio`.
5. Generation defaults to 30 steps. The installed editor requires exactly 4 steps
   and guidance 1.0; its scheduler rejects other combinations. Both presets allow
   up to 1024 pixels on the long side. Use smaller sizes for drafts. An empty
   quantization setting means use the stored weights.

Masking in this application blends the generated edit onto the original with a
soft edge. It is not native mask-conditioned diffusion, and pixels immediately
around the painted boundary may participate in feathering.

The application has one image input. The CLI below supports multiple references.
Run GPU jobs sequentially on this 48 GB machine. Keep the application open while
an application job is running; cancellation is available in its progress dialog.

## Direct commands

Generation:

```sh
HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 mflux-generate-qwen \
  --model "$HOME/.local/share/local-image-studio/models/qwen-image-2512-mflux-q6" \
  --base-model qwen-image --low-ram --width 1024 --height 1024 \
  --steps 30 --guidance 3.5 --seed 42 \
  --prompt 'Describe the image here.' --make-conf --output output.png
```

Editing, with one or more references:

```sh
HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 mflux-generate-qwen-edit \
  --model "$HOME/.local/share/local-image-studio/models/qwen-image-edit-2511-mflux-q8" \
  --base-model qwen-image-edit --low-ram --width 1024 --height 1024 \
  --steps 4 --guidance 1.0 --seed 42 \
  --scheduler lightning_scheduler.LightningScheduler \
  --lora-paths "$HOME/.local/share/local-image-studio/adapters/Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors" \
  --lora-scales 1.0 --no-bake-lora \
  --image-paths source.png reference.png \
  --prompt 'Describe the desired change here.' --make-conf --output edited.png
```

Use explicit output paths to avoid overwriting earlier versions. Preserve the
seed and generation metadata when comparing edits. Prompts may be embedded in
output image metadata; keep private company inputs and results local.

## Local modifications

The upstream UI is MIT-licensed. This checkout narrows the picker to installed
Apache-2.0 models, selects the verified 2509 edit architecture explicitly, enables
low-memory mode, resolves uv binaries when launched from Finder, and sets the
output folder. The upstream source URL is unchanged; local commits are not
pushed to that project's remote.

The MFLUX runtime patch is separate from the GUI patch. Apply it using the
version- and hash-checked `models/image-generation/apply_runtime_patch.py` after
installing the pinned runtime; this also installs the Lightning scheduler module.
Run `verify_conditioning.py` and `verify_lightning.py`. Package upgrades
can replace patched files; the patch installer refuses an unrecognized baseline.
