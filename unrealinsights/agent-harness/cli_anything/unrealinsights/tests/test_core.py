"""
Unit tests for Unreal Insights harness modules.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner


@pytest.fixture(autouse=True)
def _session_state_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CLI_ANYTHING_UNREALINSIGHTS_STATE_DIR", str(tmp_path / "state"))


class TestOutputUtils:
    def test_output_json(self):
        import io

        from cli_anything.unrealinsights.utils.output import output_json

        buf = io.StringIO()
        output_json({"ok": True, "value": 42}, file=buf)
        data = json.loads(buf.getvalue())
        assert data["ok"] is True
        assert data["value"] == 42

    def test_output_table_empty(self):
        import io

        from cli_anything.unrealinsights.utils.output import output_table

        buf = io.StringIO()
        output_table([], ["col"], file=buf)
        assert "(no data)" in buf.getvalue()

    def test_format_size(self):
        from cli_anything.unrealinsights.utils.output import format_size

        assert format_size(10) == "10 B"
        assert "KB" in format_size(4096)


class TestErrorUtils:
    def test_handle_error(self):
        from cli_anything.unrealinsights.utils.errors import handle_error

        result = handle_error(ValueError("bad"))
        assert result["error"] == "bad"
        assert result["type"] == "ValueError"


def _make_fake_binary(root: Path, binary_name: str) -> Path:
    target = root / "UE_5.5" / "Engine" / "Binaries" / "Win64" / binary_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("fake-binary", encoding="utf-8")
    return target


class TestBackendDiscovery:
    @patch("cli_anything.unrealinsights.utils.unrealinsights_backend._read_windows_product_version", return_value="5.5.4")
    def test_explicit_path_precedence(self, _mock_version, tmp_path, monkeypatch):
        from cli_anything.unrealinsights.utils.unrealinsights_backend import resolve_unrealinsights_exe

        explicit = tmp_path / "explicit" / "UnrealInsights.exe"
        explicit.parent.mkdir(parents=True)
        explicit.write_text("x", encoding="utf-8")

        env_binary = tmp_path / "env" / "UnrealInsights.exe"
        env_binary.parent.mkdir(parents=True)
        env_binary.write_text("x", encoding="utf-8")
        monkeypatch.setenv("UNREALINSIGHTS_EXE", str(env_binary))

        auto_root = tmp_path / "Epic Games"
        _make_fake_binary(auto_root, "UnrealInsights.exe")

        result = resolve_unrealinsights_exe(str(explicit), search_roots=[auto_root])
        assert result["source"] == "explicit"
        assert result["path"] == str(explicit.resolve())

    @patch("cli_anything.unrealinsights.utils.unrealinsights_backend._read_windows_product_version", return_value="5.5.4")
    def test_env_path_precedence(self, _mock_version, tmp_path, monkeypatch):
        from cli_anything.unrealinsights.utils.unrealinsights_backend import resolve_unrealinsights_exe

        env_binary = tmp_path / "env" / "UnrealInsights.exe"
        env_binary.parent.mkdir(parents=True)
        env_binary.write_text("x", encoding="utf-8")
        monkeypatch.setenv("UNREALINSIGHTS_EXE", str(env_binary))

        auto_root = tmp_path / "Epic Games"
        _make_fake_binary(auto_root, "UnrealInsights.exe")

        result = resolve_unrealinsights_exe(search_roots=[auto_root])
        assert result["source"] == "env:UNREALINSIGHTS_EXE"
        assert result["path"] == str(env_binary.resolve())

    @patch("cli_anything.unrealinsights.utils.unrealinsights_backend._read_windows_product_version", return_value="5.5.4")
    def test_auto_discovery(self, _mock_version, tmp_path, monkeypatch):
        from cli_anything.unrealinsights.utils.unrealinsights_backend import resolve_unrealinsights_exe

        monkeypatch.delenv("UNREALINSIGHTS_EXE", raising=False)
        auto_root = tmp_path / "Epic Games"
        auto_binary = _make_fake_binary(auto_root, "UnrealInsights.exe")

        result = resolve_unrealinsights_exe(search_roots=[auto_root])
        assert result["source"].startswith("auto:")
        assert result["path"] == str(auto_binary.resolve())

    def test_missing_explicit_path_fails(self, tmp_path):
        from cli_anything.unrealinsights.utils.unrealinsights_backend import resolve_unrealinsights_exe

        with pytest.raises(RuntimeError):
            resolve_unrealinsights_exe(str(tmp_path / "missing.exe"))

    def test_build_insights_command(self, tmp_path):
        from cli_anything.unrealinsights.utils.unrealinsights_backend import build_insights_command

        command = build_insights_command(
            str(tmp_path / "UnrealInsights.exe"),
            str(tmp_path / "trace.utrace"),
            'TimingInsights.ExportThreads "D:\\out\\threads.csv"',
            str(tmp_path / "threads.log"),
        )
        assert any(part.startswith("-OpenTraceFile=") for part in command)
        assert any(part.startswith("-ExecOnAnalysisCompleteCmd=") for part in command)

    def test_build_insights_command_line(self, tmp_path):
        from cli_anything.unrealinsights.utils.unrealinsights_backend import build_insights_command_line

        command = build_insights_command_line(
            str(tmp_path / "UnrealInsights.exe"),
            str(tmp_path / "trace.utrace"),
            'TimingInsights.ExportThreads D:\\out\\threads.csv',
            str(tmp_path / "threads.log"),
        )
        assert "-ExecOnAnalysisCompleteCmd=" in command
        assert command.startswith('"')

    @patch("cli_anything.unrealinsights.utils.unrealinsights_backend._read_windows_product_version", return_value="5.3.0")
    def test_resolve_binary_from_engine_root(self, _mock_version, tmp_path):
        from cli_anything.unrealinsights.utils.unrealinsights_backend import resolve_binary_from_engine_root

        binary = _make_fake_binary(tmp_path, "UnrealInsights.exe")
        result = resolve_binary_from_engine_root("UnrealInsights.exe", str(tmp_path / "UE_5.5"))
        assert result["path"] == str(binary.resolve())
        assert result["source"] == "engine:UE_5.5"

    @patch("cli_anything.unrealinsights.utils.unrealinsights_backend.subprocess.run")
    def test_build_engine_program(self, mock_run, tmp_path):
        from cli_anything.unrealinsights.utils.unrealinsights_backend import build_engine_program

        build_bat = tmp_path / "UE_5.5" / "Engine" / "Build" / "BatchFiles" / "Build.bat"
        build_bat.parent.mkdir(parents=True, exist_ok=True)
        build_bat.write_text("echo build", encoding="utf-8")

        mock_run.return_value = type("Result", (), {"stdout": "ok", "stderr": "", "returncode": 0})()
        result = build_engine_program(str(tmp_path / "UE_5.5"), "UnrealInsights")
        assert result["succeeded"] is True
        assert Path(result["log_path"]).is_file()

    @patch("cli_anything.unrealinsights.utils.unrealinsights_backend._read_windows_product_version", return_value="5.3.0")
    @patch("cli_anything.unrealinsights.utils.unrealinsights_backend.build_engine_program")
    def test_ensure_engine_unrealinsights_builds_when_missing(self, mock_build, _mock_version, tmp_path):
        from cli_anything.unrealinsights.utils.unrealinsights_backend import ensure_engine_unrealinsights

        engine_root = tmp_path / "UE_5.5"
        (engine_root / "Engine" / "Binaries" / "Win64").mkdir(parents=True, exist_ok=True)
        (engine_root / "Engine" / "Build" / "BatchFiles").mkdir(parents=True, exist_ok=True)
        (engine_root / "Engine" / "Build" / "BatchFiles" / "Build.bat").write_text("echo build", encoding="utf-8")
        built_exe = engine_root / "Engine" / "Binaries" / "Win64" / "UnrealInsights.exe"
        built_exe.write_text("x", encoding="utf-8")
        mock_build.return_value = {
            "command": ["Build.bat"],
            "cwd": str(engine_root),
            "log_path": str(engine_root / "build.log"),
            "exit_code": 0,
            "timed_out": False,
            "stdout": "",
            "stderr": "",
            "succeeded": True,
        }

        result = ensure_engine_unrealinsights(str(engine_root))
        assert result["insights"]["path"] == str(built_exe.resolve())

    def test_ensure_engine_unrealinsights_no_build_errors_when_missing(self, tmp_path):
        from cli_anything.unrealinsights.utils.unrealinsights_backend import ensure_engine_unrealinsights

        engine_root = tmp_path / "UE_5.5"
        (engine_root / "Engine" / "Binaries" / "Win64").mkdir(parents=True, exist_ok=True)
        with pytest.raises(RuntimeError):
            ensure_engine_unrealinsights(str(engine_root), build_if_missing=False)


class TestCaptureCore:
    def test_normalize_trace_output_path_prefers_explicit(self, tmp_path):
        from cli_anything.unrealinsights.core.capture import normalize_trace_output_path

        path = normalize_trace_output_path("game.exe", output_trace=str(tmp_path / "capture"))
        assert path.endswith(".utrace")

    def test_build_exec_cmds_arg(self):
        from cli_anything.unrealinsights.core.capture import build_exec_cmds_arg

        assert build_exec_cmds_arg(["Trace.Bookmark Boot", "Trace.RegionBegin Boot"]) == (
            "Trace.Bookmark Boot,Trace.RegionBegin Boot"
        )

    def test_resolve_engine_root_from_engine_subdir(self, tmp_path):
        from cli_anything.unrealinsights.core.capture import resolve_engine_root

        engine_dir = tmp_path / "UE_5.5" / "Engine"
        engine_dir.mkdir(parents=True)
        assert resolve_engine_root(str(engine_dir)) == str((tmp_path / "UE_5.5").resolve())

    def test_resolve_editor_target(self, tmp_path):
        from cli_anything.unrealinsights.core.capture import resolve_editor_target

        editor = tmp_path / "UE_5.5" / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"
        editor.parent.mkdir(parents=True)
        editor.write_text("x", encoding="utf-8")
        assert resolve_editor_target(str(tmp_path / "UE_5.5")) == str(editor.resolve())

    def test_resolve_capture_target_from_project_and_engine(self, tmp_path):
        from cli_anything.unrealinsights.core.capture import resolve_capture_target

        editor = tmp_path / "UE_5.5" / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"
        editor.parent.mkdir(parents=True)
        editor.write_text("x", encoding="utf-8")
        project = tmp_path / "Project" / "MyGame.uproject"
        project.parent.mkdir(parents=True)
        project.write_text("{}", encoding="utf-8")

        target_exe, target_args, launch_info = resolve_capture_target(
            None,
            project=str(project),
            engine_root=str(tmp_path / "UE_5.5"),
            target_args=["-game"],
        )
        assert target_exe == str(editor.resolve())
        assert target_args[0] == str(project.resolve())
        assert "-game" in target_args
        assert launch_info["project_path"] == str(project.resolve())

    def test_build_capture_command(self, tmp_path):
        from cli_anything.unrealinsights.core.capture import build_capture_command

        exe = tmp_path / "Game.exe"
        exe.write_text("x", encoding="utf-8")
        trace = tmp_path / "capture.utrace"
        command = build_capture_command(
            str(exe),
            str(trace),
            channels="default,bookmark",
            exec_cmds=["Trace.Bookmark Boot"],
            target_args=["MyGame.uproject", "-game"],
        )
        assert command[0] == str(exe.resolve())
        assert "MyGame.uproject" in command
        assert "-trace=default,bookmark" in command
        assert any(arg.startswith("-tracefile=") for arg in command)
        assert any(arg.startswith("-ExecCmds=") for arg in command)

    @patch("cli_anything.unrealinsights.core.capture.backend.run_process")
    def test_run_capture_wait_requires_clean_exit(self, mock_run_process, tmp_path):
        from cli_anything.unrealinsights.core.capture import run_capture

        exe = tmp_path / "Game.exe"
        exe.write_text("x", encoding="utf-8")
        trace = tmp_path / "capture.utrace"
        trace.write_text("partial-trace", encoding="utf-8")

        mock_run_process.return_value = {
            "command": [str(exe.resolve())],
            "waited": True,
            "timed_out": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": "boom",
            "pid": None,
        }

        result = run_capture(str(exe), str(trace), wait=True)
        assert result["trace_exists"] is True
        assert result["succeeded"] is False

    def test_capture_status(self):
        from cli_anything.unrealinsights.core.capture import capture_status
        from cli_anything.unrealinsights.core.session import UnrealInsightsSession

        session = UnrealInsightsSession()
        session.set_capture(
            pid=1234,
            target_exe="C:/UE/UnrealEditor.exe",
            target_args=["Project.uproject"],
            trace_path="C:/trace.utrace",
            channels="default",
        )
        with patch("cli_anything.unrealinsights.core.capture.backend.is_process_running", return_value=True):
            data = capture_status(session)
        assert data["active"] is True
        assert data["running"] is True

    def test_snapshot_capture(self, tmp_path):
        from cli_anything.unrealinsights.core.capture import snapshot_capture
        from cli_anything.unrealinsights.core.session import UnrealInsightsSession

        trace = tmp_path / "live.utrace"
        trace.write_text("trace-data", encoding="utf-8")
        session = UnrealInsightsSession()
        session.set_capture(
            pid=4321,
            target_exe="C:/UE/UnrealEditor.exe",
            target_args=[],
            trace_path=str(trace),
            channels="default",
        )
        with patch("cli_anything.unrealinsights.core.capture.backend.is_process_running", return_value=True):
            result = snapshot_capture(session)
        assert Path(result["snapshot_trace"]).is_file()

    def test_stop_capture(self):
        from cli_anything.unrealinsights.core.capture import stop_capture
        from cli_anything.unrealinsights.core.session import UnrealInsightsSession

        session = UnrealInsightsSession()
        session.set_capture(
            pid=9876,
            target_exe="C:/UE/UnrealEditor.exe",
            target_args=[],
            trace_path="C:/trace.utrace",
            channels="default",
        )
        with patch("cli_anything.unrealinsights.core.capture.backend.terminate_process", return_value={"requested_pid": 9876, "stopped": True, "exit_code": 0}), \
             patch("cli_anything.unrealinsights.core.capture.backend.is_process_running", return_value=False):
            result = stop_capture(session)
        assert result["termination"]["stopped"] is True


class TestExportCore:
    @pytest.mark.parametrize(
        ("exporter", "expected"),
        [
            ("threads", "TimingInsights.ExportThreads"),
            ("timers", "TimingInsights.ExportTimers"),
            ("timing-events", "TimingInsights.ExportTimingEvents"),
            ("timer-stats", "TimingInsights.ExportTimerStatistics"),
            ("timer-callees", "TimingInsights.ExportTimerCallees"),
            ("counters", "TimingInsights.ExportCounters"),
            ("counter-values", "TimingInsights.ExportCounterValues"),
        ],
    )
    def test_build_export_exec_command(self, exporter, expected, tmp_path):
        from cli_anything.unrealinsights.core.export import build_export_exec_command

        command = build_export_exec_command(
            exporter,
            str(tmp_path / f"{exporter}.csv"),
            columns="ThreadId,TimerId" if exporter in ("timing-events", "timer-stats", "counter-values") else None,
            threads="GameThread" if exporter in ("timing-events", "timer-stats", "timer-callees") else None,
            timers="*" if exporter in ("timing-events", "timer-stats", "timer-callees") else None,
            counter="*" if exporter == "counter-values" else None,
        )
        assert command.startswith(expected)
        if exporter == "counter-values":
            assert "-counter=*" in command
            assert '-counter="' not in command
        if exporter in ("timing-events", "timer-stats", "timer-callees"):
            assert "-threads=GameThread" in command
            assert "-timers=*" in command

    def test_build_rsp_exec_command(self, tmp_path):
        from cli_anything.unrealinsights.core.export import build_rsp_exec_command

        command = build_rsp_exec_command(str(tmp_path / "exports.rsp"))
        assert command.startswith("@=")

    @pytest.mark.skipif(os.name != "nt", reason="Windows quoting behavior")
    def test_normalize_rsp_line_modern_windows_avoids_nested_quotes(self, tmp_path):
        from cli_anything.unrealinsights.core.export import _normalize_rsp_line

        line, output = _normalize_rsp_line(
            f'TimingInsights.ExportThreads "{tmp_path / "threads.csv"}"',
            insights_version="5.5.4",
        )
        resolved = str((tmp_path / "threads.csv").resolve())
        assert f'"{resolved}"' not in line
        assert resolved in line
        assert output == resolved

    def test_build_export_exec_command_legacy_53_unquoted_filename(self, tmp_path):
        from cli_anything.unrealinsights.core.export import build_export_exec_command

        command = build_export_exec_command(
            "threads",
            str(tmp_path / "threads.csv"),
            insights_version="5.3.0",
        )
        assert '"{}"'.format(str((tmp_path / "threads.csv").resolve())) not in command
        assert str((tmp_path / "threads.csv").resolve()) in command

    @pytest.mark.skipif(os.name != "nt", reason="Windows quoting behavior")
    def test_build_export_exec_command_modern_windows_avoids_nested_quotes(self, tmp_path):
        from cli_anything.unrealinsights.core.export import build_export_exec_command

        command = build_export_exec_command(
            "threads",
            str(tmp_path / "threads.csv"),
            insights_version="5.5.4",
        )
        resolved = str((tmp_path / "threads.csv").resolve())
        assert f'"{resolved}"' not in command
        assert resolved in command

    @patch("cli_anything.unrealinsights.core.export.backend.parse_unreal_log")
    @patch("cli_anything.unrealinsights.core.export.backend.run_process")
    def test_execute_export_classifies_no_output(self, mock_run, mock_log, tmp_path):
        from cli_anything.unrealinsights.core.export import execute_export

        mock_run.return_value = {
            "command": "UnrealInsights.exe",
            "waited": True,
            "timed_out": False,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "pid": None,
        }
        mock_log.return_value = {
            "path": str(tmp_path / "export.log"),
            "exists": True,
            "warnings": [],
            "errors": [],
            "tail": [],
        }

        result = execute_export(
            "C:/UE/UnrealInsights.exe",
            "C:/trace.utrace",
            "counter-values",
            str(tmp_path / "counter_values.csv"),
        )
        assert result["output_status"] == "no_output"
        assert result["succeeded"] is False
        assert "without materializing" in result["status_message"]

    @patch("cli_anything.unrealinsights.core.export.backend.parse_unreal_log")
    @patch("cli_anything.unrealinsights.core.export.backend.run_process")
    def test_execute_export_classifies_exporter_error(self, mock_run, mock_log, tmp_path):
        from cli_anything.unrealinsights.core.export import execute_export

        mock_run.return_value = {
            "command": "UnrealInsights.exe",
            "waited": True,
            "timed_out": False,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "pid": None,
        }
        mock_log.return_value = {
            "path": str(tmp_path / "export.log"),
            "exists": True,
            "warnings": [],
            "errors": ["TimingInsights: Error: Export failed."],
            "tail": [],
        }

        result = execute_export(
            "C:/UE/UnrealInsights.exe",
            "C:/trace.utrace",
            "threads",
            str(tmp_path / "threads.csv"),
        )
        assert result["output_status"] == "exporter_error"
        assert result["status_message"] == "TimingInsights: Error: Export failed."

    def test_expected_outputs_from_rsp(self, tmp_path):
        from cli_anything.unrealinsights.core.export import expected_outputs_from_rsp

        rsp = tmp_path / "exports.rsp"
        rsp.write_text(
            "\n".join(
                [
                    "# comment",
                    f'TimingInsights.ExportThreads "{tmp_path / "threads.csv"}"',
                    f'TimingInsights.ExportTimers "{tmp_path / "timers.csv"}"',
                ]
            ),
            encoding="utf-8",
        )
        outputs = expected_outputs_from_rsp(str(rsp))
        assert str((tmp_path / "threads.csv").resolve()) in outputs
        assert str((tmp_path / "timers.csv").resolve()) in outputs

    def test_normalize_response_file_lines_unquotes_filename_without_spaces(self, tmp_path):
        from cli_anything.unrealinsights.core.export import normalize_response_file_lines

        output = tmp_path / "threads.csv"
        lines = [f'TimingInsights.ExportThreads "{output}"']
        normalized = normalize_response_file_lines(lines, insights_version="5.5.4")
        assert normalized[0] == f"TimingInsights.ExportThreads {output.resolve()}"

    def test_normalized_response_file_path_writes_temp_file(self, tmp_path):
        from cli_anything.unrealinsights.core.export import normalized_response_file_path

        output = tmp_path / "threads.csv"
        rsp = tmp_path / "exports.rsp"
        rsp.write_text(f'TimingInsights.ExportThreads "{output}"\n', encoding="utf-8")
        normalized_path = normalized_response_file_path(str(rsp), insights_version="5.5.4")
        assert normalized_path != str(rsp.resolve())
        assert f"TimingInsights.ExportThreads {output.resolve()}" in Path(normalized_path).read_text(encoding="utf-8")
        Path(normalized_path).unlink()

    def test_collect_materialized_outputs_placeholder(self, tmp_path):
        from cli_anything.unrealinsights.core.export import collect_materialized_outputs

        (tmp_path / "stats_GameThread.csv").write_text("ok", encoding="utf-8")
        outputs = collect_materialized_outputs(str(tmp_path / "stats_{region}.csv"))
        assert str((tmp_path / "stats_GameThread.csv").resolve()) in outputs


class TestStoreCore:
    def test_list_trace_files_includes_ucache_and_live_flag(self, tmp_path):
        from cli_anything.unrealinsights.core.store import list_trace_files

        trace_dir = tmp_path / "Store" / "001"
        trace_dir.mkdir(parents=True)
        trace = trace_dir / "session.ucache"
        trace.write_text("trace", encoding="utf-8")

        result = list_trace_files(str(tmp_path / "Store"), live_window_seconds=3600)
        assert result["trace_count"] == 1
        assert result["traces"][0]["extension"] == ".ucache"
        assert result["traces"][0]["is_live_candidate"] is True

    def test_latest_trace_file(self, tmp_path):
        from cli_anything.unrealinsights.core.store import latest_trace_file

        store = tmp_path / "Store"
        store.mkdir()
        old_trace = store / "old.utrace"
        new_trace = store / "new.utrace"
        old_trace.write_text("old", encoding="utf-8")
        new_trace.write_text("new", encoding="utf-8")
        os.utime(old_trace, (1, 1))

        result = latest_trace_file(str(store))
        assert result["latest"]["path"] == str(new_trace.resolve())

    @patch("cli_anything.unrealinsights.core.store.backend.resolve_trace_server_exe")
    def test_trace_store_info(self, mock_resolve, tmp_path, monkeypatch):
        from cli_anything.unrealinsights.core.store import trace_store_info

        trace_root = tmp_path / "Trace"
        store = trace_root / "Store"
        store.mkdir(parents=True)
        monkeypatch.setenv("UNREAL_TRACE_ROOT", str(trace_root))
        mock_resolve.return_value = {"available": False, "path": None, "error": "missing"}

        result = trace_store_info()
        assert result["store_dir"] == str(store)
        assert result["store_exists"] is True


class TestLiveCore:
    @patch("cli_anything.unrealinsights.core.live.subprocess.run")
    def test_list_unreal_processes_windows_json(self, mock_run):
        from cli_anything.unrealinsights.core.live import list_unreal_processes

        mock_run.return_value = type(
            "Result",
            (),
            {
                "returncode": 0,
                "stdout": json.dumps(
                    [
                        {
                            "Name": "UnrealEditor.exe",
                            "ProcessId": 100,
                            "ExecutablePath": "C:/UE/UnrealEditor.exe",
                            "CommandLine": "UnrealEditor.exe C:/Game.uproject",
                            "CreationDate": "now",
                        },
                        {
                            "Name": "UnrealInsights.exe",
                            "ProcessId": 200,
                            "ExecutablePath": "C:/UE/UnrealInsights.exe",
                            "CommandLine": "UnrealInsights.exe",
                            "CreationDate": "now",
                        },
                    ]
                ),
            },
        )()

        with patch("cli_anything.unrealinsights.core.live.os.name", "nt"):
            result = list_unreal_processes()
        assert result["process_count"] == 2
        assert {process["role"] for process in result["processes"]} == {"editor", "insights"}

    def test_live_exec_requires_backend(self, monkeypatch):
        from cli_anything.unrealinsights.core.live import execute_live_command

        monkeypatch.delenv("UNREALINSIGHTS_LIVE_EXEC", raising=False)
        with pytest.raises(RuntimeError, match="Live control backend unavailable"):
            execute_live_command(100, "Trace.Status", backend_command=None)

    @patch("cli_anything.unrealinsights.core.live.backend.run_process")
    def test_live_exec_uses_template(self, mock_run, monkeypatch):
        from cli_anything.unrealinsights.core.live import execute_live_command

        monkeypatch.delenv("UNREALINSIGHTS_LIVE_EXEC", raising=False)
        mock_run.return_value = {
            "command": ["sender"],
            "waited": True,
            "timed_out": False,
            "exit_code": 0,
            "stdout": "ok",
            "stderr": "",
            "pid": None,
        }

        result = execute_live_command(100, "Trace.Status", backend_command='sender --pid {pid} --cmd "{cmd}"')
        assert result["succeeded"] is True
        assert result["live_command"] == "Trace.Status"


class TestGuiCore:
    def test_build_gui_command_has_no_headless_flags(self, tmp_path):
        from cli_anything.unrealinsights.core.gui import build_gui_command

        exe = tmp_path / "UnrealInsights.exe"
        trace = tmp_path / "session.utrace"
        exe.write_text("x", encoding="utf-8")
        trace.write_text("x", encoding="utf-8")
        command = build_gui_command(str(exe), str(trace))
        assert "-NoUI" not in command
        assert "-AutoQuit" not in command
        assert any(arg.startswith("-OpenTraceFile=") for arg in command)

    @patch("cli_anything.unrealinsights.core.gui.backend.run_process")
    def test_open_gui_keeps_running(self, mock_run, tmp_path):
        from cli_anything.unrealinsights.core.gui import open_gui

        exe = tmp_path / "UnrealInsights.exe"
        exe.write_text("x", encoding="utf-8")
        mock_run.return_value = {
            "command": [str(exe)],
            "waited": False,
            "timed_out": False,
            "exit_code": None,
            "stdout": None,
            "stderr": None,
            "pid": 321,
        }
        result = open_gui(str(exe))
        assert result["pid"] == 321
        assert result["kept_running"] is True


class TestAnalyzeCore:
    def test_summarize_exports_from_synthetic_csv(self, tmp_path):
        from cli_anything.unrealinsights.core.analyze import summarize_exports

        (tmp_path / "timer_stats.csv").write_text(
            "\n".join(
                [
                    "Timer Name,Thread,Total Time,Count",
                    "Tick,GameThread,12.5,3",
                    "WaitForTasks,RenderThread,20.0,2",
                ]
            ),
            encoding="utf-8",
        )
        (tmp_path / "counter_values.csv").write_text(
            "\n".join(
                [
                    "Counter,Value",
                    "FrameTime,33.3",
                    "FrameTime,16.6",
                ]
            ),
            encoding="utf-8",
        )

        result = summarize_exports(str(tmp_path), limit=2)
        assert result["succeeded"] is True
        assert result["summary"]["top_timers"][0]["name"] == "WaitForTasks"
        assert result["summary"]["focus_threads"]["GameThread"][0]["name"] == "Tick"
        assert result["summary"]["counter_peaks"][0]["name"] == "FrameTime"
        diagnostics = result["summary"]["diagnostics"]
        assert diagnostics["primary_hotspot"]["name"] == "WaitForTasks"
        assert diagnostics["wait_pressure"] == "present"
        assert diagnostics["counter_anomaly_count"] == 1

    def test_summarize_exports_reports_export_status(self, tmp_path):
        from cli_anything.unrealinsights.core.analyze import summarize_exports

        (tmp_path / "timer_stats.csv").write_text("Timer Name,Total Time\nTick,1.0\n", encoding="utf-8")
        result = summarize_exports(
            str(tmp_path),
            export_results=[
                {
                    "exporter": "timer-stats",
                    "output_status": "ok",
                    "succeeded": True,
                    "output_files": [str(tmp_path / "timer_stats.csv")],
                    "status_message": "ok",
                    "log_path": "timer_stats.log",
                },
                {
                    "exporter": "counter-values",
                    "output_status": "no_output",
                    "succeeded": False,
                    "output_files": [],
                    "status_message": "no data",
                    "log_path": "counter_values.log",
                },
            ],
        )
        assert result["export_status"][1]["status"] == "no_output"
        assert result["summary"]["diagnostics"]["export_status_counts"]["ok"] == 1
        assert result["summary"]["diagnostics"]["export_status_counts"]["no_output"] == 1

    @patch("cli_anything.unrealinsights.core.analyze.execute_export")
    def test_analyze_summary_runs_export_bundle(self, mock_export, tmp_path):
        from cli_anything.unrealinsights.core.analyze import analyze_summary

        def _fake_export(_exe, _trace, exporter, output_path, **_kwargs):
            if exporter == "timer-stats":
                Path(output_path).write_text("Timer Name,Total Time\nTick,1.0\n", encoding="utf-8")
            elif exporter == "counter-values":
                Path(output_path).write_text("Counter,Value\nFrameTime,16.0\n", encoding="utf-8")
            else:
                Path(output_path).write_text("Name\nx\n", encoding="utf-8")
            return {"exporter": exporter, "output_files": [output_path], "succeeded": True}

        mock_export.side_effect = _fake_export
        result = analyze_summary("C:/UE/UnrealInsights.exe", "C:/trace.utrace", str(tmp_path))
        assert result["succeeded"] is True
        assert mock_export.call_count == 5


class TestCLIHelp:
    def test_main_help(self):
        from cli_anything.unrealinsights.unrealinsights_cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Unreal Insights harness" in result.output

    def test_group_help(self):
        from cli_anything.unrealinsights.unrealinsights_cli import cli

        runner = CliRunner()
        for group in ("backend", "trace", "store", "capture", "live", "gui", "export", "batch", "analyze"):
            result = runner.invoke(cli, [group, "--help"])
            assert result.exit_code == 0, f"{group} help failed"


class TestCLIJsonErrors:
    @patch("cli_anything.unrealinsights.unrealinsights_cli.resolve_unrealinsights_exe")
    def test_export_threads_requires_trace(self, _mock_resolve):
        from cli_anything.unrealinsights.unrealinsights_cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "export", "threads", "out.csv"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "error" in data

    @patch("cli_anything.unrealinsights.unrealinsights_cli.resolve_unrealinsights_exe")
    @patch("cli_anything.unrealinsights.unrealinsights_cli.resolve_trace_server_exe")
    def test_backend_info_json(self, mock_trace_server, mock_insights):
        from cli_anything.unrealinsights.unrealinsights_cli import cli

        mock_insights.return_value = {
            "available": True,
            "path": "C:/UE/UnrealInsights.exe",
            "source": "explicit",
            "version": "5.5.4",
            "engine_version_hint": "5.5",
        }
        mock_trace_server.return_value = {
            "available": False,
            "path": None,
            "source": "unresolved",
            "version": None,
            "engine_version_hint": None,
            "error": "missing",
        }

        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "backend", "info"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["insights"]["path"].endswith("UnrealInsights.exe")

    def test_capture_project_requires_engine_root(self, tmp_path):
        from cli_anything.unrealinsights.unrealinsights_cli import cli

        project = tmp_path / "MyGame.uproject"
        project.write_text("{}", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "capture", "run", "--project", str(project)])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "engine-root" in data["error"]

    @patch("cli_anything.unrealinsights.unrealinsights_cli.ensure_engine_unrealinsights")
    def test_backend_ensure_insights_json(self, mock_ensure):
        from cli_anything.unrealinsights.unrealinsights_cli import cli

        mock_ensure.return_value = {
            "engine_root": "D:/UE_5.3",
            "insights": {
                "available": True,
                "path": "D:/UE_5.3/Engine/Binaries/Win64/UnrealInsights.exe",
                "source": "engine:UE_5.3",
                "version": "5.3.0",
                "engine_version_hint": None,
            },
            "trace_server": {
                "available": False,
                "path": None,
                "source": "unresolved",
                "version": None,
                "engine_version_hint": None,
                "error": "missing",
            },
            "build_attempted": False,
            "build": None,
        }

        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "backend", "ensure-insights", "--engine-root", "D:/UE_5.3"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["insights"]["path"].endswith("UnrealInsights.exe")

    @patch("cli_anything.unrealinsights.unrealinsights_cli.capture_status")
    def test_capture_status_json(self, mock_capture_status):
        from cli_anything.unrealinsights.unrealinsights_cli import cli

        mock_capture_status.return_value = {
            "active": True,
            "pid": 1234,
            "running": True,
            "target_exe": "C:/UE/UnrealEditor.exe",
            "target_args": [],
            "project_path": "C:/Project.uproject",
            "engine_root": "C:/UE_5.3",
            "trace_path": "C:/trace.utrace",
            "trace_exists": True,
            "trace_size": 1024,
            "channels": "default",
            "started_at": "2026-04-16T00:00:00+00:00",
        }

        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "capture", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["running"] is True

    @patch("cli_anything.unrealinsights.unrealinsights_cli.stop_capture")
    def test_capture_stop_json(self, mock_stop_capture):
        from cli_anything.unrealinsights.unrealinsights_cli import cli

        mock_stop_capture.return_value = {
            "termination": {"requested_pid": 1234, "stopped": True, "exit_code": 0},
            "capture": {"active": False},
        }

        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "capture", "stop"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["termination"]["stopped"] is True

    @patch("cli_anything.unrealinsights.unrealinsights_cli.snapshot_capture")
    def test_capture_snapshot_json(self, mock_snapshot_capture):
        from cli_anything.unrealinsights.unrealinsights_cli import cli

        mock_snapshot_capture.return_value = {
            "source_trace": "C:/trace.utrace",
            "snapshot_trace": "C:/trace-snapshot.utrace",
            "snapshot_exists": True,
            "snapshot_size": 2048,
            "capture_running": True,
        }

        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "capture", "snapshot"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["snapshot_exists"] is True

    @patch("cli_anything.unrealinsights.unrealinsights_cli.trace_store_info")
    def test_store_info_json(self, mock_store_info):
        from cli_anything.unrealinsights.unrealinsights_cli import cli

        mock_store_info.return_value = {
            "trace_root": "C:/Trace",
            "trace_root_exists": True,
            "store_dir": "C:/Trace/Store",
            "store_exists": True,
            "trace_file_count": 0,
            "trace_server": {"available": False, "error": "missing"},
            "watch_folders": ["C:/Trace/Store"],
            "server_logs": [],
        }
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "store", "info"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["store_exists"] is True

    def test_live_exec_json_backend_unavailable(self, monkeypatch):
        from cli_anything.unrealinsights.unrealinsights_cli import cli

        monkeypatch.delenv("UNREALINSIGHTS_LIVE_EXEC", raising=False)
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "live", "exec", "--pid", "1234", "Trace.Status"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "Live control backend unavailable" in data["error"]

    @patch("cli_anything.unrealinsights.unrealinsights_cli.gui_status")
    def test_gui_status_json(self, mock_gui_status):
        from cli_anything.unrealinsights.unrealinsights_cli import cli

        mock_gui_status.return_value = {"running": False, "process_count": 0, "processes": []}
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "gui", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["running"] is False

    def test_analyze_summary_skip_export_json(self, tmp_path):
        from cli_anything.unrealinsights.unrealinsights_cli import cli

        (tmp_path / "timer_stats.csv").write_text("Timer Name,Total Time\nTick,1.0\n", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "analyze", "summary", "--skip-export", "--out", str(tmp_path)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["summary"]["top_timers"][0]["name"] == "Tick"


class TestREPLSessionState:
    def test_trace_set_then_info_in_repl(self):
        from cli_anything.unrealinsights.unrealinsights_cli import cli

        with patch(
            "cli_anything.unrealinsights.utils.repl_skin.ReplSkin.create_prompt_session",
            return_value=None,
        ):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                input="trace set sample.utrace\ntrace info\nquit\n",
            )
        assert result.exit_code == 0
        assert "sample.utrace" in result.output


class TestCaptureCLIConvenience:
    @patch("cli_anything.unrealinsights.unrealinsights_cli.run_capture")
    def test_capture_run_with_project_and_engine_root(self, mock_run_capture, tmp_path):
        from cli_anything.unrealinsights.unrealinsights_cli import cli

        editor = tmp_path / "UE_5.5" / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"
        editor.parent.mkdir(parents=True)
        editor.write_text("x", encoding="utf-8")
        project = tmp_path / "Project" / "MyGame.uproject"
        project.parent.mkdir(parents=True)
        project.write_text("{}", encoding="utf-8")

        mock_run_capture.return_value = {
            "command": [str(editor.resolve()), str(project.resolve()), "-trace=default"],
            "waited": True,
            "timed_out": False,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "pid": None,
            "target_exe": str(editor.resolve()),
            "target_args": [str(project.resolve())],
            "trace_path": str((tmp_path / "capture.utrace").resolve()),
            "channels": "default",
            "trace_exists": True,
            "trace_size": 10,
            "succeeded": True,
        }

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--json",
                "capture",
                "run",
                "--project",
                str(project),
                "--engine-root",
                str(tmp_path / "UE_5.5"),
                "--output-trace",
                str(tmp_path / "capture.utrace"),
                "--wait",
            ],
        )
        assert result.exit_code == 0
        mock_run_capture.assert_called_once()
        _, kwargs = mock_run_capture.call_args
        assert kwargs["target_args"][0] == str(project.resolve())

    @patch("cli_anything.unrealinsights.unrealinsights_cli.run_capture")
    def test_capture_start_persists_background_session(self, mock_run_capture, tmp_path):
        from cli_anything.unrealinsights.unrealinsights_cli import cli
        from cli_anything.unrealinsights.core.session import UnrealInsightsSession

        editor = tmp_path / "UE_5.5" / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"
        editor.parent.mkdir(parents=True)
        editor.write_text("x", encoding="utf-8")
        project = tmp_path / "Project" / "MyGame.uproject"
        project.parent.mkdir(parents=True)
        project.write_text("{}", encoding="utf-8")

        mock_run_capture.return_value = {
            "command": [str(editor.resolve()), str(project.resolve()), "-trace=default"],
            "waited": False,
            "timed_out": False,
            "exit_code": None,
            "stdout": None,
            "stderr": None,
            "pid": 2468,
            "target_exe": str(editor.resolve()),
            "target_args": [str(project.resolve())],
            "trace_path": str((tmp_path / "capture.utrace").resolve()),
            "channels": "default",
            "trace_exists": False,
            "trace_size": None,
            "succeeded": True,
        }

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--json",
                "capture",
                "start",
                "--project",
                str(project),
                "--engine-root",
                str(tmp_path / "UE_5.5"),
                "--output-trace",
                str(tmp_path / "capture.utrace"),
            ],
        )
        assert result.exit_code == 0
        session = UnrealInsightsSession.load()
        assert session.capture_pid == 2468

    @patch("cli_anything.unrealinsights.unrealinsights_cli.capture_status")
    @patch("cli_anything.unrealinsights.unrealinsights_cli.run_capture")
    def test_capture_start_refuses_running_session_without_replace(self, mock_run_capture, mock_capture_status):
        from cli_anything.unrealinsights.unrealinsights_cli import cli

        mock_capture_status.return_value = {
            "active": True,
            "pid": 1357,
            "running": True,
            "target_exe": "C:/UE/UnrealEditor.exe",
            "target_args": [],
            "project_path": "C:/Project.uproject",
            "engine_root": "C:/UE_5.5",
            "trace_path": "C:/capture.utrace",
            "trace_exists": True,
            "trace_size": 1024,
            "channels": "default",
            "started_at": "2026-04-16T00:00:00+00:00",
        }

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--json",
                "capture",
                "start",
                "--project",
                "C:/Project.uproject",
                "--engine-root",
                "C:/UE_5.5",
            ],
        )
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "--replace" in data["error"]
        mock_run_capture.assert_not_called()

    @patch("cli_anything.unrealinsights.unrealinsights_cli.stop_capture")
    @patch("cli_anything.unrealinsights.unrealinsights_cli.capture_status")
    @patch("cli_anything.unrealinsights.unrealinsights_cli.run_capture")
    def test_capture_start_replace_stops_existing_session(self, mock_run_capture, mock_capture_status, mock_stop_capture, tmp_path):
        from cli_anything.unrealinsights.unrealinsights_cli import cli
        from cli_anything.unrealinsights.core.session import UnrealInsightsSession

        editor = tmp_path / "UE_5.5" / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"
        editor.parent.mkdir(parents=True)
        editor.write_text("x", encoding="utf-8")
        project = tmp_path / "Project" / "MyGame.uproject"
        project.parent.mkdir(parents=True)
        project.write_text("{}", encoding="utf-8")

        mock_capture_status.return_value = {
            "active": True,
            "pid": 1357,
            "running": True,
            "target_exe": str(editor.resolve()),
            "target_args": [str(project.resolve())],
            "project_path": str(project.resolve()),
            "engine_root": str((tmp_path / "UE_5.5").resolve()),
            "trace_path": str((tmp_path / "previous.utrace").resolve()),
            "trace_exists": True,
            "trace_size": 1024,
            "channels": "default",
            "started_at": "2026-04-16T00:00:00+00:00",
        }
        mock_stop_capture.return_value = {
            "termination": {"requested_pid": 1357, "stopped": True, "exit_code": 0},
            "capture": {"active": False},
        }
        mock_run_capture.return_value = {
            "command": [str(editor.resolve()), str(project.resolve()), "-trace=default"],
            "waited": False,
            "timed_out": False,
            "exit_code": None,
            "stdout": None,
            "stderr": None,
            "pid": 2468,
            "target_exe": str(editor.resolve()),
            "target_args": [str(project.resolve())],
            "trace_path": str((tmp_path / "capture.utrace").resolve()),
            "channels": "default",
            "trace_exists": False,
            "trace_size": None,
            "succeeded": True,
        }

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--json",
                "capture",
                "start",
                "--replace",
                "--project",
                str(project),
                "--engine-root",
                str(tmp_path / "UE_5.5"),
                "--output-trace",
                str(tmp_path / "capture.utrace"),
            ],
        )
        assert result.exit_code == 0
        mock_stop_capture.assert_called_once()
        session = UnrealInsightsSession.load()
        assert session.capture_pid == 2468
