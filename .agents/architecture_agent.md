# Architecture agent checklist

`AGENTS.md` is authoritative. Use this guide for cross-cutting design decisions.

## Responsibilities

- Maintain clear boundaries among the SPA, API, worker, database, queue, artifact store, GitHub App, and model orchestration.
- Record materially consequential decisions in ADRs and keep docs synchronized with actual implementation.
- Optimize for a safe, understandable path to roughly 100–200 concurrent users before pursuing autonomous-agent breadth.

## Standards and architecture

- Prefer a modular monolith with separate deployable API and worker processes until a measured scaling need warrants further services.
- Cloud SQL owns durable transactional state; Redis owns bounded ephemeral coordination; Cloud Tasks owns durable retries; GCS owns large sanitized artifacts.
- Use the model for bounded reasoning and structured tool selection. The server owns authorization, data access, tool execution, scheduling, and mutation gates.
- Make state transitions explicit, auditable, and versioned: draft → snapshot pinned → plan pending approval → patch pending review → PR pending approval → complete/cancelled/failed.

## Review checklist

- Is the new component necessary, observable, replaceable, and owned?
- Does it introduce a cross-tenant, mutation, persistence, or secret boundary that needs an ADR/threat-model update?
- Can the design recover from queue retries, process restarts, stale UI, duplicate webhooks, and partial provider failure?
- Is production operational complexity justified by current requirements?

## Common mistakes

- Splitting services before there is a measured scaling or ownership need.
- Putting durable approvals in cache or performing cloud actions from request threads.
- Describing a model as an authorization or security decision-maker.
- Treating deployment templates as a deployed environment.
