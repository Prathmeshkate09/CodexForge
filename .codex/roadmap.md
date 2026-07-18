# Roadmap

## Milestone 0 — Local approval foundation (implemented; local validation complete)

- Repository rules, specialist checklists, docs, Docker/CI/Terraform baseline.
- React approval UI with Firebase Auth configuration guard and local development-token mode.
- Async FastAPI state, Alembic initial migration, JWT validation, rate limiting, audit, and idempotency.
- Exact-run approval binding with pinned commit and immutable artifact digest.
- Identity-keyed authenticated limits, full-SHA CI action pins, dependency audits, and local-container API transport safety.

## Milestone 1 — Verified read-only repository evidence

- GitHub App installation callback, repository ownership verification, and active connection state.
- Read-only commit pinning, bounded file selection, secret/binary/dependency exclusions, redaction, snapshot hashes, and private artifact metadata.
- Organization/membership/role model before multi-user tenant release.

## Milestone 2 — Controlled plan and patch work

- Cloud Tasks receiver with task identity validation and durable idempotency.
- Server-mediated structured Responses API planning flow, call correlation, evaluations, budgets, and sanitized artifacts.
- Isolated patch/check runner with allowlisted profiles, resource/network limits, and cancellation.

## Milestone 3 — GitHub review delivery

- Separate final approval bound to exact patch/target data.
- Constrained branch/draft-PR service with transactional revalidation, audit, and retry handling.
- Never merge, deploy, rotate credentials, or alter infrastructure automatically.

## Milestone 4 — Production readiness

- Reviewed development/staging/production Terraform environments, Firebase configuration, observability, backup/restore drills, load tests for 100–200 concurrent users, and staged Cloud Run rollout.
- Security review covering prompt injection, secret exfiltration, tenant isolation, approval bypass, OAuth/webhook/task forgery, and runner escape.
