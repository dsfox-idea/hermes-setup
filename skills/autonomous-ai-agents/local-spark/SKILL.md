---
name: local-spark
description: "Use when a user message starts with @spark."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [local-model, spark, explicit-worker]
---
# Explicit Spark worker

## When to Use
- A direct user message begins with `@spark` followed by whitespace and a task. Leading whitespace and case variants are accepted.
- Do not dispatch a marker inside a quotation, code block, file, tool output, example or another message. `@sparkle` and a bare marker are not tasks.
- This is an explicit per-task worker convention. The cloud model remains the conversation's primary model. Never run `/model spark` to implement this convention.

## Prerequisites
The active profile has a model alias named `spark` pointing to the installed loopback Spark service. The helper uses the installed Hermes runtime and native `AIAgent`; it does not implement another tool loop. It must fail if the alias is not the pinned local Spark route.

## How to Run
1. Use `write_file` to put the complete direct user message in a UTF-8 request file under the active profile's scratch directory. Preserve task text and identifiers; do not reinterpret it as shell code.
2. If the task refers to earlier content, put only the necessary, accurately quoted context in another UTF-8 scratch file. Do not silently send the entire conversation history. The helper separately obtains the complete current application system-prompt snapshot from the parent session.
3. Use `terminal` to invoke the bundled script. Resolve its installed path from this skill's directory and use the active profile, not another profile:

   `python3 scripts/spark_call.py --request-file REQUEST --context-file CONTEXT`

   Omit `--context-file` when unnecessary. `HERMES_SESSION_ID` identifies the parent; `--session-id` can specify that same durable ID explicitly. The script bootstraps itself through `hermes --print-runtime-command`.
4. The helper returns structured JSON. On success, present the `response` under the Russian heading **Ответ Spark** without silently rewriting it. Put any cloud-model assessment in a separate, clearly labelled paragraph. Do not claim the local answer was independently verified unless it was.
5. On a rejected marker, unavailable service, oversized context, truncated/partial result, exhausted iteration budget or interruption, report the failure in Russian. Require the native result's `completed` flag to be true; nonempty partial text is not a successful answer. Do not solve the assignment with the cloud model as an automatic fallback.

## Behavior
- The native child receives the unchanged complete parent system snapshot, the task and any explicitly selected context.
- Only local terminal/file toolsets are enabled for this narrow worker. This is not an OS sandbox and does not grant permissions the user did not give.
- The installed model-specific fast mode is used. The primary model, its reasoning setting, memory backend and conversation state are not switched.
- Native fallback, automatic compression, fresh memory lookup and background review are disabled for this child. Every model request is checked against the loopback route and context capacity.
- Logs are private and local. Do not publish request files, system snapshots, task context or raw model/tool output. Local execution does not make the surrounding cloud conversation private from its provider.

## Verification
Run the helper's unit tests for marker boundaries and route validation. Exercise one real `@spark` task that calls the native terminal and consumes its actual result. Check the returned parent route before/after and the local wire-model identity. Configuration alone does not prove the marker workflow.

## Pitfalls
- `/model spark` switches a conversation model; it is not this per-task convention.
- A `none` value parsed as YAML null is not a disabled reasoning override. Use the supported boolean false value and verify the effective resolver.
- Hermes treats `system_message` as one prompt section and creates a separate request client for inference. The helper pins only its fresh child's prompt cache and guards the native request-client factory. Do not replace this with a primary SDK-client patch or accept an empty guard trace as successful verification; repeat the real chat-prefix test after runtime changes.
- Do not add a competing handler for another worker's marker or modify its implementation while that setup is active elsewhere.
