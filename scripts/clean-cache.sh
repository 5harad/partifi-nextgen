#!/usr/bin/env bash
# Run local cache eviction (TTL, size cap, stale job scratch).
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose -f docker-compose.prod.yml exec -T worker-1 python -m jobs.clean_cache
