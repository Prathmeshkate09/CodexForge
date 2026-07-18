# ADR-0004: Bind approvals to immutable current runs

- **Status:** Accepted
- **Date:** 2026-07-18

## Context

A work item can be reset or retried after a plan or PR run has been approved. A guard that checks only work-item ID and approval action would allow an old decision to authorize different evidence or a later attempt. That is an approval bypass.

## Decision

Persist approvals against one exact `work_runs` row. Each decision snapshots the run's pinned commit SHA and immutable artifact SHA-256. The schema permits one current run per `(work_item_id, stage)` through a partial unique index. Worker-only transition methods require the exact authorizing run ID, expected stage, current-attempt flag, successful status, approved decision, and matching commit/digest before transitioning to `PATCH_READY` or `COMPLETE`.

Resetting to `DRAFT` supersedes approval-capable current runs. Queuing a retry supersedes the earlier current run. Expired idempotency records are safely reused as fresh reservations while preserving the unique lock.

## Consequences

- Delayed jobs and stale browser actions fail closed instead of borrowing a previous approval.
- Worker completion must persist valid immutable approval material before presenting an approval UI.
- The initial migration includes `work_runs.is_current`, `work_runs.approval_artifact_sha256`, and non-null approval snapshots; future migrations must preserve this invariant.
