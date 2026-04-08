"""
Pipeline diff -- compare two pipeline snapshots and output only differences.

Usage:
    from core.diff import diff_pipeline
    result = diff_pipeline(controller_a, event_a, controller_b, event_b)

The result dict only contains sections that have at least one difference.
Sections that are completely identical are either omitted or marked "SAME".

The snapshot format matches the output of ``dump_pipeline_for_diff``:

    {
      "eventId": ...,
      "PipelineState": {
        "pipelineType": ...,
        "vertexInputs": [...],
        "outputTargets": [...],
        "depthTarget": {...},
        "viewport": {...},
        "rasterizer": {...},
        "blend": {...},
        "depthStencil": {...},
        "stages": {
          "Vertex": {
            "shader": "ResourceId::...",
            "entryPoint": "...",
            "ShaderReflection": { ... },
            "bindings": {
              "constantBlocks": [ { ..., "variables": [...] } ],
              "readOnlyResources": [...],
              "readWriteResources": [...],
              "samplers": [...]
            }
          },
          ...
        }
      }
    }
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from cli_anything.renderdoc.core.pipeline import dump_pipeline_for_diff


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FLOAT_TOL = 1e-6


def _floats_equal(a, b) -> bool:
    """Compare two floats with tolerance; handle NaN/Inf."""
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        if math.isinf(a) and math.isinf(b):
            return a == b
        return abs(a - b) <= _FLOAT_TOL
    return a == b


def _values_equal(a, b) -> bool:
    """Deep equality check for plain JSON-like values."""
    if type(a) != type(b):
        return False
    if isinstance(a, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(_values_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        if len(a) != len(b):
            return False
        return all(_values_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, float):
        return _floats_equal(a, b)
    return a == b


def _diff_dicts(
    a: Optional[Dict], b: Optional[Dict], label: str = "",
) -> Optional[Dict[str, Any]]:
    """Compare two flat/nested dicts, return only differing keys.

    Returns None if both are equal (or both None).
    """
    if a is None and b is None:
        return None
    if a is None or b is None:
        return {"A": a, "B": b}

    diffs: Dict[str, Any] = {}
    all_keys = sorted(set(list(a.keys()) + list(b.keys())))
    for k in all_keys:
        va = a.get(k)
        vb = b.get(k)
        if not _values_equal(va, vb):
            diffs[k] = {"A": va, "B": vb}

    return diffs if diffs else None


def _diff_lists(
    a: Optional[List], b: Optional[List], key_field: str = "name",
) -> Optional[List[Dict[str, Any]]]:
    """Compare two lists of dicts by a key field, return only diffs.

    Items present in A but not B get status "only_in_A", vice versa.
    Items present in both get per-field diff.
    Returns None if identical.
    """
    if a is None and b is None:
        return None
    a = a or []
    b = b or []

    a_map = {str(item.get(key_field, i)): item for i, item in enumerate(a)}
    b_map = {str(item.get(key_field, i)): item for i, item in enumerate(b)}
    all_keys = sorted(set(list(a_map.keys()) + list(b_map.keys())))

    diffs = []
    for k in all_keys:
        va = a_map.get(k)
        vb = b_map.get(k)
        if va is None:
            diffs.append({"key": k, "status": "only_in_B", "B": vb})
        elif vb is None:
            diffs.append({"key": k, "status": "only_in_A", "A": va})
        else:
            d = _diff_dicts(va, vb)
            if d:
                diffs.append({"key": k, "status": "changed", "fields": d})

    return diffs if diffs else None


# ---------------------------------------------------------------------------
# CBuffer variable diff (recursive, handles struct members)
# ---------------------------------------------------------------------------

def _diff_cbuffer_vars(
    vars_a: List[Dict], vars_b: List[Dict],
) -> Optional[List[Dict]]:
    """Compare two lists of cbuffer variables; return only diffs."""
    a_map = {v["name"]: v for v in vars_a}
    b_map = {v["name"]: v for v in vars_b}
    all_names = sorted(set(list(a_map.keys()) + list(b_map.keys())))

    diffs = []
    for name in all_names:
        va = a_map.get(name)
        vb = b_map.get(name)
        if va is None:
            diffs.append({"name": name, "status": "only_in_B", "B": vb})
        elif vb is None:
            diffs.append({"name": name, "status": "only_in_A", "A": va})
        else:
            if "members" in va or "members" in vb:
                sub = _diff_cbuffer_vars(
                    va.get("members", []),
                    vb.get("members", []),
                )
                if sub:
                    diffs.append({"name": name, "status": "changed", "members": sub})
            else:
                vals_a = va.get("values", [])
                vals_b = vb.get("values", [])
                if not _values_equal(vals_a, vals_b):
                    diffs.append({
                        "name": name,
                        "status": "changed",
                        "A": vals_a,
                        "B": vals_b,
                    })

    return diffs if diffs else None


# ---------------------------------------------------------------------------
# Stage-level diff (new structure)
# ---------------------------------------------------------------------------

def _diff_bindings(bindings_a: Dict, bindings_b: Dict) -> Optional[Dict[str, Any]]:
    """Diff the bindings sub-dict of a stage.

    Handles: constantBlocks (with nested variable values),
    readOnlyResources, readWriteResources, samplers.
    """
    result: Dict[str, Any] = {}
    has_diff = False

    # --- constantBlocks ---
    cbs_a = bindings_a.get("constantBlocks", [])
    cbs_b = bindings_b.get("constantBlocks", [])

    # Build maps keyed by index
    a_map = {cb.get("index", i): cb for i, cb in enumerate(cbs_a)}
    b_map = {cb.get("index", i): cb for i, cb in enumerate(cbs_b)}
    all_indices = sorted(set(list(a_map.keys()) + list(b_map.keys())))

    cb_diffs = []
    var_diffs_all = []
    for idx in all_indices:
        ca = a_map.get(idx)
        cb_ = b_map.get(idx)
        if ca is None:
            cb_diffs.append({"index": idx, "status": "only_in_B", "B": cb_})
        elif cb_ is None:
            cb_diffs.append({"index": idx, "status": "only_in_A", "A": ca})
        else:
            # Compare binding metadata (resource, byteOffset, byteSize)
            ca_meta = {k: v for k, v in ca.items() if k not in ("variables",)}
            cb_meta = {k: v for k, v in cb_.items() if k not in ("variables",)}
            meta_diff = _diff_dicts(ca_meta, cb_meta)
            if meta_diff:
                cb_diffs.append({"index": idx, "status": "changed", "fields": meta_diff})

            # Compare runtime variable values
            va_vars = ca.get("variables", [])
            vb_vars = cb_.get("variables", [])
            vdiff = _diff_cbuffer_vars(va_vars, vb_vars)
            if vdiff:
                var_diffs_all.append({"index": idx, "variables": vdiff})

    cb_result: Dict[str, Any] = {}
    if cb_diffs:
        cb_result["metadata"] = cb_diffs
    if var_diffs_all:
        cb_result["variables"] = var_diffs_all

    if cb_result:
        result["constantBlocks"] = cb_result
        has_diff = True
    else:
        result["constantBlocks"] = "SAME"

    # --- readOnlyResources, readWriteResources, samplers ---
    for section in ("readOnlyResources", "readWriteResources", "samplers"):
        d = _diff_lists(
            bindings_a.get(section, []),
            bindings_b.get(section, []),
            key_field="index",
        )
        if d:
            result[section] = d
            has_diff = True
        else:
            result[section] = "SAME"

    return result if has_diff else None


def _diff_stages(stages_a: Dict, stages_b: Dict) -> Optional[Dict[str, Any]]:
    """Diff the stages sub-dict of PipelineState.

    For each stage present in either snapshot, compare:
    - shader / entryPoint (as a dict)
    - ShaderReflection (deep dict diff)
    - bindings (structured diff with variable values)
    """
    all_names = sorted(set(list(stages_a.keys()) + list(stages_b.keys())))
    result: Dict[str, Any] = {}
    has_diff = False

    for name in all_names:
        sa = stages_a.get(name)
        sb = stages_b.get(name)

        if sa is None:
            result[name] = {"status": "only_in_B", "B": sb}
            has_diff = True
            continue
        if sb is None:
            result[name] = {"status": "only_in_A", "A": sa}
            has_diff = True
            continue

        stage_result: Dict[str, Any] = {}
        stage_has_diff = False

        # shader + entryPoint
        shader_dict_a = {"shader": sa.get("shader"), "entryPoint": sa.get("entryPoint")}
        shader_dict_b = {"shader": sb.get("shader"), "entryPoint": sb.get("entryPoint")}
        shader_diff = _diff_dicts(shader_dict_a, shader_dict_b)
        if shader_diff:
            stage_result["shader"] = shader_diff
            stage_has_diff = True
        else:
            stage_result["shader"] = "SAME"

        # ShaderReflection
        refl_diff = _diff_dicts(
            sa.get("ShaderReflection"),
            sb.get("ShaderReflection"),
        )
        if refl_diff:
            stage_result["ShaderReflection"] = refl_diff
            stage_has_diff = True
        else:
            stage_result["ShaderReflection"] = "SAME"

        # bindings
        bindings_diff = _diff_bindings(
            sa.get("bindings", {}),
            sb.get("bindings", {}),
        )
        if bindings_diff:
            stage_result["bindings"] = bindings_diff
            stage_has_diff = True
        else:
            stage_result["bindings"] = "SAME"

        if stage_has_diff:
            result[name] = stage_result
            has_diff = True
        else:
            result[name] = "SAME"

    return result if has_diff else None


# ---------------------------------------------------------------------------
# Core diff from two snapshot dicts
# ---------------------------------------------------------------------------

def _diff_from_snapshots(snap_a: Dict[str, Any], snap_b: Dict[str, Any]) -> Dict[str, Any]:
    """Shared implementation: diff two dump_pipeline_for_diff snapshots."""
    ps_a = snap_a.get("PipelineState", {})
    ps_b = snap_b.get("PipelineState", {})

    result: Dict[str, Any] = {
        "eventA": snap_a.get("eventId"),
        "eventB": snap_b.get("eventId"),
    }

    has_diff = False

    # pipelineType
    pt_a = ps_a.get("pipelineType")
    pt_b = ps_b.get("pipelineType")
    if pt_a != pt_b:
        result["pipelineType"] = {"A": pt_a, "B": pt_b}
        has_diff = True
    else:
        result["pipelineType"] = pt_a

    # Simple sections: vertexInputs, outputTargets, depthTarget, viewport,
    # rasterizer, depthStencil
    for section, key_field in [
        ("vertexInputs", "name"),
        ("outputTargets", "index"),
    ]:
        d = _diff_lists(
            ps_a.get(section, []),
            ps_b.get(section, []),
            key_field=key_field,
        )
        if d:
            result[section] = d
            has_diff = True
        else:
            result[section] = "SAME"

    for section in ("depthTarget", "viewport", "rasterizer", "depthStencil"):
        d = _diff_dicts(ps_a.get(section), ps_b.get(section))
        if d:
            result[section] = d
            has_diff = True
        else:
            result[section] = "SAME"

    # blend — nested: top-level dict keys + blends list
    blend_a = ps_a.get("blend")
    blend_b = ps_b.get("blend")
    if blend_a is None and blend_b is None:
        result["blend"] = "SAME"
    elif blend_a is None or blend_b is None:
        result["blend"] = {"A": blend_a, "B": blend_b}
        has_diff = True
    else:
        blend_diff: Dict[str, Any] = {}
        blend_has_diff = False
        # Top-level scalar keys
        for k in sorted(set(list(blend_a.keys()) + list(blend_b.keys()))):
            if k == "blends":
                continue
            va = blend_a.get(k)
            vb = blend_b.get(k)
            if not _values_equal(va, vb):
                blend_diff[k] = {"A": va, "B": vb}
                blend_has_diff = True
        # blends list
        blends_diff = _diff_lists(
            blend_a.get("blends", []),
            blend_b.get("blends", []),
            key_field="index",
        )
        if blends_diff:
            blend_diff["blends"] = blends_diff
            blend_has_diff = True
        if blend_has_diff:
            result["blend"] = blend_diff
            has_diff = True
        else:
            result["blend"] = "SAME"

    # stages
    stages_diff = _diff_stages(
        ps_a.get("stages", {}),
        ps_b.get("stages", {}),
    )
    if stages_diff:
        result["stages"] = stages_diff
        has_diff = True
    else:
        result["stages"] = "SAME"

    result["identical"] = not has_diff
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def diff_pipeline(
    controller_a,
    event_a: int,
    controller_b,
    event_b: int,
) -> Dict[str, Any]:
    """Compare full pipeline state at two events (possibly from different captures).

    Returns a dict containing only the dimensions that differ.
    Each section is either omitted (identical) or marked "SAME".
    """
    snap_a = dump_pipeline_for_diff(controller_a, event_a)
    snap_b = dump_pipeline_for_diff(controller_b, event_b)
    return _diff_from_snapshots(snap_a, snap_b)


def diff_pipeline_from_snapshots(
    snap_a: Dict[str, Any],
    snap_b: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare two pre-built pipeline snapshots (for testing or offline use).

    Expects snapshots in the ``dump_pipeline_for_diff`` format::

        {"eventId": ..., "PipelineState": { ... }}

    Same logic as diff_pipeline but without needing live controllers.
    """
    return _diff_from_snapshots(snap_a, snap_b)
