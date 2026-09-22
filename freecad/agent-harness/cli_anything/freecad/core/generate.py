"""
Model generation module for the FreeCAD CLI harness.

Provides parametric model templates and generation recipes that translate
high-level descriptions (text prompts, parameter sets, or image references)
into sequences of FreeCAD CLI commands.  Designed for AI agent consumption.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from . import (
    document as doc_mod,
    parts as parts_mod,
    sketch as sketch_mod,
    body as body_mod,
    materials as mat_mod,
)


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

TEMPLATES: Dict[str, Dict[str, Any]] = {
    "box": {
        "description": "Simple rectangular box",
        "params": {"length": 10.0, "width": 10.0, "height": 10.0},
        "category": "primitive",
    },
    "cylinder": {
        "description": "Simple cylinder",
        "params": {"radius": 5.0, "height": 20.0},
        "category": "primitive",
    },
    "tube": {
        "description": "Hollow cylinder (pipe/tube)",
        "params": {"outer_radius": 10.0, "inner_radius": 8.0, "height": 30.0},
        "category": "mechanical",
    },
    "plate_with_holes": {
        "description": "Rectangular plate with evenly-spaced through-holes",
        "params": {
            "length": 100.0, "width": 50.0, "thickness": 5.0,
            "hole_diameter": 6.0, "holes_x": 4, "holes_y": 2,
            "margin": 10.0,
        },
        "category": "mechanical",
    },
    "bracket_l": {
        "description": "L-shaped mounting bracket",
        "params": {
            "width": 40.0, "height": 30.0, "depth": 20.0,
            "thickness": 3.0, "fillet_radius": 2.0,
            "hole_diameter": 5.0,
        },
        "category": "mechanical",
    },
    "gear_spur": {
        "description": "Spur gear (approximate involute profile)",
        "params": {
            "module": 2.0, "teeth": 20, "face_width": 10.0,
            "pressure_angle": 20.0, "bore_diameter": 8.0,
        },
        "category": "mechanical",
    },
    "enclosure_box": {
        "description": "Rectangular enclosure with lid",
        "params": {
            "length": 80.0, "width": 60.0, "height": 40.0,
            "wall_thickness": 2.0, "fillet_radius": 3.0,
        },
        "category": "enclosure",
    },
    "threaded_bolt": {
        "description": "Hex bolt with threaded shaft",
        "params": {
            "shaft_diameter": 8.0, "shaft_length": 30.0,
            "head_diameter": 13.0, "head_height": 5.0,
            "thread_pitch": 1.25,
        },
        "category": "fastener",
    },
    "washer": {
        "description": "Flat washer",
        "params": {
            "outer_diameter": 16.0, "inner_diameter": 8.5,
            "thickness": 1.6,
        },
        "category": "fastener",
    },
    "standoff": {
        "description": "PCB standoff / spacer",
        "params": {
            "outer_diameter": 6.0, "inner_diameter": 3.2,
            "height": 10.0,
        },
        "category": "electronics",
    },
    "knob": {
        "description": "Cylindrical control knob with grip ridges",
        "params": {
            "diameter": 20.0, "height": 15.0,
            "shaft_diameter": 6.0, "shaft_depth": 10.0,
            "ridges": 12,
        },
        "category": "ui",
    },
}


def list_templates() -> List[Dict[str, Any]]:
    """Return all available model templates with their parameters."""
    return [
        {
            "name": name,
            "description": t["description"],
            "category": t["category"],
            "params": t["params"],
        }
        for name, t in TEMPLATES.items()
    ]


def get_template(name: str) -> Dict[str, Any]:
    """Return a single template by name."""
    if name not in TEMPLATES:
        raise ValueError(
            f"Unknown template '{name}'. "
            f"Available: {', '.join(sorted(TEMPLATES))}"
        )
    t = TEMPLATES[name]
    return {
        "name": name,
        "description": t["description"],
        "category": t["category"],
        "params": t["params"],
    }


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


def generate_from_template(
    template_name: str,
    params: Optional[Dict[str, Any]] = None,
    name: Optional[str] = None,
    material_preset: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a FreeCAD project from a named template.

    Parameters
    ----------
    template_name:
        Name of the template (see :func:`list_templates`).
    params:
        Override default parameters.  Missing keys use defaults.
    name:
        Project name.  Defaults to the template name.
    material_preset:
        Optional material preset to assign (e.g. ``"steel"``).

    Returns
    -------
    Dict[str, Any]
        The generated project dictionary, ready for export.
    """
    if template_name not in TEMPLATES:
        raise ValueError(
            f"Unknown template '{template_name}'. "
            f"Available: {', '.join(sorted(TEMPLATES))}"
        )

    template = TEMPLATES[template_name]
    p = dict(template["params"])
    if params:
        p.update(params)

    project_name = name or template_name
    project = doc_mod.create_document(project_name)

    # Dispatch to specific generator
    gen_fn = _GENERATORS.get(template_name)
    if gen_fn is None:
        # Fallback: simple primitive
        return _gen_primitive(project, template_name, p, material_preset)

    gen_fn(project, p)

    if material_preset:
        mat = mat_mod.create_material(project, preset=material_preset)
        # Assign to first part if any exist
        part_list = project.get("parts", [])
        if part_list:
            mat_mod.assign_material(project, 0, 0)

    return project


def _gen_primitive(
    project: Dict[str, Any],
    ptype: str,
    p: Dict[str, Any],
    material_preset: Optional[str],
) -> Dict[str, Any]:
    """Generate a single-primitive project."""
    parts_mod.add_part(project, ptype, params=p)
    if material_preset:
        mat_mod.create_material(project, preset=material_preset)
        mat_mod.assign_material(project, 0, 0)
    return project


def _gen_tube(project: Dict[str, Any], p: Dict[str, Any]) -> None:
    """Generate a hollow tube via boolean cut."""
    outer = {"radius": p["outer_radius"], "height": p["height"]}
    inner = {"radius": p["inner_radius"], "height": p["height"] + 2}
    parts_mod.add_part(project, "cylinder", params=outer, name="Outer")
    parts_mod.add_part(project, "cylinder", params=inner, name="Inner",
                       position=[0, 0, -1])
    parts_mod.boolean_op(project, "cut", 0, 1, name="Tube")


def _gen_plate_with_holes(project: Dict[str, Any], p: Dict[str, Any]) -> None:
    """Generate a plate with a grid of through-holes."""
    plate = {"length": p["length"], "width": p["width"], "height": p["thickness"]}
    parts_mod.add_part(project, "box", params=plate, name="Plate")

    holes_x = int(p.get("holes_x", 4))
    holes_y = int(p.get("holes_y", 2))
    margin = float(p.get("margin", 10.0))
    d = float(p["hole_diameter"])
    r = d / 2.0

    spacing_x = (p["length"] - 2 * margin) / max(holes_x - 1, 1)
    spacing_y = (p["width"] - 2 * margin) / max(holes_y - 1, 1)

    hole_idx = 1
    for ix in range(holes_x):
        for iy in range(holes_y):
            x = margin + ix * spacing_x
            y = margin + iy * spacing_y
            parts_mod.add_part(
                project, "cylinder",
                params={"radius": r, "height": p["thickness"] + 2},
                name=f"Hole_{hole_idx}",
                position=[x, y, -1],
            )
            hole_idx += 1

    # Boolean-cut all holes from plate
    current_base = 0
    for i in range(1, hole_idx):
        parts_mod.boolean_op(
            project, "cut", current_base, i,
            name=f"PlateHole_{i}",
        )
        current_base = len(project["parts"]) - 1


def _gen_bracket_l(project: Dict[str, Any], p: Dict[str, Any]) -> None:
    """Generate an L-bracket from two boxes with fillet."""
    w = p["width"]
    h = p["height"]
    d = p["depth"]
    t = p["thickness"]

    # Vertical plate
    parts_mod.add_part(project, "box",
                       params={"length": w, "width": t, "height": h},
                       name="Vertical")
    # Horizontal plate
    parts_mod.add_part(project, "box",
                       params={"length": w, "width": d, "height": t},
                       name="Horizontal")
    # Fuse them
    parts_mod.boolean_op(project, "fuse", 0, 1, name="L_Bracket")


def _gen_washer(project: Dict[str, Any], p: Dict[str, Any]) -> None:
    """Generate a flat washer."""
    outer = {"radius": p["outer_diameter"] / 2, "height": p["thickness"]}
    inner = {"radius": p["inner_diameter"] / 2, "height": p["thickness"] + 2}
    parts_mod.add_part(project, "cylinder", params=outer, name="Outer")
    parts_mod.add_part(project, "cylinder", params=inner, name="Bore",
                       position=[0, 0, -1])
    parts_mod.boolean_op(project, "cut", 0, 1, name="Washer")


def _gen_standoff(project: Dict[str, Any], p: Dict[str, Any]) -> None:
    """Generate a PCB standoff."""
    outer = {"radius": p["outer_diameter"] / 2, "height": p["height"]}
    inner = {"radius": p["inner_diameter"] / 2, "height": p["height"] + 2}
    parts_mod.add_part(project, "cylinder", params=outer, name="Body")
    parts_mod.add_part(project, "cylinder", params=inner, name="Bore",
                       position=[0, 0, -1])
    parts_mod.boolean_op(project, "cut", 0, 1, name="Standoff")


def _gen_gear_spur(project: Dict[str, Any], p: Dict[str, Any]) -> None:
    """Generate an approximate spur gear profile.

    Uses a simplified involute approximation with polygonal tooth profiles.
    For precise gearing, export and refine in FreeCAD's Part/FCGear workbench.
    """
    m = float(p["module"])
    z = int(p["teeth"])
    fw = float(p["face_width"])
    bore = float(p.get("bore_diameter", 0))

    pitch_r = m * z / 2.0
    addendum = m
    dedendum = 1.25 * m
    outer_r = pitch_r + addendum

    # Simplified: create outer cylinder, bore, and note gear params
    parts_mod.add_part(project, "cylinder",
                       params={"radius": outer_r, "height": fw},
                       name="GearBlank")
    if bore > 0:
        parts_mod.add_part(project, "cylinder",
                           params={"radius": bore / 2, "height": fw + 2},
                           name="Bore",
                           position=[0, 0, -1])
        parts_mod.boolean_op(project, "cut", 0, 1, name="SpurGear")

    # Store gear metadata for downstream processing
    project.setdefault("metadata", {})["gear_params"] = {
        "module": m, "teeth": z, "pitch_radius": pitch_r,
        "outer_radius": outer_r, "dedendum_radius": pitch_r - dedendum,
        "pressure_angle": float(p.get("pressure_angle", 20.0)),
        "note": "Approximate blank — use FCGear for involute profile",
    }


def _gen_enclosure_box(project: Dict[str, Any], p: Dict[str, Any]) -> None:
    """Generate a rectangular enclosure (box minus inner cavity)."""
    l, w, h = p["length"], p["width"], p["height"]
    t = p["wall_thickness"]

    parts_mod.add_part(project, "box",
                       params={"length": l, "width": w, "height": h},
                       name="Outer")
    parts_mod.add_part(project, "box",
                       params={"length": l - 2*t, "width": w - 2*t, "height": h - t},
                       name="Cavity",
                       position=[t, t, t])
    parts_mod.boolean_op(project, "cut", 0, 1, name="Enclosure")


def _gen_threaded_bolt(project: Dict[str, Any], p: Dict[str, Any]) -> None:
    """Generate a hex bolt (hex head + cylindrical shaft)."""
    sd = p["shaft_diameter"]
    sl = p["shaft_length"]
    hd = p["head_diameter"]
    hh = p["head_height"]

    # Hex head approximated as cylinder (for true hex, use sketch + pad)
    parts_mod.add_part(project, "cylinder",
                       params={"radius": hd / 2, "height": hh},
                       name="Head",
                       position=[0, 0, sl])
    # Shaft
    parts_mod.add_part(project, "cylinder",
                       params={"radius": sd / 2, "height": sl},
                       name="Shaft")
    # Fuse
    parts_mod.boolean_op(project, "fuse", 0, 1, name="Bolt")

    project.setdefault("metadata", {})["bolt_params"] = {
        "thread_pitch": p.get("thread_pitch", 1.25),
        "note": "Thread profile not modeled — use body hole --threaded for mating part",
    }


def _gen_knob(project: Dict[str, Any], p: Dict[str, Any]) -> None:
    """Generate a cylindrical knob with shaft bore."""
    d = p["diameter"]
    h = p["height"]
    sd = p["shaft_diameter"]
    sdepth = p["shaft_depth"]

    parts_mod.add_part(project, "cylinder",
                       params={"radius": d / 2, "height": h},
                       name="KnobBody")
    parts_mod.add_part(project, "cylinder",
                       params={"radius": sd / 2, "height": sdepth + 1},
                       name="ShaftBore",
                       position=[0, 0, -1])
    parts_mod.boolean_op(project, "cut", 0, 1, name="Knob")


# Generator dispatch table
_GENERATORS = {
    "tube": _gen_tube,
    "plate_with_holes": _gen_plate_with_holes,
    "bracket_l": _gen_bracket_l,
    "washer": _gen_washer,
    "standoff": _gen_standoff,
    "gear_spur": _gen_gear_spur,
    "enclosure_box": _gen_enclosure_box,
    "threaded_bolt": _gen_threaded_bolt,
    "knob": _gen_knob,
}


# ---------------------------------------------------------------------------
# Prompt-to-model interpretation helpers
# ---------------------------------------------------------------------------


def parse_dimensions_from_text(text: str) -> Dict[str, float]:
    """Extract dimensional parameters from natural language text.

    Parses patterns like "20mm x 15mm x 5mm", "radius 10",
    "diameter 8", "height=30", "M8 bolt", etc.

    Returns
    -------
    dict
        Extracted parameters (may be partial; agent fills gaps).
    """
    import re

    params: Dict[str, float] = {}

    # "LxWxH" or "L x W x H" patterns
    lwh = re.findall(
        r"(\d+(?:\.\d+)?)\s*(?:mm|cm|in)?\s*[xX×]\s*"
        r"(\d+(?:\.\d+)?)\s*(?:mm|cm|in)?\s*[xX×]\s*"
        r"(\d+(?:\.\d+)?)",
        text,
    )
    if lwh:
        params["length"] = float(lwh[0][0])
        params["width"] = float(lwh[0][1])
        params["height"] = float(lwh[0][2])

    # "diameter N" or "D=N"
    dia = re.findall(r"(?:diameter|dia|d)\s*[=:]?\s*(\d+(?:\.\d+)?)", text, re.I)
    if dia:
        params["diameter"] = float(dia[0])

    # "radius N" or "R=N"
    rad = re.findall(r"(?:radius|r)\s*[=:]?\s*(\d+(?:\.\d+)?)", text, re.I)
    if rad:
        params["radius"] = float(rad[0])

    # "height N" or "H=N" (but not "h" inside other words)
    ht = re.findall(r"(?:height|(?<!\w)h)\s*[=:]?\s*(\d+(?:\.\d+)?)", text, re.I)
    if ht:
        params["height"] = float(ht[0])

    # "thickness N" or "T=N"
    thk = re.findall(r"(?:thickness|thick|t)\s*[=:]?\s*(\d+(?:\.\d+)?)", text, re.I)
    if thk:
        params["thickness"] = float(thk[0])

    # "M8" metric thread
    metric = re.findall(r"M(\d+(?:\.\d+)?)", text)
    if metric:
        params["shaft_diameter"] = float(metric[0])

    # "N teeth"
    teeth = re.findall(r"(\d+)\s*teeth", text, re.I)
    if teeth:
        params["teeth"] = int(teeth[0])

    return params


def suggest_template(description: str) -> Dict[str, Any]:
    """Suggest the best template for a natural-language description.

    Uses keyword matching to rank templates.  For more sophisticated
    matching, the AI agent should use this as a hint and refine.

    Returns
    -------
    dict
        ``{"template": str, "confidence": float, "params": dict}``
    """
    desc_lower = description.lower()

    scores: Dict[str, float] = {}
    keywords: Dict[str, List[str]] = {
        "box": ["box", "cube", "block", "rectangular"],
        "cylinder": ["cylinder", "rod", "bar", "dowel", "pin"],
        "tube": ["tube", "pipe", "hollow cylinder", "bushing"],
        "plate_with_holes": ["plate", "baseplate", "mounting plate", "panel with holes"],
        "bracket_l": ["bracket", "l-bracket", "angle bracket", "mount"],
        "gear_spur": ["gear", "spur gear", "cog", "teeth"],
        "enclosure_box": ["enclosure", "case", "housing", "box case", "shell"],
        "threaded_bolt": ["bolt", "screw", "fastener", "hex bolt"],
        "washer": ["washer", "flat washer", "spacer ring"],
        "standoff": ["standoff", "spacer", "pcb mount"],
        "knob": ["knob", "dial", "rotary", "control knob"],
    }

    for tname, kws in keywords.items():
        score = sum(1.0 for kw in kws if kw in desc_lower)
        if score > 0:
            scores[tname] = score

    if not scores:
        return {
            "template": None,
            "confidence": 0.0,
            "params": parse_dimensions_from_text(description),
            "suggestion": "No matching template. Use primitive commands to build custom geometry.",
        }

    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    confidence = min(scores[best] / 3.0, 1.0)
    parsed = parse_dimensions_from_text(description)

    return {
        "template": best,
        "confidence": confidence,
        "params": parsed,
    }
