# Backend agent checklist

`AGENTS.md` is authoritative. Use this guide when changing FastAPI services.

## Responsibilities

- Design versioned `/api/v1` routes, Pydantic v2 DTOs, services, persistence boundaries, and durable job hand-off.
- Preserve tenant isolation, approval state integrity, idempotency, auditability, and safe error handling.
- Maintain OpenAPI descriptions and API documentation with implementation changes.

## Standards and architecture

- Use async FastAPI endpoints and SQLAlchemy async sessions. Keep ORM models inside the persistence layer; expose DTOs only.
- Keep routers thin. Put authorization and orchestration in services; use repositories for non-trivial persistence queries, not simple ceremony.
- Enforce every state transition transactionally and verify actor, organization, current state, snapshot, and approval scope.
- Use correlation IDs, structured logs, problem-style safe errors, timeouts, pagination, payload limits, and idempotency keys where requests trigger work.

## Review checklist

- Is each route authenticated and tenant-authorized before returning or mutating data?
- Are model calls, GitHub calls, and queue work behind explicit service boundaries and timeouts?
- Does a migration, schema DTO, API reference, and test change accompany persistent/API behavior changes?
- Can a retry accidentally regenerate a patch, create two branches, or skip an approval?

## Common mistakes

- Returning SQLAlchemy objects or stack traces directly from routes.
- Using `BackgroundTasks` for durable work or skipping Cloud Tasks idempotency.
- Trusting client-selected organization IDs, repository paths, commit SHAs, or approval flags.
- Running migrations at application startup.
