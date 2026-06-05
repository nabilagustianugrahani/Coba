#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/aer/ugc"
DEPLOY_DIR="${PROJECT_DIR}/deploy"
SERVICE_NAME="ugc-autopipeline"
SERVICE_SRC="${DEPLOY_DIR}/${SERVICE_NAME}.service"
SERVICE_DST="/etc/systemd/system/${SERVICE_NAME}.service"
LOGROTATE_SRC="${DEPLOY_DIR}/logrotate.conf"
LOGROTATE_DST="/etc/logrotate.d/${SERVICE_NAME}"
MONITOR_SCRIPT="${DEPLOY_DIR}/monitor.sh"
CRON_FILE="/etc/cron.d/${SERVICE_NAME}-monitor"

if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: must run as root (sudo $0)" >&2
    exit 1
fi

echo "=== Installing ${SERVICE_NAME} ==="

# ── 1. systemd service ─────────────────────────────────────────────
echo "[1/4] Installing systemd service..."
cp -f "${SERVICE_SRC}" "${SERVICE_DST}"
chmod 644 "${SERVICE_DST}"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"
systemctl restart "${SERVICE_NAME}.service"
sleep 1
systemctl --no-pager --full status "${SERVICE_NAME}.service" | sed -n '1,8p' || true

# ── 2. logrotate ───────────────────────────────────────────────────
echo "[2/4] Installing logrotate config..."
cp -f "${LOGROTATE_SRC}" "${LOGROTATE_DST}"
chmod 644 "${LOGROTATE_DST}"
logrotate -d "${LOGROTATE_DST}" 2>&1 | sed -n '1,5p' || true

# ── 3. monitor cron ────────────────────────────────────────────────
echo "[3/4] Installing monitor cron entry (every 5 min)..."
chmod +x "${MONITOR_SCRIPT}"
cat > "${CRON_FILE}" <<EOF
# UGC auto-pipeline monitor — runs every 5 minutes
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
PYTHONPATH=${PROJECT_DIR}
NOTION_TOKEN=${NOTION_TOKEN:-}

*/5 * * * * aer ${MONITOR_SCRIPT} >> /home/aer/logs/monitor.log 2>&1
EOF
chmod 644 "${CRON_FILE}"
# Ensure cron daemon is running (Debian/Ubuntu path; adjust for other distros)
if command -v systemctl >/dev/null 2>&1; then
    systemctl enable --now cron 2>/dev/null || systemctl enable --now crond 2>/dev/null || true
fi

# ── 4. verify ──────────────────────────────────────────────────────
echo "[4/4] Verifying install..."
sleep 2
if systemctl is-active --quiet "${SERVICE_NAME}.service"; then
    echo "  service: active"
else
    echo "  service: INACTIVE (check: journalctl -u ${SERVICE_NAME} -n 50)" >&2
fi
echo "  logrotate: ${LOGROTATE_DST}"
echo "  cron:      ${CRON_FILE}"
echo "=== Done ==="
echo
echo "Useful commands:"
echo "  systemctl status ${SERVICE_NAME}"
echo "  journalctl -u ${SERVICE_NAME} -f"
echo "  tail -f ${PROJECT_DIR}/logs/auto-pipeline.log"
echo "  tail -f ${PROJECT_DIR}/logs/monitor.log"
