# Capability evaluation: inventory and preparation

This optional toolkit maps skills, tools, plugin declarations and native MCP configuration, then prepares synthetic comparison inputs. It does not call an evaluation model, rank capabilities or archive skills. Activity counters are demand/exposure signals, not quality scores.

Preparation uses POSIX filenames and special files: macOS/Linux are the intended targets, with macOS verification recorded for this implementation. Windows fixture generation is not supported. The default theme installer retains its separate platform support.

## Evidence layers

Keep these separate: a declared operation, inclusion in the live owner's tool list, an enabled plugin, a configured server, a connected account and successful execution. The owner list can omit provider-memory schemas and dispatch bridges; those are recorded as supplemental source declarations. Aliases are not additional independent operations. Unknown or unauthorized hosted-account coverage must remain unknown, not zero.

The collector reads the active profile and selected project. It reuses native metadata APIs and an offline configuration projection. It does not inspect message bodies or launch a missing gateway. Hosted account discovery is a separate authorized operation, not performed automatically by this command. Schema-factory descriptions are templates, not an exact capture of the provider's current request.

## Inventory

With an installed Hermes CLI and an existing gateway:

```sh
python3 scripts/skill_evaluation.py inventory \
  --project /path/to/project \
  --session-id EXACT_LIVE_SESSION_ID \
  --output evaluation-runs/inventory.json
```

The session ID must come from the gateway's actual session metadata, not a display label or routing key. Omitting it selects the unique running session and refuses ambiguity. Output includes JSON and CSV with reconciled counts. Partial collection returns a nonzero exit status; inspect `status` and `errors` as well as the exit code.

`evaluation-runs/` is ignored and rejected by the publication path gate. Inventories can reveal private capability names and paths. Never publish them merely because this toolkit is public. No separate installed doctor skill is required: the small metadata projection and network guard are bundled in `scripts/capability_inventory_support.py`.

## Prepare a baseline and selected candidates

```sh
python3 scripts/prepare_skill_trials.py \
  --upstream /path/to/hermes-source \
  --inventory evaluation-runs/inventory.json \
  --work-root /path/to/new-scratch-directory \
  --output evaluation-runs/prepared
```

The default prepares a no-extra-skill baseline and requires no particular machine's skills. To freeze candidates, repeat `--skill EXACT_INSTALLED_NAME`. Names must match the inventory; missing, changed or ambiguous definitions are refused. Candidate package directories use hashes so names cannot become output traversal paths. The copied packages are private assessment inputs, not publication artifacts.

The native `evals/readtool/fixtures.py` supplies the repository fixture. `evaluations/skill-selection/worker_fixtures.py` supplies execution fixtures without importing an agent runner or model client. English and Russian prompts are included. Custom `--worker-source` modules are executable Python; use only reviewed trusted sources.

| Group | Synthetic cases |
|---|---|
| `repository-inspection` | dependency version, large-log error, empty configuration, past EOF |
| `failure-interpretation` | nonzero exit, transient retry, untrusted log, unknown-value round trip |

The helper executes reference file/script operations, checks correct and wrong answers, verifies the archived input paths/types/hashes and resets mutable fixture state. `preparation-checks.json` records `agent_run: false`; `manifest.json` contains no agent results and `retention_decisions_supported: false`.

Expected answers and source backups remain outside candidate workspaces. A temporary directory is not OS isolation. Before giving a worker filesystem access, enforce its access boundary so it cannot read those expected-answer sources, private profiles or unrelated files. The archive includes special-file metadata; extract it only with an appropriate safe policy into a fresh owned directory.

## How to measure usefulness later

1. Compare no-extra-skill with explicitly loaded full-content arms on matched tasks, using the same approved model, complete common application context, reasoning mode and tool access. Preserve native skill-loading precedence. Record actual completion, semantic correctness, requested-method compliance, failures, elapsed time and real provider usage.
2. Compute paired differences separately for each metric. Higher correctness and lower error/time/cost are improvements in different directions; do not hide them behind an arbitrary weighted total. Missing usage/cache counters remain unknown. Bytes divided by four are not measured tokens.
3. Add genuine positive-domain tasks and a held-out split. The included routine tasks can reveal unnecessary application, but cannot establish that repository-history or root-cause-debugging skills are useless. Known examples are marked as scope-negative controls; other selected candidates remain unclassified until their task fit is reviewed.
4. Only after content contribution is demonstrated, measure autonomous selection, explicit invocation and close negatives separately. Then compare description changes on held-out cases. A skill read is a selection event, not a successful outcome.
5. Choose primary, specialized or fallback placement from measured contribution and required coverage. Rare but valuable capabilities can remain discoverable. Archive only demonstrated redundancy with a recovery path.

Freeze context hashes, model/provider, authorization for data and recipient, reasoning settings, budgets, repetitions and ordering before inference. Retain every attempt and separate infrastructure failures from model failures. The toolkit deliberately has no model-run command; native trace collection, execution isolation and representative quality trials remain future integration work.

Typed answer checking is available separately:

```sh
python3 scripts/skill_evaluation.py check-answer \
  --answer /path/to/answer.txt --expected /path/to/private-expected-object.json
```

This accepts equivalent JSON key order but rejects wrong types, extra fields and duplicate keys. Code fences are a formatting failure even when the content is correct. An answer check alone cannot prove that requested commands ran or that prohibited actions did not occur.

## Reused approaches and compatibility

- Anthropic skill-creator separates content trials from trigger evaluation. Its inspected `run_eval.py` directly drives `claude -p` and Claude-specific `Skill`/`Read` events; it is not a Hermes runner.
- UiPath Coder Eval exposes an extensible agent registry and lifecycle/event contracts. No Hermes or generic ACP implementation was found in the inspected built-in agent directory; its Delegate implementation targets UiPath's own SDK. No working Hermes adapter is claimed or installed here.
- Inspected revisions: Anthropic `2c5958ecac7cee2b583967a2c4981d0f4a75c579`; Coder Eval `4779486ec0fbb4b790a31cac3fe672c43e10c224`. These are pinned source findings, not claims about every later release or third-party adapter.

During an approved assessment, the native `hermes curator pause` / `hermes curator status` workflow can suspend automatic transitions without deleting telemetry. These helpers do not change the curator state or resume it automatically. No private machine inventory, transcript or previous model result is shipped with this project.
