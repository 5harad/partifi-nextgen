#!/usr/bin/env bash
# List or delete failed partsets (error IS NOT NULL) for a signed-in user.
set -euo pipefail
cd "$(dirname "$0")/.."
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
exec docker compose -f "$COMPOSE_FILE" exec api python -m app.admin.delete_failed_partsets "$@"
