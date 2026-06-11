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

check_health() {
  local site="${SITE_ADDRESS:-partifi.org}"
  curl -sf -H "Host: ${site}" "http://127.0.0.1/health/ready"
}

section "Health (/health/ready via Caddy)"
if check_health | python3 -m json.tool 2>/dev/null; then
  :
else
  echo "health/ready request failed (Caddy routes by Host; using SITE_ADDRESS=${SITE_ADDRESS:-partifi.org})"
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
