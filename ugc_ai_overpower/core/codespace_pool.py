from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_POOL_PATH = Path(__file__).resolve().parents[2] / ".opencode" / "codespace_pool.json"


class CodespacePool:
    """Round-robin scheduler for a pool of GitHub Codespaces.

    Each pool member represents an isolated execution environment with its
    own opencode session and model assignment, used to bypass per-model
    rate limits by parallelising work across codespaces.
    """

    def __init__(self, config_path: str | os.PathLike | None = None) -> None:
        self.config_path = Path(config_path) if config_path else DEFAULT_POOL_PATH
        self._lock = threading.Lock()
        self._cursor = 0
        self._health_cache: dict[str, dict[str, Any]] = {}
        self.config = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Codespace pool config not found: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or "pool" not in data:
            raise ValueError("Invalid codespace_pool.json: missing 'pool' key")
        if not isinstance(data["pool"], list) or not data["pool"]:
            raise ValueError("Invalid codespace_pool.json: 'pool' must be a non-empty list")
        data.setdefault("scheduler", {})
        data["scheduler"].setdefault("strategy", "round_robin")
        data["scheduler"].setdefault("health_check_interval_seconds", 60)
        data["scheduler"].setdefault("max_concurrent_per_pool", 3)
        return data

    @property
    def pool(self) -> list[dict[str, Any]]:
        return list(self.config["pool"])

    @property
    def scheduler(self) -> dict[str, Any]:
        return dict(self.config["scheduler"])

    def reload(self) -> None:
        with self._lock:
            self.config = self._load_config()
            self._cursor = 0
            self._health_cache.clear()

    def get_next_codespace(self) -> dict[str, Any]:
        """Return next pool member using configured strategy (round-robin default)."""
        with self._lock:
            members = self.config["pool"]
            if not members:
                raise RuntimeError("Codespace pool is empty")
            strategy = self.config["scheduler"].get("strategy", "round_robin")
            if strategy == "primary_with_failover":
                primary = next((m for m in members if m.get("role") == "primary"), members[0])
                if self._is_healthy(primary):
                    return dict(primary)
                logger.warning("Primary unhealthy — trying failover")
                for fail in (m for m in members if m.get("role") == "failover"):
                    if self._is_healthy(fail):
                        logger.info("Failover active: %s", fail["name"])
                        return dict(fail)
                logger.error("All failover codespaces unhealthy — using primary anyway")
                return dict(primary)
            if strategy != "round_robin":
                logger.warning("Unsupported scheduler strategy '%s' - falling back to round_robin", strategy)
            member = members[self._cursor % len(members)]
            self._cursor = (self._cursor + 1) % len(members)
            return dict(member)

    def _is_healthy(self, member: dict[str, Any]) -> bool:
        cs_name = member.get("codespace")
        if not cs_name:
            return False
        cached = self._health_cache.get(cs_name)
        if cached and (time.time() - cached.get("checked_at", 0)) < 60:
            return cached["health"].get("available", False)
        health = self._check_codespace_health(cs_name)
        self._health_cache[cs_name] = {"checked_at": time.time(), "health": health}
        return health.get("available", False)

    def _gh_available(self) -> bool:
        return shutil.which("gh") is not None

    def _check_codespace_health(self, name: str) -> dict[str, Any]:
        """Return {available: bool, state: str, error: str|None} for a codespace."""
        if not self._gh_available():
            return {"available": False, "state": "unknown", "error": "gh CLI not installed"}
        try:
            result = subprocess.run(
                ["gh", "codespace", "view", "-c", name, "--json", "state,name"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                return {
                    "available": False,
                    "state": "missing",
                    "error": result.stderr.strip() or "codespace not found",
                }
            info = json.loads(result.stdout or "{}")
            state = info.get("state", "unknown")
            available = state.lower() in {"available", "running", "started"}
            return {"available": available, "state": state, "error": None}
        except subprocess.TimeoutExpired:
            return {"available": False, "state": "timeout", "error": "gh codespace view timed out"}
        except Exception as exc:
            return {"available": False, "state": "error", "error": str(exc)}

    def pool_status(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Report health status of every pool member."""
        ttl = self.config["scheduler"].get("health_check_interval_seconds", 60)
        now = time.time()
        status: list[dict[str, Any]] = []
        with self._lock:
            for member in self.config["pool"]:
                name = member["name"]
                cached = self._health_cache.get(name)
                if (
                    not force_refresh
                    and cached
                    and (now - cached.get("checked_at", 0)) < ttl
                ):
                    health = cached["health"]
                else:
                    health = self._check_codespace_health(name)
                    self._health_cache[name] = {"checked_at": now, "health": health}
                status.append(
                    {
                        "name": name,
                        "model": member.get("model"),
                        "region": member.get("region"),
                        "machine": member.get("machine"),
                        "healthy": health["available"],
                        "state": health["state"],
                        "error": health["error"],
                    }
                )
        return status

    def dispatch_task(
        self,
        task_desc: str,
        *,
        codespace: dict[str, Any] | None = None,
        timeout: int = 600,
        extra_env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Dispatch a task to a codespace via `gh codespace ssh`.

        Uses opencode CLI inside the codespace with the assigned model.
        Returns {codespace, model, returncode, stdout, stderr}.
        """
        if not task_desc or not task_desc.strip():
            raise ValueError("task_desc must be a non-empty string")
        if codespace is None:
            codespace = self.get_next_codespace()
        if not self._gh_available():
            return {
                "codespace": codespace["name"],
                "model": codespace.get("model"),
                "returncode": 127,
                "stdout": "",
                "stderr": "gh CLI not installed - cannot dispatch to codespace",
                "dispatched": False,
            }

        model = codespace.get("model", "opencode/deepseek-v4-flash-free")
        env_exports = ""
        if extra_env:
            for key, value in extra_env.items():
                env_exports += f"export {key}={subprocess.list2cmdline([value])}; "
        remote_cmd = (
            f"{env_exports}"
            f"cd /workspaces/ugc_ai_overpower 2>/dev/null || cd ~; "
            f"opencode run --model {subprocess.list2cmdline([model])} "
            f"{subprocess.list2cmdline([task_desc])}"
        )
        cmd = ["gh", "codespace", "ssh", "-c", codespace["name"], "--", "bash", "-lc", remote_cmd]
        logger.info("Dispatching to codespace %s (model=%s)", codespace["name"], model)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "codespace": codespace["name"],
                "model": model,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "dispatched": True,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "codespace": codespace["name"],
                "model": model,
                "returncode": 124,
                "stdout": exc.stdout or "",
                "stderr": f"timed out after {timeout}s",
                "dispatched": True,
            }
        except Exception as exc:
            return {
                "codespace": codespace["name"],
                "model": model,
                "returncode": 1,
                "stdout": "",
                "stderr": str(exc),
                "dispatched": False,
            }


_default_pool: CodespacePool | None = None


def get_default_pool() -> CodespacePool:
    global _default_pool
    if _default_pool is None:
        _default_pool = CodespacePool()
    return _default_pool
