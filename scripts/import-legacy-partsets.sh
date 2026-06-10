#!/usr/bin/env bash
# Run the legacy partset import via the API virtualenv.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/api"
exec uv run python ../scripts/migrate_legacy_data.py "$@"
