"""Training workflow orchestration"""

import os
from datetime import datetime
from typing import Dict, Any, Optional
from ..utils.unimol_backend import UniMolBackend


def run_training(
    project: Dict[str, Any],
    run_name: Optional[str] = None,
    resume_from: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute training

    Args:
        project: Project dict
        run_name: Run name (auto-generated if not provided)
        resume_from: Resume from run_id (optional)

    Returns:
        Training result dict
    """
    # Validate dataset
    if not project["datasets"]["train"]:
        raise ValueError("Training dataset not set. Use 'project set-dataset train <path>'")

    # Generate run_id and save path in project directory
    run_id = run_name or f"run_{len(project['runs']) + 1:03d}"

    # Use project directory instead of dataset directory
    project_dir = project.get("_project_dir", os.path.dirname(project["datasets"]["train"]))
    save_path = os.path.join(project_dir, "experiments", run_id)

    # Prepare config
    config = {
        **project["config"],
        "save_path": save_path,
        "data_path": project["datasets"]["train"],
        "valid_data_path": project["datasets"].get("valid"),
    }

    if resume_from:
        # Find previous run
        prev_run = next((r for r in project["runs"] if r["run_id"] == resume_from), None)
        if not prev_run:
            raise ValueError(f"Run not found: {resume_from}")
        config["load_model_dir"] = prev_run["model_dir"]

    # Call backend training
    backend = UniMolBackend()
    result = backend.train(config)

    # Record run
    run_record = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "status": result["status"],
        "metrics": result.get("metrics", {}),
        "model_dir": result["model_path"],
        "config": config,
        "duration_sec": result.get("duration_sec", 0)
    }

    project["runs"].append(run_record)

    return {
        "status": "completed",
        "run_id": run_id,
        "metrics": result.get("metrics", {}),
        "model_dir": result["model_path"]
    }


def list_runs(project: Dict[str, Any]) -> Dict[str, Any]:
    """List all training runs"""
    return {
        "total": len(project["runs"]),
        "runs": [
            {
                "run_id": r["run_id"],
                "timestamp": r["timestamp"],
                "status": r["status"],
                "metrics": r["metrics"]
            }
            for r in project["runs"]
        ]
    }


def get_run_details(project: Dict[str, Any], run_id: str) -> Dict[str, Any]:
    """Get run details"""
    run = next((r for r in project["runs"] if r["run_id"] == run_id), None)
    if not run:
        raise ValueError(f"Run not found: {run_id}")

    return run
