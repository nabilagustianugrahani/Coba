"""Message Bus — SQLite-backed inter-agent communication.

Agents send/receive messages through this bus.
Each message has: sender, recipient(s), type, payload, status.

Broadcast: send to "*" — all agents receive it.
Direct: send to specific agent name.
"""
import sqlite3, json, threading, time, logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_BUS_PATH = Path(__file__).resolve().parents[1] / "data" / "swarm_bus.db"


class MessageBus:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        self._local = threading.local()
        _BUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(_BUS_PATH), check_same_thread=False)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,
                msg_type TEXT NOT NULL DEFAULT 'task',
                payload TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending',
                priority INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                processed_at TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_inbox
            ON messages(recipient, status, priority)
        """)
        conn.commit()
        self._conn = conn

    def _get_conn(self):
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(_BUS_PATH), check_same_thread=False)
        return self._local.conn

    def send(self, sender: str, recipient: str, msg_type: str = "task",
             payload: dict = None, priority: int = 0) -> int:
        payload = payload or {}
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO messages (sender, recipient, msg_type, payload, status, priority, created_at) "
            "VALUES (?, ?, ?, ?, 'pending', ?, ?)",
            (sender, recipient, msg_type, json.dumps(payload), priority,
             datetime.now().isoformat()),
        )
        conn.commit()
        msg_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        log.debug("[BUS] %s → %s: %s (id=%d)", sender, recipient, msg_type, msg_id)
        return msg_id

    def broadcast(self, sender: str, msg_type: str, payload: dict = None,
                  priority: int = 0) -> int:
        return self.send(sender, "*", msg_type, payload, priority)

    def inbox(self, agent_name: str, limit: int = 5) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, sender, recipient, msg_type, payload, status, priority, created_at "
            "FROM messages WHERE (recipient = ? OR recipient = '*') AND status = 'pending' "
            "ORDER BY priority DESC, id ASC LIMIT ?",
            (agent_name, limit),
        ).fetchall()
        return [
            {
                "id": r[0], "sender": r[1], "recipient": r[2],
                "msg_type": r[3], "payload": json.loads(r[4] or "{}"),
                "status": r[5], "priority": r[6], "created_at": r[7],
            }
            for r in rows
        ]

    def claim(self, msg_id: int, agent_name: str) -> Optional[dict]:
        conn = self._get_conn()
        conn.execute(
            "UPDATE messages SET status = 'processing' WHERE id = ? AND status = 'pending'",
            (msg_id,),
        )
        conn.commit()
        if conn.execute("SELECT changes()").fetchone()[0] == 0:
            return None
        row = conn.execute(
            "SELECT id, sender, recipient, msg_type, payload, status, priority, created_at "
            "FROM messages WHERE id = ?", (msg_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "id": row[0], "sender": row[1], "recipient": row[2],
            "msg_type": row[3], "payload": json.loads(row[4] or "{}"),
            "status": row[5], "priority": row[6], "created_at": row[7],
        }

    def complete(self, msg_id: int, result: dict = None):
        conn = self._get_conn()
        payload = json.dumps(result or {})
        conn.execute(
            "UPDATE messages SET status = 'done', payload = ?, processed_at = ? WHERE id = ?",
            (payload, datetime.now().isoformat(), msg_id),
        )
        conn.commit()

    def fail(self, msg_id: int, error: str):
        conn = self._get_conn()
        conn.execute(
            "UPDATE messages SET status = 'failed', payload = ?, processed_at = ? WHERE id = ?",
            (json.dumps({"error": error}), datetime.now().isoformat(), msg_id),
        )
        conn.commit()

    def reply(self, original_msg: dict, sender: str, payload: dict = None,
              msg_type: str = "result") -> int:
        return self.send(sender, original_msg["sender"], msg_type, payload)

    def health(self) -> dict:
        conn = self._get_conn()
        counts = {}
        for status in ("pending", "processing", "done", "failed"):
            row = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE status = ?", (status,)
            ).fetchone()
            counts[status] = row[0]
        return counts

    def clean_old(self, hours: int = 72):
        conn = self._get_conn()
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        conn.execute("DELETE FROM messages WHERE created_at < ?", (cutoff,))
        conn.commit()
