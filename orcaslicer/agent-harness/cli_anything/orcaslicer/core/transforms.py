"""OrcaSlicer CLI - ordered model transforms.

OrcaSlicer applies CLI transforms to *all* loaded objects, in command-line order
(e.g. ``--rotate-x 90 --ground-largest-face`` sees the rotation). The project therefore
stores an ordered list and emits flags in that order.
"""

from __future__ import annotations

import re
import os
from typing import Any, Dict, List, Sequence

_VEC3 = re.compile(r"^\s*-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?\s*$")

# op -> (cli flag, value kind)  kind: float | pos_float | int01 | posint | flag | vec3
OPS: Dict[str, tuple] = {
    "scale": ("--scale", "pos_float"),
    "rotate": ("--rotate", "float"),          # around Z, degrees
    "rotate_x": ("--rotate-x", "float"),
    "rotate_y": ("--rotate-y", "float"),
    "orient": ("--orient", "int01"),
    "arrange": ("--arrange", "int01"),
    "repetitions": ("--repetitions", "posint"),
    "ensure_on_bed": ("--ensure-on-bed", "flag"),
    "ground_largest_face": ("--ground-largest-face", "flag"),
    "ground_face_normal": ("--ground-face-normal", "vec3"),
    "ground_face_point": ("--ground-face-point", "vec3"),
    "repair": ("--repair", "flag"),
    "convert_unit": ("--convert-unit", "flag"),
}


def _coerce(op: str, value: Any) -> Any:
    flag, kind = OPS[op]
    if kind == "flag":
        return True
    if value is None:
        raise ValueError(f"Transform '{op}' needs a value.")
    if kind in ("float", "pos_float"):
        try:
            v = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Transform '{op}' needs a number, got {value!r}.")
        if kind == "pos_float" and v <= 0:
            raise ValueError(f"Transform '{op}' must be > 0, got {v:g}.")
        return v
    if kind == "int01":
        try:
            v = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"Transform '{op}' needs 0 or 1, got {value!r}.")
        if v not in (0, 1):
            raise ValueError(f"Transform '{op}' must be 0 or 1, got {v}.")
        return v
    if kind == "posint":
        try:
            v = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"Transform '{op}' needs an integer, got {value!r}.")
        if v < 1:
            raise ValueError(f"Transform '{op}' must be >= 1, got {v}.")
        return v
    if kind == "vec3":
        if not _VEC3.match(str(value)):
            raise ValueError(f"Transform '{op}' needs 'X,Y,Z' numbers, got {value!r}.")
        return ",".join(p.strip() for p in str(value).split(","))
    raise AssertionError(kind)  # pragma: no cover


def add_transform(project: Dict[str, Any], op: str, value: Any = None) -> Dict[str, Any]:
    if op not in OPS:
        raise ValueError(f"Unknown transform '{op}'. Valid: {', '.join(OPS)}.")
    entry = {"op": op, "value": _coerce(op, value)}
    flag_kind = OPS[op][1] == "flag"
    # Flag ops are idempotent; repeating them adds nothing.
    if flag_kind and entry in project["transforms"]:
        return entry
    project["transforms"].append(entry)
    return entry


def clear_transforms(project: Dict[str, Any]) -> int:
    n = len(project["transforms"])
    project["transforms"] = []
    return n


def copies_count(transforms: List[Dict[str, Any]]) -> int:
    """Number of copies requested by the (last) 'repetitions' transform; 1 if none."""
    n = 1
    for t in transforms:
        if t["op"] == "repetitions":
            n = int(t["value"])
    return n


def _model_exts(models: Sequence[Dict[str, Any]]) -> set:
    return {os.path.splitext(m["path"])[1].lower() for m in models}


def repetitions_need_plate(transforms: List[Dict[str, Any]], models: Sequence[Dict[str, Any]]) -> bool:
    """OrcaSlicer's native --repetitions (used for 3MF inputs) refuses ``--slice 0``."""
    return copies_count(transforms) > 1 and bool(models) and _model_exts(models) == {".3mf"}


def build_args(transforms: List[Dict[str, Any]], models: Sequence[Dict[str, Any]] = ()) -> List[str]:
    """Emit transform flags in order.

    ``repetitions`` is implemented with ``--clone-objects N,N,...`` for mesh inputs: OrcaSlicer's own
    ``--repetitions`` fails with CLI_INVALID_PARAMS on STL/OBJ/STEP input (no plate exists yet).
    For 3MF-only projects the native ``--repetitions`` is used (together with ``--slice 1``).
    """
    args: List[str] = []
    for t in transforms:
        if t["op"] == "repetitions":
            continue
        flag, kind = OPS[t["op"]]
        args.append(flag)
        if kind != "flag":
            v = t["value"]
            args.append(f"{v:g}" if isinstance(v, float) else str(v))
    n = copies_count(transforms)
    if n > 1:
        if not models:
            raise ValueError("Copies (repetitions) need at least one model.")
        exts = _model_exts(models)
        if exts == {".3mf"}:
            args += ["--repetitions", str(n)]
        elif ".3mf" in exts:
            raise ValueError("Copies cannot be combined with a mix of .3mf and mesh models; "
                             "use only .3mf or only STL/OBJ/STEP/AMF models.")
        else:
            args += ["--clone-objects", ",".join([str(n)] * len(models))]
    return args
