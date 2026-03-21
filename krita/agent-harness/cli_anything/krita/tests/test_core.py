"""Unit tests for Krita CLI core modules."""

import json, os, sys, tempfile, pytest

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from cli_anything.krita.core.session import Session
from cli_anything.krita.core.canvas import create_canvas, get_file_info, list_layers
from cli_anything.krita.core.export import list_presets, get_preset_info


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


class TestCanvas:
    def test_create_canvas(self, tmp_path):
        out = str(tmp_path / "test.png")
        result = create_canvas(100, 100, out, "#ff0000")
        assert os.path.exists(out)
        assert result["width"] == 100

    def test_get_file_info_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            get_file_info("/nonexistent/file.kra")


class TestExport:
    def test_list_presets(self):
        presets = list_presets()
        assert len(presets) > 0
        names = [p["name"] for p in presets]
        assert "png" in names

    def test_get_preset_info(self):
        info = get_preset_info("png")
        assert info["format"] == "PNG"

    def test_get_preset_info_unknown(self):
        with pytest.raises(ValueError):
            get_preset_info("nonexistent")
