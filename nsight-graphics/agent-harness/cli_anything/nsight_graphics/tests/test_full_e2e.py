"""Conditional end-to-end tests for cli-anything-nsight-graphics."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from cli_anything.nsight_graphics.utils.nsight_graphics_backend import probe_installation

HARNESS_ROOT = str(Path(__file__).resolve().parents[3])
TEST_EXE = os.environ.get("NSIGHT_GRAPHICS_TEST_EXE", "").strip()
TEST_ARGS = os.environ.get("NSIGHT_GRAPHICS_TEST_ARGS", "").strip()
TEST_WORKDIR = os.environ.get("NSIGHT_GRAPHICS_TEST_WORKDIR", "").strip()
TEST_CAPTURE_FILE = os.environ.get("NSIGHT_GRAPHICS_TEST_CAPTURE_FILE", "").strip()
HAS_NSIGHT = bool(probe_installation().get("ok"))
HAS_TEST_EXE = bool(TEST_EXE and os.path.isfile(TEST_EXE))
HAS_TEST_CAPTURE_FILE = bool(TEST_CAPTURE_FILE and os.path.isfile(TEST_CAPTURE_FILE))


def _resolve_cli(name: str) -> list[str]:
    """Resolve the CLI entry point for subprocess tests."""
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        probe = subprocess.run(
            [path, "--help"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=HARNESS_ROOT,
        )
        if probe.returncode == 0:
            return [path]
        if force:
            raise RuntimeError(
                f"{name} was found in PATH but is not runnable in this environment:\n"
                f"{probe.stderr or probe.stdout}"
            )
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    return [sys.executable, "-m", "cli_anything.nsight_graphics.nsight_graphics_cli"]


CLI_BASE = _resolve_cli("cli-anything-nsight-graphics")
skip_no_nsight = pytest.mark.skipif(not HAS_NSIGHT, reason="Nsight Graphics not installed")
skip_no_target = pytest.mark.skipif(not HAS_TEST_EXE, reason="NSIGHT_GRAPHICS_TEST_EXE not set or missing")
skip_no_capture = pytest.mark.skipif(not HAS_TEST_CAPTURE_FILE, reason="NSIGHT_GRAPHICS_TEST_CAPTURE_FILE not set or missing")


def _run_json(*args: str, timeout: int = 600) -> dict:
    """Run the CLI in JSON mode and parse stdout."""
    result = subprocess.run(
        CLI_BASE + ["--json", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=HARNESS_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"CLI failed: {result.stderr}\n{result.stdout}")
    return json.loads(result.stdout)


def _target_args() -> list[str]:
    """Build repeated CLI args for the configured test executable."""
    args = ["--exe", TEST_EXE]
    if TEST_WORKDIR:
        args.extend(["--dir", TEST_WORKDIR])
    if TEST_ARGS:
        for entry in shlex.split(TEST_ARGS, posix=os.name != "nt"):
            args.extend(["--arg", entry])
    return args


@skip_no_nsight
class TestDoctorE2E:
    def test_doctor_info(self):
        data = _run_json("doctor", "info", timeout=60)
        assert data["ok"] is True
        assert data["compatibility_mode"] in {"unified", "split", "unified+split"}
        assert data["resolved_executable"]


@skip_no_nsight
@skip_no_target
class TestTargetedE2E:
    def test_frame_capture(self, tmp_path):
        data = _run_json(
            "--output-dir",
            str(tmp_path),
            "frame",
            "capture",
            *_target_args(),
            "--wait-seconds",
            "1",
        )
        assert data["ok"] is True
        assert data["artifacts"]
        assert any(Path(item["path"]).exists() and item["size"] > 0 for item in data["artifacts"])
        capture_files = [Path(item["path"]) for item in data["artifacts"] if Path(item["path"]).suffix.lower() == ".ngfx-capture"]
        if capture_files:
            analysis = _run_json(
                "replay",
                "analyze",
                "--capture-file",
                str(capture_files[0]),
                "--output-dir",
                str(tmp_path / "frame_replay_analysis"),
                "--metadata",
                "--logs",
                timeout=600,
            )
            assert analysis["ok"] is True
            assert analysis["metadata"]["present"]["summary"] is True
            assert analysis["analysis"]["summary"]["primary_api"]
            assert analysis["analysis"]["summary"]["function_event_count"] > 0

    def test_gpu_trace_capture(self, tmp_path):
        data = _run_json(
            "--output-dir",
            str(tmp_path),
            "gpu-trace",
            "capture",
            *_target_args(),
            "--start-after-ms",
            "1000",
            "--limit-to-frames",
            "1",
            "--auto-export",
            "--summarize",
        )
        assert data["ok"] is True
        assert data["artifacts"]
        assert any(Path(item["path"]).exists() and item["size"] > 0 for item in data["artifacts"])
        assert data["summary"]["tables"]["trace_frame"]["metric_count"] > 0
        assert "metric_inventory" in data["summary"]
        assert data["summary"]["analysis"]["frame_budget"]["bucket"] in {
            "within_60fps_budget",
            "over_60fps_budget",
            "over_30fps_budget",
        }

    def test_cpp_capture(self, tmp_path):
        data = _run_json(
            "--output-dir",
            str(tmp_path),
            "cpp",
            "capture",
            *_target_args(),
            "--wait-seconds",
            "1",
        )
        assert data["ok"] is True
        assert data["artifacts"]
        assert any(Path(item["path"]).exists() and item["size"] > 0 for item in data["artifacts"])


@skip_no_nsight
@skip_no_capture
class TestReplayE2E:
    def test_replay_analyze_existing_capture(self, tmp_path):
        data = _run_json(
            "replay",
            "analyze",
            "--capture-file",
            TEST_CAPTURE_FILE,
            "--output-dir",
            str(tmp_path),
            "--metadata",
            "--logs",
            timeout=600,
        )
        assert data["ok"] is True
        assert data["artifacts"]
        assert any(Path(item["path"]).exists() and item["size"] > 0 for item in data["artifacts"])
        assert data["metadata"]["present"]["summary"] is True
        assert data["metadata"]["summary"]["primary_api"]
        assert data["metadata"]["functions"]["total"] > 0
        assert data["metadata"]["objects"]["total"] > 0
        assert "log_error_count" in data["analysis"]["summary"]
