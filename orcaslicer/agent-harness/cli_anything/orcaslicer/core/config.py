"""OrcaSlicer CLI - setting overrides validated against the real binary's schema.

OrcaSlicer silently ignores unknown keys and fails with a cryptic config error on bad
values, so every override is checked here: the key must exist in the dump produced by
``OrcaSlicer --export-settings -`` and (when the default is numeric) the value must be numeric.
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from cli_anything.orcaslicer.core import profiles as prof
from cli_anything.orcaslicer.utils import orcaslicer_backend as backend

_NUMERIC = re.compile(r"^-?\d+(\.\d+)?%?$")
_TRUE = {"true", "yes", "on"}
_FALSE = {"false", "no", "off"}


@lru_cache(maxsize=1)
def categories() -> Dict[str, str]:
    """key -> 'machine' | 'process' | 'filament' (derived from OrcaSlicer's Preset.cpp)."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "config_categories.json")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def get_schema() -> Dict[str, Any]:
    """Every valid config key with its default value, straight from the installed binary."""
    return backend.export_default_settings()


def complete_filament(preset: Dict[str, Any], schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Fill every per-filament key a preset does not define with the binary's own default.

    With more than one filament OrcaSlicer requires all per-filament vectors to be present in every
    filament preset ("filament_is_support's count 1 not equal to filament_colour's size 2" →
    CLI_CONFIG_FILE_ERROR). Explicit preset values always win.
    """
    schema = schema if schema is not None else get_schema()
    cats = categories()
    out = {k: v for k, v in schema.items() if cats.get(k) == "filament"}
    out.update(preset)
    return out


def category_of(key: str) -> Optional[str]:
    return categories().get(key)


def _is_numeric_default(default: Any) -> bool:
    d = default[0] if isinstance(default, list) and default else default
    return isinstance(d, str) and bool(_NUMERIC.match(d))


def normalize_value(key: str, value: Any, schema: Dict[str, Any]) -> Any:
    """Coerce a user-supplied value into OrcaSlicer's on-disk representation."""
    default = schema[key]
    is_vector = isinstance(default, list)

    if isinstance(value, str) and value.strip().startswith("["):
        try:
            value = json.loads(value)
        except ValueError as exc:
            raise ValueError(f"Value for '{key}' looks like a JSON array but is invalid: {exc}")
    if isinstance(value, (list, tuple)) and not is_vector:
        raise ValueError(f"'{key}' takes a single value, got a list.")

    def one(v: Any) -> str:
        if isinstance(v, bool):
            return "1" if v else "0"
        if isinstance(v, (int, float)):
            return f"{v:g}" if isinstance(v, float) else str(v)
        s = str(v)
        sample = default[0] if is_vector and default else default
        if sample in ("0", "1") and s.strip().lower() in _TRUE | _FALSE:
            return "1" if s.strip().lower() in _TRUE else "0"
        return s

    if is_vector:
        items = list(value) if isinstance(value, (list, tuple)) else [value]
        if not items:
            raise ValueError(f"'{key}' needs at least one value.")
        norm: Any = [one(v) for v in items]
        check = norm
    else:
        norm = one(value)
        check = [norm]

    if _is_numeric_default(default):
        for c in check:
            if c != "nil" and not _NUMERIC.match(c):
                raise ValueError(
                    f"'{key}' expects a number (default {default!r}), got {c!r}.")
    return norm


def resolve_kind(key: str, kind: Optional[str] = None) -> str:
    if kind:
        prof._check_kind(kind)
        return kind
    cat = category_of(key)
    if cat is None:
        raise ValueError(
            f"Cannot tell which preset kind '{key}' belongs to (it may be a project-level "
            "setting). Pass --kind machine|process|filament.")
    return cat


def set_override(project: Dict[str, Any], key: str, value: Any, kind: Optional[str] = None,
                 schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    schema = schema if schema is not None else get_schema()
    if key not in schema:
        close = suggest(key, schema)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        raise ValueError(f"Unknown setting '{key}'.{hint} Use 'config keys --search TEXT' to find valid keys.")
    k = resolve_kind(key, kind)
    norm = normalize_value(key, value, schema)
    project["overrides"][k][key] = norm
    return {"key": key, "kind": k, "value": norm}


def unset_override(project: Dict[str, Any], key: str, kind: Optional[str] = None) -> Dict[str, Any]:
    kinds = [kind] if kind else list(prof.KINDS)
    for k in kinds:
        if key in project["overrides"].get(k, {}):
            old = project["overrides"][k].pop(key)
            return {"key": key, "kind": k, "removed": old}
    raise KeyError(f"No override for '{key}'. Use 'config list' to see overrides.")


def list_overrides(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{"kind": k, "key": key, "value": v}
            for k in prof.KINDS for key, v in sorted(project["overrides"].get(k, {}).items())]


def get_effective(project: Dict[str, Any], key: str, kind: Optional[str] = None,
                  schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a setting's effective value and where it comes from."""
    schema = schema if schema is not None else get_schema()
    if key not in schema:
        raise ValueError(f"Unknown setting '{key}'. Use 'config keys --search TEXT'.")
    k = resolve_kind(key, kind)
    if key in project["overrides"][k]:
        return {"key": key, "kind": k, "value": project["overrides"][k][key], "source": "override"}
    refs = project["profiles"]
    ref = refs["filaments"][0] if k == "filament" else refs[k]
    preset = prof.resolve(k, ref, refs.get("dirs"))
    if key in preset:
        return {"key": key, "kind": k, "value": preset[key], "source": f"preset:{preset.get('name', ref)}"}
    return {"key": key, "kind": k, "value": schema[key], "source": "default"}


def suggest(key: str, schema: Dict[str, Any], n: int = 5) -> List[str]:
    import difflib
    return difflib.get_close_matches(key, list(schema), n=n, cutoff=0.6)


def search_keys(query: str = "", kind: Optional[str] = None, limit: int = 50,
                schema: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    schema = schema if schema is not None else get_schema()
    q = query.lower()
    out = []
    for key in sorted(schema):
        if q and q not in key.lower():
            continue
        cat = category_of(key)
        if kind and cat != kind:
            continue
        out.append({"key": key, "kind": cat, "default": schema[key]})
        if len(out) >= limit:
            break
    return out
