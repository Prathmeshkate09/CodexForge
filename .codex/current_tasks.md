# Current tasks

## Current status

1. The full Windows verification gate, dependency audits, Alembic in-memory smoke test, and Docker Compose configuration validation have completed locally. The frontend has 15 unit tests and 2 browser tests; the backend has 29 tests, and backend test source is included in the Ruff/Black gate.
2. Container image builds/runtime and Terraform format/init/validate/plan remain unverified locally because Docker Desktop's Linux engine is not running and Terraform is not installed on the host. CI contains those checks and must validate them after the initial push.
3. API, database, deployment, and operating documentation now reflect the implemented initial migration, approval binding, local-container transport, identity-keyed rate limits, and CI supply-chain controls.

## Next product milestone

1. Implement GitHub App installation callback and server-side repository verification; activate a project only after installation/repository ownership checks.
2. Add repository snapshot/evidence persistence with strict path, size, binary, dependency, and secret redaction policy.
3. Add a Cloud Tasks receiver and controlled worker protocol that can complete a run with pinned commit/artifact evidence, but cannot execute arbitrary model text or make GitHub writes.
4. Add a reviewed structured Responses API planning flow after the evidence boundary and evaluation tests exist.

## Guardrails

- Do not enable `enable_worker_service`, GitHub write code, or `allow_public_api_invocation` in a cloud environment until their corresponding staging tests and security reviews exist.
- Do not add a real GitHub App, Firebase configuration, OpenAI key, Terraform state, or Secret Manager value to source control.
- Do not create a branch, pull request, merge, cloud deployment, or Terraform apply without separately explicit approval.
- Do not expose a new unauthenticated/public route until trusted-edge volume/IP controls and its endpoint-specific abuse model are reviewed.
