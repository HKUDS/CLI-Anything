from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from cli_anything.wavetone.tests.helpers import make_wav
from cli_anything.wavetone.utils import wavetone_backend

REAL_BACKEND_ENV = "CLI_ANYTHING_WAVETONE_REAL_BACKEND"


def _resolve_cli(name: str, force_installed: bool = False) -> list[str]:
    """Run the in-tree module by default; installed entry points are opt-in."""
    module = "cli_anything.wavetone.wavetone_cli"
    if not force_installed:
        print(f"[_resolve_cli] Using source module: {sys.executable} -m {module}")
        return [sys.executable, "-m", module]

    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    print(f"[_resolve_cli] Using installed command: {path}")
    return [path]


def _env_flag_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _real_backend_ready() -> tuple[bool, str]:
    if not _env_flag_enabled(REAL_BACKEND_ENV):
        return False, f"set {REAL_BACKEND_ENV}=1 with WAVETONE_EXE or WAVETONE_HOME to run real backend tests"
    if sys.platform != "win32":
        return False, "WaveTone real-backend tests require Windows"
    if not (os.environ.get("WAVETONE_EXE") or os.environ.get("WAVETONE_HOME")):
        return False, "set WAVETONE_EXE or WAVETONE_HOME to run real backend tests"

    status = wavetone_backend.doctor()
    if status.get("ready"):
        return True, ""

    failed_checks = [check["name"] for check in status.get("checks", []) if not check.get("ok")]
    reason = ", ".join(failed_checks) if failed_checks else "WaveTone backend is not ready"
    return False, f"WaveTone real backend unavailable: {reason}"


_REAL_BACKEND_READY, _REAL_BACKEND_SKIP_REASON = _real_backend_ready()


def test_real_backend_requires_explicit_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(REAL_BACKEND_ENV, raising=False)
    monkeypatch.delenv("WAVETONE_EXE", raising=False)
    monkeypatch.delenv("WAVETONE_HOME", raising=False)

    ready, reason = _real_backend_ready()

    assert ready is False
    assert REAL_BACKEND_ENV in reason


def test_resolve_cli_defaults_to_source_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLI_ANYTHING_FORCE_INSTALLED", "1")
    monkeypatch.setattr(shutil, "which", lambda name: pytest.fail("default resolver should not inspect PATH"))

    assert _resolve_cli("cli-anything-wavetone") == [sys.executable, "-m", "cli_anything.wavetone.wavetone_cli"]


def test_resolve_cli_uses_installed_only_when_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "C:/installed/cli-anything-wavetone.exe")

    assert _resolve_cli("cli-anything-wavetone", force_installed=True) == ["C:/installed/cli-anything-wavetone.exe"]


class TestCLISubprocess:
    def _run(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(_resolve_cli("cli-anything-wavetone") + args, capture_output=True, text=True, check=check)

    def test_help(self) -> None:
        result = self._run(["--help"])
        assert "Agent-native CLI harness for WaveTone" in result.stdout

    def test_project_audio_workflow_json(self, tmp_path: Path) -> None:
        wav = make_wav(tmp_path / "tone.wav")
        project = tmp_path / "tone.wt.json"

        result = self._run(["--json", "project", "new", str(wav), "-o", str(project)])
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert project.exists()

        result = self._run(
            ["--project", str(project), "--json", "project", "set-tempo", "--bpm", "132.5", "--first-bar", "0.1"]
        )
        assert json.loads(result.stdout)["tempo"]["bpm"] == 132.5

        result = self._run(["--project", str(project), "--json", "project", "add-label", "intro", "--time", "0.25"])
        assert json.loads(result.stdout)["labels"][0]["name"] == "intro"

        result = self._run(["--project", str(project), "--json", "audio", "probe"])
        audio = json.loads(result.stdout)["audio"]
        assert audio["duration_seconds"] == 0.5
        assert audio["channels"] == 1
        print(f"\n  Project: {project}")
        print(f"  Audio: {wav} ({wav.stat().st_size:,} bytes)")

    def test_formats_json(self) -> None:
        result = self._run(["--json", "wavetone", "formats"])
        data = json.loads(result.stdout)
        assert ".wav" in data["formats"]["extensions"]
        assert "MP3" in data["formats"]["from_readme"]


@pytest.mark.skipif(not _REAL_BACKEND_READY, reason=_REAL_BACKEND_SKIP_REASON)
class TestRealWaveToneBackend:
    def _run(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(_resolve_cli("cli-anything-wavetone") + args, capture_output=True, text=True, check=check)

    def test_doctor_real_backend(self) -> None:
        result = self._run(["--json", "wavetone", "doctor"])
        data = json.loads(result.stdout)
        assert data["ready"] is True
        assert any(check["name"] == "data/asdecoder.exe" and check["ok"] for check in data["checks"])
        print(f"\n  WaveTone root: {data['root']}")

    def test_launch_real_backend_with_wav(self, tmp_path: Path) -> None:
        exe = wavetone_backend.find_wavetone()
        wav = make_wav(tmp_path / "launch.wav")
        result = self._run(
            [
                "--json",
                "wavetone",
                "launch",
                str(wav),
                "--exe",
                str(exe),
                "--wait",
                "1",
                "--terminate",
            ]
        )
        data = json.loads(result.stdout)["launch"]
        assert data["backend"] == "wavetone.exe"
        assert data["audio_path"] == str(wav.resolve())
        assert data["running_after_wait"] is True
        assert data["terminated"] is True
        print(f"\n  Launched WaveTone PID: {data['pid']}")
        print(f"  WAV: {wav} ({wav.stat().st_size:,} bytes)")
