#!/usr/bin/env bash
# Production health snapshot (run on EC2 from repo root).
#
# Usage:
#   ./scripts/diagnostics.sh
#   DAYS=7 ./scripts/diagnostics.sh
#   VERIFY=1 ./scripts/diagnostics.sh   # re-run scalar SQL individually; warn on mismatch
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

filter_mysql_noise() {
  grep -v 'Using a password on the command line interface can be insecure' || true
}

mysql_scalar() {
  compose exec -T mysql mysql -u partifi -p"$MYSQL_PASSWORD" \
    --default-character-set=utf8mb4 \
    -N \
    partifi -e "$1" 2>&1 \
    | filter_mysql_noise \
    | head -1 \
    || echo "?"
}

mysql_query_table() {
  compose exec -T mysql mysql -u partifi -p"$MYSQL_PASSWORD" \
    --default-character-set=utf8mb4 \
    --table \
    partifi -e "$1" 2>&1 | filter_mysql_noise
}

mysql_query() {
  compose exec -T mysql mysql -u partifi -p"$MYSQL_PASSWORD" \
    --default-character-set=utf8mb4 \
    partifi -e "$1" 2>&1 | filter_mysql_noise
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
    | grep -viE 'aborting with incomplete response|http2: stream closed|repaired or ignored|The following errors were encountered|Page drawing error occurred|Output may be incorrect|IMSLP HTTP failure.*attempt [0-9]+/[0-9]+|pdf_resolve retry in|PDF download retry in'
}

fetch_full_journal() {
  if command -v journalctl >/dev/null 2>&1; then
    journalctl --since "${ERROR_HOURS} hours ago" --no-pager -r 2>/dev/null \
      | grep -E 'partifi-nextgen-(api|worker|web)' \
      || true
    return
  fi
  compose logs --since "${ERROR_HOURS}h" api worker-1 worker-2 worker-3 web 2>&1 \
    | tac 2>/dev/null \
    || true
}

service_journal_from_full() {
  local full="$1"
  if command -v journalctl >/dev/null 2>&1; then
    echo "$full" | grep -E 'partifi-nextgen-(api|worker)' || true
    return
  fi
  echo "$full" | grep -Ev '^partifi-nextgen-web-[0-9]+[[:space:]]*\|' || true
}

filter_imslp_issue_lines() {
  # Final failures and API rejections only (no retry / disclaimer noise).
  grep -iE \
'partsets/imslp HTTP/1.1" (400|500)|import rejected: score too large|PDF URL resolution failed during pre-import check|index HTML missing PDF link|IMSLP import failed for partset|did not return a PDF|corrupt or incomplete|IMSLP HTTP failure .*failed after|IMSLP HTTP failure operation=(pdf_resolve|pre_import_pdf_resolve|pre_import_pdf_head|pdf_download) imslp_id=' \
    | grep -viE 'attempt [0-9]+/[0-9]+|pdf_resolve retry in|PDF download retry in|mirror PML-(Asia|US|CA) (disclaimer|placeholder)' \
    || true
}

count_journal_lines() {
  if [[ -z "${1:-}" ]]; then
    echo 0
  else
    echo "$1" | wc -l | tr -d ' '
  fi
}

IMSLP_FAILED_WHERE="
  imslp_id IS NOT NULL
  AND (
    error IN ('import', 'import_size')
    OR (
      status = 'import'
      AND import_complete IS NULL
      AND create_ts < NOW() - INTERVAL 1 HOUR
    )
  )
  AND create_ts >= NOW() - INTERVAL ${DAYS} DAY
"

IMSLP_IMPORT_ERROR_WINDOW="
  imslp_id IS NOT NULL
  AND error IN ('import', 'import_size')
  AND COALESCE(error_ts, create_ts) >= NOW() - INTERVAL ${ERROR_HOURS} HOUR
"

IMSLP_LEGACY_LINK_ERROR_SQL="
  error = 'import'
  AND error_message LIKE 'This IMSLP link doesn%'
"

fetch_mysql_summary_metrics() {
  compose exec -T mysql mysql -u partifi -p"$MYSQL_PASSWORD" \
    --default-character-set=utf8mb4 \
    -N \
    partifi 2>&1 <<EOF | filter_mysql_noise
SELECT 'stuck_count', COUNT(*) FROM partsets WHERE ${STUCK_WHERE};
SELECT 'new_users_24h', COUNT(*) FROM users WHERE ts >= NOW() - INTERVAL 24 HOUR;
SELECT 'user_count', COUNT(*) FROM users;
SELECT 'imslp_attempted', COUNT(*) FROM partsets WHERE imslp_id IS NOT NULL AND create_ts >= NOW() - INTERVAL ${ERROR_HOURS} HOUR;
SELECT 'imslp_created_analyzed', COUNT(*) FROM partsets WHERE imslp_id IS NOT NULL AND create_ts >= NOW() - INTERVAL ${ERROR_HOURS} HOUR AND analysis_complete IS NOT NULL AND error IS NULL;
SELECT 'imslp_succeeded', COUNT(*) FROM partsets WHERE imslp_id IS NOT NULL AND analysis_complete IS NOT NULL AND error IS NULL AND analysis_complete >= NOW() - INTERVAL ${ERROR_HOURS} HOUR;
SELECT 'imslp_import_errors_total', COUNT(*) FROM partsets WHERE ${IMSLP_IMPORT_ERROR_WINDOW};
SELECT 'imslp_import_legacy_link', COUNT(*) FROM partsets WHERE ${IMSLP_IMPORT_ERROR_WINDOW} AND ${IMSLP_LEGACY_LINK_ERROR_SQL};
SELECT 'imslp_import_fail', COUNT(*) FROM partsets WHERE ${IMSLP_IMPORT_ERROR_WINDOW} AND error = 'import' AND (error_message IS NULL OR error_message NOT LIKE 'This IMSLP link doesn%');
SELECT 'imslp_import_too_large', COUNT(*) FROM partsets WHERE ${IMSLP_IMPORT_ERROR_WINDOW} AND error = 'import_size';
SELECT 'imslp_failed_count', COUNT(*) FROM partsets WHERE ${IMSLP_FAILED_WHERE};
EOF
}

load_mysql_summary_metrics() {
  local metrics_file="$1"
  STUCK_COUNT="?"
  NEW_USERS_24H="?"
  USER_COUNT="?"
  IMSLP_ATTEMPTED="?"
  IMSLP_CREATED_ANALYZED="?"
  IMSLP_SUCCEEDED="?"
  IMSLP_IMPORT_ERRORS_TOTAL="?"
  IMSLP_IMPORT_LEGACY_LINK="?"
  IMSLP_IMPORT_FAIL="?"
  IMSLP_IMPORT_TOO_LARGE="?"
  IMSLP_FAILED_COUNT="?"

  while IFS=$'\t' read -r key value; do
    [[ -z "${key:-}" ]] && continue
    case "$key" in
      stuck_count) STUCK_COUNT="$value" ;;
      new_users_24h) NEW_USERS_24H="$value" ;;
      user_count) USER_COUNT="$value" ;;
      imslp_attempted) IMSLP_ATTEMPTED="$value" ;;
      imslp_created_analyzed) IMSLP_CREATED_ANALYZED="$value" ;;
      imslp_succeeded) IMSLP_SUCCEEDED="$value" ;;
      imslp_import_errors_total) IMSLP_IMPORT_ERRORS_TOTAL="$value" ;;
      imslp_import_legacy_link) IMSLP_IMPORT_LEGACY_LINK="$value" ;;
      imslp_import_fail) IMSLP_IMPORT_FAIL="$value" ;;
      imslp_import_too_large) IMSLP_IMPORT_TOO_LARGE="$value" ;;
      imslp_failed_count) IMSLP_FAILED_COUNT="$value" ;;
    esac
  done < "$metrics_file"
}

verify_mysql_summary_metrics() {
  local expected_key="$1"
  local expected_value="$2"
  local query="$3"
  local actual
  actual="$(mysql_scalar "$query")"
  if [[ "$actual" != "$expected_value" ]]; then
    echo "VERIFY mismatch for ${expected_key}: batched=${expected_value} scalar=${actual}" >&2
  fi
}

collect_health() {
  local out="$1"
  if compose exec -T api python -c "
import json, urllib.request, sys
with urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=10) as r:
    data = json.load(r)
sys.exit(0 if data.get('status') == 'ok' else 1)
" >/dev/null 2>&1; then
    echo ok >"$out"
  elif compose exec -T api python -c "
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=10) as r:
    print(json.load(r).get('status', 'unknown'))
" 2>/dev/null | grep -q .; then
    echo degraded >"$out"
  else
    echo fail >"$out"
  fi
}

collect_redis() {
  local out="$1"
  {
    compose exec -T redis redis-cli LLEN partifi:jobs 2>/dev/null || echo '?'
    compose exec -T redis redis-cli LLEN partifi:jobs:processing 2>/dev/null || echo '?'
  } >"$out"
}

collect_cache() {
  local du_out="$1"
  local kb_out="$2"
  local raw="${du_out}.raw"
  compose exec -T api sh -c '
    du -sh /data/partifi /data/partifi/scores /data/partifi/preview /data/partifi/parts 2>/dev/null
    du -sk /data/partifi 2>/dev/null | awk "{print \$1}"
  ' >"$raw" 2>/dev/null || true
  if [[ -s "$raw" ]]; then
    tail -n 1 "$raw" >"$kb_out"
    head -n -1 "$raw" >"$du_out"
  else
    : >"$du_out"
    : >"$kb_out"
  fi
}

GENERATED_AT="$(date -u '+%Y-%m-%d %H:%M UTC')"
DEPLOY_REV="$(git rev-parse --short HEAD 2>/dev/null || echo '?')"

echo "Partifi diagnostics"
echo "Generated: ${GENERATED_AT}  |  deploy: ${DEPLOY_REV}"

# --- collect summary metrics (parallel where safe) ---
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

collect_health "$TMPDIR/health" &
health_pid=$!
fetch_full_journal >"$TMPDIR/journal_full" &
journal_pid=$!
fetch_mysql_summary_metrics >"$TMPDIR/mysql_metrics" &
mysql_pid=$!
collect_redis "$TMPDIR/redis" &
redis_pid=$!
collect_cache "$TMPDIR/cache_du" "$TMPDIR/cache_kb" &
cache_pid=$!

set +e
wait "$health_pid" "$journal_pid" "$mysql_pid" "$redis_pid" "$cache_pid"
set -e

HEALTH_STATUS="$(cat "$TMPDIR/health" 2>/dev/null || echo fail)"
FULL_JOURNAL="$(cat "$TMPDIR/journal_full" 2>/dev/null || true)"
load_mysql_summary_metrics "$TMPDIR/mysql_metrics"
QUEUE_PENDING="$(sed -n '1p' "$TMPDIR/redis" 2>/dev/null || echo '?')"
QUEUE_PROCESSING="$(sed -n '2p' "$TMPDIR/redis" 2>/dev/null || echo '?')"

ERROR_LINES="$(echo "$FULL_JOURNAL" | filter_error_lines || true)"
if [[ -n "$ERROR_LINES" ]]; then
  ERROR_COUNT="$(echo "$ERROR_LINES" | wc -l | tr -d ' ')"
else
  ERROR_COUNT=0
fi

SERVICE_JOURNAL="$(service_journal_from_full "$FULL_JOURNAL")"
IMSLP_ISSUE_LINES="$(echo "$SERVICE_JOURNAL" | filter_imslp_issue_lines)"
IMSLP_API_OK="$(count_journal_lines "$(echo "$SERVICE_JOURNAL" | grep 'POST /api/v1/partsets/imslp HTTP/1.1" 200' || true)")"
IMSLP_API_FAIL="$(count_journal_lines "$(echo "$SERVICE_JOURNAL" | grep -E 'POST /api/v1/partsets/imslp HTTP/1.1" (400|500)' || true)")"
IMSLP_ACTIONABLE_FAIL=$((IMSLP_IMPORT_FAIL + IMSLP_IMPORT_TOO_LARGE))

if [[ "${VERIFY:-}" == 1 ]]; then
  verify_mysql_summary_metrics stuck_count "$STUCK_COUNT" "SELECT COUNT(*) FROM partsets WHERE ${STUCK_WHERE};"
  verify_mysql_summary_metrics new_users_24h "$NEW_USERS_24H" "SELECT COUNT(*) FROM users WHERE ts >= NOW() - INTERVAL 24 HOUR;"
  verify_mysql_summary_metrics user_count "$USER_COUNT" "SELECT COUNT(*) FROM users;"
  verify_mysql_summary_metrics imslp_attempted "$IMSLP_ATTEMPTED" "SELECT COUNT(*) FROM partsets WHERE imslp_id IS NOT NULL AND create_ts >= NOW() - INTERVAL ${ERROR_HOURS} HOUR;"
  verify_mysql_summary_metrics imslp_created_analyzed "$IMSLP_CREATED_ANALYZED" "SELECT COUNT(*) FROM partsets WHERE imslp_id IS NOT NULL AND create_ts >= NOW() - INTERVAL ${ERROR_HOURS} HOUR AND analysis_complete IS NOT NULL AND error IS NULL;"
  verify_mysql_summary_metrics imslp_succeeded "$IMSLP_SUCCEEDED" "SELECT COUNT(*) FROM partsets WHERE imslp_id IS NOT NULL AND analysis_complete IS NOT NULL AND error IS NULL AND analysis_complete >= NOW() - INTERVAL ${ERROR_HOURS} HOUR;"
  verify_mysql_summary_metrics imslp_import_errors_total "$IMSLP_IMPORT_ERRORS_TOTAL" "SELECT COUNT(*) FROM partsets WHERE ${IMSLP_IMPORT_ERROR_WINDOW};"
  verify_mysql_summary_metrics imslp_import_legacy_link "$IMSLP_IMPORT_LEGACY_LINK" "SELECT COUNT(*) FROM partsets WHERE ${IMSLP_IMPORT_ERROR_WINDOW} AND ${IMSLP_LEGACY_LINK_ERROR_SQL};"
  verify_mysql_summary_metrics imslp_import_fail "$IMSLP_IMPORT_FAIL" "SELECT COUNT(*) FROM partsets WHERE ${IMSLP_IMPORT_ERROR_WINDOW} AND error = 'import' AND (error_message IS NULL OR error_message NOT LIKE 'This IMSLP link doesn%');"
  verify_mysql_summary_metrics imslp_import_too_large "$IMSLP_IMPORT_TOO_LARGE" "SELECT COUNT(*) FROM partsets WHERE ${IMSLP_IMPORT_ERROR_WINDOW} AND error = 'import_size';"
  verify_mysql_summary_metrics imslp_failed_count "$IMSLP_FAILED_COUNT" "SELECT COUNT(*) FROM partsets WHERE ${IMSLP_FAILED_WHERE};"
fi

# --- output ---
section "Summary"
echo "  health:      ${HEALTH_STATUS}"
echo "  imslp API:   ${IMSLP_API_OK} ok / ${IMSLP_API_FAIL} fail (POST /partsets/imslp, last ${ERROR_HOURS}h)"
echo "  imslp DB:    ${IMSLP_ATTEMPTED} created / ${IMSLP_CREATED_ANALYZED} analyzed (of those) / ${IMSLP_IMPORT_ERRORS_TOTAL} import errors (DB)"
echo "  stuck:       ${STUCK_COUNT} (last ${DAYS}d)"
echo "  errors:      ${ERROR_COUNT} lines (${ERROR_HOURS}h)"
echo "  queue:       ${QUEUE_PENDING} pending / ${QUEUE_PROCESSING} processing"
echo "  users:       ${USER_COUNT} total (+${NEW_USERS_24H} in 24h)"

section "IMSLP imports (last ${ERROR_HOURS}h)"
echo "  API:         ${IMSLP_API_OK} POST 200 / ${IMSLP_API_FAIL} POST 4xx-5xx"
echo "  created:     ${IMSLP_ATTEMPTED} partsets (should match POST 200)"
echo "  analyzed:    ${IMSLP_CREATED_ANALYZED} of those created / ${IMSLP_SUCCEEDED} total finished in window"
echo "  import err:  ${IMSLP_IMPORT_ERRORS_TOTAL} in DB (legacy link: ${IMSLP_IMPORT_LEGACY_LINK}, import fail: ${IMSLP_IMPORT_FAIL}, too large: ${IMSLP_IMPORT_TOO_LARGE})"
echo "               (includes API-marked failures; legacy link = unimportable old IMSLP URLs)"
echo ""
echo "IMSLP failures (newest first):"
if [[ -n "$IMSLP_ISSUE_LINES" ]]; then
  echo "$IMSLP_ISSUE_LINES"
else
  echo "(no matching lines)"
fi
echo ""
echo "Failed IMSLP partsets (last ${DAYS}d, newest first):"
if [[ "$IMSLP_FAILED_COUNT" == "0" ]]; then
  echo "none"
else
  mysql_query "
SELECT error_ts, id, imslp_id, title, error, error_message
FROM partsets
WHERE ${IMSLP_FAILED_WHERE}
ORDER BY COALESCE(error_ts, create_ts) DESC;
"
fi

section "Failed / stuck partsets (last ${DAYS} days, newest first)"
if [[ "$STUCK_COUNT" == "0" ]]; then
  echo "none"
else
  mysql_query "
SELECT error_ts, id, title, error_message
FROM partsets
WHERE ${STUCK_WHERE}
ORDER BY COALESCE(error_ts, paste_start, mod_ts, last_access, create_ts) DESC;
"
fi

section "Recent errors (last ${ERROR_HOURS} hours, newest first)"
if [[ -n "$ERROR_LINES" ]]; then
  echo "$ERROR_LINES"
else
  echo "(no matching lines)"
  if [[ "$IMSLP_ACTIONABLE_FAIL" -gt 0 ]]; then
    echo "(note: ${IMSLP_ACTIONABLE_FAIL} actionable import error(s) in DB with no matching journal lines — logs may have rotated; see IMSLP failures / Failed IMSLP partsets above)"
  fi
fi

section "Activity"
echo "Last 24 hours:"
mysql_query_table "
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
mysql_query_table "
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
mysql_query_table "
SELECT id, name, given_name, ts
FROM users
ORDER BY ts DESC
LIMIT 20;
"

section "Recent part generation (last ${DAYS} days, newest first)"
mysql_query_table "
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
CACHE_DU="$(awk 'NR == 1 {print $1}' "$TMPDIR/cache_du" 2>/dev/null || echo "?")"
CACHE_KB="$(cat "$TMPDIR/cache_kb" 2>/dev/null || echo "")"
CACHE_MAX_GB="${PARTIFI_CACHE_MAX_GB:-}"
if [[ -n "$CACHE_KB" && -n "$CACHE_MAX_GB" && "$CACHE_MAX_GB" =~ ^[0-9]+$ ]]; then
  CACHE_PCT="$(awk "BEGIN {printf \"%.0f\", ($CACHE_KB / 1024 / 1024) / $CACHE_MAX_GB * 100}")"
  echo "Total: ${CACHE_DU} / ${CACHE_MAX_GB}G cap (${CACHE_PCT}%)"
else
  echo "Total: ${CACHE_DU}"
fi
if [[ -s "$TMPDIR/cache_du" ]]; then
  tail -n +2 "$TMPDIR/cache_du"
else
  echo "could not read cache breakdown (is api up?)"
fi
