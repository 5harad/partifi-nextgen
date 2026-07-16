#!/usr/bin/env bash
# Migrate MySQL from the Docker named volume to a dedicated EBS mount.
#
# Prerequisites:
#   - New EBS volume formatted, mounted at TARGET (default /mnt/mysql-ebs), in /etc/fstab
#   - Run from repo root on prod EC2 (~/partifi-nextgen)
#   - .env with MYSQL_ROOT_PASSWORD (and MYSQL_PASSWORD for smoke tests)
#
# Usage:
#   ./scripts/migrate_mysql_to_ebs.sh pass1              # bulk copy while MySQL is running
#   ./scripts/migrate_mysql_to_ebs.sh pass1 --dry-run    # show rsync plan only
#   ./scripts/migrate_mysql_to_ebs.sh cutover            # stop stack, final rsync, switch mount
#   ./scripts/migrate_mysql_to_ebs.sh cutover --dry-run  # print steps; rsync dry-run only
#   ./scripts/migrate_mysql_to_ebs.sh cutover --force    # re-sync from old volume (dangerous)
#
# Rollback (if cutover fails before you delete the old volume):
#   1. docker compose -f docker-compose.prod.yml stop api worker-1 worker-2 worker-3 web mysql
#   2. Restore docker-compose.prod.yml from docker-compose.prod.yml.bak.*
#   3. docker compose -f docker-compose.prod.yml up -d
#   The old mysql_data volume is untouched until you remove it manually.
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
TARGET="${TARGET:-/mnt/mysql-ebs}"
MYSQL_VOLUME="${MYSQL_VOLUME:-partifi-nextgen_mysql_data}"
DRY_RUN=0
FORCE=0

MYSQL_DEPENDENT_SERVICES=(api worker-1 worker-2 worker-3 web)

usage() {
  sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

confirm() {
  local prompt="$1"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] would confirm: $prompt"
    return 0
  fi
  read -r -p "$prompt [y/N] " reply
  [[ "$reply" =~ ^[Yy]$ ]]
}

compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

rsync_mysql_data() {
  local label="$1"
  local extra_flags=("${@:2}")
  echo ""
  echo "=== rsync $label: $SOURCE/ -> $TARGET/ ==="
  if [[ "$DRY_RUN" -eq 1 ]]; then
    sudo rsync -aHAX --numeric-ids --info=progress2 --dry-run \
      "${extra_flags[@]}" \
      "$SOURCE/" "$TARGET/"
  else
    sudo rsync -aHAX --numeric-ids --info=progress2 \
      "${extra_flags[@]}" \
      "$SOURCE/" "$TARGET/"
  fi
}

wait_for_mysql() {
  local attempts="${1:-60}"
  echo "Waiting for MySQL healthcheck..."
  for ((i = 1; i <= attempts; i++)); do
    if compose ps mysql 2>/dev/null | grep -q '(healthy)'; then
      echo "MySQL is healthy."
      return 0
    fi
    sleep 2
  done
  echo "MySQL did not become healthy in time." >&2
  compose ps mysql || true
  compose logs --tail=50 mysql || true
  return 1
}

mysql_smoke_test() {
  if [[ -z "${MYSQL_PASSWORD:-}" ]]; then
    echo "Skipping app-user smoke test (MYSQL_PASSWORD not set)."
    return 0
  fi
  echo "Smoke test: SELECT COUNT(*) FROM partsets ..."
  local output count status=0
  output=$(compose exec -T mysql mysql -u partifi -p"$MYSQL_PASSWORD" \
    --default-character-set=utf8mb4 \
    -N partifi -e "SELECT COUNT(*) FROM partsets;" 2>&1) || status=$?
  if [[ "$status" -ne 0 ]]; then
    echo "$output" | grep -v 'Using a password on the command line interface can be insecure' >&2 || true
    echo "Smoke test failed (mysql exit $status)." >&2
    return 1
  fi
  count=$(echo "$output" | grep -v 'Using a password on the command line interface can be insecure' | tr -d '[:space:]')
  if [[ ! "$count" =~ ^[0-9]+$ ]]; then
    echo "Smoke test failed: unexpected output: $output" >&2
    return 1
  fi
  echo "partsets count: $count"
}

patch_compose_for_bind_mount() {
  local backup="${COMPOSE_FILE}.bak.$(date +%Y%m%d%H%M%S)"
  if grep -q '/var/lib/mysql' "$COMPOSE_FILE" && grep -q 'mysql_data:/var/lib/mysql' "$COMPOSE_FILE"; then
    cp "$COMPOSE_FILE" "$backup"
    echo "Backed up compose file to $backup"
    sed -i.tmp 's|- mysql_data:/var/lib/mysql|- '"$TARGET"':/var/lib/mysql|' "$COMPOSE_FILE"
    rm -f "${COMPOSE_FILE}.tmp"
    echo "Updated $COMPOSE_FILE:"
    grep -n '/var/lib/mysql' "$COMPOSE_FILE" || true
    return 0
  fi
  if grep -q "$TARGET:/var/lib/mysql" "$COMPOSE_FILE"; then
    echo "Compose already points MySQL at $TARGET — no patch needed."
    return 0
  fi
  echo "Could not find 'mysql_data:/var/lib/mysql' in $COMPOSE_FILE — patch manually." >&2
  return 1
}

compose_uses_bind_mount() {
  grep -qF "$TARGET:/var/lib/mysql" "$COMPOSE_FILE"
}

check_target_disk_space() {
  local source_bytes target_used_bytes avail_bytes buffer_bytes=$((1024 * 1024 * 1024))
  local effective_capacity required

  source_bytes=$(sudo du -sb "$SOURCE" | awk '{print $1}')
  target_used_bytes=$(sudo du -sb "$TARGET" | awk '{print $1}')
  avail_bytes=$(df -B1 --output=avail "$TARGET" | tail -1 | tr -d '[:space:]')
  effective_capacity=$((avail_bytes + target_used_bytes))
  required=$((source_bytes + buffer_bytes))

  echo "Source size: $((source_bytes / 1024 / 1024 / 1024)) GiB (+ 1 GiB buffer)"
  echo "Target free: $((avail_bytes / 1024 / 1024 / 1024)) GiB (used on target: $((target_used_bytes / 1024 / 1024 / 1024)) GiB)"

  if [[ "$effective_capacity" -lt "$required" ]]; then
    echo "Not enough space on $TARGET." >&2
    echo "Need ~$((required / 1024 / 1024 / 1024)) GiB capacity; effective $((effective_capacity / 1024 / 1024 / 1024)) GiB (free + already copied)." >&2
    exit 1
  fi
}

preflight() {
  if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "Missing $COMPOSE_FILE (run from repo root)." >&2
    exit 1
  fi

  if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
  fi

  if ! docker volume inspect "$MYSQL_VOLUME" >/dev/null 2>&1; then
    echo "Docker volume not found: $MYSQL_VOLUME" >&2
    echo "Set MYSQL_VOLUME if the name differs." >&2
    exit 1
  fi

  SOURCE="$(docker volume inspect "$MYSQL_VOLUME" --format '{{.Mountpoint}}')"
  if [[ ! -d "$SOURCE" ]]; then
    echo "Source datadir missing: $SOURCE" >&2
    exit 1
  fi

  if [[ ! -d "$TARGET" ]]; then
    echo "Target mount missing: $TARGET" >&2
    exit 1
  fi

  if ! mountpoint -q "$TARGET"; then
    echo "Target is not mounted: $TARGET" >&2
    echo "Run: sudo mount $TARGET  (or fix /etc/fstab)" >&2
    exit 1
  fi

  echo "Source: $SOURCE ($(sudo du -sh "$SOURCE" 2>/dev/null | awk '{print $1}'))"
  echo "Target: $TARGET ($(sudo du -sh "$TARGET" 2>/dev/null | awk '{print $1}'))"
  check_target_disk_space
}

pass1() {
  preflight
  echo ""
  echo "Pass 1 copies data while MySQL is running. Users are not interrupted."
  echo "Run this in tmux; it may take a while."
  confirm "Start pass 1 rsync now?" || exit 0
  rsync_mysql_data "pass 1"
  echo ""
  echo "Pass 1 complete. When ready for downtime, run:"
  echo "  ./scripts/migrate_mysql_to_ebs.sh cutover"
}

stop_mysql_dependents() {
  echo ""
  echo "=== Stopping services that use MySQL ==="
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] compose stop ${MYSQL_DEPENDENT_SERVICES[*]}"
    return 0
  fi
  compose stop "${MYSQL_DEPENDENT_SERVICES[@]}"
}

stop_mysql() {
  echo ""
  echo "=== Stopping MySQL ==="
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] compose stop mysql"
    return 0
  fi
  compose stop mysql
}

start_stack() {
  echo ""
  echo "=== Starting full stack ==="
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] compose up -d"
    return 0
  fi
  compose up -d
}

cutover() {
  preflight

  if compose_uses_bind_mount; then
    if [[ "$FORCE" -eq 0 ]]; then
      echo "Compose already points MySQL at $TARGET — cutover appears complete." >&2
      echo "Re-running would rsync stale data from the old Docker volume with --delete." >&2
      echo "Use --force only if you intentionally need to re-copy from $MYSQL_VOLUME." >&2
      exit 1
    fi
    echo ""
    echo "WARNING: --force set; will rsync from old Docker volume over $TARGET."
    confirm "Continue with destructive re-sync?" || exit 0
  fi

  echo ""
  echo "Cutover stops prod briefly, runs a final rsync, and points MySQL at $TARGET."
  echo "Schedule a maintenance window (~5–15 min if pass 1 was recent)."
  confirm "Proceed with cutover?" || exit 0

  stop_mysql_dependents
  stop_mysql

  # --delete: target should mirror source exactly before we switch the mount.
  rsync_mysql_data "pass 2 (final)" --delete

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] would patch compose and start stack"
    exit 0
  fi

  echo ""
  confirm "Rsync looks good. Patch compose and start MySQL on $TARGET?" || {
    echo "Aborted. MySQL is still stopped. Old data is unchanged on $SOURCE."
    echo "Restart with: docker compose -f $COMPOSE_FILE up -d"
    exit 1
  }

  patch_compose_for_bind_mount

  start_stack
  wait_for_mysql
  mysql_smoke_test

  echo ""
  echo "Cutover complete."
  echo "  - MySQL is on $TARGET"
  echo "  - Old volume $MYSQL_VOLUME is still on disk for rollback"
  echo "  - Do NOT remove the old volume until you've verified prod for several days"
  echo "  - Consider setting binlog retention in prod.cnf after you're confident"
}

main() {
  local mode="${1:-}"
  shift || true

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) DRY_RUN=1 ;;
      --force) FORCE=1 ;;
      -h|--help) usage 0 ;;
      *) echo "Unknown option: $1" >&2; usage 1 ;;
    esac
    shift
  done

  case "$mode" in
    pass1) pass1 ;;
    cutover) cutover ;;
    ""|-h|--help) usage 0 ;;
    *) echo "Unknown mode: $mode (expected pass1 or cutover)" >&2; usage 1 ;;
  esac
}

main "$@"
