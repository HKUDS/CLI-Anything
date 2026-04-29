"""Model management and ranking"""

import os
from typing import Dict, Any, List, Optional
from datetime import datetime


def calculate_model_score(run: Dict[str, Any],
                          weight_auc: float = 1.0,
                          weight_time: float = 0.0,
                          weight_recency: float = 0.0) -> float:
    """
    Calculate composite score for a model

    Args:
        run: Run dict with metrics
        weight_auc: Weight for AUC metric
        weight_time: Weight for training time
        weight_recency: Weight for recency

    Returns:
        Score from 0-10
    """
    metrics = run.get("metrics", {})

    # AUC score (0-10, normalized from 0-1)
    auc = metrics.get("auc", metrics.get("auroc", 0.5))
    auc_score = auc * 10

    # Time score (inverse - faster is better)
    # Assume typical range 10-30 seconds, normalize to 0-10
    duration = run.get("duration_sec", 20)
    if duration > 0:
        # Invert: 10s = 10, 30s = 0
        time_score = max(0, min(10, (30 - duration) / 2))
    else:
        time_score = 5  # neutral if no duration

    # Recency score (newer is better)
    # Within 24h = 10, > 7 days = 0
    try:
        timestamp = datetime.fromisoformat(run.get("timestamp", ""))
        age_hours = (datetime.now() - timestamp).total_seconds() / 3600
        if age_hours < 24:
            recency_score = 10
        elif age_hours < 168:  # 7 days
            recency_score = 10 - (age_hours - 24) / 144 * 10
        else:
            recency_score = 0
    except (ValueError, TypeError):
        recency_score = 5  # neutral if no timestamp

    # Weighted score
    total_score = (
        auc_score * weight_auc +
        time_score * weight_time +
        recency_score * weight_recency
    )

    return round(total_score, 1)


def rank_models(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Rank all models in a project

    Returns:
        List of runs with scores, sorted by score (best first)
    """
    runs = project.get("runs", [])

    if not runs:
        return []

    # Calculate scores
    ranked = []
    for run in runs:
        score = calculate_model_score(run)
        metrics = run.get("metrics", {})

        # Determine status
        auc = metrics.get("auc", metrics.get("auroc", 0))
        duration = run.get("duration_sec", 0)

        if auc >= 0.85:
            status = "Best" if score >= 8.5 else "Good"
        elif auc >= 0.75:
            status = "Ok"
        elif auc >= 0.65:
            status = "Weak"
        else:
            status = "Poor"

        ranked.append({
            "run_id": run["run_id"],
            "score": score,
            "auc": auc,
            "duration_sec": duration,
            "status": status,
            "timestamp": run.get("timestamp", ""),
            "metrics": metrics
        })

    # Sort by score (descending)
    ranked.sort(key=lambda x: x["score"], reverse=True)

    # Add ranks
    for i, item in enumerate(ranked, 1):
        item["rank"] = i

    return ranked


def get_best_model(project: Dict[str, Any], metric: str = "auc") -> Optional[Dict[str, Any]]:
    """Get the best model based on a metric"""
    runs = project.get("runs", [])

    if not runs:
        return None

    # Separate runs with and without the metric
    valid_runs = []
    invalid_runs = []

    for run in runs:
        metrics = run.get("metrics", {})
        if metric in metrics:
            valid_runs.append((run, metrics[metric]))
        else:
            invalid_runs.append(run)

    # If we have runs with the metric, return the best one
    if valid_runs:
        best_run = max(valid_runs, key=lambda x: x[1])
        return best_run[0]

    # If no runs have the metric, return the first run
    if invalid_runs:
        return invalid_runs[0]

    return None


def compare_models(project: Dict[str, Any], run_ids: List[str]) -> Dict[str, Any]:
    """
    Compare multiple models

    Args:
        project: Project dict
        run_ids: List of run IDs to compare

    Returns:
        Comparison dict with metrics and winner for each metric
    """
    runs = project.get("runs", [])

    # Find requested runs
    selected_runs = []
    for run_id in run_ids:
        run = next((r for r in runs if r["run_id"] == run_id), None)
        if run:
            selected_runs.append(run)

    if len(selected_runs) < 2:
        return {
            "error": "Need at least 2 models to compare",
            "found": len(selected_runs)
        }

    # Metrics to compare
    metric_names = [
        "auc", "auroc", "accuracy", "acc",
        "precision", "recall", "f1_score",
        "mcc", "log_loss"
    ]

    comparisons = {}

    for metric in metric_names:
        values = []
        for run in selected_runs:
            value = run.get("metrics", {}).get(metric)
            if value is not None:
                values.append({
                    "run_id": run["run_id"],
                    "value": value
                })

        if values:
            # Find winner (higher is better, except log_loss)
            if metric == "log_loss":
                winner = min(values, key=lambda x: x["value"])
            else:
                winner = max(values, key=lambda x: x["value"])

            comparisons[metric] = {
                "values": {v["run_id"]: v["value"] for v in values},
                "winner": winner["run_id"]
            }

    # Add training time comparison
    duration_values = []
    for run in selected_runs:
        duration = run.get("duration_sec")
        if duration:
            duration_values.append({
                "run_id": run["run_id"],
                "value": duration
            })

    if duration_values:
        winner = min(duration_values, key=lambda x: x["value"])
        comparisons["training_time"] = {
            "values": {v["run_id"]: v["value"] for v in duration_values},
            "winner": winner["run_id"]
        }

    # Calculate overall winner (most metric wins)
    win_counts = {run_id: 0 for run_id in run_ids}
    for comp in comparisons.values():
        if "winner" in comp:
            win_counts[comp["winner"]] += 1

    overall_winner = max(win_counts.items(), key=lambda x: x[1])

    return {
        "models": run_ids,
        "comparisons": comparisons,
        "overall_winner": overall_winner[0],
        "win_counts": win_counts
    }


def get_model_history(project: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get model performance history over time

    Returns:
        {
            "timeline": [...],
            "trend": "improving" | "declining" | "stable",
            "insights": [...]
        }
    """
    runs = project.get("runs", [])

    if not runs:
        return {
            "timeline": [],
            "trend": "none",
            "insights": [],
            "total_runs": 0
        }

    # Sort by timestamp
    sorted_runs = sorted(runs, key=lambda r: r.get("timestamp", ""))

    timeline = []
    for run in sorted_runs:
        metrics = run.get("metrics", {})
        auc = metrics.get("auc", metrics.get("auroc", 0))
        timeline.append({
            "run_id": run["run_id"],
            "timestamp": run.get("timestamp", ""),
            "auc": auc,
            "duration_sec": run.get("duration_sec", 0)
        })

    # Analyze trend
    if len(timeline) >= 2:
        first_auc = timeline[0]["auc"]
        last_auc = timeline[-1]["auc"]

        if last_auc > first_auc + 0.05:
            trend = "improving"
        elif last_auc < first_auc - 0.05:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "insufficient_data"

    # Generate insights
    insights = []

    if len(timeline) >= 2:
        # Find best model
        best = max(timeline, key=lambda x: x["auc"])
        insights.append({
            "type": "best_model",
            "message": f"Best model: {best['run_id']} (AUC: {best['auc']:.4f})"
        })

        # Check if improving
        if trend == "improving":
            improvement = timeline[-1]["auc"] - timeline[0]["auc"]
            insights.append({
                "type": "trend",
                "message": f"Improving trend (+{improvement:.3f} AUC)"
            })
        elif trend == "declining":
            decline = timeline[0]["auc"] - timeline[-1]["auc"]
            insights.append({
                "type": "warning",
                "message": f"Declining performance (-{decline:.3f} AUC)"
            })

        # Recent performance
        if len(timeline) >= 3:
            recent_drop = timeline[-2]["auc"] - timeline[-1]["auc"]
            if recent_drop > 0.02:
                insights.append({
                    "type": "warning",
                    "message": f"Recent drop: {timeline[-1]['run_id']} ({timeline[-1]['auc']:.4f})"
                })

    return {
        "timeline": timeline,
        "trend": trend,
        "insights": insights,
        "total_runs": len(timeline)
    }


def suggest_deletable_models(project: Dict[str, Any],
                            keep_best_n: int = 3,
                            min_auc: float = 0.75,
                            max_age_days: int = 7) -> Dict[str, Any]:
    """
    Suggest which models can be safely deleted

    Args:
        project: Project dict
        keep_best_n: Number of best models to keep
        min_auc: Minimum AUC to keep
        max_age_days: Maximum age in days to keep recent models

    Returns:
        {
            "delete": [...],
            "keep": [...],
            "archive": [...]
        }
    """
    runs = project.get("runs", [])

    if not runs:
        return {"delete": [], "keep": [], "archive": []}

    # Rank models
    ranked = rank_models(project)

    delete = []
    keep = []
    archive = []

    # Keep top N by score
    top_n_ids = [r["run_id"] for r in ranked[:keep_best_n]]

    for run_dict in ranked:
        run_id = run_dict["run_id"]
        auc = run_dict["auc"]

        # Find full run info
        run = next((r for r in runs if r["run_id"] == run_id), None)
        if not run:
            continue

        # Calculate age
        try:
            timestamp = datetime.fromisoformat(run.get("timestamp", ""))
            age_days = (datetime.now() - timestamp).days
        except (ValueError, TypeError):
            age_days = 999  # treat as very old if no timestamp

        # Decision logic
        if run_id in top_n_ids:
            # Always keep top N
            keep.append({
                "run_id": run_id,
                "reason": f"Top {keep_best_n} model (rank {ranked.index(run_dict) + 1})"
            })
        elif age_days <= max_age_days:
            # Keep recent models
            keep.append({
                "run_id": run_id,
                "reason": f"Recent ({age_days} days old)"
            })
        elif auc < min_auc:
            # Delete low-performing old models
            delete.append({
                "run_id": run_id,
                "reason": f"Low AUC ({auc:.3f} < {min_auc})",
                "auc": auc,
                "age_days": age_days
            })
        else:
            # Archive medium-performing old models
            archive.append({
                "run_id": run_id,
                "reason": f"Old but decent (AUC: {auc:.3f}, {age_days} days old)",
                "auc": auc,
                "age_days": age_days
            })

    return {
        "delete": delete,
        "keep": keep,
        "archive": archive
    }
