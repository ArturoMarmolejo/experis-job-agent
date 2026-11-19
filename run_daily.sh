#!/usr/bin/env bash
# Daily run: discover new Experis jobs, then build today's report.
# Started by Windows Task Scheduler; all output goes to logs/daily_<date>.log
set -euo pipefail                      # stop at the first failing step

cd "$HOME/experis-job-agent"
# Only one run at a time: a second copy exits immediately instead of clashing on jobs.db
exec 9>/tmp/experis_daily.lock
if ! flock -n 9; then
    echo "=== skipped $(date '+%F %T'): another run is in progress ===" >> "logs/daily_$(date +%F).log"
    exit 0
fi
source .venv/bin/activate
mkdir -p logs
LOG="logs/daily_$(date +%F).log"

{
  echo "=== run started  $(date '+%F %T') ==="
  python -m scraper.run_discovery
  python -m scraper.report
  echo "=== run finished $(date '+%F %T') ==="
} >> "$LOG" 2>&1
