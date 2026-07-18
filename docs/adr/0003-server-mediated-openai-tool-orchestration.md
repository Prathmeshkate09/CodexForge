# ADR-0003: Use a server-mediated Responses API tool loop

- **Status:** Accepted
- **Date:** 2026-07-18

## Context

CodexForge needs model-assisted repository analysis and patch planning, but repository text and model output are untrusted. A model must not receive direct shell, GitHub write, cloud, or credential capability.

## Decision

Use the OpenAI Responses API through a backend orchestration service. Model configuration, including the initial configurable `gpt-5.6-sol` default, remains server-side. The service:

- exposes only strict, allowlisted function tools;
- validates tool inputs and enforces tenant/capability policy outside the model;
- retains prior model output and each function `call_id` when returning tool results;
- sends bounded/redacted evidence only;
- supplies a non-reversible hashed authenticated subject as `safety_identifier`;
- applies timeouts, budget limits, audit metadata, safety evaluations, and human approvals before consequential actions.

No model output is executed as arbitrary shell or treated as authorization.

## Consequences

- More orchestration code is required, but capability control and auditability are testable.
- Tool contracts need versioning and adversarial tests.
- The model cannot independently access a broader environment when a task needs additional data or action; product code must add a reviewed tool first.
