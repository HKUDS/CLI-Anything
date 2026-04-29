"""End-to-end integration tests for the OpenClaw Macro System.

Tests the full lifecycle: macro discovery → runtime execution → CLI subprocess.
Uses real file I/O and subprocess calls (echo, cat, etc.) as the "target apps".
"""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest


# ── CLI resolver (same pattern as in HARNESS.md) ─────────────────────────────

def _resolve_cli(name: str) -> list[str]:
    """Resolve installed CLI command; falls back to python -m for dev."""
    import shutil
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = "cli_anything.openclaw.openclaw_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", "cli_anything.openclaw"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def write_macro(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / f"{name}.yaml"
    p.write_text(content, encoding="utf-8")
    return p


# ── E2E: File transform workflow ──────────────────────────────────────────────

class TestFileTransformE2E:
    def test_json_set_and_verify(self, tmp_path):
        """Write a JSON file, transform it, verify the result."""
        from cli_anything.openclaw.core.macro_model import MacroDefinition, MacroStep, MacroCondition, MacroOutput
        from cli_anything.openclaw.core.registry import MacroRegistry
        from cli_anything.openclaw.core.runtime import MacroRuntime

        json_file = tmp_path / "settings.json"
        json_file.write_text('{"version": 1}', encoding="utf-8")

        yaml_content = textwrap.dedent(f"""\
            name: set_json_key
            parameters:
              file:
                type: string
                required: true
              key:
                type: string
                required: true
              value:
                type: string
                required: true
            preconditions:
              - file_exists: ${{file}}
            steps:
              - id: transform
                backend: file_transform
                action: json_set
                params:
                  input_file: ${{file}}
                  output_file: ${{file}}
                  path: ${{key}}
                  value: ${{value}}
            postconditions:
              - file_exists: ${{file}}
            outputs:
              - name: modified_file
                path: ${{file}}
        """)
        write_macro(tmp_path, "set_json_key", yaml_content)

        reg = MacroRegistry(str(tmp_path))
        rt = MacroRuntime(registry=reg)
        result = rt.execute("set_json_key", {
            "file": str(json_file),
            "key": "config.theme",
            "value": "dark",
        })

        assert result.success, f"Failed: {result.error}"
        data = json.loads(json_file.read_text())
        assert data["config"]["theme"] == "dark"
        print(f"\n  Modified JSON: {json_file} → {json.dumps(data)}")


class TestNativeAPIE2E:
    def test_run_real_command_and_capture(self, tmp_path):
        """Run a real shell command and capture its stdout."""
        from cli_anything.openclaw.core.macro_model import MacroDefinition
        from cli_anything.openclaw.core.registry import MacroRegistry
        from cli_anything.openclaw.core.runtime import MacroRuntime

        output_file = tmp_path / "result.txt"
        yaml_content = textwrap.dedent(f"""\
            name: capture_date
            parameters:
              output:
                type: string
                required: true
            steps:
              - id: run_date
                backend: native_api
                action: run_command
                params:
                  command: [date, "+%Y-%m-%d"]
                  capture_stdout: true
            postconditions: []
            outputs:
              - name: output_file
                path: ${{output}}
        """)
        write_macro(tmp_path, "capture_date", yaml_content)

        reg = MacroRegistry(str(tmp_path))
        rt = MacroRuntime(registry=reg)
        result = rt.execute("capture_date", {"output": str(output_file)})

        assert result.success, f"Failed: {result.error}"
        # Step output contains stdout
        steps_output = result.output.get("_steps", [])
        assert steps_output, "Expected _steps in output"
        stdout = steps_output[0].get("stdout", "")
        # Date format YYYY-MM-DD
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2}", stdout.strip()), f"Unexpected stdout: {stdout!r}"
        print(f"\n  Captured date: {stdout.strip()}")

    def test_step_failure_aborts_macro(self, tmp_path):
        """A failing step with on_failure=fail should abort the macro."""
        from cli_anything.openclaw.core.registry import MacroRegistry
        from cli_anything.openclaw.core.runtime import MacroRuntime

        yaml_content = textwrap.dedent("""\
            name: fail_abort
            steps:
              - id: bad
                backend: native_api
                action: run_command
                params:
                  command: [false]
                on_failure: fail
              - id: good
                backend: native_api
                action: run_command
                params:
                  command: [echo, should_not_run]
        """)
        write_macro(tmp_path, "fail_abort", yaml_content)
        reg = MacroRegistry(str(tmp_path))
        rt = MacroRuntime(registry=reg)
        result = rt.execute("fail_abort", {})

        assert not result.success
        # Only the first step should have run
        assert result.telemetry["steps_run"] == 1
        print(f"\n  Correctly aborted after first step: {result.error}")

    def test_step_failure_skip_continues(self, tmp_path):
        """A failing step with on_failure=skip should allow the macro to continue."""
        from cli_anything.openclaw.core.registry import MacroRegistry
        from cli_anything.openclaw.core.runtime import MacroRuntime

        yaml_content = textwrap.dedent("""\
            name: fail_skip
            steps:
              - id: bad
                backend: native_api
                action: run_command
                params:
                  command: [false]
                on_failure: skip
              - id: good
                backend: native_api
                action: run_command
                params:
                  command: [echo, still_ran]
        """)
        write_macro(tmp_path, "fail_skip", yaml_content)
        reg = MacroRegistry(str(tmp_path))
        rt = MacroRuntime(registry=reg)
        result = rt.execute("fail_skip", {})

        assert result.success
        assert result.telemetry["steps_run"] == 2
        print(f"\n  Macro succeeded despite skipped step")


class TestPostconditionE2E:
    def test_postcondition_file_exists_passes(self, tmp_path):
        from cli_anything.openclaw.core.registry import MacroRegistry
        from cli_anything.openclaw.core.runtime import MacroRuntime

        output_file = tmp_path / "output.txt"
        yaml_content = textwrap.dedent(f"""\
            name: write_and_verify
            parameters:
              output:
                type: string
                required: true
            steps:
              - id: write
                backend: file_transform
                action: text_replace
                params:
                  input_file: /dev/null
                  output_file: ${{output}}
                  find: ""
                  replace: ""
            postconditions:
              - file_exists: ${{output}}
        """)
        write_macro(tmp_path, "write_and_verify", yaml_content)
        reg = MacroRegistry(str(tmp_path))
        rt = MacroRuntime(registry=reg)
        result = rt.execute("write_and_verify", {"output": str(output_file)})
        assert result.success, f"Failed: {result.error}"
        print(f"\n  Output file: {output_file} ({output_file.stat().st_size} bytes)")

    def test_postcondition_file_size_gt(self, tmp_path):
        from cli_anything.openclaw.core.registry import MacroRegistry
        from cli_anything.openclaw.core.runtime import MacroRuntime

        output_file = tmp_path / "output.txt"
        output_file.write_text("x" * 200, encoding="utf-8")

        yaml_content = textwrap.dedent(f"""\
            name: size_check
            parameters:
              output:
                type: string
                required: true
            steps:
              - id: noop
                backend: native_api
                action: run_command
                params:
                  command: [echo, noop]
            postconditions:
              - file_size_gt:
                  - ${{output}}
                  - 100
        """)
        write_macro(tmp_path, "size_check", yaml_content)
        reg = MacroRegistry(str(tmp_path))
        rt = MacroRuntime(registry=reg)
        result = rt.execute("size_check", {"output": str(output_file)})
        assert result.success, f"Failed: {result.error}"
        print(f"\n  File size: {output_file.stat().st_size} bytes")


# ── CLI subprocess tests ──────────────────────────────────────────────────────

class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-openclaw")

    def _run(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            check=check,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "macro" in result.stdout.lower()

    def test_macro_list_json(self):
        result = self._run(["--json", "macro", "list"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        print(f"\n  macros: {[m['name'] for m in data]}")

    def test_macro_info_json(self):
        # Info on a bundled example macro
        result = self._run(["--json", "macro", "info", "export_file"])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["name"] == "export_file"
        assert "parameters" in data
        print(f"\n  Macro info: {data['name']} v{data['version']}")

    def test_macro_validate_all(self):
        result = self._run(["--json", "macro", "validate"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict)
        for name, info in data.items():
            assert info["valid"], f"Macro {name} failed: {info['errors']}"
        print(f"\n  Validated {len(data)} macros, all valid")

    def test_macro_dry_run_json(self):
        result = self._run([
            "--json", "--dry-run",
            "macro", "run", "export_file",
            "--param", "output=/tmp/test_openclaw_e2e.txt",
        ])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert data["telemetry"]["dry_run"] is True
        print(f"\n  Dry run result: {data['success']}")

    def test_backends_json(self):
        result = self._run(["--json", "backends"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "native_api" in data
        assert "file_transform" in data
        print(f"\n  Backends: {list(data.keys())}")

    def test_session_status_json(self):
        result = self._run(["--json", "session", "status"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "session_id" in data
        print(f"\n  Session: {data['session_id']}")

    def test_macro_run_json_transform_workflow(self, tmp_path):
        """Full E2E: create a JSON file, run transform_json macro, verify output."""
        json_file = tmp_path / "data.json"
        json_file.write_text('{"name": "test"}', encoding="utf-8")

        result = self._run([
            "--json",
            "macro", "run", "transform_json",
            "--param", f"file={json_file}",
            "--param", "key=config.mode",
            "--param", "value=production",
        ])
        print(f"\n  CLI stdout: {result.stdout[:200]}")
        print(f"  CLI stderr: {result.stderr[:200]}")

        assert result.returncode == 0, f"CLI failed:\n{result.stderr}"
        data = json.loads(result.stdout)
        assert data["success"] is True, f"Macro failed: {data.get('error')}"

        # Verify file was actually modified
        modified = json.loads(json_file.read_text())
        assert modified["config"]["mode"] == "production"
        print(f"\n  Modified JSON: {modified}")
        print(f"  File: {json_file} ({json_file.stat().st_size} bytes)")

    def test_unknown_macro_returns_error_json(self):
        result = self._run(
            ["--json", "macro", "run", "nonexistent_macro_xyz"],
            check=False,
        )
        assert result.returncode != 0
        data = json.loads(result.stdout)
        assert data["success"] is False
        assert "error" in data
        print(f"\n  Error: {data['error']}")
