# Database agent checklist

`AGENTS.md` is authoritative. Use this guide for PostgreSQL, SQLAlchemy, and Alembic work.

## Responsibilities

- Design tenant-scoped, auditable PostgreSQL schemas and safe Alembic migrations.
- Protect approval records, state transitions, snapshot/patch integrity hashes, and job idempotency.
- Keep Cloud SQL authoritative and Redis strictly ephemeral.

## Standards and architecture

- Inspect existing models, migrations, constraints, and queries before proposing schema changes.
- Use UUIDs or equivalent non-guessable identifiers, foreign keys, unique constraints, indexes, timestamps, and transactional state updates where appropriate.
- Make tenant ownership explicit in schema and query predicates. Apply database constraints for invariants the application cannot safely assume.
- Write reversible migration plans where feasible; document data backfill, lock, index-concurrently, and rollback risk before release.

## Review checklist

- Does the migration preserve existing data and have an operational rollback/forward-fix plan?
- Are organization boundaries enforced in both data model and query path?
- Are approvals append-only and tied to immutable artifact versions?
- Is job idempotency race-safe under Cloud Tasks retries?

## Common mistakes

- Assuming a schema instead of inspecting migrations.
- Storing credentials, source archives, unredacted secret material, or full raw logs in PostgreSQL.
- Treating Redis as the durable record of approvals or workflow state.
- Creating a migration without tests or a deployment review note.
