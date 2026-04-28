from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli_anything.calibre.core.session import Session
from cli_anything.calibre.core import library as library_mod
from cli_anything.calibre.core import books as books_mod
from cli_anything.calibre.core import convert as convert_mod


def test_session_initial_state(tmp_path):
    sess = Session(session_path=str(tmp_path / "session.json"))
    status = sess.status()
    assert status["has_library"] is False
    assert status["current_book_id"] is None
    assert status["undo_count"] == 0


def test_session_open_library_and_status(tmp_path):
    sess = Session(session_path=str(tmp_path / "session.json"))
    lib = tmp_path / "Calibre Library"
    lib.mkdir()
    (lib / "metadata.db").write_bytes(b"sqlite")
    sess.open_library(str(lib))
    status = sess.status()
    assert status["has_library"] is True
    assert status["library_path"] == str(lib.resolve())


def test_session_snapshot_undo_redo(tmp_path):
    sess = Session(session_path=str(tmp_path / "session.json"))
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "metadata.db").write_bytes(b"sqlite")
    sess.open_library(str(lib))
    sess.snapshot("Select book")
    sess.select_book(42)
    desc = sess.undo()
    assert desc == "Select book"
    assert sess.current_book_id is None
    redone = sess.redo()
    assert redone == "redo point"


def test_session_save_writes_json(tmp_path):
    session_file = tmp_path / "session.json"
    sess = Session(session_path=str(session_file))
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "metadata.db").write_bytes(b"sqlite")
    sess.open_library(str(lib))
    saved = sess.save()
    assert saved == str(session_file)
    payload = json.loads(session_file.read_text(encoding="utf-8"))
    assert payload["library_path"] == str(lib.resolve())


def test_open_library_validates_metadata_db(tmp_path):
    lib = tmp_path / "My Library"
    lib.mkdir()
    (lib / "metadata.db").write_bytes(b"sqlite")
    info = library_mod.open_library(str(lib))
    assert info["exists"] is True
    assert info["library_path"] == str(lib.resolve())


def test_open_library_rejects_missing_metadata_db(tmp_path):
    lib = tmp_path / "broken"
    lib.mkdir()
    with pytest.raises(FileNotFoundError):
        library_mod.open_library(str(lib))


def test_parse_added_id():
    assert books_mod.parse_added_id("Added book ids: 12, 13") == 12
    assert books_mod.parse_added_id("Added book with id: 9") == 9
    assert books_mod.parse_added_id("nothing useful") is None


def test_convert_presets_and_invalid_preset():
    presets = convert_mod.list_presets()
    assert "kindle" in presets
    with pytest.raises(ValueError):
        convert_mod.convert_book("in.epub", "out.mobi", preset="nope")
