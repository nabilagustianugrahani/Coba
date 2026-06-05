#!/bin/bash
# UGC AI Overpower — Codespace Auto-Launcher
# Starts auto-pipeline daemon + MCP server + FastAPI dashboard in background.
# Run this after SSH-ing into a GitHub Codespace.

set -e
echo "=== UGC AI Overpower — Codespace Auto-Launcher ==="

# ---------------------------------------------------------------------------
# Paths — Codespace devcontainer mounts the package at /workspaces/...
# ---------------------------------------------------------------------------
CODESPACE_DIR="/workspaces/ugc_ai_overpower"
LOCAL_DIR="/home/aer/ugc"

# Pick whichever path actually exists (Codespace vs. local).
if [ -n "$UGC_PROJECT_DIR" ] && [ -d "$UGC_PROJECT_DIR" ]; then
    PROJECT_DIR="$UGC_PROJECT_DIR"
elif [ -d "$CODESPACE_DIR" ]; then
    PROJECT_DIR="$CODESPACE_DIR"
elif [ -d "$LOCAL_DIR" ]; then
    PROJECT_DIR="$LOCAL_DIR"
else
    echo "ERROR: project directory not found at $CODESPACE_DIR or $LOCAL_DIR"
    exit 1
fi
cd "$PROJECT_DIR"

# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
AUTOPIPELINE_LOG="$LOG_DIR/auto-pipeline.log"
MCP_LOG="$LOG_DIR/mcp-server.log"
DASHBOARD_LOG="$LOG_DIR/dashboard.log"
AUTOPIPELINE_PID="$LOG_DIR/auto-pipeline.pid"
MCP_PID="$LOG_DIR/mcp-server.pid"
DASHBOARD_PID="$LOG_DIR/dashboard.pid"

# Pick a Python interpreter. Codespace image has `python`; Debian systems
# only ship `python3`. Honor $PYTHON override first.
if [ -n "$PYTHON" ] && command -v "$PYTHON" >/dev/null 2>&1; then
    PY="$PYTHON"
elif command -v python >/dev/null 2>&1; then
    PY="python"
elif command -v python3 >/dev/null 2>&1; then
    PY="python3"
else
    echo "ERROR: no python interpreter found"
    exit 1
fi
echo "    using interpreter: $PY"

# ---------------------------------------------------------------------------
# 1. Environment
# ---------------------------------------------------------------------------
echo "[1/6] Setting up environment..."

# Activate venv if present (Codespace image usually has no venv, but allow override).
if [ -d "$PROJECT_DIR/.venv" ]; then
    # shellcheck disable=SC1091
    source "$PROJECT_DIR/.venv/bin/activate"
    echo "    activated .venv"
elif [ -d "$PROJECT_DIR/venv" ]; then
    # shellcheck disable=SC1091
    source "$PROJECT_DIR/venv/bin/activate"
    echo "    activated venv"
fi

# Pull .env from vscode home if it exists, otherwise project .env.
if [ -f /home/vscode/.env ] && [ ! -f "$PROJECT_DIR/.env" ]; then
    cp /home/vscode/.env "$PROJECT_DIR/.env"
fi
if [ -f "$PROJECT_DIR/.env" ]; then
    # shellcheck disable=SC1091
    set -a; source "$PROJECT_DIR/.env"; set +a
    echo "    loaded .env"
fi

# ---------------------------------------------------------------------------
# 2. Dependencies
# ---------------------------------------------------------------------------
echo "[2/6] Checking Python dependencies..."
if $PY -c "import apscheduler, fastapi, mcp" 2>/dev/null; then
    echo "    all deps present"
else
    echo "    installing missing packages..."
    # PEP 668 (externally-managed env) needs --break-system-packages on
    # Ubuntu 22.04+ base images. The Codespace devcontainer uses the same
    # image, so this branch is hit both locally and in Codespace.
    pip install --quiet -r requirements.txt \
        ${PIP_BREAK_SYSTEM_PACKAGES:+--break-system-packages}
fi

# ---------------------------------------------------------------------------
# 3. OpenCode config (so other agents can attach)
# ---------------------------------------------------------------------------
echo "[3/6] Configuring OpenCode..."
if [ -d /home/vscode ]; then
    mkdir -p /home/vscode/.config/opencode
    if [ -f "$PROJECT_DIR/.opencode.json" ] && [ ! -f /home/vscode/.config/opencode/config.json ]; then
        cp "$PROJECT_DIR/.opencode.json" /home/vscode/.config/opencode/config.json
    fi
else
    echo "    [skip] /home/vscode not present (not a Codespace)"
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
is_running() {
    local pidfile="$1"
    [ -f "$pidfile" ] || return 1
    local pid
    pid=$(cat "$pidfile" 2>/dev/null)
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

start_bg() {
    local name="$1"
    local pidfile="$2"
    local logfile="$3"
    shift 3
    if is_running "$pidfile"; then
        echo "    [skip] $name already running (pid=$(cat "$pidfile"))"
        return 0
    fi
    echo "    [start] $name"
    nohup "$@" >>"$logfile" 2>&1 &
    echo $! >"$pidfile"
    sleep 1
    if is_running "$pidfile"; then
        echo "             pid=$(cat "$pidfile")  log=$logfile"
    else
        echo "             FAILED to start — check $logfile"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# 4. Auto-Pipeline Daemon
# ---------------------------------------------------------------------------
echo "[4/6] Starting Auto-Pipeline daemon..."
start_bg "auto-pipeline" "$AUTOPIPELINE_PID" "$AUTOPIPELINE_LOG" \
    $PY -m ugc_ai_overpower.main auto-pipeline start

# ---------------------------------------------------------------------------
# 5. MCP server (for A2A / external agents)
# ---------------------------------------------------------------------------
echo "[5/6] Starting MCP server..."
start_bg "mcp-server" "$MCP_PID" "$MCP_LOG" \
    $PY -m ugc_ai_overpower.main server

# ---------------------------------------------------------------------------
# 6. FastAPI dashboard (if defined in main.py)
# ---------------------------------------------------------------------------
echo "[6/6] Starting FastAPI dashboard..."
if $PY -c "import fastapi, uvicorn" 2>/dev/null; then
    start_bg "dashboard" "$DASHBOARD_PID" "$DASHBOARD_LOG" \
        $PY -m uvicorn ugc_ai_overpower.web.app:app \
            --host 0.0.0.0 --port 8000 --log-level info
else
    echo "    [skip] fastapi/uvicorn not installed"
fi

# ---------------------------------------------------------------------------
# Status banner
# ---------------------------------------------------------------------------
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║        UGC AI OVERPOWER — CODESSPACE READY              ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Auto-pipeline  →  tail -f $AUTOPIPELINE_LOG"
echo "║  MCP server     →  tail -f $MCP_LOG"
echo "║  Dashboard      →  tail -f $DASHBOARD_LOG"
echo "║                                                          ║"
echo "║  Stop everything:                                       ║"
echo "║    kill \$(cat $AUTOPIPELINE_PID)   # auto-pipeline       "
echo "║    kill \$(cat $MCP_PID)           # mcp                  "
echo "║    kill \$(cat $DASHBOARD_PID)     # dashboard            "
echo "║                                                          ║"
echo "║  Status check:                                          ║"
echo "║    python -m ugc_ai_overpower.main auto-pipeline status ║"
echo "╚══════════════════════════════════════════════════════════╝"
