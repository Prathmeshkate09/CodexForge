# Frontend browser tests

The Playwright suite lives in `frontend/tests/e2e/` so its imports resolve from
the frontend npm package, where `@playwright/test` is installed. Root-level
`tests/` remains the home for backend and cross-service test assets.
