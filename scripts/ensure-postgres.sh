#!/usr/bin/env bash
# Start docker-compose Postgres when local dev DB is not accepting connections.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PG_HOST="${POSTGRES_HOST:-localhost}"
PG_PORT="${POSTGRES_PORT:-5433}"
PG_USER="${POSTGRES_USER:-chatbot}"
PG_DB="${POSTGRES_DB:-chatbot}"

is_postgres_ready() {
  command -v pg_isready >/dev/null 2>&1 || return 1
  pg_isready -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" >/dev/null 2>&1
}

if is_postgres_ready; then
  echo "Postgres already running on ${PG_HOST}:${PG_PORT}."
  exit 0
fi

echo "Starting Postgres (docker compose --profile python up -d postgres)..."
docker compose --profile python up -d postgres

echo "Waiting for Postgres on ${PG_HOST}:${PG_PORT}..."
for _ in $(seq 1 30); do
  if is_postgres_ready; then
    echo "Postgres is ready."
    exit 0
  fi
  sleep 1
done

echo "Postgres did not become ready within 30s. Check: docker compose --profile python logs postgres" >&2
exit 1
