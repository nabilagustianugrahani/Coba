"""Shared error types for UGC AI Overpower."""
from __future__ import annotations


class ConfigError(RuntimeError):
    """Raised when a required configuration is not loaded or is invalid.

    Subclasses RuntimeError so existing ``except RuntimeError`` blocks still
    catch it.  Used by adapters that lazily populate their config from env vars
    and need to fail loudly if the config is missing at call time.
    """


__all__ = ["ConfigError"]
