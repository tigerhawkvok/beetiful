#!/usr/bin/env bash
# Build and run the route test suite in Docker. Falls back to a local run if Docker
# isn't available. Run from the repo root.
set -euo pipefail

cd "$(dirname "$0")/.."

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    echo "==> Running tests in Docker"
    docker compose -f docker-compose.test.yml build
    exec docker compose -f docker-compose.test.yml run --rm test
fi

echo "==> Docker unavailable; running locally (needs ffmpeg + beet on PATH)"
exec uv run pytest tests/ -q
