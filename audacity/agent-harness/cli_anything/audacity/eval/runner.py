"""Backward-compatible shim: delegates Audacity eval to the shared cli-anything-eval package.

Preserves the previous module API (discover_tasks(), run_eval(...), compare_baseline, ...)
while the generic runner now lives in cli_anything.eval.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from cli_anything.eval.baseline import compare_baseline, load_baseline
from cli_anything.eval.contracts import EvalContext, TaskSpec
from cli_anything.eval.runner import build_summary, default_output_dir
from cli_anything.eval.runner import discover_tasks as _discover_tasks
from cli_anything.eval.runner import run_eval as _run_eval

_TASKS_PACKAGE = "cli_anything.audacity.eval.tasks"
_DISPLAY_NAME = "Audacity"


def discover_tasks() -> List[TaskSpec]:
    return _discover_tasks(_TASKS_PACKAGE)


def run_eval(
    output_dir: Optional[str] = None,
    baseline_path: Optional[str] = None,
    update_baseline: bool = False,
) -> Dict[str, Any]:
    return _run_eval(
        _TASKS_PACKAGE,
        display_name=_DISPLAY_NAME,
        output_dir=output_dir,
        baseline_path=baseline_path,
        update_baseline=update_baseline,
    )


__all__ = [
    "discover_tasks", "run_eval", "compare_baseline", "load_baseline",
    "build_summary", "EvalContext", "TaskSpec", "default_output_dir",
]
