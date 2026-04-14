"""Project management - Create, load, save, configure projects"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from .session import _locked_save_json


def create_project(
    name: str,
    task: str,
    output_dir: str,
    model_name: str = "unimolv1",
    model_size: str = "84m",
    **kwargs
) -> Dict[str, Any]:
    """
    Create new Uni-Mol project

    Each project gets its own directory:
    - Project file: output_dir/name/project.json
    - Experiments: output_dir/name/experiments/
    - Conformers: output_dir/name/conformers/
    - Predictions: output_dir/name/predictions/

    Args:
        name: Project name
        task: Task type
        output_dir: Output directory
        model_name: Model name
        model_size: Model size
        **kwargs: Other config

    Returns:
        {"status": "created", "project_path": "...", "project": {...}}
    """
    # Create project directory
    project_dir = os.path.join(output_dir, name)
    os.makedirs(project_dir, exist_ok=True)

    # Determine default metric based on task type
    if task == "classification":
        default_metric = "auc"  # Binary classification uses AUC
    elif task == "multiclass":
        default_metric = "acc"  # Multiclass uses accuracy
    elif task in ["multilabel_classification"]:
        default_metric = "auc"  # Multilabel classification uses AUC per label
    elif task in ["regression", "multilabel_regression"]:
        default_metric = "mae"  # Regression tasks use MAE
    else:
        default_metric = "mae"  # Default fallback

    project = {
        "version": "1.0",
        "project_type": task,
        "_project_dir": project_dir,  # Each project has its own directory
        "metadata": {
            "name": name,
            "created": datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
            "description": kwargs.get("description", "")
        },
        "config": {
            "task": task,
            "model_name": model_name,
            "model_size": model_size if model_name == "unimolv2" else None,
            "epochs": kwargs.get("epochs", 10),
            "batch_size": kwargs.get("batch_size", 16),
            "learning_rate": kwargs.get("learning_rate", 1e-4),
            "metrics": kwargs.get("metrics", default_metric),
            "split": kwargs.get("split", "random"),
            "kfold": kwargs.get("kfold", 1),
            "early_stopping": kwargs.get("early_stopping", 20),
            "use_ddp": kwargs.get("use_ddp", False),
            "use_gpu": kwargs.get("use_gpu", "all"),
            "use_amp": kwargs.get("use_amp", False),
            "remove_hs": kwargs.get("remove_hs", False),
            "conf_cache_level": kwargs.get("conf_cache_level", 1),
            "target_normalize": kwargs.get("target_normalize", "auto"),
        },
        "datasets": {
            "train": None,
            "valid": None,
            "test": None
        },
        "runs": [],
        "predictions": []
    }

    # Save project file in project directory
    project_path = os.path.join(project_dir, "project.json")

    _locked_save_json(project_path, project)

    return {
        "status": "created",
        "project_path": project_path,
        "project": project
    }


def load_project(project_path: str) -> Dict[str, Any]:
    """Load project"""
    if not os.path.exists(project_path):
        raise FileNotFoundError(f"Project not found: {project_path}")

    with open(project_path, 'r') as f:
        project = json.load(f)

    # Ensure _project_dir is set (for backward compatibility)
    if "_project_dir" not in project:
        project["_project_dir"] = os.path.dirname(os.path.abspath(project_path))

    return {
        "status": "loaded",
        "project_path": project_path,
        "project": project
    }


def save_project(project_path: str, project: Dict[str, Any]) -> Dict[str, Any]:
    """Save project with file lock"""
    project["metadata"]["modified"] = datetime.now().isoformat()
    _locked_save_json(project_path, project)

    return {
        "status": "saved",
        "project_path": project_path
    }


def get_project_info(project: Dict[str, Any]) -> Dict[str, Any]:
    """Get project info"""
    return {
        "name": project["metadata"]["name"],
        "task": project["project_type"],
        "model": f"{project['config']['model_name']}-{project['config']['model_size']}",
        "created": project["metadata"]["created"],
        "modified": project["metadata"]["modified"],
        "total_runs": len(project["runs"]),
        "total_predictions": len(project["predictions"]),
        "datasets": project["datasets"]
    }


def set_dataset(
    project: Dict[str, Any],
    dataset_type: str,
    data_path: str
) -> Dict[str, Any]:
    """Set dataset path"""
    if dataset_type not in ["train", "valid", "test"]:
        raise ValueError(f"Invalid dataset type: {dataset_type}")

    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Dataset not found: {data_path}")

    # Ensure datasets key exists
    if "datasets" not in project:
        project["datasets"] = {"train": None, "valid": None, "test": None}

    project["datasets"][dataset_type] = os.path.abspath(data_path)

    return {
        "status": "updated",
        "dataset_type": dataset_type,
        "data_path": project["datasets"][dataset_type]
    }


def update_config(project: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Update project config"""
    for key, value in kwargs.items():
        if key in project["config"]:
            project["config"][key] = value

    return {
        "status": "updated",
        "config": project["config"]
    }
