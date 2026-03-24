import os
import sys
import json
import subprocess
import pytest
from unittest.mock import patch

def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev."""
    import shutil
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    
    # Correct module path for freecad
    module = "cli_anything.freecad.freecad_cli"
    return [sys.executable, "-m", module]

class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-freecad")

    def _run(self, args, check=True):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True,
            check=check,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "FreeCAD CLI" in result.stdout

    def test_project_new_json(self, tmp_path):
        out = tmp_path / "test.json"
        result = self._run(["--json", "project", "new", "-o", str(out)])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "created"
        assert os.path.exists(out)

    @patch("cli_anything.freecad.utils.freecad_backend.execute_freecad_python")
    def test_full_workflow(self, mock_execute, tmp_path):
        mock_execute.return_value = {"success": True, "stdout": "Mocked", "stderr": ""}
        
        project = tmp_path / "workflow.json"
        output_step = tmp_path / "model.step"
        
        # 1. Create project
        self._run(["project", "new", "-o", str(project)])
        
        # 2. Add sketch
        self._run(["--project", str(project), "sketch", "add-circle", "--radius", "10"])
        
        # 3. Pad
        self._run(["--project", str(project), "part", "pad", "--length", "5"])
        
        # 4. Export
        result = self._run(["--project", str(project), "export", "render", "-o", str(output_step)])
        assert result.returncode == 0
        assert "Exported project" in result.stdout
