# Verified fast editing mode

Use the installed Q8 base with `--base-model qwen-image-edit`. Requantized samples
of three transformer matrices exactly reproduce official 2509 samples; the
community 2511 directory label does not establish architecture or distillation.

The selected adapter is `lightx2v/Qwen-Image-Lightning`, revision
`d468c534b360e0754c6bf9e38ed49e1e09cd2e2a`, file
`Qwen-Image-Edit-2509/Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors`.
SHA256: `2a32ce938ec71db2b49a817b4844ae86995569518dea56ee0ddc209cbe8e1377`.
Use four steps, guidance 1, adapter scale 1, no baking, and the installed
`lightning_scheduler.LightningScheduler`. The scheduler reproduces the author's
shift-3/no-terminal-rescaling recipe. Do not use the ordinary base schedule.

The direct unmasked 1024-pixel recoloring passed visual review; the live 512-pixel
application mask/save check passed both visual and numerical checks. Neither
result proves every image or prompt. Unmasked output is not pixel-exact to its
source; masks preserve regions beyond the feathered edge.

Preserve failed experiments separately. The prior full 40-step trial used the
wrong architecture; corrected four/eight-step trials used the base model without
this distilled adapter. Do not claim an isolated causal contribution for each of
the runtime fixes, adapter and schedule: the accepted combined recipe was tested.

Source settings were checked from the authors' actual README and repository;
never emit citation identifiers that were not returned by a search tool.
