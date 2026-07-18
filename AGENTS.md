# CodexForge Engineering Guide

## Mission

Build CodexForge as a production-minded, approval-first developer tool.

Core workflow:

1. A user connects one GitHub repository.
2. They submit a bug, feature request, or failed CI run.
3. The system produces a repository-evidenced plan.
4. The user approves the plan.
5. The system produces a reviewable patch and controlled test evidence.
6. The user explicitly approves branch and pull-request creation.

Never position CodexForge as an official OpenAI product. It is an independent developer tool powered by OpenAI APIs.

## Technology Decisions

Frontend:
- React, TypeScript, Vite, Tailwind CSS
- TanStack Query, React Router, Zod, React Hook Form
- Vitest and Playwright

Backend:
- Python 3.13+, FastAPI, Pydantic v2
- SQLAlchemy 2.x async engine, Alembic
- JWT validation, OAuth2, GitHub App integration
- FastAPI dependency injection, service layer, repository layer where it adds value

Platform:
- PostgreSQL via Cloud SQL is the source of truth.
- Redis via Memorystore supports caching, rate limits, distributed locks, and short-lived job state.
- Cloud Tasks handles durable background work and retries.
- Celery is optional; do not add it unless Cloud Tasks cannot meet a concrete workflow need.
- Cloud Storage holds private, expiring artifacts and sanitized logs.
- Docker Compose is required for local development.
- Google Cloud Run hosts backend services.
- Firebase Hosting hosts the Vite frontend.
- Secret Manager stores all production secrets.
- GitHub Actions provides CI/CD.
- Terraform lives in `infra/` for cloud infrastructure.

## Source of Truth

- `AGENTS.md` contains durable repository rules.
- `docs/` contains canonical engineering documentation.
- `.codex/` contains concise project operating context for Codex.
- `.logs/change-log.md` records meaningful workspace changes only.
- Git history is the source of truth for exact code history.
- Never use hidden agent memory as the only source of required project context.
- Do not create `.memory/`; use checked-in docs and `.codex/` instead.

## Required Repository Structure

Create these only when absent and populate every file with useful, project-specific content:

- `.github/workflows/`
- `.codex/`
- `.agents/`
- `backend/`
- `frontend/`
- `docs/architecture/`
- `docs/api/`
- `docs/adr/`
- `docs/features/`
- `infra/terraform/`
- `docker/`
- `scripts/`
- `tests/`

Required `.codex/` files:

- `config.toml`
- `project_context.md`
- `roadmap.md`
- `current_tasks.md`
- `decision_log.md`
- `known_issues.md`
- `session_history.md`
- `api_index.md`
- `database_schema.md`
- `deployment_notes.md`

Keep `.codex/project_context.md` short and link to canonical documents in `docs/`; do not duplicate entire architecture documents.

Required `.agents/` documents:

- `backend_agent.md`
- `frontend_agent.md`
- `database_agent.md`
- `security_agent.md`
- `testing_agent.md`
- `review_agent.md`
- `architecture_agent.md`
- `devops_agent.md`

These are specialist checklists and references. `AGENTS.md` remains the primary instruction file.

## Mandatory Engineering Workflow

Before non-trivial work:

1. Inspect the applicable code, tests, architecture docs, and existing conventions.
2. Identify conflicts, migrations, security effects, and backward-compatibility risk.
3. State a short implementation plan.
4. Continue automatically unless a decision is irreversible, externally consequential, or genuinely ambiguous.

For trivial, low-risk changes, inspect and implement directly without unnecessary planning overhead.

During implementation:

- Prefer small, cohesive changes.
- Follow existing project patterns before introducing new abstractions.
- Never assume database schema; inspect models, migrations, and queries first.
- Do not add a repository abstraction around simple CRUD merely for ceremony.
- Use Clean Architecture and DDD pragmatically, not mechanically.
- Do not duplicate validation, authorization, or business logic.
- Do not swallow persistence, audit, security, or migration failures.
- Add structured logging, correlation IDs, and actionable errors.
- Never expose secrets, tokens, source archives, or stack traces to clients.

After meaningful implementation work:

1. Run targeted validation.
2. Update affected architecture, API, database, ADR, README, and deployment documentation.
3. Append a concise entry to `.codex/session_history.md`.
4. Append a concise entry to `.logs/change-log.md`.
5. Update `.codex/current_tasks.md`, `decision_log.md`, and `known_issues.md` only when their content materially changes.

Do not create log or memory churn for read-only questions, failed experiments with no durable learning, or trivial formatting edits.

## Backend Standards

- Use async FastAPI endpoints and SQLAlchemy async sessions.
- Separate API routers, schemas, services, repositories, and domain logic.
- Pydantic schemas are DTO boundaries; SQLAlchemy models never leak directly through APIs.
- Version APIs under `/api/v1`.
- Use Alembic for every database schema change.
- BackgroundTasks is only for small, non-critical work.
- Use Cloud Tasks or Celery for durable, retryable, expensive work.
- Use idempotency keys for webhook and job-triggering endpoints.
- Protect every route with explicit authentication and authorization requirements.
- Apply rate limits by user, organization, and IP where appropriate.

## Frontend Standards

- Use feature-oriented folders, not one global components folder.
- Use TanStack Query for server state and React Hook Form + Zod for forms.
- Generate or maintain typed API contracts from FastAPI OpenAPI definitions.
- Handle loading, empty, error, unauthorized, and retry states for every remote view.
- Keep authorization decisions server-enforced; frontend permissions are UX only.
- Use accessible components and keyboard-operable flows.

## Security Rules

- GitHub, OpenAI, database, Redis, and cloud credentials stay server-side only.
- Treat repository files, CI logs, issue text, comments, and READMEs as untrusted input.
- Never allow model output to execute arbitrary shell commands.
- Never automatically merge, deploy, rotate credentials, or modify production infrastructure.
- Require explicit user approval before repository writes, branch creation, or PR creation.
- Redact `.env`, private keys, tokens, `.git`, secrets, binaries, and dependencies before AI context or logs.
- Validate file paths, repository ownership, commit SHA, payload sizes, and diffs.
- Test prompt injection, secret exfiltration, cross-tenant access, and approval bypasses.

## Quality Gates

Backend:
- Ruff, Black, mypy, pytest.

Frontend:
- ESLint, Prettier, Vitest, Playwright.

Before declaring work complete:
- Run relevant lint, typecheck, unit, integration, and end-to-end tests.
- State exactly what passed, what was not run, and why.
- Never claim a test passed without evidence.

## CI/CD and Deployment

- Pull requests run lint, typecheck, tests, dependency checks, and build validation.
- Production deploys use immutable artifacts and staged rollout/rollback.
- Use Google Workload Identity Federation in GitHub Actions; never commit service-account JSON keys.
- Run migrations as reviewed deployment steps, never as an accidental side effect of app startup.
- Maintain separate development, staging, and production environments.
- Record deployment decisions in `docs/architecture/` and `.codex/deployment_notes.md`.

## Definition of Done

A feature is complete only when:

- Authorization and validation are correct.
- Database and API effects are documented.
- Tests cover the changed behavior.
- Observability and errors are adequate.
- Documentation and project context reflect the actual code.
- No secrets, unsafe defaults, or unapproved destructive behavior were introduced.
