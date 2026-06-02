#!/bin/bash
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-}:/app"

MODE="${1:-server}"

mkdir -p /app/data /app/logs /app/backups

case "$MODE" in
    server)
        echo "[skynet] Starting API server..."
        exec python3 -m ugc_ai_overpower.web.dashboard serve
        ;;
    scheduler)
        echo "[skynet] Starting campaign scheduler..."
        exec python3 -m ugc_ai_overpower.scheduler.engine serve
        ;;
    backup)
        echo "[skynet] Starting backup service..."
        INTERVAL="${BACKUP_INTERVAL:-6}"
        MAX_BACKUPS="${MAX_BACKUPS:-48}"
        while true; do
            TIMESTAMP=$(date +%Y%m%d_%H%M%S)
            BACKUP_FILE="/app/backups/skynet_${TIMESTAMP}.db.gz"
            if [ -f /app/data/skynet.db ]; then
                gzip -c /app/data/skynet.db > "$BACKUP_FILE"
                echo "[skynet] Backup created: ${BACKUP_FILE} ($(du -h "$BACKUP_FILE" | cut -f1))"
                # Rotate old backups
                ls -t /app/backups/skynet_*.db.gz 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm
            fi
            sleep $((INTERVAL * 3600))
        done
        ;;
    migrate)
        echo "[skynet] Running database migrations..."
        python3 -c "
from ugc_ai_overpower.mcp_server.tools.content_bank import ContentBank
bank = ContentBank()
bank.migrate()
print('Migration complete')
"
        ;;
    shell)
        exec python3
        ;;
    *)
        echo "Usage: $0 {server|scheduler|backup|migrate|shell}"
        exit 1
        ;;
esac
