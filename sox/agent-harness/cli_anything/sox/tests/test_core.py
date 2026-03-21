"""Tests for Sox core module."""

import os
import sys
import pytest

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from cli_anything.sox.core.session import Session


class TestSession:
    def test_init(self):
        s = Session()
        assert not s.has_project()
        assert s.status()["has_project"] is False

    def test_set_project(self):
        s = Session()
        proj = {"name": "test", "metadata": {"created": "2026-01-01"}}
        s.set_project(proj, "/tmp/test.json")
        assert s.has_project()
        assert s.get_project()["name"] == "test"
        assert s.project_path == "/tmp/test.json"

    def test_snapshot_undo_redo(self):
        s = Session()
        s.set_project({"name": "v1", "metadata": {"created": "2026-01-01"}})
        s.snapshot("change to v2")
        s.project["name"] = "v2"
        assert s.get_project()["name"] == "v2"
        desc = s.undo()
        assert s.get_project()["name"] == "v1"
        desc = s.redo()
        assert s.get_project()["name"] == "v2"

    def test_undo_empty_raises(self):
        s = Session()
        s.set_project({"name": "test", "metadata": {}})
        with pytest.raises(RuntimeError):
            s.undo()

    def test_redo_empty_raises(self):
        s = Session()
        s.set_project({"name": "test", "metadata": {}})
        with pytest.raises(RuntimeError):
            s.redo()

    def test_status(self):
        s = Session()
        st = s.status()
        assert st["has_project"] is False
        assert st["undo_count"] == 0
        assert st["redo_count"] == 0

    def test_list_history_empty(self):
        s = Session()
        s.set_project({"name": "test", "metadata": {}})
        assert s.list_history() == []

    def test_list_history(self):
        s = Session()
        s.set_project({"name": "v1", "metadata": {}})
        s.snapshot("first")
        s.project["name"] = "v2"
        s.snapshot("second")
        hist = s.list_history()
        assert len(hist) == 2

    def test_max_undo(self):
        s = Session()
        s.MAX_UNDO = 3
        s.set_project({"name": "v0", "metadata": {}})
        for i in range(5):
            s.snapshot(f"snap {i}")
            s.project["name"] = f"v{i + 1}"
        assert len(s._undo_stack) == 3

    def test_save_session_no_project(self):
        s = Session()
        with pytest.raises(RuntimeError):
            s.save_session()

    def test_save_session_no_path(self):
        s = Session()
        s.set_project({"name": "test", "metadata": {}})
        with pytest.raises(ValueError):
            s.save_session()


class TestEffectsModule:
    def test_import(self):
        from cli_anything.sox.core import effects

        assert hasattr(effects, "info")
        assert hasattr(effects, "convert")
        assert hasattr(effects, "trim")
        assert hasattr(effects, "concat")
        assert hasattr(effects, "mix")
        assert hasattr(effects, "speed")
        assert hasattr(effects, "pitch")
        assert hasattr(effects, "tempo")
        assert hasattr(effects, "volume")
        assert hasattr(effects, "normalize")
        assert hasattr(effects, "reverse")
        assert hasattr(effects, "fade")
        assert hasattr(effects, "silence")
        assert hasattr(effects, "stat")
        assert hasattr(effects, "spectrogram")
        assert hasattr(effects, "synth")
        assert hasattr(effects, "effects_list")
