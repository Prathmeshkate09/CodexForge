# Docker local development

CodexForge uses Docker Desktop for its normal local runtime. You do **not** need
to install PostgreSQL or Redis on Windows.

Run every command from the repository root:

```powershell
git rev-parse --show-toplevel
```

Ensure that command prints the path to your local `CodexForge` checkout.

## What Docker starts

| Container | Purpose | Stays running? |
| --- | --- | --- |
| `codexforge-postgres` | PostgreSQL 16 application database | Yes |
| `codexforge-redis` | Redis cache and rate-limit coordination | Yes |
| `codexforge-migrate` | Applies reviewed Alembic migrations | Stops successfully after each required run |
| `codexforge-backend` | FastAPI API | Yes |
| `codexforge-frontend` | Nginx-served React application and `/api/` proxy | Yes |

```text
Browser (127.0.0.1:5173)
          |
          v
codexforge-frontend (Nginx)
          |
          v
codexforge-backend (FastAPI) ----> codexforge-postgres (persistent data)
          |
          +-------------------------> codexforge-redis (persistent cache data)

All containers communicate only on codexforge-network.
```

## Isolation and persistence

Docker Compose uses the project name `codexforge` and explicit resource names:

- Network: `codexforge-network`
- PostgreSQL volume: `codexforge-postgres-data`
- Redis volume: `codexforge-redis-data`
- Application images: `codexforge-backend:local` and
  `codexforge-frontend:local`

PostgreSQL and Redis do not publish Windows host ports. They are reachable only
from CodexForge containers, so a database from another project cannot be used by
mistake. The browser and API bind only to `127.0.0.1`:

| Address | Default | Change in `.env` |
| --- | --- | --- |
| App | `http://127.0.0.1:5173` | `CODEXFORGE_WEB_PORT` |
| API docs | `http://127.0.0.1:8000/docs` | `CODEXFORGE_API_PORT` |

## Environment file

Copy `.env.example` to `.env` once. It is ignored by Git.

| Variable group | Required? | Meaning |
| --- | --- | --- |
| `POSTGRES_*` | Yes | Private Docker PostgreSQL database name, user, and password. |
| `CODEXFORGE_JWT_SECRET` | Yes | Server-side local JWT signing secret. |
| `CODEXFORGE_API_PORT`, `CODEXFORGE_WEB_PORT` | Yes | Loopback host ports for the API and app. |
| `VITE_FIREBASE_*` | Optional | Public Firebase web configuration for Google sign-in. Set the required values together. |
| `CODEXFORGE_JWT_ISSUER`, `CODEXFORGE_JWT_AUDIENCE`, `CODEXFORGE_JWT_JWKS_URL` | Optional | Matching server-side Firebase token validation settings. |
| `CODEXFORGE_OPENAI_API_KEY` | Optional | Server-side key for AI-assisted plan generation in `PlanningWorkerService`. |

Never put a GitHub token, OpenAI key, service-account key, database URL, or JWT
secret in a `VITE_*` variable. The Docker frontend is a production-style Nginx
build, so it intentionally does not accept a development bearer token. Configure
Firebase to use the interactive UI, or use the documented host-only development
token workflow when specifically testing that path.

## Everyday commands

Start everything in the foreground (recommended the first time):

```powershell
docker compose up --build
```

Start in the background:

```powershell
docker compose up --build -d
docker compose ps
```

View logs:

```powershell
docker compose logs -f
docker compose logs -f backend
```

Stop containers while keeping the database and cache data:

```powershell
docker compose down
```

Rebuild only after code or Dockerfile changes:

```powershell
docker compose up --build -d
```

## Database verification and reset

Check that migrations reached the Docker PostgreSQL database:

```powershell
docker compose exec postgres psql -U codexforge -d codexforge -c "SELECT version_num FROM alembic_version;"
```

Restart PostgreSQL and repeat the command above to confirm data persistence:

```powershell
docker compose restart postgres
docker compose exec postgres psql -U codexforge -d codexforge -c "SELECT version_num FROM alembic_version;"
```

To permanently reset **only CodexForge** containers, network, database, and
Redis volumes:

```powershell
docker compose down --volumes --remove-orphans
```

Run that command only from the repository root. It targets resources
with the `codexforge` Compose project label; it does not prune Docker globally
or remove containers from another project.

## Troubleshooting

- **Cannot connect to Docker:** Start Docker Desktop and wait until the engine
  shows as running, then run `docker version`.
- **Port already allocated:** Change `CODEXFORGE_WEB_PORT` or
  `CODEXFORGE_API_PORT` in `.env`, then run `docker compose up -d` again.
- **Migration container fails:** Run `docker compose logs migrate`. Do not start
  the API against a partially migrated database.
- **Frontend shows authentication configuration:** Add the required
  `VITE_FIREBASE_*` values and matching server-side Firebase validation values
  to `.env`, then rebuild with `docker compose up --build`.
- **Need database access:** Use `docker compose exec postgres psql ...`; no
  local PostgreSQL service or port is required.
