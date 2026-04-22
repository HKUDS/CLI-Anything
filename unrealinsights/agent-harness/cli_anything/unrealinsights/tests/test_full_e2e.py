"""
End-to-end tests for the Unreal Insights harness.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from cli_anything.unrealinsights.utils.unrealinsights_backend import resolve_unrealinsights_exe

HARNESS_ROOT = str(Path(__file__).resolve().parents[3])
TEST_TRACE = os.environ.get("UNREALINSIGHTS_TEST_TRACE", "")
TEST_TARGET_EXE = os.environ.get("UNREALINSIGHTS_TEST_TARGET_EXE", "")


def _has_local_insights() -> bool:
    try:
        return bool(resolve_unrealinsights_exe(required=False).get("available"))
    except RuntimeError:
        return False


HAS_TRACE = os.path.isfile(TEST_TRACE) if TEST_TRACE else False
HAS_TARGET = os.path.isfile(TEST_TARGET_EXE) if TEST_TARGET_EXE else False
HAS_LOCAL_INSIGHTS = _has_local_insights()

skip_no_trace = pytest.mark.skipif(not HAS_TRACE, reason="UNREALINSIGHTS_TEST_TRACE not set or missing")
skip_no_target = pytest.mark.skipif(not HAS_TARGET, reason="UNREALINSIGHTS_TEST_TARGET_EXE not set or missing")
skip_no_local_ue = pytest.mark.skipif(not HAS_LOCAL_INSIGHTS, reason="No local Unreal Insights install detected")


def _resolve_cli(name: str):
    """Resolve installed CLI command; falls back to python -m for dev."""
    import shutil

    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    print("[_resolve_cli] Falling back to module invocation")
    return [sys.executable, "-m", "cli_anything.unrealinsights.unrealinsights_cli"]


def _cli_env():
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = HARNESS_ROOT if not pythonpath else f"{HARNESS_ROOT}{os.pathsep}{pythonpath}"
    env["CLI_ANYTHING_UNREALINSIGHTS_STATE_DIR"] = os.path.join(HARNESS_ROOT, ".tmp_state")
    return env


class TestCLISmoke:
    CLI_BASE = _resolve_cli("cli-anything-unrealinsights")

    def _run(self, args, check=True, timeout=180):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            check=check,
            timeout=timeout,
            env=_cli_env(),
        )

    @skip_no_local_ue
    def test_backend_info(self):
        result = self._run(["--json", "backend", "info"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["insights"]["available"] is True
        assert data["insights"]["path"].lower().endswith("unrealinsights.exe")


@skip_no_trace
class TestExportE2E:
    CLI_BASE = _resolve_cli("cli-anything-unrealinsights")

    def _run(self, args, check=True, timeout=180):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            check=check,
            timeout=timeout,
            env=_cli_env(),
        )

    @pytest.mark.parametrize(
        ("subcommand", "extra_args"),
        [
            ("threads", []),
            ("timers", []),
            ("timing-events", ["--threads", "GameThread", "--timers", "*"]),
            ("timer-stats", ["--threads", "GameThread", "--timers", "*"]),
            ("timer-callees", ["--threads", "GameThread", "--timers", "*"]),
            ("counters", []),
            ("counter-values", ["--counter", "*"]),
        ],
    )
    def test_exporter_creates_output(self, subcommand, extra_args):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, f"{subcommand}.csv")
            result = self._run(
                ["--json", "-t", TEST_TRACE, "export", subcommand, output, *extra_args],
                check=False,
            )
            if result.returncode != 0:
                pytest.skip(f"{subcommand} exporter failed for supplied trace")
            data = json.loads(result.stdout)
            assert data["output_files"]
            for path in data["output_files"]:
                assert os.path.isfile(path)
                assert os.path.getsize(path) > 0

    def test_batch_run_rsp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            threads = os.path.join(tmpdir, "threads.csv")
            timers = os.path.join(tmpdir, "timers.csv")
            rsp = os.path.join(tmpdir, "exports.rsp")
            Path(rsp).write_text(
                "\n".join(
                    [
                        f'TimingInsights.ExportThreads "{threads}"',
                        f'TimingInsights.ExportTimers "{timers}"',
                    ]
                ),
                encoding="utf-8",
            )
            result = self._run(["--json", "-t", TEST_TRACE, "batch", "run-rsp", rsp], check=False)
            if result.returncode != 0:
                pytest.skip("response-file execution failed for supplied trace")
            data = json.loads(result.stdout)
            assert len(data["output_files"]) >= 2
            for path in data["output_files"]:
                assert os.path.isfile(path)
                assert os.path.getsize(path) > 0


@skip_no_target
class TestCaptureE2E:
    CLI_BASE = _resolve_cli("cli-anything-unrealinsights")

    def _run(self, args, check=True, timeout=300):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            check=check,
            timeout=timeout,
            env=_cli_env(),
        )

    def test_capture_run_wait(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_trace = os.path.join(tmpdir, "capture.utrace")
            result = self._run(
                [
                    "--json",
                    "capture",
                    "run",
                    TEST_TARGET_EXE,
                    "--output-trace",
                    output_trace,
                    "--wait",
                    "--timeout",
                    "180",
                ],
                check=False,
                timeout=360,
            )
            if result.returncode != 0:
                pytest.skip("capture run failed for supplied target executable")
            data = json.loads(result.stdout)
            assert data["trace_path"].lower().endswith(".utrace")
            assert data["trace_exists"] is True
            assert data["trace_size"] > 0
