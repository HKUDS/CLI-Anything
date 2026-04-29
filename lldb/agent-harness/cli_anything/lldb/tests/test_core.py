"""
Unit tests for LLDB CLI harness modules.

These tests are mock-based and do not require LLDB installation.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner


def _resolve_cli(name: str):
    """Resolve installed CLI command; fallback to module invocation for dev."""
    import shutil

    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    return [sys.executable, "-m", "cli_anything.lldb.lldb_cli"]


class TestOutputUtils:
    def test_output_json(self):
        from cli_anything.lldb.utils.output import output_json
        import io

        buf = io.StringIO()
        output_json({"ok": True, "value": 42}, file=buf)
        data = json.loads(buf.getvalue())
        assert data["ok"] is True
        assert data["value"] == 42

    def test_output_table(self):
        from cli_anything.lldb.utils.output import output_table
        import io

        buf = io.StringIO()
        output_table([["main", 1], ["worker", 2]], ["thread", "id"], file=buf)
        text = buf.getvalue()
        assert "main" in text
        assert "worker" in text

    def test_output_table_empty(self):
        from cli_anything.lldb.utils.output import output_table
        import io

        buf = io.StringIO()
        output_table([], ["col"], file=buf)
        assert "(no data)" in buf.getvalue()


class TestErrorUtils:
    def test_handle_error(self):
        from cli_anything.lldb.utils.errors import handle_error

        result = handle_error(ValueError("bad"))
        assert result["error"] == "bad"
        assert result["type"] == "ValueError"
        assert "traceback" not in result

    def test_handle_error_debug(self):
        from cli_anything.lldb.utils.errors import handle_error

        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            result = handle_error(exc, debug=True)
        assert "traceback" in result
        assert "boom" in result["traceback"]


class TestCoreHelpers:
    def test_breakpoints_wrapper(self):
        from cli_anything.lldb.core.breakpoints import set_breakpoint

        session = MagicMock()
        session.breakpoint_set.return_value = {"id": 1}
        data = set_breakpoint(session, function="main")
        assert data["id"] == 1
        session.breakpoint_set.assert_called_once()

    def test_inspect_wrapper(self):
        from cli_anything.lldb.core.inspect import evaluate_expression

        session = MagicMock()
        session.evaluate.return_value = {"expression": "1+1", "value": "2"}
        data = evaluate_expression(session, "1+1")
        assert data["value"] == "2"

    def test_threads_wrapper(self):
        from cli_anything.lldb.core.threads import list_threads

        session = MagicMock()
        session.threads.return_value = {"threads": []}
        data = list_threads(session)
        assert "threads" in data


class TestCLIHelp:
    def test_main_help(self):
        from cli_anything.lldb.lldb_cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "LLDB CLI" in result.output

    def test_groups_help(self):
        from cli_anything.lldb.lldb_cli import cli

        runner = CliRunner()
        for group in ("target", "process", "breakpoint", "thread", "frame", "step", "memory", "core", "session"):
            result = runner.invoke(cli, [group, "--help"])
            assert result.exit_code == 0, f"{group} help failed"


class TestCLIJsonErrors:
    @patch("cli_anything.lldb.lldb_cli._get_session")
    def test_target_info_no_target_json(self, mock_get_session):
        from cli_anything.lldb.lldb_cli import cli

        fake_session = MagicMock()
        fake_session.target = None
        mock_get_session.return_value = fake_session

        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "target", "info"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "error" in data

    @patch("cli_anything.lldb.lldb_cli._get_session")
    def test_thread_info_no_selected_thread_json(self, mock_get_session):
        from cli_anything.lldb.lldb_cli import cli

        fake_session = MagicMock()
        fake_session.session_status.return_value = {"has_target": True, "has_process": True}
        fake_session.threads.return_value = {"threads": [{"id": 1, "selected": False}]}
        mock_get_session.return_value = fake_session

        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "thread", "info"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error"] == "No selected thread"

    @patch("cli_anything.lldb.lldb_cli._get_session")
    def test_process_info_uses_public_session_api(self, mock_get_session):
        from cli_anything.lldb.lldb_cli import cli

        fake_session = MagicMock()
        fake_session.session_status.return_value = {"has_target": True, "has_process": True}
        fake_session.process_info.return_value = {"pid": 1234, "state": "stopped", "num_threads": 1}
        fake_session._process_info.side_effect = AssertionError("private API should not be used")
        mock_get_session.return_value = fake_session

        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "process", "info"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["pid"] == 1234
        fake_session.process_info.assert_called_once_with()

    @patch("cli_anything.lldb.lldb_cli._get_session")
    def test_process_info_no_process_json(self, mock_get_session):
        from cli_anything.lldb.lldb_cli import cli

        fake_session = MagicMock()
        fake_session.target = object()
        fake_session.process = None
        mock_get_session.return_value = fake_session

        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "process", "info"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "error" in data


class TestBackend:
    @patch("cli_anything.lldb.utils.lldb_backend.subprocess.run")
    @patch("cli_anything.lldb.utils.lldb_backend.os.path.isdir", return_value=False)
    def test_backend_probe_failure(self, _mock_isdir, mock_run):
        from cli_anything.lldb.utils import lldb_backend

        mock_run.return_value = MagicMock(stdout="", stderr="not found")
        with patch("builtins.__import__", side_effect=ImportError()):
            with pytest.raises(RuntimeError):
                lldb_backend.ensure_lldb_importable()

    @patch("cli_anything.lldb.utils.lldb_backend.subprocess.run", side_effect=FileNotFoundError())
    def test_backend_no_lldb_binary(self, _mock_run):
        from cli_anything.lldb.utils import lldb_backend

        with patch("builtins.__import__", side_effect=ImportError()):
            with pytest.raises(RuntimeError) as exc:
                lldb_backend.ensure_lldb_importable()
        assert "LLDB not found" in str(exc.value)


class TestSessionLifecycle:
    def _make_session(self):
        from cli_anything.lldb.core.session import LLDBSession

        session = object.__new__(LLDBSession)
        session._lldb = MagicMock()
        session._lldb.eStateDetached = 9
        session._lldb.eStateExited = 10
        session.debugger = MagicMock()
        session.target = None
        session.process = None
        session._process_origin = None
        return session

    def test_destroy_detaches_attached_process(self):
        from cli_anything.lldb.core.session import LLDBSession

        session = self._make_session()
        process = MagicMock()
        process.IsValid.return_value = True
        session.process = process
        session._process_origin = "attached"

        LLDBSession.destroy(session)

        process.Detach.assert_called_once()
        process.Kill.assert_not_called()
        session._lldb.SBDebugger.Destroy.assert_called_once_with(session.debugger)
        session._lldb.SBDebugger.Terminate.assert_called_once()

    def test_destroy_kills_launched_process(self):
        from cli_anything.lldb.core.session import LLDBSession

        session = self._make_session()
        process = MagicMock()
        process.IsValid.return_value = True
        process.GetState.return_value = 5
        session.process = process
        session._process_origin = "launched"

        LLDBSession.destroy(session)

        process.Kill.assert_called_once()
        process.Detach.assert_not_called()

    def test_session_status_reports_target_and_process(self):
        from cli_anything.lldb.core.session import LLDBSession

        session = self._make_session()
        session.target = MagicMock()
        session.target.IsValid.return_value = True
        session.process = MagicMock()
        session.process.IsValid.return_value = True
        session._process_origin = "attached"

        status = LLDBSession.session_status(session)

        assert status["has_target"] is True
        assert status["has_process"] is True
        assert status["process_origin"] == "attached"

    def test_process_info_public_wrapper(self):
        from cli_anything.lldb.core.session import LLDBSession

        session = self._make_session()
        process = MagicMock()
        process.IsValid.return_value = True
        process.GetProcessID.return_value = 77
        process.GetState.return_value = 5
        process.GetNumThreads.return_value = 2
        session.process = process

        data = LLDBSession.process_info(session)

        assert data == {"pid": 77, "state": "stopped", "num_threads": 2}

    def test_find_memory_scans_in_chunks(self):
        from cli_anything.lldb.core.session import LLDBSession

        session = self._make_session()
        process = MagicMock()
        process.IsValid.return_value = True
        session.process = process

        haystack = b"abcneedlexyz"
        start = 0x1000

        def fake_read_memory(address: int, size: int):
            offset = address - start
            return {"hex": haystack[offset : offset + size].hex()}

        session.read_memory = MagicMock(side_effect=fake_read_memory)

        data = LLDBSession.find_memory(session, "needle", start, len(haystack), chunk_size=5)

        assert data["found"] is True
        assert data["address"] == hex(start + 3)
        assert session.read_memory.call_count >= 2

    def test_find_memory_rejects_oversized_scan(self):
        from cli_anything.lldb.core.session import LLDBSession, MEMORY_FIND_MAX_SCAN_SIZE

        session = self._make_session()
        process = MagicMock()
        process.IsValid.return_value = True
        session.process = process

        with pytest.raises(ValueError) as exc:
            LLDBSession.find_memory(session, "needle", 0x1000, MEMORY_FIND_MAX_SCAN_SIZE + 1)

        assert "max supported scan size" in str(exc.value)


class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-lldb")

    def _run(self, args, check=True):
        harness_root = str(Path(__file__).resolve().parents[3])
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            check=check,
            cwd=harness_root,
        )

    def test_cli_help_subprocess(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "LLDB CLI" in result.stdout
