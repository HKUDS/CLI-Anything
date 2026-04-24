"""Unit tests for cli-anything-nsight-graphics."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from cli_anything.nsight_graphics.core import cpp_capture, frame, gpu_trace, launch
from cli_anything.nsight_graphics.utils import nsight_graphics_backend as backend
from cli_anything.nsight_graphics.utils.errors import handle_error
from cli_anything.nsight_graphics.utils.output import output_json

SAMPLE_HELP = """
NVIDIA Nsight Graphics [general_options] [activity_options]:

General Options:
  --hostname arg                        Host name of remote connection
  --project arg                         Nsight project file to load
  --output-dir arg                      Output folder to export/write data to
  --activity arg                        Target activity to use, should be one of:
                                          Frame Debugger
                                          Generate C++ Capture
                                          GPU Trace Profiler
  --platform arg                        Target platform to use, should be one of:
                                          Windows
  --launch-detached                     Run as a command line launcher
  --attach-pid arg                      PID to connect to
  --exe arg                             Executable path to be launched with the tool injected
  --dir arg                             Working directory of launched application
  --args arg                            Command-line arguments of launched application
  --env arg                             Environment variables of launched application

Frame Debugger activity options:
  --wait-frames arg                     Wait in frames before capturing a frame
  --wait-seconds arg                    Wait in time (seconds) before capturing a frame
  --wait-hotkey                         Wait for hotkey
  --export-frame-perf-metrics           Export metrics

Generate C++ Capture activity options:
  --wait-seconds arg                    Wait in time (seconds) before capturing a frame
  --wait-hotkey                         Wait for hotkey

GPU Trace Profiler activity options:
  --start-after-frames arg              Wait N frames before generating GPU trace
  --start-after-ms arg                  Wait N milliseconds before generating GPU trace
  --limit-to-frames arg                 Trace a maximum of N frames
  --auto-export                         Automatically export metrics data after generating GPU trace
  --architecture arg                    Selects which architecture the options configure
  --metric-set-id arg                   Metric set id
  --multi-pass-metrics                  Enable multi-pass metrics
  --real-time-shader-profiler           Enable shader profiler
"""


class TestOutputAndErrors:
    def test_output_json(self):
        buffer = io.StringIO()
        output_json({"key": "value", "num": 42}, file=buffer)
        payload = json.loads(buffer.getvalue())
        assert payload["key"] == "value"
        assert payload["num"] == 42

    def test_handle_error_debug(self):
        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            payload = handle_error(exc, debug=True)
        assert payload["type"] == "RuntimeError"
        assert "traceback" in payload


class TestBackendDiscovery:
    def test_default_windows_install_dirs_prefers_higher_version(self):
        with patch("cli_anything.nsight_graphics.utils.backend.discovery._fixed_windows_drive_roots", return_value=["C:", "D:"]):
            result = backend._default_windows_install_dirs(
                lambda pattern: {
                    "C:/Program Files/NVIDIA Corporation/Nsight Graphics */host/windows-desktop-nomad-x64": [
                        "C:/Program Files/NVIDIA Corporation/Nsight Graphics 2023.3.2/host/windows-desktop-nomad-x64"
                    ],
                    "D:/Program Files/NVIDIA Corporation/Nsight Graphics */host/windows-desktop-nomad-x64": [
                        "D:/Program Files/NVIDIA Corporation/Nsight Graphics 2026.1.0/host/windows-desktop-nomad-x64"
                    ],
                    "C:/Program Files (x86)/NVIDIA Corporation/Nsight Graphics */host/windows-desktop-nomad-x64": [],
                    "D:/Program Files (x86)/NVIDIA Corporation/Nsight Graphics */host/windows-desktop-nomad-x64": [],
                }.get(pattern, [])
            )
        assert result[0].startswith("D:/Program Files")

    def test_discover_binaries_from_env_dir(self, tmp_path):
        (tmp_path / "ngfx.exe").write_text("", encoding="utf-8")
        (tmp_path / "ngfx-capture.exe").write_text("", encoding="utf-8")

        result = backend.discover_binaries(
            env={backend.ENV_VAR: str(tmp_path)},
            which=lambda _: None,
            glob_func=lambda _: [],
            platform_system="Windows",
        )

        assert result["binaries"]["ngfx"].endswith("ngfx.exe")
        assert result["binaries"]["ngfx_capture"].endswith("ngfx-capture.exe")
        assert result["effective_override"] == str(tmp_path)

    def test_discover_binaries_prefers_cli_override(self, tmp_path):
        (tmp_path / "ngfx.exe").write_text("", encoding="utf-8")
        result = backend.discover_binaries(
            env={backend.ENV_VAR: "C:/Ignored/FromEnv"},
            nsight_path=str(tmp_path),
            which=lambda _: None,
            glob_func=lambda _: [],
            platform_system="Windows",
        )
        assert result["cli_override"] == str(tmp_path)
        assert result["effective_override"] == str(tmp_path)
        assert result["binaries"]["ngfx"].endswith("ngfx.exe")

    def test_detect_tool_mode(self):
        assert backend.detect_tool_mode({"ngfx": "a", "ngfx_capture": None, "ngfx_replay": None}) == "unified"
        assert backend.detect_tool_mode({"ngfx": None, "ngfx_capture": "a", "ngfx_replay": None}) == "split"
        assert backend.detect_tool_mode({"ngfx": None, "ngfx_capture": None, "ngfx_replay": None}) == "missing"

    def test_list_installations_reports_versions(self, tmp_path):
        install_dir = tmp_path / "Nsight Graphics 2025.1" / "host" / "windows-desktop-nomad-x64"
        install_dir.mkdir(parents=True)
        (install_dir / "ngfx.exe").write_text("", encoding="utf-8")
        (install_dir / "ngfx-ui.exe").write_text("", encoding="utf-8")

        with patch("cli_anything.nsight_graphics.utils.backend.discovery._read_registry_installations", return_value=[]):
            result = backend.list_installations(
                env={},
                nsight_path=str(install_dir),
                which=lambda _: None,
                glob_func=lambda _: [str(install_dir)],
                platform_system="Windows",
            )

        assert result["count"] == 1
        assert result["installations"][0]["version"] == "2025.1"
        assert result["installations"][0]["selected"] is True

    def test_list_installations_includes_registry_only_entries(self):
        registry_entries = [
            {
                "display_name": "NVIDIA Nsight Graphics 2026.1.0",
                "display_version": "26.1.26068.0509",
                "install_location": None,
                "install_source": "C:/Users/Test/Downloads",
                "uninstall_string": "msiexec /x ...",
                "publisher": "NVIDIA Corporation",
                "registry_key": r"HKLM\SOFTWARE\...\{ABC}",
            }
        ]
        with patch("cli_anything.nsight_graphics.utils.backend.discovery._read_registry_installations", return_value=registry_entries):
            result = backend.list_installations(
                env={},
                which=lambda _: None,
                glob_func=lambda _: [],
                platform_system="Windows",
            )

        assert result["count"] == 1
        assert result["registry_count"] == 1
        assert result["installations"][0]["version"] == "2026.1.0"
        assert result["installations"][0]["registered_only"] is True
        assert result["installations"][0]["tool_mode"] == "registered-only"

    def test_list_installations_merges_registry_metadata_into_filesystem_entry(self, tmp_path):
        install_root = tmp_path / "Nsight Graphics 2025.1"
        install_dir = install_root / "host" / "windows-desktop-nomad-x64"
        install_dir.mkdir(parents=True)
        (install_dir / "ngfx.exe").write_text("", encoding="utf-8")

        registry_entries = [
            {
                "display_name": "NVIDIA Nsight Graphics 2025.1",
                "display_version": "25.1.0",
                "install_location": str(install_root),
                "install_source": "C:/Installers",
                "uninstall_string": "msiexec /x ...",
                "publisher": "NVIDIA Corporation",
                "registry_key": r"HKLM\SOFTWARE\...\{DEF}",
            }
        ]
        with patch("cli_anything.nsight_graphics.utils.backend.discovery._read_registry_installations", return_value=registry_entries):
            result = backend.list_installations(
                env={},
                nsight_path=str(install_dir),
                which=lambda _: None,
                glob_func=lambda _: [str(install_dir)],
                platform_system="Windows",
            )

        assert result["count"] == 1
        assert result["registry_count"] == 1
        assert result["installations"][0]["registered_only"] is False
        assert result["installations"][0]["display_name"] == "NVIDIA Nsight Graphics 2025.1"
        assert "registry" in result["installations"][0]["discovery_sources"]

    def test_list_installations_promotes_newer_drive_install(self, tmp_path):
        c_dir = tmp_path / "CDrive" / "Nsight Graphics 2023.3.2" / "host" / "windows-desktop-nomad-x64"
        d_dir = tmp_path / "DDrive" / "Nsight Graphics 2026.1.0" / "host" / "windows-desktop-nomad-x64"
        c_dir.mkdir(parents=True)
        d_dir.mkdir(parents=True)
        (c_dir / "ngfx.exe").write_text("", encoding="utf-8")
        (d_dir / "ngfx.exe").write_text("", encoding="utf-8")

        with patch("cli_anything.nsight_graphics.utils.backend.discovery._fixed_windows_drive_roots", return_value=["C:", "D:"]), \
             patch("cli_anything.nsight_graphics.utils.backend.discovery._read_registry_installations", return_value=[]):
            result = backend.list_installations(
                env={},
                which=lambda _: None,
                glob_func=lambda pattern: {
                    "C:/Program Files/NVIDIA Corporation/Nsight Graphics */host/windows-desktop-nomad-x64": [str(c_dir).replace("\\", "/")],
                    "D:/Program Files/NVIDIA Corporation/Nsight Graphics */host/windows-desktop-nomad-x64": [str(d_dir).replace("\\", "/")],
                    "C:/Program Files (x86)/NVIDIA Corporation/Nsight Graphics */host/windows-desktop-nomad-x64": [],
                    "D:/Program Files (x86)/NVIDIA Corporation/Nsight Graphics */host/windows-desktop-nomad-x64": [],
                }.get(pattern, []),
                platform_system="Windows",
            )

        assert result["installations"][0]["version"] == "2026.1.0"


class TestHelpParsing:
    def test_parse_unified_help_extracts_activities_and_options(self):
        result = backend.parse_unified_help(SAMPLE_HELP)
        assert result["activities"] == [
            "Frame Debugger",
            "Generate C++ Capture",
            "GPU Trace Profiler",
        ]
        assert result["platforms"] == ["Windows"]
        assert "--project" in result["general_options"]
        assert "--wait-frames" in result["activity_options"]["Frame Debugger"]
        assert "--metric-set-id" in result["activity_options"]["GPU Trace Profiler"]

    def test_resolve_activity_name_maps_legacy_frame_debugger_to_graphics_capture(self):
        report = {
            "supported_activities": [
                "Graphics Capture",
                "Generate C++ Capture",
                "GPU Trace Profiler",
            ]
        }
        assert backend.resolve_activity_name(report, "Frame Debugger") == "Graphics Capture"
        assert backend.resolve_activity_name(report, "Graphics Capture") == "Graphics Capture"


class TestCommandBuilders:
    def test_build_unified_command_formats_args_and_env(self):
        command = backend.build_unified_command(
            {"ngfx": "C:/Nsight/ngfx.exe"},
            activity="Frame Debugger",
            project="demo.ngfx-proj",
            output_dir="D:/out",
            hostname="localhost",
            platform_name="Windows",
            exe="C:/demo.exe",
            working_dir="C:/demo",
            args=["--flag", "value with spaces"],
            envs=["A=1", "B=two"],
            launch_detached=True,
            extra_args=["--wait-frames", "10"],
        )
        assert command[0] == "C:/Nsight/ngfx.exe"
        assert "--launch-detached" in command
        assert "--args" in command
        assert "--env" in command
        assert "value with spaces" in command[command.index("--args") + 1]
        assert command[command.index("--env") + 1].endswith(";")

    def test_build_split_capture_command_maps_wait_seconds(self):
        command = backend.build_split_capture_command(
            {"ngfx_capture": "C:/Nsight/ngfx-capture.exe"},
            exe="C:/demo.exe",
            wait_seconds=3,
            wait_frames=None,
            wait_hotkey=False,
        )
        assert command[0] == "C:/Nsight/ngfx-capture.exe"
        assert "--capture-countdown-timer" in command
        assert command[command.index("--capture-countdown-timer") + 1] == "3000"

    @patch("cli_anything.nsight_graphics.utils.backend.execution.subprocess.run")
    def test_run_command_suppresses_graphics_capture_suggestion_dialog(self, run_mock):
        run_mock.return_value = type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        backend.run_command(["C:/Nsight/ngfx.exe", "--help"])
        assert run_mock.call_args.kwargs["env"]["NSIGHT_SUGGEST_GRAPHICS_CAPTURE"] == "0"

    def test_diff_snapshots_reports_new_nonempty_files(self, tmp_path):
        before = backend.snapshot_files([str(tmp_path)])
        artifact = tmp_path / "capture.ngfx-capture"
        artifact.write_text("data", encoding="utf-8")
        after = backend.snapshot_files([str(tmp_path)])
        diff = backend.diff_snapshots(before, after)
        assert len(diff) == 1
        assert diff[0]["path"].endswith("capture.ngfx-capture")
        assert diff[0]["size"] > 0

    def test_activity_artifact_roots_keeps_default_graphics_capture_location(self):
        roots = backend.activity_artifact_roots("Graphics Capture", "D:/captures")
        assert str(Path("D:/captures").resolve()) in roots
        assert any(root.endswith("Documents\\NVIDIA Nsight Graphics") for root in roots)
        assert any(root.endswith("Documents\\NVIDIA Nsight Graphics\\GraphicsCaptures") for root in roots)

    def test_gpu_trace_summary_from_export_dir(self, tmp_path):
        base = tmp_path / "BASE"
        base.mkdir()
        (base / "FRAME.xls").write_text("GPU frame time\t31.0446\n", encoding="utf-8")
        (base / "GPUTRACE_FRAME.xls").write_text(
            "\n".join(
                [
                    "FE_B.TriageAC.fe__draw_count.sum\t309",
                    "FE_A.TriageAC.gr__dispatch_count.sum\t2561",
                    "FE_B.TriageAC.gr__cycles_active.avg.pct_of_peak_sustained_elapsed\t98.1079",
                    "FE_A.TriageAC.gr__compute_cycles_active_queue_sync.avg.pct_of_peak_sustained_elapsed\t84.24",
                    "TriageAC.sm__throughput.avg.pct_of_peak_sustained_elapsed\t23.6331",
                    "LTS.TriageAC.lts__throughput.avg.pct_of_peak_sustained_elapsed\t32.0437",
                    "FBSP.TriageAC.dramc__throughput.avg.pct_of_peak_sustained_elapsed\t19.5897",
                ]
            ),
            encoding="utf-8",
        )
        (base / "D3DPERF_EVENTS.xls").write_text(
            "event_text\ttime_ms\n"
            "Frame 1221\t31.0431\n"
            "Scene\t29.9644\n"
            "        DirectLighting\t15.3828\n"
            "        ReSTIRDI\t14.0627\n",
            encoding="utf-8",
        )

        summary = gpu_trace.summarize_export_dir(str(tmp_path), top_n=3)
        assert summary["frame_time_ms"] == pytest.approx(31.0446)
        assert summary["fps_estimate"] == pytest.approx(1000.0 / 31.0446)
        assert summary["metrics"]["draw_count"] == 309
        assert summary["metrics"]["dispatch_count"] == 2561
        assert summary["top_events"][0]["event"] == "Scene"
        assert summary["top_events"][1]["event"] == "DirectLighting"
        assert summary["highlights"]

    def test_gpu_trace_summary_prefers_newest_complete_export_dir(self, tmp_path):
        old_export = tmp_path / "A_old_export"
        new_export = tmp_path / "B_new_export"
        old_export.mkdir()
        new_export.mkdir()

        old_files = {
            "frame": old_export / "FRAME.xls",
            "trace": old_export / "GPUTRACE_FRAME.xls",
            "events": old_export / "D3DPERF_EVENTS.xls",
        }
        old_files["frame"].write_text("GPU frame time\t40.0\n", encoding="utf-8")
        old_files["trace"].write_text(
            "FE_B.TriageAC.fe__draw_count.sum\t10\n",
            encoding="utf-8",
        )
        old_files["events"].write_text(
            "event_text\ttime_ms\nFrame 1\t40.0\nOldPass\t30.0\n",
            encoding="utf-8",
        )

        new_files = {
            "frame": new_export / "FRAME.xls",
            "trace": new_export / "GPUTRACE_FRAME.xls",
            "events": new_export / "D3DPERF_EVENTS.xls",
        }
        new_files["frame"].write_text("GPU frame time\t12.5\n", encoding="utf-8")
        new_files["trace"].write_text(
            "FE_B.TriageAC.fe__draw_count.sum\t123\n",
            encoding="utf-8",
        )
        new_files["events"].write_text(
            "event_text\ttime_ms\nFrame 2\t12.5\nNewPass\t8.5\n",
            encoding="utf-8",
        )

        for path in old_files.values():
            os.utime(path, ns=(1_000_000_000, 1_000_000_000))
        for path in new_files.values():
            os.utime(path, ns=(2_000_000_000, 2_000_000_000))

        summary = gpu_trace.summarize_export_dir(str(tmp_path), top_n=3)

        assert summary["output_dir"] == str(new_export.resolve())
        assert summary["search_root"] == str(tmp_path.resolve())
        assert summary["frame_time_ms"] == pytest.approx(12.5)
        assert summary["metrics"]["draw_count"] == 123
        assert summary["top_events"][0]["event"] == "NewPass"
        assert Path(summary["files"]["frame"]).parent == new_export.resolve()
        assert Path(summary["files"]["trace_frame"]).parent == new_export.resolve()
        assert Path(summary["files"]["events"]).parent == new_export.resolve()


class TestCoreModules:
    @patch("cli_anything.nsight_graphics.core.frame.backend.run_with_artifacts")
    @patch("cli_anything.nsight_graphics.core.frame.backend.build_unified_command")
    @patch("cli_anything.nsight_graphics.core.frame.backend.probe_installation")
    def test_frame_capture_uses_unified_ngfx(self, probe_mock, build_mock, run_mock):
        probe_mock.return_value = {
            "binaries": {"ngfx": "C:/Nsight/ngfx.exe", "ngfx_capture": None, "ngfx_replay": None},
        }
        build_mock.return_value = ["C:/Nsight/ngfx.exe", "--activity", "Frame Debugger"]
        run_mock.return_value = {
            "ok": True,
            "returncode": 0,
            "stdout": "",
            "stderr": "",
            "command": "ngfx",
            "artifacts": [{"path": "D:/out/capture.ngfx-capture", "size": 10, "mtime_ns": 1}],
        }

        result = frame.capture_frame(
            nsight_path=None,
            project=None,
            output_dir="D:/out",
            hostname=None,
            platform_name=None,
            exe="C:/demo.exe",
            working_dir=None,
            args=(),
            envs=(),
            wait_seconds=None,
            wait_frames=10,
            wait_hotkey=False,
            export_frame_perf_metrics=False,
            export_range_perf_metrics=False,
        )

        assert build_mock.called
        assert result["tool_mode"] == "unified"
        assert result["activity"] == "Frame Debugger"
        assert result["artifacts"]

    @patch("cli_anything.nsight_graphics.core.frame.backend.run_with_artifacts")
    @patch("cli_anything.nsight_graphics.core.frame.backend.build_unified_command")
    @patch("cli_anything.nsight_graphics.core.frame.backend.probe_installation")
    def test_frame_capture_maps_graphics_capture_options(self, probe_mock, build_mock, run_mock):
        probe_mock.return_value = {
            "binaries": {"ngfx": "C:/Nsight/ngfx.exe", "ngfx_capture": None, "ngfx_replay": None},
            "supported_activities": ["Graphics Capture", "GPU Trace Profiler"],
        }
        build_mock.return_value = ["C:/Nsight/ngfx.exe", "--activity", "Graphics Capture"]
        run_mock.return_value = {
            "ok": True,
            "returncode": 0,
            "stdout": "",
            "stderr": "",
            "command": "ngfx",
            "artifacts": [{"path": "D:/out/capture.ngfx-capture", "size": 10, "mtime_ns": 1}],
        }

        result = frame.capture_frame(
            nsight_path=None,
            project=None,
            output_dir="D:/out",
            hostname=None,
            platform_name=None,
            exe="C:/demo.exe",
            working_dir=None,
            args=(),
            envs=(),
            wait_seconds=1,
            wait_frames=None,
            wait_hotkey=False,
            export_frame_perf_metrics=False,
            export_range_perf_metrics=False,
        )

        assert build_mock.call_args.kwargs["activity"] == "Graphics Capture"
        assert build_mock.call_args.kwargs["extra_args"] == ["--frame-count", "1", "--elapsed-time", "1"]
        assert result["activity"] == "Graphics Capture"

    @patch("cli_anything.nsight_graphics.core.frame.backend.probe_installation")
    def test_frame_capture_split_mode_rejects_perf_exports(self, probe_mock):
        probe_mock.return_value = {
            "binaries": {"ngfx": None, "ngfx_capture": "C:/Nsight/ngfx-capture.exe", "ngfx_replay": None},
        }
        with pytest.raises(RuntimeError, match="Frame performance export flags"):
            frame.capture_frame(
                nsight_path=None,
                project=None,
                output_dir=None,
                hostname=None,
                platform_name=None,
                exe="C:/demo.exe",
                working_dir=None,
                args=(),
                envs=(),
                wait_seconds=None,
                wait_frames=1,
                wait_hotkey=False,
                export_frame_perf_metrics=True,
                export_range_perf_metrics=False,
            )

    @patch("cli_anything.nsight_graphics.core.gpu_trace.backend.probe_installation")
    def test_gpu_trace_requires_arch_for_metric_set(self, probe_mock):
        probe_mock.return_value = {
            "binaries": {"ngfx": "C:/Nsight/ngfx.exe", "ngfx_capture": None, "ngfx_replay": None},
        }
        with pytest.raises(ValueError, match="requires --architecture"):
            gpu_trace.capture_trace(
                nsight_path=None,
                project=None,
                output_dir=None,
                hostname=None,
                platform_name=None,
                exe="C:/demo.exe",
                working_dir=None,
                args=(),
                envs=(),
                start_after_frames=1,
                start_after_submits=None,
                start_after_ms=None,
                start_after_hotkey=False,
                max_duration_ms=None,
                limit_to_frames=1,
                limit_to_submits=None,
                auto_export=False,
                architecture=None,
                metric_set_id="1",
                multi_pass_metrics=False,
                real_time_shader_profiler=False,
            )

    @patch("cli_anything.nsight_graphics.core.launch.backend.run_command")
    @patch("cli_anything.nsight_graphics.core.launch.backend.build_unified_command")
    @patch("cli_anything.nsight_graphics.core.launch.backend.probe_installation")
    def test_launch_attach_returns_unified_result(self, probe_mock, build_mock, run_mock):
        probe_mock.return_value = {
            "binaries": {"ngfx": "C:/Nsight/ngfx.exe", "ngfx_capture": None, "ngfx_replay": None},
        }
        build_mock.return_value = ["C:/Nsight/ngfx.exe", "--attach-pid", "123"]
        run_mock.return_value = {
            "ok": True,
            "returncode": 0,
            "stdout": "",
            "stderr": "",
            "command": "ngfx",
        }

        result = launch.attach(
            nsight_path=None,
            activity="Frame Debugger",
            pid=123,
            project=None,
            output_dir=None,
            hostname=None,
            platform_name=None,
        )
        assert result["tool_mode"] == "unified"
        assert result["pid"] == 123

    @patch("cli_anything.nsight_graphics.core.cpp_capture.backend.run_with_artifacts")
    @patch("cli_anything.nsight_graphics.core.cpp_capture.backend.build_unified_command")
    @patch("cli_anything.nsight_graphics.core.cpp_capture.backend.probe_installation")
    def test_cpp_capture_sets_activity(self, probe_mock, build_mock, run_mock):
        probe_mock.return_value = {
            "binaries": {"ngfx": "C:/Nsight/ngfx.exe", "ngfx_capture": None, "ngfx_replay": None},
        }
        build_mock.return_value = ["C:/Nsight/ngfx.exe", "--activity", "Generate C++ Capture"]
        run_mock.return_value = {
            "ok": True,
            "returncode": 0,
            "stdout": "",
            "stderr": "",
            "command": "ngfx",
            "artifacts": [],
        }
        result = cpp_capture.capture_cpp(
            nsight_path=None,
            project=None,
            output_dir="D:/out",
            hostname=None,
            platform_name=None,
            exe="C:/demo.exe",
            working_dir=None,
            args=(),
            envs=(),
            wait_seconds=5,
            wait_hotkey=False,
        )
        assert result["activity"] == "Generate C++ Capture"
        assert result["tool_mode"] == "unified"

    @patch("cli_anything.nsight_graphics.core.gpu_trace.backend.run_with_artifacts")
    @patch("cli_anything.nsight_graphics.core.gpu_trace.backend.build_unified_command")
    @patch("cli_anything.nsight_graphics.core.gpu_trace.backend.probe_installation")
    def test_gpu_trace_capture_with_summary(self, probe_mock, build_mock, run_mock, tmp_path):
        base = tmp_path / "BASE"
        base.mkdir()
        (base / "FRAME.xls").write_text("GPU frame time\t16.0\n", encoding="utf-8")
        (base / "GPUTRACE_FRAME.xls").write_text(
            "FE_B.TriageAC.fe__draw_count.sum\t100\nFE_A.TriageAC.gr__dispatch_count.sum\t50\n",
            encoding="utf-8",
        )
        (base / "D3DPERF_EVENTS.xls").write_text(
            "event_text\ttime_ms\nFrame 1\t16.0\nScene\t10.0\n",
            encoding="utf-8",
        )

        probe_mock.return_value = {
            "binaries": {"ngfx": "C:/Nsight/ngfx.exe", "ngfx_capture": None, "ngfx_replay": None},
        }
        build_mock.return_value = ["C:/Nsight/ngfx.exe", "--activity", "GPU Trace Profiler"]
        run_mock.return_value = {
            "ok": True,
            "returncode": 0,
            "stdout": "",
            "stderr": "",
            "command": "ngfx",
            "artifacts": [],
            "artifact_count": 0,
        }

        result = gpu_trace.capture_trace(
            nsight_path=None,
            project=None,
            output_dir=str(tmp_path),
            hostname=None,
            platform_name=None,
            exe="C:/demo.exe",
            working_dir=None,
            args=(),
            envs=(),
            start_after_frames=1,
            start_after_submits=None,
            start_after_ms=None,
            start_after_hotkey=False,
            max_duration_ms=None,
            limit_to_frames=1,
            limit_to_submits=None,
            auto_export=False,
            architecture=None,
            metric_set_id=None,
            multi_pass_metrics=False,
            real_time_shader_profiler=False,
            summarize=True,
            summary_limit=5,
        )

        assert result["auto_export"] is True
        assert result["summary"]["frame_time_ms"] == pytest.approx(16.0)
        assert result["summary"]["top_events"][0]["event"] == "Scene"


class TestCLIHelp:
    def test_root_help(self):
        from click.testing import CliRunner
        from cli_anything.nsight_graphics.nsight_graphics_cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Nsight Graphics CLI" in result.output
        assert "--nsight-path" in result.output

    def test_nsight_path_is_forwarded_to_doctor(self):
        from click.testing import CliRunner
        from cli_anything.nsight_graphics.nsight_graphics_cli import cli

        runner = CliRunner()
        with patch("cli_anything.nsight_graphics.nsight_graphics_cli.doctor.get_installation_report") as doctor_mock:
            doctor_mock.return_value = {
                "ok": True,
                "compatibility_mode": "unified",
                "resolved_executable": "C:/Custom/ngfx.exe",
                "supported_activities": [],
                "warnings": [],
            }
            result = runner.invoke(cli, ["--json", "--nsight-path", "C:/Custom/NG", "doctor", "info"])

        assert result.exit_code == 0
        doctor_mock.assert_called_once_with(nsight_path="C:/Custom/NG")

    @pytest.mark.parametrize(
        ("args", "needle"),
        [
            (["doctor", "--help"], "info"),
            (["doctor", "--help"], "versions"),
            (["launch", "--help"], "detached"),
            (["frame", "--help"], "capture"),
            (["gpu-trace", "--help"], "capture"),
            (["gpu-trace", "--help"], "summarize"),
            (["cpp", "--help"], "capture"),
        ],
    )
    def test_group_help(self, args, needle):
        from click.testing import CliRunner
        from cli_anything.nsight_graphics.nsight_graphics_cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, args)
        assert result.exit_code == 0
        assert needle in result.output


class TestCLISubprocess:
    def test_cli_help_subprocess(self):
        harness_root = Path(__file__).resolve().parents[3]
        result = subprocess.run(
            [sys.executable, "-m", "cli_anything.nsight_graphics.nsight_graphics_cli", "--help"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(harness_root),
        )
        assert result.returncode == 0
        assert "Nsight Graphics CLI" in result.stdout
