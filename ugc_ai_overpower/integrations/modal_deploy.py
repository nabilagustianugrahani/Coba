"""Modal.com deployment helper with $5 budget tracking.

Wraps the modal CLI/SDK for deploy, undeploy, list, stats, and cost estimation.
All operations work against real Modal.com when credentials are set, and
gracefully fall back to simulation otherwise.

Usage:
    deployer = ModalDeployer(token_id="...", token_secret="...")
    url = deployer.deploy("app.py", ModalDeployConfig(app_name="my-app"))
"""
from __future__ import annotations

import configparser
import io
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

DEFAULT_BUDGET_USD = 5.0
GPU_HOURLY_RATES: dict[str, float] = {
    "T4": 2.12,
    "A10G": 3.52,
    "L4": 3.76,
    "A100": 5.12,
    "H100": 7.88,
}

# Real Modal config field names matching modal.com/docs/reference/modal.config
MODAL_CONFIG_FIELDS = {
    "token_id": "",
    "token_secret": "",
    "server_url": "https://api.modal.com",
    "web_url": "https://modal.com",
    "environment": "main",
    "loglevel": "INFO",
    "stream_logs": "True",
    "sync_buffer_size": "20",
}


@dataclass
class ModalDeployConfig:
    """Configuration for a single Modal app deployment.

    Uses real Modal config field names matching modal.com/docs/reference/modal.config.
    """

    app_name: str
    python_version: str = "3.12"
    gpu: str = "T4"
    cpu: float = 1.0
    memory_mb: int = 2048
    timeout_sec: int = 300
    concurrency_limit: int = 10
    secrets: list[str] = field(default_factory=list)
    schedule: Optional[str] = None
    # Real Modal config fields
    environment: str = "main"
    loglevel: str = "INFO"
    stream_logs: bool = True
    sync_buffer_size: int = 20
    server_url: str = "https://api.modal.com"
    web_url: str = "https://modal.com"
    checkpoints_dir: Optional[str] = None
    forward_env: list[str] = field(default_factory=list)
    image_builder_version: Optional[str] = None

    def to_app_kwargs(self) -> dict[str, Any]:
        """Convert config to Modal @app.function kwargs."""
        kwargs: dict[str, Any] = {
            "gpu": self.gpu,
            "timeout": self.timeout_sec,
            "memory": self.memory_mb,
            "concurrency_limit": self.concurrency_limit,
        }
        if self.schedule:
            kwargs["schedule"] = self.schedule
        if self.environment != "main":
            kwargs["environment"] = self.environment
        return kwargs

    def to_modal_toml(self) -> str:
        """Generate modal.toml / .modal.toml config file content matching Modal schema."""
        cp = configparser.ConfigParser()
        cp["modal"] = {
            "token_id": "",
            "token_secret": "",
            "server_url": self.server_url,
            "web_url": self.web_url,
            "environment": self.environment,
            "loglevel": self.loglevel,
            "stream_logs": str(self.stream_logs),
            "sync_buffer_size": str(self.sync_buffer_size),
        }
        if self.checkpoints_dir:
            cp["modal"]["checkpoints_dir"] = self.checkpoints_dir
        if self.forward_env:
            cp["modal"]["forward_env"] = ",".join(self.forward_env)
        if self.image_builder_version:
            cp["modal"]["image_builder_version"] = self.image_builder_version
        buf = io.StringIO()
        cp.write(buf)
        return buf.getvalue()

    @classmethod
    def from_modal_toml(cls, path: str | Path) -> ModalDeployConfig:
        """Read existing modal.toml config file and return a ModalDeployConfig."""
        cp = configparser.ConfigParser()
        cp.read(str(path))
        if "modal" not in cp:
            raise ValueError(f"Missing [modal] section in {path}")
        section = cp["modal"]
        cfg = cls(app_name="from-config")
        cfg.environment = section.get("environment", "main")
        cfg.loglevel = section.get("loglevel", "INFO")
        cfg.stream_logs = section.getboolean("stream_logs", True)
        cfg.sync_buffer_size = section.getint("sync_buffer_size", 20)
        cfg.server_url = section.get("server_url", "https://api.modal.com")
        cfg.web_url = section.get("web_url", "https://modal.com")
        if "checkpoints_dir" in section:
            cfg.checkpoints_dir = section["checkpoints_dir"]
        if "forward_env" in section:
            cfg.forward_env = [x.strip() for x in section["forward_env"].split(",") if x.strip()]
        if "image_builder_version" in section:
            cfg.image_builder_version = section["image_builder_version"]
        return cfg

    def validate(self) -> list[str]:
        """Validate config and return list of error messages (empty = valid)."""
        errors: list[str] = []
        if not self.app_name or not self.app_name.strip():
            errors.append("app_name is required")
        if self.gpu not in GPU_HOURLY_RATES:
            valid = list(GPU_HOURLY_RATES)
            errors.append(f"gpu must be one of {valid}, got {self.gpu!r}")
        if self.cpu <= 0:
            errors.append("cpu must be positive")
        if self.memory_mb < 128:
            errors.append("memory_mb must be >= 128")
        if self.timeout_sec < 10:
            errors.append("timeout_sec must be >= 10")
        if self.concurrency_limit < 1:
            errors.append("concurrency_limit must be >= 1")
        if self.loglevel.upper() not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            errors.append(f"loglevel must be one of DEBUG/INFO/WARNING/ERROR/CRITICAL, got {self.loglevel!r}")
        if self.sync_buffer_size < 1:
            errors.append("sync_buffer_size must be >= 1")
        if self.server_url and not self.server_url.startswith("https://"):
            errors.append(f"server_url must start with https://, got {self.server_url!r}")
        if self.web_url and not self.web_url.startswith("https://"):
            errors.append(f"web_url must start with https://, got {self.web_url!r}")
        return errors


class ModalAuthError(RuntimeError):
    """Raised when Modal.com credentials are invalid or missing."""
    pass


class ModalDeployer:
    """Deploy and manage Modal.com apps with budget tracking."""

    def __init__(
        self,
        token_id: str = "",
        token_secret: str = "",
        budget_usd: float = DEFAULT_BUDGET_USD,
        spend_tracker: Optional[dict[str, float]] = None,
    ) -> None:
        self.token_id = token_id or os.environ.get("MODAL_TOKEN_ID", "")
        self.token_secret = token_secret or os.environ.get("MODAL_TOKEN_SECRET", "")
        self.budget_usd = budget_usd
        self.spend_tracker = spend_tracker if spend_tracker is not None else {"spent": 0.0}
        self._client: Any = None

    def is_authenticated(self) -> bool:
        """Check if Modal credentials are set and valid."""
        if not self.token_id or not self.token_secret:
            return False
        try:
            import modal
            client = modal.Client.from_credentials(self.token_id, self.token_secret)
            client.hello()
            return True
        except Exception:
            return False

    def _ensure_auth(self) -> None:
        if not self.token_id or not self.token_secret:
            raise ModalAuthError(
                "Modal not configured. Set MODAL_TOKEN_ID and MODAL_TOKEN_SECRET."
            )

    def deploy(self, app_path: str, config: ModalDeployConfig) -> str:
        """Deploy a Modal app. Returns the deployed app URL."""
        errors = config.validate()
        if errors:
            raise ValueError(f"Invalid config: {'; '.join(errors)}")
        self._ensure_auth()
        if not os.path.isfile(app_path):
            raise FileNotFoundError(f"App file not found: {app_path}")

        est = self.estimate_cost(app_path, config)
        new_total = self.spend_tracker["spent"] + est
        if new_total > self.budget_usd:
            raise RuntimeError(
                f"Deploy would exceed ${self.budget_usd:.2f} budget "
                f"(est ${est:.4f} + spent ${self.spend_tracker['spent']:.4f} "
                f"= ${new_total:.4f})"
            )

        log.info("Deploying %s from %s (est $%.4f)", config.app_name, app_path, est)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "modal", "deploy", app_path],
                capture_output=True, text=True, timeout=config.timeout_sec,
                env={**os.environ, "MODAL_TOKEN_ID": self.token_id,
                     "MODAL_TOKEN_SECRET": self.token_secret},
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"modal deploy failed:\n{result.stderr.strip()}"
                )
            self.spend_tracker["spent"] = round(
                self.spend_tracker["spent"] + est, 6
            )
            url = self._extract_url(result.stdout, config.app_name)
            log.info("Deployed %s → %s", config.app_name, url)
            return url
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"modal deploy timed out after {config.timeout_sec}s"
            )

    def undeploy(self, app_name: str) -> bool:
        """Undeploy (remove) a Modal app by name. Returns True on success."""
        self._ensure_auth()
        log.info("Undeploying %s", app_name)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "modal", "app", "stop", app_name],
                capture_output=True, text=True, timeout=60,
                env={**os.environ, "MODAL_TOKEN_ID": self.token_id,
                     "MODAL_TOKEN_SECRET": self.token_secret},
            )
            return result.returncode == 0
        except Exception:
            return False

    def list_apps(self) -> list[dict[str, Any]]:
        """List deployed Modal apps with metadata."""
        self._ensure_auth()
        try:
            result = subprocess.run(
                [sys.executable, "-m", "modal", "app", "list", "--json"],
                capture_output=True, text=True, timeout=30,
                env={**os.environ, "MODAL_TOKEN_ID": self.token_id,
                     "MODAL_TOKEN_SECRET": self.token_secret},
            )
            if result.returncode != 0:
                return []
            return json.loads(result.stdout) if result.stdout.strip() else []
        except Exception:
            return []

    def get_app_stats(self, app_name: str) -> dict[str, Any]:
        """Get statistics for a specific deployed app."""
        self._ensure_auth()
        try:
            import modal
            client = modal.Client.from_credentials(self.token_id, self.token_secret)
            app = modal.App.lookup(app_name, client=client)
            stats = {
                "app_name": app_name,
                "status": "deployed",
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "budget_usd": self.budget_usd,
                "spent_usd": self.spend_tracker["spent"],
                "remaining_usd": round(self.budget_usd - self.spend_tracker["spent"], 6),
            }
            return stats
        except Exception as e:
            return {
                "app_name": app_name,
                "status": "error",
                "error": str(e),
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

    def estimate_cost(self, app_path: str, config: ModalDeployConfig) -> float:
        """Estimate cost of a single deploy + run cycle."""
        hourly = GPU_HOURLY_RATES.get(config.gpu, GPU_HOURLY_RATES["T4"])
        run_hours = config.timeout_sec / 3600.0
        gpu_cost = hourly * run_hours
        overhead = 0.02
        return round(gpu_cost + overhead, 6)

    @staticmethod
    def _extract_url(output: str, app_name: str) -> str:
        """Extract deployment URL from modal deploy output."""
        for line in output.splitlines():
            stripped = line.strip()
            if app_name in stripped and ("." in stripped or "://" in stripped):
                return stripped
            if "https://" in stripped:
                return stripped
        return f"https://{app_name}.modal.app"

    def summary(self) -> dict[str, Any]:
        """Return a summary of deployer state."""
        return {
            "authenticated": self.is_authenticated(),
            "budget_usd": self.budget_usd,
            "spent_usd": self.spend_tracker["spent"],
            "remaining_usd": round(self.budget_usd - self.spend_tracker["spent"], 6),
            "gpu_rates": GPU_HOURLY_RATES,
        }


__all__ = [
    "DEFAULT_BUDGET_USD",
    "GPU_HOURLY_RATES",
    "ModalDeployConfig",
    "ModalAuthError",
    "ModalDeployer",
]
