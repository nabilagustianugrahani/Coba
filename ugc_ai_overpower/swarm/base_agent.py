"""Base Agent — every swarm agent inherits this.

Pattern:
  1. Agent polls inbox for messages
  2. Claims one message at a time
  3. Processes it via handle_{msg_type}()
  4. Marks done/failed
  5. Auto-healing: detects & fixes stuck tasks, dead threads, missing deps
  6. Sleeps, repeats
"""
import json, logging, time, threading, traceback
from datetime import datetime
from typing import Optional

from swarm.message_bus import MessageBus
from swarm.autoheal import HealableMixin, DependencyHealer

log = logging.getLogger(__name__)


class BaseAgent(HealableMixin):
    name: str = "base"

    def __init__(self, poll_interval: float = 1.0, max_concurrent: int = 1,
                 heal_interval: int = 60):
        super().__init__(poll_interval=poll_interval, max_concurrent=max_concurrent,
                         heal_interval=heal_interval)
        self.bus = MessageBus()
        self.poll_interval = poll_interval
        self.max_concurrent = max_concurrent
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._active_tasks: dict[int, dict] = {}
        self._status = "idle"
        self._dep_healed = False

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name=self.name)
        self._thread.start()
        log.info("[%s] Agent started (poll=%ss, max_concurrent=%d, heal=%ds)",
                 self.name, self.poll_interval, self.max_concurrent, self._heal_interval)

    def stop(self):
        self._running = False
        log.info("[%s] Agent stopping", self.name)

    def _run_loop(self):
        self.announce()
        if not self._dep_healed:
            actions = DependencyHealer.check_and_heal()
            if actions:
                log.info("[%s] Auto-healed deps: %s", self.name, actions)
            self._dep_healed = True

        while self._running:
            try:
                self.tick()
                self.tick_heal()
                self._process_inbox()
            except Exception as e:
                log.error("[%s] Loop error: %s", self.name, e)
            time.sleep(self.poll_interval)

    def announce(self):
        self.bus.broadcast(self.name, "agent_hello",
                           {"name": self.name, "status": "online", "time": datetime.now().isoformat()})

    def tick(self):
        pass

    def _process_inbox(self):
        if len(self._active_tasks) >= self.max_concurrent:
            return
        msgs = self.bus.inbox(self.name, limit=self.max_concurrent)
        for msg in msgs:
            claimed = self.bus.claim(msg["id"], self.name)
            if claimed:
                self._active_tasks[msg["id"]] = claimed
                t = threading.Thread(
                    target=self._handle_wrapper,
                    args=(claimed,),
                    daemon=True,
                )
                t.start()

    def _handle_wrapper(self, msg: dict):
        try:
            self._status = "busy"
            handler = f"handle_{msg['msg_type']}"
            if hasattr(self, handler):
                result = getattr(self, handler)(msg)
            else:
                result = self.handle_default(msg)

            if result:
                self.bus.complete(msg["id"], result)
            else:
                self.bus.complete(msg["id"], {"status": "done"})
        except Exception as e:
            log.error("[%s] Failed msg %d: %s", self.name, msg["id"], e)
            self.bus.fail(msg["id"], str(e))
        finally:
            self._active_tasks.pop(msg["id"], None)
            self._status = "idle"

    def handle_default(self, msg: dict) -> Optional[dict]:
        log.info("[%s] No handler for %s — ignoring", self.name, msg["msg_type"])
        return {"status": "ignored", "reason": f"no handler for {msg['msg_type']}"}

    def send(self, recipient: str, msg_type: str, payload: dict = None,
             priority: int = 0) -> int:
        return self.bus.send(self.name, recipient, msg_type, payload, priority)

    def broadcast(self, msg_type: str, payload: dict = None, priority: int = 0) -> int:
        return self.bus.broadcast(self.name, msg_type, payload, priority)

    @property
    def status(self) -> dict:
        return {
            "name": self.name,
            "status": self._status,
            "active_tasks": len(self._active_tasks),
            "running": self._running,
            "healthy": getattr(self, "_health_status", None).healthy if hasattr(self, "_health_status") else True,
            "heal_interval_s": self._heal_interval,
        }
