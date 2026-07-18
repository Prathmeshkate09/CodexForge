# ADR-0002: Use Firebase Hosting, Cloud Run, Cloud SQL, Memorystore, Cloud Tasks, and GCS

- **Status:** Accepted
- **Date:** 2026-07-18

## Context

CodexForge needs a practical Google Cloud path for a Vite SPA, async FastAPI API, durable workflow state, bounded background work, and private artifacts while supporting an early target of 100–200 concurrent users.

## Decision

- Serve the static Vite SPA with Firebase Hosting.
- Run the FastAPI API and separate controlled worker workloads on Cloud Run.
- Use Cloud SQL PostgreSQL as the system of record.
- Use Memorystore Redis only for cache, rate limit, lock, and short-lived coordination state.
- Use Cloud Tasks for durable background dispatch/retry; do not introduce Celery until a concrete Cloud Tasks limitation exists.
- Use private Cloud Storage for sanitized, expiring artifacts.
- Store secrets in Secret Manager and deploy through GitHub Actions Workload Identity Federation.

## Consequences

- Components have clear durability and scaling roles.
- Terraform and IAM design are required before a real cloud deployment.
- Workers must be idempotent because Cloud Tasks delivery can retry.
- No local development setup should require a Google Cloud credential.
