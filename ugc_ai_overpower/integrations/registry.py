"""Adapter registry — auto-discovers and routes platform adapters.

All platform adapters register themselves via @register_adapter decorator.
The registry is the single source of truth for which platforms are available.
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Any, Optional

from ugc_ai_overpower.integrations.base import PlatformAdapter, PlatformCategory, Region

log = logging.getLogger(__name__)

_REGISTRY: dict[str, PlatformAdapter] = {}


def register_adapter(cls: type[PlatformAdapter]) -> type[PlatformAdapter]:
    """Class decorator that registers an adapter in the global registry."""
    if not cls.platform:
        raise ValueError(f"{cls.__name__} must set class attribute 'platform'")
    instance = cls()
    _REGISTRY[cls.platform] = instance
    log.debug("Registered adapter: %s (%s)", cls.platform, cls.category.value)
    return cls


def get_adapter(platform: str) -> Optional[PlatformAdapter]:
    """Get a single adapter by platform name."""
    return _REGISTRY.get(platform)


def list_adapters(category: Optional[PlatformCategory] = None,
                  region: Optional[Region] = None) -> list[PlatformAdapter]:
    """List all registered adapters, optionally filtered."""
    adapters = list(_REGISTRY.values())
    if category is not None:
        adapters = [a for a in adapters if a.category == category]
    if region is not None:
        adapters = [a for a in adapters if a.region == region]
    return adapters


def list_platforms(category: Optional[PlatformCategory] = None) -> list[str]:
    """List platform names, optionally filtered by category."""
    adapters = list_adapters(category=category)
    return sorted(a.platform for a in adapters)


def auto_discover(package_path: str = "ugc_ai_overpower.integrations.social") -> int:
    """Auto-discover adapters by importing all submodules.

    Each submodule that defines adapter classes with @register_adapter will
    be picked up automatically. Returns the number of adapters discovered.
    """
    before = len(_REGISTRY)
    package = importlib.import_module(package_path)
    for _finder, name, _is_pkg in pkgutil.iter_modules(package.__path__):
        full_name = f"{package_path}.{name}"
        try:
            importlib.import_module(full_name)
            log.debug("Imported adapter module: %s", full_name)
        except Exception as e:
            log.warning("Failed to import %s: %s", full_name, e)
    return len(_REGISTRY) - before


def get_registry_stats() -> dict[str, Any]:
    """Return summary stats about the registry."""
    adapters = list(_REGISTRY.values())
    by_category: dict[str, int] = {}
    by_region: dict[str, int] = {}
    configured = 0
    for a in adapters:
        by_category[a.category.value] = by_category.get(a.category.value, 0) + 1
        by_region[a.region.value] = by_region.get(a.region.value, 0) + 1
        if a.is_configured():
            configured += 1
    return {
        "total": len(adapters),
        "configured": configured,
        "by_category": by_category,
        "by_region": by_region,
        "platforms": sorted(a.platform for a in adapters),
    }
