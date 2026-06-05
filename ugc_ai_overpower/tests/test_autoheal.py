"""Tests for system-level auto-heal orchestrator."""
import json
import os
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ugc_ai_overpower.core.autoheal import (
    ActionType,
    AutoHealOrchestrator,
    HealingAction,
    HealingRule,
    Incident,
)


@pytest.fixture
def clean_incident_log(tmp_path, monkeypatch):
    log_path = tmp_path / "incidents.jsonl"
    monkeypatch.setenv("UGC_INCIDENT_LOG", str(log_path))
    yield log_path
    if log_path.exists():
        log_path.unlink()


def test_healing_action_restart_daemon():
    action = HealingAction(ActionType.RESTART, "daemon", description="test")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = action.execute()
    assert result["ok"] is True
    assert result["action"] == "restart"


def test_healing_action_retry_success():
    action = HealingAction(ActionType.RETRY, "", params={"cmd": "echo hello"})
    result = action.execute()
    assert result["ok"] is True
    assert result["returncode"] == 0


def test_healing_action_retry_no_cmd():
    action = HealingAction(ActionType.RETRY, "")
    result = action.execute()
    assert result["ok"] is False
    assert "no cmd" in result["error"]


def test_healing_action_skip():
    action = HealingAction(ActionType.SKIP, "anything")
    result = action.execute()
    assert result["ok"] is True
    assert result["skipped"] is True


def test_healing_action_cleanup(tmp_path):
    f1 = tmp_path / "old.log"
    f1.write_text("stale")
    d1 = tmp_path / "old_cache"
    d1.mkdir()
    (d1 / "x").write_text("y")

    action = HealingAction(ActionType.CLEANUP, "", params={"paths": [str(f1), str(d1)]})
    result = action.execute()
    assert result["ok"] is True
    assert str(f1) in result["removed"]
    assert not f1.exists()
    assert not d1.exists()


def test_healing_rule_daemon_down():
    rule = HealingRule(
        name="test_daemon", condition="daemon_down",
        actions=[HealingAction(ActionType.RESTART, "daemon")]
    )
    unhealthy = {"daemon": {"ok": False}, "run": {"ok": True}}
    healthy = {"daemon": {"ok": True}, "run": {"ok": True}}
    assert rule.matches(unhealthy) is True
    assert rule.matches(healthy) is False


def test_healing_rule_log_error():
    rule = HealingRule(
        name="test_log", condition="log_error",
        actions=[HealingAction(ActionType.ALERT, "")]
    )
    with_err = {"daemon": {"ok": True}, "run": {"ok": False, "error": "Recent failure in log"}}
    no_err = {"daemon": {"ok": True}, "run": {"ok": True, "error": None}}
    assert rule.matches(with_err) is True
    assert rule.matches(no_err) is False


def test_healing_rule_cooldown():
    rule = HealingRule(name="t", condition="daemon_down", actions=[], cooldown_seconds=300)
    assert rule.in_cooldown() is False
    rule.last_triggered = datetime.now() - timedelta(seconds=10)
    assert rule.in_cooldown() is True
    rule.last_triggered = datetime.now() - timedelta(seconds=400)
    assert rule.in_cooldown() is False


def test_incident_creation():
    inc = Incident(
        id="inc-1",
        timestamp="2026-01-01T00:00:00",
        rule="test",
        condition="daemon_down",
        actions_taken=[],
        outcome="fixed",
        duration_ms=100,
        health_snapshot={},
    )
    assert inc.id == "inc-1"
    assert inc.outcome == "fixed"


def test_orchestrator_with_healthy_system(clean_incident_log):
    mock_health = {"healthy": True, "daemon": {"ok": True}, "run": {"ok": True}}
    with patch.object(AutoHealOrchestrator, "_get_health", return_value=mock_health):
        orch = AutoHealOrchestrator()
        result = orch.run_heal_cycle(auto_apply=True)
    assert result["healthy"] is True
    assert result["rules_triggered"] == 0
    assert result["incidents"] == []


def test_orchestrator_triggers_rule_when_unhealthy(clean_incident_log):
    mock_health = {
        "healthy": False,
        "daemon": {"ok": False, "error": "PID missing"},
        "run": {"ok": True, "error": None},
    }
    with patch.object(AutoHealOrchestrator, "_get_health", return_value=mock_health):
        orch = AutoHealOrchestrator()
        for r in orch.rules:
            r.last_triggered = None
        result = orch.run_heal_cycle(auto_apply=False)
    assert result["rules_triggered"] >= 1
    assert len(result["incidents"]) >= 1
    assert result["incidents"][0]["outcome"] == "dry_run"


def test_orchestrator_rule_cooldown_prevents_retrigger(clean_incident_log):
    mock_health = {
        "healthy": False,
        "daemon": {"ok": False},
        "run": {"ok": True},
    }
    rule = HealingRule(
        name="r1", condition="daemon_down", priority=10,
        actions=[HealingAction(ActionType.SKIP, "test")],
        cooldown_seconds=300,
    )
    rule.last_triggered = datetime.now()
    with patch.object(AutoHealOrchestrator, "_get_health", return_value=mock_health):
        orch = AutoHealOrchestrator(rules=[rule])
        result = orch.run_heal_cycle(auto_apply=False)
    assert result["rules_triggered"] == 0


def test_orchestrator_incident_log_persists(clean_incident_log):
    mock_health = {
        "healthy": False,
        "daemon": {"ok": False},
        "run": {"ok": True},
    }
    with patch.object(AutoHealOrchestrator, "_get_health", return_value=mock_health):
        orch = AutoHealOrchestrator()
        for r in orch.rules:
            r.last_triggered = None
        orch.run_heal_cycle(auto_apply=False)
    assert clean_incident_log.exists()
    lines = clean_incident_log.read_text().strip().split("\n")
    assert len(lines) >= 1
    parsed = json.loads(lines[0])
    assert "id" in parsed
    assert "outcome" in parsed


def test_orchestrator_stats_aggregation(clean_incident_log):
    mock_health = {
        "healthy": False,
        "daemon": {"ok": False},
        "run": {"ok": True},
    }
    with patch.object(AutoHealOrchestrator, "_get_health", return_value=mock_health):
        orch = AutoHealOrchestrator()
        for r in orch.rules:
            r.last_triggered = None
        orch.run_heal_cycle(auto_apply=False)
        orch.run_heal_cycle(auto_apply=False)
    stats = orch.get_stats()
    assert stats["total"] >= 2
    assert "by_rule" in stats
    assert sum(r["triggered"] for r in stats["by_rule"].values()) >= 2


def test_orchestrator_recent_incidents(clean_incident_log):
    mock_health = {
        "healthy": False,
        "daemon": {"ok": False},
        "run": {"ok": True},
    }
    with patch.object(AutoHealOrchestrator, "_get_health", return_value=mock_health):
        orch = AutoHealOrchestrator()
        for r in orch.rules:
            r.last_triggered = None
        orch.run_heal_cycle(auto_apply=False)
    recent = orch.recent_incidents(limit=5)
    assert len(recent) >= 1
    assert recent[0]["rule"] in ["restart_daemon", "switch_failover_codespace"]


def test_orchestrator_reload_custom_rules(tmp_path, monkeypatch):
    custom_rules = tmp_path / "rules.json"
    custom_rules.write_text(json.dumps({
        "rules": [{
            "name": "custom_rule",
            "condition": "daemon_down",
            "priority": 1,
            "cooldown_seconds": 60,
            "actions": [{"type": "skip", "target": "x", "description": "skip"}]
        }]
    }))
    monkeypatch.setenv("UGC_HEALING_RULES", str(custom_rules))
    orch = AutoHealOrchestrator()
    orch.reload()
    assert any(r.name == "custom_rule" for r in orch.rules)
