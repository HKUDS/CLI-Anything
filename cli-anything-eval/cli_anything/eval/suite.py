"""Cross-harness eval suite and leaderboard."""

from __future__ import annotations

import importlib
import pkgutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cli_anything.eval.io import safe_write_json
from cli_anything.eval.report import leaderboard_to_markdown
from cli_anything.eval.runner import iso_now, run_eval


def discover_harness_task_packages() -> List[Tuple[str, str]]:
    import cli_anything  # the PEP 420 namespace package
    found: List[Tuple[str, str]] = []
    for mod in pkgutil.iter_modules(cli_anything.__path__):
        if not mod.ispkg or mod.name == "eval":
            continue
        tasks_pkg = f"cli_anything.{mod.name}.eval.tasks"
        try:
            importlib.import_module(tasks_pkg)
        except Exception:
            continue
        found.append((mod.name, tasks_pkg))
    found.sort()
    return found


def run_suite(
    harnesses: Optional[List[str]] = None,
    *,
    output_dir: Optional[str] = None,
    now: Optional[str] = None,
) -> Dict[str, Any]:
    discovered = discover_harness_task_packages()
    if harnesses is not None:
        wanted = set(harnesses)
        discovered = [(sw, pkg) for sw, pkg in discovered if sw in wanted]

    out_dir = Path(output_dir) if output_dir else (Path("eval_results") / "suite")
    out_dir.mkdir(parents=True, exist_ok=True)
    started_at = now or iso_now()

    entries: List[Dict[str, Any]] = []
    for sw, pkg in discovered:
        started = time.time()
        res = run_eval(pkg, display_name=sw, output_dir=str(out_dir / sw), now=started_at)
        duration_ms = int((time.time() - started) * 1000)
        entries.append({"harness": sw, "summary": res["report"]["summary"],
                        "duration_ms": duration_ms})

    entries.sort(key=lambda e: e["summary"].get("success_rate", 0.0), reverse=True)
    suite = {"schema_version": 1, "started_at": started_at, "harnesses": entries}

    safe_write_json(out_dir / "leaderboard.json", suite, indent=2, default=str)
    (out_dir / "leaderboard.md").write_text(leaderboard_to_markdown(suite), encoding="utf-8")

    return {"suite": suite, "paths": {
        "output_dir": str(out_dir),
        "leaderboard_json": str(out_dir / "leaderboard.json"),
        "leaderboard_md": str(out_dir / "leaderboard.md"),
    }}
