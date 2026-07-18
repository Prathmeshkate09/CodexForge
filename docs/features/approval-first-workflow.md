# Approval-first workflow

## User goal

An authorized developer wants help with a bug, feature, or failed CI run without granting an AI system open-ended access to mutate their repository.

## Happy path

1. **Connect repository.** The user installs the CodexForge GitHub App and selects a repository. The API records installation/repository metadata only after server-side ownership validation.
2. **Create work request.** The user describes a bug, feature, or failed CI run and selects an allowed repository/ref. CodexForge pins the exact commit SHA.
3. **Collect evidence.** A read-only collector gathers relevant, bounded, redacted evidence. It does not collect secret files, `.git`, binaries, dependencies, or arbitrary source archives.
4. **Review plan.** CodexForge presents affected areas, evidence references, assumptions, risks, proposed tests, and an explicit scope. This action has no repository write.
5. **Approve plan.** The user explicitly approves the exact plan version. CodexForge records actor, organization, artifact hash, time, policy version, and correlation ID.
6. **Review patch and checks.** A controlled worker produces a patch and sanitized test evidence in an isolated workspace. The user sees changed files, diff, command profile/check results, skipped checks, and unresolved risks.
7. **Approve draft PR creation.** The user explicitly approves the exact patch plus base branch/PR content. The server revalidates approval and creates one branch and draft PR through the GitHub App.
8. **Human review and merge.** The repository’s normal owners review, change, merge, and deploy through their existing process. CodexForge does not merge or deploy automatically.

## Decision points

| Decision | Actor | Server-enforced condition |
| --- | --- | --- |
| Repository connection | Authorized organization user | GitHub installation/repository ownership matches tenant. |
| Plan approval | Authorized user | Exact current plan run has succeeded and its pinned commit/artifact digest are immutable and present. |
| Patch creation | Worker | Exact approved plan run, commit SHA, and artifact SHA-256 still match under the transaction boundary. |
| PR approval | Authorized user | Exact current PR run has succeeded and its pinned commit/artifact digest are immutable and present. |
| Branch/draft PR write | Constrained GitHub service | Transactional revalidation immediately before provider call; no earlier attempt's approval is reusable. |

## Required plan content

A repository-evidenced plan includes:

- pinned repository and commit identity;
- selected evidence references and redaction notice;
- problem statement, assumptions, and non-goals;
- affected files/components and intended changes;
- security, compatibility, data/migration, and rollback considerations;
- proposed test/check plan and any expected limitations;
- an explicit request for human approval before patch generation.

## Required patch review content

- exact patch hash and file manifest;
- sanitized unified diff or authorized per-file diff view;
- controlled test/check commands or profiles, result status, duration, and truncated/redacted output;
- skipped checks and reason; known risks; rollback/revert path;
- explicit action text for draft PR creation, including base branch and PR metadata.

## Cancellation and failure

Users can cancel non-terminal work requests. Workers check cancellation before expensive stages and before GitHub actions. A provider timeout, validation failure, redaction failure, policy violation, or unsafe workspace result moves the request to `FAILED` with a safe reason and correlation ID; it never falls back to an unreviewed mutation.

## Non-goals

- Autonomous merge, production deployment, credential rotation, or infrastructure change.
- Arbitrary shell access based on model output.
- Sending an entire repository, raw secret file, or unrestricted CI log history to a model.
- Replacing human code review or repository branch-protection policies.
