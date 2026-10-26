import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from cli_anything.copt.core.backend import CoptError, _invoke, find_copt


MODEL = Path(__file__).parent / "data" / "sample.lp"
MIP = Path(__file__).parent / "data" / "sample_mip.lp"
INFEASIBLE = Path(__file__).parent / "data" / "infeasible.lp"


def _resolve_cli(name):
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if os.environ.get("CLI_ANYTHING_FORCE_INSTALLED") == "1":
        raise RuntimeError(f"{name} not found in PATH; install with pip install -e .")
    return [sys.executable, "-m", "cli_anything.copt.copt_cli"]


class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-copt")

    def _run(self, args):
        result = subprocess.run(self.CLI_BASE + args, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        return result

    def test_help(self):
        assert "solve" in self._run(["--help"]).stdout

    def test_doctor(self):
        data = json.loads(self._run(["--json", "doctor"]).stdout)
        assert Path(data["binary"]).is_file()
        assert "Cardinal Optimizer" in data["version"]

    def test_inspect_real_model(self):
        data = json.loads(self._run(["--json", "model", "inspect", str(MODEL)]).stdout)
        assert data["attributes"]["Rows"] == 2
        assert data["attributes"]["Cols"] == 2

    def test_solve_and_export_json_solution(self, tmp_path):
        output = tmp_path / "sample solution.json"
        data = json.loads(self._run([
            "--json", "solve", str(MODEL), "--solution", str(output), "--time-limit", "10"
        ]).stdout)
        assert data["status"] == "optimal"
        assert abs(data["objective"] - 2.2) < 1e-6
        assert data["output"] == str(output)
        assert json.loads(output.read_text())
        print(f"\n  JSON solution: {output} ({output.stat().st_size:,} bytes)")

    def test_convert_to_mps(self, tmp_path):
        output = tmp_path / "sample converted.mps"
        data = json.loads(self._run([
            "--json", "model", "convert", str(MODEL), "--output", str(output)
        ]).stdout)
        assert data["output"] == str(output)
        assert "ROWS" in output.read_text() and "ENDATA" in output.read_text()
        print(f"\n  MPS model: {output} ({output.stat().st_size:,} bytes)")

    def test_solve_mip(self):
        data = json.loads(self._run(["--json", "solve", str(MIP)]).stdout)
        assert data["attributes"]["IsMIP"] == 1
        assert data["status"] == "optimal"
        assert abs(data["objective"] - 2.0) < 1e-6

    def test_infeasible_solve_has_no_objective(self):
        data = json.loads(self._run(["--json", "solve", str(INFEASIBLE)]).stdout)
        assert data["status"] == "infeasible"
        assert data["objective"] is None

    def test_iis_export(self, tmp_path):
        output = tmp_path / "conflict.iis"
        data = json.loads(self._run([
            "--json", "diagnose", "iis", str(INFEASIBLE), "--output", str(output)
        ]).stdout)
        assert data["attributes"]["IISRows"] == 2
        assert output.is_file() and output.stat().st_size > 0
        print(f"\n  IIS: {output} ({output.stat().st_size:,} bytes)")

    def test_terminal_json_has_no_copt_prompt_echo(self):
        result = subprocess.run(
            ["script", "-q", "/dev/null", *self.CLI_BASE,
             "--json", "model", "inspect", str(MODEL)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "COPT>" not in result.stdout
        data = json.loads(result.stdout[result.stdout.index("{"):])
        assert data["attributes"]["Rows"] == 2


def test_copt_unknown_parameter_is_an_error():
    with pytest.raises(CoptError, match="Unknown COPT parameter"):
        _invoke(find_copt(), "set mipgap 0.1; quit")
