# Decision log

| Date | Decision | Rationale | Canonical record |
| --- | --- | --- | --- |
| 2026-07-18 | Use an approval-first workflow for all repository mutations. | It prevents a model, job retry, or user-interface ambiguity from writing to a repository without a human decision. | [ADR-0001](../docs/adr/0001-approval-first-repository-mutations.md) |
| 2026-07-18 | Host the Vite SPA on Firebase Hosting and FastAPI services on Cloud Run. | It keeps static delivery separate from stateless APIs and controlled workers. | [ADR-0002](../docs/adr/0002-google-cloud-runtime-and-data-platform.md) |
| 2026-07-18 | Use Cloud SQL PostgreSQL as the system of record, Memorystore Redis for ephemeral coordination, Cloud Tasks for durable jobs, and GCS for private artifacts. | Each state type has clear durability and retention semantics. | [ADR-0002](../docs/adr/0002-google-cloud-runtime-and-data-platform.md) |
| 2026-07-18 | Use a server-mediated Responses API tool loop rather than model-issued shell commands. | The server can validate input, restrict tools, redact context, retain call correlation, and enforce approvals. | [ADR-0003](../docs/adr/0003-server-mediated-openai-tool-orchestration.md) |
| 2026-07-18 | Bind each plan/PR approval to the exact current run, pinned commit SHA, and immutable artifact SHA-256. | Reset/retry attempts must never reuse an earlier approval or immutable evidence. | [ADR-0004](../docs/adr/0004-immutable-run-bound-approvals.md) |
| 2026-07-18 | Key authenticated API limits by verified JWT subject, not proxy-derived IP. | Shared Cloud Run/Nginx proxy addresses would turn an IP bucket into a deployment-wide throttle; forwarded headers require a separate trust contract. | [ADR-0005](../docs/adr/0005-authenticated-rate-limit-identity-keying.md) |
| 2026-07-18 | Pin CI actions to reviewed full commit SHAs and use Dependabot for update proposals. | A mutable action tag in a job with cloud identity permissions is an avoidable supply-chain risk. | [Deployment and operations](../docs/architecture/deployment-and-operations.md) |
