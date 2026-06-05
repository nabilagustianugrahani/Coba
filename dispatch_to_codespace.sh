#!/usr/bin/env bash
# dispatch_to_codespace.sh
# Dispatch a task to a codespace from the configured pool.
#
# Usage:
#   ./dispatch_to_codespace.sh "Build a new feature X"
#   ./dispatch_to_codespace.sh --codespace pool-2-zen "Run tests"
#   ./dispatch_to_codespace.sh --list
#   ./dispatch_to_codespace.sh --status
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POOL_JSON="${POOL_JSON:-$SCRIPT_DIR/.opencode/codespace_pool.json}"

usage() {
    cat <<'EOF'
Usage: dispatch_to_codespace.sh [options] "<task description>"

Options:
  --codespace <name>    Force dispatch to a specific codespace (skips round-robin)
  --list                List pool members and exit
  --status              Show pool health status and exit
  --timeout <seconds>   SSH timeout (default: 600)
  -h, --help            Show this help

Environment:
  POOL_JSON             Path to codespace_pool.json (default: ./.opencode/codespace_pool.json)
EOF
}

if [ $# -eq 0 ]; then
    usage
    exit 1
fi

CODESPACE=""
TIMEOUT="600"
MODE="dispatch"
TASK=""

while [ $# -gt 0 ]; do
    case "$1" in
        --codespace) CODESPACE="$2"; shift 2 ;;
        --timeout) TIMEOUT="$2"; shift 2 ;;
        --list) MODE="list"; shift ;;
        --status) MODE="status"; shift ;;
        -h|--help) usage; exit 0 ;;
        --) shift; TASK="$*"; break ;;
        *) TASK="$1"; shift ;;
    esac
done

if [ ! -f "$POOL_JSON" ]; then
    echo "[dispatch] ERROR: pool config not found at $POOL_JSON" >&2
    exit 2
fi

PYTHON="${PYTHON:-python3}"

case "$MODE" in
    list)
        "$PYTHON" -c "
import json, sys
with open('$POOL_JSON') as f:
    cfg = json.load(f)
for m in cfg['pool']:
    print(f\"{m['name']:18s} model={m['model']:40s} region={m.get('region','-'):10s} machine={m.get('machine','-')}\")
"
        ;;
    status)
        "$PYTHON" - <<PY
import json, sys
sys.path.insert(0, '$SCRIPT_DIR')
from ugc_ai_overpower.core.codespace_pool import CodespacePool
pool = CodespacePool('$POOL_JSON')
for s in pool.pool_status():
    flag = 'OK' if s['healthy'] else 'DOWN'
    err = f" err={s['error']}" if s.get('error') else ''
    print(f"[{flag}] {s['name']:18s} state={s['state']:12s} model={s['model']}{err}")
PY
        ;;
    dispatch)
        if [ -z "$TASK" ]; then
            echo "[dispatch] ERROR: task description required" >&2
            usage
            exit 1
        fi
        "$PYTHON" - "$TASK" <<PY
import json, sys
sys.path.insert(0, '$SCRIPT_DIR')
from ugc_ai_overpower.core.codespace_pool import CodespacePool
pool = CodespacePool('$POOL_JSON')
task = sys.argv[1]
cs = None
forced = "$CODESPACE"
if forced:
    matches = [m for m in pool.pool if m['name'] == forced]
    if not matches:
        print(f"[dispatch] ERROR: codespace '{forced}' not in pool", file=sys.stderr)
        sys.exit(2)
    cs = matches[0]
result = pool.dispatch_task(task, codespace=cs, timeout=$TIMEOUT)
print(json.dumps(result, indent=2))
sys.exit(result.get('returncode', 1))
PY
        ;;
esac
