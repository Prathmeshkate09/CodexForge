# Frontend agent checklist

`AGENTS.md` is authoritative. Use this guide for the Vite React application.

## Responsibilities

- Build accessible, keyboard-operable approval workflows that accurately represent server state.
- Use feature-oriented modules, typed API contracts, TanStack Query, React Hook Form, Zod, and React Router.
- Make the safety boundary legible: plans, patches, test evidence, and branch/PR approval are distinct irreversible user actions.

## Standards and architecture

- Treat the server as authorization authority. Client visibility and disabled controls are user experience only.
- Model loading, empty, retrying, unauthorized, expired-session, and error states for every remote view.
- Use Zod validation at form boundaries; do not duplicate business policy that the server must enforce.
- Use a generated or maintained typed API client; never place secrets, GitHub tokens, OpenAI credentials, or internal artifact URLs in the bundle.

## Review checklist

- Is approval text scoped to the exact snapshot, plan/patch version, and repository action?
- Does the UI prevent accidental duplicate requests while the server still enforces idempotency?
- Are errors actionable without leaking stack traces or redacted evidence?
- Is the flow covered by Vitest and critical Playwright tests, including keyboard navigation?

## Common mistakes

- Treating a browser boolean as proof of approval.
- Polling aggressively instead of consuming bounded SSE/job updates.
- Showing raw CI logs, repository files, model output, or API errors without redaction-aware rendering.
- Building one global components directory instead of cohesive feature modules.
