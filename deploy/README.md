# UGC Auto-Pipeline Deployment

Production deployment artifacts for the **UGC AI Overpower** auto-pipeline daemon.

## Files

| File | Purpose |
|---|---|
| `ugc-autopipeline.service` | systemd unit for the auto-pipeline daemon |
| `logrotate.conf` | Daily rotation of `/home/aer/ugc/logs/*.log` (keep 7) |
| `monitor.sh` | Health-check script (PID file + Notion alert) |
| `install.sh` | One-shot installer (systemd + logrotate + cron) |
| `codespace_cron_restart.sh` | Codespace fail-safe: restarts daemon if down |
| `healthcheck_cron.sh` | Periodic health check via health_monitor.py |
| `failover_monitor.sh` | Codespace pool failover (primary → backup) |

## Architecture

```
┌──────────────────────────────────────────┐
│  systemd: ugc-autopipeline.service      │
│   └─ python3 -m ugc_ai_overpower.main   │
│         auto-pipeline start             │
│   stdout → logs/auto-pipeline.log       │
│   stderr → logs/auto-pipeline-err.log   │
│   PID    → logs/auto-pipeline.pid       │
└──────────────┬───────────────────────────┘
               │
        cron (*/5)
               │
┌──────────────▼───────────────────────────┐
│  monitor.sh                             │
│   ├─ checks PID file + kill -0 <pid>   │
│   ├─ posts alert to Notion Inbox DB     │
│   └─ logs to logs/monitor.log           │
└──────────────────────────────────────────┘
```

## Install

```bash
sudo NOTION_TOKEN="secret_xxx" /home/aer/ugc/deploy/install.sh
```

The installer:
1. Copies `ugc-autopipeline.service` → `/etc/systemd/system/`, then `enable` + `restart`.
2. Copies `logrotate.conf` → `/etc/logrotate.d/ugc-autopipeline`.
3. Writes a cron entry to `/etc/cron.d/ugc-autopipeline-monitor` (every 5 min).
4. Verifies the service is active.

Environment variables honored at install time:
- `NOTION_TOKEN` — propagated to the monitor cron so health alerts can post to Notion.

## Uninstall

```bash
sudo systemctl disable --now ugc-autopipeline
sudo rm /etc/systemd/system/ugc-autopipeline.service
sudo rm /etc/logrotate.d/ugc-autopipeline
sudo rm /etc/cron.d/ugc-autopipeline-monitor
sudo systemctl daemon-reload
```

## Day-to-day operations

```bash
# Service
sudo systemctl status ugc-autopipeline
sudo systemctl restart ugc-autopipeline
sudo journalctl -u ugc-autopipeline -f

# Logs
tail -f /home/aer/ugc/logs/auto-pipeline.log
tail -f /home/aer/ugc/logs/auto-pipeline-err.log
tail -f /home/aer/ugc/logs/monitor.log

# Manual run
cd /home/aer/ugc
python3 -m ugc_ai_overpower.main auto-pipeline status
python3 -m ugc_ai_overpower.main auto-pipeline run-once

# Codespace operations
# - codespace_cron_restart.sh is run every 5min via background loop in codespace
# - healthcheck_cron.sh runs every 10min, posts to Notion Inbox on failure
# - failover_monitor.sh checks primary codespace, switches to backup on 3 failures

# Manual checks (in codespace)
/tmp/ugc-restart                    # restart daemon
/tmp/healthcheck_cron.sh            # health check
bash /workspaces/Coba/deploy/failover_monitor.sh
```

## Monitor behaviour

`monitor.sh` runs every 5 minutes via cron. It:

1. Reads `logs/auto-pipeline.pid`.
2. Verifies the PID is alive (`kill -0`).
3. If the file is missing **or** the PID is dead, posts an alert page to the Notion **Inbox** DB with:
   - `Type = alert`
   - `Sender = monitor.sh`
   - `Platform = system`
   - `Account = ugc-autopipeline`
   - `Content` = short subject line
   - `AI Reply` = body with remediation hint
4. Logs the outcome to `logs/monitor.log`.

Required env var on the host where cron runs: `NOTION_TOKEN` (and optionally `NOTION_INBOX_DB` if not already exported system-wide).

## Log retention

- `daily` rotation, `rotate 7` — one week of compressed history.
- `delaycompress` keeps yesterday's log uncompressed for easy inspection.
- `missingok` / `notifempty` make rotation a no-op when there's nothing to do.

## Manual test of the monitor

```bash
# Simulate the daemon being down
sudo systemctl stop ugc-autopipeline
rm -f /home/aer/ugc/logs/auto-pipeline.pid

# Trigger one check
NOTION_TOKEN="$NOTION_TOKEN" /home/aer/ugc/deploy/monitor.sh
echo "exit=$?"

# Restore
sudo systemctl start ugc-autopipeline
```
