"""
FreeCAD version compatibility module.

Detects installed FreeCAD version and gates features that require
specific minimum versions.  Allows the harness to work with both
FreeCAD 1.0.x and 1.1+.
"""

from __future__ import annotations

import functools
import re
from typing import Optional, Tuple

# Lazy-cached version tuple.  Populated by :func:`freecad_version`.
_cached_version: Optional[Tuple[int, ...]] = None


def freecad_version(force_refresh: bool = False) -> Tuple[int, ...]:
    """Return the installed FreeCAD version as a comparable tuple.

    Examples: ``(1, 0, 2)`` for FreeCAD 1.0.2, ``(1, 1, 0)`` for 1.1.

    Falls back to ``(0, 0, 0)`` when FreeCAD is not installed (offline /
    test mode).  The result is cached after the first successful call.
    """
    global _cached_version
    if _cached_version is not None and not force_refresh:
        return _cached_version

    try:
        from cli_anything.freecad.utils.freecad_backend import get_version

        raw = get_version()  # e.g. "1.0.2" or "1.1.0"
        nums = tuple(int(x) for x in re.findall(r"\d+", raw)[:3])
        _cached_version = nums if nums else (0, 0, 0)
    except Exception:
        # FreeCAD not installed — default to permissive (1.1) so pure-
        # state operations still work.  Real backend calls will fail
        # later with a clear "FreeCAD not found" message.
        _cached_version = (0, 0, 0)

    return _cached_version


def has_version(minimum: Tuple[int, ...]) -> bool:
    """Return ``True`` if the installed FreeCAD meets *minimum*."""
    ver = freecad_version()
    # (0,0,0) means unknown/offline — be permissive
    if ver == (0, 0, 0):
        return True
    return ver >= minimum


def require_version(
    minimum: Tuple[int, ...],
    feature_name: str,
) -> None:
    """Raise ``RuntimeError`` if FreeCAD is below *minimum*.

    Parameters
    ----------
    minimum:
        Version tuple, e.g. ``(1, 1, 0)``.
    feature_name:
        Human-readable name shown in the error message.
    """
    ver = freecad_version()
    if ver == (0, 0, 0):
        return  # unknown/offline — allow
    if ver < minimum:
        ver_str = ".".join(str(x) for x in ver)
        min_str = ".".join(str(x) for x in minimum)
        raise RuntimeError(
            f"'{feature_name}' requires FreeCAD >= {min_str}, "
            f"but {ver_str} is installed.  Upgrade FreeCAD or use "
            f"a command that is compatible with your version."
        )


# Convenience constants
V1_1 = (1, 1, 0)
V1_0 = (1, 0, 0)
