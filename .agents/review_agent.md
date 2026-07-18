# Review agent checklist

`AGENTS.md` is authoritative. Use this guide for implementation and patch review.

## Responsibilities

- Evaluate correctness, scope, authorization, data safety, operability, test quality, and documentation alignment.
- Distinguish evidence from assumptions and flag behavior that has not been executed or independently verified.
- Keep proposed code changes reviewable and bounded to an approved work request.

## Review checklist

- Does the change honor the approval state machine and avoid implicit repository/cloud mutations?
- Does authorization cover organization, repository installation, actor role, and exact artifact version?
- Are secret redaction, input validation, errors, logs, retries, and idempotency handled deliberately?
- Does the patch include focused tests, migration/API docs where relevant, and accurate deployment notes?
- Is any abstraction justified by complexity rather than framework preference?

## Common mistakes

- Approving a broad refactor hidden inside a feature patch.
- Missing a changed trust boundary or assuming a UI confirmation is a server approval.
- Suggesting automatic merge/deploy, arbitrary shell execution, or raw model output consumption.
- Treating a passing formatter as a functional/security review.
