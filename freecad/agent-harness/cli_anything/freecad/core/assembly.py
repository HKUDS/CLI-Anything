"""FreeCAD CLI - Assembly module.

Manages assembly creation, component placement, constraints, solving,
bill-of-materials generation, and exploded/collapsed views on a
JSON-based project state.
"""

from copy import deepcopy
from typing import Any, Dict, List, Optional, Set

from .document import ensure_collection


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CONSTRAINTS: Set[str] = {
    "fixed", "coincident", "distance", "angle",
    "parallel", "perpendicular", "tangent",
    "revolute", "prismatic", "cylindrical",
    "ball", "planar", "gear", "belt",
}

_COLLECTION_KEY = "assemblies"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _next_id(project: Dict[str, Any]) -> int:
    """Return the next available integer ID for assemblies."""
    items = project.get(_COLLECTION_KEY, [])
    if not items:
        return 1
    return max(item["id"] for item in items) + 1


def _unique_name(project: Dict[str, Any], base: str) -> str:
    """Return a unique name derived from *base* inside the assemblies list."""
    existing = {item["name"] for item in project.get(_COLLECTION_KEY, [])}
    if base not in existing:
        return base
    counter = 2
    while f"{base}_{counter}" in existing:
        counter += 1
    return f"{base}_{counter}"


def _validate_vec3(value: Any, label: str) -> List[float]:
    """Validate that *value* is a list of exactly three numbers."""
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{label} must be a list of 3 numbers, got {type(value).__name__}")
    if len(value) != 3:
        raise ValueError(f"{label} must have exactly 3 elements, got {len(value)}")
    try:
        return [float(v) for v in value]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} elements must be numeric: {exc}") from exc


def _get_assembly(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Internal accessor with bounds checking."""
    items = ensure_collection(project, _COLLECTION_KEY)
    if not isinstance(index, int) or index < 0 or index >= len(items):
        raise IndexError(
            f"Assembly index {index} out of range (0..{len(items) - 1})"
        )
    return items[index]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_assembly(
    project: Dict[str, Any],
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new empty assembly and append it to the project.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    name : str or None
        Human-readable label. Auto-generated when *None*.

    Returns
    -------
    dict
        The newly created assembly dictionary.
    """
    items = ensure_collection(project, _COLLECTION_KEY)

    if name is None:
        name = _unique_name(project, "Assembly")

    assembly: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "components": [],
        "constraints": [],
        "solved": False,
    }

    items.append(assembly)
    return assembly


def add_part_to_assembly(
    project: Dict[str, Any],
    asm_index: int,
    part_index: int,
    transform: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add a part reference to an assembly as a component.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    asm_index : int
        Index of the target assembly.
    part_index : int
        Index of the part in ``project["parts"]``.
    transform : list[float] or None
        Optional ``[x, y, z]`` placement offset. Defaults to ``[0, 0, 0]``.

    Returns
    -------
    dict
        The newly created component entry.

    Raises
    ------
    IndexError
        If *asm_index* or *part_index* is out of range.
    """
    assembly = _get_assembly(project, asm_index)

    parts = project.get("parts", [])
    if not isinstance(part_index, int) or part_index < 0 or part_index >= len(parts):
        raise IndexError(
            f"Part index {part_index} out of range (0..{len(parts) - 1})"
        )

    if transform is not None:
        transform = _validate_vec3(transform, "transform")
    else:
        transform = [0.0, 0.0, 0.0]

    part = parts[part_index]
    component: Dict[str, Any] = {
        "part_index": part_index,
        "transform": transform,
        "name": part["name"],
    }

    assembly["components"].append(component)
    assembly["solved"] = False
    return component


def remove_part_from_assembly(
    project: Dict[str, Any],
    asm_index: int,
    component_index: int,
) -> Dict[str, Any]:
    """Remove a component from an assembly by its component index.

    Returns the removed component dictionary.

    Raises ``IndexError`` when either index is out of range.
    """
    assembly = _get_assembly(project, asm_index)
    components = assembly["components"]

    if not isinstance(component_index, int) or component_index < 0 or component_index >= len(components):
        raise IndexError(
            f"Component index {component_index} out of range "
            f"(0..{len(components) - 1})"
        )

    assembly["solved"] = False
    return components.pop(component_index)


def list_assemblies(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return all assemblies in the project."""
    return project.get(_COLLECTION_KEY, [])


def get_assembly(project: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Return the assembly at *index* without removing it.

    Raises ``IndexError`` when the index is out of range.
    """
    return _get_assembly(project, index)


def add_assembly_constraint(
    project: Dict[str, Any],
    asm_index: int,
    constraint_type: str,
    component_indices: List[int],
    **params: Any,
) -> Dict[str, Any]:
    """Add a constraint between components in an assembly.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    asm_index : int
        Index of the target assembly.
    constraint_type : str
        One of :data:`VALID_CONSTRAINTS`.
    component_indices : list[int]
        Indices of components involved in the constraint.
    **params
        Extra parameters depending on the constraint type (e.g.
        ``distance``, ``angle``, ``axis``).

    Returns
    -------
    dict
        The newly created constraint entry.

    Raises
    ------
    ValueError
        If *constraint_type* is unknown or *component_indices* is invalid.
    IndexError
        If *asm_index* or any component index is out of range.
    """
    if constraint_type not in VALID_CONSTRAINTS:
        valid = ", ".join(sorted(VALID_CONSTRAINTS))
        raise ValueError(
            f"Unknown constraint_type '{constraint_type}'. Valid: {valid}"
        )

    assembly = _get_assembly(project, asm_index)

    if not isinstance(component_indices, (list, tuple)) or len(component_indices) == 0:
        raise ValueError("component_indices must be a non-empty list of integers")

    num_components = len(assembly["components"])
    for ci in component_indices:
        if not isinstance(ci, int) or ci < 0 or ci >= num_components:
            raise IndexError(
                f"Component index {ci} out of range (0..{num_components - 1})"
            )

    constraint: Dict[str, Any] = {
        "type": constraint_type,
        "component_indices": list(component_indices),
        "params": dict(params),
    }

    assembly["constraints"].append(constraint)
    assembly["solved"] = False
    return constraint


def solve_assembly(
    project: Dict[str, Any],
    asm_index: int,
) -> Dict[str, Any]:
    """Mark the assembly as solved and return a DOF estimate.

    In the CLI harness the actual constraint solving happens in the
    generated FreeCAD macro. This function records the intent and
    provides a rough degrees-of-freedom estimate.

    Returns
    -------
    dict
        ``{"solved": True, "dof": <int>}``
    """
    assembly = _get_assembly(project, asm_index)
    assembly["solved"] = True

    num_components = len(assembly["components"])
    num_constraints = len(assembly["constraints"])
    dof = max(0, 6 * num_components - num_constraints)

    return {"solved": True, "dof": dof}


def degrees_of_freedom(
    project: Dict[str, Any],
    asm_index: int,
) -> Dict[str, Any]:
    """Estimate the remaining degrees of freedom for an assembly.

    Uses the simple formula ``6 * components - constraints``, clamped
    to zero.

    Returns
    -------
    dict
        ``{"dof": <int>, "components": <int>, "constraints": <int>}``
    """
    assembly = _get_assembly(project, asm_index)

    num_components = len(assembly["components"])
    num_constraints = len(assembly["constraints"])
    dof = max(0, 6 * num_components - num_constraints)

    return {
        "dof": dof,
        "components": num_components,
        "constraints": num_constraints,
    }


def generate_bom(
    project: Dict[str, Any],
    asm_index: int,
) -> Dict[str, Any]:
    """Generate a bill of materials for an assembly.

    Returns
    -------
    dict
        ``{"items": [{"name", "part_index", "quantity", "material"}], "total_parts": <int>}``
    """
    assembly = _get_assembly(project, asm_index)
    parts = project.get("parts", [])
    materials = project.get("materials", [])

    # Count occurrences of each part_index
    counts: Dict[int, int] = {}
    for comp in assembly["components"]:
        pi = comp["part_index"]
        counts[pi] = counts.get(pi, 0) + 1

    items: List[Dict[str, Any]] = []
    for pi, qty in sorted(counts.items()):
        part = parts[pi] if pi < len(parts) else {"name": f"Part_{pi}", "material_index": None}
        mat_name = None
        mi = part.get("material_index")
        if mi is not None and mi < len(materials):
            mat_name = materials[mi].get("name")

        items.append({
            "name": part["name"],
            "part_index": pi,
            "quantity": qty,
            "material": mat_name,
        })

    return {
        "items": items,
        "total_parts": len(assembly["components"]),
    }


def explode_assembly(
    project: Dict[str, Any],
    asm_index: int,
    factor: float = 2.0,
) -> Dict[str, Any]:
    """Move assembly components outward by *factor* for an exploded view.

    Each component's transform is scaled by *factor* relative to the
    assembly centroid.

    Returns
    -------
    dict
        ``{"exploded": True, "factor": <float>, "components": <int>}``
    """
    assembly = _get_assembly(project, asm_index)
    components = assembly["components"]

    if not components:
        return {"exploded": True, "factor": factor, "components": 0}

    # Compute centroid
    cx = sum(c["transform"][0] for c in components) / len(components)
    cy = sum(c["transform"][1] for c in components) / len(components)
    cz = sum(c["transform"][2] for c in components) / len(components)

    # Move each component outward
    for comp in components:
        t = comp["transform"]
        comp["transform"] = [
            cx + (t[0] - cx) * factor,
            cy + (t[1] - cy) * factor,
            cz + (t[2] - cz) * factor,
        ]

    return {"exploded": True, "factor": factor, "components": len(components)}


def collapse_assembly(
    project: Dict[str, Any],
    asm_index: int,
) -> Dict[str, Any]:
    """Reset all component transforms to their origin positions.

    If the assembly was previously solved, transforms are reset to
    ``[0, 0, 0]``.

    Returns
    -------
    dict
        ``{"collapsed": True, "components": <int>}``
    """
    assembly = _get_assembly(project, asm_index)

    for comp in assembly["components"]:
        comp["transform"] = [0.0, 0.0, 0.0]

    return {"collapsed": True, "components": len(assembly["components"])}


def insert_new_part(
    project: Dict[str, Any],
    asm_index: int,
    part_type: str = "box",
    name: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    transform: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Create a new part inline within an assembly.

    Instead of referencing an existing part from ``project["parts"]``,
    this function embeds an inline part definition directly in the
    assembly's components list.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    asm_index : int
        Index of the target assembly.
    part_type : str
        The type of part to create (e.g. ``"box"``, ``"cylinder"``).
    name : str or None
        Human-readable label. Auto-generated when *None*.
    params : dict or None
        Part-specific parameters (e.g. dimensions). Defaults to ``{}``.
    transform : list[float] or None
        Optional ``[x, y, z]`` placement offset. Defaults to ``[0, 0, 0]``.

    Returns
    -------
    dict
        The newly created component entry.

    Raises
    ------
    IndexError
        If *asm_index* is out of range.
    """
    assembly = _get_assembly(project, asm_index)

    if transform is not None:
        transform = _validate_vec3(transform, "transform")
    else:
        transform = [0.0, 0.0, 0.0]

    if params is None:
        params = {}

    if name is None:
        name = _unique_name(project, f"InlinePart_{part_type}")

    component: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "inline_part": {
            "type": part_type,
            "params": dict(params),
        },
        "transform": transform,
    }

    assembly["components"].append(component)
    assembly["solved"] = False
    return component


def create_simulation(
    project: Dict[str, Any],
    asm_index: int,
    name: Optional[str] = None,
    duration: float = 5.0,
    fps: int = 24,
) -> Dict[str, Any]:
    """Create a simulation entry on an assembly for joint motion/animation.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    asm_index : int
        Index of the target assembly.
    name : str or None
        Human-readable label. Auto-generated when *None*.
    duration : float
        Total simulation duration in seconds.
    fps : int
        Frames per second for the simulation.

    Returns
    -------
    dict
        The newly created simulation dictionary.

    Raises
    ------
    IndexError
        If *asm_index* is out of range.
    """
    assembly = _get_assembly(project, asm_index)

    if name is None:
        name = f"Simulation_{len(assembly.get('simulations', [])) + 1}"

    simulation: Dict[str, Any] = {
        "name": name,
        "duration": float(duration),
        "fps": int(fps),
        "steps": [],
        "status": "configured",
    }

    assembly.setdefault("simulations", []).append(simulation)
    return simulation


def add_simulation_step(
    project: Dict[str, Any],
    asm_index: int,
    sim_index: int,
    joint_index: int,
    start_value: float = 0.0,
    end_value: float = 1.0,
) -> Dict[str, Any]:
    """Append a motion step to an existing simulation.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    asm_index : int
        Index of the target assembly.
    sim_index : int
        Index of the simulation within the assembly's ``simulations`` list.
    joint_index : int
        Index of the joint/constraint this step drives.
    start_value : float
        Starting value for the joint parameter.
    end_value : float
        Ending value for the joint parameter.

    Returns
    -------
    dict
        The newly created step dictionary.

    Raises
    ------
    IndexError
        If *asm_index* or *sim_index* is out of range.
    """
    assembly = _get_assembly(project, asm_index)

    simulations = assembly.get("simulations", [])
    if not isinstance(sim_index, int) or sim_index < 0 or sim_index >= len(simulations):
        raise IndexError(
            f"Simulation index {sim_index} out of range "
            f"(0..{len(simulations) - 1})"
        )

    simulation = simulations[sim_index]

    step: Dict[str, Any] = {
        "joint_index": int(joint_index),
        "start_value": float(start_value),
        "end_value": float(end_value),
    }

    simulation["steps"].append(step)
    return step
