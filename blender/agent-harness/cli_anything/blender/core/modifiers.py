"""Blender CLI - Modifier registry and management module."""

from typing import Dict, Any, List, Optional


# Modifier registry: maps modifier type -> specification
MODIFIER_REGISTRY = {
    "subdivision_surface": {
        "category": "generate",
        "description": "Subdivide mesh for smoother appearance",
        "bpy_type": "SUBSURF",
        "params": {
            "levels": {"type": "int", "default": 1, "min": 0, "max": 6,
                       "description": "Subdivision levels for viewport"},
            "render_levels": {"type": "int", "default": 2, "min": 0, "max": 6,
                              "description": "Subdivision levels for render"},
            "use_creases": {"type": "bool", "default": False,
                            "description": "Use edge crease weights"},
        },
    },
    "mirror": {
        "category": "generate",
        "description": "Mirror mesh across an axis",
        "bpy_type": "MIRROR",
        "params": {
            "use_axis_x": {"type": "bool", "default": True, "description": "Mirror on X axis"},
            "use_axis_y": {"type": "bool", "default": False, "description": "Mirror on Y axis"},
            "use_axis_z": {"type": "bool", "default": False, "description": "Mirror on Z axis"},
            "use_clip": {"type": "bool", "default": True, "description": "Prevent vertices from crossing the mirror plane"},
            "merge_threshold": {"type": "float", "default": 0.001, "min": 0.0, "max": 1.0,
                                "description": "Distance within which mirrored vertices are merged"},
        },
    },
    "array": {
        "category": "generate",
        "description": "Create array of object copies",
        "bpy_type": "ARRAY",
        "params": {
            "count": {"type": "int", "default": 2, "min": 1, "max": 1000,
                      "description": "Number of array copies"},
            "relative_offset_x": {"type": "float", "default": 1.0, "min": -100.0, "max": 100.0,
                                  "description": "Relative offset on X axis"},
            "relative_offset_y": {"type": "float", "default": 0.0, "min": -100.0, "max": 100.0,
                                  "description": "Relative offset on Y axis"},
            "relative_offset_z": {"type": "float", "default": 0.0, "min": -100.0, "max": 100.0,
                                  "description": "Relative offset on Z axis"},
        },
    },
    "bevel": {
        "category": "generate",
        "description": "Bevel edges of mesh",
        "bpy_type": "BEVEL",
        "params": {
            "width": {"type": "float", "default": 0.1, "min": 0.0, "max": 100.0,
                      "description": "Bevel width"},
            "segments": {"type": "int", "default": 1, "min": 1, "max": 100,
                         "description": "Number of bevel segments"},
            "limit_method": {"type": "str", "default": "NONE",
                             "description": "Limit method: NONE, ANGLE, WEIGHT, VGROUP"},
            "angle_limit": {"type": "float", "default": 0.523599, "min": 0.0, "max": 3.14159,
                            "description": "Angle limit in radians (for ANGLE method)"},
        },
    },
    "solidify": {
        "category": "generate",
        "description": "Add thickness to mesh surface",
        "bpy_type": "SOLIDIFY",
        "params": {
            "thickness": {"type": "float", "default": 0.01, "min": -10.0, "max": 10.0,
                          "description": "Thickness of solidified surface"},
            "offset": {"type": "float", "default": -1.0, "min": -1.0, "max": 1.0,
                       "description": "Offset direction (-1=outward, 1=inward)"},
            "use_even_offset": {"type": "bool", "default": False,
                                "description": "Maintain even thickness"},
        },
    },
    "decimate": {
        "category": "generate",
        "description": "Reduce polygon count",
        "bpy_type": "DECIMATE",
        "params": {
            "ratio": {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0,
                      "description": "Ratio of faces to keep"},
            "decimate_type": {"type": "str", "default": "COLLAPSE",
                              "description": "Method: COLLAPSE, UNSUBDIV, DISSOLVE"},
        },
    },
    "boolean": {
        "category": "generate",
        "description": "Boolean operation with another object",
        "bpy_type": "BOOLEAN",
        "params": {
            "operation": {"type": "str", "default": "DIFFERENCE",
                          "description": "Operation: DIFFERENCE, UNION, INTERSECT"},
            "operand_object": {"type": "str", "default": "",
                               "description": "Name of the operand object"},
            "solver": {"type": "str", "default": "EXACT",
                       "description": "Solver: EXACT, FAST"},
        },
    },
    "smooth": {
        "category": "deform",
        "description": "Smooth mesh vertices",
        "bpy_type": "SMOOTH",
        "params": {
            "factor": {"type": "float", "default": 0.5, "min": -10.0, "max": 10.0,
                       "description": "Smoothing factor"},
            "iterations": {"type": "int", "default": 1, "min": 0, "max": 1000,
                           "description": "Number of smoothing iterations"},
            "use_x": {"type": "bool", "default": True, "description": "Smooth on X axis"},
            "use_y": {"type": "bool", "default": True, "description": "Smooth on Y axis"},
            "use_z": {"type": "bool", "default": True, "description": "Smooth on Z axis"},
        },
    },
}


def list_available(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """List available modifiers, optionally filtered by category."""
    result = []
    for name, info in MODIFIER_REGISTRY.items():
        if category and info["category"] != category:
            continue
        result.append({
            "name": name,
            "category": info["category"],
            "description": info["description"],
            "bpy_type": info["bpy_type"],
            "param_count": len(info["params"]),
        })
    return result


def get_modifier_info(name: str) -> Dict[str, Any]:
    """Get detailed info about a modifier type."""
    if name not in MODIFIER_REGISTRY:
        raise ValueError(
            f"Unknown modifier: {name}. Use 'modifier list-available' to see options."
        )
    info = MODIFIER_REGISTRY[name]
    return {
        "name": name,
        "category": info["category"],
        "description": info["description"],
        "bpy_type": info["bpy_type"],
        "params": info["params"],
    }


def validate_params(name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and fill defaults for modifier parameters."""
    if name not in MODIFIER_REGISTRY:
        raise ValueError(f"Unknown modifier: {name}")

    spec = MODIFIER_REGISTRY[name]["params"]
    result = {}

    for pname, pspec in spec.items():
        if pname in params:
            val = params[pname]
            ptype = pspec["type"]
            if ptype == "float":
                val = float(val)
                if "min" in pspec and val < pspec["min"]:
                    raise ValueError(f"Parameter '{pname}' minimum is {pspec['min']}, got {val}")
                if "max" in pspec and val > pspec["max"]:
                    raise ValueError(f"Parameter '{pname}' maximum is {pspec['max']}, got {val}")
            elif ptype == "int":
                val = int(val)
                if "min" in pspec and val < pspec["min"]:
                    raise ValueError(f"Parameter '{pname}' minimum is {pspec['min']}, got {val}")
                if "max" in pspec and val > pspec["max"]:
                    raise ValueError(f"Parameter '{pname}' maximum is {pspec['max']}, got {val}")
            elif ptype == "bool":
                val = str(val).lower() in ("true", "1", "yes")
            elif ptype == "str":
                val = str(val)
            result[pname] = val
        else:
            result[pname] = pspec.get("default")

    # Warn about unknown params
    unknown = set(params.keys()) - set(spec.keys())
    if unknown:
        raise ValueError(f"Unknown parameters for modifier '{name}': {unknown}")

    return result


def add_modifier(
    project: Dict[str, Any],
    modifier_type: str,
    object_index: int = 0,
    name: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Add a modifier to an object.

    Args:
        project: The scene dict
        modifier_type: Modifier type name (e.g., "subdivision_surface")
        object_index: Index of the target object
        name: Custom modifier name (auto-generated if None)
        params: Override modifier parameters

    Returns:
        The new modifier entry dict
    """
    objects = project.get("objects", [])
    if object_index < 0 or object_index >= len(objects):
        raise IndexError(f"Object index {object_index} out of range (0-{len(objects)-1})")

    if modifier_type not in MODIFIER_REGISTRY:
        raise ValueError(f"Unknown modifier: {modifier_type}")

    validated = validate_params(modifier_type, params or {})

    modifier_name = name or modifier_type.replace("_", " ").title()

    modifier_entry = {
        "type": modifier_type,
        "name": modifier_name,
        "bpy_type": MODIFIER_REGISTRY[modifier_type]["bpy_type"],
        "params": validated,
    }

    obj = objects[object_index]
    if "modifiers" not in obj:
        obj["modifiers"] = []
    obj["modifiers"].append(modifier_entry)

    return modifier_entry


def remove_modifier(
    project: Dict[str, Any],
    modifier_index: int,
    object_index: int = 0,
) -> Dict[str, Any]:
    """Remove a modifier from an object by index."""
    objects = project.get("objects", [])
    if object_index < 0 or object_index >= len(objects):
        raise IndexError(f"Object index {object_index} out of range")

    obj = objects[object_index]
    modifiers = obj.get("modifiers", [])
    if modifier_index < 0 or modifier_index >= len(modifiers):
        raise IndexError(f"Modifier index {modifier_index} out of range (0-{len(modifiers)-1})")

    return modifiers.pop(modifier_index)


def set_modifier_param(
    project: Dict[str, Any],
    modifier_index: int,
    param: str,
    value: Any,
    object_index: int = 0,
) -> None:
    """Set a modifier parameter value."""
    objects = project.get("objects", [])
    if object_index < 0 or object_index >= len(objects):
        raise IndexError(f"Object index {object_index} out of range")

    obj = objects[object_index]
    modifiers = obj.get("modifiers", [])
    if modifier_index < 0 or modifier_index >= len(modifiers):
        raise IndexError(f"Modifier index {modifier_index} out of range")

    mod = modifiers[modifier_index]
    mod_type = mod["type"]
    spec = MODIFIER_REGISTRY[mod_type]["params"]

    if param not in spec:
        raise ValueError(
            f"Unknown parameter '{param}' for modifier '{mod_type}'. Valid: {list(spec.keys())}"
        )

    # Validate using the spec
    test_params = dict(mod["params"])
    test_params[param] = value
    validated = validate_params(mod_type, test_params)
    mod["params"] = validated


def list_modifiers(
    project: Dict[str, Any],
    object_index: int = 0,
) -> List[Dict[str, Any]]:
    """List modifiers on an object."""
    objects = project.get("objects", [])
    if object_index < 0 or object_index >= len(objects):
        raise IndexError(f"Object index {object_index} out of range")

    obj = objects[object_index]
    result = []
    for i, mod in enumerate(obj.get("modifiers", [])):
        result.append({
            "index": i,
            "type": mod["type"],
            "name": mod.get("name", mod["type"]),
            "bpy_type": mod.get("bpy_type", "UNKNOWN"),
            "params": mod["params"],
            "category": MODIFIER_REGISTRY.get(mod["type"], {}).get("category", "unknown"),
        })
    return result
