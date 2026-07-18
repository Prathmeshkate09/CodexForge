# Known issues and constraints

## Deliberate product constraints

- The GitHub App installation/callback is not implemented. Manual project records remain `pending`, and work-item creation is blocked until an internal verified integration can set `active`.
- There is no repository snapshot/evidence collector, model dispatch endpoint, Cloud Tasks receiver, isolated test runner, artifact store adapter, webhook handler, SSE stream, or GitHub branch/PR writer. Terraform keeps the worker disabled by default for this reason.
- Plan and PR approval routes record durable decisions only. They do not enqueue jobs or trigger provider/GitHub side effects.
- The first schema uses `owner_subject` as its local ownership boundary. Organization membership and role modeling must precede a multi-user tenant launch.
- Firebase Hosting must be built with an explicit HTTPS Cloud Run API URL in staging/production. The frontend should refuse a production build without that configuration; see the frontend deployment notes.
- Authenticated routes are limited by verified subject, not proxy-derived IP. Before adding an unauthenticated/public endpoint, configure and validate trusted-edge volume/IP protection; a forwarded-IP application policy must not be inferred from arbitrary request headers.

## Environment constraints

- Terraform is a template, not a provisioned environment. GCP project IDs, Firebase identity values, domain decisions, Secret Manager values, WIF state bucket, and protected GitHub Environments require user-owned configuration and review.
- Cloud SQL/PostgreSQL migration behavior is not verified against a live production database until a reviewed development environment is provisioned. The initial migration is present and local validation is recorded in session history.
- No live OpenAI, GitHub, Firebase, Google Cloud, or Docker image registry credential has been used in this workspace.
