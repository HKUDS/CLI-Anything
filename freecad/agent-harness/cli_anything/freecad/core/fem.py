"""FreeCAD CLI - FEM (Finite Element Method) analysis module.

Manages FEM analyses, boundary constraints (fixed, force, pressure,
displacement, temperature, heat flux), material assignment, meshing,
solving, and result export on a JSON-based project state.
"""

from copy import deepcopy
from typing import Any, Dict, List, Optional, Set

from .document import ensure_collection
from cli_anything.freecad.utils.compat import require_version, V1_1


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_ELEMENT_TYPES: Set[str] = {"Tet4", "Tet10", "Hex8", "Hex20", "Tri3", "Tri6"}
VALID_SOLVERS: Set[str] = {"calculix", "elmer", "z88"}
VALID_EXPORT_FORMATS: Set[str] = {"vtk", "csv", "json"}
VALID_BEAM_SECTIONS: Set[str] = {"rectangular", "circular", "box_beam", "elliptical", "pipe"}
VALID_OUTPUT_FORMATS: Set[str] = {"vtu", "vtk", "result"}
VALID_MESHERS: Set[str] = {"gmsh", "netgen"}

_COLLECTION_KEY = "fem_analyses"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _next_id(project: Dict[str, Any]) -> int:
    """Return the next available integer ID for FEM analyses."""
    items = project.get(_COLLECTION_KEY, [])
    if not items:
        return 1
    return max(item["id"] for item in items) + 1


def _unique_name(project: Dict[str, Any], base: str) -> str:
    """Return a unique name derived from *base* inside the analyses list."""
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


def _get_analysis(project: Dict[str, Any], ai: int) -> Dict[str, Any]:
    """Internal accessor with bounds checking.

    Parameters
    ----------
    ai : int
        Analysis index.
    """
    items = ensure_collection(project, _COLLECTION_KEY)
    if not isinstance(ai, int) or ai < 0 or ai >= len(items):
        raise IndexError(
            f"Analysis index {ai} out of range (0..{len(items) - 1})"
        )
    return items[ai]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def new_analysis(
    project: Dict[str, Any],
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new FEM analysis and append it to the project.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    name : str or None
        Human-readable label. Auto-generated when *None*.

    Returns
    -------
    dict
        The newly created analysis dictionary.
    """
    items = ensure_collection(project, _COLLECTION_KEY)

    if name is None:
        name = _unique_name(project, "FEMAnalysis")

    analysis: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "constraints": [],
        "material_index": None,
        "mesh_params": None,
        "solver": None,
        "results": None,
    }

    items.append(analysis)
    return analysis


def add_fixed_constraint(
    project: Dict[str, Any],
    ai: int,
    references: List[Any],
) -> Dict[str, Any]:
    """Add a fixed (zero-displacement) boundary constraint.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    ai : int
        Analysis index.
    references : list
        Geometry references (faces, edges, vertices) to fix.

    Returns
    -------
    dict
        The constraint entry.
    """
    analysis = _get_analysis(project, ai)

    constraint: Dict[str, Any] = {
        "type": "fixed",
        "references": list(references),
    }

    analysis["constraints"].append(constraint)
    return constraint


def add_force_constraint(
    project: Dict[str, Any],
    ai: int,
    references: List[Any],
    magnitude: float,
    direction: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add a force constraint to the analysis.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    ai : int
        Analysis index.
    references : list
        Geometry references where the force is applied.
    magnitude : float
        Force magnitude in Newtons.
    direction : list[float] or None
        Force direction vector ``[x, y, z]``. Defaults to ``[0, 0, -1]``.

    Returns
    -------
    dict
        The constraint entry.
    """
    analysis = _get_analysis(project, ai)

    if direction is not None:
        direction = _validate_vec3(direction, "direction")
    else:
        direction = [0.0, 0.0, -1.0]

    constraint: Dict[str, Any] = {
        "type": "force",
        "references": list(references),
        "magnitude": float(magnitude),
        "direction": direction,
    }

    analysis["constraints"].append(constraint)
    return constraint


def add_pressure_constraint(
    project: Dict[str, Any],
    ai: int,
    references: List[Any],
    pressure: float,
) -> Dict[str, Any]:
    """Add a pressure constraint to the analysis.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    ai : int
        Analysis index.
    references : list
        Geometry references (faces) where pressure is applied.
    pressure : float
        Pressure value in MPa.

    Returns
    -------
    dict
        The constraint entry.
    """
    analysis = _get_analysis(project, ai)

    constraint: Dict[str, Any] = {
        "type": "pressure",
        "references": list(references),
        "pressure": float(pressure),
    }

    analysis["constraints"].append(constraint)
    return constraint


def add_displacement_constraint(
    project: Dict[str, Any],
    ai: int,
    references: List[Any],
    displacement: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Add a prescribed displacement constraint.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    ai : int
        Analysis index.
    references : list
        Geometry references where the displacement is prescribed.
    displacement : list[float] or None
        Displacement vector ``[dx, dy, dz]``. Defaults to ``[0, 0, 0]``.

    Returns
    -------
    dict
        The constraint entry.
    """
    analysis = _get_analysis(project, ai)

    if displacement is not None:
        displacement = _validate_vec3(displacement, "displacement")
    else:
        displacement = [0.0, 0.0, 0.0]

    constraint: Dict[str, Any] = {
        "type": "displacement",
        "references": list(references),
        "displacement": displacement,
    }

    analysis["constraints"].append(constraint)
    return constraint


def add_temperature_constraint(
    project: Dict[str, Any],
    ai: int,
    references: List[Any],
    temperature: float,
) -> Dict[str, Any]:
    """Add a temperature boundary constraint.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    ai : int
        Analysis index.
    references : list
        Geometry references where temperature is fixed.
    temperature : float
        Temperature value in Kelvin.

    Returns
    -------
    dict
        The constraint entry.
    """
    analysis = _get_analysis(project, ai)

    constraint: Dict[str, Any] = {
        "type": "temperature",
        "references": list(references),
        "temperature": float(temperature),
    }

    analysis["constraints"].append(constraint)
    return constraint


def add_heatflux_constraint(
    project: Dict[str, Any],
    ai: int,
    references: List[Any],
    flux: float,
) -> Dict[str, Any]:
    """Add a heat flux boundary constraint.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    ai : int
        Analysis index.
    references : list
        Geometry references where the heat flux is applied.
    flux : float
        Heat flux value in W/m^2.

    Returns
    -------
    dict
        The constraint entry.
    """
    analysis = _get_analysis(project, ai)

    constraint: Dict[str, Any] = {
        "type": "heatflux",
        "references": list(references),
        "flux": float(flux),
    }

    analysis["constraints"].append(constraint)
    return constraint


def set_fem_material(
    project: Dict[str, Any],
    ai: int,
    material_index: int,
) -> Dict[str, Any]:
    """Assign a material from the project's materials list to an analysis.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    ai : int
        Analysis index.
    material_index : int
        Index into ``project["materials"]``.

    Returns
    -------
    dict
        The updated analysis dictionary.

    Raises
    ------
    IndexError
        If *material_index* is out of range.
    """
    analysis = _get_analysis(project, ai)

    materials = project.get("materials", [])
    if not isinstance(material_index, int) or material_index < 0 or material_index >= len(materials):
        raise IndexError(
            f"Material index {material_index} out of range (0..{len(materials) - 1})"
        )

    analysis["material_index"] = material_index
    return analysis


def generate_fem_mesh(
    project: Dict[str, Any],
    ai: int,
    max_size: Optional[float] = None,
    min_size: Optional[float] = None,
    element_type: str = "Tet10",
    mesher: str = "gmsh",
    gmsh_verbosity: int = 1,
    second_order_linear: bool = False,
    local_refinement: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Configure mesh generation parameters for an analysis.

    The actual mesh generation is performed by the generated FreeCAD
    macro. This function stores the meshing parameters.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    ai : int
        Analysis index.
    max_size : float or None
        Maximum element size. When *None*, FreeCAD uses automatic sizing.
    min_size : float or None
        Minimum element size. When *None*, FreeCAD uses automatic sizing.
    element_type : str
        Element type (e.g. ``"Tet4"``, ``"Tet10"``, ``"Hex8"``).
    mesher : str
        Meshing backend (``"gmsh"`` or ``"netgen"``).
    gmsh_verbosity : int
        Gmsh verbosity level (only relevant when *mesher* is ``"gmsh"``).
    second_order_linear : bool
        Enable Netgen Second Order Linear elements.
    local_refinement : dict or None
        Mapping of geometry references to local mesh sizes.

    Returns
    -------
    dict
        The mesh parameters dictionary.

    Raises
    ------
    ValueError
        If *element_type* or *mesher* is unknown.
    """
    if element_type not in VALID_ELEMENT_TYPES:
        valid = ", ".join(sorted(VALID_ELEMENT_TYPES))
        raise ValueError(
            f"Unknown element_type '{element_type}'. Valid: {valid}"
        )

    if mesher not in VALID_MESHERS:
        valid = ", ".join(sorted(VALID_MESHERS))
        raise ValueError(
            f"Unknown mesher '{mesher}'. Valid: {valid}"
        )

    analysis = _get_analysis(project, ai)

    mesh_params: Dict[str, Any] = {
        "max_size": float(max_size) if max_size is not None else None,
        "min_size": float(min_size) if min_size is not None else None,
        "element_type": element_type,
        "mesher": mesher,
        "gmsh_verbosity": int(gmsh_verbosity),
        "second_order_linear": bool(second_order_linear),
        "local_refinement": dict(local_refinement) if local_refinement is not None else None,
    }

    analysis["mesh_params"] = mesh_params
    return mesh_params


def add_beam_section(
    project: Dict[str, Any],
    analysis_index: int,
    section_type: str = "rectangular",
    references: Optional[List[str]] = None,
    width: Optional[float] = None,
    height: Optional[float] = None,
    radius: Optional[float] = None,
) -> Dict[str, Any]:
    """Add an ElementGeometry1D beam section (FreeCAD 1.1: box_beam, elliptical).

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    analysis_index : int
        Analysis index.
    section_type : str
        Beam cross-section type (``"rectangular"``, ``"circular"``,
        ``"box_beam"``, ``"elliptical"``, ``"pipe"``).
    references : list[str] or None
        Geometry references (edges) where the section applies.
    width : float or None
        Section width (relevant for rectangular / box_beam / elliptical).
    height : float or None
        Section height (relevant for rectangular / box_beam / elliptical).
    radius : float or None
        Section radius (relevant for circular / pipe).

    Returns
    -------
    dict
        The constraint entry.

    Raises
    ------
    ValueError
        If *section_type* is unknown.
    """
    if section_type not in VALID_BEAM_SECTIONS:
        valid = ", ".join(sorted(VALID_BEAM_SECTIONS))
        raise ValueError(
            f"Unknown section_type '{section_type}'. Valid: {valid}"
        )

    # box_beam and elliptical sections require FreeCAD 1.1+
    if section_type in ("box_beam", "elliptical"):
        require_version(V1_1, f"beam section type '{section_type}'")

    analysis = _get_analysis(project, analysis_index)

    constraint: Dict[str, Any] = {
        "type": "beam_section",
        "section_type": section_type,
        "references": list(references) if references is not None else [],
        "width": float(width) if width is not None else None,
        "height": float(height) if height is not None else None,
        "radius": float(radius) if radius is not None else None,
    }

    analysis["constraints"].append(constraint)
    return constraint


def add_tie_constraint(
    project: Dict[str, Any],
    analysis_index: int,
    master_refs: List[str],
    slave_refs: List[str],
) -> Dict[str, Any]:
    """Add a tie constraint between shell faces.

    Requires FreeCAD >= 1.1.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    analysis_index : int
        Analysis index.
    master_refs : list[str]
        Geometry references for the master surface.
    slave_refs : list[str]
        Geometry references for the slave surface.

    Returns
    -------
    dict
        The constraint entry.
    """
    require_version(V1_1, "tie constraints")
    analysis = _get_analysis(project, analysis_index)

    constraint: Dict[str, Any] = {
        "type": "tie",
        "master_refs": list(master_refs),
        "slave_refs": list(slave_refs),
    }

    analysis["constraints"].append(constraint)
    return constraint


def purge_results(
    project: Dict[str, Any],
    analysis_index: int,
) -> Dict[str, Any]:
    """Delete all result objects from an analysis.

    Requires FreeCAD >= 1.1.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    analysis_index : int
        Analysis index.

    Returns
    -------
    dict
        The updated analysis dictionary.
    """
    require_version(V1_1, "purge_results")
    analysis = _get_analysis(project, analysis_index)
    analysis["results"] = None
    return analysis


def suppress_object(
    project: Dict[str, Any],
    analysis_index: int,
    constraint_index: int,
) -> Dict[str, Any]:
    """Toggle suppressed state on a constraint.

    Requires FreeCAD >= 1.1.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    analysis_index : int
        Analysis index.
    constraint_index : int
        Index of the constraint to toggle.

    Returns
    -------
    dict
        The updated constraint dictionary.

    Raises
    ------
    IndexError
        If *constraint_index* is out of range.
    """
    require_version(V1_1, "suppress_object")
    analysis = _get_analysis(project, analysis_index)
    constraints = analysis["constraints"]

    if not isinstance(constraint_index, int) or constraint_index < 0 or constraint_index >= len(constraints):
        raise IndexError(
            f"Constraint index {constraint_index} out of range "
            f"(0..{len(constraints) - 1})"
        )

    constraint = constraints[constraint_index]
    constraint["suppressed"] = not constraint.get("suppressed", False)
    return constraint


def solve_fem(
    project: Dict[str, Any],
    ai: int,
    solver: str = "calculix",
    output_format: Optional[str] = None,
    buckling_accuracy: Optional[float] = None,
) -> Dict[str, Any]:
    """Configure the FEM solver for an analysis.

    The actual solving is performed by the generated FreeCAD macro.
    This function stores the solver configuration and validates that
    the analysis has the minimum required setup.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    ai : int
        Analysis index.
    solver : str
        Solver backend name (``"calculix"``, ``"elmer"``, ``"z88"``).
    output_format : str or None
        Result output format (``"vtu"``, ``"vtk"``, ``"result"``).
        When *None*, the solver default is used.
    buckling_accuracy : float or None
        Buckling accuracy parameter for CalculiX solver.

    Returns
    -------
    dict
        Solver configuration summary.

    Raises
    ------
    ValueError
        If *solver* is unknown, *output_format* is invalid, or the
        analysis is missing constraints or mesh parameters.
    """
    if solver not in VALID_SOLVERS:
        valid = ", ".join(sorted(VALID_SOLVERS))
        raise ValueError(f"Unknown solver '{solver}'. Valid: {valid}")

    if output_format is not None and output_format not in VALID_OUTPUT_FORMATS:
        valid = ", ".join(sorted(VALID_OUTPUT_FORMATS))
        raise ValueError(
            f"Unknown output_format '{output_format}'. Valid: {valid}"
        )

    analysis = _get_analysis(project, ai)

    if not analysis["constraints"]:
        raise ValueError("Analysis has no constraints defined")

    if analysis["mesh_params"] is None:
        raise ValueError(
            "Mesh parameters must be set before solving "
            "(call generate_fem_mesh first)"
        )

    analysis["solver"] = solver
    analysis["results"] = {
        "status": "pending",
        "solver": solver,
        "constraints_count": len(analysis["constraints"]),
        "output_format": output_format,
        "buckling_accuracy": float(buckling_accuracy) if buckling_accuracy is not None else None,
    }

    return analysis["results"]


def get_fem_results(
    project: Dict[str, Any],
    ai: int,
) -> Dict[str, Any]:
    """Return the results of an analysis.

    Returns
    -------
    dict
        The results dictionary, or a status indicator if not yet solved.
    """
    analysis = _get_analysis(project, ai)

    if analysis["results"] is None:
        return {"status": "not_run", "message": "Analysis has not been solved yet"}

    return analysis["results"]


def export_fem_results(
    project: Dict[str, Any],
    ai: int,
    path: str,
    format: str = "vtk",
) -> Dict[str, Any]:
    """Record metadata for exporting FEM results.

    The actual export is performed by the generated FreeCAD macro.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    ai : int
        Analysis index.
    path : str
        Output file path.
    format : str
        Export format (``"vtk"``, ``"csv"``, ``"json"``).

    Returns
    -------
    dict
        Export metadata.

    Raises
    ------
    ValueError
        If *format* is unknown or *path* is invalid.
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Path must be a non-empty string")

    if format not in VALID_EXPORT_FORMATS:
        valid = ", ".join(sorted(VALID_EXPORT_FORMATS))
        raise ValueError(f"Unknown format '{format}'. Valid: {valid}")

    analysis = _get_analysis(project, ai)

    return {
        "action": "export_fem_results",
        "analysis_name": analysis["name"],
        "analysis_index": ai,
        "path": path.strip(),
        "format": format,
    }
