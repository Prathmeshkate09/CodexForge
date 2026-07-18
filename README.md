# CodexForge

CodexForge is an independent, approval-first developer tool powered by OpenAI APIs. It turns a GitHub issue, feature request, or failed CI signal into a repository-evidenced plan, then—after explicit approval—a reviewable patch and controlled test evidence. A separate explicit approval is required before a branch or draft pull request can be created.

It is not an official OpenAI product.

## What is implemented now

This first vertical slice is safe to run locally:

- a React/Vite frontend with Firebase Google sign-in support and a local development-token mode;
- an async FastAPI API with JWT verification, authorization-scoped repository/work-item access, correlation IDs, rate limiting, and safe errors;
- PostgreSQL persistence and an Alembic initial migration for repositories, work items, workflow runs, approvals, audit events, and idempotency records;
- an approval state machine in which an approval is bound to the exact current run, pinned commit SHA, and immutable artifact digest; and
- Docker, CI, Firebase Hosting, Terraform, Cloud Run, Cloud SQL, Redis, Cloud Tasks, Secret Manager, and GitHub Actions/WIF foundations.

Repository access is deliberately not enabled yet. A manually entered repository remains `pending` until a future GitHub App verification callback activates it, and pending projects cannot create work items. No current route invokes a model, executes shell commands, writes to GitHub, creates a branch, opens a PR, merges, deploys, or runs migrations automatically at startup.

## Product boundary

1. A user connects one GitHub repository through a GitHub App.
2. CodexForge pins a commit, collects bounded/redacted evidence, and produces a plan.
3. The user approves that exact plan before patch generation.
4. The user reviews the patch and controlled check evidence.
5. The user explicitly approves a constrained branch/draft-PR action.

Repository files, CI output, issue text, comments, and model output are untrusted input. Read the [system architecture](docs/architecture/system-architecture.md) and [security model](docs/architecture/security-model.md) before changing GitHub, model, runner, or cloud integration code.

## Technology overview

- Frontend: React, TypeScript, Vite, Tailwind CSS, TanStack Query, React Router, Zod, React Hook Form, Firebase Auth.
- Backend: Python 3.13+, FastAPI, Pydantic v2, SQLAlchemy async, Alembic, OAuth2/JWT.
- Data/jobs: PostgreSQL, Redis, Cloud Tasks, Cloud Storage.
- Hosting: Firebase Hosting for the SPA; Cloud Run for API and controlled workers.
- Infrastructure: Terraform, Docker Compose, GitHub Actions with Workload Identity Federation.

## Local development

Prerequisites: Node.js 22, Python 3.13+, `uv`, Docker Desktop or Docker Engine, and Git.

1. Create ignored local configuration files and replace the marked values. Keep the PostgreSQL password in the root and backend examples aligned.

   ```powershell
   Copy-Item .env.example .env
   Copy-Item backend/.env.example backend/.env
   Copy-Item frontend/.env.example frontend/.env.local
   ```

2. Start only the local dependencies, install the locked backend graph, and apply the reviewed migration manually.

   ```powershell
   docker compose --env-file .env up -d postgres redis
   Push-Location backend
   uv sync --locked --all-groups
   uv run alembic upgrade head
   uv run uvicorn app.main:app --reload --port 8000
   ```

3. In another terminal, configure Firebase Auth in `frontend/.env.local` (recommended) or set an explicitly issued short-lived local development token. Then start the frontend.

   ```powershell
   Push-Location frontend
   npm ci
   npm run dev
   ```

The local frontend defaults to `/api/v1`, which Vite proxies to `http://127.0.0.1:8000`. Firebase configuration is public browser configuration, but GitHub, OpenAI, database, Redis, and cloud credentials must remain server-side. See [frontend setup](frontend/README.md) and [backend setup](backend/README.md) for the authentication details.

To test the container images after the migration is applied, use `docker compose --env-file .env up --build backend frontend`. Application startup intentionally does not run Alembic.

## Verification

Run the local quality gate after dependencies are installed:

```powershell
./scripts/verify.ps1
```

On macOS/Linux, run `sh scripts/verify.sh`. The gate runs frontend formatting/lint/type/unit/build/browser checks, backend Ruff/Black/mypy/pytest, and Docker Compose configuration validation. See the final task report or CI run for the exact checks that completed on a given machine.

## Production deployment posture

No cloud resources are provisioned by this repository. The Terraform release workflow creates a reviewed plan only; it never applies Terraform or deploys a revision.

For Firebase Hosting to reach Cloud Run in staging/production, build the SPA with an explicit HTTPS `VITE_API_BASE_URL` pointing to the API service and configure that Firebase origin in `cors_allowed_origins`. After staging verification, Terraform may deliberately grant public Cloud Run transport invocation (`allow_public_api_invocation = true`) because browsers cannot present Google IAM identities. FastAPI still validates every protected request's Firebase/OIDC bearer token. The detailed sequence is in [deployment and operations](docs/architecture/deployment-and-operations.md).

## Repository map

| Path | Purpose |
| --- | --- |
| `frontend/` | Vite SPA and browser-facing approval flows. |
| `backend/` | FastAPI API, domain services, Alembic migration, and data access. |
| `docs/` | Canonical architecture, API, feature, and ADR documentation. |
| `infra/terraform/` | Reviewable Google Cloud baseline; no environment is provisioned by default. |
| `docker/` | Container definitions. |
| `scripts/` | Cross-platform local quality gates. |

## Canonical documentation

- [Architecture](docs/architecture/system-architecture.md)
- [Approval-first workflow](docs/features/approval-first-workflow.md)
- [Live API contract](docs/api/api-overview.md)
- [Cloud deployment guide](docs/architecture/deployment-and-operations.md)
- [Architecture decisions](docs/adr/)
