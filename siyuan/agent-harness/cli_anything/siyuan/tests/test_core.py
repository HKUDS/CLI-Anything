"""Unit tests for cli-anything-siyuan core modules.

Tests use synthetic data and mocking — no external dependencies.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cli_anything.siyuan.core.client import SiYuanClient, SiYuanConfig, load_config
from cli_anything.siyuan.core.session import SessionManager, SessionState


# ── Client config tests ────────────────────────────────────────────────

class TestClientConfig:
    def test_default_config(self):
        """Default config has correct default values."""
        config = SiYuanConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 6806
        assert config.token == ""
        assert config.base_url == "http://127.0.0.1:6806"

    def test_custom_config(self):
        """Custom config values are used."""
        config = SiYuanConfig(host="localhost", port=6807, token="abc123")
        assert config.host == "localhost"
        assert config.port == 6807
        assert config.token == "abc123"
        assert config.base_url == "http://localhost:6807"

    @patch.dict(os.environ, {"SIYUAN_HOST": "192.168.1.100", "SIYUAN_PORT": "6808", "SIYUAN_TOKEN": "envtoken"}, clear=True)
    @patch("cli_anything.siyuan.core.client.Path.home")
    def test_load_config_from_env(self, mock_home):
        """load_config reads from environment variables."""
        mock_home.return_value = Path(tempfile.mkdtemp())
        config = load_config()
        assert config.host == "192.168.1.100"
        assert config.port == 6808
        assert config.token == "envtoken"

    def test_load_config_from_file(self):
        """load_config reads from JSON config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"host": "10.0.0.1", "port": 6809, "token": "filetoken"}, f)
            fname = f.name
        try:
            config = load_config(fname)
            assert config.host == "10.0.0.1"
            assert config.port == 6809
            assert config.token == "filetoken"
        finally:
            os.unlink(fname)


# ── Client API tests ───────────────────────────────────────────────────

class TestSiYuanClient:
    @pytest.fixture
    def client(self):
        return SiYuanClient(SiYuanConfig(token="test-token"))

    def test_ping_success(self, client):
        """ping returns True when server responds."""
        mock_session = MagicMock()
        mock_session.post.return_value.status_code = 200
        mock_session.post.return_value.json.return_value = {"code": 0, "data": "3.6.5"}
        client._session = mock_session
        assert client.ping() is True

    def test_ping_failure(self, client):
        """ping returns False when server is unreachable."""
        mock_session = MagicMock()
        mock_session.post.side_effect = __import__("requests").ConnectionError("refused")
        client._session = mock_session
        assert client.ping() is False

    def test_list_notebooks(self, client):
        """list_notebooks parses API response correctly."""
        mock_data = {
            "notebooks": [
                {"id": "nb1", "name": "Test Notebook", "icon": "1f4d4", "closed": False},
                {"id": "nb2", "name": "Daily Notes", "icon": "1f4cb", "closed": True},
            ]
        }
        mock_session = MagicMock()
        mock_session.post.return_value.status_code = 200
        mock_session.post.return_value.json.return_value = {"code": 0, "data": mock_data}
        client._session = mock_session

        notebooks = client.list_notebooks()
        assert len(notebooks) == 2
        assert notebooks[0]["name"] == "Test Notebook"
        assert notebooks[1]["id"] == "nb2"

    def test_create_doc_with_md(self, client):
        """create_doc_with_md returns the doc ID."""
        mock_session = MagicMock()
        mock_session.post.return_value.status_code = 200
        mock_session.post.return_value.json.return_value = {"code": 0, "data": "doc123"}
        client._session = mock_session

        doc_id = client.create_doc_with_md("nb1", "/test/path", "# Hello")
        assert doc_id == "doc123"
        # Verify correct API call (requests uses json= kwarg, not data=)
        call_kwargs = mock_session.post.call_args[1]
        body = call_kwargs["json"]
        assert body["notebook"] == "nb1"
        assert body["path"] == "/test/path"
        assert body["markdown"] == "# Hello"

    def test_query_sql(self, client):
        """query_sql returns list of rows."""
        mock_session = MagicMock()
        mock_session.post.return_value.status_code = 200
        mock_session.post.return_value.json.return_value = {
            "code": 0, "data": [{"id": "b1", "content": "hello"}, {"id": "b2", "content": "world"}],
        }
        client._session = mock_session

        results = client.query_sql("SELECT * FROM blocks")
        assert len(results) == 2
        assert results[0]["content"] == "hello"


# ── Session tests ──────────────────────────────────────────────────────

class TestSessionManager:
    @pytest.fixture
    def mgr(self):
        tmp_dir = tempfile.mkdtemp()
        return SessionManager(state_dir=tmp_dir)

    def test_default_state(self, mgr):
        """Fresh session has correct defaults."""
        assert mgr.state.connected is False
        assert mgr.state.current_notebook_id == ""
        assert mgr.state.current_notebook_name == ""
        assert mgr.state.current_doc_id == ""

    def test_save_load_roundtrip(self, mgr):
        """Save then load preserves all state."""
        mgr.update(current_notebook_id="nb1", current_notebook_name="Test", connected=True)
        mgr.save()

        mgr2 = SessionManager(state_dir=str(mgr.state_dir))
        mgr2.load()
        assert mgr2.state.current_notebook_id == "nb1"
        assert mgr2.state.current_notebook_name == "Test"
        assert mgr2.state.connected is True

    def test_partial_update(self, mgr):
        """Update only changes specified fields."""
        mgr.update(current_notebook_id="nb1")
        assert mgr.state.current_notebook_id == "nb1"
        assert mgr.state.connected is False  # unchanged


class TestFindReplace:
    """Tests for find_replace using SiYuan API k/r/ids payload."""

    @pytest.fixture
    def client(self):
        return SiYuanClient(SiYuanConfig(token="test-token"))

    def test_find_replace_uses_k_r_ids_payload(self, client):
        """find_replace sends k/r/ids payload keys."""
        mock_session = MagicMock()
        mock_session.post.return_value.status_code = 200
        mock_session.post.return_value.json.return_value = {"code": 0, "data": {"count": 3}}
        client._session = mock_session
        client.find_replace("old", "new", ["id1", "id2"])
        call_kwargs = mock_session.post.call_args[1]
        body = call_kwargs["json"]
        assert "k" in body
        assert "r" in body
        assert "ids" in body
        assert body["k"] == "old"
        assert body["r"] == "new"
        assert body["ids"] == ["id1", "id2"]

class TestUncappedListings:
    """Tests for list_docs_by_path with maxListCount."""

    @pytest.fixture
    def client(self):
        return SiYuanClient(SiYuanConfig(token="test-token"))

    def test_list_docs_by_path_sends_max_list_count(self, client):
        """list_docs_by_path sends maxListCount: 0 for uncapped listings."""
        mock_session = MagicMock()
        mock_session.post.return_value.status_code = 200
        mock_session.post.return_value.json.return_value = {"code": 0, "data": {"files": [{"id": "doc1", "name": "test"}]}}
        client._session = mock_session
        client.list_docs_by_path("nb1", "/")
        call_kwargs = mock_session.post.call_args[1]
        body = call_kwargs["json"]
        assert "maxListCount" in body
        assert body["maxListCount"] == 0
