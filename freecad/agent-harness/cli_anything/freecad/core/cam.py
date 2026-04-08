"""FreeCAD CLI - CAM/CNC module.

Manages CAM jobs, stock definitions, tool configurations, machining
operations (profile, pocket, drilling, facing), G-code generation,
simulation, and export on a JSON-based project state.
"""

from copy import deepcopy
from typing import Any, Dict, List, Optional, Set

from .document import ensure_collection


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STOCK_TYPES: Set[str] = {"box", "cylinder", "from_part"}
VALID_TOOL_TYPES: Set[str] = {"endmill", "ballnose", "drill", "chamfer", "vbit", "facemill", "tap", "threadmill", "reamer"}

_COLLECTION_KEY = "cam_jobs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _next_id(project: Dict[str, Any]) -> int:
    """Return the next available integer ID for CAM jobs."""
    items = project.get(_COLLECTION_KEY, [])
    if not items:
        return 1
    return max(item["id"] for item in items) + 1


def _unique_name(project: Dict[str, Any], base: str) -> str:
    """Return a unique name derived from *base* inside the jobs list."""
    existing = {item["name"] for item in project.get(_COLLECTION_KEY, [])}
    if base not in existing:
        return base
    counter = 2
    while f"{base}_{counter}" in existing:
        counter += 1
    return f"{base}_{counter}"


def _get_job(project: Dict[str, Any], job_index: int) -> Dict[str, Any]:
    """Internal accessor with bounds checking."""
    items = ensure_collection(project, _COLLECTION_KEY)
    if not isinstance(job_index, int) or job_index < 0 or job_index >= len(items):
        raise IndexError(
            f"Job index {job_index} out of range (0..{len(items) - 1})"
        )
    return items[job_index]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def new_job(
    project: Dict[str, Any],
    part_index: int,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new CAM job for a part and append it to the project.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    part_index : int
        Index of the source part in ``project["parts"]``.
    name : str or None
        Human-readable label. Auto-generated when *None*.

    Returns
    -------
    dict
        The newly created job dictionary.

    Raises
    ------
    IndexError
        If *part_index* is out of range.
    """
    items = ensure_collection(project, _COLLECTION_KEY)

    parts = project.get("parts", [])
    if not isinstance(part_index, int) or part_index < 0 or part_index >= len(parts):
        raise IndexError(
            f"Part index {part_index} out of range (0..{len(parts) - 1})"
        )

    if name is None:
        name = _unique_name(project, "Job")

    job: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "source_part_index": part_index,
        "stock": None,
        "tools": [],
        "operations": [],
        "gcode": None,
    }

    items.append(job)
    return job


def set_stock(
    project: Dict[str, Any],
    job_index: int,
    stock_type: str = "box",
    extra_x: float = 2.0,
    extra_y: float = 2.0,
    extra_z: float = 2.0,
) -> Dict[str, Any]:
    """Define the raw stock material for a CAM job.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    job_index : int
        Index of the target job.
    stock_type : str
        Stock shape type (``"box"``, ``"cylinder"``, ``"from_part"``).
    extra_x : float
        Extra material on the X axis (each side).
    extra_y : float
        Extra material on the Y axis (each side).
    extra_z : float
        Extra material on the Z axis (each side).

    Returns
    -------
    dict
        The stock definition.

    Raises
    ------
    ValueError
        If *stock_type* is unknown.
    """
    if stock_type not in VALID_STOCK_TYPES:
        valid = ", ".join(sorted(VALID_STOCK_TYPES))
        raise ValueError(f"Unknown stock_type '{stock_type}'. Valid: {valid}")

    job = _get_job(project, job_index)

    stock: Dict[str, Any] = {
        "type": stock_type,
        "extra_x": float(extra_x),
        "extra_y": float(extra_y),
        "extra_z": float(extra_z),
    }

    job["stock"] = stock
    return stock


def add_profile_op(
    project: Dict[str, Any],
    job_index: int,
    faces: str = "all",
    depth: Optional[float] = None,
    step_down: float = 1.0,
    passes: Optional[int] = None,
    finishing_pass: bool = False,
) -> Dict[str, Any]:
    """Add a profile (contour) machining operation.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    job_index : int
        Index of the target job.
    faces : str
        Face selection (``"all"`` or specific face references).
    depth : float or None
        Total cut depth. When *None*, derived from part geometry.
    step_down : float
        Depth of cut per pass.
    passes : int or None
        Explicit number of passes. When provided, overrides automatic
        calculation from *step_down*.
    finishing_pass : bool
        When *True*, adds a light finishing pass after roughing.

    Returns
    -------
    dict
        The operation entry.
    """
    job = _get_job(project, job_index)

    op: Dict[str, Any] = {
        "type": "profile",
        "faces": faces,
        "depth": float(depth) if depth is not None else None,
        "step_down": float(step_down),
        "passes": int(passes) if passes is not None else None,
        "finishing_pass": finishing_pass,
    }

    job["operations"].append(op)
    return op


def add_pocket_op(
    project: Dict[str, Any],
    job_index: int,
    faces: str = "all",
    depth: Optional[float] = None,
    step_down: float = 1.0,
    step_over: float = 0.5,
) -> Dict[str, Any]:
    """Add a pocket machining operation.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    job_index : int
        Index of the target job.
    faces : str
        Face selection (``"all"`` or specific face references).
    depth : float or None
        Total pocket depth. When *None*, derived from part geometry.
    step_down : float
        Depth of cut per pass.
    step_over : float
        Lateral step-over as a fraction of tool diameter (0.0 to 1.0).

    Returns
    -------
    dict
        The operation entry.
    """
    job = _get_job(project, job_index)

    op: Dict[str, Any] = {
        "type": "pocket",
        "faces": faces,
        "depth": float(depth) if depth is not None else None,
        "step_down": float(step_down),
        "step_over": float(step_over),
    }

    job["operations"].append(op)
    return op


def add_drilling_op(
    project: Dict[str, Any],
    job_index: int,
    holes: str = "all",
    depth: Optional[float] = None,
    peck_depth: Optional[float] = None,
) -> Dict[str, Any]:
    """Add a drilling operation.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    job_index : int
        Index of the target job.
    holes : str
        Hole selection (``"all"`` or specific hole references).
    depth : float or None
        Total drill depth. When *None*, derived from part geometry.
    peck_depth : float or None
        Peck drilling increment. When *None*, drilling is continuous.

    Returns
    -------
    dict
        The operation entry.
    """
    job = _get_job(project, job_index)

    op: Dict[str, Any] = {
        "type": "drilling",
        "holes": holes,
        "depth": float(depth) if depth is not None else None,
        "peck_depth": float(peck_depth) if peck_depth is not None else None,
    }

    job["operations"].append(op)
    return op


def add_facing_op(
    project: Dict[str, Any],
    job_index: int,
    depth: float = 1.0,
    step_over: float = 0.5,
) -> Dict[str, Any]:
    """Add a facing (surface levelling) operation.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    job_index : int
        Index of the target job.
    depth : float
        Total material to remove from the top surface.
    step_over : float
        Lateral step-over as a fraction of tool diameter (0.0 to 1.0).

    Returns
    -------
    dict
        The operation entry.
    """
    job = _get_job(project, job_index)

    op: Dict[str, Any] = {
        "type": "facing",
        "depth": float(depth),
        "step_over": float(step_over),
    }

    job["operations"].append(op)
    return op


def add_tapping_op(
    project: Dict[str, Any],
    job_index: int,
    holes: str = "all",
    depth: Optional[float] = None,
    thread_pitch: float = 1.5,
    right_hand: bool = True,
) -> Dict[str, Any]:
    """Add a tapping operation (G84 right-hand / G74 left-hand).

    FreeCAD 1.1 introduces native tapping cycle support.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    job_index : int
        Index of the target job.
    holes : str
        Hole selection (``"all"`` or specific hole references).
    depth : float or None
        Total tap depth. When *None*, derived from part geometry.
    thread_pitch : float
        Thread pitch in project units.
    right_hand : bool
        When *True*, uses G84 (right-hand thread). When *False*,
        uses G74 (left-hand thread).

    Returns
    -------
    dict
        The operation entry.
    """
    job = _get_job(project, job_index)

    op: Dict[str, Any] = {
        "type": "tapping",
        "holes": holes,
        "depth": float(depth) if depth is not None else None,
        "thread_pitch": float(thread_pitch),
        "right_hand": right_hand,
        "g_code": "G84" if right_hand else "G74",
    }

    job["operations"].append(op)
    return op


def set_tool(
    project: Dict[str, Any],
    job_index: int,
    tool_number: int = 1,
    diameter: float = 6.0,
    flutes: int = 2,
    type: str = "endmill",
    tool_material: Optional[str] = None,
    coating: Optional[str] = None,
) -> Dict[str, Any]:
    """Define or replace a cutting tool in a CAM job.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    job_index : int
        Index of the target job.
    tool_number : int
        Tool number in the tool table (T1, T2, etc.).
    diameter : float
        Tool diameter in project units.
    flutes : int
        Number of cutting flutes.
    type : str
        Tool type (``"endmill"``, ``"ballnose"``, ``"drill"``, etc.).
    tool_material : str or None
        Tool substrate material (e.g. ``"HSS"``, ``"carbide"``).
    coating : str or None
        Tool coating (e.g. ``"TiN"``, ``"AlTiN"``, ``"DLC"``).

    Returns
    -------
    dict
        The tool entry.

    Raises
    ------
    ValueError
        If *type* is unknown.
    """
    if type not in VALID_TOOL_TYPES:
        valid = ", ".join(sorted(VALID_TOOL_TYPES))
        raise ValueError(f"Unknown tool type '{type}'. Valid: {valid}")

    job = _get_job(project, job_index)

    tool: Dict[str, Any] = {
        "tool_number": int(tool_number),
        "diameter": float(diameter),
        "flutes": int(flutes),
        "type": type,
    }

    if tool_material is not None:
        tool["tool_material"] = str(tool_material)
    if coating is not None:
        tool["coating"] = str(coating)

    # Replace existing tool with same number, or append
    for i, existing in enumerate(job["tools"]):
        if existing["tool_number"] == tool_number:
            job["tools"][i] = tool
            return tool

    job["tools"].append(tool)
    return tool


def generate_gcode(
    project: Dict[str, Any],
    job_index: int,
) -> Dict[str, Any]:
    """Record metadata for G-code generation.

    The actual G-code generation is performed by the generated FreeCAD
    macro. This function validates the job setup and stores generation
    metadata.

    Returns
    -------
    dict
        G-code generation metadata.

    Raises
    ------
    ValueError
        If the job is missing required setup (stock, tools, operations).
    """
    job = _get_job(project, job_index)

    if job["stock"] is None:
        raise ValueError("Job has no stock defined (call set_stock first)")

    if not job["tools"]:
        raise ValueError("Job has no tools defined (call set_tool first)")

    if not job["operations"]:
        raise ValueError("Job has no operations defined")

    job["gcode"] = {
        "status": "pending",
        "operations_count": len(job["operations"]),
        "tools_count": len(job["tools"]),
    }

    return job["gcode"]


def simulate_job(
    project: Dict[str, Any],
    job_index: int,
) -> Dict[str, Any]:
    """Simulate a CAM job and return estimated metrics.

    This is a rough estimation based on the number and type of
    operations. Actual simulation runs inside FreeCAD.

    Returns
    -------
    dict
        Simulation summary with estimated time and material removal.
    """
    job = _get_job(project, job_index)

    if not job["operations"]:
        raise ValueError("Job has no operations to simulate")

    # Rough time estimation per operation type (seconds)
    time_estimates = {
        "profile": 120.0,
        "pocket": 300.0,
        "drilling": 60.0,
        "facing": 180.0,
        "tapping": 90.0,
    }

    total_time = 0.0
    for op in job["operations"]:
        total_time += time_estimates.get(op["type"], 120.0)

    return {
        "job_name": job["name"],
        "operations_count": len(job["operations"]),
        "tools_used": len(job["tools"]),
        "estimated_time_seconds": total_time,
        "material_removal": "estimated",
    }


def export_gcode(
    project: Dict[str, Any],
    job_index: int,
    path: str,
) -> Dict[str, Any]:
    """Record metadata for exporting G-code to a file.

    The actual export is performed by the generated FreeCAD macro.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    job_index : int
        Index of the target job.
    path : str
        Output file path for the G-code.

    Returns
    -------
    dict
        Export metadata.

    Raises
    ------
    ValueError
        If *path* is invalid.
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Path must be a non-empty string")

    job = _get_job(project, job_index)

    return {
        "action": "export_gcode",
        "job_name": job["name"],
        "job_index": job_index,
        "path": path.strip(),
        "format": "gcode",
    }


def import_tool_library(
    project: Dict[str, Any],
    job_index: int,
    library_path: str,
) -> Dict[str, Any]:
    """Import a FreeCAD 1.1 tool library file into a CAM job.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    job_index : int
        Index of the target job.
    library_path : str
        Path to the tool library file to import.

    Returns
    -------
    dict
        Import metadata.

    Raises
    ------
    ValueError
        If *library_path* is invalid.
    """
    if not isinstance(library_path, str) or not library_path.strip():
        raise ValueError("library_path must be a non-empty string")

    job = _get_job(project, job_index)

    if "metadata" not in job:
        job["metadata"] = {}

    job["metadata"]["tool_library_path"] = library_path.strip()

    return {
        "action": "import_tool_library",
        "job_name": job["name"],
        "job_index": job_index,
        "library_path": library_path.strip(),
    }


def export_tool_library(
    project: Dict[str, Any],
    job_index: int,
    path: str,
) -> Dict[str, Any]:
    """Export the tool library of a CAM job to a file.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    job_index : int
        Index of the target job.
    path : str
        Output file path for the tool library.

    Returns
    -------
    dict
        Export metadata.

    Raises
    ------
    ValueError
        If *path* is invalid.
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Path must be a non-empty string")

    job = _get_job(project, job_index)

    return {
        "action": "export_tool_library",
        "job_name": job["name"],
        "job_index": job_index,
        "path": path.strip(),
        "tools_count": len(job["tools"]),
    }
