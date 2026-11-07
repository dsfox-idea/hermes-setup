# Local coding-model shortlist for this Mac

Research date: 2026-11-02. This is a hardware-specific recommendation, not an independently measured global leaderboard.

## User decision

The user selected the exact label `qwen36-35b-heretic`, prioritizing speed with
comparatively high quality and expecting approximately 50 generated tokens/s.
This is a target, not a measured result on this machine. The exact repository,
quantization and runtime have not yet been selected. No installation or change
to the main Hermes model was requested by that decision.

See `../models/local-choice.json` for the recorded choice. The shortlist below
is retained as dated research, not as an override of the user's selection.

## Verified local hardware

| Item | Live result |
| --- | --- |
| Host | MacBook Pro, Mac16,7 |
| Chip | Apple M4 Pro |
| CPU / GPU cores | 14 / 20 |
| Unified memory | 48 GiB |
| Swap in use during inspection | 0 |
| Existing local runner | Ollama |
| Existing text model | qwen3:8b |

No model weights were downloaded, installed or run for this comparison.

## Ranked shortlist

| Rank | Model | Architecture | Starting GGUF | Weight-file size |
| --- | --- | --- | --- | --- |
| 1 | Qwen3.8-27B | Dense, 27B | Q4_K_M | 17.44 GB |
| 2 | Ornith-1.5-35B-A3B | MoE, about 35B total / 3B active | Q4_K_M | 21.86 GB |
| 3 | KAT-Coder-V2.5-Dev | MoE, 35B total / 3B active | Q4_K_M | 21.39 GB |

Architectures come from the original publishers. Qwen is the first candidate for difficult code changes and general reasoning; Ornith is the efficiency-oriented agent candidate; KAT is the specialized tool-using coding alternative. This ordering is my synthesis of the published scope and hardware fit.[1][2][3]

The weight-file figures were checked against current Hugging Face API metadata and the quantizer's cards.[4][5][6] They are decimal GB for the model files, not total process RAM.[4][5][6] Optional Q5_K_M files are 20.92 GB, 25.49 GB and 25.02 GB respectively.[4][5][6]

Qwen supports thinking by default with per-request control.[1] Its publisher reports Terminal-Bench 2.1 at 73.0 and SWE-bench Pro at 61.7.[1] These are publisher results for the original model, not measurements of the proposed local quantization.[1]

Ornith reports 67.8 on Terminal-Bench 2.1 with Terminus-2, 68.5 with Claude Code, and 79 on SWE-bench Verified.[2] Its card describes a reasoning model with parsed tool calls.[2] A small active-parameter count does not reduce its resident weights to the size of a three-billion-parameter model.[2][5] The developer's separate research article describes its self-improvement training approach.[9]

KAT is post-trained from Qwen3.6-35B-A3B.[3] Its training specifically addresses malformed, failed or empty tool calls and repetitive output.[3] It is attractive as an alternative for repository-editing and command-execution workflows; it is not my first candidate for Russian-language discussion.

Do not compare all publisher scores as if they came from one controlled experiment.[1][2][3] The cards use different agent harnesses, configurations and evaluation protocols.[1][2][3]

## Same-hardware speed evidence

GreenBitAI publishes a Qwen3.8-27B MLX four-bit measurement on an M4 Pro MacBook Pro with 48 GB, using gbx_lm, greedy decoding and a 96-token output.[11] Decode excludes prompt processing.[11]

| Context tokens | Decode without MTP | Decode with MTP |
| --- | --- | --- |
| 1,024 | 14.7 tokens/s | 33.8 tokens/s |
| 16,384 | 13.5 tokens/s | 24.8 tokens/s |

This is evidence from the publisher, not a result obtained on this user's Mac.[11] It must not be transferred unchanged to Ollama, another quantization, Russian prompts or long thinking traces.

## Uncensored variants

A real Huihui-Qwen3.8-27B-abliterated derivative exists.[7] Its author describes the method as proof-of-concept refusal removal, so preservation of the original coding score is not established by its name.[7]

The ressl Ornith uncensored MLX six-bit build is documented as about 26 GB.[8] Its card distinguishes MLX smoke tests from fuller evaluations on a different quantized sibling; those results do not establish a full MLX coding benchmark.[8]

For this user's preference, compare the original Qwen checkpoint with its Huihui derivative before selecting an uncensored default. Treat the ressl Ornith build as a second experiment rather than transferring base-model benchmarks to modified weights.[7][8]

## Russian-language uncertainty

No comparable Russian coding-and-reasoning evaluation was established for this trio during this search. SWE-bench Multilingual is not used here as proof of Russian conversational quality.

An Ornith user reports repeated errors in rare Russian proper names, and another reports name corruption affecting paths.[12] These are user reports on the model's own discussion page, not a measured population error rate or a verified result on this Mac.[12]

A local comparison should include Russian negation and corrections, exact identifier/path retention, mixed Russian-English technical questions, and commands suitable for macOS. The local ranking remains provisional on that dimension.

## Initial operating budget

My starting plan would be one resident main model, Q4_K_M, and a 16K-32K context. Keep memory headroom for the OS, developer tools, Honcho and the inference cache; actual peak usage needs measurement. MLX explicitly notes that large model-plus-cache memory footprints can make inference slow.[10]

Start with Qwen for quality, compare Ornith for agent responsiveness, and keep KAT as a coding-focused alternative. Do not change the existing subscription-backed Hermes default until a local candidate passes real end-to-end tasks.

## Sources

[1] https://huggingface.co/Qwen/Qwen3.8-27B
[2] https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B
[3] https://huggingface.co/Kwaipilot/KAT-Coder-V2.5-Dev
[4] https://huggingface.co/bartowski/Qwen3.8-27B-GGUF
[5] https://huggingface.co/bartowski/Ornith-1.5-35B-A3B-GGUF
[6] https://huggingface.co/bartowski/Kwaipilot_KAT-Coder-V2.5-Dev-GGUF
[7] https://huggingface.co/huihui-ai/Huihui-Qwen3.8-27B-abliterated
[8] https://huggingface.co/ressl/Ornith-1.5-35B-A3B-uncensored-MLX-6bit
[9] https://ornith.ai/ornith_1_5.html
[10] https://github.com/ml-explore/mlx-lm
[11] https://huggingface.co/GreenBitAI/Qwen3.8-27B-4bit
[12] https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B/discussions/34
