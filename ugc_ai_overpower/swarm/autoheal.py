"""Auto-Healing System — agents that detect and fix their own problems.

Every agent inherits from HealableAgent which adds:
  - Health checks every N seconds
  - Automatic issue detection (stuck tasks, import errors, deps missing)
  - Self-repair actions (reinstall deps, restart threads, clean stale state)
  - Circuit breaker pattern: after 3 failures, cooldown before retry
"""
import logging, threading, time, subprocess, sys, importlib
from datetime import datetime, timedelta
from typing import Optional, Callable
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

COOLDOWN_SECONDS = 300  # 5min cooldown after 3 failures
MAX_FAILURES_BEFORE_COOLDOWN = 3


@dataclass
class HealthStatus:
    healthy: bool = True
    issues: list[str] = field(default_factory=list)
    last_check: Optional[datetime] = None
    consecutive_failures: int = 0
    in_cooldown: bool = False
    cooldown_until: Optional[datetime] = None


class CircuitBreaker:
    """Prevents cascading failures by backing off after repeated errors."""

    def __init__(self, name: str, max_failures: int = MAX_FAILURES_BEFORE_COOLDOWN,
                 cooldown: int = COOLDOWN_SECONDS):
        self.name = name
        self.max_failures = max_failures
        self.cooldown = cooldown
        self.failures = 0
        self.last_failure: Optional[datetime] = None
        self.cooldown_until: Optional[datetime] = None

    @property
    def is_open(self) -> bool:
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return True
        if self.cooldown_until:
            self.cooldown_until = None
            self.failures = 0
        return False

    def record_success(self):
        self.failures = 0
        self.cooldown_until = None

    def record_failure(self):
        self.failures += 1
        self.last_failure = datetime.now()
        if self.failures >= self.max_failures:
            self.cooldown_until = datetime.now() + timedelta(seconds=self.cooldown)
            log.warning("[HEAL] %s circuit OPEN — cooling down for %ds", self.name, self.cooldown)
            return True  # circuit just opened
        return False


class HealableMixin:
    """Mixin for BaseAgent to add auto-healing capabilities.

    Usage:
        class MyAgent(BaseAgent, HealableMixin):
            name = "my_agent"

            def health_checks(self) -> list[str]:
                issues = []
                # check things...
                return issues

            def heal(self, issue: str) -> bool:
                # fix the issue
                return True
    """

    def __init__(self, *args, heal_interval: int = 60, **kwargs):
        super().__init__(*args, **kwargs)
        self._heal_interval = heal_interval
        self._last_heal_check: Optional[datetime] = None
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._health_status = HealthStatus()

    def health_checks(self) -> list[str]:
        """Override this to define custom health checks.

        Returns list of issue descriptions (empty = healthy).
        """
        issues = []

        # 1. Check for stale active tasks
        stale = self._detect_stale_tasks()
        issues.extend(stale)

        # 2. Check thread is alive
        if self._thread and not self._thread.is_alive():
            issues.append("worker_thread_dead")

        # 3. Check message bus connectivity
        try:
            _ = self.bus.health()
        except Exception as e:
            issues.append(f"bus_unreachable: {e}")

        return issues

    def heal(self, issue: str) -> bool:
        """Override this to define custom healing actions.

        Returns True if healed, False if not.
        """
        if issue == "worker_thread_dead":
            log.warning("[HEAL] %s — restarting worker thread", self.name)
            self._running = True
            self._thread = threading.Thread(
                target=self._run_loop, daemon=True, name=self.name
            )
            self._thread.start()
            return True

        if "stale" in issue:
            # Extract the task ID from the issue string
            try:
                parts = issue.split(":")
                if len(parts) >= 2:
                    task_id = int(parts[1].strip())
                    self._active_tasks.pop(task_id, None)
                    return True
            except (ValueError, IndexError):
                pass

        return False

    def tick_heal(self):
        """Call this from tick() to enable auto-healing."""
        now = datetime.now()
        if self._last_heal_check and (now - self._last_heal_check).total_seconds() < self._heal_interval:
            return

        self._last_heal_check = now

        if self._health_status.in_cooldown:
            if self._health_status.cooldown_until and now >= self._health_status.cooldown_until:
                self._health_status.in_cooldown = False
                self._health_status.consecutive_failures = 0
                log.info("[HEAL] %s cooldown ended, resuming health checks", self.name)
            else:
                return

        try:
            issues = self.health_checks()
        except Exception as e:
            log.error("[HEAL] %s health check crashed: %s", self.name, e)
            self._record_failure()
            return

        if not issues:
            self._health_status.healthy = True
            self._health_status.consecutive_failures = 0
            return

        self._health_status.healthy = False
        self._health_status.issues = issues

        for issue in issues:
            cb_name = issue.split(":")[0] if ":" in issue else issue
            if cb_name not in self._circuit_breakers:
                self._circuit_breakers[cb_name] = CircuitBreaker(
                    f"{self.name}/{cb_name}"
                )

            cb = self._circuit_breakers[cb_name]
            if cb.is_open:
                log.debug("[HEAL] %s/%s circuit open, skipping heal", self.name, cb_name)
                continue

            try:
                healed = self.heal(issue)
            except Exception as e:
                log.error("[HEAL] %s heal crashed for %s: %s", self.name, issue, e)
                healed = False

            if healed:
                cb.record_success()
                log.info("[HEAL] %s healed: %s", self.name, issue)
            else:
                opened = cb.record_failure()
                log.warning("[HEAL] %s failed to heal %s (failures=%d)",
                            self.name, issue, cb.failures)
                if opened:
                    self._health_status.in_cooldown = True
                    self._health_status.cooldown_until = cb.cooldown_until

    def _detect_stale_tasks(self) -> list[str]:
        stale = []
        now = datetime.now()
        for tid, msg in list(self._active_tasks.items()):
            created = datetime.fromisoformat(msg.get("created_at", "2000-01-01"))
            age = (now - created).total_seconds()
            if age > 1800:  # 30 min
                stale.append(f"stale_task:{tid}")
        return stale

    def _record_failure(self):
        self._health_status.consecutive_failures += 1
        if self._health_status.consecutive_failures >= MAX_FAILURES_BEFORE_COOLDOWN:
            self._health_status.in_cooldown = True
            self._health_status.cooldown_until = datetime.now() + timedelta(seconds=COOLDOWN_SECONDS)
            log.warning("[HEAL] %s — %d consecutive failures, cooling down",
                        self.name, self._health_status.consecutive_failures)


class DependencyHealer:
    """Utility class to detect and fix missing Python dependencies."""

    REQUIRED_PACKAGES = {
        "browser-use": "browser_use",
        "langchain-openai": "langchain_openai",
        "mcp": "mcp",
        "fastapi": "fastapi",
        "edge-tts": "edge_tts",
        "Pillow": "PIL",
        "moviepy": "moviepy",
        "requests": "requests",
    }

    @classmethod
    def check_and_heal(cls) -> list[str]:
        """Check all required packages, attempt auto-install for missing ones.

        Returns list of actions taken.
        """
        actions = []
        for pkg, mod in cls.REQUIRED_PACKAGES.items():
            try:
                importlib.import_module(mod)
            except ImportError:
                log.warning("[HEAL] Missing dependency: %s — attempting auto-install", pkg)
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", "--quiet", pkg],
                        capture_output=True, text=True, timeout=60,
                    )
                    if result.returncode == 0:
                        actions.append(f"installed {pkg}")
                        log.info("[HEAL] Auto-installed %s", pkg)
                    else:
                        actions.append(f"failed {pkg}: {result.stderr[:100]}")
                        log.error("[HEAL] Failed to install %s: %s", pkg, result.stderr[:200])
                except Exception as e:
                    actions.append(f"error {pkg}: {e}")
                    log.error("[HEAL] Install error for %s: %s", pkg, e)
        return actions

    @classmethod
    def verify_all(cls) -> dict[str, bool]:
        """Return {package_name: is_installed} for all required packages."""
        result = {}
        for pkg, mod in cls.REQUIRED_PACKAGES.items():
            try:
                importlib.import_module(mod)
                result[pkg] = True
            except ImportError:
                result[pkg] = False
        return result
