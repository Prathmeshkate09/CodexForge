# ADR-0001: Require explicit approvals before patch and PR actions

- **Status:** Accepted
- **Date:** 2026-07-18

## Context

CodexForge handles untrusted repository content and uses AI-assisted reasoning. Bugs, provider retries, compromised integrations, UI ambiguity, or prompt injection must not turn an analysis request into a repository mutation.

## Decision

Use two separate, durable, server-enforced approvals:

1. Approve the exact evidence-backed plan before a patch-generation job starts.
2. Approve the exact reviewed patch before a constrained service creates a GitHub branch and draft PR.

Approvals bind actor, organization, action type, immutable artifact hash/version, target repository data, policy version, timestamp, correlation ID, and expiry when applicable. The provider write service revalidates the approval transactionally at execution time.

CodexForge will never automatically merge, deploy, rotate credentials, or mutate production infrastructure.

## Consequences

- Users gain predictable control and a strong audit trail.
- The product has more explicit UI states and requires robust retry/idempotency handling.
- Some workflows take an additional click, which is an intentional safety tradeoff.
