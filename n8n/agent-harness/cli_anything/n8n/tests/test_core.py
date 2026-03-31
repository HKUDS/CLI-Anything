"""Unit tests — all HTTP calls mocked."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from cli_anything.n8n.core import (
    credentials,
    executions,
    project,
    tags,
    variables,
    workflows,
)
from cli_anything.n8n.utils import n8n_backend


# ─── Helpers ────────────────────────────────────────────────────────────────

def mock_response(status_code: int = 200, json_data: dict | list | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = json.dumps(json_data or {})
    resp.raise_for_status = MagicMock()
    return resp


BASE = "https://n8n.example.com"
KEY = "test-api-key-1234"


# ─── Backend ────────────────────────────────────────────────────────────────

class TestBackend:
    def test_url_construction(self):
        url = n8n_backend._url(BASE, "/workflows")
        assert url == f"{BASE}/api/v1/workflows"

    def test_url_with_full_api_path(self):
        url = n8n_backend._url(BASE, "/api/v1/workflows")
        assert url == f"{BASE}/api/v1/workflows"

    @patch.dict("os.environ", {"N8N_BASE_URL": ""}, clear=False)
    def test_url_missing_base(self):
        with pytest.raises(ValueError, match="base URL not configured"):
            n8n_backend._url("", "/workflows")

    def test_headers_with_key(self):
        h = n8n_backend._headers("mykey")
        assert h["X-N8N-API-KEY"] == "mykey"
        assert h["Content-Type"] == "application/json"

    def test_headers_no_key(self):
        with patch.dict("os.environ", {}, clear=True):
            h = n8n_backend._headers("")
            assert "X-N8N-API-KEY" not in h

    @patch("cli_anything.n8n.utils.n8n_backend.requests.request")
    def test_api_get(self, mock_req):
        mock_req.return_value = mock_response(200, {"data": []})
        result = n8n_backend.api_get("/workflows", base_url=BASE, api_key=KEY)
        assert result == {"data": []}
        args, kwargs = mock_req.call_args
        assert args[0] == "GET"

    @patch("cli_anything.n8n.utils.n8n_backend.requests.request")
    def test_api_post(self, mock_req):
        mock_req.return_value = mock_response(200, {"id": "1"})
        result = n8n_backend.api_post("/workflows", {"name": "test"}, base_url=BASE, api_key=KEY)
        assert result == {"id": "1"}

    @patch("cli_anything.n8n.utils.n8n_backend.requests.request")
    def test_api_delete_204(self, mock_req):
        mock_req.return_value = mock_response(204)
        result = n8n_backend.api_delete("/workflows/1", base_url=BASE, api_key=KEY)
        assert result == {}

    @patch("cli_anything.n8n.utils.n8n_backend.requests.request")
    def test_custom_timeout(self, mock_req):
        mock_req.return_value = mock_response(200, {})
        n8n_backend.api_request("GET", "/test", base_url=BASE, api_key=KEY, timeout=120)
        _, kwargs = mock_req.call_args
        assert kwargs["timeout"] == 120


# ─── Workflows ──────────────────────────────────────────────────────────────

class TestWorkflows:
    @patch("cli_anything.n8n.core.workflows.api_get")
    def test_list_workflows(self, mock_get):
        mock_get.return_value = {"data": [{"id": "1", "name": "Test"}]}
        result = workflows.list_workflows(base_url=BASE, api_key=KEY)
        assert result["data"][0]["name"] == "Test"

    @patch("cli_anything.n8n.core.workflows.api_get")
    def test_list_workflows_with_filters(self, mock_get):
        mock_get.return_value = {"data": []}
        workflows.list_workflows(base_url=BASE, api_key=KEY, active=True, name="foo")
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["active"] == "true"
        assert kwargs["params"]["name"] == "foo"

    @patch("cli_anything.n8n.core.workflows.api_get")
    def test_get_workflow(self, mock_get):
        mock_get.return_value = {"id": "1", "name": "Test"}
        result = workflows.get_workflow("1", base_url=BASE, api_key=KEY)
        assert result["id"] == "1"

    @patch("cli_anything.n8n.core.workflows.api_post")
    def test_create_workflow(self, mock_post):
        mock_post.return_value = {"id": "2"}
        result = workflows.create_workflow({"name": "New"}, base_url=BASE, api_key=KEY)
        assert result["id"] == "2"

    @patch("cli_anything.n8n.core.workflows.api_delete")
    def test_delete_workflow(self, mock_del):
        mock_del.return_value = {}
        workflows.delete_workflow("1", base_url=BASE, api_key=KEY)
        mock_del.assert_called_once()

    @patch("cli_anything.n8n.core.workflows.api_post")
    def test_activate_workflow(self, mock_post):
        mock_post.return_value = {"active": True}
        result = workflows.activate_workflow("1", base_url=BASE, api_key=KEY)
        assert result["active"] is True

    @patch("cli_anything.n8n.core.workflows.api_put")
    def test_transfer_workflow(self, mock_put):
        mock_put.return_value = {}
        workflows.transfer_workflow("1", "proj-1", base_url=BASE, api_key=KEY)
        mock_put.assert_called_once()

    @patch("cli_anything.n8n.core.workflows.api_put")
    def test_update_workflow_tags(self, mock_put):
        mock_put.return_value = [{"id": "t1"}]
        result = workflows.update_workflow_tags("1", [{"id": "t1"}], base_url=BASE, api_key=KEY)
        assert result == [{"id": "t1"}]


# ─── Executions ─────────────────────────────────────────────────────────────

class TestExecutions:
    @patch("cli_anything.n8n.core.executions.api_get")
    def test_list_executions(self, mock_get):
        mock_get.return_value = {"data": [{"id": "10", "status": "success"}]}
        result = executions.list_executions(base_url=BASE, api_key=KEY, status="success")
        assert result["data"][0]["status"] == "success"

    @patch("cli_anything.n8n.core.executions.api_post")
    def test_retry_execution(self, mock_post):
        mock_post.return_value = {"id": "11"}
        result = executions.retry_execution("10", base_url=BASE, api_key=KEY)
        assert result["id"] == "11"

    @patch("cli_anything.n8n.core.executions.api_delete")
    def test_delete_execution(self, mock_del):
        mock_del.return_value = {}
        executions.delete_execution("10", base_url=BASE, api_key=KEY)
        mock_del.assert_called_once()


# ─── Credentials ────────────────────────────────────────────────────────────

class TestCredentials:
    @patch("cli_anything.n8n.core.credentials.api_post")
    def test_create_credential(self, mock_post):
        mock_post.return_value = {"id": "c1"}
        result = credentials.create_credential({"name": "test", "type": "httpBasicAuth", "data": {}}, base_url=BASE, api_key=KEY)
        assert result["id"] == "c1"

    @patch("cli_anything.n8n.core.credentials.api_get")
    def test_get_schema(self, mock_get):
        mock_get.return_value = {"properties": {}}
        result = credentials.get_credential_schema("telegramApi", base_url=BASE, api_key=KEY)
        assert "properties" in result

    @patch("cli_anything.n8n.core.credentials.api_delete")
    def test_delete_credential(self, mock_del):
        mock_del.return_value = {}
        credentials.delete_credential("c1", base_url=BASE, api_key=KEY)
        mock_del.assert_called_once()

    @patch("cli_anything.n8n.core.credentials.api_put")
    def test_transfer_credential(self, mock_put):
        mock_put.return_value = {}
        credentials.transfer_credential("c1", "proj-1", base_url=BASE, api_key=KEY)
        mock_put.assert_called_once()


# ─── Variables ──────────────────────────────────────────────────────────────

class TestVariables:
    @patch("cli_anything.n8n.core.variables.api_get")
    def test_list_variables(self, mock_get):
        mock_get.return_value = [{"id": "1", "key": "FOO", "value": "bar"}]
        result = variables.list_variables(base_url=BASE, api_key=KEY)
        assert result[0]["key"] == "FOO"

    @patch("cli_anything.n8n.core.variables.api_post")
    def test_create_variable(self, mock_post):
        mock_post.return_value = {"id": "2", "key": "BAZ", "value": "qux"}
        result = variables.create_variable("BAZ", "qux", base_url=BASE, api_key=KEY)
        assert result["key"] == "BAZ"


# ─── Tags ───────────────────────────────────────────────────────────────────

class TestTags:
    @patch("cli_anything.n8n.core.tags.api_get")
    def test_list_tags(self, mock_get):
        mock_get.return_value = {"data": [{"id": "1", "name": "prod"}]}
        result = tags.list_tags(base_url=BASE, api_key=KEY)
        assert result["data"][0]["name"] == "prod"

    @patch("cli_anything.n8n.core.tags.api_post")
    def test_create_tag(self, mock_post):
        mock_post.return_value = {"id": "2", "name": "dev"}
        result = tags.create_tag("dev", base_url=BASE, api_key=KEY)
        assert result["name"] == "dev"


# ─── Project config ─────────────────────────────────────────────────────────

class TestProject:
    @patch.dict("os.environ", {"N8N_BASE_URL": "https://env.example.com", "N8N_API_KEY": "env-key"})
    def test_load_config_env_override(self):
        cfg = project.load_config()
        assert cfg["base_url"] == "https://env.example.com"
        assert cfg["api_key"] == "env-key"

    def test_get_connection_explicit_args(self):
        url, key = project.get_connection("https://arg.com", "arg-key")
        assert url == "https://arg.com"
        assert key == "arg-key"


# ─── JSON arg parsing ──────────────────────────────────────────────────────

class TestLoadJsonArg:
    def test_parse_inline_json(self):
        from cli_anything.n8n.n8n_cli import _load_json_arg
        result = _load_json_arg('{"name": "test"}')
        assert result == {"name": "test"}

    def test_invalid_json_raises(self):
        from cli_anything.n8n.n8n_cli import _load_json_arg
        with pytest.raises(ValueError, match="Invalid JSON"):
            _load_json_arg("not json")

    def test_file_not_found_raises(self):
        from cli_anything.n8n.n8n_cli import _load_json_arg
        with pytest.raises(ValueError, match="File not found"):
            _load_json_arg("@/nonexistent/file.json")
