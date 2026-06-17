#!/usr/bin/env bash
# Production health snapshot (run on EC2 from repo root).
#
# Usage:
#   ./scripts/diagnostics.sh
#   DAYS=7 ./scripts/diagnostics.sh
#
# Requires .env with MYSQL_PASSWORD (same as docker compose prod).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
DAYS="${DAYS:-7}"
ERROR_HOURS="${ERROR_HOURS:-24}"

export LANG="${LANG:-en_US.UTF-8}"
export LC_ALL="${LC_ALL:-en_US.UTF-8}"

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

mysql_scalar() {
  compose exec -T mysql mysql -u partifi -p"$MYSQL_PASSWORD" \
    --default-character-set=utf8mb4 \
    -N \
    partifi -e "$1" 2>/dev/null \
    || echo "?"
}

mysql_query() {
  compose exec -T mysql mysql -u partifi -p"$MYSQL_PASSWORD" \
    --default-character-set=utf8mb4 \
    --table \
    partifi -e "$1"
}

STUCK_WHERE="
  COALESCE(error_ts, paste_start, mod_ts, last_access, create_ts)
    >= NOW() - INTERVAL ${DAYS} DAY
  AND (
    error IS NOT NULL
    OR (import_complete IS NULL AND create_ts < NOW() - INTERVAL 1 HOUR)
    OR (
      paste_start IS NOT NULL
      AND paste_complete IS NULL
      AND parts_ready = 0
      AND paste_start < NOW() - INTERVAL 1 HOUR
    )
  )
"

filter_error_lines() {
  grep -iE ' ERROR |exception|failed|timed out|exit 137(\s|$)|\bOOM\b|Out of memory|Traceback|ValueError|Could not' \
    | grep -viE 'aborting with incomplete response|http2: stream closed|repaired or ignored|The following errors were encountered'
}

normalize_error_key() {
  sed -E \
    -e 's/^[A-Za-z]{3} [0-9]+ [0-9:]+ [^ ]+ partifi\/[^:]*: //' \
    -e 's/^api-[0-9]+ +\| //' \
    -e 's/^worker-[0-9]+ +\| //' \
    -e 's/^web-[0-9]+ +\| //' \
    | sed -E 's/^[[:space:]]+//'
}

fetch_error_lines() {
  if command -v journalctl >/dev/null 2>&1; then
    journalctl --since "${ERROR_HOURS} hours ago" --no-pager -r 2>/dev/null \
      | grep -E 'partifi-nextgen-(api|worker|web)' \
      | filter_error_lines \
      || true
    return
  fi
  compose logs --since "${ERROR_HOURS}h" api worker-1 worker-2 worker-3 web 2>&1 \
    | filter_error_lines \
    | tac 2>/dev/null \
    || true
}

print_deduped_errors() {
  local lines="$1"
  if [[ -z "$lines" ]]; then
    echo "none"
    return
  fi
  local deduped
  deduped="$(
    echo "$lines" \
      | normalize_error_key \
      | awk '{
          line = $0
          if (line ~ /sqlalchemy\.exc\.|pymysql\.err\./) {
            if (match(line, /(sqlalchemy|pymysql)\.[^:]+\: /)) {
              line = substr(line, RSTART)
            }
          } else if (line ~ /Exception in ASGI/) {
            line = "Exception in ASGI application"
          } else if (line ~ / ERROR:/) {
            sub(/^.* ERROR:[[:space:]]*/, "", line)
          }
          if (length(line) > 140) {
            line = substr(line, 1, 137) "..."
          }
          if (line != "") {
            counts[line]++
          }
        }
        END {
          for (k in counts) {
            printf "%d\t%s\n", counts[k], k
          }
        }' \
      | sort -rn -t $'\t' -k1,1 \
      | head -15
  )"
  if [[ -z "$deduped" ]]; then
    echo "none"
    return
  fi
  while IFS=$'\t' read -r count text; do
    printf '  %4dx  %s\n' "$count" "$text"
  done <<< "$deduped"
}

GENERATED_AT="$(date -u '+%Y-%m-%d %H:%M UTC')"
DEPLOY_REV="$(git rev-parse --short HEAD 2>/dev/null || echo '?')"

echo "Partifi diagnostics"
echo "Generated: ${GENERATED_AT}  |  deploy: ${DEPLOY_REV}"

# --- collect summary metrics ---
HEALTH_STATUS="fail"
if compose exec -T api python -c "
import json, urllib.request, sys
with urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=10) as r:
    data = json.load(r)
sys.exit(0 if data.get('status') == 'ok' else 1)
" >/dev/null 2>&1; then
  HEALTH_STATUS="ok"
elif compose exec -T api python -c "
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=10) as r:
    print(json.load(r).get('status', 'unknown'))
" 2>/dev/null | grep -q .; then
  HEALTH_STATUS="degraded"
fi

STUCK_COUNT="$(mysql_scalar "SELECT COUNT(*) FROM partsets WHERE ${STUCK_WHERE};")"
NEW_USERS_24H="$(mysql_scalar "SELECT COUNT(*) FROM users WHERE ts >= NOW() - INTERVAL 24 HOUR;")"
USER_COUNT="$(mysql_scalar "SELECT COUNT(*) FROM users;")"

QUEUE_PENDING="$(compose exec -T redis redis-cli LLEN partifi:jobs 2>/dev/null || echo '?')"
QUEUE_PROCESSING="$(compose exec -T redis redis-cli LLEN partifi:jobs:processing 2>/dev/null || echo '?')"

ERROR_LINES="$(fetch_error_lines)"
if [[ -n "$ERROR_LINES" ]]; then
  ERROR_COUNT="$(echo "$ERROR_LINES" | wc -l | tr -d ' ')"
else
  ERROR_COUNT=0
fi

# --- output ---
section "Health (/health/ready)"
if [[ "$HEALTH_STATUS" == "ok" ]]; then
  compose exec -T api python -c "
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=10) as r:
    data = json.load(r)
for name in sorted(data.get('checks', {})):
    value = data['checks'][name]
    mark = 'ok' if value == 'ok' else 'FAIL'
    print(f'  {name:6} {mark:4}  {value}')
" 2>/dev/null || echo "Health check failed (is the api container up?)"
else
  echo "Status: ${HEALTH_STATUS}"
  compose exec -T api python -c "
import json, urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=10) as r:
        data = json.load(r)
    for name in sorted(data.get('checks', {})):
        print(f'  {name}: {data[\"checks\"][name]}')
except Exception as exc:
    print(f'  (unreachable: {exc})')
" 2>/dev/null || echo "  (api unreachable)"
fi

section "Summary"
echo "  health:      ${HEALTH_STATUS}"
echo "  stuck:       ${STUCK_COUNT} (last ${DAYS}d)"
echo "  errors:      ${ERROR_COUNT} lines (${ERROR_HOURS}h)"
echo "  queue:       ${QUEUE_PENDING} pending / ${QUEUE_PROCESSING} processing"
echo "  users:       ${USER_COUNT} total (+${NEW_USERS_24H} in 24h)"

section "Failed / stuck partsets (last ${DAYS} days, newest first)"
if [[ "$STUCK_COUNT" == "0" ]]; then
  echo "none"
else
  mysql_query "
SELECT
  id,
  IF(CHAR_LENGTH(title) > 40, CONCAT(LEFT(title, 37), '...'), title) AS title,
  COALESCE(error_ts, paste_start, last_access, mod_ts, create_ts) AS activity_ts,
  COALESCE(error_message, error) AS error
FROM partsets
WHERE ${STUCK_WHERE}
ORDER BY activity_ts DESC;
"
fi

section "Recent errors (last ${ERROR_HOURS} hours, deduplicated)"
print_deduped_errors "$ERROR_LINES"

section "Activity"
echo "Last 24 hours:"
mysql_query "
SELECT
  (SELECT COUNT(*)
   FROM partsets
   WHERE paste_complete >= NOW() - INTERVAL 24 HOUR
     AND error IS NULL) AS partsets_generated,
  (SELECT COUNT(*)
   FROM parts p
   JOIN partsets ps ON ps.id = p.partset_id
   WHERE ps.paste_complete >= NOW() - INTERVAL 24 HOUR
     AND ps.error IS NULL) AS part_lines_generated,
  (SELECT COUNT(*)
   FROM partsets
   WHERE analysis_complete IS NOT NULL
     AND import_complete IS NOT NULL
     AND error IS NULL
     AND analysis_complete >= NOW() - INTERVAL 24 HOUR) AS imports_completed,
  (SELECT COUNT(*)
   FROM downloads
   WHERE ts >= NOW() - INTERVAL 24 HOUR) AS part_downloads;
"
echo ""
echo "Last ${DAYS} days:"
mysql_query "
SELECT
  (SELECT COUNT(*)
   FROM partsets
   WHERE paste_complete >= NOW() - INTERVAL ${DAYS} DAY
     AND error IS NULL) AS partsets_generated,
  (SELECT COUNT(*)
   FROM parts p
   JOIN partsets ps ON ps.id = p.partset_id
   WHERE ps.paste_complete >= NOW() - INTERVAL ${DAYS} DAY
     AND ps.error IS NULL) AS part_lines_generated,
  (SELECT COUNT(*)
   FROM partsets
   WHERE analysis_complete IS NOT NULL
     AND import_complete IS NOT NULL
     AND error IS NULL
     AND analysis_complete >= NOW() - INTERVAL ${DAYS} DAY) AS imports_completed,
  (SELECT COUNT(*)
   FROM downloads
   WHERE ts >= NOW() - INTERVAL ${DAYS} DAY) AS part_downloads;
"

section "Users (+${NEW_USERS_24H} in last 24h, total ${USER_COUNT})"
mysql_query "
SELECT id, name, given_name, ts
FROM users
ORDER BY ts DESC
LIMIT 20;
"

section "Recent part generation (last ${DAYS} days, newest first)"
mysql_query "
SELECT
  p.id,
  IF(CHAR_LENGTH(p.title) > 40, CONCAT(LEFT(p.title, 37), '...'), p.title) AS title,
  p.paste_complete,
  (SELECT COUNT(*) FROM parts pt WHERE pt.partset_id = p.id) AS num_parts
FROM partsets p
WHERE p.paste_complete >= NOW() - INTERVAL ${DAYS} DAY
  AND p.error IS NULL
ORDER BY p.paste_complete DESC
LIMIT 10;
"

section "Cache (/data/partifi)"
CACHE_DU="$(compose exec -T api du -sh /data/partifi 2>/dev/null | awk '{print $1}' || echo "?")"
CACHE_KB="$(compose exec -T api du -sk /data/partifi 2>/dev/null | awk '{print $1}' || echo "")"
CACHE_MAX_GB="${PARTIFI_CACHE_MAX_GB:-}"
if [[ -n "$CACHE_KB" && -n "$CACHE_MAX_GB" && "$CACHE_MAX_GB" =~ ^[0-9]+$ ]]; then
  CACHE_PCT="$(awk "BEGIN {printf \"%.0f\", ($CACHE_KB / 1024 / 1024) / $CACHE_MAX_GB * 100}")"
  echo "Total: ${CACHE_DU} / ${CACHE_MAX_GB}G cap (${CACHE_PCT}%)"
else
  echo "Total: ${CACHE_DU}"
fi
compose exec -T api du -sh /data/partifi/scores /data/partifi/preview /data/partifi/parts 2>/dev/null \
  || echo "could not read cache breakdown (is api up?)"

section "Containers"
compose ps
