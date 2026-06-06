"""Structured logging with JSON output, file rotation, and async safety.

Features:
- JSON formatter for production log ingestion
- Pretty console formatter for local development
- Per-module log levels via ``LOG_LEVEL_<MODULE>`` env vars
- Request ID injection via ``contextvars`` (async-safe)
- Rotating file handler (10 MB × 5 backups)
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

__all__ = [
    "request_id_var",
    "JSONFormatter",
    "PrettyConsoleFormatter",
    "setup_logging",
    "apply_env_log_levels",
]

# Async-safe request ID carried through the call stack.
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects.

    Extra keyword arguments passed via ``logging.debug(..., extra={})``
    are merged into the output automatically.
    """

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
            "request_id": request_id_var.get(),
        }
        # Fold in extra fields passed via log call
        extra_keys = set(record.__dict__.keys()) - {
            "args", "asctime", "created", "exc_info", "exc_text",
            "filename", "funcName", "id", "levelname", "levelno",
            "lineno", "module", "msecs", "message", "msg",
            "name", "pathname", "process", "processName",
            "relativeCreated", "stack_info", "thread", "threadName",
        }
        for k in extra_keys:
            entry[k] = record.__dict__[k]

        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            entry["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(entry, ensure_ascii=False)


_COLORS = {
    "DEBUG": "\033[36m",       # cyan
    "INFO": "\033[32m",        # green
    "WARNING": "\033[33m",     # yellow
    "ERROR": "\033[31m",       # red
    "CRITICAL": "\033[35m",    # magenta
    "RESET": "\033[0m",
}


class PrettyConsoleFormatter(logging.Formatter):
    """Human-readable, colorized console format for development."""

    def format(self, record: logging.LogRecord) -> str:
        color = _COLORS.get(record.levelname, _COLORS["RESET"])
        reset = _COLORS["RESET"]
        req_id = request_id_var.get()
        rid = f" [rid={req_id}]" if req_id else ""
        return (
            f"{self.formatTime(record, '%H:%M:%S')} "
            f"{color}{record.levelname:8s}{reset} "
            f"{record.name:>20s} │ "
            f"{record.getMessage()}{rid}"
        )


def setup_logging(
    name: str = "skynet",
    level: int = logging.INFO,
    *,
    log_dir: str = "logs",
    max_bytes: int = 10_485_760,
    backup_count: int = 5,
    console_json: Optional[bool] = None,
) -> logging.Logger:
    """Configure a logger with JSON file output and console output.

    Parameters
    ----------
    name:
        Logger name (also used as the log file basename).
    level:
        Minimum log level for the logger.
    log_dir:
        Directory to store rotated log files.
    max_bytes:
        Maximum size of a single log file before rotation.
    backup_count:
        Number of rotated backup files to keep.
    console_json:
        If True, console handler also uses JSON format.
        If ``None``, reads ``LOG_FORMAT`` env var (default: plain text).
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    # Apply per-module overrides from environment
    apply_env_log_levels()

    os.makedirs(log_dir, exist_ok=True)

    # --- File handler (JSON, rotated) ---
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, f"{name}.log"),
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)

    # --- Console handler ---
    console_handler = logging.StreamHandler(sys.stdout)

    if console_json is None:
        console_json = os.getenv("LOG_FORMAT", "").lower() == "json"

    if console_json:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(PrettyConsoleFormatter())

    logger.addHandler(console_handler)

    return logger


def apply_env_log_levels() -> None:
    """Read ``LOG_LEVEL_<MODULE>`` env vars and set per-module log levels.

    Example::

        LOG_LEVEL_UGC=DEBUG        → logging.getLogger("ugc").setLevel(DEBUG)
        LOG_LEVEL_UGC_AI_TOOLS=WARNING  → logging.getLogger("ugc.ai_tools").setLevel(WARNING)
    """
    prefix = "LOG_LEVEL_"
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        module_name = key[len(prefix):].lower().replace("_", ".")
        level = getattr(logging, value.upper(), None)
        if isinstance(level, int):
            logging.getLogger(module_name).setLevel(level)
