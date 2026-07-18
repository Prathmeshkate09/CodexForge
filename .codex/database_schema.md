# Database schema index

Cloud SQL PostgreSQL is the intended production source of truth. `backend/alembic/versions/20260718_0001_initial_workflow.py` is the current initial schema migration. The local test suite uses SQLite-compatible metadata where practical; production schema review must use PostgreSQL before deployment.

| Table | Current purpose | Security and integrity rules |
| --- | --- | --- |
| `repositories` | Caller-owned repository metadata and connection state. | `owner_subject` scopes every read; manually created records are `pending` and are not proof of GitHub access. |
| `work_items` | Bug, feature, or failed-CI workflow root. | References a repository; status transitions occur through the service layer. |
| `work_runs` | Plan/patch/check/PR attempts for a work item. | `is_current` plus a partial unique index permit one current attempt per work item/stage. `base_commit_sha` and `approval_artifact_sha256` are immutable approval material after successful worker completion. |
| `approvals` | Explicit plan or PR decision for one run. | Unique per `(run_id, action)` and snapshots non-null pinned commit SHA plus artifact SHA-256. An approval cannot be reused by a retry. |
| `audit_events` | Security/business audit trail. | Stores actor, action, entity, correlation ID, and safe structured detail; no credentials or source archives. |
| `idempotency_records` | Durable deduplication of create requests. | Unique by actor/scope/key; expiry permits a fresh reservation rather than an indefinite replay. |

Not modeled yet: organizations/memberships, GitHub App installations, verified repository IDs, snapshots/evidence, plans/patches/artifacts, durable task records, artifact access grants, and retention policy metadata. Add a reviewed Alembic migration for each change; never infer schema from this document alone.
