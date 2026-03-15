"""Workflow management — load, save, list, and validate ComfyUI workflow JSON files.

ComfyUI workflows are node graphs stored as JSON. Each node has a class_type
and an inputs dict. This module handles the file-level operations for workflows.
"""

import json
from pathlib import Path


def load_workflow(path: str) -> dict:
    """Load a ComfyUI workflow from a JSON file.

    Args:
        path: Path to the workflow JSON file.

    Returns:
        Workflow dict (node graph).

    Raises:
        RuntimeError: If the file does not exist or is not valid JSON.
    """
    p = Path(path)
    if not p.exists():
        raise RuntimeError(f"Workflow file not found: {path}")
    if not p.suffix.lower() == ".json":
        raise RuntimeError(f"Workflow file must be a .json file, got: {path}")
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON in workflow file {path}: {e}") from e

    if not isinstance(data, dict):
        raise RuntimeError(
            f"Workflow file must contain a JSON object (node graph), got: {type(data).__name__}"
        )

    return data


def save_workflow(workflow: dict, path: str) -> dict:
    """Save a ComfyUI workflow to a JSON file.

    Args:
        workflow: Workflow dict (node graph).
        path: Destination path for the JSON file.

    Returns:
        Dict with status and saved path.

    Raises:
        RuntimeError: If the workflow is not a dict or write fails.
    """
    if not isinstance(workflow, dict):
        raise RuntimeError(
            f"Workflow must be a dict, got: {type(workflow).__name__}"
        )

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(workflow, f, indent=2)
    except OSError as e:
        raise RuntimeError(f"Failed to write workflow to {path}: {e}") from e

    return {"status": "saved", "path": str(p.resolve()), "node_count": len(workflow)}


def list_workflows(directory: str) -> list[dict]:
    """List all workflow JSON files in a directory.

    Args:
        directory: Directory to search for workflow files.

    Returns:
        List of dicts with filename, path, and node_count for each workflow.

    Raises:
        RuntimeError: If the directory does not exist.
    """
    d = Path(directory)
    if not d.exists():
        raise RuntimeError(f"Workflow directory not found: {directory}")
    if not d.is_dir():
        raise RuntimeError(f"Not a directory: {directory}")

    results = []
    for p in sorted(d.glob("*.json")):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            node_count = len(data) if isinstance(data, dict) else 0
            valid = isinstance(data, dict)
        except Exception:
            node_count = 0
            valid = False

        results.append({
            "filename": p.name,
            "path": str(p.resolve()),
            "node_count": node_count,
            "valid": valid,
        })

    return results


def validate_workflow(workflow: dict) -> dict:
    """Validate a workflow's structure.

    Checks that the workflow is a dict of nodes, and each node has
    a 'class_type' and 'inputs' field.

    Args:
        workflow: Workflow dict to validate.

    Returns:
        Dict with 'valid' bool, 'node_count', 'errors' list, and 'warnings' list.
    """
    errors = []
    warnings = []

    if not isinstance(workflow, dict):
        return {
            "valid": False,
            "node_count": 0,
            "errors": [f"Workflow must be a dict, got: {type(workflow).__name__}"],
            "warnings": [],
        }

    if len(workflow) == 0:
        warnings.append("Workflow is empty (no nodes)")

    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            errors.append(f"Node '{node_id}': must be a dict, got {type(node).__name__}")
            continue

        if "class_type" not in node:
            errors.append(f"Node '{node_id}': missing 'class_type' field")

        if "inputs" not in node:
            warnings.append(f"Node '{node_id}': missing 'inputs' field")
        elif not isinstance(node["inputs"], dict):
            errors.append(
                f"Node '{node_id}': 'inputs' must be a dict, "
                f"got {type(node['inputs']).__name__}"
            )

    return {
        "valid": len(errors) == 0,
        "node_count": len(workflow),
        "errors": errors,
        "warnings": warnings,
    }
