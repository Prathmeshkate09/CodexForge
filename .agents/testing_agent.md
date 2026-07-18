# Testing agent checklist

`AGENTS.md` is authoritative. Use this guide for validation design and execution.

## Responsibilities

- Maintain a layered quality strategy: static analysis, unit tests, API/service integration tests, migration checks, and critical Playwright flows.
- Make controlled test evidence reproducible, scoped, sanitized, and clearly labeled as pass, fail, or not run.
- Build adversarial coverage for approval and repository-safety boundaries.

## Standards and architecture

- Use pytest for backend behavior, Vitest for frontend behavior, and Playwright for end-to-end approval journeys.
- Tests must use isolated tenants, disposable databases, fake GitHub/OpenAI services, and no live credentials by default.
- Assert both positive and negative authorization paths, idempotent retries, state-machine invalid transitions, race handling, and redaction.
- Keep test fixtures realistic but synthetic; never commit secrets or copied private repository material.

## Review checklist

- Does the test prove an unapproved plan cannot create a patch and an unapproved patch cannot create a branch/PR?
- Are errors, partial failures, Cloud Tasks retries, expired approvals, and cancellation tested?
- Do tests validate server enforcement rather than only disabled UI controls?
- Is any skipped/blocked validation reported honestly with an actionable reason?

## Common mistakes

- Treating a mock invocation as evidence an external side effect is safe.
- Testing only happy paths or making tests depend on shared cloud state.
- Recording raw tokens, unredacted model transcripts, or repository source in snapshots.
- Claiming a test passed without command output or CI evidence.
