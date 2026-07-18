# Security model

## Security objectives

CodexForge must ensure that one user or future organization cannot access another party's repository evidence, plans, patches, approvals, artifacts, or credentials. It must ensure that a model, a task retry, an untrusted repository file, a CI log, or a forged request cannot cause an unapproved repository write, secret disclosure, or cloud mutation.

The current initial slice scopes records by one verified JWT subject (`owner_subject`). It is not a multi-user tenant implementation: organization, membership, and role tables are required before that launch. This limitation does not relax the requirement that every implemented lookup remains subject-scoped.

## Assets and trust assumptions

| Asset | Classification | Protection |
| --- | --- | --- |
| GitHub App private key, webhook secret, and installation tokens | Highly sensitive | Secret Manager; server-only, short-lived token minting, no browser/database plaintext. |
| OpenAI credential | Highly sensitive | Secret Manager; API/worker only, never logged or embedded in frontend. |
| Repository content and CI logs | Untrusted, potentially confidential | Size/path/type allowlists, redaction, private GCS, tenant authorization. |
| Approval records and audit events | Security-critical | PostgreSQL transaction, immutable version binding, append-only audit events. |
| Patches and test artifacts | Confidential and untrusted | Integrity hashes, private GCS, expiration, authorized retrieval. |
| Model output | Untrusted | Strict schema validation and server-controlled capability checks. |

## Primary threats and controls

### Prompt injection in repository content

Files, README text, issues, comments, and CI logs can contain instructions aimed at a model. The collector labels this material as untrusted evidence, minimizes it, redacts it, and sends it only in bounded structured fields. The worker never treats repository/model text as authority to disclose data, call a new tool, execute a shell command, change policies, or write to GitHub.

### Secret exfiltration

Before model context, storage, logs, and UI rendering, inspect paths and content for `.env` files, private keys, tokens, credentials, certificates, connection strings, binaries, and oversized files. Exclude first, redact second, and fail closed when redaction cannot establish a safe result. Do not rely on a model to decide whether content is secret.

### Approval bypass and confused deputy

Approval is recorded server-side against an exact current run and snapshots its pinned commit plus immutable artifact SHA-256. The guarded transition rechecks run ID, stage, current-attempt flag, successful status, decision, commit, and artifact under transaction/lock. Reset/retry supersedes approval-capable runs. A future GitHub write service must repeat that recheck immediately before a branch or draft PR action. Frontend buttons, task payloads, webhooks, model output, or an old approval cannot authorize a write.

### Cross-tenant access

Validate issuer, audience, signature, expiration, and subject for identity tokens. Derive current ownership from the authenticated principal and apply it in every service/repository query. Before multi-user release, add server-side organization membership/role resolution and tests for tenant substitution. In all phases, test ID substitution, stale session replay, artifact URL reuse, and GitHub installation mismatch.

### Rate limiting and proxy handling

The current protected routes consume a Redis-backed bucket keyed by the verified JWT subject. They intentionally do not derive an end-user IP from `request.client` or `X-Forwarded-For`: Cloud Run and local Nginx can collapse many users behind a shared proxy address, and forwarded headers are spoofable until a specific trusted-proxy policy exists. Protect any future unauthenticated/public entry point at a trusted edge and use provider-specific signature and delivery controls for GitHub webhooks. Add organization/project quotas only after server-side membership and ownership modeling exists. See [ADR-0005](../adr/0005-authenticated-rate-limit-identity-keying.md).

### Arbitrary execution and supply-chain abuse

Model output cannot generate free-form shell execution. Controlled test runner profiles are selected by server policy and run in short-lived isolated workspaces with file, process, CPU, memory, time, output, and network constraints. Do not run `npm install`, package scripts, Docker builds, or CI configuration from an untrusted target repository without a separately reviewed runner policy.

Repository CI action references are pinned to reviewed full commit SHAs. Dependabot proposes dependency and action updates as normal pull requests; each update remains subject to review and the same CI quality gates before its pin changes.

### Webhook, OAuth, and task forgery

Verify GitHub webhook signatures and delivery IDs; store idempotency before durable enqueue. Use OAuth state, PKCE where applicable, strict callback allowlists, and token verification. Authenticate Cloud Tasks delivery with service identity/OIDC and reject untrusted direct worker requests.

## OpenAI-specific safeguards

- Keep the API key server-side and use project/service level usage limits.
- Use a hashed authenticated subject as `safety_identifier`, not an email address or raw provider subject.
- Use the Responses API with structured function tools. Preserve `call_id` and prior model output across tool-result continuations.
- Strictly validate tool arguments with schemas and enforce capability/tenant checks outside the model.
- Retain only sanitized, minimally necessary model input/output metadata needed for debugging and audit; apply private retention and access controls.
- Test prompt injection, data exfiltration, unsafe tool invocation, approval bypass, and cross-tenant behavior before a release. Add moderation and adversarial evaluation where model inputs or outputs create abuse risk.
- Keep a human in the loop before patch production and again before GitHub branch/PR creation. A model cannot approve its own work.

## Logging and incident response

Use structured logging with correlation IDs, actor/tenant identifiers in safe pseudonymous form, request route, operation result, and redaction status. Do not log credentials, authorization headers, raw repository archives, full prompts, source files, private artifacts, or stack traces returned to clients.

Security events include token validation failure, webhook verification failure, authorization denial, path-policy rejection, redaction failure, invalid transition, task replay, GitHub write attempt, and artifact retrieval denial. Escalate suspected secret exposure by revoking/rotating the affected secret through the approved incident process, invalidating artifact links, preserving audit evidence, and investigating scope without copying secrets into tickets.

## Security test minimums

1. A plan cannot generate a patch before the exact current plan run, pinned commit, and artifact digest are approved.
2. A retry/reset or artifact mismatch cannot reuse a prior plan/PR approval.
3. A patch cannot create a branch/PR before the exact current patch/PR evidence is approved.
4. A repeated task/webhook cannot duplicate a patch or PR.
5. Users cannot retrieve another party's work request, artifact, or SSE stream.
6. Repository content that asks for secrets/tools does not expand model capabilities.
7. `.env`, private key, token, binary, traversal, and oversized inputs are excluded/redacted and never reach model/log output.
8. Invalid GitHub signature, OAuth state, task identity, commit SHA, and repository installation ownership are rejected.

See [the system architecture](system-architecture.md) and [ADR-0003](../adr/0003-server-mediated-openai-tool-orchestration.md).
