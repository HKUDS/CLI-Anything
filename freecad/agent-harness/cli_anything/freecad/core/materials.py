"""
Materials module for the FreeCAD CLI harness.

Provides material creation, assignment, and management with a library of
physically-based rendering presets for common engineering materials.
"""

import json
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Material presets
# ---------------------------------------------------------------------------

PRESETS: Dict[str, Dict[str, Any]] = {
    "steel": {
        "color": [0.7, 0.7, 0.75, 1.0],
        "metallic": 0.9,
        "roughness": 0.3,
    },
    "aluminum": {
        "color": [0.8, 0.8, 0.85, 1.0],
        "metallic": 0.9,
        "roughness": 0.2,
    },
    "copper": {
        "color": [0.72, 0.45, 0.2, 1.0],
        "metallic": 1.0,
        "roughness": 0.25,
    },
    "brass": {
        "color": [0.78, 0.68, 0.35, 1.0],
        "metallic": 0.9,
        "roughness": 0.3,
    },
    "plastic_white": {
        "color": [0.95, 0.95, 0.95, 1.0],
        "metallic": 0.0,
        "roughness": 0.4,
    },
    "plastic_black": {
        "color": [0.1, 0.1, 0.1, 1.0],
        "metallic": 0.0,
        "roughness": 0.5,
    },
    "wood": {
        "color": [0.55, 0.35, 0.15, 1.0],
        "metallic": 0.0,
        "roughness": 0.7,
    },
    "glass": {
        "color": [0.85, 0.9, 0.95, 0.3],
        "metallic": 0.0,
        "roughness": 0.05,
    },
    "rubber": {
        "color": [0.15, 0.15, 0.15, 1.0],
        "metallic": 0.0,
        "roughness": 0.9,
    },
    "gold": {
        "color": [1.0, 0.84, 0.0, 1.0],
        "metallic": 1.0,
        "roughness": 0.1,
    },
    "titanium": {
        "color": [0.75, 0.75, 0.78, 1.0],
        "metallic": 0.9,
        "roughness": 0.25,
        "density": 4507,
        "youngs_modulus": 116,
        "poisson_ratio": 0.34,
        "yield_strength": 880,
        "ultimate_strength": 950,
    },
    "stainless_steel": {
        "color": [0.75, 0.75, 0.77, 1.0],
        "metallic": 0.95,
        "roughness": 0.2,
        "density": 8000,
        "youngs_modulus": 193,
        "poisson_ratio": 0.29,
        "yield_strength": 205,
        "ultimate_strength": 515,
    },
    "cast_iron": {
        "color": [0.4, 0.4, 0.42, 1.0],
        "metallic": 0.85,
        "roughness": 0.6,
        "density": 7200,
        "youngs_modulus": 170,
        "poisson_ratio": 0.26,
    },
    "carbon_fiber": {
        "color": [0.1, 0.1, 0.12, 1.0],
        "metallic": 0.3,
        "roughness": 0.15,
        "density": 1600,
        "youngs_modulus": 230,
    },
    "nylon": {
        "color": [0.9, 0.88, 0.82, 1.0],
        "metallic": 0.0,
        "roughness": 0.5,
        "density": 1150,
        "youngs_modulus": 2.7,
    },
    "abs": {
        "color": [0.95, 0.95, 0.9, 1.0],
        "metallic": 0.0,
        "roughness": 0.45,
        "density": 1040,
        "youngs_modulus": 2.3,
    },
    "pla": {
        "color": [0.9, 0.9, 0.85, 1.0],
        "metallic": 0.0,
        "roughness": 0.4,
        "density": 1240,
        "youngs_modulus": 3.5,
    },
    "petg": {
        "color": [0.85, 0.88, 0.92, 1.0],
        "metallic": 0.05,
        "roughness": 0.35,
        "density": 1270,
        "youngs_modulus": 2.2,
    },
    "concrete": {
        "color": [0.7, 0.7, 0.68, 1.0],
        "metallic": 0.0,
        "roughness": 0.9,
        "density": 2400,
        "youngs_modulus": 30,
    },
    "granite": {
        "color": [0.55, 0.5, 0.48, 1.0],
        "metallic": 0.1,
        "roughness": 0.7,
        "density": 2700,
        "youngs_modulus": 70,
    },
    "marble": {
        "color": [0.92, 0.9, 0.88, 1.0],
        "metallic": 0.05,
        "roughness": 0.3,
        "density": 2700,
        "youngs_modulus": 70,
    },
}

# Valid material properties and their constraints
MATERIAL_PROPS: Dict[str, Dict[str, Any]] = {
    "color": {"type": "color4", "description": "Base color [R, G, B, A] (0.0-1.0)"},
    "metallic": {"type": "float", "min": 0.0, "max": 1.0, "description": "Metallic factor"},
    "roughness": {"type": "float", "min": 0.0, "max": 1.0, "description": "Roughness factor"},
    "name": {"type": "str", "description": "Material display name"},
    "density": {"type": "float", "min": 0.0, "description": "Density (kg/m^3)"},
    "youngs_modulus": {"type": "float", "min": 0.0, "description": "Young's modulus (GPa)"},
    "poisson_ratio": {"type": "float", "min": 0.0, "max": 0.5, "description": "Poisson's ratio"},
    "thermal_conductivity": {"type": "float", "min": 0.0, "description": "Thermal conductivity (W/(m*K))"},
    "specific_heat": {"type": "float", "min": 0.0, "description": "Specific heat capacity (J/(kg*K))"},
    "yield_strength": {"type": "float", "min": 0.0, "description": "Yield strength (MPa)"},
    "ultimate_strength": {"type": "float", "min": 0.0, "description": "Ultimate tensile strength (MPa)"},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _next_id(project: Dict[str, Any]) -> int:
    """Generate the next unique material ID."""
    materials = project.get("materials", [])
    existing_ids = [m.get("id", 0) for m in materials]
    return max(existing_ids, default=-1) + 1


def _unique_name(project: Dict[str, Any], base_name: str) -> str:
    """Generate a unique material name."""
    materials = project.get("materials", [])
    existing_names = {m.get("name", "") for m in materials}
    if base_name not in existing_names:
        return base_name
    counter = 1
    while f"{base_name}.{counter:03d}" in existing_names:
        counter += 1
    return f"{base_name}.{counter:03d}"


def _validate_project(project: Dict[str, Any]) -> None:
    """Raise ``ValueError`` if *project* is not a valid dict with a materials list."""
    if not isinstance(project, dict):
        raise ValueError("Project must be a dictionary")
    if "materials" not in project:
        raise ValueError("Project is missing 'materials' collection")
    if not isinstance(project["materials"], list):
        raise ValueError("Project 'materials' must be a list")


def _get_material(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Return material at *index* or raise ``IndexError``."""
    materials = project["materials"]
    if index < 0 or index >= len(materials):
        raise IndexError(
            f"Material index {index} out of range (0-{len(materials) - 1})"
        )
    return materials[index]


def _validate_color(color: List[float]) -> List[float]:
    """Validate and return a color as a list of 4 floats in [0, 1]."""
    if not isinstance(color, (list, tuple)):
        raise ValueError(f"Color must be a list, got {type(color).__name__}")
    if len(color) < 3:
        raise ValueError(f"Color must have at least 3 components [R, G, B], got {len(color)}")
    if len(color) == 3:
        color = list(color) + [1.0]
    if len(color) > 4:
        raise ValueError(f"Color must have at most 4 components [R, G, B, A], got {len(color)}")
    result: List[float] = []
    for i, c in enumerate(color):
        try:
            val = float(c)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Color component {i} must be numeric: {exc}") from exc
        if not 0.0 <= val <= 1.0:
            raise ValueError(f"Color component {i} must be 0.0-1.0, got {val}")
        result.append(val)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_material(
    project: Dict[str, Any],
    name: str = "Material",
    preset: Optional[str] = None,
    color: Optional[List[float]] = None,
    metallic: float = 0.0,
    roughness: float = 0.5,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Create a new material, optionally based on a preset.

    When *preset* is given, its ``color``, ``metallic``, and ``roughness``
    values are used as defaults.  Explicit *color*, *metallic*, and
    *roughness* arguments override the preset values.

    Parameters
    ----------
    project:
        The project dictionary.
    name:
        Material display name.
    preset:
        Optional preset key from :data:`PRESETS`.
    color:
        Base color ``[R, G, B, A]`` with components in ``[0, 1]``.
    metallic:
        Metallic factor ``[0, 1]``.
    roughness:
        Roughness factor ``[0, 1]``.
    **kwargs:
        Optional engineering properties: ``density``, ``youngs_modulus``,
        ``poisson_ratio``, ``thermal_conductivity``, ``specific_heat``,
        ``yield_strength``, ``ultimate_strength``.

    Returns
    -------
    Dict[str, Any]
        The newly created material dictionary.

    Raises
    ------
    ValueError
        If the preset is unknown, colour is invalid, or numeric values are
        out of range.
    """
    _validate_project(project)

    # Resolve preset defaults
    preset_data: Dict[str, Any] = {}
    if preset is not None:
        if preset not in PRESETS:
            raise ValueError(
                f"Unknown preset '{preset}'. Available presets: {', '.join(sorted(PRESETS))}"
            )
        preset_data = PRESETS[preset]
        # Use preset name as the material name if caller left the default
        if name == "Material":
            name = preset.replace("_", " ").title()

    # Determine final values (explicit args override preset)
    final_color: List[float]
    if color is not None:
        final_color = _validate_color(color)
    elif "color" in preset_data:
        final_color = list(preset_data["color"])
    else:
        final_color = [0.8, 0.8, 0.8, 1.0]

    final_metallic = metallic
    if preset_data and metallic == 0.0 and "metallic" in preset_data:
        # Only use preset metallic when caller left the default
        final_metallic = preset_data["metallic"]
    final_metallic = float(final_metallic)

    final_roughness = roughness
    if preset_data and roughness == 0.5 and "roughness" in preset_data:
        final_roughness = preset_data["roughness"]
    final_roughness = float(final_roughness)

    if not 0.0 <= final_metallic <= 1.0:
        raise ValueError(f"Metallic must be 0.0-1.0, got {final_metallic}")
    if not 0.0 <= final_roughness <= 1.0:
        raise ValueError(f"Roughness must be 0.0-1.0, got {final_roughness}")

    mat_name = _unique_name(project, name)

    mat: Dict[str, Any] = {
        "id": _next_id(project),
        "name": mat_name,
        "preset": preset,
        "color": final_color,
        "metallic": final_metallic,
        "roughness": final_roughness,
        "assigned_to": [],
    }

    # Engineering properties from preset (as defaults) and kwargs (overrides)
    _ENG_PROPS = (
        "density", "youngs_modulus", "poisson_ratio",
        "thermal_conductivity", "specific_heat",
        "yield_strength", "ultimate_strength",
    )
    for ep in _ENG_PROPS:
        value = kwargs.get(ep)
        if value is None and preset_data:
            value = preset_data.get(ep)
        if value is not None:
            value = float(value)
            spec = MATERIAL_PROPS.get(ep, {})
            if spec.get("min") is not None and value < spec["min"]:
                raise ValueError(
                    f"Property '{ep}' minimum is {spec['min']}, got {value}"
                )
            if spec.get("max") is not None and value > spec["max"]:
                raise ValueError(
                    f"Property '{ep}' maximum is {spec['max']}, got {value}"
                )
            mat[ep] = value

    project["materials"].append(mat)
    return mat


def assign_material(
    project: Dict[str, Any],
    material_index: int,
    part_index: int,
) -> Dict[str, Any]:
    """Assign a material to a part.

    Parameters
    ----------
    project:
        The project dictionary.
    material_index:
        Index of the material in ``project["materials"]``.
    part_index:
        Index of the part in ``project["parts"]``.

    Returns
    -------
    Dict[str, Any]
        Assignment summary with material and part names/IDs.

    Raises
    ------
    IndexError
        If either index is out of range.
    """
    _validate_project(project)

    mat = _get_material(project, material_index)

    parts = project.get("parts", [])
    if not isinstance(parts, list):
        raise ValueError("Project 'parts' must be a list")
    if part_index < 0 or part_index >= len(parts):
        raise IndexError(
            f"Part index {part_index} out of range (0-{len(parts) - 1})"
        )

    part = parts[part_index]

    # Record the assignment on the material
    if part_index not in mat.get("assigned_to", []):
        mat.setdefault("assigned_to", []).append(part_index)

    # Record the material on the part
    part["material_id"] = mat["id"]
    part["material_index"] = material_index

    return {
        "material": mat["name"],
        "material_id": mat["id"],
        "part": part.get("name", f"Part {part_index}"),
        "part_id": part.get("id", part_index),
    }


def list_materials(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return a summary list of all materials in the project.

    Parameters
    ----------
    project:
        The project dictionary.

    Returns
    -------
    List[Dict[str, Any]]
        List of material summaries.
    """
    _validate_project(project)

    result: List[Dict[str, Any]] = []
    for i, mat in enumerate(project["materials"]):
        result.append({
            "index": i,
            "id": mat.get("id", i),
            "name": mat.get("name", f"Material {i}"),
            "preset": mat.get("preset"),
            "color": mat.get("color", [0.8, 0.8, 0.8, 1.0]),
            "metallic": mat.get("metallic", 0.0),
            "roughness": mat.get("roughness", 0.5),
            "assigned_to": mat.get("assigned_to", []),
        })
    return result


def get_material(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Return the full material dictionary at the given index.

    Parameters
    ----------
    project:
        The project dictionary.
    index:
        Material index.

    Returns
    -------
    Dict[str, Any]
        The complete material dictionary.
    """
    _validate_project(project)
    return _get_material(project, index)


def set_material_property(
    project: Dict[str, Any],
    index: int,
    prop: str,
    value: Any,
) -> None:
    """Set a single property on a material.

    Parameters
    ----------
    project:
        The project dictionary.
    index:
        Material index.
    prop:
        Property name.  One of ``"color"``, ``"metallic"``, ``"roughness"``,
        or ``"name"``.
    value:
        New value.  Type depends on the property.

    Raises
    ------
    IndexError
        If *index* is out of range.
    ValueError
        If *prop* is unknown or *value* is invalid.
    """
    _validate_project(project)
    mat = _get_material(project, index)

    if prop not in MATERIAL_PROPS:
        raise ValueError(
            f"Unknown material property: '{prop}'. "
            f"Valid properties: {', '.join(sorted(MATERIAL_PROPS))}"
        )

    spec = MATERIAL_PROPS[prop]
    ptype = spec["type"]

    if ptype == "float":
        value = float(value)
        if "min" in spec and value < spec["min"]:
            raise ValueError(f"Property '{prop}' minimum is {spec['min']}, got {value}")
        if "max" in spec and value > spec["max"]:
            raise ValueError(f"Property '{prop}' maximum is {spec['max']}, got {value}")
        mat[prop] = value
    elif ptype == "color4":
        if isinstance(value, str):
            value = [float(x.strip()) for x in value.split(",")]
        mat[prop] = _validate_color(value)
    elif ptype == "str":
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Property '{prop}' must be a non-empty string")
        mat[prop] = value.strip()
    else:
        mat[prop] = value


def list_presets() -> List[Dict[str, Any]]:
    """Return a list of all available material presets.

    Returns
    -------
    List[Dict[str, Any]]
        Each entry contains the preset ``name``, ``color``, ``metallic``,
        ``roughness``, and any engineering properties.
    """
    results: List[Dict[str, Any]] = []
    for key, value in PRESETS.items():
        entry: Dict[str, Any] = {
            "name": key,
            "color": list(value["color"]),
            "metallic": value["metallic"],
            "roughness": value["roughness"],
        }
        for ep in (
            "density", "youngs_modulus", "poisson_ratio",
            "thermal_conductivity", "specific_heat",
            "yield_strength", "ultimate_strength",
        ):
            if ep in value:
                entry[ep] = value[ep]
        results.append(entry)
    return results


def import_material(project: Dict[str, Any], path: str) -> Dict[str, Any]:
    """Load a material from a JSON file and add it to the project.

    The JSON file should contain keys such as ``name``, ``color``,
    ``metallic``, ``roughness``, and optional engineering properties.

    Parameters
    ----------
    project:
        The project dictionary.
    path:
        Path to a JSON file describing the material.

    Returns
    -------
    Dict[str, Any]
        The newly created material dictionary.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the JSON is invalid or material properties are out of range.
    """
    _validate_project(project)

    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, dict):
        raise ValueError(f"Material JSON must be an object, got {type(data).__name__}")

    # Extract recognised kwargs for create_material
    create_kwargs: Dict[str, Any] = {}
    for ep in (
        "density", "youngs_modulus", "poisson_ratio",
        "thermal_conductivity", "specific_heat",
        "yield_strength", "ultimate_strength",
    ):
        if ep in data:
            create_kwargs[ep] = data[ep]

    return create_material(
        project,
        name=data.get("name", "Imported Material"),
        preset=data.get("preset"),
        color=data.get("color"),
        metallic=float(data.get("metallic", 0.0)),
        roughness=float(data.get("roughness", 0.5)),
        **create_kwargs,
    )


def export_material(project: Dict[str, Any], index: int, path: str) -> Dict[str, Any]:
    """Save a material to a JSON file.

    Parameters
    ----------
    project:
        The project dictionary.
    index:
        Material index.
    path:
        Destination file path.

    Returns
    -------
    Dict[str, Any]
        Summary with ``path`` and ``material_name``.

    Raises
    ------
    IndexError
        If *index* is out of range.
    """
    _validate_project(project)
    mat = _get_material(project, index)

    # Build a clean export dict (omit internal bookkeeping)
    export_data: Dict[str, Any] = {}
    for key in (
        "name", "color", "metallic", "roughness", "preset",
        "density", "youngs_modulus", "poisson_ratio",
        "thermal_conductivity", "specific_heat",
        "yield_strength", "ultimate_strength",
    ):
        if key in mat:
            export_data[key] = mat[key]

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(export_data, fh, indent=2)

    return {"path": path, "material_name": mat.get("name", f"Material {index}")}
