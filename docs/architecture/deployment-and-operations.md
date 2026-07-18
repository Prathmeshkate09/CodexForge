# Deployment and operations

## Environment model

CodexForge uses separate development, staging, and production environments. Local development uses Docker Compose plus host-run frontend/backend processes. Staging and production are planned as Terraform-managed Google Cloud environments. This repository does not provision or deploy an environment by itself.

| Component | Local | Staging/production |
| --- | --- | --- |
| SPA | Vite development server | Firebase Hosting |
| API | FastAPI process/container | Cloud Run |
| Worker | Not implemented | Disabled until a task receiver and isolation policy are implemented/reviewed |
| PostgreSQL | Docker Compose | Cloud SQL PostgreSQL |
| Redis | Docker Compose | Memorystore Redis |
| Durable jobs | Test doubles only | Cloud Tasks after receiver implementation |
| Artifacts | None yet | Private Cloud Storage after artifact policy implementation |
| Secrets | Ignored `.env` | Secret Manager |

## Firebase Hosting to Cloud Run

Firebase Hosting is intentionally configured only for SPA routing. It does not proxy `/api` to a Cloud Run service. A production browser build must therefore set an explicit HTTPS value such as:

```text
VITE_API_BASE_URL=https://codexforge-production-api-<hash>-<region>.a.run.app/api/v1
```

The matching Firebase Hosting origins must be passed to Terraform as `cors_allowed_origins`. Cloud Run normally requires Google IAM invocation, which a browser cannot provide. Only after staging validation may `allow_public_api_invocation = true` be enabled for the API transport layer. This grants Cloud Run invocation to `allUsers`; it does **not** make application routes anonymous because FastAPI still requires and validates the Firebase/OIDC bearer token for every protected route.

The frontend deployment configuration must also include the public Firebase web values. It must never include GitHub App credentials, OpenAI keys, database/Redis URLs, service-account material, or Secret Manager values.

## Local Docker Compose API transport

The Docker Compose frontend is intentionally distinct from Firebase Hosting. Its build passes the explicit
`VITE_API_TRANSPORT_MODE=local-container-proxy` and exact `VITE_API_BASE_URL=/api/v1` values. The Nginx runtime
proxies only `/api/` to the Compose `backend` service while preserving the FastAPI `/api/v1` prefix. The frontend runtime
rejects any other relative, HTTP, or external value in this mode. Normal production builds remain direct HTTPS-only;
Firebase Hosting must never set `local-container-proxy`.

The Compose UI can authenticate with Firebase ID tokens when its ignored root `.env` contains both the non-secret
`VITE_FIREBASE_*` build values and the backend's matching `CODEXFORGE_JWT_ISSUER`, `CODEXFORGE_JWT_AUDIENCE`, and
`CODEXFORGE_JWT_JWKS_URL` settings. The Firebase web values are browser-visible and constrained in Firebase Console;
the three validation settings remain server-side. If these values are omitted, Compose retains the guarded local
development-token path for host-run Vite development, while the production Docker bundle intentionally does not accept
a `VITE_DEV_BEARER_TOKEN`.

## Before a first cloud plan

1. Choose isolated GCP project(s), region, budget alerts, audit-log retention, domain/DNS ownership, data retention, and a private Terraform state bucket.
2. Create a Firebase project and enable Google sign-in. Record the exact Firebase project ID, issuer, audience, JWKS URL, authorized domains, and Hosting origins.
3. Review the GitHub App scopes, callback URL, webhook secret, installation policy, and repository ownership model. Do not make a project `active` until callback verification exists.
4. Supply non-secret Terraform variables through an ignored `terraform.tfvars` and write secret values directly to Secret Manager through an approved process. Never put secret versions in Terraform state or source.
5. Build/scanner-check immutable image digests. Run a reviewed migration job before promotion; application startup must not run migrations.
6. Run `terraform plan` behind a protected GitHub Environment. The included workflow intentionally never applies Terraform or deploys a Cloud Run revision.

## IAM and network model

- Cloud SQL, Redis, GCS, Cloud Tasks, and runtime services use separate least-privilege service accounts.
- Cloud SQL and Redis use private connectivity; databases are not public by default.
- Cloud Storage blocks public access and stores only private, sanitized, expiring artifacts after that feature is implemented.
- Cloud Tasks uses an OIDC task-invoker identity. The API has scoped `iam.serviceAccounts.actAs` permission on that identity, and only that identity may invoke the future worker service.
- GitHub Actions uses Workload Identity Federation, constrained to the configured repository and protected ref; service-account JSON keys are not part of this design.

## Release and rollback discipline

1. CI runs formatting, lint, type, unit, browser, dependency-audit, build/container-scan, and Terraform validation gates. GitHub Actions are pinned to reviewed immutable commits; Dependabot proposes updates through reviewable pull requests.
2. A separate approved workflow builds and scans digest-pinned images, then records the immutable artifact reference.
3. A reviewed migration step runs before the corresponding revision is promoted. Use expand/contract design for live changes and document a forward-fix/rollback plan.
4. Deploy a no-traffic or low-traffic revision, perform authenticated smoke checks, then increase traffic deliberately. Retain the previous revision for rollback.
5. Do not enable worker delivery, GitHub writes, model execution, or public API invocation until their staging tests and incident runbooks exist.

## Operations and observability

Use structured, sanitized logs with request/correlation IDs. Monitor API latency/error rates, rate-limit denials, Cloud Run revision health, Cloud SQL connections/latency, Redis health, task queue/dead letters, worker saturation, redaction failures, model/provider failures, GitHub failures, and attempted approval-bypass events. Establish an owned alert channel before onboarding external repositories.

Cloud SQL backups/point-in-time recovery and private artifact retention are infrastructure settings, not a substitute for restore exercises. Redis is never a source of truth; workflow decisions reconstruct from PostgreSQL and durable task records.
