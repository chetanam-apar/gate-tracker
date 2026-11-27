#!/usr/bin/env bash
# ------------------------------------------------------------------
# Adds the nightly job to cron, at the time set in config.yaml
# (schedule -> daily_run_time). Safe to run again: it replaces the old entry.
#
#   ./scripts/install_cron.sh      add or update the job
#   crontab -l                     see it
#   ./scripts/uninstall_cron.sh    remove it
#
# Cron uses this computer's time zone. Your Mac is in IST, so "00:00" = 12 AM IST.
# ------------------------------------------------------------------
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$PROJECT_DIR/backend/.venv/bin/python"
MARKER="# game-tracker nightly collect"

# Read "00:00" from config.yaml using our own app (so the time lives in ONE place)
RUN_TIME="$(cd "$PROJECT_DIR/backend" && "$PYTHON" -m app.cli schedule-time)"
HOUR="${RUN_TIME%%:*}"
MINUTE="${RUN_TIME##*:}"

# Cron line: minute hour day-of-month month day-of-week command
# The path is in quotes because the folder name has spaces.
LINE="$((10#$MINUTE)) $((10#$HOUR)) * * * \"$PROJECT_DIR/scripts/collect.sh\" $MARKER"

# Keep every other cron job, remove our old line, add the new one
( crontab -l 2>/dev/null | grep -v "$MARKER" || true; echo "$LINE" ) | crontab -

chmod +x "$PROJECT_DIR/scripts/collect.sh"

echo "Installed. The job runs every day at $RUN_TIME (this computer's time zone: $(date +%Z))."
echo "Your cron entry:"
crontab -l | grep "$MARKER"
