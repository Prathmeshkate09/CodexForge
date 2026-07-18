# CodexForge API

The FastAPI service manages authorization-scoped workflow state, approvals, audit records, idempotency, and safe orchestration metadata. It does not execute model-produced shell commands, call GitHub, create a branch/PR, merge, deploy, or run migrations automatically at startup.

## Local configuration and startup

Copy `backend/.env.example` to ignored `backend/.env`, align its PostgreSQL password with the root `.env`, then run:

```powershell
cd backend
uv sync --locked --all-groups
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

The development token endpoint and HS256 verification are disabled by default. They must never be enabled in staging or production. For an intentional local-only browser test, set `CODEXFORGE_ALLOW_DEV_IDENTITY=true`, a non-placeholder `CODEXFORGE_JWT_SECRET`, and a high-entropy `CODEXFORGE_DEV_IDENTITY_SECRET` (both at least 32 characters) in `backend/.env`, restart the API, then issue a 15-minute token:

```powershell
$body = @{ subject = "local-developer"; email = "developer@example.invalid"; name = "Local Developer" } | ConvertTo-Json
$token = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/auth/dev/token" `
  -Headers @{ "X-Dev-Identity-Key" = "<your-local-dev-identity-secret>" } `
  -ContentType "application/json" -Body $body
$token.access_token
```

Place only that short-lived token in ignored `frontend/.env.local` as `VITE_DEV_BEARER_TOKEN`. Do not put a server secret, service-account key, GitHub credential, OpenAI key, or database password in a Vite variable.

`CODEXFORGE_JWT_JWKS_URL` is an operator-controlled deployment setting, never a client request field. A nonblank value must be an absolute HTTPS URL without userinfo, query, or fragment; the API disables inherited proxy environment settings when it retrieves JWKS documents. Use the Firebase URL from `.env.example` or another trusted OAuth/OIDC provider endpoint.

## Approval boundary

`POST /api/v1/runs/{run_id}/pull-request-approval` records an explicit decision only. A future, separately reviewed worker and GitHub service are required before any repository write can occur.

Each approval is valid only for its exact current work run, a canonical full repository commit ID (40-character SHA-1 or 64-character SHA-256), and immutable artifact SHA-256. Worker-only transition methods require all three to match. Retrying/resetting supersedes the prior approval-capable run, so an old approval cannot authorize a later plan, patch, branch, or pull request.
