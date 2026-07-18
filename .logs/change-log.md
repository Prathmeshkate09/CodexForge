# Change log

This file records meaningful workspace changes. Exact change history belongs in Git.

## 2026-07-18 - Platform foundation initialized

- **User request:** Initialize CodexForge from the committed GitHub repository using the approved production-minded engineering guide.
- **Reasoning summary:** The checkout contained only `AGENTS.md`, so the platform baseline was added before application implementation. The baseline preserves approval-first repository mutations and does not provision cloud resources or use credentials.
- **Files created:** Repository operating context, specialist checklists, canonical architecture/API/feature/ADR docs, CI and delivery workflow templates, Terraform GCP baseline, container definitions, and validation scripts.
- **Files modified:** None.
- **Files deleted:** None.
- **Migration notes:** No database schema or Alembic migration exists yet.
- **Breaking changes:** None; this is initial scaffolding.

## 2026-07-18 - Local approval workflow foundation

- **User request:** Start building the committed CodexForge GitHub repository according to the supplied production-minded engineering guide.
- **Reasoning summary:** Implemented the first safe vertical slice without using external credentials, provisioning cloud resources, or performing GitHub writes. The workflow fails closed: a project stays pending until future GitHub App verification, and approval is tied to exact immutable run evidence.
- **Files created:** FastAPI service, React/Firebase client, Alembic initial migration, backend/frontend tests, package lockfiles, Docker/CI/Firebase/Terraform assets, local environment samples, ADR-0004, and canonical documentation updates.
- **Files modified:** Root README/ignore files, Docker Compose and backend Dockerfile, validation scripts, `.codex` project context, API/database/deployment notes, security/architecture/feature docs, and Terraform deployment instructions.
- **Files deleted:** None.
- **Migration notes:** Adds repositories, work_items, work_runs, approvals, audit_events, and idempotency_records. `work_runs` has a partial unique current-attempt index; approvals snapshot non-null commit and artifact SHA-256 values. Apply with `uv run alembic upgrade head` as a reviewed step.
- **Breaking changes:** None; the repository had no prior application API/schema. Production SPA builds now require an explicit HTTPS `VITE_API_BASE_URL` rather than silently using a Firebase SPA rewrite.
- **Validation:** Backend Ruff/Black/mypy/pytest (10 tests), health, and in-memory migration passed. Frontend format/lint/type/Vitest (11 tests)/production build/Playwright (2 tests) passed. Docker Compose config passed. Docker image and Terraform runtime validation were blocked by an unavailable Docker Linux engine and missing Terraform binary.

## 2026-07-18 - Security and delivery hardening

- **User request:** Continue building CodexForge as a production-grade, scalable developer tool under the supplied engineering guide.
- **Reasoning summary:** Integration review exposed approval/JWKS/rate-limit/supply-chain concerns before any external deployment. The fixes preserve approval-first behavior, avoid trusting proxy headers, and make the delivery path auditable.
- **Files created:** ADR-0005 and `.github/dependabot.yml`.
- **Files modified:** Backend security, workflow, validation, and rate-limit code/tests; frontend package manifest and lockfile; Docker/Terraform/CI delivery configuration; API, architecture, security, deployment, README-adjacent, and `.codex` operating documents.
- **Files deleted:** None.
- **Migration notes:** No new schema migration. Existing approval data invariants remain unchanged; future workers must persist canonical 40-character SHA-1 or 64-character SHA-256 commit IDs.
- **Breaking changes:** Production builds continue to require HTTPS API configuration. Relative `/api/v1` is reserved for the explicit local Compose transport mode; CI action references now require immutable SHAs.
- **Validation:** Backend Ruff/Black/mypy/pytest (29 tests), frontend format/lint/type/Vitest (15 tests)/two production builds/Playwright (2 tests), `npm audit` (zero vulnerabilities), `pip-audit` (no known vulnerabilities), Compose configuration, and workflow YAML parsing passed. Container runtime/scans and Terraform CLI validation remain blocked by unavailable local tooling.

## 2026-07-18 - Verification gate correction

- **User request:** Continue, complete the work, and push it to GitHub.
- **Reasoning summary:** The full Windows verification wrapper was exercised before publishing and exposed PowerShell's `npm.ps1` argument reconstruction behavior. The wrapper now invokes the Windows command shims directly, and backend test source is included in lint/format gates.
- **Files created:** None.
- **Files modified:** `scripts/verify.ps1`, `scripts/verify.sh`, `.github/workflows/ci.yml`, `backend/pyproject.toml`, and backend test formatting/import order.
- **Files deleted:** None.
- **Migration notes:** None.
- **Breaking changes:** None; local Windows verification is now reliable and checks more source files.
- **Validation:** Full `./scripts/verify.ps1` passed: frontend format/lint/type/Vitest (15 tests)/production build/Playwright (2 tests); backend dependency sync/Ruff/Black/mypy/pytest (29 tests); Docker Compose configuration. Expected non-failing React Router future-flag and Node color-environment warnings were emitted during browser tests.
