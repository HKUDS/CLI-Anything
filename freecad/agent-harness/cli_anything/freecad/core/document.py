"""
Document and project management for the FreeCAD CLI harness.

Provides creation, loading, saving, and inspection of JSON-based
FreeCAD project files, along with a set of predefined unit/workflow profiles.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

SOFTWARE_VERSION = "cli-anything-freecad 1.2.0"
PROJECT_SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

PROFILES: Dict[str, Dict[str, Any]] = {
    "default": {
        "description": "Default profile with millimetre units",
        "units": "mm",
    },
    "metric_small": {
        "description": "Metric profile for small parts",
        "units": "mm",
    },
    "metric_large": {
        "description": "Metric profile for architectural / large-scale work",
        "units": "m",
    },
    "imperial": {
        "description": "Imperial profile with inch units",
        "units": "in",
    },
    "print3d": {
        "description": "Profile oriented for 3D printing workflows",
        "units": "mm",
    },
    "cnc": {
        "description": "Precision-focused profile for CNC machining",
        "units": "mm",
    },
}

VALID_UNITS = {"mm", "m", "in"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return the current local time as an ISO-8601 string."""
    return datetime.now().isoformat()


# All collection keys that can exist in a project.  The first four are
# required for backward compatibility; the rest are lazily initialised.
_REQUIRED_COLLECTIONS = ("parts", "sketches", "bodies", "materials")
_OPTIONAL_COLLECTIONS = (
    "assemblies", "meshes", "techdraw_pages", "draft_objects",
    "measurements", "surfaces", "fem_analyses", "cam_jobs", "spreadsheets",
)
ALL_COLLECTIONS = _REQUIRED_COLLECTIONS + _OPTIONAL_COLLECTIONS


def ensure_collection(project: Dict[str, Any], key: str) -> list:
    """Return ``project[key]``, creating it as ``[]`` if absent."""
    if key not in project:
        project[key] = []
    return project[key]


def _validate_project(project: Dict[str, Any]) -> None:
    """Raise ``ValueError`` if *project* is missing required keys or has bad types."""
    required_keys = {"version", "name", "units", "parts", "sketches", "bodies", "materials", "metadata"}
    missing = required_keys - set(project.keys())
    if missing:
        raise ValueError(f"Project is missing required keys: {', '.join(sorted(missing))}")

    if not isinstance(project["name"], str) or not project["name"]:
        raise ValueError("Project 'name' must be a non-empty string")

    if project["units"] not in VALID_UNITS:
        raise ValueError(f"Invalid units '{project['units']}'. Must be one of: {', '.join(sorted(VALID_UNITS))}")

    for collection in _REQUIRED_COLLECTIONS:
        if not isinstance(project[collection], list):
            raise ValueError(f"Project '{collection}' must be a list")

    # Optional collections: validate type if present, but don't require
    for collection in _OPTIONAL_COLLECTIONS:
        if collection in project and not isinstance(project[collection], list):
            raise ValueError(f"Project '{collection}' must be a list")

    if not isinstance(project.get("metadata"), dict):
        raise ValueError("Project 'metadata' must be a dict")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_document(
    name: str = "Untitled",
    units: str = "mm",
    profile: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new project document.

    Parameters
    ----------
    name:
        Human-readable project name.
    units:
        Unit system (``"mm"``, ``"m"``, or ``"in"``).  Overridden by
        *profile* when a profile is supplied.
    profile:
        Optional profile key from :data:`PROFILES`.  When given, the
        profile's ``units`` value takes precedence over the *units*
        argument.

    Returns
    -------
    Dict[str, Any]
        A new project dictionary ready for use.

    Raises
    ------
    ValueError
        If *name* is empty, *units* is invalid, or *profile* is unknown.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Document name must be a non-empty string")

    if profile is not None:
        if profile not in PROFILES:
            raise ValueError(
                f"Unknown profile '{profile}'. Available profiles: {', '.join(sorted(PROFILES))}"
            )
        units = PROFILES[profile]["units"]

    if units not in VALID_UNITS:
        raise ValueError(f"Invalid units '{units}'. Must be one of: {', '.join(sorted(VALID_UNITS))}")

    now = _now_iso()

    project: Dict[str, Any] = {
        "version": PROJECT_SCHEMA_VERSION,
        "name": name.strip(),
        "units": units,
        "parts": [],
        "sketches": [],
        "bodies": [],
        "materials": [],
        "assemblies": [],
        "meshes": [],
        "techdraw_pages": [],
        "draft_objects": [],
        "measurements": [],
        "surfaces": [],
        "fem_analyses": [],
        "cam_jobs": [],
        "spreadsheets": [],
        "metadata": {
            "created": now,
            "modified": now,
            "software": SOFTWARE_VERSION,
        },
    }
    return project


def open_document(path: str) -> Dict[str, Any]:
    """Load a project document from a JSON file.

    Parameters
    ----------
    path:
        Filesystem path to the ``.json`` project file.

    Returns
    -------
    Dict[str, Any]
        The validated project dictionary.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the file cannot be parsed or fails validation.
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Path must be a non-empty string")

    if not os.path.isfile(path):
        raise FileNotFoundError(f"Project file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as fh:
            project = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse project file: {exc}") from exc

    if not isinstance(project, dict):
        raise ValueError("Project file must contain a JSON object at the top level")

    _validate_project(project)
    return project


def save_document(project: Dict[str, Any], path: str) -> str:
    """Save a project document to a JSON file.

    The ``metadata.modified`` timestamp is updated automatically before
    writing.

    Parameters
    ----------
    project:
        The project dictionary to persist.
    path:
        Destination file path.

    Returns
    -------
    str
        The absolute path of the saved file.

    Raises
    ------
    ValueError
        If the project fails validation or *path* is invalid.
    OSError
        If the file cannot be written.
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Path must be a non-empty string")

    _validate_project(project)

    project["metadata"]["modified"] = _now_iso()

    dir_name = os.path.dirname(path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(project, fh, indent=2, ensure_ascii=False)

    return os.path.abspath(path)


def get_document_info(project: Dict[str, Any]) -> Dict[str, Any]:
    """Return a concise summary of a project document.

    Parameters
    ----------
    project:
        A valid project dictionary.

    Returns
    -------
    Dict[str, Any]
        Summary containing name, units, and collection counts.

    Raises
    ------
    ValueError
        If the project fails validation.
    """
    _validate_project(project)

    info = {
        "name": project["name"],
        "units": project["units"],
        "version": project["version"],
    }
    for col in ALL_COLLECTIONS:
        info[f"{col}_count"] = len(project.get(col, []))
    info["metadata"] = project.get("metadata", {})
    return info


def list_profiles() -> List[Dict[str, Any]]:
    """Return a list of available project profiles.

    Each entry contains the profile ``name``, ``units``, and
    ``description``.

    Returns
    -------
    List[Dict[str, Any]]
    """
    return [
        {
            "name": key,
            "units": value["units"],
            "description": value["description"],
        }
        for key, value in PROFILES.items()
    ]
