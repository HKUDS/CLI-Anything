import json
import os
import shutil
import subprocess
import sys

from cli_anything.dify_workflow.utils.dify_workflow_backend import require_dify_workflow_command


def _decode_output(data: bytes | None) -> str:
    if not data:
        return ""
    return data.decode("utf-8", errors="replace")


def _require_working_upstream() -> None:
    command = require_dify_workflow_command()
    result = subprocess.run(
        command + ["--help"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = _decode_output(result.stderr)
        stdout = _decode_output(result.stdout)
        raise RuntimeError(
            "upstream dify-workflow CLI is required for wrapper E2E tests and must respond to --help.\n"
            f"stdout: {stdout}\n"
            f"stderr: {stderr}"
        )


def _resolve_cli(name: str, module: str) -> list[str]:
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    return [sys.executable, "-m", module]


class TestWrapperE2E:
    CLI_BASE = _resolve_cli("cli-anything-dify-workflow", "cli_anything.dify_workflow")

    @classmethod
    def setup_class(cls):
        _require_working_upstream()

    def _run(self, args, check=True):
        result = subprocess.run(self.CLI_BASE + args, capture_output=True, check=False)
        stdout = _decode_output(result.stdout)
        stderr = _decode_output(result.stderr)
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, result.args, output=stdout, stderr=stderr)
        result.stdout = stdout
        result.stderr = stderr
        return result

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "create" in result.stdout

    def test_create_and_validate_workflow(self, tmp_path):
        workflow_path = tmp_path / "workflow.yaml"

        result = self._run(["create", "-o", str(workflow_path), "--template", "llm", "-j"])
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "created"

        result = self._run(["validate", str(workflow_path), "-j"])
        assert result.returncode == 0, result.stderr
        report = json.loads(result.stdout)
        assert report["valid"] is True

    def test_inspect_json(self, tmp_path):
        workflow_path = tmp_path / "workflow.yaml"
        self._run(["create", "-o", str(workflow_path)], check=True)

        result = self._run(["inspect", str(workflow_path), "-j"])
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip().startswith("{")
