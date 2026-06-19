#!/usr/bin/env bash
# Delete all partsets (and related rows) for a junk / ghost score id.
#
# Usage:
#   ./scripts/purge-score-cluster.sh --score-id aX38M --dry-run
#   ./scripts/purge-score-cluster.sh --score-id aX38M --confirm
set -euo pipefail
cd "$(dirname "$0")/.."
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
exec docker compose -f "$COMPOSE_FILE" exec api python -m app.admin.purge_score_cluster "$@"
