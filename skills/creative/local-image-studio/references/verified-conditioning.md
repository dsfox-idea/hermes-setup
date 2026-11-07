# Verified checkpoint and conditioning findings

Read the installed application's LOCAL_SETUP.md and setup repository acceptance
records before launching expensive work. Historical model names and earlier trial
settings are not evidence that the selected architecture is correct.

## Checkpoint identity

The pinned community directories named qwen-image-edit-2511-mflux-q6 and q8 contain
sampled biases that match official Qwen-Image-Edit-2509 exactly, not 2511. Sampled
Q8 dequantized matrices are also closest to 2509. The configured editor therefore
uses qwen-image-edit (2509), with Q8 weights, while retaining the download directory
name. Genuine 2511 weights require a different architecture setting. Validate
both bias fingerprints and dequantized matrix samples before trusting a converted
checkpoint's label; shared or frozen biases alone are not conclusive.

## Runtime patch

The local MFLUX 0.24.0 runtime has three conditioning fixes, backed up under
models/image-generation/mflux-conditioning.patch with exact source hashes:
- Image tokens receive independent temporal, height and width positions.
- M-RoPE sections repeat [16,24,24] twice, instead of doubling each section.
- EditPlus uses a Picture prefix for each reference image.

Use apply_runtime_patch.py with the MFLUX interpreter. It refuses another version
or modified source and verifies the result. verify_conditioning.py checks the
actual installed code without loading weights. Text-only position behavior stays
unchanged. The position helper matched the official Transformers v4.57.1 function
on randomized padded, batched and multi-image inputs.

These are verified code defects; passing their regressions does not establish
that an image's visual quality is acceptable. A four-step patched run still showed
background drift. The old 40-step run used the wrong architecture and is not a
valid quality benchmark for the corrected runtime.

## Efficient diagnosis and acceptance

Use checkpoint fingerprints, tensor-key coverage, VAE roundtrips, schedule and
packing checks, and miniature CPU/GPU parity tests before full-image inference.
A single diffusion block and a miniature full transformer can share weights with
Diffusers and compare outputs without loading a real large model. Keep reference
packages in scratch, outside the installed production environment.

A mask composite can preserve the background exactly, but must be labeled as a
masked result, not evidence that unrestricted editing is fixed. A hand-designed
or color-derived mask for a test image is an acceptance fixture, not a general
segmentation feature. Keep original output, mask and composite separately.
