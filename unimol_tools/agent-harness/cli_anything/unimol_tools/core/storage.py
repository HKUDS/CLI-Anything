"""Storage analysis and management"""

import os
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timedelta


def get_file_size(path: str) -> int:
    """Get file size in bytes"""
    try:
        return os.path.getsize(path)
    except (OSError, FileNotFoundError):
        return 0


def get_directory_size(path: str) -> int:
    """Get total size of directory recursively"""
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                total += get_file_size(filepath)
    except (OSError, FileNotFoundError):
        pass
    return total


def format_size(bytes_size: int) -> str:
    """Format bytes to human readable size"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f}{unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f}PB"


def get_file_age_days(path: str) -> int:
    """Get file age in days"""
    try:
        mtime = os.path.getmtime(path)
        age = datetime.now() - datetime.fromtimestamp(mtime)
        return age.days
    except (OSError, FileNotFoundError):
        return 0


def analyze_project_storage(project: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze storage usage for a project

    Returns:
        {
            "total_mb": float,
            "breakdown": {
                "models": float,
                "conformers": float,
                "predictions": float,
                "models_pct": float,
                "conformers_pct": float,
                "predictions_pct": float
            },
            "models_detail": [...],
            "recommendations": [...]
        }
    """
    project_root = project.get("_project_dir", "")

    # Initialize counters
    models_size = 0
    conformers_size = 0
    predictions_size = 0

    models_detail = []

    # Scan experiments directory (where models are stored)
    experiments_dir = os.path.join(project_root, "experiments") if project_root else ""
    if experiments_dir and os.path.exists(experiments_dir):
        for run in project.get("runs", []):
            # Support both model_dir and save_path
            model_dir = run.get("model_dir") or run.get("save_path", "")
            if model_dir and os.path.exists(model_dir):
                size = get_directory_size(model_dir)
                models_size += size

                # Get age from timestamp
                try:
                    timestamp = run.get("timestamp", "")
                    if timestamp:
                        run_time = datetime.fromisoformat(timestamp)
                        age_days = (datetime.now() - run_time).days
                    else:
                        age_days = 0
                except (ValueError, TypeError):
                    age_days = 0

                models_detail.append({
                    "run_id": run["run_id"],
                    "size_mb": size / (1024 ** 2),
                    "auc": run.get("metrics", {}).get("auc", 0),
                    "age_days": age_days
                })

    # Scan conformers directory
    conformers_dir = os.path.join(project_root, "conformers") if project_root else ""
    if conformers_dir and os.path.exists(conformers_dir):
        conformers_size = get_directory_size(conformers_dir)

    # Scan predictions directory
    predictions_dir = os.path.join(project_root, "predictions") if project_root else ""
    if predictions_dir and os.path.exists(predictions_dir):
        predictions_size = get_directory_size(predictions_dir)

    total_size = models_size + conformers_size + predictions_size
    total_mb = total_size / (1024 ** 2)

    # Calculate percentages
    models_pct = (models_size / total_size * 100) if total_size > 0 else 0
    conformers_pct = (conformers_size / total_size * 100) if total_size > 0 else 0
    predictions_pct = (predictions_size / total_size * 100) if total_size > 0 else 0

    # Generate recommendations
    recommendations = []

    # Check for old models (> 7 days)
    old_models = [m for m in models_detail if m["age_days"] > 7]
    if old_models:
        old_size_mb = sum(m["size_mb"] for m in old_models)
        recommendations.append({
            "type": "old_models",
            "message": f"{len(old_models)} models are > 7 days old",
            "potential_savings_mb": old_size_mb
        })

    # Check for low-performing models (AUC < 0.75)
    low_models = [m for m in models_detail if m["auc"] < 0.75 and m["age_days"] > 1]
    if low_models:
        low_size_mb = sum(m["size_mb"] for m in low_models)
        recommendations.append({
            "type": "low_performance",
            "message": f"{len(low_models)} models with AUC < 0.75",
            "potential_savings_mb": low_size_mb
        })

    return {
        "total_mb": total_mb,
        "breakdown": {
            "models": models_size / (1024 ** 2),
            "conformers": conformers_size / (1024 ** 2),
            "predictions": predictions_size / (1024 ** 2),
            "models_pct": models_pct,
            "conformers_pct": conformers_pct,
            "predictions_pct": predictions_pct
        },
        "models_detail": models_detail,
        "recommendations": recommendations
    }


def get_age_description(days: int) -> str:
    """Convert days to human readable age description"""
    if days == 0:
        return "today"
    elif days == 1:
        return "1 day"
    elif days < 7:
        return f"{days} days"
    elif days < 30:
        weeks = days // 7
        return f"{weeks} week{'s' if weeks > 1 else ''}"
    else:
        months = days // 30
        return f"{months} month{'s' if months > 1 else ''}"
