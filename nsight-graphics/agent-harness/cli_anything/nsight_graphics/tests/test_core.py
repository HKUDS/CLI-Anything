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

from cli_anything.nsight_graphics.core import cpp_capture, frame, gpu_trace, launch, replay
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
                                          Graphics Capture
                                          OpenGL Frame Debugger
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

Graphics Capture activity options:
  --frame-count arg                     Capture N frames
  --hotkey-capture                      Wait for hotkey
  --frame-index arg                     Capture frame index
  --elapsed-time arg                    Wait in time (seconds) before capturing

OpenGL Frame Debugger activity options:
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
        with patch("cli_anything.nsight_graphics.utils.nsight_graphics_backend._fixed_windows_drive_roots", return_value=["C:", "D:"]):
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
        assert backend.detect_tool_mode({"ngfx": "a", "ngfx_capture": "b", "ngfx_replay": "c"}) == "unified+split"
        assert backend.detect_tool_mode({"ngfx": None, "ngfx_capture": "a", "ngfx_replay": None}) == "split"
        assert backend.detect_tool_mode({"ngfx": None, "ngfx_capture": None, "ngfx_replay": None}) == "missing"

    def test_prepare_output_dir_creates_missing_directory(self, tmp_path):
        output_dir = tmp_path / "new" / "capture-output"
        assert not output_dir.exists()
        resolved = backend.prepare_output_dir(str(output_dir))
        assert resolved == str(output_dir.resolve())
        assert output_dir.is_dir()

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

        with patch("cli_anything.nsight_graphics.utils.nsight_graphics_backend._fixed_windows_drive_roots", return_value=["C:", "D:"]), \
             patch("cli_anything.nsight_graphics.utils.nsight_graphics_backend._read_registry_installations", return_value=[]):
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
            "Graphics Capture",
            "OpenGL Frame Debugger",
            "Generate C++ Capture",
            "GPU Trace Profiler",
        ]
        assert result["platforms"] == ["Windows"]
        assert "--project" in result["general_options"]
        assert "--frame-index" in result["activity_options"]["Graphics Capture"]
        assert "--wait-frames" in result["activity_options"]["OpenGL Frame Debugger"]
        assert "--metric-set-id" in result["activity_options"]["GPU Trace Profiler"]


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

    def test_build_replay_command_uses_capture_file_as_positional(self):
        command = backend.build_replay_command(
            {"ngfx_replay": "C:/Nsight/ngfx-replay.exe"},
            capture_file="D:/captures/frame.ngfx-capture",
            extra_args=["--metadata"],
        )
        assert command == [
            "C:/Nsight/ngfx-replay.exe",
            "--metadata",
            "D:/captures/frame.ngfx-capture",
        ]

    def test_diff_snapshots_reports_new_nonempty_files(self, tmp_path):
        before = backend.snapshot_files([str(tmp_path)])
        artifact = tmp_path / "capture.ngfx-capture"
        artifact.write_text("data", encoding="utf-8")
        after = backend.snapshot_files([str(tmp_path)])
        diff = backend.diff_snapshots(before, after)
        assert len(diff) == 1
        assert diff[0]["path"].endswith("capture.ngfx-capture")
        assert diff[0]["size"] > 0

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
                    "PCI.TriageAC.pcie__throughput.avg.pct_of_peak_sustained_elapsed\t12.0",
                    "SM_A.TriageAC.sm__inst_executed_realtime.sum\t123456",
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
        (base / "GPUTRACE_REGIMES.xls").write_text(
            "flattened_event_name\tTriageAC.sm__throughput.avg.pct_of_peak_sustained_elapsed\n"
            "Scene\t23.6331\n",
            encoding="utf-8",
        )

        summary = gpu_trace.summarize_export_dir(str(tmp_path), top_n=3)
        assert summary["frame_time_ms"] == pytest.approx(31.0446)
        assert summary["fps_estimate"] == pytest.approx(1000.0 / 31.0446)
        assert summary["metrics"]["draw_count"] == 309
        assert summary["metrics"]["dispatch_count"] == 2561
        assert summary["tables"]["trace_frame"]["metric_count"] == 9
        assert summary["tables"]["events"]["row_count"] == 4
        assert summary["tables"]["regimes"]["row_count"] == 1
        assert summary["metric_inventory"]["metric_count"] == 9
        assert summary["metric_inventory"]["top_pct_of_peak_metrics"][0]["metric"].endswith(
            "gr__cycles_active.avg.pct_of_peak_sustained_elapsed"
        )
        assert summary["top_events"][0]["event"] == "Scene"
        assert summary["top_events"][1]["event"] == "DirectLighting"
        assert summary["analysis"]["workload"]["classification"] == "compute_heavy"
        assert summary["analysis"]["throughput"]["dominant_unit"]["name"] == "graphics_engine"
        assert summary["analysis"]["event_summary"]["event_count"] == 3
        assert any(item["id"] == "frame_budget_60fps" for item in summary["analysis"]["bottlenecks"])
        assert summary["highlights"]

    def test_gpu_trace_summary_reports_empty_event_and_regime_tables(self, tmp_path):
        base = tmp_path / "BASE"
        base.mkdir()
        (base / "FRAME.xls").write_text("GPU frame time\t1.5\n", encoding="utf-8")
        (base / "GPUTRACE_FRAME.xls").write_text(
            "\n".join(
                [
                    "FE_B.TriageAC.fe__draw_count.sum\t38",
                    "FE_A.TriageAC.gr__dispatch_count.sum\t0",
                    "FE_B.TriageAC.gr__cycles_active.avg.pct_of_peak_sustained_elapsed\t12.0",
                    "TriageAC.sm__throughput.avg.pct_of_peak_sustained_elapsed\t3.0",
                    "SM_B.TriageAC.l1tex__t_sector_hit_rate.pct\t96.0",
                ]
            ),
            encoding="utf-8",
        )
        (base / "D3DPERF_EVENTS.xls").write_text("event_text\ttime_ms\n", encoding="utf-8")
        (base / "GPUTRACE_REGIMES.xls").write_text(
            "flattened_event_name\tFE_B.TriageAC.gr__cycles_active.avg.pct_of_peak_sustained_elapsed\n",
            encoding="utf-8",
        )

        summary = gpu_trace.summarize_export_dir(str(tmp_path), top_n=2)

        assert summary["tables"]["events"]["row_count"] == 0
        assert summary["tables"]["regimes"]["present"] is True
        assert summary["tables"]["regimes"]["row_count"] == 0
        assert summary["analysis"]["event_summary"]["event_count"] == 0
        assert summary["analysis"]["frame_budget"]["bucket"] == "within_60fps_budget"
        assert summary["analysis"]["workload"]["classification"] == "mixed"
        assert any("D3DPERF_EVENTS.xls contains no timed GPU event rows" in warning for warning in summary["analysis"]["warnings"])
        assert any("GPUTRACE_REGIMES.xls contains headers" in warning for warning in summary["analysis"]["warnings"])

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
    def test_frame_capture_uses_unified_ngfx(self, probe_mock, build_mock, run_mock, tmp_path):
        probe_mock.return_value = {
            "binaries": {"ngfx": "C:/Nsight/ngfx.exe", "ngfx_capture": None, "ngfx_replay": None},
            "supported_activities": ["Graphics Capture", "OpenGL Frame Debugger"],
            "activity_options": {
                "Graphics Capture": ["--frame-count", "--frame-index", "--elapsed-time", "--hotkey-capture"],
                "OpenGL Frame Debugger": ["--wait-frames", "--wait-seconds", "--wait-hotkey"],
            },
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
            output_dir=str(tmp_path / "out"),
            hostname=None,
            platform_name=None,
            exe="C:/demo.exe",
            working_dir=None,
            args=(),
            envs=(),
            activity=None,
            wait_seconds=None,
            wait_frames=10,
            wait_hotkey=False,
            export_frame_perf_metrics=False,
            export_range_perf_metrics=False,
        )

        assert build_mock.called
        assert build_mock.call_args.kwargs["activity"] == "Graphics Capture"
        assert "--frame-index" in build_mock.call_args.kwargs["extra_args"]
        assert result["tool_mode"] == "unified"
        assert result["activity"] == "Graphics Capture"
        assert result["artifacts"]

    @patch("cli_anything.nsight_graphics.core.frame.backend.run_with_artifacts")
    @patch("cli_anything.nsight_graphics.core.frame.backend.build_unified_command")
    @patch("cli_anything.nsight_graphics.core.frame.backend.probe_installation")
    def test_frame_capture_allows_explicit_opengl_frame_debugger(self, probe_mock, build_mock, run_mock, tmp_path):
        probe_mock.return_value = {
            "binaries": {"ngfx": "C:/Nsight/ngfx.exe", "ngfx_capture": None, "ngfx_replay": None},
            "supported_activities": ["Graphics Capture", "OpenGL Frame Debugger"],
            "activity_options": {
                "Graphics Capture": ["--frame-count", "--frame-index", "--elapsed-time", "--hotkey-capture"],
                "OpenGL Frame Debugger": ["--wait-frames", "--wait-seconds", "--wait-hotkey"],
            },
        }
        build_mock.return_value = ["C:/Nsight/ngfx.exe", "--activity", "OpenGL Frame Debugger"]
        run_mock.return_value = {
            "ok": True,
            "returncode": 0,
            "stdout": "",
            "stderr": "",
            "command": "ngfx",
            "artifacts": [],
        }

        result = frame.capture_frame(
            nsight_path=None,
            project=None,
            output_dir=str(tmp_path / "out"),
            hostname=None,
            platform_name=None,
            exe="C:/demo.exe",
            working_dir=None,
            args=(),
            envs=(),
            activity="OpenGL Frame Debugger",
            wait_seconds=None,
            wait_frames=10,
            wait_hotkey=False,
            export_frame_perf_metrics=False,
            export_range_perf_metrics=False,
        )

        assert build_mock.call_args.kwargs["activity"] == "OpenGL Frame Debugger"
        assert "--wait-frames" in build_mock.call_args.kwargs["extra_args"]
        assert result["activity"] == "OpenGL Frame Debugger"

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
                activity=None,
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
    def test_cpp_capture_sets_activity(self, probe_mock, build_mock, run_mock, tmp_path):
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
            output_dir=str(tmp_path / "out"),
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
            "artifacts": [
                {"path": str(base / "FRAME.xls"), "size": 1, "mtime_ns": 1},
                {"path": str(base / "GPUTRACE_FRAME.xls"), "size": 1, "mtime_ns": 1},
                {"path": str(base / "D3DPERF_EVENTS.xls"), "size": 1, "mtime_ns": 1},
            ],
            "artifact_count": 3,
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

    @patch("cli_anything.nsight_graphics.core.gpu_trace.backend.run_with_artifacts")
    @patch("cli_anything.nsight_graphics.core.gpu_trace.backend.build_unified_command")
    @patch("cli_anything.nsight_graphics.core.gpu_trace.backend.probe_installation")
    def test_gpu_trace_capture_summary_refuses_failed_capture(self, probe_mock, build_mock, run_mock, tmp_path):
        probe_mock.return_value = {
            "binaries": {"ngfx": "C:/Nsight/ngfx.exe", "ngfx_capture": None, "ngfx_replay": None},
        }
        build_mock.return_value = ["C:/Nsight/ngfx.exe", "--activity", "GPU Trace Profiler"]
        run_mock.return_value = {
            "ok": False,
            "returncode": 1,
            "stdout": "",
            "stderr": "capture failed",
            "command": "ngfx",
            "artifacts": [],
            "artifact_count": 0,
        }

        with pytest.raises(RuntimeError, match="refusing to summarize stale"):
            gpu_trace.capture_trace(
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

    @patch("cli_anything.nsight_graphics.core.gpu_trace.backend.run_with_artifacts")
    @patch("cli_anything.nsight_graphics.core.gpu_trace.backend.build_unified_command")
    @patch("cli_anything.nsight_graphics.core.gpu_trace.backend.probe_installation")
    def test_gpu_trace_capture_summary_requires_new_complete_export(self, probe_mock, build_mock, run_mock, tmp_path):
        old_export = tmp_path / "old"
        old_export.mkdir()
        (old_export / "FRAME.xls").write_text("GPU frame time\t16.0\n", encoding="utf-8")
        (old_export / "GPUTRACE_FRAME.xls").write_text("FE_B.TriageAC.fe__draw_count.sum\t1\n", encoding="utf-8")
        (old_export / "D3DPERF_EVENTS.xls").write_text("event_text\ttime_ms\nOldPass\t1.0\n", encoding="utf-8")

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
            "artifacts": [{"path": str(tmp_path / "capture.ngfx-gputrace"), "size": 1, "mtime_ns": 1}],
            "artifact_count": 1,
        }

        with pytest.raises(RuntimeError, match="complete newly exported table set"):
            gpu_trace.capture_trace(
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

    @patch("cli_anything.nsight_graphics.core.replay.backend.run_command")
    @patch("cli_anything.nsight_graphics.core.replay.backend.probe_installation")
    def test_replay_analyze_exports_requested_metadata_logs_screenshot_and_perf(self, probe_mock, run_mock, tmp_path):
        capture_file = tmp_path / "frame.ngfx-capture"
        capture_file.write_text("capture", encoding="utf-8")

        probe_mock.return_value = {
            "version": "2026.1.0",
            "tool_mode": "unified+split",
            "compatibility_mode": "unified+split",
            "binaries": {"ngfx_replay": "C:/Nsight/ngfx-replay.exe"},
        }

        def fake_run(command, timeout=120, cwd=None):
            if "--metadata-screenshot" in command:
                screenshot_path = Path(command[command.index("--metadata-screenshot") + 1])
                screenshot_path.write_bytes(b"png")
                stdout = ""
            elif "--perf-report-dir" in command:
                perf_dir = Path(command[command.index("--perf-report-dir") + 1])
                perf_dir.mkdir(parents=True, exist_ok=True)
                (perf_dir / "report.txt").write_text("perf", encoding="utf-8")
                stdout = ""
            elif "--metadata-functions" in command:
                stdout = json.dumps(
                    [
                        {"function_name": "vkQueueSubmit", "sequence_id": 1, "thread_index": 0},
                        {"function_name": "vkQueueSubmit", "sequence_id": 2, "thread_index": 0},
                        {"function_name": "vkCreateImage", "sequence_id": 3, "thread_index": 1},
                    ]
                )
            elif "--metadata-objects" in command:
                stdout = json.dumps(
                    [
                        {"api": "Vulkan", "object_name": "Device_1", "type_name": "Device", "uid": 1},
                        {"api": "Vulkan", "object_name": "Image_2", "type_name": "Image", "uid": 2},
                        {"api": "Vulkan", "object_name": "Image_3", "type_name": "Image", "uid": 3},
                    ]
                )
            elif "--metadata-logs-errors" in command:
                stdout = "Captured error A\nCaptured error B\n"
            elif "--metadata-logs" in command:
                stdout = "Captured info A\n"
            elif "--metadata" in command:
                stdout = json.dumps(
                    {
                        "nsight_version": "2026.1.0",
                        "captured_frame": "2",
                        "primary_api": "Vulkan",
                        "primary_gpu": "NVIDIA GeForce RTX 4070 Ti",
                        "driver_vendor": "NVIDIA",
                        "driver_version": "591.74",
                        "graphics_apis": {"Vulkan": ["general"]},
                    }
                )
            else:
                stdout = f"{command[1]} output"
            return {
                "ok": True,
                "returncode": 0,
                "stdout": stdout,
                "stderr": "",
                "command": " ".join(command),
            }

        run_mock.side_effect = fake_run

        result = replay.analyze_capture(
            nsight_path=None,
            capture_file=str(capture_file),
            output_dir=str(tmp_path / "analysis"),
            metadata=True,
            logs=True,
            screenshot=True,
            perf_report=True,
        )

        assert result["ok"] is True
        assert result["capture_type"] == "graphics_capture"
        assert result["metadata"]["present"]["functions"] is True
        assert result["metadata"]["present"]["objects"] is True
        assert result["metadata"]["summary"]["primary_api"] == "Vulkan"
        assert result["metadata"]["summary"]["primary_gpu"] == "NVIDIA GeForce RTX 4070 Ti"
        assert result["metadata"]["functions"]["total"] == 3
        assert result["metadata"]["functions"]["top_functions"][0] == {"name": "vkQueueSubmit", "count": 2}
        assert result["metadata"]["objects"]["total"] == 3
        assert result["metadata"]["objects"]["top_types"][0] == {"name": "Image", "count": 2}
        assert result["logs"]["error_line_count"] == 2
        assert result["logs"]["error_summary"] == ["Captured error A", "Captured error B"]
        assert result["screenshot"]["present"] is True
        assert result["perf_report"]["present"] is True
        assert result["analysis"]["summary"]["object_count"] == 3
        assert result["analysis"]["summary"]["function_event_count"] == 3
        assert result["analysis"]["summary"]["log_error_count"] == 2
        assert any("Captured log errors" in warning for warning in result["analysis"]["warnings"])
        commands = [item["command"] for item in result["command_results"]]
        assert any("--metadata-objects" in command for command in commands)
        assert any("--metadata-logs" in command for command in commands)
        assert any("--metadata-screenshot" in command for command in commands)
        assert any("--perf-report-dir" in command for command in commands)

    @patch("cli_anything.nsight_graphics.core.replay.backend.run_command")
    @patch("cli_anything.nsight_graphics.core.replay.backend.probe_installation")
    def test_replay_analyze_defaults_to_metadata_logs_and_perf(self, probe_mock, run_mock, tmp_path):
        capture_file = tmp_path / "trace.ngfx-gputrace"
        capture_file.write_text("trace", encoding="utf-8")
        probe_mock.return_value = {
            "version": "2026.1.0",
            "tool_mode": "unified+split",
            "compatibility_mode": "unified+split",
            "binaries": {"ngfx_replay": "C:/Nsight/ngfx-replay.exe"},
        }

        def fake_run(command, timeout=120, cwd=None):
            if "--perf-report-dir" in command:
                perf_dir = Path(command[command.index("--perf-report-dir") + 1])
                perf_dir.mkdir(parents=True, exist_ok=True)
                (perf_dir / "report.txt").write_text("perf", encoding="utf-8")
                stdout = ""
            else:
                stdout = "output"
            return {
                "ok": True,
                "returncode": 0,
                "stdout": stdout,
                "stderr": "",
                "command": " ".join(command),
            }

        run_mock.side_effect = fake_run

        result = replay.analyze_capture(
            nsight_path=None,
            capture_file=str(capture_file),
            output_dir=str(tmp_path / "analysis"),
            metadata=False,
            logs=False,
            screenshot=False,
            perf_report=False,
        )

        assert result["capture_type"] == "gpu_trace"
        assert result["requested_outputs"] == {
            "metadata": True,
            "logs": True,
            "screenshot": False,
            "perf_report": True,
        }
        assert any(".ngfx-gputrace inputs may not produce metadata" in warning for warning in result["analysis"]["warnings"])

    @patch("cli_anything.nsight_graphics.core.replay.backend.run_command")
    @patch("cli_anything.nsight_graphics.core.replay.backend.probe_installation")
    def test_replay_analyze_filters_no_error_log_marker(self, probe_mock, run_mock, tmp_path):
        capture_file = tmp_path / "frame.ngfx-capture"
        capture_file.write_text("capture", encoding="utf-8")
        probe_mock.return_value = {
            "version": "2026.1.0",
            "tool_mode": "unified+split",
            "compatibility_mode": "unified+split",
            "binaries": {"ngfx_replay": "C:/Nsight/ngfx-replay.exe"},
        }

        def fake_run(command, timeout=120, cwd=None):
            stdout = "No log messages found with severity >= 2\n" if "--metadata-logs-errors" in command else ""
            return {
                "ok": True,
                "returncode": 0,
                "stdout": stdout,
                "stderr": "",
                "command": " ".join(command),
            }

        run_mock.side_effect = fake_run

        result = replay.analyze_capture(
            nsight_path=None,
            capture_file=str(capture_file),
            output_dir=str(tmp_path / "analysis"),
            metadata=False,
            logs=True,
            screenshot=False,
            perf_report=False,
        )

        assert result["ok"] is True
        assert result["logs"]["status"] == "no_errors"
        assert result["logs"]["error_line_count"] == 0
        assert result["logs"]["error_summary"] == []
        assert result["logs"]["raw_error_summary"] == ["No log messages found with severity >= 2"]
        assert any("no severity >= 2 errors" in item for item in result["analysis"]["highlights"])

    @patch("cli_anything.nsight_graphics.core.replay.backend.run_command")
    @patch("cli_anything.nsight_graphics.core.replay.backend.probe_installation")
    def test_replay_analyze_reports_gputrace_replay_incompatibility(self, probe_mock, run_mock, tmp_path):
        capture_file = tmp_path / "trace.ngfx-gputrace"
        capture_file.write_text("trace", encoding="utf-8")
        probe_mock.return_value = {
            "version": "2026.1.0",
            "tool_mode": "unified+split",
            "compatibility_mode": "unified+split",
            "binaries": {"ngfx_replay": "C:/Nsight/ngfx-replay.exe"},
        }

        def fake_run(command, timeout=120, cwd=None):
            is_log_command = "--metadata-logs" in command or "--metadata-logs-errors" in command
            return {
                "ok": not is_log_command,
                "returncode": 1 if is_log_command else 0,
                "stdout": "ERROR: Invalid file header (trace.ngfx-gputrace)\n" if is_log_command else "",
                "stderr": "",
                "command": " ".join(command),
            }

        run_mock.side_effect = fake_run

        result = replay.analyze_capture(
            nsight_path=None,
            capture_file=str(capture_file),
            output_dir=str(tmp_path / "analysis"),
            metadata=True,
            logs=True,
            screenshot=False,
            perf_report=False,
        )

        assert result["ok"] is False
        assert result["metadata"]["present"] == {"summary": False, "functions": False, "objects": False}
        assert result["logs"]["error_line_count"] == 1
        assert "Invalid file header" in result["logs"]["error_summary"][0]
        assert any(".ngfx-gputrace inputs may not produce metadata" in warning for warning in result["analysis"]["warnings"])
        assert any("Replay command failures" in warning for warning in result["analysis"]["warnings"])

    @patch("cli_anything.nsight_graphics.core.replay.backend.probe_installation")
    def test_replay_analyze_requires_ngfx_replay(self, probe_mock, tmp_path):
        capture_file = tmp_path / "frame.ngfx-capture"
        capture_file.write_text("capture", encoding="utf-8")
        probe_mock.return_value = {
            "binaries": {"ngfx_replay": None},
        }
        with pytest.raises(RuntimeError, match="ngfx-replay.exe is required"):
            replay.analyze_capture(
                nsight_path=None,
                capture_file=str(capture_file),
                output_dir=str(tmp_path / "analysis"),
                metadata=True,
                logs=False,
                screenshot=False,
                perf_report=False,
            )

    def test_replay_analyze_rejects_unknown_capture_extension(self, tmp_path):
        capture_file = tmp_path / "frame.rdc"
        capture_file.write_text("capture", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported Nsight capture file extension"):
            replay.analyze_capture(
                nsight_path=None,
                capture_file=str(capture_file),
                output_dir=str(tmp_path / "analysis"),
                metadata=True,
                logs=False,
                screenshot=False,
                perf_report=False,
            )


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
            (["replay", "--help"], "analyze"),
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

    def test_replay_analyze_json_cli(self, tmp_path):
        from click.testing import CliRunner
        from cli_anything.nsight_graphics.nsight_graphics_cli import cli

        capture_file = tmp_path / "frame.ngfx-capture"
        capture_file.write_text("capture", encoding="utf-8")
        runner = CliRunner()
        with patch("cli_anything.nsight_graphics.nsight_graphics_cli.replay.analyze_capture") as analyze_mock:
            analyze_mock.return_value = {
                "ok": True,
                "capture_file": str(capture_file),
                "capture_type": "graphics_capture",
                "output_dir": str(tmp_path / "analysis"),
                "artifact_count": 1,
            }
            result = runner.invoke(
                cli,
                [
                    "--json",
                    "replay",
                    "analyze",
                    "--capture-file",
                    str(capture_file),
                    "--output-dir",
                    str(tmp_path / "analysis"),
                ],
            )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["ok"] is True
        analyze_mock.assert_called_once()
        assert analyze_mock.call_args.kwargs["metadata"] is False
        assert analyze_mock.call_args.kwargs["logs"] is False
        assert analyze_mock.call_args.kwargs["perf_report"] is False


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
