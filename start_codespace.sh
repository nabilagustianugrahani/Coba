#!/bin/bash
# UGC Swarm 2.0 — Codespace Startup Script
# Jalankan ini pertama kali setelah SSH ke codespace

set -e
echo "=== UGC Swarm 2.0 — Codespace Setup ==="

# 1. Setup env
echo "[1/5] Setup environment..."
cd /workspaces/ugc_ai_overpower
cp /home/vscode/.env .env 2>/dev/null || true

# 2. Install dependencies
echo "[2/5] Install Python dependencies..."
pip install --quiet -r requirements.txt

# 3. Setup opencode config
echo "[3/5] Setup OpenCode config..."
mkdir -p /home/vscode/.config/opencode
cp .opencode.json /home/vscode/.config/opencode/config.json 2>/dev/null || true

# 4. Init data
echo "[4/5] Seed demo data..."
python seed_full_data.py 2>&1 | tail -5

# 5. Start opencode server
echo "[5/5] Starting OpenCode swarm server..."
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║         UGC SWARM 2.0 — READY                        ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Jalankan perintah:                                 ║"
echo "║                                                      ║"
echo "║  opencode run --model alibaba/qwen3-max              ║"
echo "║    'Complete all remaining tasks in AGENTS.md'       ║"
echo "║                                                      ║"
echo "║  Untuk parallel agents:                             ║"
echo "║  opencode serve --port 4096 &                       ║"
echo "║  opencode run --attach http://localhost:4096 'task1' ║"
echo "╚══════════════════════════════════════════════════════╝"
