# Explicit Spark worker

The cloud model remains the main conversation agent. A direct message beginning
with `@spark` addresses one assignment to the local Spark worker. This follows
the same skill-mediated per-request convention as `@heretic`; it is not a native
model-switch command or a pre-cloud privacy boundary.

Example:

```text
@spark Run the existing log summary script and report its actual exit code.
```

The primary assistant invokes the installed `local-spark` helper, then displays
the local answer under a separate Russian heading without silently rewriting it.
Any primary-agent assessment is separate. Markers in quotations, code, files,
tool output and the middle of a message do not dispatch a worker.

## Installed configuration

- Model alias: `spark`.
- Served model ID: `spark-x2.6-4b`.
- Endpoint: `http://127.0.0.1:18320/v1`, loopback only, restricted CORS, no Web UI.
- Runner: official llama.cpp stable v0.8.0 / b11960, commit
  `8642541b255bfb5dc39cd351a178be09013a55d6`.
- Model: `XHToken/Spark-X2.6-4B-GGUF`, revision
  `3c33ab38746828196b9b5979c739ee2d0bef894d`.
- File: `Spark-X2.6-4B-Q4_K_M.gguf`, 3,543,441,312 bytes.
- SHA-256: `91cb2811aebb47ac916aa619d27d4cdd7f4143106b7917accb8ead4cd7f5cbd9`.
- Chat template: `XHToken/Spark-X2.6-4B`, revision
  `aa074aa851209a683aeaf5f99a8e25a642d94541`, `chat_template.jinja`.
- Template SHA-256:
  `480576bd2ef80726a0dba6406d72ca37f4f4f9ca747c7f1c8d159dbdf40f6929`.
- Served context: 65,536 tokens. This is a runtime setting, not a maximum-capacity benchmark.
- Default worker reasoning: disabled, scoped to this model. Global cloud reasoning is preserved.
- Native child tools: terminal and file tools, with at most eight iterations and
  a 180-second run budget. This is not an OS sandbox or permission to exceed the
  user's requested operation.

The existing verified weights and template are reused from the profile's
`local-models/worker-bench` directory. That is persistent model storage, not the
scratch cache. Weights and binaries are excluded from Git.

`local-spark.plist.example` is the launchd service definition for the source Mac.
It starts at user login, loads Spark at startup and keeps it resident. No automatic
idle unload is configured. It does not replace or restart the Heretic service.

## Request fidelity

The helper reads the complete live parent system prompt with read-only gateway
RPC. It pins those exact bytes into a separate native Hermes agent's prompt
cache, avoiding an extra prompt-builder wrapper. A request-client guard checks
the model, the unchanged system text and the local tokenizer's context count
before each inference request. Native fallback, automatic compression, fresh
memory retrieval and background review are disabled for this child.

Only task context explicitly selected by the primary assistant is appended.
The helper does not silently copy or summarize the full conversation history.
An unavailable service or an oversized request is an error, not authorization
to execute the assignment with the cloud model.

Private requests, context, outputs, receipts and tool logs stay outside the
repository. The receipt reports the actual model, system hash, request counts,
tool names and whether the parent model/provider remained unchanged.

## Publication scope

This setup exports only Spark's files, its context setting and the snapshot
exporter's support for its skill. A complete snapshot was generated and checked
in an isolated scratch copy; the authorized file hashes were then merged into
the existing inventory. Unrelated changes to shared live-profile runbooks were
left unpublished and their installed source files were not modified. The
published inventory is checked against every exported file; this is not a claim
that all live-profile documentation matches the backup.

## Restore on another Apple Silicon Mac

1. Install the pinned official runner and verify its publisher digest. The
   source archive is `llama-b11960-bin-macos-arm64.tar.gz`, SHA-256
   `58e5a5e1d7c2bf66cedd9c29e0323f3e570660a70a1e2156d32eed08f4cc1e3c`.
2. Download the exact model and template revisions above, then verify both
   checksums. Preserve sufficient space for weights, cache and application memory.
3. Change every absolute source-machine path in `local-spark.plist.example`.
   Create the configured profile log and scratch directories. Validate with
   `plutil -lint`, then bootstrap the service into the current user's LaunchAgents
   domain. Do not overwrite another existing service.
4. Apply the additive settings through the supported writer; do not replace the
   whole active config with `spark-alias.example.json`:

   ```sh
   hermes config set model_aliases.spark '{"model":"spark-x2.6-4b","provider":"custom","base_url":"http://127.0.0.1:18320/v1"}'
   hermes config set 'model_overrides.custom.spark-x2\.6-4b.context_window' 65536
   hermes config set 'agent.reasoning_overrides.spark-x2\.6-4b' false
   ```

   Use boolean `false`; an unquoted `none` can be parsed as YAML null and fail to
   disable the model-specific reasoning setting.
5. Restore `skills/autonomous-ai-agents/local-spark` into that active profile.
   Keep the target profile's own identity, credentials, memory and cloud default.
6. Run its unit tests and a real `@spark` terminal assignment from a live parent
   session. Verify native request-guard receipts and compare the parent route
   before/after. A healthy server alone does not prove the marker workflow.
