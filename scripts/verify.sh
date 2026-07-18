#!/usr/bin/env sh
set -eu

skip_browser_tests=false
skip_docker_config=false

for argument in "$@"; do
  case "$argument" in
    --skip-browser-tests) skip_browser_tests=true ;;
    --skip-docker-config) skip_docker_config=true ;;
    *) echo "Unknown option: $argument" >&2; exit 2 ;;
  esac
done

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

command -v npm >/dev/null 2>&1 || { echo "npm is required; install Node.js 22 LTS." >&2; exit 1; }
command -v uv >/dev/null 2>&1 || { echo "uv is required; install uv." >&2; exit 1; }

cd "$repo_root/frontend"
npm ci
npm run format:check
npm run lint
npm run typecheck
npm run test
npm run build

if [ "$skip_browser_tests" = false ]; then
  npx playwright test --config playwright.config.ts --pass-with-no-tests
fi

cd "$repo_root/backend"
uv sync --locked --all-groups
uv run ruff check --config pyproject.toml . ../tests/backend
uv run black --config pyproject.toml --check . ../tests/backend
uv run mypy app
uv run pytest

if [ "$skip_docker_config" = false ]; then
  command -v docker >/dev/null 2>&1 || { echo "Docker is required; pass --skip-docker-config only when intentionally unavailable." >&2; exit 1; }
  cd "$repo_root"
  docker compose --env-file .env.example config --quiet
fi

echo "CodexForge verification completed successfully."
