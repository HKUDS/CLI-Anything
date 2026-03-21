"""Unit tests for Darktable CLI core modules."""

import json, os, sys, tempfile, pytest

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from cli_anything.darktable.core.session import Session
from cli_anything.darktable.core.process import list_styles, get_file_info
from cli_anything.darktable.core.export import (
    list_presets,
    get_preset_info,
    EXPORT_PRESETS,
)


class TestSession:
    def test_create_session(self):
        sess = Session()
        assert not sess.has_project()

    def test_set_project(self):
        sess = Session()
        proj = {"name": "test", "metadata": {"created": "2024-01-01"}}
        sess.set_project(proj)
        assert sess.has_project()

    def test_get_project_no_project(self):
        sess = Session()
        with pytest.raises(RuntimeError, match="No project loaded"):
            sess.get_project()

    def test_undo_redo(self):
        sess = Session()
        proj = {"name": "original", "metadata": {}}
        sess.set_project(proj)
        sess.snapshot("change")
        proj["name"] = "modified"
        sess.undo()
        assert sess.get_project()["name"] == "original"
        sess.redo()
        assert sess.get_project()["name"] == "modified"

    def test_undo_empty(self):
        sess = Session()
        sess.set_project({"name": "t", "metadata": {}})
        with pytest.raises(RuntimeError, match="Nothing to undo"):
            sess.undo()

    def test_status(self):
        sess = Session()
        proj = {"name": "test", "metadata": {}}
        sess.set_project(proj, "/tmp/test.json")
        s = sess.status()
        assert s["has_project"] is True
        assert s["project_path"] == "/tmp/test.json"

    def test_save_session(self):
        sess = Session()
        proj = {"name": "save_test", "metadata": {"created": "2024-01-01"}}
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            sess.set_project(proj, path)
            saved = sess.save_session()
            assert os.path.exists(saved)
            with open(saved) as f:
                loaded = json.load(f)
            assert loaded["name"] == "save_test"
        finally:
            os.unlink(path)

    def test_list_history(self):
        sess = Session()
        proj = {"name": "t", "metadata": {}}
        sess.set_project(proj)
        sess.snapshot("a1")
        sess.snapshot("a2")
        assert len(sess.list_history()) == 2


class TestProcess:
    def test_list_styles(self):
        result = list_styles()
        assert isinstance(result, list)

    def test_get_file_info_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            get_file_info("/nonexistent/file.cr2")


class TestExport:
    def test_list_presets(self):
        presets = list_presets()
        assert len(presets) > 0
        names = [p["name"] for p in presets]
        assert "jpeg-high" in names

    def test_get_preset_info(self):
        info = get_preset_info("jpeg-high")
        assert info["quality"] == 95

    def test_get_preset_info_unknown(self):
        with pytest.raises(ValueError):
            get_preset_info("nonexistent")

    def test_all_presets_valid(self):
        for name, p in EXPORT_PRESETS.items():
            assert "format" in p
            assert "ext" in p
