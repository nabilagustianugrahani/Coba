#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/aer/ugc"
PID_FILE="${PROJECT_DIR}/logs/auto-pipeline.pid"
LOG_DIR="${PROJECT_DIR}/logs"
MONITOR_LOG="${LOG_DIR}/monitor.log"
SERVICE_NAME="ugc-autopipeline"

mkdir -p "${LOG_DIR}"

log() {
    local ts
    ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "${ts} $*" | tee -a "${MONITOR_LOG}"
}

is_process_alive() {
    local pid="$1"
    [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null
}

send_notion_alert() {
    local subject="$1"
    local body="$2"
    if [[ -z "${NOTION_TOKEN:-}" ]]; then
        log "NOTION_TOKEN not set; skipping Notion alert"
        return 1
    fi
    (
        cd "${PROJECT_DIR}"
        NOTION_TOKEN="${NOTION_TOKEN}" \
        PYTHONPATH="${PROJECT_DIR}" \
        UGC_ALERT_SUBJECT="${subject}" \
        UGC_ALERT_BODY="${body}" \
        /usr/bin/python3 - <<'PY'
import os, datetime, sys
try:
    from ugc_ai_overpower.core.notion_sync import NotionDashboard
except Exception as e:
    print(f"[monitor] Notion import failed: {e}", file=sys.stderr)
    sys.exit(1)

nd = NotionDashboard()
if not nd.ready:
    print("[monitor] Notion not ready (no token)", file=sys.stderr)
    sys.exit(1)

now = datetime.datetime.utcnow().isoformat() + "Z"
subject = os.environ.get("UGC_ALERT_SUBJECT", "")
body = os.environ.get("UGC_ALERT_BODY", "")

if nd.inbox_db:
    props = {
        "Content": {"title": nd._format_title(subject[:100])},
        "Platform": {"select": {"name": "system"}},
        "Sender": {"rich_text": nd._format_rich("monitor.sh")},
        "Account": {"rich_text": nd._format_rich("ugc-autopipeline")},
        "Type": {"select": {"name": "alert"}},
        "Sentiment": {"select": {"name": "neutral"}},
        "AI Reply": {"rich_text": nd._format_rich(body[:200])},
        "Replied": {"checkbox": False},
        "Is Read": {"checkbox": False},
        "Created At": {"date": {"start": now}},
    }
    result = nd._request("POST", "pages", {"parent": {"database_id": nd.inbox_db}, "properties": props})
    pid = result.get("id")
    if pid:
        print(f"[monitor] Notion alert created: {pid}")
    else:
        print(f"[monitor] Notion alert failed: {result}", file=sys.stderr)
        sys.exit(1)
else:
    print("[monitor] NOTION_INBOX_DB not set; cannot post alert", file=sys.stderr)
    sys.exit(1)
PY
    ) || log "Notion alert failed"
}

# ── Main check ────────────────────────────────────────────────────────
if [[ ! -f "${PID_FILE}" ]]; then
    log "ALERT: PID file missing at ${PID_FILE}"
    send_notion_alert \
        "[UGC] Auto-pipeline DOWN — PID file missing" \
        "Monitor detected that ${PID_FILE} is absent on $(hostname). Service ${SERVICE_NAME} may have crashed before writing its PID."
    exit 1
fi

PID="$(cat "${PID_FILE}" 2>/dev/null || true)"
if ! is_process_alive "${PID}"; then
    log "ALERT: process ${PID} from ${PID_FILE} is not running"
    send_notion_alert \
        "[UGC] Auto-pipeline DOWN — process ${PID} not alive" \
        "Monitor detected that PID ${PID} from ${PID_FILE} is not alive. Check: systemctl status ${SERVICE_NAME}; journalctl -u ${SERVICE_NAME} -n 50"
    exit 1
fi

log "OK: auto-pipeline running (pid=${PID})"
exit 0
