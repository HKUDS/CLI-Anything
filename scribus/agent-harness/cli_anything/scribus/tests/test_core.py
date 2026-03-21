"""Unit tests for Scribus CLI core modules."""

import json, os, sys, tempfile, pytest

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from cli_anything.scribus.core.session import Session
from cli_anything.scribus.core.document import (
    create_document,
    get_file_info,
    list_pages,
    list_layers_sla,
    list_fonts,
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


class TestDocument:
    def test_create_document(self, tmp_path):
        out = str(tmp_path / "test.sla")
        result = create_document(out, width=210, height=297, pages=2)
        assert os.path.exists(out)
        assert result["pages"] == 2

    def test_get_file_info(self, tmp_path):
        out = str(tmp_path / "test.sla")
        create_document(out)
        info = get_file_info(out)
        assert info["page_count"] == 1

    def test_list_pages(self, tmp_path):
        out = str(tmp_path / "test.sla")
        create_document(out, pages=3)
        pages = list_pages(out)
        assert len(pages) == 3

    def test_list_layers(self, tmp_path):
        out = str(tmp_path / "test.sla")
        create_document(out)
        layers = list_layers_sla(out)
        assert len(layers) >= 1

    def test_get_file_info_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            get_file_info("/nonexistent/file.sla")

    def test_list_fonts(self):
        fonts = list_fonts()
        assert isinstance(fonts, list)
