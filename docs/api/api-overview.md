# API overview

## Status

The routes in the first table are implemented by the FastAPI service and described by its OpenAPI document. GitHub App callbacks, repository evidence collection, model orchestration, task receivers, artifacts, webhooks, SSE, and GitHub write routes are not implemented and must not be inferred from the user interface.

## Conventions

- Base path: `/api/v1`.
- JSON request and response fields use `snake_case`.
- Every protected route requires `Authorization: Bearer <JWT>` and resolves ownership from the verified subject; the client never supplies a trusted tenant identifier.
- `POST /projects` and `POST /work-items` require a 16–128 character `Idempotency-Key` header. If an optional body `idempotency_key` is sent, it must match the header.
- Responses expose `X-Request-ID` and `X-Correlation-ID`; safe errors omit stack traces, tokens, secrets, source archives, and raw provider failures.
- In development only, `/auth/dev/token` is hidden from OpenAPI and requires both `CODEXFORGE_ALLOW_DEV_IDENTITY=true` and an `X-Dev-Identity-Key`. It is rejected outside development/test configuration.

## Implemented routes

| Route | Method | Auth | Behavior |
| --- | --- | --- | --- |
| `/health` | `GET` | No | Service liveness response. |
| `/api/v1/health` | `GET` | No | Versioned API health response. |
| `/api/v1/auth/dev/token` | `POST` | Local-only secret header | Issues a 15-minute development JWT when explicitly enabled. |
| `/api/v1/projects` | `GET` | Bearer | Lists only projects owned by the caller subject. |
| `/api/v1/projects` | `POST` | Bearer + idempotency | Registers a repository as `pending`; it does not establish GitHub access. |
| `/api/v1/work-items` | `GET` | Bearer | Lists only work items whose project belongs to the caller. `project_id` is optional. |
| `/api/v1/work-items` | `POST` | Bearer + idempotency | Creates a work item only for an `active` verified project and creates its initial plan run. |
| `/api/v1/runs/{run_id}` | `GET` | Bearer | Returns one caller-owned run, its work item, approval gates, and safe audit timeline. |
| `/api/v1/runs/{run_id}/plan-approval` | `POST` | Bearer | Records approval/rejection only for a completed, current plan run with immutable evidence. |
| `/api/v1/runs/{run_id}/pull-request-approval` | `POST` | Bearer | Records the final approval only for a completed, current PR run with immutable evidence. It does not create a branch or PR. |

## Approval contract

An approval is not a generic work-item flag. It is stored against one exact current `work_run` with its pinned repository commit SHA and immutable artifact SHA-256. Worker-only service methods revalidate all of the following immediately before the protected transition:

- matching run ID, work item, expected stage, and `is_current` flag;
- successful run status and approved decision;
- matching pinned commit SHA and artifact digest.

Resetting a work item or queuing a retry supersedes approval-capable runs. A stale browser request, delayed worker, or prior approval therefore cannot authorize a later plan, patch, branch, or draft PR.

## Error contract

| HTTP status | Meaning |
| --- | --- |
| `400` | Invalid syntax or request semantics. |
| `401` | Missing, malformed, expired, or invalid bearer credential. |
| `403` | Authenticated but not permitted for the action. |
| `404` | The resource is not visible to this caller. |
| `409` | State, approval, or idempotency conflict; refresh before retrying. |
| `422` | Well-formed input rejected by a business rule. |
| `429` | Authenticated-subject rate limit exceeded; retry using `Retry-After`. |
| `500` | Sanitized unexpected server failure; correlation/request IDs are safe to share with support. |

## Planned, not exposed

The following contracts remain future work: GitHub App installation callback, signed GitHub webhook, evidence and snapshot APIs, model-run dispatch, controlled check evidence, artifact retrieval, SSE progress, and constrained GitHub branch/draft-PR creation. Each needs an authorization, idempotency, audit, and threat-model review before exposure.
