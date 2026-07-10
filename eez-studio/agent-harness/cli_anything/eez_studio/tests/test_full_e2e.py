import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from cli_anything.eez_studio.core import project as project_mod


def _resolve_cli(name):
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = "cli_anything.eez_studio.eez_studio_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


class TestCLISubprocessE2E:
    CLI_BASE = _resolve_cli("cli-anything-eez-studio")

    def _run(self, args, check=True):
        result = subprocess.run(self.CLI_BASE + args, capture_output=True, text=True)
        if check and result.returncode != 0:
            raise AssertionError(
                f"command failed: {self.CLI_BASE + args}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        return result

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "EEZ Studio CLI harness" in result.stdout

    def test_native_project_scpi_workflow(self, tmp_path):
        project_path = tmp_path / "workflow.eez-project"
        result = self._run(["--json", "project", "new", "-o", str(project_path), "--name", "Workflow"])
        data = json.loads(result.stdout)
        assert data["project_name"] == "Workflow"
        self._run(["--project", str(project_path), "lvgl", "add-label", "--text", "Ready"])
        self._run(["--project", str(project_path), "lvgl", "add-button", "--text", "Run"])
        self._run(["--project", str(project_path), "scpi", "subsystem-add", "SOURCE"])
        self._run(["--project", str(project_path), "scpi", "command-add", "SOURCE", ":VOLTage?"])
        loaded = project_mod.load_project(project_path)
        info = project_mod.project_info(loaded)
        assert info["widget_count"] >= 3
        assert info["scpi_commands"] == 1
        print(f"\n  EEZ project: {project_path} ({project_path.stat().st_size:,} bytes)")

    def test_backend_status_json(self):
        result = self._run(["--json", "backend", "status"])
        data = json.loads(result.stdout)
        assert "available" in data

    def test_backend_inspect_reports_unavailable_without_source(self, tmp_path, monkeypatch):
        monkeypatch.delenv("EEZ_STUDIO_SOURCE", raising=False)
        project_path = tmp_path / "backend-unavailable.eez-project"
        self._run(["--json", "project", "new", "-o", str(project_path), "--name", "NoBackend"])
        result = self._run(
            ["--json", "--project", str(project_path), "lvgl", "backend-inspect"],
            check=False,
        )
        assert result.returncode != 0
        data = json.loads(result.stderr)
        assert data["type"] == "RuntimeError"
        assert "EEZ Studio backend is not available" in data["error"]
        assert "EEZ_STUDIO_SOURCE" in data["error"]

    @pytest.mark.skipif(
        os.environ.get("EEZ_STUDIO_RUN_LIVE_BACKEND") != "1",
        reason="set EEZ_STUDIO_RUN_LIVE_BACKEND=1 with a built EEZ_STUDIO_SOURCE to run live backend tests",
    )
    def test_real_backend_inspect_required(self, tmp_path):
        project_path = tmp_path / "backend.eez-project"
        self._run(["--json", "project", "new", "-o", str(project_path), "--name", "Backend"])
        self._run(["--project", str(project_path), "lvgl", "ensure-destination"])
        result = self._run(
            ["--json", "--project", str(project_path), "lvgl", "backend-inspect"],
            check=False,
        )
        assert result.returncode == 0, (
            "EEZ Studio backend is required for this E2E test.\n"
            "Set EEZ_STUDIO_SOURCE to a built https://github.com/eez-open/studio checkout.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["projectInfo"]["displayWidth"] == 800
