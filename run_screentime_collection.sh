#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

export PYTHONUNBUFFERED=1
LOG_FILE="$LOG_DIR/collection_$(date +%Y%m%d_%H%M%S).log"
LAUNCHD_LOG="$LOG_DIR/launchd.log"

exec > >(tee -a "$LOG_FILE" "$LAUNCHD_LOG") 2>&1

echo "Starting Screen Time collection at $(date)"
echo "Script directory: $SCRIPT_DIR"
echo "Knowledge DB: $HOME/Library/Application Support/Knowledge/knowledgeC.db"
echo "Biome DB: $HOME/Library/Biome/sync/sync.db"

if [[ -f "$HOME/Library/Application Support/Knowledge/knowledgeC.db" ]]; then
  echo "knowledgeC.db exists"
else
  echo "knowledgeC.db not found"
fi

if [[ -f "$HOME/Library/Biome/sync/sync.db" ]]; then
  echo "sync.db exists"
else
  echo "sync.db not found"
fi

python3 "$SCRIPT_DIR/collect_screentime.py"
echo "Completed at $(date)"

if [[ -f "$SCRIPT_DIR/logs/last_run.status" ]]; then
  echo "Last run status:"
  cat "$SCRIPT_DIR/logs/last_run.status"
fi

# Keep only the most recent 10 logs.
ls -t "$LOG_DIR/collection_"*.log 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null
