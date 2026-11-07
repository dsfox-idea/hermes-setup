# OpenAI subscription-backed inference for Honcho

Use when a standalone Honcho server needs a strong model through an existing ChatGPT subscription.

## Verify official support before making negative claims

Read https://developers.openai.com/siwc/quickstart and the open-source plan-usage guide at https://developers.openai.com/siwc/token-sharing-open-source. Eligible Plus/Pro accounts can authorize participating open-source/local personal apps without a separate paid API key. Eligibility, allowed workloads and the available model catalog must be checked live. A missing Codex adapter in `hermes proxy` does not disprove this independent official route.

Do not assume an existing Hermes/Codex OAuth token is the new application's grant. Use the official app registration, PKCE, identity validation, granted-scope checks, protected storage and renewable session lifecycle. Do not copy a shared rotating refresh token into a second independent refresher.

## Resolve the protocol mismatch explicitly

Check the installed Honcho backend. If it emits Chat Completions, an OAuth bearer alone is insufficient when the plan grant only supports Responses. Read https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference for the public endpoint, account-specific catalog, required store/stream settings and terminal completion/error contract. Never substitute undocumented ChatGPT backend endpoints or treat a model name in a documentation example as account entitlement.

Look for an existing, released compatibility gateway before writing an adapter. CLIProxyAPI is a candidate with a distinct SIWC mode, not an automatically trusted deployment. Check the pinned release's implementation, including identity validation, not just its README or ordinary Codex OAuth support. A nonce being generated is not evidence that the returned ID token's nonce/signature/audience was verified. Inspect the call path before accepting credentials. If authentication is incomplete, prefer the official maintained DevKit (https://github.com/openai/sign-in-with-chatgpt-devkit), not a home-grown OAuth flow. Keep source findings, exact release pins and open blockers in the deployment project's research notes, not this general reference.

## Prepare and exercise the gateway before authorization

1. Pin the release and inspect its configuration and request-logging call paths. Before executing a downloaded binary, compare the archive SHA-256 with both the publisher's checksum manifest and the release asset digest when available; inspect `-h` and the reported build identity rather than guessing supported flags.
2. Build an explicit local configuration: loopback listener, required local client credential, dedicated auth directory, disabled remote management/control-panel downloads, discovery, plugins and usage aggregation, and bounded retries. Reject empty or short client credentials in the settings builder; an empty authentication list can unintentionally expose the API.
3. Inspect error logging separately from ordinary request logging. In CLIProxyAPI, `request-log: false` can still permit forced error-payload files; where the installed source supports it, `server.commercial-mode: true` avoids constructing that request logger. Prove the desired effect with an error-payload canary instead of trusting the flag's name.
4. Start the real binary transiently with an empty isolated auth directory and synthetic local client key, under an outbound-denying or loopback-only sandbox. For CLIProxyAPI, use `-local-model -config <protected-runtime-file>` to select embedded catalogs during this offline probe; disable unrelated environment-based credentials. Never use the user's working grant for this test.
5. Exercise HTTP behavior: missing/wrong local keys must receive 401; a valid synthetic key must receive a successful empty model list; disabled management must return 404. Submit an unavailable-model request containing a unique synthetic canary, require a visible failure, then verify that the service remains responsive and no file contains the canary. Close HTTP error responses, terminate the process in a finally block and remove temporary credentials/configuration.
6. Record this as pre-authorization safety verification only. An empty model list, passing local tests or successful binary startup does not prove account entitlement, completed inference, token renewal or functioning memory.

## Acceptance before primary-memory activation

- Verify text, schema-constrained JSON, multi-step tool calls, streaming and completion/error propagation through the real Honcho backend. A Hello response is not the whole contract.
- Exercise renewal, quota exhaustion and revoked authorization. Do not silently fall back to a weaker model or save an empty structured result as successful memory.
- Route all reasoning stages, not only the visible chat or one deriver setting. Fix and evaluate multilingual retrieval independently of the generation model.
- Keep storage local while accurately describing the external text processing. Audit the new gateway's egress, logs, optional panel/plugin downloads and management access. Preserve the existing network restrictions until an explicit tested replacement is ready.
- Verify fresh-session Hermes turn hooks and cross-session persistence. Distinguish configured/available providers from actual message accumulation. Keep old-history import a separate authorization.
- Report implemented changes separately from the proposed route. Do not promise infallible conclusions from a stronger model or imply that plan-backed calls have unlimited allowance.

## Backend and lifecycle pitfalls

- A Pydantic model_json_schema() is not necessarily an OpenAI strict schema: default extra=ignore can omit additionalProperties, optional defaults can omit required keys, and nested objects need normalization too. The SDK parse() path already performs its strict conversion, whereas create() with a manually constructed response format may bypass it. Reuse the pinned official SDK converter at that seam and explicitly set strict=true; do not implement a second recursive schema converter. Test the actual Honcho backend, including non-strict tool-loop requests, rather than only a direct SDK example.
- Inspect exception handling for false success. Returning an empty representation after BadRequestError or repairing a LengthFinishReasonError into an empty default model can mark missing derivation as successful. Verify visible rejection and truncation with the real representation type, plus simulated authentication/quota failures. Keep simulated SDK failures distinct from real grant renewal; never revoke the working grant or intentionally exhaust the subscription merely to test error handling.
- A standalone dense top-one diagnostic and a retrieval-plus-reasoning pipeline test measure different things. Preserve a failed top-one result, record candidate recall, then verify actual source selection and exact evidence through the real memory API. Do not relabel the former as passed or present a small synthetic corpus as statistical accuracy.
- Atomic replacement of a host file can leave an existing file bind mount stale, including a missing file on macOS virtualization. Recreate only the affected read-only containers after an override/config replacement; verify the loaded backend and effective API/worker settings. Keep patches against the pinned original, test their application in isolated scratch storage and record source hashes for upgrade revalidation.
