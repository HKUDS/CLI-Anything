"""
Unit tests for LLDB CLI harness modules.

These tests are mock-based and do not require LLDB installation.
"""

from __future__ import annotations

import json
import os
import io
import subprocess
import sys
import stat
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


class TestDAPProtocol:
    def test_encode_and_read_message(self):
        from cli_anything.lldb.dap import encode_message, read_message

        payload = {"seq": 1, "type": "request", "command": "initialize"}
        stream = io.BytesIO(encode_message(payload))

        assert read_message(stream) == payload
        assert read_message(stream) is None

    def test_read_message_rejects_missing_content_length(self):
        from cli_anything.lldb.dap import DAPProtocolError, read_message

        with pytest.raises(DAPProtocolError, match="Missing Content-Length"):
            read_message(io.BytesIO(b"Header: value\r\n\r\n{}"))

    def test_initialize_capabilities_and_event(self):
        from cli_anything.lldb.dap import LLDBDebugAdapter, encode_message, read_message

        out = io.BytesIO()
        adapter = LLDBDebugAdapter(session_factory=MagicMock())
        adapter.run(
            io.BytesIO(encode_message({"seq": 1, "type": "request", "command": "initialize", "arguments": {}})),
            out,
        )
        out.seek(0)
        response = read_message(out)
        event = read_message(out)

        assert response["success"] is True
        assert response["body"]["supportsConfigurationDoneRequest"] is True
        assert response["body"]["supportsFunctionBreakpoints"] is True
        assert response["body"]["supportsLoadedSourcesRequest"] is True
        assert response["body"]["supportsReadMemoryRequest"] is True
        assert response["body"]["supportsSetVariable"] is True
        assert response["body"]["supportsModulesRequest"] is True
        assert response["body"]["supportsExceptionInfoRequest"] is True
        assert event["event"] == "initialized"

    def test_variable_references_reset_on_resume(self):
        from cli_anything.lldb.dap import LLDBDebugAdapter

        adapter = LLDBDebugAdapter(session_factory=MagicMock())
        frame_ref = adapter._alloc_frame_ref(1, 0)
        variable_ref = adapter._alloc_variable_ref({"kind": "locals", "frame_ref": frame_ref})

        adapter._reset_refs_for_resume()

        assert frame_ref not in adapter._frame_refs
        assert variable_ref not in adapter._variable_refs

    def test_run_cleans_up_session_on_eof(self):
        from cli_anything.lldb.dap import LLDBDebugAdapter

        fake_session = MagicMock()
        adapter = LLDBDebugAdapter(session_factory=lambda: fake_session)
        adapter._ensure_session()

        result = adapter.run(io.BytesIO(), io.BytesIO())

        assert result == 0
        fake_session.destroy.assert_called_once()
        assert adapter._session is None

    def test_running_state_emits_continued_not_stopped(self):
        from cli_anything.lldb.dap import LLDBDebugAdapter, read_message

        fake_session = MagicMock()
        fake_session.process_info.return_value = {
            "state": "running",
            "selected_thread_id": 99,
            "stop": None,
            "exit_status": 0,
        }
        out = io.BytesIO()
        adapter = LLDBDebugAdapter(session_factory=lambda: fake_session)
        adapter._out = out
        adapter._ensure_session()

        adapter._emit_execution_event(default_reason="breakpoint")
        out.seek(0)
        event = read_message(out)

        assert event["event"] == "continued"
        assert event["body"]["threadId"] == 99

    def test_pause_request_interrupts_process_and_reports_stop(self):
        from cli_anything.lldb.dap import LLDBDebugAdapter, read_message

        fake_session = MagicMock()
        fake_session.process_info.return_value = {
            "state": "stopped",
            "selected_thread_id": 99,
            "stop": {"reason": None, "description": None, "hit_breakpoint_ids": []},
            "exit_status": 0,
        }
        out = io.BytesIO()
        adapter = LLDBDebugAdapter(session_factory=lambda: fake_session)
        adapter.run(
            io.BytesIO(
                b"".join(
                    [
                        __import__("cli_anything.lldb.dap", fromlist=["encode_message"]).encode_message(
                            {"seq": 1, "type": "request", "command": "pause", "arguments": {"threadId": 99}}
                        )
                    ]
                )
            ),
            out,
        )
        out.seek(0)
        response = read_message(out)
        event = read_message(out)

        assert response["success"] is True
        assert event["event"] == "stopped"
        assert event["body"]["reason"] == "pause"
        fake_session.interrupt.assert_called_once()

    def test_stack_trace_reports_total_frames(self):
        from cli_anything.lldb.dap import LLDBDebugAdapter, read_message

        fake_session = MagicMock()
        fake_session.backtrace.return_value = {
            "frames": [
                {"index": 0, "function": "main", "file": None, "line": None, "address": "0x1000"},
            ],
            "total_frames": 7,
        }
        out = io.BytesIO()
        adapter = LLDBDebugAdapter(session_factory=lambda: fake_session)
        adapter.run(
            io.BytesIO(
                __import__("cli_anything.lldb.dap", fromlist=["encode_message"]).encode_message(
                    {"seq": 1, "type": "request", "command": "stackTrace", "arguments": {"threadId": 123}}
                )
            ),
            out,
        )
        out.seek(0)
        response = read_message(out)

        assert response["success"] is True
        assert response["body"]["totalFrames"] == 7
        fake_session.thread_select.assert_called_once_with(123)

    def test_read_memory_response_is_base64(self):
        from cli_anything.lldb.dap import LLDBDebugAdapter, read_message

        fake_session = MagicMock()
        fake_session.read_memory.return_value = {"address": "0x1000", "size": 3, "hex": "616263"}
        out = io.BytesIO()
        adapter = LLDBDebugAdapter(session_factory=lambda: fake_session)
        adapter.run(
            io.BytesIO(
                __import__("cli_anything.lldb.dap", fromlist=["encode_message"]).encode_message(
                    {
                        "seq": 1,
                        "type": "request",
                        "command": "readMemory",
                        "arguments": {"memoryReference": "0x1000", "count": 3},
                    }
                )
            ),
            out,
        )
        out.seek(0)
        response = read_message(out)

        assert response["success"] is True
        assert response["body"]["address"] == "0x1000"
        assert response["body"]["data"] == "YWJj"
        fake_session.read_memory.assert_called_once_with(0x1000, 3)

    def test_launch_transcript_keeps_dap_response_event_order(self):
        from cli_anything.lldb.dap import LLDBDebugAdapter, encode_message, read_message

        breakpoint_payload = {
            "id": 1,
            "resolved": True,
            "location_details": [],
            "locations": 1,
        }
        fake_session = MagicMock()
        fake_session.target_create.return_value = {}
        fake_session.breakpoint_set.return_value = breakpoint_payload
        fake_session.breakpoint_list.return_value = {"breakpoints": [breakpoint_payload]}
        fake_session.launch.return_value = {}
        fake_session.process_info.return_value = {
            "state": "stopped",
            "selected_thread_id": 99,
            "stop": {"reason": "breakpoint", "description": "hit breakpoint", "hit_breakpoint_ids": [1]},
            "exit_status": 0,
        }
        messages = [
            {"seq": 1, "type": "request", "command": "initialize", "arguments": {}},
            {"seq": 2, "type": "request", "command": "launch", "arguments": {"program": "app.exe"}},
            {
                "seq": 3,
                "type": "request",
                "command": "setFunctionBreakpoints",
                "arguments": {"breakpoints": [{"name": "main"}]},
            },
            {"seq": 4, "type": "request", "command": "configurationDone", "arguments": {}},
        ]
        out = io.BytesIO()
        adapter = LLDBDebugAdapter(session_factory=lambda: fake_session)
        adapter.run(io.BytesIO(b"".join(encode_message(message) for message in messages)), out)
        out.seek(0)
        transcript = []
        while True:
            message = read_message(out)
            if message is None:
                break
            transcript.append(message)

        labels = [
            item.get("command") if item.get("type") == "response" else item.get("event")
            for item in transcript
        ]
        assert labels == [
            "initialize",
            "initialized",
            "launch",
            "setFunctionBreakpoints",
            "configurationDone",
            "breakpoint",
            "stopped",
        ]
        assert all(item["type"] in {"response", "event"} for item in transcript)

    def test_modules_response_shape(self):
        from cli_anything.lldb.dap import LLDBDebugAdapter, read_message

        fake_session = MagicMock()
        fake_session.modules.return_value = {
            "modules": [
                {
                    "id": 1,
                    "name": "app.exe",
                    "path": "C:/tmp/app.exe",
                    "symbol_status": "loaded",
                    "address": "0x1000",
                    "version": [1, 2, 3],
                }
            ]
        }
        out = io.BytesIO()
        adapter = LLDBDebugAdapter(session_factory=lambda: fake_session)
        adapter.run(
            io.BytesIO(
                __import__("cli_anything.lldb.dap", fromlist=["encode_message"]).encode_message(
                    {"seq": 1, "type": "request", "command": "modules", "arguments": {}}
                )
            ),
            out,
        )
        out.seek(0)
        response = read_message(out)

        assert response["success"] is True
        module = response["body"]["modules"][0]
        assert module["name"] == "app.exe"
        assert module["symbolStatus"] == "loaded"

    def test_exception_info_uses_current_stop_reason(self):
        from cli_anything.lldb.dap import LLDBDebugAdapter, read_message

        fake_session = MagicMock()
        fake_session.process_info.return_value = {
            "state": "stopped",
            "stop": {"reason": "breakpoint", "description": "breakpoint 1.1"},
        }
        out = io.BytesIO()
        adapter = LLDBDebugAdapter(session_factory=lambda: fake_session)
        adapter.run(
            io.BytesIO(
                __import__("cli_anything.lldb.dap", fromlist=["encode_message"]).encode_message(
                    {"seq": 1, "type": "request", "command": "exceptionInfo", "arguments": {"threadId": 1}}
                )
            ),
            out,
        )
        out.seek(0)
        response = read_message(out)

        assert response["success"] is True
        assert response["body"]["exceptionId"] == "breakpoint"
        assert response["body"]["description"] == "breakpoint 1.1"


class TestCoreHelpers:
    def test_breakpoints_wrapper(self):
        from cli_anything.lldb.core.breakpoints import set_breakpoint

        session = MagicMock()
        session.breakpoint_set.return_value = {"id": 1}
        data = set_breakpoint(session, function="main", allow_pending=True)
        assert data["id"] == 1
        session.breakpoint_set.assert_called_once_with(
            file=None,
            line=None,
            function="main",
            condition=None,
            allow_pending=True,
        )

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

    def test_interrupt_stops_process(self):
        from cli_anything.lldb.core.session import LLDBSession

        session = self._make_session()
        process = MagicMock()
        process.IsValid.return_value = True
        process.Stop.return_value = MagicMock()
        process.Stop.return_value.Success.return_value = True
        process.GetState.return_value = 5
        process.GetSelectedThread.return_value = None
        process.GetProcessID.return_value = 123
        process.GetNumThreads.return_value = 0
        process.GetExitStatus.return_value = 0
        session.process = process

        payload = LLDBSession.interrupt(session)

        process.Stop.assert_called_once()
        assert payload["pid"] == 123

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
        process.GetSelectedThread.return_value = None
        process.GetExitStatus.return_value = 0
        session.process = process

        data = LLDBSession.process_info(session)

        assert data == {
            "pid": 77,
            "state": "stopped",
            "num_threads": 2,
            "selected_thread_id": None,
            "stop": None,
            "exit_status": 0,
        }

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

    def test_unresolved_breakpoint_fails_by_default(self):
        from cli_anything.lldb.core.session import LLDBSession

        session = self._make_session()
        session.target = MagicMock()
        session.target.IsValid.return_value = True
        bp = MagicMock()
        bp.IsValid.return_value = True
        bp.GetID.return_value = 7
        bp.GetNumLocations.return_value = 0
        bp.GetHitCount.return_value = 0
        bp.IsEnabled.return_value = True
        bp.GetCondition.return_value = None
        session.target.BreakpointCreateByName.return_value = bp

        with pytest.raises(RuntimeError, match="unresolved"):
            LLDBSession.breakpoint_set(session, function="missing")

        session.target.BreakpointDelete.assert_called_once_with(7)

    def test_pending_breakpoint_returns_resolution_state(self):
        from cli_anything.lldb.core.session import LLDBSession

        session = self._make_session()
        session.target = MagicMock()
        session.target.IsValid.return_value = True
        bp = MagicMock()
        bp.IsValid.return_value = True
        bp.GetID.return_value = 7
        bp.GetNumLocations.return_value = 0
        bp.GetHitCount.return_value = 0
        bp.IsEnabled.return_value = True
        bp.GetCondition.return_value = None
        session.target.BreakpointCreateByName.return_value = bp

        payload = LLDBSession.breakpoint_set(session, function="missing", allow_pending=True)

        assert payload["id"] == 7
        assert payload["resolved"] is False
        assert payload["locations"] == 0
        session.target.BreakpointDelete.assert_not_called()


class TestSessionDaemonSecurity:
    def test_state_file_is_written_with_restrictive_mode(self, tmp_path):
        from cli_anything.lldb.utils.session_server import _write_state_file

        state_file = tmp_path / "secure" / "session.json"
        _write_state_file(state_file, ("127.0.0.1", 1234), b"secret")

        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert data["host"] == "127.0.0.1"
        assert data["port"] == 1234
        assert data["token"]
        if os.name != "nt":
            assert stat.S_IMODE(state_file.parent.stat().st_mode) == 0o700
            assert stat.S_IMODE(state_file.stat().st_mode) == 0o600

    def test_session_server_rejects_unknown_methods(self):
        from cli_anything.lldb.utils.session_server import SessionServer

        server = SessionServer()
        response, should_stop = server.handle({"method": "__getattribute__", "args": ["debugger"], "kwargs": {}})

        assert should_stop is False
        assert response["ok"] is False
        assert "Unsupported session method" in response["error"]


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
