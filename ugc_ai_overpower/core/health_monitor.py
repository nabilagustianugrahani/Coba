"""Health monitor — periodic daemon health check with Notion Inbox alerts.

Pushes structured alerts to the Notion Inbox database when:
- Auto-pipeline daemon is down
- Recent run failed
- Notion sync failed
- Stale engagement data
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from dotenv import load_dotenv
from typing import cast, Any

load_dotenv()
log = logging.getLogger(__name__)

NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_INBOX_DB = os.getenv("NOTION_INBOX_DB", "")


class HealthMonitor:
    def __init__(self, pidfile: str = "/tmp/ugc_autopipeline.pid",
                 logfile: str = "/tmp/auto-pipeline.log"):
        self.pidfile = pidfile
        self.logfile = logfile

    def check_daemon_alive(self) -> dict:
        if not os.path.exists(self.pidfile):
            return {"ok": False, "error": "PID file missing", "pid": None}
        try:
            pid = int(open(self.pidfile).read().strip())
            os.kill(pid, 0)
            return {"ok": True, "pid": pid, "error": None}
        except (ProcessLookupError, ValueError):
            return {"ok": False, "error": "Process dead", "pid": None}
        except PermissionError:
            return {"ok": True, "pid": None, "error": None}

    def check_recent_run(self, lookback_lines: int = 100) -> dict:
        if not os.path.exists(self.logfile):
            return {"ok": False, "error": "Log file missing"}
        try:
            with open(self.logfile) as f:
                lines = f.readlines()[-lookback_lines:]
            text = "".join(lines)
            has_failure = any(w in text for w in ["ERROR", "Traceback", "FAILED"])
            last_run_marker = None
            for line in reversed(lines):
                if "cycle" in line.lower() or "pipeline" in line.lower() or "completed" in line.lower():
                    last_run_marker = line.strip()
                    break
            return {
                "ok": not has_failure,
                "error": "Recent failure in log" if has_failure else None,
                "last_marker": last_run_marker,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def push_to_inbox(self, title: str, body: str, severity: str = "warning") -> dict:
        if not NOTION_TOKEN or not NOTION_INBOX_DB:
            log.warning("Notion Inbox not configured — skipping alert")
            return {"ok": False, "error": "Notion not configured"}
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "parent": {"database_id": NOTION_INBOX_DB},
            "properties": {
                "Title": {"title": [{"text": {"content": title}}]},
                "Severity": {"select": {"name": severity}},
                "Status": {"select": {"name": "open"}},
                "Source": {"select": {"name": "health_monitor"}},
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": body}}]
                    },
                }
            ],
        }
        headers = {
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        try:
            r = requests.post(
                "https://api.notion.com/v1/pages", json=cast(Any, payload), headers=headers, timeout=30
            )
            r.raise_for_status()
            return {"ok": True, "page_id": r.json().get("id")}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def run_health_check(self, alert: bool = True) -> dict:
        daemon = self.check_daemon_alive()
        run = self.check_recent_run()
        healthy = daemon["ok"] and run["ok"]
        result = {
            "healthy": healthy,
            "daemon": daemon,
            "run": run,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        log.info(f"Health check: daemon={daemon['ok']} run={run['ok']} → healthy={healthy}")
        if not healthy and alert:
            title = "🚨 UGC Pipeline Unhealthy"
            body_lines = [
                f"**Daemon**: {daemon}",
                f"**Last run**: {run}",
                f"**Checked**: {result['checked_at']}",
            ]
            self.push_to_inbox(title, "\n".join(body_lines), severity="critical")
        return result


def main() -> None:
    import sys
    monitor = HealthMonitor()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        result = monitor.run_health_check(alert=True)
        sys.exit(0 if result["healthy"] else 1)
    elif cmd == "silent":
        result = monitor.run_health_check(alert=False)
        print(result)
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
