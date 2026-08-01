#!/usr/bin/env bash
# Email a 24h Partifi usage / error summary via Amazon SES (run on EC2 from repo root).
#
# Usage:
#   ./scripts/daily-summary.sh
#   DRY_RUN=1 ./scripts/daily-summary.sh
#   HOURS=48 ./scripts/daily-summary.sh
#
# Requires .env with MYSQL_PASSWORD, SES_FROM, SES_TO (and optional SES_REGION).
# EC2 instance role (or S3_* keys) must allow ses:SendEmail / ses:SendRawEmail.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
HOURS="${HOURS:-24}"
DRY_RUN="${DRY_RUN:-0}"
MAX_LOG_LINES="${MAX_LOG_LINES:-20}"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

filter_error_lines() {
  grep -iE ' ERROR |exception|failed|timed out|exit 137(\s|$)|\bOOM\b|Out of memory|Traceback|ValueError|Could not' \
    | grep -viE 'aborting with incomplete response|http2: stream closed|repaired or ignored|The following errors were encountered|Page drawing error occurred|Output may be incorrect|IMSLP HTTP failure.*attempt [0-9]+/[0-9]+|pdf_resolve retry in|PDF download retry in' \
    || true
}

collect_journal_errors() {
  if command -v journalctl >/dev/null 2>&1; then
    journalctl --since "${HOURS} hours ago" --no-pager -r 2>/dev/null \
      | grep -E 'partifi-nextgen-(api|worker|web)' \
      | filter_error_lines \
      | head -n "$MAX_LOG_LINES" \
      || true
    return
  fi
  compose logs --since "${HOURS}h" api worker-1 worker-2 worker-3 web 2>&1 \
    | tac 2>/dev/null \
    | filter_error_lines \
    | head -n "$MAX_LOG_LINES" \
    || true
}

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT
collect_journal_errors >"$TMPDIR/log_errors.txt"

REBOOT_REQUIRED=0
REBOOT_REQUIRED_PKGS=""
if [[ -e /run/reboot-required || -e /var/run/reboot-required ]]; then
  REBOOT_REQUIRED=1
  for pkgs_file in /run/reboot-required.pkgs /var/run/reboot-required.pkgs; do
    if [[ -f "$pkgs_file" ]]; then
      # Package names only; keep the env value short for compose exec.
      # head the file first so pipefail cannot abort on SIGPIPE from a long list.
      REBOOT_REQUIRED_PKGS="$(head -c 400 "$pkgs_file" | tr '\n\r' '  ' | tr -s ' ')"
      break
    fi
  done
fi

ARGS=(python -m jobs.daily_summary --hours "$HOURS" --log-file /tmp/partifi-daily-summary-logs.txt)
if [[ "$DRY_RUN" == "1" ]]; then
  ARGS+=(--dry-run)
fi

# Copy filtered logs into the worker, then run the job.
compose exec -T worker-1 sh -c 'cat > /tmp/partifi-daily-summary-logs.txt' <"$TMPDIR/log_errors.txt"
compose exec -T \
  -e "REBOOT_REQUIRED=${REBOOT_REQUIRED}" \
  -e "REBOOT_REQUIRED_PKGS=${REBOOT_REQUIRED_PKGS}" \
  worker-1 "${ARGS[@]}"
