"""Unit tests for the ChromaDB CLI-Anything harness.

All HTTP calls are mocked -- no external dependencies required.
Tests cover: output formatting, CLI argument parsing, URL construction,
request building, and error handling.
"""

import json
import os
import sys

import pytest
from unittest.mock import patch, MagicMock

# Ensure the package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from cli_anything.chromadb.utils.chromadb_backend import ChromaDBBackend


# ============================================================================
# ChromaDBBackend -- URL construction and request building
# ============================================================================

class TestBackendURLConstruction:
    """Verify that the backend builds correct API URLs."""

    def test_default_base_url(self):
        b = ChromaDBBackend()
        assert b.base_url == "http://localhost:8000"

    def test_custom_base_url(self):
        b = ChromaDBBackend(base_url="http://myhost:9090")
        assert b.base_url == "http://myhost:9090"

    def test_trailing_slash_stripped(self):
        b = ChromaDBBackend(base_url="http://localhost:8000/")
        assert b.base_url == "http://localhost:8000"

    def test_tenant_db_prefix(self):
        b = ChromaDBBackend()
        expected = "http://localhost:8000/api/v2/tenants/default_tenant/databases/default_database"
        assert b._tenant_db_prefix == expected

    def test_custom_tenant_and_database(self):
        b = ChromaDBBackend(tenant="my_tenant", database="my_db")
        expected = "http://localhost:8000/api/v2/tenants/my_tenant/databases/my_db"
        assert b._tenant_db_prefix == expected

    def test_session_headers(self):
        b = ChromaDBBackend()
        assert b._session.headers["Content-Type"] == "application/json"


# ============================================================================
# ChromaDBBackend -- heartbeat and version (mocked)
# ============================================================================

class TestBackendServerCommands:
    """Test server heartbeat and version with mocked HTTP."""

    @patch("cli_anything.chromadb.utils.chromadb_backend.requests.Session")
    def test_heartbeat_url(self, MockSession):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"nanosecond_heartbeat": 1234567890}
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response
        MockSession.return_value = mock_session

        b = ChromaDBBackend()
        result = b.heartbeat()

        mock_session.get.assert_called_with("http://localhost:8000/api/v2/heartbeat")
        assert result == {"nanosecond_heartbeat": 1234567890}

    @patch("cli_anything.chromadb.utils.chromadb_backend.requests.Session")
    def test_version_url(self, MockSession):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = "0.6.0"
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response
        MockSession.return_value = mock_session

        b = ChromaDBBackend()
        result = b.version()

        mock_session.get.assert_called_with("http://localhost:8000/api/v2/version")
        assert result == "0.6.0"


# ============================================================================
# ChromaDBBackend -- collection operations (mocked)
# ============================================================================

class TestBackendCollections:
    """Test collection CRUD with mocked HTTP."""

    def _make_backend(self):
        """Create a backend with a mocked session."""
        b = ChromaDBBackend()
        b._session = MagicMock()
        return b

    def _mock_response(self, json_data, status_code=200):
        resp = MagicMock()
        resp.json.return_value = json_data
        resp.status_code = status_code
        resp.raise_for_status.return_value = None
        return resp

    def test_list_collections_url(self):
        b = self._make_backend()
        b._session.get.return_value = self._mock_response([])
        b.list_collections()
        called_url = b._session.get.call_args[0][0]
        assert "/collections" in called_url
        assert "/tenants/default_tenant/databases/default_database" in called_url

    def test_list_collections_returns_list(self):
        b = self._make_backend()
        collections = [{"name": "test", "id": "abc-123"}]
        b._session.get.return_value = self._mock_response(collections)
        result = b.list_collections()
        assert isinstance(result, list)
        assert result[0]["name"] == "test"

    def test_create_collection_sends_name(self):
        b = self._make_backend()
        b._session.post.return_value = self._mock_response({"name": "new_col", "id": "xyz"})
        result = b.create_collection("new_col")
        call_kwargs = b._session.post.call_args
        assert call_kwargs[1]["json"]["name"] == "new_col"
        assert result["name"] == "new_col"

    def test_create_collection_with_metadata(self):
        b = self._make_backend()
        b._session.post.return_value = self._mock_response({"name": "c", "id": "x"})
        b.create_collection("c", metadata={"key": "val"})
        body = b._session.post.call_args[1]["json"]
        assert body["metadata"] == {"key": "val"}

    def test_get_collection_url(self):
        b = self._make_backend()
        b._session.get.return_value = self._mock_response({"name": "hub_knowledge", "id": "abc"})
        b.get_collection("hub_knowledge")
        called_url = b._session.get.call_args[0][0]
        assert called_url.endswith("/collections/hub_knowledge")

    def test_delete_collection_returns_true(self):
        b = self._make_backend()
        b._session.delete.return_value = self._mock_response(None)
        result = b.delete_collection("old_col")
        assert result is True


# ============================================================================
# ChromaDBBackend -- document operations (mocked)
# ============================================================================

class TestBackendDocuments:
    """Test document operations with mocked HTTP."""

    def _make_backend(self):
        b = ChromaDBBackend()
        b._session = MagicMock()
        return b

    def _mock_response(self, json_data, text=""):
        resp = MagicMock()
        resp.json.return_value = json_data
        resp.text = text or json.dumps(json_data) if json_data else ""
        resp.raise_for_status.return_value = None
        return resp

    def test_add_documents_body(self):
        b = self._make_backend()
        b._session.post.return_value = self._mock_response(None, text="")
        b.add_documents("col-id", ids=["d1"], documents=["hello world"])
        body = b._session.post.call_args[1]["json"]
        assert body["ids"] == ["d1"]
        assert body["documents"] == ["hello world"]
        assert "metadatas" not in body

    def test_add_documents_with_metadatas(self):
        b = self._make_backend()
        b._session.post.return_value = self._mock_response(None, text="")
        b.add_documents("col-id", ids=["d1"], documents=["text"],
                        metadatas=[{"source": "test"}])
        body = b._session.post.call_args[1]["json"]
        assert body["metadatas"] == [{"source": "test"}]

    def test_get_documents_url(self):
        b = self._make_backend()
        b._session.post.return_value = self._mock_response({"ids": [], "documents": []})
        b.get_documents("col-id-123")
        called_url = b._session.post.call_args[0][0]
        assert "col-id-123/get" in called_url

    def test_get_documents_with_limit_offset(self):
        b = self._make_backend()
        b._session.post.return_value = self._mock_response({"ids": [], "documents": []})
        b.get_documents("col-id", limit=10, offset=5)
        body = b._session.post.call_args[1]["json"]
        assert body["limit"] == 10
        assert body["offset"] == 5

    def test_delete_documents_body(self):
        b = self._make_backend()
        b._session.post.return_value = self._mock_response(None, text="")
        b.delete_documents("col-id", ids=["d1", "d2"])
        body = b._session.post.call_args[1]["json"]
        assert body["ids"] == ["d1", "d2"]

    def test_count_documents_url(self):
        b = self._make_backend()
        b._session.post.return_value = self._mock_response(42)
        result = b.count_documents("col-id")
        called_url = b._session.post.call_args[0][0]
        assert "col-id/count" in called_url
        assert result == 42


# ============================================================================
# ChromaDBBackend -- query (mocked)
# ============================================================================

class TestBackendQuery:
    """Test semantic search query with mocked HTTP."""

    def _make_backend(self):
        b = ChromaDBBackend()
        b._session = MagicMock()
        return b

    def _mock_response(self, json_data):
        resp = MagicMock()
        resp.json.return_value = json_data
        resp.raise_for_status.return_value = None
        return resp

    def test_query_body(self):
        b = self._make_backend()
        b._session.post.return_value = self._mock_response({"ids": [[]], "documents": [[]]})
        b.query("col-id", query_texts=["test query"], n_results=3)
        body = b._session.post.call_args[1]["json"]
        assert body["query_texts"] == ["test query"]
        assert body["n_results"] == 3

    def test_query_default_n_results(self):
        b = self._make_backend()
        b._session.post.return_value = self._mock_response({"ids": [[]]})
        b.query("col-id", query_texts=["hello"])
        body = b._session.post.call_args[1]["json"]
        assert body["n_results"] == 5

    def test_query_url(self):
        b = self._make_backend()
        b._session.post.return_value = self._mock_response({"ids": [[]]})
        b.query("col-id-abc", query_texts=["x"])
        called_url = b._session.post.call_args[0][0]
        assert "col-id-abc/query" in called_url


# ============================================================================
# ChromaDBBackend -- error handling (mocked)
# ============================================================================

class TestBackendErrorHandling:
    """Test error handling for server-down and bad-response scenarios."""

    def test_heartbeat_connection_error(self):
        b = ChromaDBBackend()
        b._session = MagicMock()
        import requests
        b._session.get.side_effect = requests.ConnectionError("Connection refused")
        with pytest.raises(requests.ConnectionError):
            b.heartbeat()

    def test_version_connection_error(self):
        b = ChromaDBBackend()
        b._session = MagicMock()
        import requests
        b._session.get.side_effect = requests.ConnectionError("Connection refused")
        with pytest.raises(requests.ConnectionError):
            b.version()

    def test_list_collections_http_error(self):
        b = ChromaDBBackend()
        b._session = MagicMock()
        import requests
        resp = MagicMock()
        resp.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        b._session.get.return_value = resp
        with pytest.raises(requests.HTTPError):
            b.list_collections()

    def test_get_collection_404(self):
        b = ChromaDBBackend()
        b._session = MagicMock()
        import requests
        resp = MagicMock()
        resp.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        b._session.get.return_value = resp
        with pytest.raises(requests.HTTPError):
            b.get_collection("nonexistent")


# ============================================================================
# CLI argument parsing (Click CliRunner)
# ============================================================================

class TestCLIParsing:
    """Test Click CLI argument parsing and output formatting."""

    @pytest.fixture
    def runner(self):
        from click.testing import CliRunner
        return CliRunner()

    @pytest.fixture
    def cli(self):
        from cli_anything.chromadb.chromadb_cli import cli
        return cli

    def test_help_flag(self, runner, cli):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "ChromaDB" in result.output or "chromadb" in result.output.lower()

    def test_server_help(self, runner, cli):
        result = runner.invoke(cli, ["server", "--help"])
        assert result.exit_code == 0
        assert "heartbeat" in result.output
        assert "version" in result.output

    def test_collection_help(self, runner, cli):
        result = runner.invoke(cli, ["collection", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "create" in result.output
        assert "delete" in result.output
        assert "info" in result.output

    def test_document_help(self, runner, cli):
        result = runner.invoke(cli, ["document", "--help"])
        assert result.exit_code == 0
        assert "add" in result.output
        assert "get" in result.output
        assert "delete" in result.output
        assert "count" in result.output

    def test_query_help(self, runner, cli):
        result = runner.invoke(cli, ["query", "--help"])
        assert result.exit_code == 0
        assert "search" in result.output

    @patch("cli_anything.chromadb.utils.chromadb_backend.ChromaDBBackend.heartbeat")
    def test_json_output_heartbeat(self, mock_hb, runner, cli):
        mock_hb.return_value = {"nanosecond_heartbeat": 9999}
        result = runner.invoke(cli, ["--json", "server", "heartbeat"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "nanosecond_heartbeat" in data

    @patch("cli_anything.chromadb.utils.chromadb_backend.ChromaDBBackend.version")
    def test_json_output_version(self, mock_ver, runner, cli):
        mock_ver.return_value = "0.6.0"
        result = runner.invoke(cli, ["--json", "server", "version"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["version"] == "0.6.0"

    @patch("cli_anything.chromadb.utils.chromadb_backend.ChromaDBBackend.list_collections")
    def test_json_output_collection_list(self, mock_list, runner, cli):
        mock_list.return_value = [{"name": "test_col", "id": "abc-123", "metadata": {}}]
        result = runner.invoke(cli, ["--json", "collection", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["name"] == "test_col"

    @patch("cli_anything.chromadb.utils.chromadb_backend.ChromaDBBackend.heartbeat")
    def test_human_output_heartbeat(self, mock_hb, runner, cli):
        mock_hb.return_value = {"nanosecond_heartbeat": 9999}
        result = runner.invoke(cli, ["server", "heartbeat"])
        assert result.exit_code == 0
        # Human mode should not be valid JSON
        assert "alive" in result.output.lower() or "heartbeat" in result.output.lower()

    @patch("cli_anything.chromadb.utils.chromadb_backend.ChromaDBBackend.heartbeat")
    def test_server_error_json_output(self, mock_hb, runner, cli):
        import requests
        mock_hb.side_effect = requests.ConnectionError("Connection refused")
        result = runner.invoke(cli, ["--json", "server", "heartbeat"])
        # Should exit with error
        assert result.exit_code != 0
        data = json.loads(result.output)
        assert "error" in data

    def test_custom_host_flag(self, runner, cli):
        """Verify --host flag is accepted (even if connection fails)."""
        result = runner.invoke(cli, ["--host", "http://fake:9999", "server", "--help"])
        assert result.exit_code == 0
