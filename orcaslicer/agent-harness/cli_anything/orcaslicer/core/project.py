"""OrcaSlicer CLI - project data layer (JSON project file) and model list."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from cli_anything.orcaslicer.core.session import _locked_save_json
from cli_anything.orcaslicer.utils.orcaslicer_backend import SUPPORTED_MODEL_EXTENSIONS

PROJECT_VERSION = "1.0"
PROJECT_SUFFIX = ".orca-cli.json"

DEFAULT_MACHINE = "Generic FDM 256"
DEFAULT_PROCESS = "0.20mm Standard"
DEFAULT_FILAMENT = "Generic PLA"


def _now() -> str:
    return datetime.now().isoformat()


def create_project(
    name: str = "untitled",
    machine: str = DEFAULT_MACHINE,
    process: str = DEFAULT_PROCESS,
    filament: str = DEFAULT_FILAMENT,
    profile_dirs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create an empty project. Preset refs are validated by the CLI layer."""
    if not name or not name.strip():
        raise ValueError("Project name must not be empty.")
    return {
        "version": PROJECT_VERSION,
        "name": name.strip(),
        "metadata": {"created": _now(), "modified": _now()},
        "models": [],
        "transforms": [],
        "profiles": {
            "machine": machine,
            "process": process,
            "filaments": [filament],
            "dirs": [os.path.abspath(os.path.expanduser(d)) for d in (profile_dirs or [])],
        },
        "overrides": {"machine": {}, "process": {}, "filament": {}},
        "slice": {"plate": 0, "strict": False, "no_check": False, "outdir": None,
                  "auto_ensure_on_bed": True},
        "history": [],
    }


def open_project(path: str) -> Dict[str, Any]:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Project file not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            project = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Project file is not valid JSON: {path} ({exc})") from exc
    validate_project(project, path)
    return project


def validate_project(project: Any, path: str = "<project>") -> None:
    if not isinstance(project, dict):
        raise ValueError(f"{path}: project must be a JSON object.")
    missing = [k for k in ("name", "models", "transforms", "profiles", "overrides", "slice") if k not in project]
    if missing:
        raise ValueError(f"{path}: not an OrcaSlicer CLI project (missing {', '.join(missing)}).")
    for kind in ("machine", "process", "filament"):
        project["overrides"].setdefault(kind, {})
    project.setdefault("history", [])
    project["profiles"].setdefault("dirs", [])
    project["profiles"].setdefault("filaments", [DEFAULT_FILAMENT])


def save_project(project: Dict[str, Any], path: str) -> str:
    project.setdefault("metadata", {})["modified"] = _now()
    _locked_save_json(path, project, indent=2, sort_keys=True, default=str)
    return os.path.abspath(path)


def project_info(project: Dict[str, Any]) -> Dict[str, Any]:
    profiles = project["profiles"]
    return {
        "name": project["name"],
        "models": len(project["models"]),
        "model_files": [m["path"] for m in project["models"]],
        "transforms": [describe_transform(t) for t in project["transforms"]],
        "machine": profiles["machine"],
        "process": profiles["process"],
        "filaments": list(profiles["filaments"]),
        "profile_dirs": list(profiles.get("dirs", [])),
        "overrides": {k: len(v) for k, v in project["overrides"].items()},
        "slice": dict(project["slice"]),
        "slices_run": len(project.get("history", [])),
        "modified": project.get("metadata", {}).get("modified"),
    }


def describe_transform(t: Dict[str, Any]) -> str:
    v = t.get("value")
    if v is None or v is True:
        return t["op"]
    return f"{t['op']}={v:g}" if isinstance(v, float) else f"{t['op']}={v}"


# ── Models ───────────────────────────────────────────────────────


def add_model(project: Dict[str, Any], path: str, name: Optional[str] = None,
              filament: Optional[int] = None) -> Dict[str, Any]:
    """Register an input model (STL/OBJ/3MF/STEP/AMF). Path is stored absolute."""
    full = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(full):
        raise FileNotFoundError(f"Model file not found: {full}")
    ext = os.path.splitext(full)[1].lower()
    if ext not in SUPPORTED_MODEL_EXTENSIONS:
        raise ValueError(
            f"Unsupported model format '{ext}'. Supported: {', '.join(SUPPORTED_MODEL_EXTENSIONS)}")
    if os.path.getsize(full) == 0:
        raise ValueError(f"Model file is empty: {full}")
    n_fil = len(project["profiles"]["filaments"])
    if filament is not None and not (1 <= filament <= max(n_fil, 1)):
        raise ValueError(
            f"Filament slot {filament} out of range: project has {n_fil} filament(s) (1-based).")
    next_id = max([m["id"] for m in project["models"]], default=-1) + 1
    model = {
        "id": next_id,
        "name": name or os.path.basename(full),
        "path": full,
        "filament": filament,
        "bytes": os.path.getsize(full),
    }
    project["models"].append(model)
    return model


def remove_model(project: Dict[str, Any], model_id: int) -> Dict[str, Any]:
    for i, m in enumerate(project["models"]):
        if m["id"] == model_id:
            return project["models"].pop(i)
    raise IndexError(f"No model with id {model_id}. Use 'model list' to see ids.")


def list_models(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for m in project["models"]:
        entry = copy.deepcopy(m)
        entry["exists"] = os.path.isfile(m["path"])
        out.append(entry)
    return out


def fingerprint(project: Dict[str, Any]) -> str:
    """Stable fingerprint of everything that influences a slice (incl. model file stats)."""
    models = []
    for m in project["models"]:
        try:
            st = os.stat(m["path"])
            models.append([m["path"], st.st_size, st.st_mtime_ns, m.get("filament")])
        except OSError:
            models.append([m["path"], None, None, m.get("filament")])
    payload = {
        "models": models,
        "transforms": project["transforms"],
        "profiles": project["profiles"],
        "overrides": project["overrides"],
        "slice": {k: v for k, v in project["slice"].items() if k != "outdir"},
    }
    blob = json.dumps(payload, sort_keys=True, default=str).encode()
    return "sha256:" + hashlib.sha256(blob).hexdigest()
