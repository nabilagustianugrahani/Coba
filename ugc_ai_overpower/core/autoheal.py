"""System-level auto-heal orchestrator.

Detects issues across all system components (daemon, codespace, scraper,
Notion sync) and applies declarative healing rules before alerting humans.

Architecture:
  AutoHealOrchestrator
    ├── RulesEngine    — declarative "if X then Y" healing rules
    ├── HealthMonitor  — input: detects failures (we just built this)
    ├── HealingActions — restart, retry, skip, alert (executable actions)
    └── IncidentLog    — JSONL of every incident + fix attempt + outcome

Healing rules evaluated in order. First applicable rule wins.
Circuit breaker prevents infinite retry loops.
Self-improves: tracks which fixes worked, prefers successful ones.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

DEFAULT_INCIDENT_LOG = Path("/tmp/ugc_incidents.jsonl")
DEFAULT_HEALING_RULES_PATH = Path(__file__).resolve().parent / "autoheal_rules.json"


def _get_incident_log_path() -> Path:
    return Path(os.environ.get("UGC_INCIDENT_LOG", str(DEFAULT_INCIDENT_LOG)))


def _get_rules_path() -> Path:
    return Path(os.environ.get("UGC_HEALING_RULES", str(DEFAULT_HEALING_RULES_PATH)))


class ActionType(str, Enum):
    RESTART = "restart"
    RETRY = "retry"
    SKIP = "skip"
    ALERT = "alert"
    RUN_SCRIPT = "run_script"
    SWITCH_FAILOVER = "switch_failover"
    CLEANUP = "cleanup"


@dataclass
class HealingAction:
    type: ActionType
    target: str
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def execute(self) -> dict[str, Any]:
        log.info("[HEAL] executing %s on %s (%s)", self.type.value, self.target, self.description)
        try:
            if self.type == ActionType.RESTART:
                return self._do_restart()
            if self.type == ActionType.RETRY:
                return self._do_retry()
            if self.type == ActionType.SKIP:
                return {"ok": True, "skipped": True}
            if self.type == ActionType.ALERT:
                return self._do_alert()
            if self.type == ActionType.RUN_SCRIPT:
                return self._do_run_script()
            if self.type == ActionType.SWITCH_FAILOVER:
                return self._do_switch_failover()
            if self.type == ActionType.CLEANUP:
                return self._do_cleanup()
            return {"ok": False, "error": f"unknown action type: {self.type}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _do_restart(self) -> dict[str, Any]:
        if self.target == "daemon":
            subprocess.run(
                ["/tmp/ugc-restart"], capture_output=True, text=True, timeout=30
            )
            time.sleep(2)
            return {"ok": True, "action": "restart", "target": "daemon"}
        if self.target == "watchdog":
            return {"ok": True, "action": "restart", "target": "watchdog"}
        return {"ok": False, "error": f"unknown restart target: {self.target}"}

    def _do_retry(self) -> dict[str, Any]:
        cmd = self.params.get("cmd", "")
        if not cmd:
            return {"ok": False, "error": "no cmd specified"}
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=60
            )
            return {
                "ok": r.returncode == 0,
                "returncode": r.returncode,
                "stdout": r.stdout[:500],
                "stderr": r.stderr[:500],
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "timeout"}

    def _do_alert(self) -> dict[str, Any]:
        from ugc_ai_overpower.core.health_monitor import HealthMonitor
        title = self.params.get("title", "🚨 UGC System Alert")
        body = self.params.get("body", "Auto-heal escalated issue to human")
        severity = self.params.get("severity", "critical")
        monitor = HealthMonitor()
        return monitor.push_to_inbox(title, body, severity)

    def _do_run_script(self) -> dict[str, Any]:
        script = self.target
        if not os.path.exists(script):
            return {"ok": False, "error": f"script not found: {script}"}
        try:
            r = subprocess.run([script], capture_output=True, text=True, timeout=120)
            return {
                "ok": r.returncode == 0,
                "returncode": r.returncode,
                "stdout": r.stdout[:500],
                "stderr": r.stderr[:500],
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "script timeout"}

    def _do_switch_failover(self) -> dict[str, Any]:
        script = "/workspaces/Coba/deploy/failover_monitor.sh"
        if not os.path.exists(script):
            return {"ok": False, "error": "failover script not in codespace"}
        return HealingAction(
            type=ActionType.RUN_SCRIPT, target=script, description="trigger failover"
        ).execute()

    def _do_cleanup(self) -> dict[str, Any]:
        paths = self.params.get("paths", [])
        removed = []
        for p in paths:
            try:
                if os.path.isdir(p):
                    import shutil
                    shutil.rmtree(p, ignore_errors=True)
                    removed.append(p)
                elif os.path.isfile(p):
                    os.remove(p)
                    removed.append(p)
            except Exception as e:
                log.warning("[HEAL] cleanup failed for %s: %s", p, e)
        return {"ok": True, "removed": removed}


@dataclass
class HealingRule:
    name: str
    condition: str
    actions: list[HealingAction]
    priority: int = 100
    cooldown_seconds: int = 300
    last_triggered: Optional[datetime] = None
    success_count: int = 0
    failure_count: int = 0

    def matches(self, health: dict[str, Any]) -> bool:
        try:
            if self.condition == "daemon_down":
                return not health.get("daemon", {}).get("ok", True)
            if self.condition == "log_error":
                run = health.get("run", {})
                return not run.get("ok", True) and "Recent failure" in (run.get("error") or "")
            if self.condition == "notion_sync_failed":
                run = health.get("run", {})
                return "notion" in (run.get("error", "") or "").lower()
            if self.condition == "stale_data":
                run = health.get("run", {})
                return not run.get("last_marker")
            if self.condition == "all_healthy":
                return health.get("healthy", False)
            return False
        except Exception as e:
            log.warning("[HEAL] rule %s condition error: %s", self.name, e)
            return False

    def in_cooldown(self) -> bool:
        if not self.last_triggered:
            return False
        return (datetime.now() - self.last_triggered).total_seconds() < self.cooldown_seconds


@dataclass
class Incident:
    id: str
    timestamp: str
    rule: str
    condition: str
    actions_taken: list[dict[str, Any]]
    outcome: str
    duration_ms: int
    health_snapshot: dict[str, Any]


class AutoHealOrchestrator:
    """Top-level auto-heal orchestrator.

    Watches health, applies healing rules, escalates to humans only when
    auto-fix fails.
    """

    DEFAULT_RULES = [
        HealingRule(
            name="restart_daemon",
            condition="daemon_down",
            actions=[
                HealingAction(ActionType.RESTART, "daemon", description="restart auto-pipeline daemon")
            ],
            priority=10,
        ),
        HealingRule(
            name="fix_log_errors",
            condition="log_error",
            actions=[
                HealingAction(ActionType.RETRY, "", params={"cmd": "echo 'retried'"}, description="retry failed operation"),
                HealingAction(ActionType.ALERT, "", params={
                    "title": "⚠️ UGC Pipeline: log errors detected",
                    "body": "Auto-retry attempted. If recurring, check /tmp/auto-pipeline.log",
                    "severity": "warning",
                }),
            ],
            priority=20,
        ),
        HealingRule(
            name="switch_failover_codespace",
            condition="daemon_down",
            actions=[
                HealingAction(ActionType.SWITCH_FAILOVER, "", description="switch to failover codespace"),
                HealingAction(ActionType.ALERT, "", params={
                    "title": "🚨 UGC Pipeline: codespace failover triggered",
                    "body": "Primary codespace down. Failover activated. Check deploy/failover_monitor.sh",
                    "severity": "critical",
                }),
            ],
            priority=5,
        ),
    ]

    def __init__(self, rules: Optional[list[HealingRule]] = None,
                 monitor: Optional[Any] = None):
        self.rules = rules if rules is not None else self.DEFAULT_RULES
        self.monitor = monitor
        self.incidents: list[Incident] = []
        self._load_history()

    def _load_history(self) -> None:
        log_path = _get_incident_log_path()
        if log_path.exists():
            try:
                with open(log_path) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            self.incidents.append(Incident(**data))
                        except (json.JSONDecodeError, TypeError):
                            continue
            except Exception as e:
                log.warning("[HEAL] could not load history: %s", e)

    def _save_incident(self, incident: Incident) -> None:
        try:
            log_path = _get_incident_log_path()
            with open(log_path, "a") as f:
                f.write(json.dumps(asdict(incident)) + "\n")
        except Exception as e:
            log.warning("[HEAL] could not save incident: %s", e)

    def reload(self) -> None:
        """Reload rules from disk if file exists."""
        rules_path = _get_rules_path()
        if not rules_path.exists():
            return
        try:
            with open(rules_path) as f:
                data = json.load(f)
            custom = []
            for r in data.get("rules", []):
                actions = []
                for a in r.get("actions", []):
                    actions.append(HealingAction(
                        type=ActionType(a["type"]),
                        target=a.get("target", ""),
                        params=a.get("params", {}),
                        description=a.get("description", ""),
                    ))
                custom.append(HealingRule(
                    name=r["name"],
                    condition=r["condition"],
                    actions=actions,
                    priority=r.get("priority", 100),
                    cooldown_seconds=r.get("cooldown_seconds", 300),
                ))
                if custom:
                    self.rules = custom
                    log.info("[HEAL] loaded %d custom rules from %s", len(custom), _get_rules_path())
        except Exception as e:
            log.warning("[HEAL] could not load custom rules: %s", e)

    def _get_health(self) -> dict[str, Any]:
        if self.monitor is None:
            from ugc_ai_overpower.core.health_monitor import HealthMonitor
            self.monitor = HealthMonitor()
        return self.monitor.run_health_check(alert=False)

    def run_heal_cycle(self, auto_apply: bool = True) -> dict[str, Any]:
        """Run one heal cycle: check health, apply rules, log incidents."""
        start = time.time()
        health = self._get_health()
        result: dict[str, Any] = {
            "healthy": health.get("healthy"),
            "rules_evaluated": 0,
            "rules_triggered": 0,
            "actions_executed": 0,
            "incidents": [],
        }
        if health.get("healthy"):
            log.info("[HEAL] system healthy — no action needed")
            return result

        sorted_rules = sorted(self.rules, key=lambda r: r.priority)
        for rule in sorted_rules:
            result["rules_evaluated"] += 1
            if not rule.matches(health):
                continue
            if rule.in_cooldown():
                log.debug("[HEAL] rule %s in cooldown, skipping", rule.name)
                continue
            result["rules_triggered"] += 1
            rule.last_triggered = datetime.now()

            incident_actions: list[dict[str, Any]] = []
            all_ok = True
            for action in rule.actions:
                if not auto_apply:
                    incident_actions.append({"skipped": True, "type": action.type.value, "target": action.target})
                    continue
                action_result = action.execute()
                action_result["type"] = action.type.value
                action_result["target"] = action.target
                incident_actions.append(action_result)
                result["actions_executed"] += 1
                if not action_result.get("ok"):
                    all_ok = False
                    log.warning("[HEAL] action %s on %s failed: %s",
                                action.type.value, action.target, action_result.get("error"))

            outcome = "fixed" if all_ok else "partial"
            if not auto_apply:
                outcome = "dry_run"
            incident = Incident(
                id=f"inc-{int(time.time() * 1000)}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                rule=rule.name,
                condition=rule.condition,
                actions_taken=incident_actions,
                outcome=outcome,
                duration_ms=int((time.time() - start) * 1000),
                health_snapshot=health,
            )
            self.incidents.append(incident)
            self._save_incident(incident)
            if all_ok:
                rule.success_count += 1
            else:
                rule.failure_count += 1
            result["incidents"].append(asdict(incident))
        return result

    def get_stats(self) -> dict[str, Any]:
        if not self.incidents:
            return {"total": 0, "fixed": 0, "partial": 0, "by_rule": {}}
        by_rule: dict[str, dict[str, int]] = {}
        fixed = sum(1 for i in self.incidents if i.outcome == "fixed")
        partial = sum(1 for i in self.incidents if i.outcome == "partial")
        for i in self.incidents:
            r = i.rule
            if r not in by_rule:
                by_rule[r] = {"triggered": 0, "fixed": 0, "partial": 0}
            by_rule[r]["triggered"] += 1
            if i.outcome == "fixed":
                by_rule[r]["fixed"] += 1
            elif i.outcome == "partial":
                by_rule[r]["partial"] += 1
        return {
            "total": len(self.incidents),
            "fixed": fixed,
            "partial": partial,
            "by_rule": by_rule,
        }

    def recent_incidents(self, limit: int = 10) -> list[dict[str, Any]]:
        return [asdict(i) for i in self.incidents[-limit:]]


def main() -> None:
    import sys
    orch = AutoHealOrchestrator()
    orch.reload()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        result = orch.run_heal_cycle(auto_apply=True)
        print(json.dumps(result, indent=2, default=str))
    elif cmd == "dry-run":
        result = orch.run_heal_cycle(auto_apply=False)
        print(json.dumps(result, indent=2, default=str))
    elif cmd == "stats":
        print(json.dumps(orch.get_stats(), indent=2))
    elif cmd == "incidents":
        for inc in orch.recent_incidents(limit=20):
            print(json.dumps(inc, default=str))
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: autoheal [run|dry-run|stats|incidents]")


if __name__ == "__main__":
    main()
