"""Auto-discover all Adapter subclasses in this package."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Type

from .base import Adapter

_registry: Dict[str, Type[Adapter]] = {}


def _discover() -> None:
    """Import every module in this package so Adapter subclasses register."""
    pkg_dir = Path(__file__).parent
    for info in pkgutil.iter_modules([str(pkg_dir)]):
        if info.name == "base":
            continue
        importlib.import_module(f".{info.name}", __package__)
    for cls in Adapter.__subclasses__():
        _registry[cls.name] = cls


def get_adapters() -> Dict[str, Type[Adapter]]:
    if not _registry:
        _discover()
    return _registry
