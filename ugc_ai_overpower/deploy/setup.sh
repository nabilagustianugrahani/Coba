#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "=== Skynet Deployment ==="
echo "App dir: $APP_DIR"
cd "$APP_DIR"

# ── Dependencies ──────────────────────────────────────────────────
echo "[1/5] Installing Python dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt 2>/dev/null || true

# ── DB migration ──────────────────────────────────────────────────
echo "[2/5] Initializing database..."
python3 -c "from core.content_bank import ContentBank; ContentBank(); print('DB OK')"

# ── Systemd services ─────────────────────────────────────────────
echo "[3/5] Installing systemd services..."

mkdir -p ~/.config/systemd/user/

# Copy service files
for svc in dashboard scheduler; do
    cp "deploy/${svc}.service" ~/.config/systemd/user/skynet-${svc}.service
    chmod 644 ~/.config/systemd/user/skynet-${svc}.service
done

systemctl --user daemon-reload

# Enable & start
for svc in dashboard scheduler; do
    systemctl --user enable skynet-${svc}.service 2>/dev/null || true
    systemctl --user restart skynet-${svc}.service 2>/dev/null || true
    echo "  ✅ skynet-${svc}.service"
done

# ── Affiliate config ─────────────────────────────────────────────
echo "[4/5] Creating affiliate config..."
mkdir -p data
if [ ! -f data/affiliate_config.json ]; then
    echo '{"shopee":{"af_id":"","track_id":""},"tokopedia":{"af_id":"","track_id":""},"lazada":{"af_id":"","track_id":""},"sociolla":{"af_id":"","track_id":""},"blibli":{"af_id":"","track_id":""}}' \
        > data/affiliate_config.json
fi

# ── Status ────────────────────────────────────────────────────────
echo "[5/5] Checking services..."
sleep 2
for svc in dashboard scheduler; do
    status=$(systemctl --user is-active skynet-${svc}.service 2>/dev/null || echo "inactive")
    echo "  skynet-${svc}: $status"
done

echo ""
echo "=== Done ==="
echo "Dashboard: http://localhost:8111"
echo "Login: admin / admin123"
echo ""
echo "Commands:"
echo "  systemctl --user status skynet-dashboard"
echo "  systemctl --user status skynet-scheduler"
echo "  journalctl --user -u skynet-dashboard -f"
echo "  journalctl --user -u skynet-scheduler -f"
