import sqlite3, json, os, threading
from datetime import datetime, timedelta, timezone
from ugc_ai_overpower.core.logging import setup_logging

logger = setup_logging("metrics")
_lock = threading.Lock()

class MetricsCollector:
    def __init__(self, db_path="data/metrics.db"):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS metrics_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                event_data TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )""")
            c.execute("""CREATE INDEX IF NOT EXISTS idx_metrics_type ON metrics_events(event_type)""")

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def track(self, event_type, **data):
        with _lock:
            with self._conn() as c:
                c.execute("INSERT INTO metrics_events (event_type, event_data) VALUES (?, ?)",
                          (event_type, json.dumps(data)))
        logger.info("Track: %s %s", event_type, data.get("product", ""))

    def track_campaign(self, product, total_content, duration):
        self.track("campaign", product=product, total=total_content, duration=duration)

    def track_content(self, content_id, platform, action, success=True):
        self.track("content", content_id=content_id, platform=platform, action=action, success=success)

    def track_gpu(self, job_type, duration, success=True):
        self.track("gpu", job_type=job_type, duration=duration, success=success)

    def get_daily_stats(self, days=7):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._conn() as c:
            rows = c.execute("""SELECT date(created_at) as day, event_type, COUNT(*) as total
                FROM metrics_events WHERE created_at >= ? GROUP BY day, event_type ORDER BY day""", (since,)).fetchall()
        result = {}
        for day, etype, total in rows:
            if day not in result:
                result[day] = {}
            result[day][etype] = total
        return result

    def get_top_products(self, limit=10):
        with self._conn() as c:
            rows = c.execute("""SELECT json_extract(event_data, '$.product') as product, COUNT(*) as total
                FROM metrics_events WHERE event_type='campaign' AND product IS NOT NULL
                GROUP BY product ORDER BY total DESC LIMIT ?""", (limit,)).fetchall()
        return [{"product": r[0], "campaigns": r[1]} for r in rows]

    def get_summary(self):
        with self._conn() as c:
            total = c.execute("SELECT COUNT(*) FROM metrics_events").fetchone()[0]
            campaigns = c.execute("SELECT COUNT(*) FROM metrics_events WHERE event_type='campaign'").fetchone()[0]
            contents = c.execute("SELECT COUNT(*) FROM metrics_events WHERE event_type='content'").fetchone()[0]
        return {"total_events": total, "total_campaigns": campaigns, "total_contents": contents}

_metrics_instance = None
def get_metrics_collector():
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = MetricsCollector()
    return _metrics_instance
