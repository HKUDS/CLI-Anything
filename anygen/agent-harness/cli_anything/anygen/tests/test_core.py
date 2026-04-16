"""Unit tests for AnyGen CLI — mocked HTTP, no API key needed."""

import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cli_anything.anygen.utils.anygen_backend import (
    get_api_key,
    load_config,
    save_config,
    _make_auth_token,
    _require_api_key,
    VALID_OPERATIONS,
)
from cli_anything.anygen.core.session import Session, HistoryEntry
from cli_anything.anygen.core.export import verify_file


# ── TestConfig ────────────────────────────────────────────────────

class TestConfig:
    def test_load_config_missing_file(self, tmp_path):
        with patch("cli_anything.anygen.utils.anygen_backend.CONFIG_FILE", tmp_path / "nope.json"):
            assert load_config() == {}

    def test_save_and_load_config(self, tmp_path):
        cfg_file = tmp_path / "cfg" / "config.json"
        with patch("cli_anything.anygen.utils.anygen_backend.CONFIG_DIR", tmp_path / "cfg"), \
             patch("cli_anything.anygen.utils.anygen_backend.CONFIG_FILE", cfg_file):
            save_config({"api_key": "sk-test123"})
            assert cfg_file.exists()
            result = load_config()
            assert result["api_key"] == "sk-test123"

    def test_api_key_priority_cli_arg(self):
        assert get_api_key("sk-cli") == "sk-cli"

    def test_api_key_priority_env(self, monkeypatch):
        monkeypatch.setenv("ANYGEN_API_KEY", "sk-env")
        assert get_api_key(None) == "sk-env"

    def test_make_auth_token_bare(self):
        assert _make_auth_token("sk-test") == "Bearer sk-test"

    def test_make_auth_token_already_bearer(self):
        assert _make_auth_token("Bearer sk-test") == "Bearer sk-test"

    def test_require_api_key_raises(self):
        with pytest.raises(RuntimeError, match="API key not found"):
            _require_api_key(None)

    def test_require_api_key_returns(self):
        assert _require_api_key("sk-ok") == "sk-ok"


# ── TestCreateTask ────────────────────────────────────────────────

class TestCreateTask:
    def _mock_response(self, status_code=200, json_data=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data or {}
        resp.text = json.dumps(json_data or {})
        return resp

    @patch("cli_anything.anygen.utils.anygen_backend.requests.post")
    def test_create_slide_task(self, mock_post):
        mock_post.return_value = self._mock_response(200, {
            "success": True, "task_id": "task_001", "task_url": "https://anygen.io/task/001"
        })
        from cli_anything.anygen.utils.anygen_backend import create_task
        result = create_task("sk-test", "slide", "Make a presentation",
                             language="en-US", slide_count=10)
        assert result["task_id"] == "task_001"
        body = mock_post.call_args[1]["json"]
        assert body["operation"] == "slide"
        assert body["slide_count"] == 10

    @patch("cli_anything.anygen.utils.anygen_backend.requests.post")
    def test_create_doc_minimal(self, mock_post):
        mock_post.return_value = self._mock_response(200, {
            "success": True, "task_id": "task_002"
        })
        from cli_anything.anygen.utils.anygen_backend import create_task
        result = create_task("sk-test", "doc", "Write a report")
        assert result["task_id"] == "task_002"

    def test_create_invalid_operation(self):
        from cli_anything.anygen.utils.anygen_backend import create_task
        with pytest.raises(ValueError, match="Invalid operation"):
            create_task("sk-test", "invalid_op", "test")

    @patch("cli_anything.anygen.utils.anygen_backend.requests.post")
    def test_create_with_file_tokens(self, mock_post):
        mock_post.return_value = self._mock_response(200, {
            "success": True, "task_id": "task_003"
        })
        from cli_anything.anygen.utils.anygen_backend import create_task
        create_task("sk-test", "slide", "test", file_tokens=["tk_a", "tk_b"])
        body = mock_post.call_args[1]["json"]
        assert body["file_tokens"] == ["tk_a", "tk_b"]

    @patch("cli_anything.anygen.utils.anygen_backend.requests.post")
    def test_create_with_style(self, mock_post):
        mock_post.return_value = self._mock_response(200, {
            "success": True, "task_id": "task_004"
        })
        from cli_anything.anygen.utils.anygen_backend import create_task
        create_task("sk-test", "slide", "test prompt", style="business formal")
        body = mock_post.call_args[1]["json"]
        assert "Style requirement: business formal" in body["prompt"]

    @patch("cli_anything.anygen.utils.anygen_backend.requests.post")
    def test_create_http_error(self, mock_post):
        mock_post.return_value = self._mock_response(500, {})
        from cli_anything.anygen.utils.anygen_backend import create_task
        with pytest.raises(RuntimeError, match="HTTP 500"):
            create_task("sk-test", "slide", "test")

    @patch("cli_anything.anygen.utils.anygen_backend.requests.post")
    def test_create_api_error(self, mock_post):
        mock_post.return_value = self._mock_response(200, {
            "success": False, "error": "quota exceeded"
        })
        from cli_anything.anygen.utils.anygen_backend import create_task
        with pytest.raises(RuntimeError, match="quota exceeded"):
            create_task("sk-test", "slide", "test")


# ── TestQueryTask ─────────────────────────────────────────────────

class TestQueryTask:
    @patch("cli_anything.anygen.utils.anygen_backend.requests.get")
    def test_query_returns_dict(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"status": "running", "progress": 42}
        mock_get.return_value = resp
        from cli_anything.anygen.utils.anygen_backend import query_task
        result = query_task("sk-test", "task_001")
        assert result["status"] == "running"
        assert result["progress"] == 42

    @patch("cli_anything.anygen.utils.anygen_backend.requests.get")
    def test_query_completed_with_output(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "status": "completed", "progress": 100,
            "output": {"file_url": "https://dl.example.com/f.pptx", "file_name": "f.pptx"}
        }
        mock_get.return_value = resp
        from cli_anything.anygen.utils.anygen_backend import query_task
        result = query_task("sk-test", "task_001")
        assert result["output"]["file_name"] == "f.pptx"

    @patch("cli_anything.anygen.utils.anygen_backend.requests.get")
    def test_query_http_error(self, mock_get):
        resp = MagicMock()
        resp.status_code = 404
        resp.text = "Not found"
        mock_get.return_value = resp
        from cli_anything.anygen.utils.anygen_backend import query_task
        with pytest.raises(RuntimeError, match="HTTP 404"):
            query_task("sk-test", "task_bad")


# ── TestPollTask ──────────────────────────────────────────────────

class TestPollTask:
    @patch("cli_anything.anygen.utils.anygen_backend.time.sleep")
    @patch("cli_anything.anygen.utils.anygen_backend.query_task")
    def test_poll_until_completed(self, mock_query, mock_sleep):
        mock_query.side_effect = [
            {"status": "running", "progress": 30},
            {"status": "running", "progress": 70},
            {"status": "completed", "progress": 100, "output": {}},
        ]
        from cli_anything.anygen.utils.anygen_backend import poll_task
        result = poll_task("sk-test", "task_001")
        assert result["status"] == "completed"
        assert mock_sleep.call_count == 2

    @patch("cli_anything.anygen.utils.anygen_backend.time.sleep")
    @patch("cli_anything.anygen.utils.anygen_backend.query_task")
    def test_poll_failed_raises(self, mock_query, mock_sleep):
        mock_query.return_value = {"status": "failed", "error": "server error"}
        from cli_anything.anygen.utils.anygen_backend import poll_task
        with pytest.raises(RuntimeError, match="failed"):
            poll_task("sk-test", "task_001")

    @patch("cli_anything.anygen.utils.anygen_backend.time.time")
    @patch("cli_anything.anygen.utils.anygen_backend.time.sleep")
    @patch("cli_anything.anygen.utils.anygen_backend.query_task")
    def test_poll_timeout(self, mock_query, mock_sleep, mock_time):
        mock_time.side_effect = [0, 0, 9999]
        mock_query.return_value = {"status": "running", "progress": 10}
        from cli_anything.anygen.utils.anygen_backend import poll_task
        with pytest.raises(TimeoutError, match="timeout"):
            poll_task("sk-test", "task_001", max_time=5)

    @patch("cli_anything.anygen.utils.anygen_backend.time.sleep")
    @patch("cli_anything.anygen.utils.anygen_backend.query_task")
    def test_poll_progress_callback(self, mock_query, mock_sleep):
        mock_query.side_effect = [
            {"status": "running", "progress": 50},
            {"status": "completed", "progress": 100, "output": {}},
        ]
        cb = MagicMock()
        from cli_anything.anygen.utils.anygen_backend import poll_task
        poll_task("sk-test", "task_001", on_progress=cb)
        assert cb.call_count == 2
        cb.assert_any_call("running", 50)
        cb.assert_any_call("completed", 100)


# ── TestSession ───────────────────────────────────────────────────

class TestSession:
    def test_record_and_history(self):
        sess = Session()
        sess.record("task create", {"op": "slide"}, {"task_id": "t1"})
        sess.record("task poll", {"id": "t1"})
        h = sess.history()
        assert len(h) == 2
        assert h[0]["command"] == "task create"

    def test_undo(self):
        sess = Session()
        sess.record("cmd1", {})
        sess.record("cmd2", {})
        entry = sess.undo()
        assert entry.command == "cmd2"
        assert sess.history_count == 1

    def test_redo(self):
        sess = Session()
        sess.record("cmd1", {})
        sess.undo()
        entry = sess.redo()
        assert entry.command == "cmd1"
        assert sess.history_count == 1

    def test_undo_clears_redo_on_record(self):
        sess = Session()
        sess.record("cmd1", {})
        sess.undo()
        sess.record("cmd2", {})
        assert not sess.can_redo

    def test_undo_empty(self):
        sess = Session()
        assert sess.undo() is None

    def test_redo_empty(self):
        sess = Session()
        assert sess.redo() is None

    def test_history_limit(self):
        sess = Session()
        for i in range(30):
            sess.record(f"cmd{i}", {})
        assert len(sess.history(limit=5)) == 5

    def test_status(self):
        sess = Session()
        sess.record("cmd1", {})
        st = sess.status()
        assert st["history_count"] == 1
        assert st["can_undo"] is True
        assert st["can_redo"] is False

    def test_save_and_load(self, tmp_path):
        path = str(tmp_path / "session.json")
        sess = Session()
        sess.record("cmd1", {"a": 1}, {"r": "ok"})
        sess.save(path)

        sess2 = Session(session_file=path)
        h = sess2.history()
        assert len(h) == 1
        assert h[0]["command"] == "cmd1"

    def test_load_corrupt_file(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not json")
        sess = Session(session_file=str(path))
        assert sess.history_count == 0


# ── TestExportVerify ──────────────────────────────────────────────

class TestExportVerify:
    def test_verify_missing_file(self):
        r = verify_file("/nonexistent/file.pptx")
        assert not r["valid"]

    def test_verify_empty_file(self, tmp_path):
        f = tmp_path / "empty.pptx"
        f.write_bytes(b"")
        r = verify_file(str(f))
        assert not r["valid"]

    def test_verify_valid_pptx(self, tmp_path):
        f = tmp_path / "test.pptx"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
            zf.writestr("ppt/presentation.xml", "<p/>")
        r = verify_file(str(f))
        assert r["valid"]
        assert r["format"] == "OOXML"

    def test_verify_valid_docx(self, tmp_path):
        f = tmp_path / "test.docx"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
            zf.writestr("word/document.xml", "<w/>")
        r = verify_file(str(f))
        assert r["valid"]

    def test_verify_valid_pdf(self, tmp_path):
        f = tmp_path / "test.pdf"
        f.write_bytes(b"%PDF-1.4 fake pdf content")
        r = verify_file(str(f))
        assert r["valid"]
        assert r["format"] == "PDF"

    def test_verify_valid_png(self, tmp_path):
        f = tmp_path / "test.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        r = verify_file(str(f))
        assert r["valid"]
        assert r["format"] == "PNG"

    def test_verify_valid_svg(self, tmp_path):
        f = tmp_path / "test.svg"
        f.write_text('<svg xmlns="http://www.w3.org/2000/svg"><circle/></svg>')
        r = verify_file(str(f))
        assert r["valid"]

    def test_verify_corrupt_zip(self, tmp_path):
        f = tmp_path / "bad.pptx"
        f.write_bytes(b"PK\x03\x04" + b"\x00" * 50)
        r = verify_file(str(f))
        assert not r["valid"]
