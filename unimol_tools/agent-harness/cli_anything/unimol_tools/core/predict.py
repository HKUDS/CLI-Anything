"""Prediction workflow orchestration"""

import os
from datetime import datetime
from typing import Dict, Any, Optional
from ..utils.unimol_backend import UniMolBackend


def run_prediction(
    project: Dict[str, Any],
    run_id: str,
    data_path: str,
    output_path: Optional[str] = None,
    metrics: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute prediction

    Args:
        project: Project dict
        run_id: Model run ID to use
        data_path: Prediction data path
        output_path: Output path (optional)
        metrics: Evaluation metrics (optional, if true labels available)

    Returns:
        Prediction result dict
    """
    # Find model run
    run = next((r for r in project["runs"] if r["run_id"] == run_id), None)
    if not run:
        raise ValueError(f"Run not found: {run_id}")

    model_dir = run["model_dir"]
    if not os.path.exists(model_dir):
        raise FileNotFoundError(f"Model directory not found: {model_dir}")

    # Generate output path in project directory
    if not output_path:
        pred_id = f"pred_{len(project['predictions']) + 1:03d}"
        project_dir = project.get("_project_dir", os.path.dirname(data_path))
        output_path = os.path.join(project_dir, "predictions", f"{pred_id}.csv")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Call backend prediction
    backend = UniMolBackend()
    result = backend.predict(
        model_dir=model_dir,
        data_path=data_path,
        output_path=output_path,
        metrics=metrics
    )

    # Record prediction
    pred_record = {
        "pred_id": os.path.basename(output_path).replace('.csv', ''),
        "run_id": run_id,
        "data_path": data_path,
        "output_path": output_path,
        "timestamp": datetime.now().isoformat(),
        "metrics": result.get("metrics", {})
    }

    project["predictions"].append(pred_record)

    return {
        "status": "completed",
        "output_path": output_path,
        "metrics": result.get("metrics", {})
    }


def list_predictions(project: Dict[str, Any]) -> Dict[str, Any]:
    """List all predictions"""
    return {
        "total": len(project["predictions"]),
        "predictions": [
            {
                "pred_id": p["pred_id"],
                "run_id": p["run_id"],
                "timestamp": p["timestamp"],
                "output_path": p["output_path"]
            }
            for p in project["predictions"]
        ]
    }
