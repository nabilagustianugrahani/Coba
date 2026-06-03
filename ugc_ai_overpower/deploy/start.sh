#!/usr/bin/env bash
# Start Skynet services (works on containers/VPS where systemd user services fail)
set -eo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHONPATH_ROOT="$(dirname "$APP_DIR")"
PID_DIR="$APP_DIR/data/pids"
mkdir -p "$PID_DIR"

stop_all() {
    echo "Stopping all services..."
    for pidfile in "$PID_DIR"/*.pid; do
        [ -f "$pidfile" ] || continue
        pid=$(cat "$pidfile")
        kill "$pid" 2>/dev/null || true
        rm -f "$pidfile"
    done
    echo "All stopped."
}

start_dashboard() {
    local log="$APP_DIR/data/logs/dashboard.log"
    mkdir -p "$(dirname "$log")"
    cd "$APP_DIR"
    PYTHONPATH="$PYTHONPATH_ROOT:${PYTHONPATH:-}" nohup python3 -m uvicorn web.dashboard:app --host 0.0.0.0 --port 8111 \
        > "$log" 2>&1 &
    echo $! > "$PID_DIR/dashboard.pid"
    echo "Dashboard started (PID: $!) -> http://localhost:8111"
}

start_scheduler() {
    local log="$APP_DIR/data/logs/scheduler.log"
    mkdir -p "$(dirname "$log")"
    cd "$APP_DIR"
    PYTHONPATH="$PYTHONPATH_ROOT:${PYTHONPATH:-}" nohup python3 deploy/run_scheduler.py \
        > "$log" 2>&1 &
    echo $! > "$PID_DIR/scheduler.pid"
    echo "Scheduler started (PID: $!)"
}

case "${1:-start}" in
    start)
        stop_all
        sleep 1
        cd "$APP_DIR"
        export PYTHONPATH="$PYTHONPATH_ROOT:${PYTHONPATH:-}"
        export ROUTER_URL="${ROUTER_URL:-http://localhost:20128}"
        export ROUTER_KEY="${ROUTER_KEY:-sk-8028a980b0c7366a-4a45za-36eef5ef}"
        start_dashboard
        start_scheduler
        echo "---"
        echo "All services started. Logs:"
        echo "  tail -f $APP_DIR/data/logs/dashboard.log"
        echo "  tail -f $APP_DIR/data/logs/scheduler.log"
        ;;
    stop)
        stop_all
        ;;
    restart)
        "$0" stop
        sleep 2
        "$0" start
        ;;
    status)
        for pidfile in "$PID_DIR"/*.pid; do
            [ -f "$pidfile" ] || continue
            svc=$(basename "$pidfile" .pid)
            pid=$(cat "$pidfile")
            if kill -0 "$pid" 2>/dev/null; then
                echo "  $svc: running (PID: $pid)"
            else
                echo "  $svc: dead"
                rm -f "$pidfile"
            fi
        done
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
