# Image acceptance and controlled comparisons

## Prepare a repeatable case

1. Choose an agent-owned synthetic source with clear geometry and a plain background.
   Request one localized change plus explicit preservation requirements. A clean
   background makes unintended texture easier to detect than a busy scene.
2. Save the source, actual mask and request payload before starting the job. Retain
   source and mask hashes, output dimensions, checkpoint revision, precision,
   seed, steps, guidance and reference order. Distinguish requested CLI values
   from effective runtime values when metadata leaves fields empty.
3. Use unique output filenames and persist the returned job identifier outside
   the browser. Recover the result from that job instead of generating again
   when browser state is lost. Keep rejected outputs for comparison.

## Run acceptance in layers

| Layer | Agent-run check | What it does not establish |
|---|---|---|
| Installation | Verify every expected file's size and SHA256 against the pinned receipt | Model quality or a working GUI |
| Execution | Require successful completion, a decodable output and expected dimensions | Instruction adherence |
| Mask preservation | Compare source and output pixels wherever the actual blend mask is zero | Quality inside the selected region |
| Requested change | Measure the relevant change, such as recoloring of the original foreground | Shape, material or background fidelity |
| Visual quality | Inspect the whole image and selected-region detail, including background inside a broad mask | Reliability on arbitrary prompts |
| Interaction | Exercise actual load, selection, undo/redo, compare, revert and save behavior as required; read saved pixels back | Untested controls or native pointer delivery |

Use the application's real feathering/compositing procedure when deriving the
unchanged region. If the actual mask was not retained, report only the regions
that were checked; do not reconstruct approximate coordinates and claim exact
preservation everywhere outside the user's selection.

For a recoloring case, check the silhouette, lid, handle, spout, material,
reflections, object position and background. A high fraction of red pixels
turning blue can coexist with severe geometric or texture corruption.

Write separate technical and visual verdicts. After numerical checks, use a
pending-review state rather than an overall pass. If inspection fails, mark the
trial rejected and correct any readiness claim before further experiments.

## Isolate a quality regression

Start with the existing successful and failed trials. Change only one factor per
comparison, keeping source bytes, prompt, reference order, seed and other settings
fixed. Useful comparisons are:

- Same target resolution and precision, fewer steps: tests step-count dependence.
- Same steps and precision, lower output resolution: tests resolution dependence.
- Same target resolution and steps, another precision: tests checkpoint precision.

Do not infer a quantization defect solely because lower resolution looks clean.
Check the installed implementation and the exact model/conversion guidance before
choosing the next experiment. Do not install successive alternatives without a
specific hypothesis. Inspect each short trial before spending time on a long run.

A low-resolution or few-step pass is a smoke result. Repeat the intended delivery
configuration before promoting it to an approved default. Keep an unchanged,
working generator separate from an editor under investigation.

## Preserve and report the evidence

- Retain failed and accepted trial records separately; never overwrite a rejected
  example with a better result under the same filename.
- Record wall-clock duration separately from model-reported generation time and
  peak MLX allocation separately from process RSS; they measure different things.
- Store only portable revisions, checksums, dependency locks, source patches and
  concise acceptance records in the setup backup. Keep full prompts and images
  in the user's local output directory.
- Describe a dependent background run as queued until it actually starts. Require
  a complete, matching installation receipt before inference; process exit alone
  does not establish successful download or checksum verification.
- Report ready components and unresolved gates separately. A candidate download
  or a completed numerical check must not turn an unfinished editor into a
  completed setup in the final answer.
