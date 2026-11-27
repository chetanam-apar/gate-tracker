#!/usr/bin/env bash
# Removes the nightly job from cron. Other cron jobs are not touched.
set -euo pipefail

MARKER="# game-tracker nightly collect"
( crontab -l 2>/dev/null | grep -v "$MARKER" || true ) | crontab -
echo "Removed. The nightly job will not run anymore."
