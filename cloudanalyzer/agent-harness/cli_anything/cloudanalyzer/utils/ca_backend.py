"""CloudAnalyzer backend — direct Python import (no subprocess needed).

CloudAnalyzer is a Python package so we import and call its functions
directly rather than shelling out to a binary.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MISSING_CLOUDANALYZER_MSG = (
    "CloudAnalyzer is not installed or not importable. "
    "Install with: pip install cloudanalyzer"
)


def is_available() -> bool:
    """Check if CloudAnalyzer is importable."""
    try:
        import ca  # noqa: F401
        return True
    except ImportError:
        return False


def _ensure_ca() -> None:
    if not is_available():
        raise RuntimeError(MISSING_CLOUDANALYZER_MSG)


def get_version() -> str:
    """Return the installed CloudAnalyzer version."""
    try:
        from importlib.metadata import version
        return version("cloudanalyzer")
    except Exception:
        return "unknown"


def evaluate(source: str, reference: str, **kwargs: Any) -> dict:
    """Run point cloud evaluation."""
    _ensure_ca()
    from ca.evaluate import evaluate as _evaluate
    return _evaluate(source, reference, **kwargs)


def compare(source: str, target: str, method: str = "gicp", **kwargs: Any) -> dict:
    """Run point cloud comparison with optional registration."""
    _ensure_ca()
    from ca.compare import run_compare
    return run_compare(source, target, method=method, **kwargs)


def diff(source: str, target: str, threshold: float | None = None) -> dict:
    """Run quick distance diff."""
    _ensure_ca()
    from ca.diff import run_diff
    return run_diff(source, target, threshold=threshold)


def evaluate_trajectory(estimated: str, reference: str, **kwargs: Any) -> dict:
    """Evaluate a trajectory against reference."""
    _ensure_ca()
    from ca.trajectory import evaluate_trajectory as _eval_traj
    return _eval_traj(estimated, reference, **kwargs)


def evaluate_ground(
    est_ground: str, est_nonground: str,
    ref_ground: str, ref_nonground: str, **kwargs: Any,
) -> dict:
    """Evaluate ground segmentation quality."""
    _ensure_ca()
    from ca.ground_evaluate import evaluate_ground_segmentation
    return evaluate_ground_segmentation(
        est_ground, est_nonground, ref_ground, ref_nonground, **kwargs,
    )


def run_check_suite(config_path: str) -> dict:
    """Run config-driven QA checks."""
    _ensure_ca()
    from ca.core import load_check_suite, run_check_suite as _run
    suite = load_check_suite(config_path)
    return _run(suite)


def render_check_scaffold(profile: str = "integrated") -> str:
    """Generate a starter config YAML."""
    _ensure_ca()
    from ca.core import render_check_scaffold as _render
    result = _render(profile=profile)
    return result.yaml_text


def baseline_decision(candidate_path: str, history_paths: list[str]) -> dict:
    """Decide promote / keep / reject for a baseline."""
    _ensure_ca()
    from ca.core import summarize_baseline_evolution
    cp = Path(candidate_path)
    if not cp.exists():
        raise FileNotFoundError(f"Candidate file not found: {candidate_path}")
    try:
        candidate = json.loads(cp.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {candidate_path}: {e}") from e
    history = []
    for p in history_paths:
        hp = Path(p)
        if not hp.exists():
            raise FileNotFoundError(f"History file not found: {p}")
        try:
            history.append(json.loads(hp.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {p}: {e}") from e
    return summarize_baseline_evolution(candidate, history)


def baseline_save(summary_path: str, history_dir: str, **kwargs: Any) -> str:
    """Save a QA summary to the history directory."""
    _ensure_ca()
    from ca.baseline_history import save_baseline
    return save_baseline(summary_path, history_dir, **kwargs)


def baseline_list(history_dir: str) -> list[dict]:
    """List saved baselines."""
    _ensure_ca()
    from ca.baseline_history import list_baselines
    return list_baselines(history_dir)


def baseline_discover(history_dir: str) -> list[str]:
    """Discover history JSON paths."""
    _ensure_ca()
    from ca.baseline_history import discover_history
    return discover_history(history_dir)


def baseline_rotate(history_dir: str, keep: int = 10) -> list[str]:
    """Rotate old baselines."""
    _ensure_ca()
    from ca.baseline_history import rotate_history
    return rotate_history(history_dir, keep=keep)


def downsample(input_path: str, output_path: str, voxel_size: float) -> dict:
    """Voxel grid downsampling."""
    _ensure_ca()
    from ca.downsample import downsample as _ds
    return _ds(input_path, voxel_size, output_path)


def split(input_path: str, output_dir: str, grid_size: float, axis: str = "xy") -> dict:
    """Split a point cloud into grid tiles."""
    _ensure_ca()
    from ca.split import split as _split
    return _split(input_path, output_dir, grid_size, axis=axis)


def info(path: str) -> dict:
    """Get point cloud metadata."""
    _ensure_ca()
    from ca.info import get_info
    return get_info(path)


def batch_evaluate(directory: str, reference: str, **kwargs: Any) -> dict:
    """Evaluate every point cloud in a directory against one reference."""
    _ensure_ca()
    from ca.batch import batch_evaluate as _be
    return _be(directory, reference, **kwargs)


def run_pipeline(
    input_path: str, reference: str, output: str, **kwargs: Any,
) -> dict:
    """Filter, downsample, evaluate in one pipeline."""
    _ensure_ca()
    from ca.pipeline import run_pipeline as _rp
    return _rp(input_path, reference, output, **kwargs)


def trajectory_batch_evaluate(
    directory: str, reference_dir: str, **kwargs: Any,
) -> dict:
    """Batch trajectory evaluation."""
    _ensure_ca()
    from ca.batch import trajectory_batch_evaluate as _tbe
    return _tbe(directory, reference_dir, **kwargs)


def evaluate_run(
    map_path: str,
    map_reference_path: str,
    trajectory_path: str,
    trajectory_reference_path: str,
    **kwargs: Any,
) -> dict:
    """Evaluate one map and one trajectory together."""
    _ensure_ca()
    from ca.run_evaluate import evaluate_run as _er
    return _er(
        map_path,
        map_reference_path,
        trajectory_path,
        trajectory_reference_path,
        **kwargs,
    )


def random_sample(input_path: str, output_path: str, num_points: int) -> dict:
    """Random point sampling."""
    _ensure_ca()
    from ca.sample import random_sample as _rs
    return _rs(input_path, output_path, num_points)


def filter_outliers(
    input_path: str, output_path: str, **kwargs: Any,
) -> dict:
    """Statistical outlier removal."""
    _ensure_ca()
    from ca.filter import filter_outliers as _fo
    return _fo(input_path, output_path, **kwargs)


def merge(paths: list[str], output: str) -> dict:
    """Merge point clouds."""
    _ensure_ca()
    from ca.merge import merge as _m
    return _m(paths, output)


def convert(input_path: str, output_path: str) -> dict:
    """Convert between point cloud formats."""
    _ensure_ca()
    from ca.convert import convert as _c
    return _c(input_path, output_path)


def view_point_cloud(path: str) -> None:
    """Open the interactive point cloud viewer (single file)."""
    _ensure_ca()
    from ca.view import view as _view
    _view([path])


def web_serve(
    source: str,
    reference: str | None,
    *,
    port: int = 8080,
    heatmap: bool = False,
    trajectory: str | None = None,
    trajectory_reference: str | None = None,
    open_browser: bool = True,
) -> None:
    """Start the CloudAnalyzer web viewer."""
    _ensure_ca()
    from ca.web import serve
    paths: list[str] = [source] if not reference else [source, reference]
    serve(
        paths,
        port=port,
        open_browser=open_browser,
        heatmap=heatmap,
        trajectory_path=trajectory,
        trajectory_reference_path=trajectory_reference,
    )


def web_export_bundle(
    source: str,
    reference: str | None,
    output_dir: str,
    *,
    heatmap: bool = False,
    trajectory: str | None = None,
    trajectory_reference: str | None = None,
) -> dict:
    """Write a static HTML viewer bundle."""
    _ensure_ca()
    from ca.web import export_static_bundle
    paths: list[str] = [source] if not reference else [source, reference]
    return export_static_bundle(
        paths,
        output_dir=output_dir,
        heatmap=heatmap,
        trajectory_path=trajectory,
        trajectory_reference_path=trajectory_reference,
    )
