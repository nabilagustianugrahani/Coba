#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# Codespace auto-pipeline fail-safe restart
# Triggered by codespace postStart OR on cron interval
# Ensures auto-pipeline daemon is alive in the codespace
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

WORKDIR="/workspaces/Coba"
PIDFILE="/tmp/ugc_autopipeline.pid"
LOGFILE="/tmp/auto-pipeline.log"
PYTHONPATH="$WORKDIR"
DAEMON_CMD="python3 -m ugc_ai_overpower.main auto-pipeline start"

# Only run in codespace container
if [[ ! -d "$WORKDIR" ]]; then
    echo "[restart_daemon] $WORKDIR not mounted — not a codespace, skipping"
    exit 0
fi

is_running() {
    [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null
}

start_daemon() {
    echo "[restart_daemon] Starting auto-pipeline daemon at $(date -Iseconds)"
    cd "$WORKDIR"
    PYTHONPATH="$WORKDIR" nohup $DAEMON_CMD > "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    sleep 3
    if is_running; then
        echo "[restart_daemon] ✅ Daemon started (PID $(cat "$PIDFILE"))"
        return 0
    fi
    echo "[restart_daemon] ❌ Daemon failed to start. Tail of log:"
    tail -20 "$LOGFILE" || true
    return 1
}

if is_running; then
    UPTIME_SEC=$(( $(date +%s) - $(stat -c %Y "$PIDFILE" 2>/dev/null || echo 0) ))
    echo "[restart_daemon] ✅ Daemon alive (PID $(cat "$PIDFILE"), up ${UPTIME_SEC}s)"
    exit 0
fi

# Stale PID file?
if [[ -f "$PIDFILE" ]]; then
    echo "[restart_daemon] Stale PID file $(cat "$PIDFILE") — removing"
    rm -f "$PIDFILE"
fi

start_daemon
