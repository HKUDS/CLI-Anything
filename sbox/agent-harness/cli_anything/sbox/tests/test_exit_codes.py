"""Verify one-shot CLI invocations exit non-zero on failure.

Reviewer feedback at HKUDS/CLI-Anything PR #251 flagged that handlers were
catching exceptions, printing via ``_output_error()``, then returning normally.
That made scripts and agents see failures as success. These tests pin the
contract: any failed command in one-shot mode must exit with code 1, while
the success path stays exit 0 and the REPL absorbs the exit so the loop
continues.

The subprocess tests use ``python -m cli_anything.sbox`` rather than the
installed ``cli-anything-sbox`` binary so the suite is portable across
environments where the launcher script may behave differently (e.g. Windows
+ Python 3.14 native launcher quirks).
"""

import json
import os
import subprocess
import sys

import pytest


CLI = [sys.executable, "-m", "cli_anything.sbox"]


def _run(args, cwd=None, env=None, timeout=30):
    """Run the CLI as a subprocess and return CompletedProcess (no check).

    ``stdin=DEVNULL`` is required on Windows + Python 3.14 + pytest where the
    parent test runner's stdin handle is not inheritable, otherwise Popen
    raises ``OSError: [WinError 6] The handle is invalid`` before the child
    even starts.
    """
    return subprocess.run(
        CLI + list(args),
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
    )


# ---------------------------------------------------------------------------
# One-shot exit codes - failure paths exit non-zero
# ---------------------------------------------------------------------------


class TestOneShotFailureExitsNonZero:
    """Failure exits 1 in both human and JSON modes, success exits 0."""

    def test_help_exits_zero(self):
        result = _run(["--help"])
        assert result.returncode == 0

    def test_scene_info_missing_file_exits_one_human_mode(self, tmp_path):
        """Missing file raises FileNotFoundError -> exit 1, error on stderr."""
        result = _run(["scene", "info", str(tmp_path / "missing.scene")])
        assert result.returncode == 1
        assert "Error" in result.stderr

    def test_scene_info_missing_file_exits_one_json_mode(self, tmp_path):
        """JSON mode emits {"error": ...} on stdout AND exits 1."""
        result = _run(["--json", "scene", "info", str(tmp_path / "missing.scene")])
        assert result.returncode == 1
        data = json.loads(result.stdout)
        assert "error" in data
        assert "missing.scene" in data["error"]

    def test_project_info_outside_project_exits_one(self, tmp_path):
        """Running project info from a directory with no .sbproj exits 1."""
        result = _run(["project", "info"], cwd=str(tmp_path))
        assert result.returncode == 1

    def test_project_info_explicit_missing_path_exits_one(self):
        """--project pointing at a missing path exits 1."""
        result = _run(
            ["--project", "/definitely/nonexistent/sbox/project", "project", "info"]
        )
        assert result.returncode == 1

    def test_localization_get_missing_key_exits_one(self, tmp_path):
        """Querying a missing key emits an error and exits 1."""
        loc_path = tmp_path / "en.json"
        loc_path.write_text(json.dumps({"existing": "value"}), encoding="utf-8")
        result = _run(
            ["localization", "get", str(loc_path), "--key", "missing_key"]
        )
        assert result.returncode == 1

    def test_scene_remove_object_missing_args_exits_one(self, tmp_path):
        """remove-object with no --name or --guid raises ClickException -> exit 1."""
        scene_path = tmp_path / "stub.scene"
        scene_path.write_text(json.dumps({"GameObjects": []}), encoding="utf-8")
        result = _run(["scene", "remove-object", str(scene_path)])
        assert result.returncode == 1

    def test_codegen_invalid_json_properties_exits_one(self):
        """Invalid JSON in --properties triggers JSONDecodeError -> exit 1."""
        result = _run([
            "codegen", "component", "--name", "Bad", "--properties", "not-json",
        ])
        assert result.returncode == 1

    def test_asset_compile_missing_sbox_exits_one(self, tmp_path):
        """asset compile with no s&box install (or missing file) exits 1.

        Either find_executable raises (no install) or the missing file path
        triggers FileNotFoundError. Both paths must exit 1.
        """
        result = _run(["asset", "compile", str(tmp_path / "nope.vmat")])
        assert result.returncode == 1

    def test_scene_list_missing_file_exits_one(self, tmp_path):
        """scene list on a missing file: bare except Exception path.

        Direct gate of the _output_error sys.exit fix - this handler does
        ``except Exception as exc: _output_error(ctx, str(exc))`` with no
        ClickException re-raise short-circuit, so without the fix the
        FileNotFoundError would print and exit 0.
        """
        result = _run(["scene", "list", str(tmp_path / "missing.scene")])
        assert result.returncode == 1

    def test_asset_info_corrupt_json_exits_one(self, tmp_path):
        """asset info on a corrupt .scene surfaces _parse_json_asset's error
        and exits 1, instead of burying the error in nested json_info."""
        bad_scene = tmp_path / "broken.scene"
        bad_scene.write_text("{not valid json", encoding="utf-8")
        result = _run(["asset", "info", str(bad_scene)])
        assert result.returncode == 1


class TestOneShotSuccessExitsZero:
    """Successful one-shot commands still exit 0 after the fix."""

    def test_project_new_exits_zero(self, tmp_path):
        result = _run([
            "--json", "project", "new",
            "--name", "exit_test",
            "--output-dir", str(tmp_path),
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["name"] == "exit_test"

    def test_project_info_on_valid_project_exits_zero(self, tmp_path):
        _run([
            "--json", "project", "new",
            "--name", "info_test",
            "--output-dir", str(tmp_path),
        ])
        result = _run([
            "--json", "--project", str(tmp_path), "project", "info",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["title"] == "info_test"


# ---------------------------------------------------------------------------
# Validation failure exits non-zero (project_validate ok=False)
# ---------------------------------------------------------------------------


class TestProjectValidateExitsNonZero:
    """project validate must exit 1 when ok=False so CI can gate on it."""

    def test_validate_clean_project_exits_zero(self, tmp_path):
        _run([
            "--json", "project", "new",
            "--name", "clean", "--output-dir", str(tmp_path),
        ])
        result = _run([
            "--json", "--project", str(tmp_path), "project", "validate",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True

    def test_validate_broken_ref_exits_one(self, tmp_path):
        """A scene that references a missing prefab makes ok=False -> exit 1."""
        _run([
            "--json", "project", "new",
            "--name", "brokenproj", "--output-dir", str(tmp_path),
        ])
        scene_path = tmp_path / "Assets" / "scenes" / "minimal.scene"
        scene_data = json.loads(scene_path.read_text(encoding="utf-8"))
        scene_data["GameObjects"].append({
            "__guid": "11111111-1111-1111-1111-111111111111",
            "Name": "BrokenRef",
            "Position": "0,0,0",
            "Tags": "",
            "Components": [{
                "__guid": "22222222-2222-2222-2222-222222222222",
                "__type": "Sandbox.PrefabScene",
                "PrefabSource": "missing/prefab/path.prefab",
            }],
        })
        scene_path.write_text(json.dumps(scene_data), encoding="utf-8")

        result = _run([
            "--json", "--project", str(tmp_path), "project", "validate",
        ])
        assert result.returncode == 1
        data = json.loads(result.stdout)
        assert data["ok"] is False
        assert data["issue_count"] >= 1


# ---------------------------------------------------------------------------
# REPL mode unit tests - _output_error must NOT sys.exit when repl=True
# ---------------------------------------------------------------------------


class TestAuditedFailurePaths:
    """Coverage for failure paths added during the silent-failure audit.

    These paths return dicts (not exceptions) on failure, so the standard
    ``except Exception`` path doesn't catch them. The audit added explicit
    success/error checks to surface them; these tests pin those checks.
    """

    def test_asset_compile_returns_success_false_exits_one(self, monkeypatch):
        """asset compile sees ``success=False`` from run_resource_compiler
        and exits 1 with the compiler's stderr in the error message."""
        from click.testing import CliRunner
        from cli_anything.sbox import sbox_cli
        from cli_anything.sbox.utils import sbox_backend

        def fake_compile(asset_path):
            return {
                "success": False,
                "return_code": 1,
                "stdout": "",
                "stderr": "mock compiler error: bad shader",
                "asset_path": asset_path,
                "compiler_path": "/fake/resourcecompiler",
            }

        monkeypatch.setattr(sbox_backend, "run_resource_compiler", fake_compile)

        runner = CliRunner()
        result = runner.invoke(sbox_cli.cli, ["asset", "compile", "/fake/path.vmat"])

        assert result.exit_code == 1
        # The error message includes both rc and stderr context.
        assert "Resource compilation failed" in result.output
        assert "mock compiler error" in result.output

    def test_server_info_version_error_exits_one(self, monkeypatch):
        """server info sees ``error`` field in get_sbox_version() and exits 1
        instead of reporting "version: unknown" with exit 0."""
        from click.testing import CliRunner
        from cli_anything.sbox import sbox_cli
        from cli_anything.sbox.utils import sbox_backend

        monkeypatch.setattr(sbox_backend, "find_executable", lambda name: "/fake/sbox-server.exe")
        monkeypatch.setattr(sbox_backend, "get_sbox_version", lambda: {
            "version": "unknown",
            "error": "mock: .version file unreadable",
        })

        runner = CliRunner()
        result = runner.invoke(sbox_cli.cli, ["server", "info"])

        assert result.exit_code == 1
        assert "Failed to read s&box version" in result.output


class TestReplModeAbsorbsExit:
    """Direct unit tests on _output_error to prove REPL mode doesn't exit.

    These tests don't go through the interactive REPL loop because the
    upstream-shared repl_skin uses unicode glyphs (e.g. ●) that fail to
    encode on Windows cp1252 console when stdin is piped, which is unrelated
    to the exit-code contract under test.
    """

    def test_output_error_does_not_exit_in_repl_mode(self):
        from click import Context
        from cli_anything.sbox import sbox_cli

        ctx = Context(sbox_cli.cli)
        ctx.obj = {"json": False, "repl": True}
        # Must NOT raise SystemExit when repl flag is set.
        sbox_cli._output_error(ctx, "test error")

    def test_output_error_exits_in_oneshot_mode(self):
        from click import Context
        from cli_anything.sbox import sbox_cli

        ctx = Context(sbox_cli.cli)
        ctx.obj = {"json": False, "repl": False}
        with pytest.raises(SystemExit) as exc_info:
            sbox_cli._output_error(ctx, "test error")
        assert exc_info.value.code == 1

    def test_output_error_exits_when_repl_key_missing(self):
        """Defaulting to one-shot when repl flag absent matches the contract."""
        from click import Context
        from cli_anything.sbox import sbox_cli

        ctx = Context(sbox_cli.cli)
        ctx.obj = {"json": False}  # no 'repl' key
        with pytest.raises(SystemExit) as exc_info:
            sbox_cli._output_error(ctx, "test error")
        assert exc_info.value.code == 1
