#!/usr/bin/env bash
# Detect a common local-dev footgun: Docker publishes *:8000 (IPv6-reachable via
# "localhost") while `make backend` binds only 127.0.0.1:8000. Vite used to proxy
# to http://localhost:8000, so Google login hit the Docker backend without
# GOOGLE_CLIENT_ID → 503 auth_not_configured, even though the local API worked.
set -euo pipefail

PORT="${API_PORT:-8000}"

listeners="$(lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null || true)"
if [[ -z "${listeners}" ]]; then
  exit 0
fi

# macOS Docker Desktop truncates lsof COMMAND to "com.docke" (not full "com.docker").
docker_hit="$(printf '%s\n' "${listeners}" | awk 'NR>1 && tolower($1) ~ /docke/ {print; exit}')"
ipv4_local="$(printf '%s\n' "${listeners}" | awk 'NR>1 && $9 ~ /^127\.0\.0\.1:'"${PORT}"'$/ {print; exit}')"
star_or_ipv6="$(printf '%s\n' "${listeners}" | awk 'NR>1 && ($9 ~ /^\*:'"${PORT}"'$/ || $9 ~ /^\[::\]:'"${PORT}"'$/ || $9 ~ /^\[::1\]:'"${PORT}"'$/) {print; exit}')"

if [[ -n "${docker_hit}" && -n "${ipv4_local}" ]]; then
  cat >&2 <<EOF
WARNING: Port ${PORT} has both a Docker listener and a local 127.0.0.1 listener.

  Docker (IPv6 / *: ${PORT}) and local uvicorn (127.0.0.1:${PORT}) can both
  appear "up", but http://localhost:${PORT} usually reaches Docker first.

  Vite proxies /api to http://127.0.0.1:${PORT} (not localhost) for this reason.
  If Google login still returns auth_not_configured, stop the compose backend:

    docker compose --profile python stop backend-python
    # or: docker stop chatbot-backend-python

  Then keep using: make backend
EOF
  exit 0
fi

if [[ -n "${docker_hit}" && -z "${ipv4_local}" ]]; then
  cat >&2 <<EOF
NOTE: Docker is listening on port ${PORT}. Local \`make backend\` will bind
127.0.0.1:${PORT} alongside it. Prefer one backend at a time for auth:

  docker compose --profile python stop backend-python
EOF
  exit 0
fi

if [[ -n "${star_or_ipv6}" && -n "${ipv4_local}" && -z "${docker_hit}" ]]; then
  cat >&2 <<EOF
WARNING: Port ${PORT} has both a wildcard/IPv6 listener and 127.0.0.1.
http://localhost:${PORT} may not reach your local uvicorn. Prefer
http://127.0.0.1:${PORT} (Vite already does this for /api).
EOF
fi
