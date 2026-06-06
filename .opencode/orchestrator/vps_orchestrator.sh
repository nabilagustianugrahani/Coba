#!/bin/bash
# VPS-side multi-codespace orchestrator
# Usage: ./vps_orchestrator.sh <command> [args]
#
# Commands:
#   list                          - list all codespaces
#   status                        - show all opencode sessions across codespaces
#   dispatch <cs> <task>          - dispatch task to specific codespace
#   broadcast <task>              - dispatch same task to all codespaces
#   parallel <task> <cs1,cs2,...> - dispatch to specific list
#   logs <cs> <session>           - tail logs
#   kill <cs> <pid>               - kill session
#
# Codespace registry at ~/.orchestrator/codespaces.json

set -e

ORCH_DIR="$HOME/.orchestrator"
CS_REGISTRY="$ORCH_DIR/codespaces.json"
LOG_DIR="$ORCH_DIR/logs"
mkdir -p "$LOG_DIR"

# Get auth token
TOKEN=$(grep oauth_token ~/.config/gh/hosts.yml 2>/dev/null | head -1 | awk '{print $2}')
[ -z "$TOKEN" ] && { echo "No GH token found"; exit 1; }

# Default codespaces (use the ones we have)
DEFAULT_CS=("symmetrical-palm-tree-5gpr979vgv6jhvqr" "opencode-3-big-pjqw6567j9g9hg96")

cmd="${1:-help}"
shift || true

case "$cmd" in
  list)
    gh codespace list 2>&1
    ;;
  status)
    echo "=== Codespaces status ==="
    gh codespace list --json name,state,gitStatus 2>/dev/null | python3 -c "
import sys, json
for cs in json.load(sys.stdin):
    if 'Coba' in cs.get('name','') or 'ugc' in cs.get('name',''):
        print(f\"  {cs['name']:50s} {cs['state']:10s}\")"
    echo ""
    echo "=== Active opencode sessions per codespace ==="
    for cs in "${DEFAULT_CS[@]}"; do
      ACTIVE=$(gh codespace ssh -c "$cs" -- "ps -ef | grep -E '/opencode/bin/opencode' | grep -v grep | wc -l" 2>&1 | tail -1)
      echo "  $cs: $ACTIVE active sessions"
    done
    ;;
  dispatch)
    CS="$1"
    TASK="$2"
    [ -z "$CS" ] || [ -z "$TASK" ] && { echo "Usage: dispatch <cs> <task>"; exit 1; }
    TASK_FILE=$(mktemp)
    echo "$TASK" > "$TASK_FILE"
    B64=$(base64 -w0 "$TASK_FILE")
    rm "$TASK_FILE"
    SESSION_ID=$(date +%s)
    LOG="$LOG_DIR/cs-${CS//\//_}-${SESSION_ID}.log"
    gh codespace ssh -c "$CS" -- "echo '$B64' | base64 -d > /tmp/task-$SESSION_ID.md && nohup ~/.opencode/bin/opencode run --model opencode/minimax-m3-free --agent build \"\$(cat /tmp/task-$SESSION_ID.md)\" > /tmp/orch-$SESSION_ID.log 2>&1 & echo \$! > /tmp/orch-$SESSION_ID.pid && echo Session: $SESSION_ID PID: \$(cat /tmp/orch-$SESSION_ID.pid)" 2>&1
    echo "$LOG"
    echo "Session ID: $SESSION_ID on $CS"
    ;;
  broadcast)
    TASK="$1"
    [ -z "$TASK" ] && { echo "Usage: broadcast <task>"; exit 1; }
    for cs in "${DEFAULT_CS[@]}"; do
      echo "=== Dispatching to $cs ==="
      "$0" dispatch "$cs" "$TASK"
      sleep 10
    done
    ;;
  parallel)
    TASK="$1"
    CSLIST="$2"
    [ -z "$TASK" ] || [ -z "$CSLIST" ] && { echo "Usage: parallel <task> <cs1,cs2,...>"; exit 1; }
    IFS=',' read -ra CS_ARRAY <<< "$CSLIST"
    for cs in "${CS_ARRAY[@]}"; do
      echo "=== Dispatching to $cs ==="
      "$0" dispatch "$cs" "$TASK"
      sleep 10
    done
    ;;
  logs)
    CS="$1"
    SESSION="$2"
    [ -z "$CS" ] || [ -z "$SESSION" ] && { echo "Usage: logs <cs> <session_id>"; exit 1; }
    gh codespace ssh -c "$CS" -- "tail -f /tmp/orch-$SESSION.log" 2>&1
    ;;
  kill)
    CS="$1"
    SESSION="$2"
    [ -z "$CS" ] || [ -z "$SESSION" ] && { echo "Usage: kill <cs> <session_id>"; exit 1; }
    gh codespace ssh -c "$CS" -- "PID=\$(cat /tmp/orch-$SESSION.pid 2>/dev/null); if [ -n \"\$PID\" ]; then kill \$PID 2>/dev/null && echo Killed \$PID || echo Not running; fi"
    ;;
  help|*)
    echo "VPS Multi-Codespace Orchestrator"
    echo ""
    echo "Commands:"
    echo "  list                          List all codespaces"
    echo "  status                        Show codespace + session status"
    echo "  dispatch <cs> <task>          Dispatch task to one codespace"
    echo "  broadcast <task>              Same task to all default codespaces"
    echo "  parallel <task> <cs1,cs2,...> Dispatch to specific list"
    echo "  logs <cs> <session>           Tail session log"
    echo "  kill <cs> <session>           Kill session"
    echo ""
    echo "Default codespaces: ${DEFAULT_CS[*]}"
    ;;
esac
