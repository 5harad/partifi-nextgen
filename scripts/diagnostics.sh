#!/usr/bin/env bash
# Quick production health snapshot: readiness, cache, failed partsets, recent errors.
#
# Usage (on EC2, from repo root):
#   ./scripts/diagnostics.sh
#   HOURS=24 ./scripts/diagnostics.sh
#
# Requires .env with MYSQL_PASSWORD (same as docker compose prod).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
HOURS="${HOURS:-6}"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ -z "${MYSQL_PASSWORD:-}" ]]; then
  echo "MYSQL_PASSWORD is not set. Add it to .env or export it before running." >&2
  exit 1
fi

compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

section() {
  echo ""
  echo "=== $1 ==="
}

check_health_api() {
  compose exec -T api python -c "
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=10) as r:
    print(json.dumps(json.load(r), indent=2))
"
}

check_health_caddy() {
  local site="${SITE_ADDRESS:-partifi.org}"
  # Caddy serves this site on HTTPS; plain HTTP gets a redirect, not JSON.
  curl -sk --max-time 10 -H "Host: ${site}" "https://127.0.0.1/health/ready"
}

section "Health (API /health/ready)"
if check_health_api 2>/dev/null; then
  :
else
  echo "API health/ready request failed (is the api container up?)"
fi

section "Health (via Caddy HTTPS /health/ready)"
if check_health_caddy | python3 -m json.tool 2>/dev/null; then
  :
else
  echo "Caddy health/ready request failed (Host: ${SITE_ADDRESS:-partifi.org}, https://127.0.0.1)"
  echo "Raw response:"
  check_health_caddy 2>/dev/null || echo "(no response)"
fi

section "Cache (/data/partifi)"
compose exec -T api du -sh /data/partifi 2>/dev/null || echo "could not read cache (is api up?)"
compose exec -T api du -sh /data/partifi/scores /data/partifi/preview /data/partifi/parts 2>/dev/null \
  || true

if [[ -f .env ]]; then
  section "Cache cap (.env)"
  grep -E '^PARTIFI_CACHE' .env || echo "(no PARTIFI_CACHE_* vars set — using defaults)"
fi

section "Failed / stuck partsets (MySQL)"
compose exec -T mysql mysql -u partifi -p"$MYSQL_PASSWORD" partifi -e "
SELECT id, title, status, error,
       ROUND(import_progress) AS imp,
       ROUND(convert_progress) AS conv,
       ROUND(analysis_progress) AS anal,
       parts_ready,
       create_ts, mod_ts, last_access
FROM partsets
WHERE error IS NOT NULL
   OR (import_complete IS NULL AND create_ts < NOW() - INTERVAL 1 HOUR)
ORDER BY COALESCE(mod_ts, create_ts) DESC
LIMIT 20;
"

section "Recent errors (last ${HOURS}h)"
ERROR_PATTERN='error|exception|failed|timed out|exit 137|OOM'

if command -v journalctl >/dev/null 2>&1; then
  # Prod compose uses journald (tag: partifi/<container-name>).
  JOURNAL_LINES="$(
    journalctl --since "${HOURS} hours ago" --no-pager 2>/dev/null \
      | grep -E 'partifi-nextgen-(api|worker|web)' \
      | grep -iE "$ERROR_PATTERN" \
      | tail -40 || true
  )"
  if [[ -n "$JOURNAL_LINES" ]]; then
    echo "$JOURNAL_LINES"
  else
    echo "(no matching journal lines — try docker logs below or increase HOURS)"
    compose logs --since "${HOURS}h" api worker-1 worker-2 worker-3 web 2>&1 \
      | grep -iE "$ERROR_PATTERN" \
      | tail -40 || echo "(no matching docker log lines)"
  fi
else
  compose logs --since "${HOURS}h" api worker-1 worker-2 worker-3 web 2>&1 \
    | grep -iE "$ERROR_PATTERN" \
    | tail -40 || echo "(no matching docker log lines)"
fi

section "Containers"
compose ps
