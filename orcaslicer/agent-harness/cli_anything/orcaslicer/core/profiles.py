"""OrcaSlicer CLI - printer / process / filament presets.

OrcaSlicer's CLI (--load-settings / --load-filaments) takes *flattened* preset JSON
files; it does not resolve ``inherits`` chains. This module:

* ships a few original, minimal built-in "generic" presets (layered by the real
  binary on top of its own defaults),
* discovers vendor/user presets (JSON) in OrcaSlicer's preset directories or in
  directories supplied by the user, and flattens their ``inherits`` chains,
* materialises the final preset JSON (preset + project overrides) for a slice.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

KINDS = ("machine", "process", "filament")


# ── Built-in generic presets (original value sets) ───────────────

def _machine(name: str, x: int, y: int, z: int) -> Dict[str, Any]:
    return {
        "type": "machine", "name": name, "from": "system", "gcode_flavor": "marlin",
        "printer_technology": "FFF",
        "printable_area": [f"0x0", f"{x}x0", f"{x}x{y}", f"0x{y}"],
        "printable_height": str(z),
        "nozzle_diameter": ["0.4"],
        # Without these the real binary fails validation ("clearance ... invalid value 0").
        "extruder_clearance_radius": "60",
        "extruder_clearance_height_to_rod": "40",
        "extruder_clearance_height_to_lid": "120",
        # Relative extruder addressing requires an E reset at each layer.
        "layer_change_gcode": "G92 E0",
        "machine_start_gcode": "G28 ; home all\nG90\nM83\nG92 E0",
        "machine_end_gcode": "M104 S0 ; hotend off\nM140 S0 ; bed off\nM107 ; fan off\nM84 ; motors off",
    }


def _process(name: str, layer_height: float, **extra: str) -> Dict[str, Any]:
    d = {"type": "process", "name": name, "from": "system", "layer_height": f"{layer_height:g}"}
    d.update(extra)
    return d


def _filament(name: str, ftype: str, nozzle: int, bed: int, density: float, cost: int,
              flow: float = 0.98, fan_min: int = 100) -> Dict[str, Any]:
    temps = {}
    for plate in ("cool_plate", "eng_plate", "hot_plate", "textured_plate"):
        temps[f"{plate}_temp"] = [str(bed)]
        temps[f"{plate}_temp_initial_layer"] = [str(bed)]
    d = {
        "type": "filament", "name": name, "from": "system",
        "filament_type": [ftype],
        "filament_diameter": ["1.75"],  # REQUIRED: a missing value segfaults OrcaSlicer 2.5
        "filament_density": [f"{density:g}"],
        "filament_cost": [str(cost)],
        "filament_flow_ratio": [f"{flow:g}"],
        "nozzle_temperature": [str(nozzle)],
        "nozzle_temperature_initial_layer": [str(nozzle + 5)],
        "fan_min_speed": [str(fan_min if ftype in ("PLA",) else 40)],
        "fan_max_speed": [str(100 if ftype in ("PLA", "PETG") else 50)],
    }
    d.update(temps)
    return d


BUILTIN: Dict[str, Dict[str, Dict[str, Any]]] = {
    "machine": {
        "Generic FDM 220": _machine("Generic FDM 220", 220, 220, 250),
        "Generic FDM 256": _machine("Generic FDM 256", 256, 256, 256),
        "Generic FDM 350": _machine("Generic FDM 350", 350, 350, 350),
    },
    "process": {
        "0.08mm Extra Fine": _process("0.08mm Extra Fine", 0.08),
        "0.12mm Fine": _process("0.12mm Fine", 0.12),
        "0.16mm Optimal": _process("0.16mm Optimal", 0.16),
        "0.20mm Standard": _process("0.20mm Standard", 0.20),
        "0.20mm Strength": _process("0.20mm Strength", 0.20, wall_loops="4",
                                    sparse_infill_density="25%"),
        "0.24mm Draft": _process("0.24mm Draft", 0.24),
        "0.28mm Extra Draft": _process("0.28mm Extra Draft", 0.28),
    },
    "filament": {
        "Generic PLA": _filament("Generic PLA", "PLA", 210, 60, 1.24, 20),
        "Generic PETG": _filament("Generic PETG", "PETG", 240, 80, 1.27, 25),
        "Generic ABS": _filament("Generic ABS", "ABS", 260, 100, 1.04, 22),
        "Generic ASA": _filament("Generic ASA", "ASA", 260, 100, 1.07, 26),
        "Generic TPU": _filament("Generic TPU", "TPU", 230, 50, 1.21, 35),
    },
}


# ── Preset discovery ─────────────────────────────────────────────


def default_search_dirs() -> List[str]:
    """Directories where plain-JSON OrcaSlicer presets may live (existing ones only)."""
    dirs: List[str] = []
    env = os.environ.get("ORCASLICER_PROFILES_DIR")
    if env:
        dirs += [p for p in env.split(os.pathsep) if p]
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support/OrcaSlicer")
        res = "/Applications/OrcaSlicer.app/Contents/Resources/profiles"
    elif sys.platform.startswith("win"):
        base = os.path.join(os.environ.get("APPDATA", ""), "OrcaSlicer")
        res = r"C:\Program Files\OrcaSlicer\resources\profiles"
    else:
        base = os.path.expanduser("~/.config/OrcaSlicer")
        res = "/usr/share/OrcaSlicer/profiles"
    dirs += [os.path.join(base, "system"), os.path.join(base, "user", "default"), res]
    # Bambu Studio (OrcaSlicer's upstream) ships/synchronises plain-JSON presets in the same format;
    # OrcaSlicer's own bundled profiles are an opaque .opc archive on some platforms.
    if sys.platform == "darwin":
        dirs += [os.path.expanduser("~/Library/Application Support/BambuStudio/system"),
                 "/Applications/BambuStudio.app/Contents/Resources/profiles"]
    elif sys.platform.startswith("win"):
        dirs += [os.path.join(os.environ.get("APPDATA", ""), "BambuStudio", "system"),
                 r"C:\Program Files\Bambu Studio\resources\profiles"]
    else:
        dirs += [os.path.expanduser("~/.config/BambuStudio/system")]
    return [d for d in dirs if os.path.isdir(d)]


def search_dirs(extra: Optional[List[str]] = None) -> List[str]:
    out: List[str] = []
    for d in list(extra or []) + default_search_dirs():
        d = os.path.abspath(os.path.expanduser(d))
        if d not in out and os.path.isdir(d):
            out.append(d)
    return out


_INDEX_CACHE: Dict[Tuple[str, ...], Dict[Tuple[str, str], List[str]]] = {}


def _build_index(dirs: List[str]) -> Dict[Tuple[str, str], List[str]]:
    key = tuple(dirs)
    if key in _INDEX_CACHE:
        return _INDEX_CACHE[key]
    index: Dict[Tuple[str, str], List[str]] = {}
    for root in dirs:
        for d, _, files in os.walk(root):
            for f in files:
                if not f.endswith(".json"):
                    continue
                path = os.path.join(d, f)
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        j = json.load(fh)
                except (OSError, ValueError):
                    continue
                if isinstance(j, dict) and j.get("type") in KINDS and "name" in j:
                    index.setdefault((j["type"], j["name"]), []).append(path)
    _INDEX_CACHE[key] = index
    return index


def _pick(paths: Optional[List[str]], near: Optional[str] = None) -> Optional[str]:
    """Choose among same-named presets. Vendors reuse parent names (e.g. 'fdm_machine_common'), so
    prefer the candidate that shares the longest directory prefix with the child that inherits it."""
    if not paths:
        return None
    if near and len(paths) > 1:
        near_dir = os.path.dirname(os.path.abspath(near))

        def shared(p: str) -> int:
            try:
                return len(os.path.commonpath([os.path.dirname(os.path.abspath(p)), near_dir]))
            except ValueError:
                return 0
        return max(paths, key=shared)
    return paths[0]


def clear_index_cache() -> None:
    _INDEX_CACHE.clear()


def list_presets(kind: Optional[str] = None, extra_dirs: Optional[List[str]] = None,
                 include_system: bool = True) -> List[Dict[str, str]]:
    kinds = [kind] if kind else list(KINDS)
    for k in kinds:
        _check_kind(k)
    out: List[Dict[str, str]] = []
    for k in kinds:
        for name in BUILTIN[k]:
            out.append({"kind": k, "name": name, "source": "builtin", "path": ""})
    if include_system:
        for (k, name), paths in sorted(_build_index(search_dirs(extra_dirs)).items()):
            if k in kinds and name not in BUILTIN[k]:
                out.append({"kind": k, "name": name, "source": "system", "path": paths[0]})
    return out


def _check_kind(kind: str) -> None:
    if kind not in KINDS:
        raise ValueError(f"Unknown preset kind '{kind}'. Use one of: {', '.join(KINDS)}.")


def _load_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        raise FileNotFoundError(f"Preset file not found: {path}")
    except ValueError as exc:
        raise ValueError(f"Preset file is not valid JSON: {path} ({exc})") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Preset file must contain a JSON object: {path}")
    return data


def _flatten(kind: str, data: Dict[str, Any], dirs: List[str], seen: Tuple[str, ...],
             origin: Optional[str] = None) -> Dict[str, Any]:
    parent_name = data.get("inherits")
    result: Dict[str, Any] = {}
    if parent_name:
        if parent_name in seen:
            raise ValueError(f"Circular 'inherits' chain: {' -> '.join(seen + (parent_name,))}")
        pname = parent_name
        if pname in BUILTIN[kind]:
            parent = copy.deepcopy(BUILTIN[kind][pname])
        else:
            path = _pick(_build_index(dirs).get((kind, pname)), origin)
            if path is None:
                raise ValueError(
                    f"Cannot resolve parent {kind} preset '{pname}' (inherits chain: "
                    f"{' -> '.join(seen) or data.get('name', '?')}).\n"
                    f"  Searched: {', '.join(dirs) or '(no preset directories found)'}\n"
                    "  Point the project at a directory containing OrcaSlicer's JSON presets with "
                    "--profiles-dir or the ORCASLICER_PROFILES_DIR environment variable.")
            parent = _load_json(path)
        result = _flatten(kind, parent, dirs, seen + (pname,), origin=path if pname not in BUILTIN[kind] else origin)
    result.update({k: v for k, v in data.items() if k != "inherits"})
    return result


def resolve(kind: str, ref: str, extra_dirs: Optional[List[str]] = None) -> Dict[str, Any]:
    """Resolve a preset reference into a flat preset dict.

    ``ref`` is a built-in name, a path to a preset JSON file, or the name of a preset found
    in the OrcaSlicer / user preset directories.
    """
    _check_kind(kind)
    dirs = search_dirs(extra_dirs)
    if ref in BUILTIN[kind]:
        return copy.deepcopy(BUILTIN[kind][ref])
    if ref.lower().endswith(".json") or os.path.sep in ref:
        path = os.path.abspath(os.path.expanduser(ref))
        data = _load_json(path)
        ptype = data.get("type")
        if ptype and ptype != kind:
            raise ValueError(f"Preset file {path} is a '{ptype}' preset, expected '{kind}'.")
        flat = _flatten(kind, data, dirs, (data.get("name", os.path.basename(path)),), origin=path)
        flat.setdefault("type", kind)
        flat.setdefault("name", os.path.splitext(os.path.basename(path))[0])
        return flat
    path = _pick(_build_index(dirs).get((kind, ref)))
    if path:
        data = _load_json(path)
        return _flatten(kind, data, dirs, (ref,), origin=path)
    known = ", ".join(BUILTIN[kind])
    raise ValueError(
        f"Unknown {kind} preset '{ref}'. Built-in: {known}. "
        f"Or give a path to a preset .json, or a preset name found in: "
        f"{', '.join(dirs) or '(no preset directories found)'}.")


def apply_overrides(kind: str, preset: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(preset)
    merged.update(copy.deepcopy(overrides))
    merged["type"] = kind
    merged["inherits"] = ""
    # OrcaSlicer rejects presets whose "from" is not system/User/user (CLI_CONFIG_FILE_ERROR),
    # and user-written presets frequently omit it.
    if merged.get("from") not in ("system", "User", "user"):
        merged["from"] = "User"
    merged.setdefault("name", f"cli-anything {kind}")
    if kind == "filament" and not merged.get("filament_diameter"):
        merged["filament_diameter"] = ["1.75"]
    return merged


# Renames OrcaSlicer applies when loading newer presets (PrintConfig.cpp handle_legacy). Vendor presets
# (e.g. Bambu Lab A1 mini) carry the NEW name while the installed 2.5.0 CLI validates the OLD one,
# so the stale parent value (0) would win and fail validation.
LEGACY_KEY_MIGRATIONS = {
    "extruder_clearance_max_radius": "extruder_clearance_radius",
}


def migrate_legacy_keys(preset: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """Rename keys the installed binary doesn't know to the name it does (schema-checked)."""
    out = dict(preset)
    for old, new in LEGACY_KEY_MIGRATIONS.items():
        if old in out and old not in schema and new in schema:
            out[new] = out.pop(old)
    return out


def materialize(kind: str, ref: str, overrides: Dict[str, Any], out_path: str,
                extra_dirs: Optional[List[str]] = None) -> Dict[str, Any]:
    """Write the final flat preset JSON (preset + overrides) to ``out_path``."""
    merged = apply_overrides(kind, resolve(kind, ref, extra_dirs), overrides)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2, ensure_ascii=False)
    return merged


def validate_ref(kind: str, ref: str, extra_dirs: Optional[List[str]] = None) -> Dict[str, Any]:
    """Resolve and return a summary (raises with a helpful message if invalid)."""
    flat = resolve(kind, ref, extra_dirs)
    return {"kind": kind, "ref": ref, "name": flat.get("name", ref), "keys": len(flat)}
