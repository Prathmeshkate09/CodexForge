# Terraform baseline

This directory declares a Google Cloud baseline for one isolated CodexForge environment. It is an infrastructure template, not permission to provision resources. No credential values, secret versions, state credentials, domains, or service-account keys are committed here.

## What a reviewed apply would create

- required APIs, VPC/private service networking, Artifact Registry, a private lifecycle-managed artifact bucket, Cloud SQL PostgreSQL, Memorystore Redis, and a bounded Cloud Tasks queue;
- API, future worker, task-invoker, and Terraform service accounts with scoped runtime grants;
- Secret Manager secret containers only; values are supplied outside Terraform;
- GitHub Actions Workload Identity Federation restricted to `github_repository` and `github_wif_ref`;
- optional Cloud Run API service when an immutable API image and production identity/CORS values are supplied.

`enable_worker_service` defaults to `false`. Do not enable it until a task receiver, runner isolation policy, artifact/redaction boundary, and worker tests exist. `allow_public_api_invocation` also defaults to `false`; it is the deliberate browser-to-Cloud-Run transport opt-in described below.

## Validate locally

1. Copy `terraform.tfvars.example` to an ignored `terraform.tfvars` and fill only non-secret values.
2. Run:

   ```sh
   terraform init -backend=false
   terraform fmt -check -recursive
   terraform validate
   terraform plan
   ```

3. For stateful environments, initialize with a separately bootstrapped private state bucket and a narrow Terraform identity. Review the plan with security/operations owners before any apply.

An apply is externally consequential and needs explicit approval. Do not create service-account JSON keys for GitHub Actions; use the WIF output and protected environments.

## Cloud Run API configuration

When `enable_runtime_services = true`, Terraform fails closed unless all of the following are supplied:

- a digest-pinned `api_image`;
- `jwt_jwks_url`, `jwt_issuer`, and `jwt_audience` for the Firebase/OIDC provider;
- explicit non-wildcard `cors_allowed_origins`.

For Firebase Hosting, the static build must use the deployed Cloud Run URL as `VITE_API_BASE_URL`. If the browser needs to call that API directly, set `allow_public_api_invocation = true` only after staging verification. The resulting `allUsers` Cloud Run IAM binding makes transport invocation possible; FastAPI bearer-token checks remain mandatory and protect business routes.

## Cloud Tasks and worker posture

The API service account has Cloud Tasks enqueue permission and scoped `roles/iam.serviceAccountUser` on the task-invoker identity. That supports OIDC task creation when a real receiver is implemented. The task-invoker gets `roles/run.invoker` only for the future worker service. Do not treat this baseline as safe authority to run untrusted repository code.

## Secrets and deployment

Create only Secret Manager containers through Terraform. Write database/Redis URLs, GitHub App material, OpenAI key, JWT secret, webhook secret, and safety-identifier salt through a reviewed secure process outside Terraform state. Build and scan immutable images, perform migrations as a separately reviewed deployment step, and use a staged Cloud Run rollout/rollback plan.
