# CodexForge context

CodexForge is an independent, approval-first developer tool—not an official OpenAI product. It helps a developer turn a GitHub issue, feature request, or failed CI signal into a repository-evidenced plan, then only after explicit approval a reviewable patch and controlled validation evidence. A second approval is required before any branch or draft PR action.

Current phase: local authenticated workflow foundation. The implemented API persists project metadata, work items, runs, approvals, audit events, and idempotency records. Manual projects are deliberately `pending` until a GitHub App callback verifies access; this blocks work-item creation. No GitHub App callback, repository evidence collector, Cloud Tasks receiver, worker executor, model run, branch/PR creation, or deployed environment exists yet.

Key invariants:

- no route performs a GitHub write, model invocation, shell execution, merge, deployment, or automatic migration;
- every approval is bound to the exact current run, pinned commit SHA, and immutable artifact SHA-256; resets/retries supersede old approval-capable runs;
- browser credentials are Firebase/OIDC ID tokens only; GitHub, OpenAI, database, Redis, and cloud credentials remain server-side.

Canonical references:

- [System architecture](../docs/architecture/system-architecture.md)
- [Security model](../docs/architecture/security-model.md)
- [Approval-first workflow](../docs/features/approval-first-workflow.md)
- [Implemented API contract](../docs/api/api-overview.md)
- [Database schema index](database_schema.md)
- [Architecture decisions](../docs/adr/)

Read `AGENTS.md`, this file, `.codex/current_tasks.md`, and the latest `.codex/session_history.md` before non-trivial work.
