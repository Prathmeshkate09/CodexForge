# ADR-0005: Key authenticated API rate limits by verified subject

- **Status:** Accepted
- **Date:** 2026-07-18

## Context

Cloud Run and the local Nginx container can present the API with a shared proxy address. Treating `request.client.host` as an end-user IP would make a per-IP bucket a global deployment bucket, while blindly trusting `X-Forwarded-For` would allow spoofing without an explicit trusted-proxy contract.

## Decision

All currently protected API routes consume a Redis-backed rate-limit bucket keyed by the verified JWT subject. The API does not read `X-Forwarded-For` or apply a request-client IP bucket to authenticated traffic. Future organization and project quotas will be added only after server-side membership and ownership models exist.

Public/unauthenticated traffic must be protected at a trusted edge before it is exposed. A future application-level IP limiter requires a documented proxy topology, a restrictive trusted-proxy allowlist, normalization tests, and staged validation. GitHub webhook controls will be keyed by signature and delivery ID rather than a generic client IP.

## Consequences

- One proxy address cannot exhaust an entire deployment's authenticated quota.
- A compromised individual token remains bounded by its subject bucket.
- Edge volumetric protection and organization/project quota design remain explicit production prerequisites rather than unsafe implicit behavior.
