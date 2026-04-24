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
DEFAULT_TEST_EXE = os.environ.get("NSIGHT_GRAPHICS_TEST_EXE", "").strip()
DEFAULT_TEST_ARGS = os.environ.get("NSIGHT_GRAPHICS_TEST_ARGS", "").strip()
DEFAULT_TEST_WORKDIR = os.environ.get("NSIGHT_GRAPHICS_TEST_WORKDIR", "").strip()

FRAME_TEST_EXE = os.environ.get("NSIGHT_GRAPHICS_FRAME_TEST_EXE", "").strip() or DEFAULT_TEST_EXE
FRAME_TEST_ARGS = os.environ.get("NSIGHT_GRAPHICS_FRAME_TEST_ARGS", "").strip() or DEFAULT_TEST_ARGS
FRAME_TEST_WORKDIR = os.environ.get("NSIGHT_GRAPHICS_FRAME_TEST_WORKDIR", "").strip() or DEFAULT_TEST_WORKDIR

GPU_TRACE_TEST_EXE = os.environ.get("NSIGHT_GRAPHICS_GPU_TRACE_TEST_EXE", "").strip() or DEFAULT_TEST_EXE
GPU_TRACE_TEST_ARGS = os.environ.get("NSIGHT_GRAPHICS_GPU_TRACE_TEST_ARGS", "").strip() or DEFAULT_TEST_ARGS
GPU_TRACE_TEST_WORKDIR = os.environ.get("NSIGHT_GRAPHICS_GPU_TRACE_TEST_WORKDIR", "").strip() or DEFAULT_TEST_WORKDIR

CPP_TEST_EXE = os.environ.get("NSIGHT_GRAPHICS_CPP_TEST_EXE", "").strip() or DEFAULT_TEST_EXE
CPP_TEST_ARGS = os.environ.get("NSIGHT_GRAPHICS_CPP_TEST_ARGS", "").strip() or DEFAULT_TEST_ARGS
CPP_TEST_WORKDIR = os.environ.get("NSIGHT_GRAPHICS_CPP_TEST_WORKDIR", "").strip() or DEFAULT_TEST_WORKDIR

HAS_NSIGHT = bool(probe_installation().get("ok"))
HAS_FRAME_TEST_EXE = bool(FRAME_TEST_EXE and os.path.isfile(FRAME_TEST_EXE))
HAS_GPU_TRACE_TEST_EXE = bool(GPU_TRACE_TEST_EXE and os.path.isfile(GPU_TRACE_TEST_EXE))
HAS_CPP_TEST_EXE = bool(CPP_TEST_EXE and os.path.isfile(CPP_TEST_EXE))


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
skip_no_frame_target = pytest.mark.skipif(
    not HAS_FRAME_TEST_EXE,
    reason="NSIGHT_GRAPHICS_FRAME_TEST_EXE or NSIGHT_GRAPHICS_TEST_EXE not set or missing",
)
skip_no_gpu_trace_target = pytest.mark.skipif(
    not HAS_GPU_TRACE_TEST_EXE,
    reason="NSIGHT_GRAPHICS_GPU_TRACE_TEST_EXE or NSIGHT_GRAPHICS_TEST_EXE not set or missing",
)
skip_no_cpp_target = pytest.mark.skipif(
    not HAS_CPP_TEST_EXE,
    reason="NSIGHT_GRAPHICS_CPP_TEST_EXE or NSIGHT_GRAPHICS_TEST_EXE not set or missing",
)


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


def _target_args(exe_path: str, args_text: str, workdir: str) -> list[str]:
    """Build repeated CLI args for a configured activity target."""
    args = ["--exe", exe_path]
    if workdir:
        args.extend(["--dir", workdir])
    if args_text:
        for entry in shlex.split(args_text, posix=os.name != "nt"):
            args.extend(["--arg", entry])
    return args


@skip_no_nsight
class TestDoctorE2E:
    def test_doctor_info(self):
        data = _run_json("doctor", "info", timeout=60)
        assert data["ok"] is True
        assert data["compatibility_mode"] in {"unified", "split"}
        assert data["resolved_executable"]


@skip_no_nsight
class TestTargetedE2E:
    @skip_no_frame_target
    def test_frame_capture(self, tmp_path):
        data = _run_json(
            "--output-dir",
            str(tmp_path),
            "frame",
            "capture",
            *_target_args(FRAME_TEST_EXE, FRAME_TEST_ARGS, FRAME_TEST_WORKDIR),
            "--wait-seconds",
            "1",
        )
        assert data["ok"] is True
        assert data["artifacts"]
        assert any(Path(item["path"]).exists() and item["size"] > 0 for item in data["artifacts"])

    @skip_no_gpu_trace_target
    def test_gpu_trace_capture(self, tmp_path):
        data = _run_json(
            "--output-dir",
            str(tmp_path),
            "gpu-trace",
            "capture",
            *_target_args(GPU_TRACE_TEST_EXE, GPU_TRACE_TEST_ARGS, GPU_TRACE_TEST_WORKDIR),
            "--start-after-ms",
            "1000",
            "--limit-to-frames",
            "1",
            "--auto-export",
        )
        assert data["ok"] is True
        assert data["artifacts"]
        assert any(Path(item["path"]).exists() and item["size"] > 0 for item in data["artifacts"])

    @skip_no_cpp_target
    def test_cpp_capture(self, tmp_path):
        data = _run_json(
            "--output-dir",
            str(tmp_path),
            "cpp",
            "capture",
            *_target_args(CPP_TEST_EXE, CPP_TEST_ARGS, CPP_TEST_WORKDIR),
            "--wait-seconds",
            "1",
        )
        assert data["ok"] is True
        assert data["artifacts"]
        assert any(Path(item["path"]).exists() and item["size"] > 0 for item in data["artifacts"])
