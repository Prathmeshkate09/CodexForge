# DevOps agent checklist

`AGENTS.md` is authoritative. Use this guide for containers, CI/CD, Terraform, environments, and observability.

## Responsibilities

- Maintain reproducible local Docker workflows, immutable container builds, GitHub Actions checks, Terraform plans, staged rollout guidance, and rollback readiness.
- Protect deployment credentials with Workload Identity Federation and Secret Manager.
- Ensure application migrations are separately reviewed and never run accidentally at service startup.

## Standards and architecture

- Build frontend and backend images with explicit build stages, non-root runtime users, and predictable entry points.
- Run lint, type checks, unit tests, builds, dependency checks, and IaC validation in CI. Keep deployments manual and protected until environment ownership is configured.
- Use GitHub OIDC/WIF rather than service-account JSON keys. Scope cloud IAM to the deploy environment and workload only.
- Emit structured logs with correlation IDs, create health/readiness probes, define retention, and document rollback before a release.

## Review checklist

- Does CI avoid secrets in logs and block unreviewed production deployment?
- Are Cloud Run service accounts, Secret Manager access, Cloud SQL/Redis networking, and bucket access least-privilege?
- Does Terraform plan cleanly with supplied variables and avoid outputting sensitive data?
- Is a migration explicit, ordered, monitored, and reversible/forward-fixable?

## Common mistakes

- Committing service-account keys or `.tfstate`.
- Using `latest` base images, root containers, or startup migrations.
- Treating a passing `terraform validate` as permission to apply production infrastructure.
- Making CI manipulate GitHub branches/PRs outside the product approval workflow.
