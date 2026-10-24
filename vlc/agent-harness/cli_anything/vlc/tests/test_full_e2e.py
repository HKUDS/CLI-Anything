"""End-to-end tests for the VLC harness — REQUIRE the real VLC binary.

Per HARNESS.md non-negotiables, these tests invoke the actual VLC engine and FAIL (they
do not skip) when VLC is not installed. A tiny WAV sample is synthesised with the stdlib
so the basic transcode / info / stream paths run without ffmpeg.
"""

from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path

import pytest
from click.testing import CliRunner

from cli_anything.vlc import vlc_cli
from cli_anything.vlc.core import project as proj
from cli_anything.vlc.utils import vlc_backend

HERE = Path(__file__).parent
ASSETS = HERE / "assets"
WAV = ASSETS / "sample.wav"


def _make_wav() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    if WAV.exists():
        return
    with wave.open(str(WAV), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        data = bytearray()
        for i in range(8000):
            val = int(7000 * math.sin(2 * math.pi * 440 * i / 8000))
            data += struct.pack("<h", val)
        w.writeframes(bytes(data))


@pytest.fixture(scope="session")
def sample_wav():
    try:
        vlc_backend.find_vlc()
    except RuntimeError as e:
        pytest.fail(
            "VLC is not installed — E2E tests require the real VLC binary "
            "(HARNESS.md: E2E MUST invoke the real software). "
            f"{e}"
        )
    _make_wav()
    return WAV


def test_transcode_wav_to_wav(sample_wav, tmp_path):
    j = proj.new_job()
    j["inputs"] = [str(sample_wav)]
    out = tmp_path / "out.wav"
    j["output"] = {"path": str(out), "format": "wav"}
    j["transcode"] = {
        "vcodec": None, "acodec": "wav", "vbitrate": None, "abitrate": None,
        "scale": 1.0, "width": None, "height": None, "fps": None,
        "channels": 1, "samplerate": 8000, "extra": [],
    }
    result = vlc_backend.run_transcode(j)
    assert out.is_file(), result
    assert out.stat().st_size > 1000
    assert out.read_bytes()[:4] == b"RIFF"


def test_transcode_replaces_stale_output(sample_wav, tmp_path):
    # A pre-existing destination (from a prior run) must be replaced by genuinely
    # fresh output, never passed off as success on stale bytes.
    j = proj.new_job()
    j["inputs"] = [str(sample_wav)]
    out = tmp_path / "out.wav"
    out.write_bytes(b"STALE" * 200)  # junk from a previous run
    j["output"] = {"path": str(out), "format": "wav"}
    j["transcode"] = {
        "vcodec": None, "acodec": "wav", "vbitrate": None, "abitrate": None,
        "scale": 1.0, "width": None, "height": None, "fps": None,
        "channels": 1, "samplerate": 8000, "extra": [],
    }
    result = vlc_backend.run_transcode(j)
    assert out.is_file(), result
    assert out.read_bytes()[:4] == b"RIFF"  # replaced, not the stale "STALE" bytes
    assert out.stat().st_size > 1000


def test_info_wav(sample_wav):
    info = vlc_backend.run_info(sample_wav)
    assert info["path"] == str(sample_wav)
    assert "returncode" in info


def test_stream_udp(sample_wav):
    j = proj.new_job()
    j["inputs"] = [str(sample_wav)]
    j["output"] = {"path": "nul", "format": "wav"}
    j["transcode"] = {
        "vcodec": None, "acodec": "wav", "vbitrate": None, "abitrate": None,
        "scale": 1.0, "width": None, "height": None, "fps": None,
        "channels": 1, "samplerate": 8000, "extra": [],
    }
    j["stream"] = {"protocol": "udp", "dst": "127.0.0.1", "port": 6004, "mux": "ts"}
    result = vlc_backend.run_stream(j, run_time=1)
    assert result["returncode"] == 0


def test_cli_transcode_end_to_end(sample_wav, tmp_path):
    runner = CliRunner()
    job = tmp_path / "job.json"
    runner.invoke(vlc_cli.cli, ["project", "new", "-o", str(job)], catch_exceptions=False)
    runner.invoke(vlc_cli.cli, ["--project", str(job), "add-input", str(sample_wav)], catch_exceptions=False)
    runner.invoke(vlc_cli.cli, ["--project", str(job), "set-output", str(tmp_path / "o.wav"), "--format", "wav"], catch_exceptions=False)
    runner.invoke(vlc_cli.cli, ["--project", str(job), "set-option", "acodec", "wav"], catch_exceptions=False)
    r = runner.invoke(vlc_cli.cli, ["--json", "--project", str(job), "transcode"], catch_exceptions=False)
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert data["method"] == "vlc-transcode"
    assert data["file_size"] > 0
