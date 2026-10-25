"""Unit tests for cli-anything-voxtype core modules.

Synthetic data only: no voxtype binary, no audio model. Backend calls are
replaced with fakes where a module would otherwise shell out.
"""

import json
import os
import sqlite3
import subprocess
import tempfile

import pytest

from cli_anything.voxtype.core import config as config_mod
from cli_anything.voxtype.core import daemon as daemon_mod
from cli_anything.voxtype.core import meeting as meeting_mod
from cli_anything.voxtype.core import project as project_mod
from cli_anything.voxtype.core import transcribe as transcribe_mod
from cli_anything.voxtype.core.session import Session, _locked_save_json
from cli_anything.voxtype.utils import audio as audio_mod
from cli_anything.voxtype.utils import voxtype_backend as backend


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory(prefix="vt-unit-") as d:
        yield d


# ── project.py ─────────────────────────────────────────────────────────

class TestProject:
    def test_create_workspace_defaults(self):
        ws = project_mod.create_workspace("w")
        assert ws["format"] == project_mod.WORKSPACE_FORMAT
        assert ws["name"] == "w"
        assert ws["config_path"] is None
        assert ws["history"] == [] and ws["redo"] == [] and ws["overrides"] == {}

    def test_create_workspace_absolutizes_config(self):
        ws = project_mod.create_workspace("w", "rel/c.toml")
        assert os.path.isabs(ws["config_path"])

    def test_validate_rejects_wrong_format(self):
        with pytest.raises(ValueError):
            project_mod.validate_workspace({"format": "other"})

    def test_validate_fills_missing_fields(self):
        ws = project_mod.validate_workspace({"format": project_mod.WORKSPACE_FORMAT})
        assert ws["history"] == [] and ws["transcriptions"] == [] and ws["config_path"] is None

    def test_load_invalid_json(self, tmp_dir):
        p = os.path.join(tmp_dir, "bad.json")
        with open(p, "w") as f:
            f.write("{nope")
        with pytest.raises(ValueError):
            project_mod.load_workspace(p)

    def test_load_missing(self, tmp_dir):
        with pytest.raises(FileNotFoundError):
            project_mod.load_workspace(os.path.join(tmp_dir, "x.json"))

    def test_set_override_value(self):
        ws = project_mod.create_workspace()
        project_mod.set_override(ws, "language", "fr")
        assert ws["overrides"]["language"] == "fr"

    def test_set_override_unknown(self):
        with pytest.raises(ValueError):
            project_mod.set_override(project_mod.create_workspace(), "bogus", "1")

    def test_set_override_requires_value(self):
        with pytest.raises(ValueError):
            project_mod.set_override(project_mod.create_workspace(), "model", "")

    @pytest.mark.parametrize("raw,expected", [("yes", True), ("off", False), ("0", False), (None, True)])
    def test_set_override_bool_parsing(self, raw, expected):
        ws = project_mod.create_workspace()
        project_mod.set_override(ws, "translate", raw)
        assert ws["overrides"]["translate"] is expected

    def test_override_flags_translation(self):
        flags = project_mod.override_flags({"model": "base.en", "translate": True, "vad": False,
                                            "vad_backend": "energy", "unknown": "x"})
        assert flags == ["--model", "base.en", "--translate", "--vad-backend", "energy"]

    def test_remove_override_and_info(self):
        ws = project_mod.create_workspace("n")
        project_mod.set_override(ws, "model", "tiny")
        project_mod.remove_override(ws, "model")
        project_mod.remove_override(ws, "model")  # idempotent
        info = project_mod.workspace_info(ws, "ws.json")
        assert info["overrides"] == {} and info["history_depth"] == 0 and os.path.isabs(info["path"])


# ── session.py ─────────────────────────────────────────────────────────

class TestSession:
    def test_new_and_save_roundtrip(self, tmp_dir):
        p = os.path.join(tmp_dir, "sub", "ws.json")
        s = Session()
        s.new(p, "w", "/tmp/c.toml")
        assert s._modified
        s.save_session()
        assert not s._modified
        s2 = Session()
        s2.open(p)
        assert s2.workspace["config_path"] == "/tmp/c.toml"

    def test_save_without_workspace(self):
        with pytest.raises(RuntimeError):
            Session().save_session("/tmp/x.json")

    def test_undo_empty(self, tmp_dir):
        s = Session()
        s.new(os.path.join(tmp_dir, "w.json"), "w")
        with pytest.raises(RuntimeError):
            s.pop_undo()
        with pytest.raises(RuntimeError):
            s.pop_redo()

    def test_undo_redo_stacks(self, tmp_dir):
        s = Session()
        s.new(os.path.join(tmp_dir, "w.json"), "w")
        s.record({"op": "set", "key": "a", "old": None, "new": 1})
        s.record({"op": "set", "key": "b", "old": None, "new": 2})
        e = s.pop_undo()
        assert e["key"] == "b" and len(s.workspace["redo"]) == 1
        e = s.pop_redo()
        assert e["key"] == "b" and s.workspace["redo"] == []

    def test_new_record_clears_redo(self, tmp_dir):
        s = Session()
        s.new(os.path.join(tmp_dir, "w.json"), "w")
        s.record({"op": "set", "key": "a"})
        s.pop_undo()
        s.record({"op": "set", "key": "c"})
        assert s.workspace["redo"] == []

    def test_history_cap(self, tmp_dir):
        from cli_anything.voxtype.core import session as session_mod
        s = Session()
        s.new(os.path.join(tmp_dir, "w.json"), "w")
        for i in range(session_mod.MAX_HISTORY + 15):
            s.record({"op": "set", "key": f"k{i}"})
        assert len(s.workspace["history"]) == session_mod.MAX_HISTORY
        assert s.workspace["history"][-1]["key"] == f"k{session_mod.MAX_HISTORY + 14}"

    def test_record_without_workspace_is_noop(self):
        s = Session()
        s.record({"op": "set", "key": "a"})
        assert not s._modified

    def test_config_path_precedence(self, tmp_dir):
        s = Session()
        assert s.config_path() is None
        s.new(os.path.join(tmp_dir, "w.json"), "w", "/a/c.toml")
        assert s.config_path() == "/a/c.toml"
        s.config_override = "/b/c.toml"
        assert s.config_path() == "/b/c.toml"

    def test_locked_save_truncates(self, tmp_dir):
        p = os.path.join(tmp_dir, "x.json")
        _locked_save_json(p, {"a": "x" * 500})
        _locked_save_json(p, {"a": 1})
        with open(p) as f:
            assert json.load(f) == {"a": 1}

    def test_status_and_transcription_log(self, tmp_dir):
        s = Session()
        s.new(os.path.join(tmp_dir, "w.json"), "w")
        s.log_transcription({"file": "a.wav", "text": "hi"})
        st = s.status()
        assert st["has_workspace"] and st["transcriptions"] == 1


# ── transcribe.py ──────────────────────────────────────────────────────

SAMPLE_OUT = """Loading audio file: "a.wav"
Audio format: 44100 Hz, 2 channel(s), Int
Resampling from 44100 Hz to 16000 Hz...
Processing 76048 samples (4.75s)...
VAD: 3.20s speech (67.4% of audio)

This is a test.
Second line.
"""


class TestTranscribeParsing:
    def test_full_report(self):
        r = transcribe_mod.parse_transcribe_output(SAMPLE_OUT)
        assert r["sample_rate_in"] == 44100 and r["channels_in"] == 2
        assert r["resampled"] is True
        assert r["samples"] == 76048 and r["duration_secs"] == 4.75
        assert r["vad"] == {"speech_secs": 3.2, "speech_percent": 67.4}
        assert r["text"] == "This is a test.\nSecond line."

    def test_no_speech(self):
        out = ('Loading audio file: "s.wav"\nAudio format: 16000 Hz, 1 channel(s), Int\n'
               "Processing 32000 samples (2.00s)...\nVAD: 0.00s speech (0.0% of audio)\n"
               "No speech detected, skipping transcription.\n")
        r = transcribe_mod.parse_transcribe_output(out)
        assert r["no_speech"] is True and r["text"] == "" and r["duration_secs"] == 2.0

    def test_minimal(self):
        out = 'Loading audio file: "a"\nAudio format: 16000 Hz, 1 channel(s), Int\nProcessing 10 samples (0.00s)...\n\nHi\n'
        r = transcribe_mod.parse_transcribe_output(out)
        assert r["text"] == "Hi" and r["resampled"] is False and r["vad"] is None

    def test_garbage(self):
        r = transcribe_mod.parse_transcribe_output("nonsense\n")
        assert r["samples"] is None and r["text"] == ""


class TestCollectInputs:
    def test_dir_glob_and_dedupe(self, tmp_dir):
        for n in ("a.wav", "b.mp3", "notes.txt"):
            open(os.path.join(tmp_dir, n), "w").close()
        os.makedirs(os.path.join(tmp_dir, "sub"))
        open(os.path.join(tmp_dir, "sub", "c.flac"), "w").close()
        flat = transcribe_mod.collect_inputs([tmp_dir, os.path.join(tmp_dir, "a.wav")])
        assert [os.path.basename(f) for f in flat] == ["a.wav", "b.mp3"]
        rec = transcribe_mod.collect_inputs([tmp_dir], recursive=True)
        assert len(rec) == 3
        globbed = transcribe_mod.collect_inputs([os.path.join(tmp_dir, "*.mp3")])
        assert [os.path.basename(f) for f in globbed] == ["b.mp3"]

    def test_missing(self, tmp_dir):
        with pytest.raises(FileNotFoundError):
            transcribe_mod.collect_inputs([os.path.join(tmp_dir, "nope.wav")])


RESULTS = [
    {"file": "/x/a.wav", "text": "Hello world!", "duration_secs": 1.0, "words": 2, "elapsed_secs": 0.5,
     "no_speech": False},
    {"file": "/x/b.wav", "text": "", "duration_secs": 2.0, "words": 0, "elapsed_secs": 0.4, "no_speech": True},
]


class TestExportResults:
    @pytest.mark.parametrize("fmt", transcribe_mod.EXPORT_FORMATS)
    def test_each_format(self, tmp_dir, fmt):
        out = os.path.join(tmp_dir, f"r.{fmt}")
        res = transcribe_mod.export_results(RESULTS, out)
        assert res["format"] == fmt and res["file_size"] > 0
        body = open(out, encoding="utf-8").read()
        if fmt == "json":
            assert json.loads(body)["count"] == 2
        elif fmt == "jsonl":
            assert len(body.strip().splitlines()) == 2
        elif fmt == "csv":
            assert body.splitlines()[0].startswith("file,duration_secs")
            assert len(body.strip().splitlines()) == 3
        elif fmt == "md":
            assert "## a.wav" in body and "_(no speech)_" in body
        else:
            assert body.strip() == "Hello world!"

    def test_overwrite_guard(self, tmp_dir):
        out = os.path.join(tmp_dir, "r.txt")
        transcribe_mod.export_results(RESULTS, out)
        with pytest.raises(FileExistsError):
            transcribe_mod.export_results(RESULTS, out)
        transcribe_mod.export_results(RESULTS, out, overwrite=True)

    def test_bad_format_and_empty(self, tmp_dir):
        with pytest.raises(ValueError):
            transcribe_mod.export_results(RESULTS, os.path.join(tmp_dir, "r.xyz"))
        with pytest.raises(ValueError):
            transcribe_mod.export_results([], os.path.join(tmp_dir, "r.txt"))


# ── config.py ──────────────────────────────────────────────────────────

class TestConfigLogic:
    @pytest.mark.parametrize("v,expected", [(True, "true"), (False, "false"), (0.7, "0.7"),
                                            (5, "5"), ("F13", "F13")])
    def test_value_to_cli(self, v, expected):
        assert config_mod.value_to_cli(v) == expected

    def test_value_to_cli_none(self):
        with pytest.raises(ValueError):
            config_mod.value_to_cli(None)

    def _fake_backend(self, monkeypatch, store):
        """In-memory stand-in for `voxtype config get/set/unset` keyed by file path."""
        def run_json(args, config_path=None, global_flags=None, timeout=0):
            if args[:2] == ["config", "schema"]:
                return {"config_path": "/default/config.toml", "keys": [], "replacements": {}}
            key = args[2]
            val = store.get(config_path, {}).get(key)
            return {"key": key, "value": val if val is not None else "DEFAULT", "file_value": val}

        def run(args, config_path=None, global_flags=None, check=True, timeout=0, input_text=None):
            d = store.setdefault(config_path, {})
            if args[1] == "set":
                d[args[2]] = args[3]
            elif args[1] == "unset":
                d.pop(args[2], None)
            return subprocess.CompletedProcess(args, 0, "Set ...\nRestart voxtype to apply: x\n", "")

        monkeypatch.setattr(backend, "run_json", run_json)
        monkeypatch.setattr(backend, "run", run)

    def test_set_records_old_and_new(self, monkeypatch):
        store = {"/c.toml": {"hotkey.key": "SCROLLLOCK"}}
        self._fake_backend(monkeypatch, store)
        e = config_mod.set_key("hotkey.key", "F13", "/c.toml")
        assert e["old"] == "SCROLLLOCK" and e["new"] == "F13" and e["restart_required"]
        assert store["/c.toml"]["hotkey.key"] == "F13"

    def test_dry_run_uses_scratch(self, monkeypatch, tmp_dir):
        cfg = os.path.join(tmp_dir, "c.toml")
        with open(cfg, "w") as f:
            f.write("# original\n")
        store = {}
        self._fake_backend(monkeypatch, store)
        e = config_mod.set_key("hotkey.key", "F13", cfg, dry_run=True)
        assert e["dry_run"] and e["new"] == "F13"
        assert cfg not in store or "hotkey.key" not in store[cfg]
        assert open(cfg).read() == "# original\n"
        scratch = [p for p in store if p != cfg]
        assert scratch and not os.path.exists(scratch[0])  # scratch cleaned up

    def test_undo_absent_key_unsets_and_redo_resets(self, monkeypatch):
        store = {"/c.toml": {}}
        self._fake_backend(monkeypatch, store)
        e = config_mod.set_key("text.spoken_punctuation", "true", "/c.toml")
        config_mod.undo_entry(e)
        assert "text.spoken_punctuation" not in store["/c.toml"]
        config_mod.redo_entry(e)
        assert store["/c.toml"]["text.spoken_punctuation"] == "true"

    def test_resolved_path_default(self, monkeypatch):
        self._fake_backend(monkeypatch, {})
        assert config_mod.resolved_path(None) == "/default/config.toml"
        assert config_mod.resolved_path("rel.toml") == os.path.abspath("rel.toml")


# ── daemon.py ──────────────────────────────────────────────────────────

class TestRecordArgs:
    def test_plain(self):
        assert daemon_mod.record_args("start") == ["record", "start"]

    @pytest.mark.parametrize("mode", ["type", "clipboard", "paste"])
    def test_modes(self, mode):
        assert daemon_mod.record_args("start", output_mode=mode) == ["record", "start", f"--{mode}"]

    def test_file(self):
        assert daemon_mod.record_args("toggle", output_mode="file") == ["record", "toggle", "--file"]
        assert daemon_mod.record_args("start", file_path="/t/o.txt") == ["record", "start", "--file=/t/o.txt"]

    def test_full_options(self):
        a = daemon_mod.record_args("start", model="tiny", profile="slack", auto_submit=False, no_osd=True)
        assert a == ["record", "start", "--model", "tiny", "--profile", "slack", "--no-auto-submit", "--no-osd"]
        assert "--auto-submit" in daemon_mod.record_args("start", auto_submit=True)

    def test_stop_rejects_options(self):
        assert daemon_mod.record_args("stop") == ["record", "stop"]
        with pytest.raises(ValueError):
            daemon_mod.record_args("cancel", model="tiny")

    def test_bad_action_and_mode(self):
        with pytest.raises(ValueError):
            daemon_mod.record_args("explode")
        with pytest.raises(ValueError):
            daemon_mod.record_args("start", output_mode="fax")


# ── meeting.py ─────────────────────────────────────────────────────────

class TestMeetingLogic:
    def test_build_transcript_timeline(self):
        res = [{"text": "a", "duration_secs": 1.03}, {"text": "b", "duration_secs": 4.75},
               {"text": "c", "duration_secs": 0.5}]
        t = meeting_mod.build_transcript(res, speakers=[0, 1], gap_ms=500)
        segs = t["segments"]
        assert t["total_chunks"] == 3
        assert [(s["start_ms"], s["end_ms"]) for s in segs] == [(0, 1030), (1530, 6280), (6780, 7280)]
        assert [s["speaker_id"] for s in segs] == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_00"]

    def test_build_transcript_no_speakers(self):
        t = meeting_mod.build_transcript([{"text": "a", "duration_secs": 1}])
        assert "speaker_id" not in t["segments"][0]

    def test_storage_dir_name(self):
        from datetime import datetime
        d = datetime(2026, 10, 25)
        assert meeting_mod._storage_dir_name("Standup Sync!", d, "abc-def") == "2026-10-25-standup-sync_"
        assert meeting_mod._storage_dir_name(None, d, "d85f9781-9fea") == "2026-10-25-d85f9781"

    def _seed_db(self, storage):
        conn = meeting_mod._connect(storage, create=True)
        with conn:
            for i, mid in enumerate(["aaaa1111-0000", "aaaa2222-0000", "bbbb3333-0000"]):
                conn.execute("INSERT INTO meetings (id, title, started_at, status) VALUES (?,?,?,?)",
                             (mid, f"m{i}", 1000 + i, "completed" if i < 2 else "active"))
            conn.execute("INSERT INTO speaker_labels (meeting_id, speaker_num, label) VALUES (?,?,?)",
                         ("aaaa1111-0000", 1, "Alice"))
        conn.close()

    def test_list_and_resolve(self, monkeypatch, tmp_dir):
        self._seed_db(tmp_dir)
        monkeypatch.setattr(meeting_mod, "storage_dir", lambda cfg=None: tmp_dir)
        data = meeting_mod.list_meetings()
        assert data["count"] == 3 and data["meetings"][0]["id"] == "bbbb3333-0000"
        assert data["meetings"][2]["speaker_labels"] == {"SPEAKER_01": "Alice"}
        assert meeting_mod.list_meetings(status="active")["count"] == 1
        assert meeting_mod.resolve_id("latest") == "bbbb3333-0000"
        assert meeting_mod.resolve_id("aaaa2") == "aaaa2222-0000"
        with pytest.raises(ValueError):
            meeting_mod.resolve_id("aaaa")  # ambiguous
        with pytest.raises(ValueError):
            meeting_mod.resolve_id("zzzz")

    def test_list_without_db(self, monkeypatch, tmp_dir):
        monkeypatch.setattr(meeting_mod, "storage_dir", lambda cfg=None: os.path.join(tmp_dir, "none"))
        assert meeting_mod.list_meetings()["count"] == 0
        with pytest.raises(ValueError):
            meeting_mod.resolve_id("latest")

    def test_schema_matches_voxtype_columns(self, tmp_dir):
        conn = meeting_mod._connect(tmp_dir, create=True)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(meetings)")]
        conn.close()
        assert cols == ["id", "title", "started_at", "ended_at", "duration_secs", "status", "chunk_count",
                        "storage_path", "audio_retained", "model", "synced_at", "created_at"]


# ── utils/audio.py ─────────────────────────────────────────────────────

class TestAudio:
    def test_tone_probe_and_rms(self, tmp_dir):
        p = audio_mod.write_tone(os.path.join(tmp_dir, "t.wav"), secs=0.5, amplitude=0.5)
        info = audio_mod.probe_wav(p)
        assert info["sample_rate"] == 16000 and info["channels"] == 1 and info["duration_secs"] == 0.5
        assert audio_mod.is_voxtype_native(info)
        # sine RMS = A/sqrt(2) → 0.5/1.414 ≈ -9.03 dBFS
        assert abs(audio_mod.rms_dbfs(p) - (-9.03)) < 0.1

    def test_silence_rms(self, tmp_dir):
        p = audio_mod.write_silence(os.path.join(tmp_dir, "s.wav"), 0.2)
        assert audio_mod.rms_dbfs(p) == float("-inf")

    def test_non_wav(self, tmp_dir):
        p = os.path.join(tmp_dir, "x.mp3")
        with open(p, "wb") as f:
            f.write(b"ID3\x03\x00garbage")
        with pytest.raises(ValueError):
            audio_mod.probe_wav(p)
        assert audio_mod.needs_conversion(p)

    def test_missing(self, tmp_dir):
        with pytest.raises(FileNotFoundError):
            audio_mod.probe_wav(os.path.join(tmp_dir, "none.wav"))


# ── utils/voxtype_backend.py ───────────────────────────────────────────

class TestBackendHelpers:
    def test_error_message_strips_prefix(self):
        p = subprocess.CompletedProcess([], 2, "", "error: unknown config key 'x'.\n  Run `voxtype config schema`\n")
        assert backend._error_message(p).startswith("unknown config key 'x'.")

    def test_error_message_skips_log_noise(self):
        p = subprocess.CompletedProcess([], 1, "", "whisper_model_load: foo\nggml_x: bar\nModel file missing\n")
        assert backend._error_message(p) == "Model file missing"

    def test_bad_voxtype_bin(self, monkeypatch, tmp_dir):
        monkeypatch.setenv("VOXTYPE_BIN", os.path.join(tmp_dir, "nope"))
        with pytest.raises(RuntimeError, match="VOXTYPE_BIN"):
            backend.find_voxtype()


# ── CLI wiring that needs no backend ───────────────────────────────────

class TestCLINoBackend:
    def _invoke(self, args):
        from click.testing import CliRunner
        from cli_anything.voxtype import voxtype_cli
        voxtype_cli._session = None
        return CliRunner().invoke(voxtype_cli.cli, args)

    def test_help(self):
        r = self._invoke(["--help"])
        assert r.exit_code == 0
        for group in ("config", "transcribe", "meeting", "daemon", "info", "setup", "session", "project"):
            assert group in r.output

    def test_project_new_and_override(self, tmp_dir):
        ws = os.path.join(tmp_dir, "ws.json")
        r = self._invoke(["--json", "project", "new", "-o", ws, "--config", os.path.join(tmp_dir, "c.toml")])
        assert r.exit_code == 0, r.output
        assert json.loads(r.output)["config_path"].endswith("c.toml")
        r = self._invoke(["--project", ws, "--json", "project", "override", "language", "de"])
        assert r.exit_code == 0, r.output
        assert json.load(open(ws))["overrides"] == {"language": "de"}

    def test_dry_run_project_override_not_saved(self, tmp_dir):
        ws = os.path.join(tmp_dir, "ws.json")
        self._invoke(["project", "new", "-o", ws])
        r = self._invoke(["--project", ws, "--dry-run", "project", "override", "model", "tiny"])
        assert r.exit_code == 0
        assert json.load(open(ws))["overrides"] == {}

    def test_missing_workspace_errors(self, tmp_dir):
        r = self._invoke(["--json", "--project", os.path.join(tmp_dir, "none.json"), "session", "history"])
        assert r.exit_code == 1
        assert "Workspace not found" in json.loads(r.output)["error"]

    def test_undo_without_history(self, tmp_dir):
        ws = os.path.join(tmp_dir, "ws.json")
        self._invoke(["project", "new", "-o", ws])
        r = self._invoke(["--json", "--project", ws, "session", "undo"])
        assert r.exit_code == 1 and "Nothing to undo" in r.output

    def test_meeting_delete_requires_yes(self):
        r = self._invoke(["--json", "meeting", "delete", "abc"])
        assert r.exit_code == 1 and "--yes" in r.output
