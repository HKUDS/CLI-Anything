"""Unit tests for cli-anything-musescore core modules.

These tests use synthetic data and do NOT require mscore to be installed.
They test key name resolution, session management, XML parsing, etc.
"""

import json
import os
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

# ── Session Tests ─────────────────────────────────────────────────────

from cli_anything.musescore.core.session import Session


class TestSession:
    def test_create_session(self):
        s = Session()
        assert not s.has_project()
        assert s.project_data is None

    def test_set_project(self):
        s = Session()
        s.set_project({"name": "test"}, "/tmp/test.mscz")
        assert s.has_project()
        assert s.project_data["name"] == "test"
        assert s.project_path == "/tmp/test.mscz"

    def test_get_project_raises_without_open(self):
        s = Session()
        with pytest.raises(RuntimeError, match="No project"):
            s.get_project()

    def test_undo_redo(self):
        s = Session()
        s.set_project({"name": "v1"})
        s.snapshot("edit 1")
        s.project_data["name"] = "v2"
        s.snapshot("edit 2")
        s.project_data["name"] = "v3"

        # Undo edit 2
        desc = s.undo()
        assert desc == "edit 2"
        assert s.project_data["name"] == "v2"

        # Undo edit 1
        desc = s.undo()
        assert desc == "edit 1"
        assert s.project_data["name"] == "v1"

        # Redo edit 1
        desc = s.redo()
        assert desc == "edit 1"
        assert s.project_data["name"] == "v2"

    def test_undo_empty_raises(self):
        s = Session()
        s.set_project({"name": "test"})
        with pytest.raises(RuntimeError, match="Nothing to undo"):
            s.undo()

    def test_redo_empty_raises(self):
        s = Session()
        s.set_project({"name": "test"})
        with pytest.raises(RuntimeError, match="Nothing to redo"):
            s.redo()

    def test_snapshot_clears_redo(self):
        s = Session()
        s.set_project({"name": "v1"})
        s.snapshot("edit 1")
        s.project_data["name"] = "v2"
        s.undo()
        # New edit should clear redo stack
        s.snapshot("edit 2")
        assert len(s.redo_stack) == 0

    def test_history(self):
        s = Session()
        s.set_project({"name": "test"})
        s.snapshot("action 1")
        s.snapshot("action 2")
        s.snapshot("action 3")
        assert s.list_history() == ["action 1", "action 2", "action 3"]

    def test_status(self):
        s = Session()
        s.set_project({"name": "test"}, "/tmp/test.mscz")
        s.snapshot("edit")
        status = s.status()
        assert status["project_path"] == "/tmp/test.mscz"
        assert status["undo_depth"] == 1
        assert status["redo_depth"] == 0

    def test_modified_flag(self):
        s = Session()
        s.set_project({"name": "test"})
        assert not s.is_modified()
        s.snapshot("edit")
        assert s.is_modified()

    def test_save_session(self):
        s = Session()
        s.set_project({"name": "test"}, "/tmp/test.mscz")
        s.snapshot("edit")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.mscz")
            result = s.save_session(path)
            assert os.path.isfile(result)
            with open(result) as f:
                data = json.load(f)
            assert data["history"] == ["edit"]


# ── Key Signature Tests ───────────────────────────────────────────────

from cli_anything.musescore.utils.mscx_xml import (
    key_name_to_int, key_int_to_name, KEY_INT_TO_MAJOR,
)


class TestKeySignature:
    def test_major_keys(self):
        assert key_name_to_int("C") == 0
        assert key_name_to_int("C major") == 0
        assert key_name_to_int("G") == 1
        assert key_name_to_int("Db") == -5
        assert key_name_to_int("Db major") == -5
        assert key_name_to_int("F#") == 6

    def test_minor_keys(self):
        assert key_name_to_int("A minor") == 0
        assert key_name_to_int("Am") == 0
        assert key_name_to_int("D minor") == -1
        assert key_name_to_int("F# minor") == 3

    def test_case_insensitive(self):
        assert key_name_to_int("c major") == 0
        assert key_name_to_int("DB MAJOR") == -5
        assert key_name_to_int("am") == 0

    def test_invalid_key(self):
        with pytest.raises(ValueError, match="Unrecognized key"):
            key_name_to_int("X major")

    def test_int_to_name(self):
        assert key_int_to_name(0) == "C major"
        assert key_int_to_name(-5) == "Db major"
        assert key_int_to_name(0, minor=True) == "A minor"

    def test_all_major_keys_roundtrip(self):
        for i, name in KEY_INT_TO_MAJOR.items():
            assert key_name_to_int(name) == i
            assert key_name_to_int(f"{name} major") == i


# ── Transpose Option Building Tests ───────────────────────────────────

from cli_anything.musescore.core.transpose import (
    semitones_to_interval_index, INTERVAL_ENUM,
)


class TestTranspose:
    def test_semitones_to_interval_unison(self):
        assert semitones_to_interval_index(0) == 0  # Perfect Unison

    def test_semitones_to_interval_minor_second(self):
        assert semitones_to_interval_index(1) == 1  # Minor Second

    def test_semitones_to_interval_octave(self):
        assert semitones_to_interval_index(12) == 12  # Perfect Octave

    def test_semitones_to_interval_fifth(self):
        assert semitones_to_interval_index(7) == 7  # Perfect Fifth

    def test_interval_enum_count(self):
        assert len(INTERVAL_ENUM) == 26


# ── XML Parsing Tests ─────────────────────────────────────────────────

from cli_anything.musescore.utils.mscx_xml import (
    get_key_signature, get_time_signature, get_instruments,
    get_score_title, count_measures, count_notes,
    detect_format, read_mscz, write_mscz,
)


class TestXMLParsing:
    def _make_musicxml(self, fifths=-5, beats="4", beat_type="4",
                       title="Test Score", num_measures=4, num_notes=16):
        """Create a synthetic MusicXML tree for testing."""
        root = ET.Element("score-partwise", version="4.0")
        # Work title
        work = ET.SubElement(root, "work")
        ET.SubElement(work, "work-title").text = title
        # Part list
        part_list = ET.SubElement(root, "part-list")
        sp = ET.SubElement(part_list, "score-part", id="P1")
        ET.SubElement(sp, "part-name").text = "Piano"
        si = ET.SubElement(sp, "score-instrument", id="P1-I1")
        ET.SubElement(si, "instrument-name").text = "Piano"
        # Part with measures
        part = ET.SubElement(root, "part", id="P1")
        for m in range(num_measures):
            measure = ET.SubElement(part, "measure", number=str(m + 1))
            if m == 0:
                attrs = ET.SubElement(measure, "attributes")
                key = ET.SubElement(attrs, "key")
                ET.SubElement(key, "fifths").text = str(fifths)
                time = ET.SubElement(attrs, "time")
                ET.SubElement(time, "beats").text = beats
                ET.SubElement(time, "beat-type").text = beat_type
            for n in range(num_notes // num_measures):
                note = ET.SubElement(measure, "note")
                pitch = ET.SubElement(note, "pitch")
                ET.SubElement(pitch, "step").text = "C"
                ET.SubElement(pitch, "octave").text = "4"
        return ET.ElementTree(root)

    def test_get_key_signature(self):
        tree = self._make_musicxml(fifths=-5)
        assert get_key_signature(tree) == -5

    def test_get_time_signature(self):
        tree = self._make_musicxml(beats="3", beat_type="4")
        assert get_time_signature(tree) == "3/4"

    def test_get_instruments(self):
        tree = self._make_musicxml()
        instruments = get_instruments(tree)
        assert len(instruments) == 1
        assert instruments[0]["name"] == "Piano"

    def test_get_score_title(self):
        tree = self._make_musicxml(title="My Score")
        assert get_score_title(tree) == "My Score"

    def test_count_measures(self):
        tree = self._make_musicxml(num_measures=8)
        assert count_measures(tree) == 8

    def test_count_notes(self):
        tree = self._make_musicxml(num_measures=4, num_notes=16)
        assert count_notes(tree) == 16

    def test_detect_format(self):
        assert detect_format("score.mscz") == "mscz"
        assert detect_format("score.mxl") == "mxl"
        assert detect_format("score.musicxml") == "musicxml"
        assert detect_format("score.mid") == "mid"
        assert detect_format("score.txt") == "unknown"

    def test_mscz_roundtrip(self):
        """Test writing and reading a .mscz file."""
        tree = self._make_musicxml()
        data = {
            "mscx": tree,
            "mscx_filename": "score.mscx",
            "style": "<Style></Style>",
            "audio_settings": '{"master_gain": 1.0}',
            "view_settings": '{"zoom": 100}',
            "other_files": {},
        }
        with tempfile.NamedTemporaryFile(suffix=".mscz", delete=False) as f:
            tmp_path = f.name

        try:
            write_mscz(tmp_path, data)
            assert os.path.isfile(tmp_path)

            # Verify it's a valid ZIP
            assert zipfile.is_zipfile(tmp_path)

            # Read back
            read_data = read_mscz(tmp_path)
            assert read_data["mscx"] is not None
            assert read_data["style"] == "<Style></Style>"
            assert get_key_signature(read_data["mscx"]) == -5
        finally:
            os.unlink(tmp_path)


# ── Export Verification Tests ─────────────────────────────────────────

from cli_anything.musescore.core.export import verify_output, _ext_to_format


class TestExportVerification:
    def test_ext_to_format(self):
        assert _ext_to_format(".pdf") == "pdf"
        assert _ext_to_format(".mid") == "midi"
        assert _ext_to_format(".mp3") == "mp3"
        assert _ext_to_format(".musicxml") == "musicxml"

    def test_verify_nonexistent(self):
        result = verify_output("/nonexistent/file.pdf")
        assert not result["exists"]
        assert not result["valid"]

    def test_verify_pdf(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 test content")
            tmp = f.name
        try:
            result = verify_output(tmp, "pdf")
            assert result["exists"]
            assert result["valid"]
        finally:
            os.unlink(tmp)

    def test_verify_midi(self):
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            f.write(b"MThd\x00\x00\x00\x06")
            tmp = f.name
        try:
            result = verify_output(tmp, "midi")
            assert result["exists"]
            assert result["valid"]
        finally:
            os.unlink(tmp)

    def test_verify_mp3_sync(self):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"\xff\xfb\x90\x00" + b"\x00" * 100)
            tmp = f.name
        try:
            result = verify_output(tmp, "mp3")
            assert result["valid"]
        finally:
            os.unlink(tmp)

    def test_verify_mp3_id3(self):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"ID3" + b"\x00" * 100)
            tmp = f.name
        try:
            result = verify_output(tmp, "mp3")
            assert result["valid"]
        finally:
            os.unlink(tmp)

    def test_verify_png(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
            tmp = f.name
        try:
            result = verify_output(tmp, "png")
            assert result["valid"]
        finally:
            os.unlink(tmp)

    def test_verify_empty_file(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            tmp = f.name
        try:
            result = verify_output(tmp, "pdf")
            assert result["exists"]
            assert not result["valid"]
        finally:
            os.unlink(tmp)


# ── Media Stats Tests (synthetic) ─────────────────────────────────────

class TestMediaStats:
    def test_score_stats_from_mxl(self):
        """Create a synthetic .mxl and test stats extraction."""
        tree = TestXMLParsing()._make_musicxml(
            fifths=0, num_measures=8, num_notes=32, title="Stats Test"
        )
        xml_str = ET.tostring(tree.getroot(), encoding="unicode",
                              xml_declaration=True)

        with tempfile.NamedTemporaryFile(suffix=".mxl", delete=False) as f:
            tmp_path = f.name

        try:
            with zipfile.ZipFile(tmp_path, "w") as zf:
                zf.writestr("score.xml", xml_str)

            from cli_anything.musescore.core.media import score_stats
            result = score_stats(tmp_path)
            assert result["format"] == "mxl"
            assert result["stats"]["measures"] == 8
            assert result["stats"]["notes"] == 32
            assert result["stats"]["title"] == "Stats Test"
            assert result["stats"]["key_signature"] == 0
            assert result["stats"]["key_name"] == "C major"
        finally:
            os.unlink(tmp_path)
