# Deployment notes

## Current status

Nothing has been deployed or provisioned. Terraform has not been applied, no Firebase project/domain/GCP project is configured, and no production secret exists in the repository.

## Intended topology

- Firebase Hosting serves the Vite SPA.
- Cloud Run serves the FastAPI API. A worker Cloud Run service is disabled until its receiver/runner security boundary exists.
- Cloud SQL PostgreSQL is authoritative; Memorystore Redis is ephemeral coordination only; Cloud Tasks is future durable dispatch; Cloud Storage will hold private sanitized artifacts.
- Secret Manager holds production secrets. GitHub Actions uses WIF and a protected environment for reviewed plans/deployments.

## Critical deployment configuration

1. Build the production SPA with an absolute HTTPS `VITE_API_BASE_URL` for the Cloud Run API; Firebase's current rewrite is SPA-only.
2. Configure Firebase issuer/audience/JWKS URL and explicit Firebase origins in Terraform before enabling Cloud Run.
3. Set `allow_public_api_invocation = true` only after staging confirms Firebase bearer-token validation and CORS; it opens Cloud Run transport, not protected API routes.
4. Keep `enable_worker_service = false` until the task receiver, runner isolation policy, and tests are implemented.
5. Run Alembic migrations as a reviewed deployment step, never at API startup.
6. Do not add public/unauthenticated API routes until trusted-edge IP/volumetric controls are configured and tested. Authenticated application limits are keyed by verified identity, not an untrusted forwarded header.

See [deployment and operations](../docs/architecture/deployment-and-operations.md) and [Terraform instructions](../infra/terraform/README.md).
