# API index

The canonical public contract is [docs/api/api-overview.md](../docs/api/api-overview.md). All product routes are versioned under `/api/v1` except unauthenticated `/health`.

| Area | Route | Method | Current behavior |
| --- | --- | --- | --- |
| Health | `/health`, `/api/v1/health` | `GET` | Implemented unauthenticated liveness responses. |
| Local dev identity | `/api/v1/auth/dev/token` | `POST` | Implemented but hidden and disabled unless explicitly enabled in a local/test environment. |
| Projects | `/api/v1/projects` | `GET`, `POST` | Implemented bearer-scoped list/create. Manual projects remain `pending` until a future GitHub App verification hook. |
| Work items | `/api/v1/work-items` | `GET`, `POST` | Implemented bearer-scoped list/create; creation is blocked unless the project is `active`. |
| Runs | `/api/v1/runs/{run_id}` | `GET` | Implemented ownership-scoped run view. |
| Plan approval | `/api/v1/runs/{run_id}/plan-approval` | `POST` | Implemented exact-current-run approval/rejection recording; no patch job is dispatched yet. |
| PR approval | `/api/v1/runs/{run_id}/pull-request-approval` | `POST` | Implemented exact-current-run approval recording; no GitHub write is dispatched. |

Not implemented: `/me`, GitHub OAuth/App callback, webhook ingestion, repository evidence, artifacts, checks, SSE, model-run jobs, branch creation, and pull-request creation.
