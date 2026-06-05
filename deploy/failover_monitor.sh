#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# Codespace pool failover healthcheck
# Checks primary codespace; if down, activates failover
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

POOL_FILE="$(dirname "$0")/../.opencode/codespace_pool.json"
PRIMARY=$(jq -r '.pool[] | select(.role == "primary") | .codespace' "$POOL_FILE" 2>/dev/null)
FAILOVERS=$(jq -r '.pool[] | select(.role == "failover") | .codespace' "$POOL_FILE" 2>/dev/null)
THRESHOLD=$(jq -r '.scheduler.failover_threshold_failures' "$POOL_FILE" 2>/dev/null)
COOLDOWN=$(jq -r '.scheduler.failover_cooldown_seconds' "$POOL_FILE" 2>/dev/null)
STATE_FILE="/tmp/ugc_failover_state.json"

is_healthy() {
    local cs="$1"
    gh codespace ssh -c "$cs" -- "echo ok" 2>/dev/null | grep -q "ok"
}

count_failures() {
    [[ -f "$STATE_FILE" ]] && jq -r '.failures // 0' "$STATE_FILE" || echo 0
}

set_failures() {
    local n="$1"
    cat > "$STATE_FILE" <<EOF
{"failures": $n, "last_check": "$(date -Iseconds)", "active": "$(jq -r '.active // "primary"' "$STATE_FILE" 2>/dev/null)"}
EOF
}

main() {
    if [[ -z "$PRIMARY" ]]; then
        echo "[failover] no primary configured in $POOL_FILE"
        exit 1
    fi

    if is_healthy "$PRIMARY"; then
        set_failures 0
        echo "[failover] ✅ primary healthy ($PRIMARY)"
        exit 0
    fi

    local failures=$(( $(count_failures) + 1 ))
    set_failures "$failures"
    echo "[failover] primary unhealthy (failure $failures/$THRESHOLD)"

    if [[ "$failures" -lt "$THRESHOLD" ]]; then
        exit 0
    fi

    echo "[failover] ⚠️  threshold reached — activating failover"
    while IFS= read -r fcs; do
        [[ -z "$fcs" ]] && continue
        echo "[failover] trying failover: $fcs"
        if ! gh codespace list --json name,state 2>/dev/null | jq -e ".[] | select(.name == \"$fcs\" and .state == \"Available\")" > /dev/null; then
            echo "[failover] starting $fcs..."
            gh codespace start -c "$fcs" 2>&1 | tail -3 || true
            sleep 30
        fi
        if is_healthy "$fcs"; then
            jq -n --arg a "$fcs" '{active: $a, activated_at: (now | todate)}' > "$STATE_FILE"
            echo "[failover] ✅ failover active: $fcs"
            gh codespace ssh -c "$fcs" -- "nohup /tmp/ugc-restart > /tmp/ugc-restart-failover.log 2>&1 &"
            exit 0
        fi
    done <<< "$FAILOVERS"

    echo "[failover] ❌ all failovers exhausted"
    exit 1
}

main "$@"
