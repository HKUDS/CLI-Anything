"""Unit tests for the VLC harness — no VLC binary required.

These exercise the pure-Python core (job spec, session undo/redo, --sout chain
construction, stats parsing) and the Click command wiring for the mutation commands.
They run in CI / anywhere with only Python + click installed.
"""

from __future__ import annotations

import json
import math
import os
import re
import struct
import subprocess
import wave
from pathlib import Path

import pytest
from click.testing import CliRunner

from cli_anything.vlc import vlc_cli
from cli_anything.vlc.core import project as proj
from cli_anything.vlc.core import session as sess_mod
from cli_anything.vlc.core import transcode
from cli_anything.vlc.core import media
from cli_anything.vlc.utils import vlc_backend
from cli_anything.vlc.utils.repl_skin import ReplSkin


# ── core.project ───────────────────────────────────────────────────────

def test_new_job_defaults():
    j = proj.new_job()
    assert j["software"] == "vlc"
    assert j["inputs"] == []
    assert j["transcode"]["vcodec"] == "h264"


def test_save_and_load_roundtrip(tmp_path):
    p = tmp_path / "job.json"
    meta = proj.save_job(proj.new_job(), p)
    assert p.is_file()
    assert meta["size_bytes"] > 0
    loaded = proj.load_job(p)
    assert loaded["software"] == "vlc"


def test_validate_job():
    j = proj.new_job()
    errs = proj.validate_job(j)
    assert any("input" in e for e in errs)
    j["inputs"].append("a.mp4")
    j["output"]["path"] = "o.mp4"
    assert proj.validate_job(j) == []


# ── core.session ───────────────────────────────────────────────────────

def test_session_undo_redo():
    s = sess_mod.Session()
    s.mutate("add", lambda j: j["inputs"].append("x.mp4"))
    assert s.job["inputs"] == ["x.mp4"]
    s.undo()
    assert s.job["inputs"] == []
    assert s.can_redo()
    s.redo()
    assert s.job["inputs"] == ["x.mp4"]


def test_session_history_labels():
    s = sess_mod.Session()
    s.mutate("a", lambda j: j["inputs"].append("1"))
    s.mutate("b", lambda j: j["inputs"].append("2"))
    assert s.history() == ["a", "b"]
    s.undo()
    assert s.history() == ["a"]


# ── core.transcode ─────────────────────────────────────────────────────

def test_build_transcode_sout_basic():
    j = proj.new_job()
    j["inputs"].append("in.mp4")
    j["output"] = {"path": "out.mp4", "format": "mp4"}
    j["transcode"]["vbitrate"] = 1000
    s = transcode.build_transcode_sout(j)
    assert s.startswith("#transcode{")
    assert "vcodec=h264" in s
    assert "vb=1000" in s
    assert "std{access=file,mux=mp4,dst='out.mp4'}" in s


def test_build_transcode_sout_windows_path_normalized():
    j = proj.new_job()
    j["output"] = {"path": "C:\\out.mp4", "format": "mkv"}
    s = transcode.build_transcode_sout(j)
    assert "\\\\" not in s
    assert "dst='C:/out.mp4'" in s


def test_build_stream_sout_rtp():
    j = proj.new_job()
    j["stream"] = {"protocol": "rtp", "dst": "127.0.0.1", "port": 5004, "mux": "ts"}
    s = transcode.build_stream_sout(j)
    assert "rtp{dst=127.0.0.1,port=5004,mux=ts}" in s


def test_build_snapshot_args():
    j = proj.new_job()
    j["snapshot"] = {"path": "/tmp/shots", "time": 2.0, "ratio": 1}
    args = transcode.build_snapshot_args(j)
    assert "--video-filter=scene" in args
    assert "--scene-path=/tmp/shots" in args
    assert "--start-time=2.0" in args


def test_build_snapshot_args_scene_prefix():
    # Third-round fix: the caller must be able to pin VLC's scene filename prefix.
    j = proj.new_job()
    j["snapshot"] = {"path": "/tmp/shots", "time": 2.0, "ratio": 1}
    assert "--scene-prefix=scene" in transcode.build_snapshot_args(j)
    custom = transcode.build_snapshot_args(j, scene_prefix="vlc-snap-abc-")
    assert "--scene-prefix=vlc-snap-abc-" in custom


# ── core.media ─────────────────────────────────────────────────────────

def test_parse_vlc_stats_synthetic():
    text = (
        "decoder: using h264 codec\n"
        "resolution 1920x1080\n"
        "duration: 12.5 s\n"
        "bitrate: 1234"
    )
    info = media.parse_vlc_stats(text)
    assert info["video_codec"] == "H264"
    assert info["width"] == 1920
    assert info["height"] == 1080
    assert info["duration_seconds"] == 12.5
    assert info["bitrate_kbps"] == 1234


# ── CLI wiring (no backend) ────────────────────────────────────────────

def test_cli_version_and_help():
    runner = CliRunner()
    assert runner.invoke(vlc_cli.cli, ["--version"]).exit_code == 0
    assert runner.invoke(vlc_cli.cli, ["--help"]).exit_code == 0


def test_cli_project_new_and_mutate(tmp_path):
    runner = CliRunner()
    job = tmp_path / "job.json"
    r = runner.invoke(vlc_cli.cli, ["--json", "project", "new", "-o", str(job)])
    assert r.exit_code == 0, r.output

    # add-input records a real (existing) media path
    media_file = tmp_path / "in.mp4"
    media_file.write_text("dummy", encoding="utf-8")
    r = runner.invoke(vlc_cli.cli, ["--json", "--project", str(job), "add-input", str(media_file)])
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["input_count"] == 1

    r = runner.invoke(vlc_cli.cli, ["--json", "--project", str(job), "set-option", "vbitrate", "900"])
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["transcode"]["vbitrate"] == 900

    # persisted to disk
    saved = json.loads(job.read_text(encoding="utf-8"))
    assert saved["transcode"]["vbitrate"] == 900


def test_cli_set_output_and_stream(tmp_path):
    runner = CliRunner()
    job = tmp_path / "job.json"
    runner.invoke(vlc_cli.cli, ["project", "new", "-o", str(job)])
    runner.invoke(vlc_cli.cli, ["--project", str(job), "set-output", "out.mp4", "--format", "mkv"])
    runner.invoke(vlc_cli.cli, ["--project", str(job), "set-stream", "--protocol", "udp",
                                "--dst", "127.0.0.1", "--port", "6000", "--mux", "ts"])
    saved = json.loads(job.read_text(encoding="utf-8"))
    assert saved["output"]["format"] == "mkv"
    assert saved["stream"]["protocol"] == "udp"


def test_cli_transcode_requires_project(tmp_path):
    runner = CliRunner()
    r = runner.invoke(vlc_cli.cli, ["transcode"])
    assert r.exit_code != 0
    assert "project" in r.output.lower()


def test_cli_doctor_without_vlc(monkeypatch):
    # doctor imports find_vlc by name, so patch the reference it actually calls.
    def _raise(*_a, **_k):
        raise RuntimeError("VLC not found")

    monkeypatch.setattr(vlc_cli, "find_vlc", _raise)
    runner = CliRunner()
    r = runner.invoke(vlc_cli.cli, ["--json", "doctor"])
    assert r.exit_code == 1
    assert json.loads(r.output)["ready"] is False


def test_cli_transcode_missing_project_is_structured_json(tmp_path):
    # P2 fix: a missing project must surface as a structured --json error, not a traceback.
    runner = CliRunner()
    missing = tmp_path / "nope.json"
    r = runner.invoke(vlc_cli.cli, ["--json", "--project", str(missing), "transcode"])
    assert r.exit_code == 1
    payload = json.loads(r.output)
    assert payload.get("error")
    assert "project" in payload.get("detail", "").lower()


# ── P1/P2 review fixes ─────────────────────────────────────────────────

def test_transcode_copy_and_none_codecs_omitted():
    # copy / none resolve to None -> must NOT emit the literal "vcodec=None".
    j = proj.new_job()
    j["inputs"].append("in.mp4")
    j["output"] = {"path": "out.mkv", "format": "mkv"}
    j["transcode"]["vcodec"] = "copy"
    j["transcode"]["acodec"] = "none"
    s = transcode.build_transcode_sout(j)
    assert "vcodec=None" not in s
    assert "acodec=None" not in s
    assert "vcodec=copy" not in s
    assert "acodec=none" not in s


def test_run_stream_timeout_scales_with_run_time(monkeypatch):
    # P1 fix: a long --run-time must not be killed by the fixed 120s subprocess timeout.
    captured = {}

    monkeypatch.setattr(vlc_backend, "find_vlc", lambda: Path("vlc-stub"))

    def _fake_run(cmd, **kw):
        captured["timeout"] = kw.get("timeout")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(vlc_backend.subprocess, "run", _fake_run)

    j = proj.new_job()
    j["inputs"].append("in.mp4")
    j["stream"] = {"protocol": "rtp", "dst": "127.0.0.1", "port": 1234, "mux": "ts"}
    vlc_backend.run_stream(j, run_time=300)
    assert captured["timeout"] >= 300

    # short run keeps the historical 120s floor
    captured.clear()
    vlc_backend.run_stream(j, run_time=1)
    assert captured["timeout"] >= 120


def test_run_snapshot_ignores_stale_files(monkeypatch, tmp_path):
    # P1 fix: a reused directory must not leak pre-existing PNGs into the result,
    # and the lexicographically-last stale file must not be returned.
    shot = tmp_path / "shots"
    shot.mkdir()
    stale = shot / "zzzz_old.png"  # would win a naive sorted()[-1]
    stale.write_bytes(b"\x89PNG-stale")
    captured = {}

    def _fake_run(cmd, **kw):
        captured["prefix"] = next(a.split("=", 1)[1] for a in cmd
                                  if a.startswith("--scene-prefix="))
        (shot / f"{captured['prefix']}00001.png").write_bytes(b"\x89PNG-new")  # VLC's real output
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(vlc_backend, "find_vlc", lambda: Path("vlc-stub"))
    monkeypatch.setattr(vlc_backend.subprocess, "run", _fake_run)

    j = proj.new_job()
    j["inputs"].append("in.mp4")
    j["snapshot"] = {"path": str(shot), "time": 1.0, "ratio": 1}
    result = vlc_backend.run_snapshot(j)
    assert Path(result["snapshot"]).name == f"{captured['prefix']}00001.png"
    assert result["count"] == 1  # only the file produced by this run
    assert stale.is_file()  # pre-existing files are left alone


def test_run_info_propagates_nonzero_exit(monkeypatch):
    # P2 fix: a failing VLC probe must surface as an error (not a silent dict).

    def _fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")

    monkeypatch.setattr(vlc_backend, "find_vlc", lambda: Path("vlc-stub"))
    monkeypatch.setattr(vlc_backend.subprocess, "run", _fake_run)
    with pytest.raises(RuntimeError):
        vlc_backend.run_info("/dev/null")


def test_registry_names_not_in_both_files():
    # P2 fix: CLI-Hub concatenates registry.json + public_registry.json without
    # dedup, so a name must not appear in both. Runs only in the monorepo checkout.
    root = Path(__file__).resolve().parents[5]
    local = root / "registry.json"
    public = root / "public_registry.json"
    if not (local.is_file() and public.is_file()):
        pytest.skip("registry files not present (standalone install)")

    def _names(path):
        with open(path, encoding="utf-8") as fh:
            return {c["name"] for c in json.load(fh).get("clis", [])}

    dup = _names(local) & _names(public)
    assert not dup, f"names present in both registries: {sorted(dup)}"


# ── second-round review fixes ──────────────────────────────────────────

def test_transcode_rejects_output_equal_to_input(monkeypatch):
    # P1: output that aliases the input would clobber the source being read.
    monkeypatch.setattr(vlc_backend, "find_vlc", lambda: Path("vlc-stub"))
    j = proj.new_job()
    j["inputs"].append("/media/clip.mp4")
    j["output"] = {"path": "/media/clip.mp4", "format": "mp4"}
    with pytest.raises(ValueError):
        vlc_backend.run_transcode(j)


def test_run_stream_persistent_omits_run_time(monkeypatch):
    # P1: omitting run-time must yield a persistent stream (no --run-time, no
    # bounded subprocess timeout).
    captured = {}
    monkeypatch.setattr(vlc_backend, "find_vlc", lambda: Path("vlc-stub"))

    def _fake_run(cmd, **kw):
        captured["cmd"] = cmd
        captured["timeout"] = kw.get("timeout")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(vlc_backend.subprocess, "run", _fake_run)
    j = proj.new_job()
    j["inputs"].append("in.mp4")
    j["stream"] = {"protocol": "udp", "dst": "127.0.0.1", "port": 6004, "mux": "ts"}
    res = vlc_backend.run_stream(j)  # run_time omitted -> persistent
    assert not any(a.startswith("--run-time") for a in captured["cmd"])
    assert captured["timeout"] is None
    assert "persistent" in res["note"]


def test_find_vlc_rejects_directory_binary(monkeypatch, tmp_path):
    # P2: VLC_BINARY pointing at a directory (not a file) must fail loudly on
    # every platform, rather than making `doctor` report ready.
    a_dir = tmp_path / "vlc_dir"
    a_dir.mkdir()
    monkeypatch.setenv("VLC_BINARY", str(a_dir))
    with pytest.raises(RuntimeError):
        vlc_backend.find_vlc()


@pytest.mark.skipif(os.name != "posix", reason="the exec-bit check is POSIX-only")
def test_find_vlc_rejects_non_executable_file(monkeypatch, tmp_path):
    # P2: a regular non-executable file must fail (POSIX exec-bit check).
    not_exe = tmp_path / "not_vlc"
    not_exe.write_text("hello", encoding="utf-8")
    not_exe.chmod(0o644)  # readable, not executable
    monkeypatch.setenv("VLC_BINARY", str(not_exe))
    with pytest.raises(RuntimeError):
        vlc_backend.find_vlc()


def test_cli_mutation_malformed_project_structured(tmp_path):
    # P2: mutation commands must emit a structured --json error on malformed JSON,
    # not a traceback.
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    media_file = tmp_path / "in.mp4"
    media_file.write_text("x", encoding="utf-8")
    runner = CliRunner()
    r = runner.invoke(vlc_cli.cli, ["--json", "--project", str(bad), "add-input", str(media_file)])
    assert r.exit_code == 1
    assert json.loads(r.output).get("error")


def test_repl_shlex_handles_spaces_and_backslashes():
    # P2: the REPL tokenizer must keep Windows backslashes literal while still
    # respecting quotes around paths containing spaces.
    import shlex as _shlex
    line = r'add-input "C:\Users\me\my clip.mp4"'
    lexer = _shlex.shlex(line, posix=False)
    lexer.whitespace_split = True
    parts = [t[1:-1] if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'" else t for t in lexer]
    assert parts == ["add-input", r"C:\Users\me\my clip.mp4"]


# ── third-round review fixes ────────────────────────────────────────────

def test_load_job_rejects_schema_invalid_types(tmp_path):
    # Third-round fix: valid JSON with the wrong *shape* must fail at load time
    # instead of exploding later inside a mutator.
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"software": "vlc", "inputs": ["a.mp4"], "output": []}),
                 encoding="utf-8")
    with pytest.raises(ValueError, match="output"):
        proj.load_job(p)


def test_load_job_rejects_non_string_inputs(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"software": "vlc", "inputs": [1, 2]}), encoding="utf-8")
    with pytest.raises(ValueError, match="inputs"):
        proj.load_job(p)


def test_cli_mutation_schema_invalid_project_is_structured(tmp_path):
    # Third-round fix: a project that loads but is schema-invalid must produce a
    # structured --json error, not an AttributeError traceback with an empty stdout.
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"software": "vlc", "output": []}), encoding="utf-8")
    media_file = tmp_path / "in.mp4"
    media_file.write_text("x", encoding="utf-8")
    runner = CliRunner()
    r = runner.invoke(vlc_cli.cli, ["--json", "--project", str(bad),
                                    "set-output", str(tmp_path / "o.mp4")])
    assert r.exit_code == 1
    payload = json.loads(r.output)
    assert payload.get("error")
    assert "output" in payload.get("detail", "").lower()


def test_repl_new_detaches_opened_project(tmp_path, monkeypatch):
    # Third-round fix: `new` starts an in-memory job, so a later mutation must not
    # silently overwrite the project file that was opened.
    job = tmp_path / "job.json"
    proj.save_job(proj.new_job(), job)
    before = job.read_text(encoding="utf-8")

    script = [f"open {job}", "new", f"set-output {tmp_path / 'other.mp4'}", "quit"]

    class _FakeSkin:
        def __init__(self, *a, **k):
            pass

        def print_banner(self):
            pass

        def create_prompt_session(self):
            return object()

        def get_input(self, pt, project_name=None, modified=False):
            return script.pop(0) if script else "quit"

        def success(self, *a, **k):
            pass

        def error(self, *a, **k):
            pass

        def info(self, *a, **k):
            pass

        def status_block(self, *a, **k):
            pass

        def help(self, *a, **k):
            pass

        def print_goodbye(self):
            pass

    monkeypatch.setattr(vlc_cli, "ReplSkin", _FakeSkin)
    vlc_cli._repl(None)
    assert job.read_text(encoding="utf-8") == before


def test_run_transcode_removes_temp_when_subprocess_raises(monkeypatch, tmp_path):
    # Third-round fix: a subprocess timeout must not leave a partial `.vlc-tc-*`
    # sibling beside the destination.
    monkeypatch.setattr(vlc_backend, "find_vlc", lambda: Path("vlc-stub"))

    def _fake_run(cmd, **kw):
        chain = cmd[cmd.index("--sout") + 1]
        dst = chain.split("dst='")[1].split("'")[0]
        Path(dst).write_bytes(b"partial-output")  # VLC got this far before hanging
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))

    monkeypatch.setattr(vlc_backend.subprocess, "run", _fake_run)

    j = proj.new_job()
    j["inputs"].append("in.mp4")
    j["output"] = {"path": str(tmp_path / "out.mp4"), "format": "mp4"}
    with pytest.raises(subprocess.TimeoutExpired):
        vlc_backend.run_transcode(j)
    assert list(tmp_path.glob(".vlc-tc-*")) == []
    assert not (tmp_path / "out.mp4").exists()


def test_run_snapshot_rerun_same_directory_succeeds(monkeypatch, tmp_path):
    # Third-round fix: re-running in the same directory must not be misreported as a
    # failure just because VLC would reuse the previous run's scene filename.
    shot = tmp_path / "shots"
    shot.mkdir()
    prefixes = []

    def _fake_run(cmd, **kw):
        prefix = next(a.split("=", 1)[1] for a in cmd if a.startswith("--scene-prefix="))
        prefixes.append(prefix)
        (shot / f"{prefix}00001.png").write_bytes(b"\x89PNG")  # VLC's real naming
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(vlc_backend, "find_vlc", lambda: Path("vlc-stub"))
    monkeypatch.setattr(vlc_backend.subprocess, "run", _fake_run)

    j = proj.new_job()
    j["inputs"].append("in.mp4")
    j["snapshot"] = {"path": str(shot), "time": 1.0, "ratio": 1}
    first = vlc_backend.run_snapshot(j)
    second = vlc_backend.run_snapshot(j)  # same directory, second invocation
    assert first["count"] == 1 and second["count"] == 1
    assert Path(first["snapshot"]) != Path(second["snapshot"])
    assert prefixes[0] != prefixes[1]


# ── fourth-round review fixes ───────────────────────────────────────────

def test_load_job_normalizes_null_inputs(tmp_path):
    # Fourth-round fix: an explicit null for a defaulted container means "unset", not a
    # type error waiting to blow up in job_summary (list(None) / len(None)).
    p = tmp_path / "null.json"
    p.write_text(json.dumps({"software": "vlc", "inputs": None}), encoding="utf-8")
    job = proj.load_job(p)
    assert job["inputs"] == []
    assert proj.job_summary(job)["input_count"] == 0


def test_run_info_bounds_playback(monkeypatch):
    # Fourth-round fix (P1): a probe must return in bounded time regardless of media
    # length, instead of waiting for EOF and being killed by the fixed timeout.
    captured = {}
    monkeypatch.setattr(vlc_backend, "find_vlc", lambda: Path("vlc-stub"))

    def _fake_run(cmd, **kw):
        captured["cmd"] = cmd
        captured["timeout"] = kw.get("timeout")
        return subprocess.CompletedProcess(cmd, 0, stdout="duration: 1 s", stderr="")

    monkeypatch.setattr(vlc_backend.subprocess, "run", _fake_run)
    vlc_backend.run_info("/media/long.mp4", timeout=5)

    run_time = next(a for a in captured["cmd"] if a.startswith("--run-time="))
    assert int(run_time.split("=", 1)[1]) <= 5  # playback is bounded, not media-length
    # timeout is sized from the probe window, never below it
    assert captured["timeout"] == vlc_backend._INFO_PROBE_SECONDS + 30


def test_repl_binds_missing_project_path(tmp_path, monkeypatch):
    # Fourth-round fix: `--project new.json` that does not exist yet is the file to
    # create, so the REPL must bind it (auto-save + bare `save` destination).
    job = tmp_path / "new.json"
    script = [f"set-output {tmp_path / 'o.mp4'}", "quit"]

    class _FakeSkin:
        def __init__(self, *a, **k):
            pass

        def print_banner(self):
            pass

        def create_prompt_session(self):
            return object()

        def get_input(self, pt, project_name=None, modified=False):
            return script.pop(0) if script else "quit"

        def success(self, *a, **k):
            pass

        def error(self, *a, **k):
            pass

        def info(self, *a, **k):
            pass

        def status_block(self, *a, **k):
            pass

        def help(self, *a, **k):
            pass

        def print_goodbye(self):
            pass

    monkeypatch.setattr(vlc_cli, "ReplSkin", _FakeSkin)
    vlc_cli._repl(job)

    assert job.is_file(), "the requested --project path should have been created"
    saved = json.loads(job.read_text(encoding="utf-8"))
    assert saved["output"]["path"].endswith("o.mp4")


def test_set_option_rejects_unknown_key(tmp_path):
    # Fourth-round fix: a mistyped option key must fail loudly instead of being
    # persisted and then silently ignored by the sout builder.
    job = tmp_path / "job.json"
    proj.save_job(proj.new_job(), job)
    before = job.read_text(encoding="utf-8")

    runner = CliRunner()
    r = runner.invoke(vlc_cli.cli, ["--json", "--project", str(job),
                                    "set-option", "vcdoec", "h265"])
    assert r.exit_code == 1
    payload = json.loads(r.output)
    assert payload.get("error")
    assert "vcdoec" in payload.get("detail", "")
    assert "vcodec" in payload.get("detail", "")  # the documented set is offered back
    assert job.read_text(encoding="utf-8") == before  # nothing persisted
    assert "vcdoec" not in job.read_text(encoding="utf-8")


def test_repl_set_option_rejects_unknown_key(tmp_path, monkeypatch):
    # Same guard on the REPL path.
    errors = []
    script = ["set-option vcdoec h265", "quit"]

    class _FakeSkin:
        def __init__(self, *a, **k):
            pass

        def print_banner(self):
            pass

        def create_prompt_session(self):
            return object()

        def get_input(self, pt, project_name=None, modified=False):
            return script.pop(0) if script else "quit"

        def success(self, *a, **k):
            pass

        def error(self, msg):
            errors.append(msg)

        def info(self, *a, **k):
            pass

        def status_block(self, *a, **k):
            pass

        def help(self, *a, **k):
            pass

        def print_goodbye(self):
            pass

    monkeypatch.setattr(vlc_cli, "ReplSkin", _FakeSkin)
    vlc_cli._repl(None)
    assert errors and "vcdoec" in errors[0]


# ── structured-error contract sweep ─────────────────────────────────────

def test_cli_info_missing_file_is_structured(tmp_path):
    # A missing media file must surface as a structured --json error, not a Click
    # usage error (exit 2, human-only text, empty stdout).
    runner = CliRunner()
    r = runner.invoke(vlc_cli.cli, ["--json", "info", str(tmp_path / "nope.mp4")])
    assert r.exit_code == 1
    payload = json.loads(r.output)
    assert payload.get("error")
    assert "nope.mp4" in payload.get("detail", "")


def test_cli_add_input_missing_file_is_structured(tmp_path):
    job = tmp_path / "job.json"
    proj.save_job(proj.new_job(), job)
    runner = CliRunner()
    r = runner.invoke(vlc_cli.cli, ["--json", "--project", str(job),
                                    "add-input", str(tmp_path / "nope.mp4")])
    assert r.exit_code == 1
    assert json.loads(r.output).get("error")


def test_cli_set_output_directory_is_structured(tmp_path):
    job = tmp_path / "job.json"
    proj.save_job(proj.new_job(), job)
    runner = CliRunner()
    r = runner.invoke(vlc_cli.cli, ["--json", "--project", str(job), "set-output", str(tmp_path)])
    assert r.exit_code == 1
    payload = json.loads(r.output)
    assert payload.get("error")
    assert "directory" in payload.get("detail", "").lower()


def test_cli_project_show_without_project_is_structured():
    runner = CliRunner()
    r = runner.invoke(vlc_cli.cli, ["--json", "project", "show"])
    assert r.exit_code == 1
    payload = json.loads(r.output)
    assert payload.get("error")
    assert "project" in payload.get("detail", "").lower()


# ── fifth-round review fixes ────────────────────────────────────────────

def test_cli_project_new_unwritable_target_is_structured(tmp_path):
    # A target that cannot be written must surface as a structured --json error instead
    # of a traceback with an empty stdout. Assert on the contract only: the exception
    # type differs by platform (Windows PermissionError, POSIX IsADirectoryError) and
    # the message is *localised* ([WinError 5] 拒绝访问。), so no English substring.
    runner = CliRunner()
    r = runner.invoke(vlc_cli.cli, ["--json", "project", "new", "-o", str(tmp_path)])
    assert r.exit_code == 1
    payload = json.loads(r.output)
    assert payload.get("error") in {"IsADirectoryError", "PermissionError", "OSError"}
    assert payload.get("detail")
    # and the failed write must not leave a stray temp sibling behind
    assert list(tmp_path.parent.glob(".vlc-job-*")) == []


def test_cli_add_input_directory_is_structured(tmp_path):
    # A directory passed as FILE must reach the callback's is_file() check rather than
    # being rejected by click.Path(dir_okay=False) with exit 2 and human-only text.
    job = tmp_path / "job.json"
    proj.save_job(proj.new_job(), job)
    runner = CliRunner()
    r = runner.invoke(vlc_cli.cli, ["--json", "--project", str(job),
                                    "add-input", str(tmp_path)])
    assert r.exit_code == 1
    payload = json.loads(r.output)
    assert payload.get("error")
    assert "directory" in payload.get("detail", "").lower()


def test_cli_info_directory_is_structured(tmp_path):
    runner = CliRunner()
    r = runner.invoke(vlc_cli.cli, ["--json", "info", str(tmp_path)])
    assert r.exit_code == 1
    assert json.loads(r.output).get("error")


@pytest.mark.parametrize("bad", ["nan", "inf", "1e309"])
def test_set_option_rejects_non_finite_numbers(tmp_path, bad):
    # float() accepts nan/inf/1e309; those serialise as the NaN/Infinity tokens, which
    # are not valid JSON, so both the --json response and the saved project would be
    # unparseable for strict agent callers.
    # (`-inf` is deliberately absent: a leading dash is intercepted by Click's option
    # parser before the callback — the CLI-syntax class left out of the data contract.)
    job = tmp_path / "job.json"
    proj.save_job(proj.new_job(), job)
    before = job.read_text(encoding="utf-8")
    runner = CliRunner()
    r = runner.invoke(vlc_cli.cli, ["--json", "--project", str(job),
                                    "set-option", "vbitrate", bad])
    assert r.exit_code == 1
    payload = json.loads(r.output)
    assert payload.get("error")
    assert "finite" in payload.get("detail", "").lower()
    assert job.read_text(encoding="utf-8") == before  # nothing persisted


def test_set_option_rejects_non_numeric_value(tmp_path):
    job = tmp_path / "job.json"
    proj.save_job(proj.new_job(), job)
    runner = CliRunner()
    r = runner.invoke(vlc_cli.cli, ["--json", "--project", str(job),
                                    "set-option", "vbitrate", "fast"])
    assert r.exit_code == 1
    assert json.loads(r.output).get("error")


def test_load_job_rejects_non_finite_transcode(tmp_path):
    p = tmp_path / "nan.json"
    p.write_text(json.dumps({"software": "vlc", "inputs": ["a.mp4"],
                             "transcode": {"vbitrate": float("nan")}}), encoding="utf-8")
    with pytest.raises(ValueError, match="finite"):
        proj.load_job(p)


def test_load_job_rejects_boolean_transcode_value(tmp_path):
    p = tmp_path / "bool.json"
    p.write_text(json.dumps({"software": "vlc", "inputs": ["a.mp4"],
                             "transcode": {"vbitrate": True}}), encoding="utf-8")
    with pytest.raises(ValueError, match="vbitrate"):
        proj.load_job(p)


def test_load_job_rejects_scalar_extra(tmp_path):
    # A string `extra` would be extend()ed character by character into the sout chain.
    p = tmp_path / "extra.json"
    p.write_text(json.dumps({"software": "vlc", "inputs": ["a.mp4"],
                             "transcode": {"extra": "soverlay"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="extra"):
        proj.load_job(p)


def test_load_job_rejects_non_string_extra_items(tmp_path):
    p = tmp_path / "extra.json"
    p.write_text(json.dumps({"software": "vlc", "inputs": ["a.mp4"],
                             "transcode": {"extra": ["soverlay", 3]}}), encoding="utf-8")
    with pytest.raises(ValueError, match="extra"):
        proj.load_job(p)


def test_build_sout_treats_scalar_extra_as_single_option():
    # Defence in depth for jobs built in memory rather than loaded from disk.
    j = proj.new_job()
    j["inputs"].append("in.mp4")
    j["output"] = {"path": "out.mp4", "format": "mp4"}
    j["transcode"]["extra"] = "soverlay"
    s = transcode.build_transcode_sout(j)
    assert "soverlay" in s
    assert "s,o,v,e,r,l,a,y" not in s


# ── sixth-round review fixes ────────────────────────────────────────────

def test_find_vlc_rejects_runnable_binary_that_is_not_vlc(monkeypatch, tmp_path):
    # /bin/true is runnable but is not VLC: doctor must not report ready against it.
    fake = tmp_path / "vlc"
    fake.write_text("#!/bin/sh\ntrue\n", encoding="utf-8")
    fake.chmod(0o755)  # POSIX: without the exec bit find_vlc() rejects before the probe
    monkeypatch.setenv("VLC_BINARY", str(fake))
    monkeypatch.setattr(
        vlc_backend.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 0, stdout="true (GNU coreutils) 9.4", stderr=""))
    with pytest.raises(RuntimeError, match="does not identify"):
        vlc_backend.find_vlc()


def test_find_vlc_accepts_binary_that_identifies_as_vlc(monkeypatch, tmp_path):
    fake = tmp_path / "vlc"
    fake.write_text("stub", encoding="utf-8")
    fake.chmod(0o755)  # POSIX: without the exec bit find_vlc() rejects before the probe
    monkeypatch.setenv("VLC_BINARY", str(fake))
    monkeypatch.setattr(
        vlc_backend.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 0, stdout="VLC media player 3.0.21 Vetinari", stderr=""))
    assert vlc_backend.find_vlc() == fake


def test_find_vlc_probe_failure_is_rejected(monkeypatch, tmp_path):
    # A candidate whose --version probe cannot even run must not be accepted.
    fake = tmp_path / "vlc"
    fake.write_text("stub", encoding="utf-8")
    fake.chmod(0o755)  # POSIX: without the exec bit find_vlc() rejects before the probe
    monkeypatch.setenv("VLC_BINARY", str(fake))

    def _boom(cmd, **kw):
        raise OSError("cannot execute")

    monkeypatch.setattr(vlc_backend.subprocess, "run", _boom)
    with pytest.raises(RuntimeError):
        vlc_backend.find_vlc()


def test_build_sout_null_output_format_uses_mp4_default():
    j = proj.new_job()
    j["inputs"].append("in.mp4")
    j["output"] = {"path": "out.mp4", "format": None}
    s = transcode.build_transcode_sout(j)
    assert "mux=none" not in s
    assert "mux=mp4" in s


def test_build_stream_sout_null_mux_uses_ts_default():
    j = proj.new_job()
    j["inputs"].append("in.mp4")
    j["stream"] = {"protocol": "rtp", "dst": "127.0.0.1", "port": 5004, "mux": None}
    s = transcode.build_stream_sout(j)
    assert "mux=none" not in s
    assert "mux=ts" in s


def test_build_snapshot_args_defaults_missing_time():
    # A loaded snapshot may omit `time`; without a seek + run-time bound the scene
    # filter would capture frames all the way to EOF.
    j = proj.new_job()
    j["snapshot"] = {"path": "/tmp/shots", "ratio": 1}
    args = transcode.build_snapshot_args(j)
    assert any(a.startswith("--start-time=") for a in args)
    assert any(a.startswith("--run-time=") for a in args)


def test_build_snapshot_args_tolerates_null_time_and_ratio():
    j = proj.new_job()
    j["snapshot"] = {"path": "/tmp/shots", "time": None, "ratio": None}
    args = transcode.build_snapshot_args(j)  # int(None) used to raise TypeError
    assert "--scene-ratio=1" in args
    assert "--start-time=1.0" in args


@pytest.mark.parametrize("bad", ["nan", "inf", "1e309"])
def test_set_snapshot_rejects_non_finite_time(tmp_path, bad):
    job = tmp_path / "job.json"
    proj.save_job(proj.new_job(), job)
    before = job.read_text(encoding="utf-8")
    runner = CliRunner()
    r = runner.invoke(vlc_cli.cli, ["--json", "--project", str(job), "set-snapshot",
                                    "--path", str(tmp_path), "--time", bad])
    assert r.exit_code == 1
    payload = json.loads(r.output)
    assert payload.get("error")
    assert "finite" in payload.get("detail", "").lower()
    assert job.read_text(encoding="utf-8") == before


def test_run_snapshot_cleans_up_when_vlc_fails(monkeypatch, tmp_path):
    # Frames already written when VLC fails must not be left in the output directory.
    shot = tmp_path / "shots"
    shot.mkdir()
    written = []

    def _fake_run(cmd, **kw):
        prefix = next(a.split("=", 1)[1] for a in cmd if a.startswith("--scene-prefix="))
        p = shot / f"{prefix}00001.png"
        p.write_bytes(b"\x89PNG-partial")
        written.append(p)
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")

    monkeypatch.setattr(vlc_backend, "find_vlc", lambda: Path("vlc-stub"))
    monkeypatch.setattr(vlc_backend.subprocess, "run", _fake_run)

    j = proj.new_job()
    j["inputs"].append("in.mp4")
    j["snapshot"] = {"path": str(shot), "time": 1.0, "ratio": 1}
    with pytest.raises(RuntimeError):
        vlc_backend.run_snapshot(j)
    assert list(shot.glob("*.png")) == []
    assert all(not p.exists() for p in written)


def test_readme_command_table_matches_the_cli():
    # The documented command groups must not advertise commands that do not exist.
    readme = (Path(__file__).resolve().parents[5] / "vlc" / "agent-harness"
              / "cli_anything" / "vlc" / "README.md")
    if not readme.is_file():
        pytest.skip("README not present")
    text = readme.read_text(encoding="utf-8")
    runner = CliRunner()
    root = runner.invoke(vlc_cli.cli, ["--help"]).output
    group = runner.invoke(vlc_cli.cli, ["project", "--help"]).output

    # Every command named in the table must exist on the matching surface.
    assert "project open" not in text.replace("`", "")
    for name in ("new", "show"):
        assert name in group, f"`project {name}` is documented but missing"
    for name in ("add-input", "set-output", "set-option", "set-stream", "set-snapshot",
                 "clear", "transcode", "stream", "snapshot", "info", "doctor"):
        assert name in root, f"`{name}` is documented but missing"
    # undo/redo are REPL-only, so the table must say so rather than list them as commands.
    assert "REPL only" in text


# ── class-wide sweep (same bug classes as earlier rounds, other paths) ───

def test_build_stream_sout_null_dst_and_port_use_defaults():
    # `get(k, default)` returns the stored null: dst used to reach the chain as
    # `dst=None` and `int(None)` raised TypeError.
    j = proj.new_job()
    j["inputs"].append("in.mp4")
    j["stream"] = {"protocol": "udp", "dst": None, "port": None, "mux": "ts"}
    s = transcode.build_stream_sout(j)
    assert "dst=None" not in s
    assert "dst=127.0.0.1" in s
    assert "port=1234" in s


@pytest.mark.parametrize("bad", ["abc", 1e309, 0, 70000, -1, ""])
def test_build_stream_sout_rejects_or_defaults_bad_port(bad):
    j = proj.new_job()
    j["inputs"].append("in.mp4")
    j["stream"] = {"protocol": "udp", "dst": "127.0.0.1", "port": bad, "mux": "ts"}
    if bad == "":
        # an empty string means "unset" and falls back to the documented default
        assert "port=1234" in transcode.build_stream_sout(j)
    else:
        with pytest.raises(ValueError, match="port"):
            transcode.build_stream_sout(j)


def test_load_job_rejects_invalid_stream_fields(tmp_path):
    cases = [
        ({"protocol": 1}, "protocol"),
        ({"dst": 2}, "dst"),
        ({"mux": 3}, "mux"),
        ({"port": "abc"}, "port"),
        ({"port": 0}, "port"),
        ({"port": 70000}, "port"),
        ({"port": float("nan")}, "port"),
    ]
    for extra, needle in cases:
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"software": "vlc", "inputs": ["a.mp4"],
                                 "stream": {"protocol": "udp", "dst": "127.0.0.1",
                                            "port": 6004, "mux": "ts", **extra}}),
                     encoding="utf-8")
        with pytest.raises(ValueError, match=needle):
            proj.load_job(p)


def test_load_job_accepts_valid_stream(tmp_path):
    p = tmp_path / "ok.json"
    p.write_text(json.dumps({"software": "vlc", "inputs": ["a.mp4"],
                             "stream": {"protocol": "udp", "dst": "127.0.0.1",
                                        "port": 6004, "mux": "ts"}}), encoding="utf-8")
    assert proj.load_job(p)["stream"]["port"] == 6004


def test_load_job_rejects_invalid_snapshot_fields(tmp_path):
    cases = [
        ({"path": 1}, "snapshot.path"),
        ({"ratio": 0}, "snapshot.ratio"),
        ({"ratio": "x"}, "snapshot.ratio"),
        ({"time": -1}, "snapshot.time"),
        ({"time": float("nan")}, "snapshot.time"),
        ({"time": "soon"}, "snapshot.time"),
    ]
    for extra, needle in cases:
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"software": "vlc", "inputs": ["a.mp4"],
                                 "snapshot": {"path": "/tmp/s", "time": 1.0,
                                              "ratio": 1, **extra}}), encoding="utf-8")
        with pytest.raises(ValueError, match=re.escape(needle)):
            proj.load_job(p)


def test_documented_doctor_shape_matches_reality():
    # The workflow doc's doctor example must describe the document the CLI actually
    # emits; it used to advertise `binary` / `version` keys that do not exist.
    doc = (Path(__file__).resolve().parents[5] / "vlc" / "agent-harness"
           / "examples" / "agent-workflows.md")
    if not doc.is_file():
        pytest.skip("examples doc not present")
    text = doc.read_text(encoding="utf-8")
    match = re.search(r"#\s*->\s*(\{.*\})\s*\(exit 0\)", text)
    assert match, "the doctor section must show a ready:true JSON example"
    documented = set(json.loads(match.group(1)))

    runner = CliRunner()
    result = runner.invoke(vlc_cli.cli, ["--json", "doctor"])
    # The shape must hold whether or not VLC is installed here: exit 0 when it is,
    # 1 when it is not. Asserting a specific code made this test fail on any machine
    # that actually has VLC — i.e. on the maintainer's.
    assert result.exit_code in (0, 1)
    actual = set(json.loads(result.output))
    assert documented == actual, (
        f"doc documents {sorted(documented)} but doctor emits {sorted(actual)}"
    )
    # the failure example must describe the same shape
    assert '"checks"' in text and '"ready"' in text


# ── seventh-round review fixes ──────────────────────────────────────────

def test_find_vlc_rejects_probe_that_exits_nonzero(monkeypatch, tmp_path):
    # Printing "VLC" is not enough: a nonzero --version status means the binary is
    # broken, and doctor must not report ready against it.
    fake = tmp_path / "vlc"
    fake.write_text("stub", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("VLC_BINARY", str(fake))
    monkeypatch.setattr(
        vlc_backend.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 3, stdout="VLC media player 3.0.21", stderr="fatal: no plugins"))
    with pytest.raises(RuntimeError, match="does not identify"):
        vlc_backend.find_vlc()


def test_set_snapshot_rejects_zero_ratio(tmp_path):
    # A zero ratio used to be persisted and then silently replaced by 1 at build time,
    # so the run captured a different cadence than the saved spec.
    job = tmp_path / "job.json"
    proj.save_job(proj.new_job(), job)
    before = job.read_text(encoding="utf-8")
    runner = CliRunner()
    r = runner.invoke(vlc_cli.cli, ["--json", "--project", str(job), "set-snapshot",
                                    "--path", str(tmp_path), "--ratio", "0"])
    assert r.exit_code == 1
    payload = json.loads(r.output)
    assert payload.get("error")
    assert "ratio" in payload.get("detail", "").lower()
    assert job.read_text(encoding="utf-8") == before


def test_build_snapshot_args_rejects_zero_ratio():
    j = proj.new_job()
    j["snapshot"] = {"path": "/tmp/shots", "time": 1.0, "ratio": 0}
    with pytest.raises(ValueError, match="ratio"):
        transcode.build_snapshot_args(j)


def test_build_snapshot_args_rejects_non_integer_ratio():
    j = proj.new_job()
    j["snapshot"] = {"path": "/tmp/shots", "time": 1.0, "ratio": "every"}
    with pytest.raises(ValueError, match="ratio"):
        transcode.build_snapshot_args(j)


class _ScriptedSkin:
    """Minimal ReplSkin stand-in that feeds a fixed command script and records errors."""

    def __init__(self, script, errors):
        self._script = list(script)
        self._errors = errors

    def __call__(self, *a, **k):
        return self

    def print_banner(self):
        pass

    def create_prompt_session(self):
        return object()

    def get_input(self, pt, project_name=None, modified=False):
        return self._script.pop(0) if self._script else "quit"

    def success(self, *a, **k):
        pass

    def error(self, msg):
        self._errors.append(msg)

    def info(self, *a, **k):
        pass

    def status_block(self, *a, **k):
        pass

    def help(self, *a, **k):
        pass

    def print_goodbye(self):
        pass


def _run_repl(script, monkeypatch, project=None):
    """Drive _repl() with a scripted skin; return the error messages it emitted."""
    errors: list = []

    def _factory(*a, **k):
        return _ScriptedSkin(script, errors)

    monkeypatch.setattr(vlc_cli, "ReplSkin", _factory)
    vlc_cli._repl(project)
    return errors


def test_skill_copies_stay_in_sync():
    # registry.json points agents at the root copy, so the two must not diverge — and
    # neither may place root options after the subcommand they belong to.
    root_dir = Path(__file__).resolve().parents[5]
    root = root_dir / "skills" / "cli-anything-vlc" / "SKILL.md"
    packaged = (root_dir / "vlc" / "agent-harness" / "cli_anything" / "vlc"
                / "skills" / "SKILL.md")
    if not (root.is_file() and packaged.is_file()):
        pytest.skip("skill copies not present")

    assert root.read_text(encoding="utf-8") == packaged.read_text(encoding="utf-8"), (
        "the registry-facing root SKILL.md and the packaged copy have diverged"
    )
    for line in root.read_text(encoding="utf-8").splitlines():
        if "project show" not in line or not line.strip().startswith("cli-anything-vlc"):
            continue
        assert line.index("--project") < line.index("project show"), line
        assert line.index("--json") < line.index("project show"), line


# ── class sweep, second pass: REPL path + on-disk atomicity ─────────────

def test_repl_add_input_rejects_missing_file(monkeypatch, tmp_path):
    # The Click path validates existence; the REPL used to accept a typo'd path and
    # only fail later, inside VLC.
    errors = _run_repl([f"add-input {tmp_path / 'nope.mp4'}", "quit"], monkeypatch)
    assert errors and "not found" in errors[0].lower()


def test_repl_add_input_accepts_existing_file(monkeypatch, tmp_path):
    media = tmp_path / "in.mp4"
    media.write_text("x", encoding="utf-8")
    job = tmp_path / "job.json"
    proj.save_job(proj.new_job(), job)
    errors = _run_repl([f"add-input {media}", "quit"], monkeypatch, project=job)
    assert not errors
    assert json.loads(job.read_text(encoding="utf-8"))["inputs"] == [str(media)]


def test_repl_set_output_rejects_directory(monkeypatch, tmp_path):
    errors = _run_repl([f"set-output {tmp_path}", "quit"], monkeypatch)
    assert errors and "directory" in errors[0].lower()


def test_save_job_is_atomic_on_success(tmp_path):
    target = tmp_path / "job.json"
    meta = proj.save_job(proj.new_job(), target)
    assert target.is_file()
    assert meta["size_bytes"] == target.stat().st_size
    assert list(tmp_path.glob(".vlc-job-*")) == []


def test_save_job_leaves_no_temp_and_keeps_old_file_on_failure(monkeypatch, tmp_path):
    # An interrupted write must not leave a truncated project behind for the next
    # load_job to choke on, nor a stray temp sibling.
    target = tmp_path / "job.json"
    proj.save_job(proj.new_job(), target)
    before = target.read_text(encoding="utf-8")

    def _boom(src, dst):
        raise OSError("simulated interruption")

    monkeypatch.setattr(proj.os, "replace", _boom)
    with pytest.raises(OSError):
        proj.save_job({**proj.new_job(), "inputs": ["x"]}, target)
    assert target.read_text(encoding="utf-8") == before
    assert list(tmp_path.glob(".vlc-job-*")) == []


def test_repl_skin_construction_does_not_write_home(monkeypatch, tmp_path):
    # Constructing the skin must not touch HOME: a read-only HOME used to raise
    # before _repl()'s error handling was in place, killing the REPL on startup.
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    skin = ReplSkin("vlc", version="1.0.0")
    assert not (fake_home / ".cli-anything-vlc").exists()
    assert skin.history_file.replace("\\", "/").endswith(".cli-anything-vlc/history")
