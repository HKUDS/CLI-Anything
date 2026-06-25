"""cli-anything-eval: shared eval/benchmark framework for CLI-Anything harnesses."""

from cli_anything.eval.baseline import compare_baseline, load_baseline
from cli_anything.eval.contracts import EvalContext, Status, TaskSpec
from cli_anything.eval.runner import build_summary, discover_tasks, run_eval, run_task
from cli_anything.eval.suite import discover_harness_task_packages, run_suite

__all__ = [
    "EvalContext", "Status", "TaskSpec",
    "run_eval", "run_task", "discover_tasks", "build_summary",
    "compare_baseline", "load_baseline",
    "run_suite", "discover_harness_task_packages",
]
__version__ = "0.1.0"
