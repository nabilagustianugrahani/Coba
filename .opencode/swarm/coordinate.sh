#!/bin/bash
# Swarm coordinator: spawn N opencode sessions in parallel
# Usage: ./coordinate.sh <count> <task_file>
# Each session writes to logs/session-{i}.log

set -e
COUNT="${1:-3}"
TASK_FILE="${2:-/tmp/task.md}"

if [ ! -f "$TASK_FILE" ]; then
  echo "Task file not found: $TASK_FILE"
  exit 1
fi

cd /workspaces/Coba
mkdir -p .opencode/logs

# Stagger starts to avoid rate-limit bursts
for i in $(seq 1 $COUNT); do
  (
    ~/.opencode/bin/opencode run --model opencode/minimax-m3-free \
      --agent build \
      "$(cat $TASK_FILE)" \
      > .opencode/logs/session-$i.log 2>&1
  ) &
  echo "Spawned session $i (PID $!)"
  sleep 2  # 2s stagger to spread requests
done

echo "All $COUNT sessions launched. Monitor with: tail -f .opencode/logs/session-*.log"
