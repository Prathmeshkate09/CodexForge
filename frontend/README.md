# CodexForge frontend

The Vite SPA is an approval-first client for the FastAPI `/api/v1` service. It does not contain GitHub App,
OpenAI, database, Redis, or Google Cloud credentials.

## Authentication

Production and preview deployments use Firebase Authentication with the Google provider:

1. Enable Google as a sign-in provider in Firebase Authentication.
2. Add the Firebase Hosting and local development origins to Firebase's authorized domains.
3. Copy `frontend/.env.example` to an untracked `frontend/.env.local` and set every required `VITE_FIREBASE_*`
   variable.
4. Configure the FastAPI service to validate Firebase ID tokens before authorizing `/api/v1` routes.

Firebase web configuration is intentionally browser-visible. Restrict the Firebase API key and authorized domains in
Google Cloud/Firebase; do not treat it as a server secret.

If a required Firebase variable is absent, the UI displays a configuration state and makes no protected API request.
After sign-in, the API client requests the current Firebase ID token for each protected request and sends
`Authorization: Bearer <token>`.

### Local development token

`VITE_DEV_BEARER_TOKEN` is available only when Vite runs in development mode, including Playwright's local browser
server. It is for a short-lived developer user token in an untracked `.env.local` file. It is deliberately ignored in
production builds and must never contain a service-account key, GitHub token, OpenAI key, or other server secret.

## Commands

```powershell
npm install
npm run dev
npm run typecheck
npm run lint
npm run test
npm run test:e2e
```

Vite proxies `/api` to `VITE_DEV_API_PROXY_TARGET` in local development. Firebase Hosting does not currently provide
an API rewrite, so a Firebase/Cloud production build must set `VITE_API_BASE_URL` to an HTTPS absolute Cloud Run API
URL ending in `/api/v1`. The SPA refuses to make API calls if that production variable is missing or non-HTTPS. The
backend must allow that frontend origin with CORS and validate Firebase ID tokens.

## Local Docker Compose

Docker Compose builds the SPA in an explicit `local-container-proxy` transport mode. Its Nginx container proxies only
the same-origin `/api/` path to the Compose backend, preserving the `/api/v1` FastAPI prefix. This exception is
deliberately confined to the Docker image build; it must not be used for Firebase Hosting or any Cloud deployment.

To use Google sign-in through the local container UI, copy the repository `.env.example` to ignored `.env` and provide
the public `VITE_FIREBASE_*` values together with the matching server-side Firebase validation values:

```text
CODEXFORGE_JWT_ISSUER=https://securetoken.google.com/<firebase-project-id>
CODEXFORGE_JWT_AUDIENCE=<firebase-project-id>
CODEXFORGE_JWT_JWKS_URL=https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com
```

Then run `docker compose up --build` and open `http://127.0.0.1:5173`. The Firebase variables are public browser
configuration, not server secrets; do not place a service-account key, JWT signing secret, GitHub credential, OpenAI
key, or database password in a `VITE_*` variable. Without Firebase configuration, the container UI intentionally stops
at its authentication configuration state. The development-token flow remains available only for a host-run Vite
development server, never for the production Docker bundle.
