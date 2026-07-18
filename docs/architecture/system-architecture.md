# System architecture

## Purpose and implementation status

CodexForge is an independent developer tool powered by OpenAI APIs. It is intentionally approval-first: analysis, patch generation, and GitHub delivery are distinct stages with server-enforced human decisions. It is not an official OpenAI product, and it never automatically merges, deploys, rotates credentials, changes infrastructure, or executes model-generated shell text.

The current codebase implements the local authenticated workflow foundation: FastAPI JWT verification, subject-scoped data access, PostgreSQL/Alembic persistence, idempotency, audit events, explicit approval recording, and a Firebase-aware React client. It does **not** yet implement GitHub App verification, evidence collection, model invocation, Cloud Tasks dispatch, isolated execution, artifacts, webhooks/SSE, or GitHub writes. Those capabilities must remain disabled until their boundaries are implemented and tested.

## Target topology

```text
Browser (Firebase Hosting SPA)
  | Firebase ID token + HTTPS
  v
FastAPI API (Cloud Run)
  |- authorization, rate limits, audit, workflow state
  |- GitHub App boundary (future)
  |- model orchestration boundary (future)
  v                 v                 v
Cloud SQL       Memorystore Redis   Cloud Tasks
source of truth ephemeral limits    durable dispatch
                                      |
                                      v
                         Controlled worker (future, Cloud Run)
                           |- redacted evidence / structured model tools
                           |- isolated patch/check runner
                           `- private GCS artifacts
                                      |
                                      v
                              GitHub API / OpenAI API
```

The browser never receives GitHub App, OpenAI, database, Redis, Cloud Tasks, Cloud Storage, or cloud service-account credentials. Firebase web configuration is browser-visible by design, but it is not a server credential and must be restricted by Firebase/Google Cloud configuration.

## Approval-first data model

The initial migration defines `repositories`, `work_items`, `work_runs`, `approvals`, `audit_events`, and `idempotency_records`. Local ownership is currently derived from the verified JWT subject (`owner_subject`); organization/membership modeling is required before a multi-user tenant launch.

The work-item state graph is:

```text
DRAFT -> SNAPSHOT_PINNED -> PLAN_AWAITING_APPROVAL -> PATCH_READY
      -> CHECKS_QUEUED -> CHECKS_RUNNING -> REVIEW_READY
      -> PR_AWAITING_APPROVAL -> COMPLETE

Any permitted non-terminal state may transition to FAILED or CANCELLED.
```

The current API only creates the initial queued plan run and records approvals once a future worker has completed a valid run. It does not move work items through the full graph by itself.

Approval is a capability check, not a work-item boolean:

1. An approval belongs to one exact `work_runs` record.
2. That run must be the current attempt for its work item/stage, must have succeeded, and must carry a valid pinned commit SHA plus immutable artifact SHA-256.
3. The stored approval snapshots the same commit/digest.
4. A guarded worker transition requires the exact run ID and compares every value under the transaction boundary.
5. Reset/retry operations supersede prior approval-capable attempts, making stale approvals fail closed.

See [ADR-0004](../adr/0004-immutable-run-bound-approvals.md) and the [workflow feature specification](../features/approval-first-workflow.md).

## Trust boundaries

| Boundary | Required control |
| --- | --- |
| Browser -> API | Firebase/OIDC issuer, audience, signature, expiry validation; explicit CORS allowlist; rate limits; safe error handling. |
| API -> GitHub | Future GitHub App installation verification, owner/repository/commit validation, short-lived server-side tokens, approval revalidation immediately before a write. |
| API/worker -> model | Future server-mediated Responses API with strict tool schemas, redacted/bounded evidence, call correlation, safety identifier, and no shell/GitHub/cloud capability. |
| Worker -> workspace | Future ephemeral isolation, allowed checkout/ref, command profile, resource/network limits, cancellation checks, artifact redaction. |
| Service -> cloud | Least-privilege per-service account, Secret Manager, private data paths, immutable artifacts, audit logs. |

## Capacity baseline

The initial production target is 100–200 concurrent interactive users, not unlimited concurrent repository jobs. The API is stateless and has a Cloud Run maximum instance guardrail; Redis absorbs rate-limit/lock activity, Cloud SQL remains authoritative, and Cloud Tasks bounds worker delivery. Initial Terraform values cap the queue at 10 concurrent dispatches and 2 dispatches/second and cap API instances at 10. These are starting safety limits, not load-test proof.

Before production, validate Cloud SQL connection pooling, authenticated-subject and future tenant/project rate limits, queue saturation, model/provider budgets, artifact size limits, test-run duration, and degraded behavior under the expected concurrent load. The API deliberately does not apply a request-client IP bucket to authenticated traffic: Cloud Run and local Nginx can present one shared proxy address and turn it into a global throttle. Apply public IP/volumetric protection at the trusted edge (for example, Cloud Armor) before exposing unauthenticated endpoints; add an application-level forwarded-IP policy only when a concrete trusted-proxy contract is deployed and tested.
