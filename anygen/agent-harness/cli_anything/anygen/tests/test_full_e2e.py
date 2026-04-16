"""E2E tests for AnyGen CLI — require ANYGEN_API_KEY for real API calls.

Run with:
    ANYGEN_API_KEY=sk-xxx python3 -m pytest cli_anything/anygen/tests/test_full_e2e.py -v -s
    CLI_ANYTHING_FORCE_INSTALLED=1 ANYGEN_API_KEY=sk-xxx python3 -m pytest ... -v -s
"""

import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

from cli_anything.anygen.utils.anygen_backend import get_api_key, DOWNLOADABLE_OPERATIONS
from cli_anything.anygen.core.task import create_task, poll_task, download_file, run_full_workflow
from cli_anything.anygen.core.export import verify_file


API_KEY = get_api_key()
SKIP_REASON = "ANYGEN_API_KEY not set — skipping E2E tests"
requires_api_key = pytest.mark.skipif(not API_KEY, reason=SKIP_REASON)


def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev."""
    import shutil
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = "cli_anything.anygen.anygen_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


# ── Slide Workflow ────────────────────────────────────────────────

@requires_api_key
class TestSlideWorkflow:
    def test_create_slide_task(self):
        result = create_task(API_KEY, "slide", "Create a 3-slide demo about Python")
        assert "task_id" in result
        assert result["task_id"].startswith("task_") or len(result["task_id"]) > 0
        print(f"\n  Task ID: {result['task_id']}")
        if result.get("task_url"):
            print(f"  Task URL: {result['task_url']}")

    def test_full_slide_workflow(self, tmp_path):
        result = run_full_workflow(
            API_KEY, "slide",
            "Create a brief 3-slide presentation about CLI tools",
            output_dir=str(tmp_path),
            slide_count=3,
        )
        assert result["status"] == "completed"
        assert result.get("local_path")

        local = result["local_path"]
        assert os.path.exists(local)
        size = os.path.getsize(local)
        assert size > 1000, f"File suspiciously small: {size} bytes"

        v = verify_file(local)
        assert v["valid"], f"File verification failed: {v['details']}"
        print(f"\n  PPTX: {local} ({size:,} bytes)")
        print(f"  Format: {v['format']} — {v['details']}")


# ── Doc Workflow ──────────────────────────────────────────────────

@requires_api_key
class TestDocWorkflow:
    def test_create_doc_task(self):
        result = create_task(API_KEY, "doc", "Write a one-page summary about REST APIs")
        assert "task_id" in result
        print(f"\n  Task ID: {result['task_id']}")

    def test_full_doc_workflow(self, tmp_path):
        result = run_full_workflow(
            API_KEY, "doc",
            "Write a brief technical note about HTTP status codes",
            output_dir=str(tmp_path),
        )
        assert result["status"] == "completed"
        assert result.get("local_path")

        local = result["local_path"]
        assert os.path.exists(local)
        size = os.path.getsize(local)
        assert size > 1000, f"File suspiciously small: {size} bytes"

        v = verify_file(local)
        assert v["valid"], f"File verification failed: {v['details']}"
        print(f"\n  DOCX: {local} ({size:,} bytes)")
        print(f"  Format: {v['format']} — {v['details']}")


# ── CLI Subprocess ────────────────────────────────────────────────

class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-anygen")

    def _run(self, args, check=True):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True,
            check=check,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "AnyGen" in result.stdout

    def test_json_config_path(self):
        result = self._run(["--json", "config", "path"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "path" in data

    def test_json_task_list(self):
        result = self._run(["--json", "task", "list"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    def test_session_status(self):
        result = self._run(["--json", "session", "status"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "history_count" in data

    @requires_api_key
    def test_create_slide_subprocess(self):
        result = self._run([
            "--json", "--api-key", API_KEY,
            "task", "create",
            "--operation", "slide",
            "--prompt", "Brief demo about testing",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "task_id" in data
        print(f"\n  Subprocess task ID: {data['task_id']}")

    @requires_api_key
    def test_full_workflow_subprocess(self, tmp_path):
        result = self._run([
            "--json", "--api-key", API_KEY,
            "task", "run",
            "--operation", "slide",
            "--prompt", "A 3-slide overview of Python testing",
            "--output", str(tmp_path),
            "--slide-count", "3",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data.get("local_path") or data.get("task_url")
        if data.get("local_path"):
            assert os.path.exists(data["local_path"])
            v = verify_file(data["local_path"])
            print(f"\n  Subprocess file: {data['local_path']}")
            print(f"  Valid: {v['valid']} — {v['details']}")
