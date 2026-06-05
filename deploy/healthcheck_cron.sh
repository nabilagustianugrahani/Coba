#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# Periodic health check — runs in codespace
# Alerts Notion Inbox on failure
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

WORKDIR="/workspaces/Coba"
LOGFILE="/tmp/healthcheck.log"
HEALTH_SCRIPT="$WORKDIR/ugc_ai_overpower/core/health_monitor.py"

if [[ ! -f "$HEALTH_SCRIPT" ]]; then
    WORKDIR="/workspaces/ugc_ai_overpower"
    HEALTH_SCRIPT="$WORKDIR/ugc_ai_overpower/core/health_monitor.py"
fi

if [[ ! -f "$HEALTH_SCRIPT" ]]; then
    echo "[$(date -Iseconds)] health_monitor.py not found — skipping"
    exit 0
fi

cd "$WORKDIR"
PYTHONPATH="$WORKDIR" python3 -m ugc_ai_overpower.core.health_monitor check >> "$LOGFILE" 2>&1 || \
    PYTHONPATH="$WORKDIR" python3 -m ugc_ai_overpower.core.health_monitor check >> "$LOGFILE" 2>&1
