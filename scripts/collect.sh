#!/usr/bin/env bash
# ------------------------------------------------------------------
# Runs one collection: fetch all platforms and save to the database.
# Cron calls this every night (see install_cron.sh).
# You can also run it by hand:  ./scripts/collect.sh
#
# Output goes to logs/collect_YYYY-MM.log (one file per month).
# ------------------------------------------------------------------
set -uo pipefail

# Find the project folder from where this script lives (works from anywhere, even from cron)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/collect_$(date +%Y-%m).log"
LOCK_DIR="/tmp/game-tracker-collect.lock"
PYTHON="$PROJECT_DIR/backend/.venv/bin/python"

mkdir -p "$LOG_DIR"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S %Z') | $*" >> "$LOG_FILE"; }

# Lock: if the previous run is somehow still going, don't start a second one at the same time.
# (mkdir is "all or nothing", so only one run can create the folder.)
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  log "SKIPPED: another collection is still running (remove $LOCK_DIR if that's wrong)"
  exit 1
fi
trap 'rmdir "$LOCK_DIR"' EXIT   # always remove the lock when this script ends

if [ ! -x "$PYTHON" ]; then
  log "FAILED: $PYTHON not found. Create it: cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

log "===== START ====="
cd "$PROJECT_DIR/backend"
"$PYTHON" -m app.cli collect --trigger scheduled >> "$LOG_FILE" 2>&1
STATUS=$?
log "===== END (exit code $STATUS: $([ $STATUS -eq 0 ] && echo OK || echo PROBLEM)) ====="
exit $STATUS
