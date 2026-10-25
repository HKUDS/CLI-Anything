"""End-to-end tests for cli-anything-voxtype against the REAL voxtype binary.

Hard dependencies (tests fail, never skip): voxtype, ffmpeg, an installed
whisper model. All writes go to temporary config files and meeting storage;
the user's real config and meetings are never modified.

    CLI_ANYTHING_FORCE_INSTALLED=1 python -m pytest cli_anything/voxtype/tests/ -v -s
"""

import csv
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile

import pytest

from cli_anything.voxtype.core import config as config_mod
from cli_anything.voxtype.core import daemon as daemon_mod
from cli_anything.voxtype.core import meeting as meeting_mod
from cli_anything.voxtype.core import system as system_mod
from cli_anything.voxtype.core import transcribe as transcribe_mod
from cli_anything.voxtype.utils import audio as audio_mod
from cli_anything.voxtype.utils import voxtype_backend as backend
from cli_anything.voxtype.utils.voxtype_backend import VoxtypeError

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
HELLO = os.path.join(FIXTURES, "speech_hello.wav")
LONG = os.path.join(FIXTURES, "speech_long.wav")
SILENCE = os.path.join(FIXTURES, "silence_2s.wav")
LONG_TEXT = "This is a longer test of voice activity detection with multiple words and phrases."


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="vt-e2e-")
    yield d
    if os.environ.get("VT_KEEP_ARTIFACTS") != "1":
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def cfg(tmp_dir):
    """A scratch voxtype config with meetings stored in the temp dir."""
    path = os.path.join(tmp_dir, "config.toml")
    backend.run(["config", "set", "meeting.storage_path", os.path.join(tmp_dir, "meetings")], path)
    return path


# ── Prerequisites ───────────────────────────────────────────────────────

class TestPrerequisites:
    def test_voxtype_installed(self):
        path = backend.find_voxtype()
        v = backend.version()
        print(f"\n  voxtype: {path} ({v})")
        assert re.match(r"\d+\.\d+", v)

    def test_ffmpeg_installed(self):
        assert backend.find_ffmpeg()

    def test_whisper_model_installed(self):
        models = system_mod.installed_models(engine="whisper")
        print(f"\n  installed whisper models: {[m['name'] for m in models]}")
        assert models, "No whisper model installed: voxtype setup --download --model base.en"

    def test_fixtures_are_voxtype_native(self):
        for f in (HELLO, LONG, SILENCE):
            assert audio_mod.is_voxtype_native(audio_mod.probe_wav(f))


# ── Config (real validator, real TOML editor) ───────────────────────────

class TestConfigE2E:
    def test_set_get_unset_roundtrip(self, cfg):
        e = config_mod.set_key("hotkey.key", "F13", cfg)
        assert e["old"] is None and e["new"] == "F13" and e["restart_required"]
        assert 'key = "F13"' in open(cfg).read()
        assert config_mod.get_key("hotkey.key", cfg)["value"] == "F13"
        config_mod.unset_key("hotkey.key", cfg)
        assert "F13" not in open(cfg).read()
        assert config_mod.get_key("hotkey.key", cfg)["file_value"] is None

    def test_typed_values(self, cfg):
        config_mod.set_key("audio.feedback.volume", "0.25", cfg)
        config_mod.set_key("text.spoken_punctuation", "yes", cfg)
        config_mod.set_key("audio.max_duration_secs", "90", cfg)
        assert config_mod.get_key("audio.feedback.volume", cfg)["value"] == pytest.approx(0.25)
        assert config_mod.get_key("text.spoken_punctuation", cfg)["value"] is True
        assert config_mod.get_key("audio.max_duration_secs", cfg)["value"] == 90

    def test_invalid_value_rejected_file_unchanged(self, cfg):
        before = open(cfg).read()
        with pytest.raises(VoxtypeError) as ei:
            config_mod.set_key("audio.feedback.volume", "9", cfg)
        assert ei.value.returncode == 2 and "out of range" in str(ei.value)
        with pytest.raises(VoxtypeError) as ei:
            config_mod.set_key("no.such.key", "1", cfg)
        assert ei.value.returncode == 2
        assert open(cfg).read() == before

    def test_dry_run_validates_without_writing(self, cfg):
        before = open(cfg).read()
        e = config_mod.set_key("hotkey.key", "F13", cfg, dry_run=True)
        assert e["new"] == "F13" and e["dry_run"]
        with pytest.raises(VoxtypeError):
            config_mod.set_key("hotkey.mode", "sideways", cfg, dry_run=True)
        assert open(cfg).read() == before

    def test_undo_restores_previous_value(self, cfg):
        config_mod.set_key("hotkey.key", "F13", cfg)
        e = config_mod.set_key("hotkey.key", "PAUSE", cfg)
        assert e["old"] == "F13"
        config_mod.undo_entry(e)
        assert config_mod.get_key("hotkey.key", cfg)["file_value"] == "F13"
        config_mod.redo_entry(e)
        assert config_mod.get_key("hotkey.key", cfg)["file_value"] == "PAUSE"

    def test_replacements(self, cfg):
        config_mod.set_key("text.replacements.btw", "by the way", cfg)
        assert config_mod.replacements(cfg) == {"btw": "by the way"}
        changed = {d["key"] for d in config_mod.diff_against_defaults(cfg)}
        assert "text.replacements.btw" in changed and "meeting.storage_path" in changed
        config_mod.unset_key("text.replacements.btw", cfg)
        assert config_mod.replacements(cfg) == {}

    def test_schema_filters(self, cfg):
        s = config_mod.schema(cfg, section="Text")
        assert s["keys"] and all(k["section"] == "Text" for k in s["keys"])
        assert config_mod.schema(cfg, search="spoken_punctuation")["keys"]
        assert config_mod.resolved_path(cfg) == os.path.abspath(cfg)
        assert any(sec["section"] == "Engine" for sec in config_mod.sections(cfg))


# ── Transcription (real whisper via voxtype) ────────────────────────────

class TestTranscribeE2E:
    def test_hello(self, cfg):
        r = transcribe_mod.transcribe_file(HELLO, cfg)
        print(f"\n  {HELLO} -> {r['text']!r} ({r['elapsed_secs']}s)")
        assert _norm(r["text"]) == "hello world"
        assert r["duration_secs"] == pytest.approx(audio_mod.probe_wav(HELLO)["duration_secs"], abs=0.02)
        assert r["converted"] is False and r["resampled"] is False

    def test_long(self, cfg):
        r = transcribe_mod.transcribe_file(LONG, cfg)
        assert _norm(r["text"]) == _norm(LONG_TEXT)
        assert r["words"] == len(LONG_TEXT.split())

    def test_replacement_applied_by_voxtype(self, cfg):
        config_mod.set_key("text.replacements.voice activity detection", "VAD", cfg)
        r = transcribe_mod.transcribe_file(LONG, cfg)
        assert "VAD" in r["text"] and "voice activity detection" not in r["text"].lower()

    def test_mp3_converted_by_ffmpeg(self, cfg, tmp_dir):
        mp3 = os.path.join(tmp_dir, "long.mp3")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", LONG, "-ar", "44100", "-ac", "2", mp3],
                       check=True)
        with open(mp3, "rb") as f:
            head = f.read(3)
        assert head == b"ID3" or head[:2] in (b"\xff\xfb", b"\xff\xf3")
        keep = os.path.join(tmp_dir, "converted.wav")
        r = transcribe_mod.transcribe_file(mp3, cfg, keep_converted=keep)
        print(f"\n  MP3: {mp3} -> converted {keep}")
        assert r["converted"] is True
        assert _norm(r["text"]) == _norm(LONG_TEXT)
        assert audio_mod.is_voxtype_native(audio_mod.probe_wav(keep))

    def test_48k_stereo_resampled_by_voxtype(self, cfg, tmp_dir):
        wav = os.path.join(tmp_dir, "hello48.wav")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", HELLO, "-ar", "48000", "-ac", "2", wav],
                       check=True)
        r = transcribe_mod.transcribe_file(wav, cfg)
        assert r["sample_rate_in"] == 48000 and r["channels_in"] == 2 and r["resampled"] is True
        assert _norm(r["text"]) == "hello world"

    def test_silence_with_energy_vad(self, cfg):
        assert audio_mod.rms_dbfs(SILENCE) < -80  # near-silence (LSB dither)
        r = transcribe_mod.transcribe_file(SILENCE, cfg, {"vad": True, "vad_backend": "energy"})
        assert r["no_speech"] is True and r["text"] == ""
        assert r["vad"]["speech_secs"] == 0.0

    def test_speech_passes_energy_vad(self, cfg):
        r = transcribe_mod.transcribe_file(HELLO, cfg, {"vad": True, "vad_backend": "energy"})
        assert r["vad"]["speech_percent"] > 30 and _norm(r["text"]) == "hello world"

    def test_missing_file(self, cfg):
        with pytest.raises(FileNotFoundError):
            transcribe_mod.transcribe_file("/nonexistent/a.wav", cfg)

    def test_bad_engine_errors(self, cfg):
        with pytest.raises(VoxtypeError):
            transcribe_mod.transcribe_file(HELLO, cfg, engine="bogus")


# ── Meetings (native storage, voxtype exporters) ────────────────────────

class TestMeetingE2E:
    def _import(self, cfg):
        return meeting_mod.import_meeting([HELLO, LONG], "Standup Sync", [0, 1], 500, cfg)

    def test_import_creates_native_meeting(self, cfg, tmp_dir):
        m = self._import(cfg)
        storage = meeting_mod.storage_dir(cfg)
        assert storage == os.path.join(tmp_dir, "meetings")
        conn = sqlite3.connect(os.path.join(storage, "index.db"))
        row = conn.execute("SELECT title, status, chunk_count FROM meetings WHERE id=?", (m["id"],)).fetchone()
        conn.close()
        assert row == ("Standup Sync", "completed", 2)
        assert os.path.exists(os.path.join(m["storage_path"], "transcript.json"))
        # voxtype itself must be able to read it
        report = meeting_mod.show(m["id"], cfg)["report"]
        assert "Standup Sync" in report and "Segments: 2" in report

    def test_export_formats(self, cfg, tmp_dir):
        m = self._import(cfg)
        meeting_mod.label(m["id"], "1", "Alice", cfg)

        srt = meeting_mod.export("latest", os.path.join(tmp_dir, "m.srt"), "srt", config_path=cfg)
        body = open(srt["output"]).read()
        print(f"\n  SRT: {srt['output']} ({srt['file_size']} bytes)")
        stamps = re.findall(r"(\d\d:\d\d:\d\d,\d{3}) --> (\d\d:\d\d:\d\d,\d{3})", body)
        assert stamps == [("00:00:00,000", "00:00:01,030"), ("00:00:01,530", "00:00:06,280")]
        assert body.startswith("1\n")

        vtt = meeting_mod.export(m["id"][:8], os.path.join(tmp_dir, "m.vtt"), "vtt", config_path=cfg)
        assert open(vtt["output"]).read().startswith("WEBVTT")

        js = meeting_mod.export(m["id"], os.path.join(tmp_dir, "m.json"), "json", speakers=True, config_path=cfg)
        data = json.load(open(js["output"]))
        segs = data["transcript"]["segments"]
        assert [s["speaker"] for s in segs] == ["SPEAKER_00", "Alice"]
        assert _norm(segs[1]["text"]) == _norm(LONG_TEXT)

        md = meeting_mod.export(m["id"], os.path.join(tmp_dir, "m.md"), "md", speakers=True,
                                timestamps=True, config_path=cfg)
        text = open(md["output"]).read()
        assert text.startswith("# Standup Sync") and "### Alice" in text and "*[00:01]*" in text

        txt = meeting_mod.export(m["id"], None, "text", config_path=cfg)
        assert "Hello world" in txt["content"]

    def test_get_meeting_json_and_list(self, cfg):
        m = self._import(cfg)
        data = meeting_mod.get_meeting_json(m["id"], cfg)
        assert data["metadata"]["id"] == m["id"] and data["metadata"]["chunkCount"] == 2
        listing = meeting_mod.list_meetings(cfg)
        assert listing["count"] == 1 and listing["meetings"][0]["title"] == "Standup Sync"

    def test_export_overwrite_guard_and_bad_format(self, cfg, tmp_dir):
        self._import(cfg)
        out = os.path.join(tmp_dir, "x.md")
        meeting_mod.export("latest", out, config_path=cfg)
        with pytest.raises(FileExistsError):
            meeting_mod.export("latest", out, config_path=cfg)
        with pytest.raises(ValueError):
            meeting_mod.export("latest", None, "docx", config_path=cfg)

    def test_delete(self, cfg):
        m = self._import(cfg)
        meeting_mod.delete(m["id"], cfg)
        assert meeting_mod.list_meetings(cfg)["count"] == 0
        with pytest.raises(ValueError):
            meeting_mod.resolve_id(m["id"], cfg)


# ── Live system probes (read-only) ──────────────────────────────────────

class TestSystemE2E:
    def test_engines(self):
        engines = system_mod.info("engines")
        assert any(e["name"] == "whisper" and e["compiled"] for e in engines)

    def test_models_and_devices(self):
        models = system_mod.info("models", engine="whisper")
        assert "whisper" in models["engines"]
        devices = system_mod.info("devices")
        assert any(d["name"] == "default" for d in devices)

    def test_daemon_status_shape(self):
        st = daemon_mod.status()
        print(f"\n  daemon state: {st['state']} pid={st['pid']}")
        assert st["state"] in ("idle", "recording", "transcribing", "outputting", "stopped", "meeting")
        assert "tooltip" in st

    def test_service_status(self):
        st = daemon_mod.service("status")
        assert st["active"] in ("active", "inactive", "failed", "activating", "unknown", "")


# ── Installed CLI via subprocess ────────────────────────────────────────

def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = name.replace("cli-anything-", "cli_anything.") + "." + name.split("-")[-1] + "_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-voxtype")

    def _run(self, args, check=True):
        return subprocess.run(self.CLI_BASE + args, capture_output=True, text=True, check=check, timeout=600)

    def _json(self, args):
        return json.loads(self._run(["--json"] + args).stdout)

    def _workspace(self, tmp_dir):
        ws = os.path.join(tmp_dir, "ws.json")
        cfg = os.path.join(tmp_dir, "config.toml")
        self._run(["project", "new", "-o", ws, "--config", cfg])
        # via --config only, so the setup step is not in the workspace's undo history
        self._run(["--config", cfg, "config", "set", "meeting.storage_path", os.path.join(tmp_dir, "meetings")])
        return ws, cfg

    def test_help(self):
        r = self._run(["--help"])
        assert r.returncode == 0 and "transcribe" in r.stdout

    def test_version(self):
        assert "1.0.0" in self._run(["--version"]).stdout

    def test_info_engines_json(self):
        data = self._json(["info", "engines"])
        assert isinstance(data, list) and any(e["name"] == "whisper" for e in data)

    def test_project_new_json(self, tmp_dir):
        out = os.path.join(tmp_dir, "test.json")
        data = self._json(["project", "new", "-o", out, "--name", "t"])
        assert data["name"] == "t" and os.path.exists(out)
        assert json.load(open(out))["format"] == "cli-anything-voxtype/workspace-v1"

    def test_dictation_tuning_workflow(self, tmp_dir):
        """Workflow 1: replacement + transcribe + undo + redo, all persisted."""
        ws, cfg = self._workspace(tmp_dir)
        self._run(["--project", ws, "config", "replace", "add", "voice activity detection", "VAD"])
        r1 = self._json(["--project", ws, "transcribe", "file", LONG])
        assert "VAD" in r1["text"]
        undo = self._json(["--project", ws, "session", "undo"])
        assert undo["key"] == "text.replacements.voice activity detection" and undo["now"] is None
        assert "VAD" not in open(cfg).read()
        r2 = self._json(["--project", ws, "transcribe", "file", LONG])
        assert "voice activity detection" in r2["text"].lower()
        self._run(["--project", ws, "session", "redo"])
        assert '"voice activity detection" = "VAD"' in open(cfg).read()
        w = json.load(open(ws))
        assert len(w["transcriptions"]) == 2 and len(w["history"]) == 1 and w["redo"] == []

    def test_batch_workflow(self, tmp_dir):
        """Workflow 2: mixed formats in a folder → CSV + Markdown + history export."""
        ws, _ = self._workspace(tmp_dir)
        media = os.path.join(tmp_dir, "media")
        os.makedirs(media)
        shutil.copy(HELLO, media)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", LONG, os.path.join(media, "long.mp3")],
                       check=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", HELLO, "-ar", "48000", "-ac", "2",
                        os.path.join(media, "hello48.flac")], check=True)
        out_csv = os.path.join(tmp_dir, "out.csv")
        data = self._json(["--project", ws, "transcribe", "batch", media, "-o", out_csv])
        assert data["count"] == 3 and data["succeeded"] == 3 and data["failed"] == 0
        rows = list(csv.DictReader(open(out_csv)))
        print(f"\n  CSV: {out_csv} ({os.path.getsize(out_csv)} bytes)")
        assert {os.path.basename(r["file"]) for r in rows} == {"hello48.flac", "long.mp3", "speech_hello.wav"}
        assert all(r["text"] for r in rows)
        hist_json = os.path.join(tmp_dir, "all.json")
        self._run(["--project", ws, "transcribe", "export", hist_json])
        assert json.load(open(hist_json))["count"] == 3

    def test_meeting_workflow(self, tmp_dir):
        """Workflow 3: import → label → SRT export → delete."""
        ws, _ = self._workspace(tmp_dir)
        m = self._json(["--project", ws, "meeting", "import", HELLO, LONG, "-t", "Call", "--speakers", "0,1",
                        "--gap-ms", "500"])
        assert m["segments"] == 2
        listing = self._json(["--project", ws, "meeting", "list"])
        assert listing["count"] == 1
        self._run(["--project", ws, "meeting", "label", "latest", "SPEAKER_01", "Bob"])
        srt = os.path.join(tmp_dir, "call.srt")
        res = self._json(["--project", ws, "meeting", "export", "latest", "-f", "srt", "-o", srt])
        assert res["file_size"] > 0 and "00:00:01,530 --> 00:00:06,280" in open(srt).read()
        shown = self._json(["--project", ws, "meeting", "show", "latest"])
        assert [s["speaker"] for s in shown["transcript"]["segments"]] == ["SPEAKER_00", "Bob"]
        self._run(["--project", ws, "meeting", "delete", m["id"], "--yes"])
        assert self._json(["--project", ws, "meeting", "list"])["count"] == 0

    def test_dry_run_workflow(self, tmp_dir):
        """Workflow 4: dry-run never touches config or workspace."""
        ws, cfg = self._workspace(tmp_dir)
        cfg_before, ws_before = open(cfg).read(), open(ws).read()
        ok = self._json(["--project", ws, "--dry-run", "config", "set", "hotkey.key", "F13"])
        assert ok["dry_run"] and ok["new"] == "F13"
        bad = self._run(["--json", "--project", ws, "--dry-run", "config", "set", "audio.feedback.volume", "9"],
                        check=False)
        assert bad.returncode == 2 and "out of range" in json.loads(bad.stdout)["error"]
        assert open(cfg).read() == cfg_before and open(ws).read() == ws_before

    def test_undo_redo_stress(self, tmp_dir):
        """Workflow 5: 8 mixed operations, full undo, full redo."""
        ws, cfg = self._workspace(tmp_dir)
        original = config_mod.diff_against_defaults(cfg)
        ops = [["set", "hotkey.key", "F13"], ["set", "hotkey.mode", "toggle"],
               ["set", "audio.feedback.volume", "0.3"], ["set", "hotkey.key", "PAUSE"],
               ["unset", "hotkey.mode"], ["set", "text.spoken_punctuation", "true"],
               ["set", "audio.max_duration_secs", "120"], ["unset", "meeting.storage_path"]]
        for op in ops:
            self._run(["--project", ws, "config"] + op)
        final = config_mod.diff_against_defaults(cfg)
        for _ in ops:
            self._run(["--project", ws, "session", "undo"])
        assert config_mod.diff_against_defaults(cfg) == original
        empty = self._run(["--json", "--project", ws, "session", "undo"], check=False)
        assert empty.returncode == 1 and "Nothing to undo" in empty.stdout
        assert config_mod.diff_against_defaults(cfg) == original
        for _ in ops:
            self._run(["--project", ws, "session", "redo"])
        assert config_mod.diff_against_defaults(cfg) == final
        hist = self._json(["--project", ws, "session", "history", "-n", "100"])
        assert len(hist["history"]) == len(ops) and hist["redo"] == []

    def test_status_introspection(self, tmp_dir):
        """Workflow 6: cheap probes an agent runs before acting."""
        st = self._json(["daemon", "status"])
        assert "state" in st
        models = self._json(["info", "models", "--installed"])
        assert any(m["engine"] == "whisper" for m in models)
        schema = self._json(["config", "schema", "--section", "Text"])
        assert schema["keys"]

    def test_error_json_for_missing_audio(self):
        r = self._run(["--json", "transcribe", "file", "/nonexistent/x.wav"], check=False)
        assert r.returncode == 1 and json.loads(r.stdout)["type"] == "FileNotFoundError"
