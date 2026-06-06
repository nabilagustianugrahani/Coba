"""Launch the web dashboard with proper config and graceful shutdown."""

from __future__ import annotations

import logging
import os
import signal
import socket
import sys
from dataclasses import dataclass, field

logger = logging.getLogger("dashboard-launcher")


@dataclass
class DashboardConfig:
    """Configuration for the web dashboard server."""
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    workers: int = 1
    log_level: str = "info"


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a TCP port is already in use on *host*."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def find_available_port(start: int = 8000, host: str = "127.0.0.1") -> int:
    """Return the first available port starting from *start*."""
    port = start
    while port < start + 100:
        if not is_port_in_use(port, host):
            return port
        port += 1
    raise RuntimeError(f"No available port found starting from {start}")


def launch_dashboard(config: DashboardConfig) -> None:
    """Start the Uvicorn server for the web dashboard.

    Handles SIGINT/SIGTERM for graceful shutdown.
    """
    from ugc_ai_overpower.web.dashboard import app

    if is_port_in_use(config.port, config.host):
        print(
            f"  ✗ Port {config.port} on {config.host} is already in use.\n"
            f"    Try: ugc ui --port {find_available_port(config.port)}"
        )
        sys.exit(1)

    pid = os.getpid()
    url = f"http://{config.host}:{config.port}"
    print(f"  ℹ Dashboard starting on {url}  (pid={pid})")
    print(f"  ℹ Workers: {config.workers}  Reload: {config.reload}")

    # Graceful shutdown on SIGINT/SIGTERM
    shutdown = False

    def _signal_handler(signum, frame):
        nonlocal shutdown
        if shutdown:
            return
        shutdown = True
        print(f"\n  ✓ Shutting down dashboard (pid={pid})…")
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        import uvicorn
        uvicorn.run(
            app,
            host=config.host,
            port=config.port,
            reload=config.reload,
            workers=config.workers,
            log_level=config.log_level,
        )
    except Exception as exc:
        print(f"  ✗ Failed to start dashboard: {exc}")
        print(f"    Hint: check that port {config.port} is available")
        print(f"    Or try: ugc ui --port {config.port + 1}")
        sys.exit(1)
