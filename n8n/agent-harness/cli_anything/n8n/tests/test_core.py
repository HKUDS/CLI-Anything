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

    def test_load_from_file(self, tmp_path):
        from cli_anything.n8n.n8n_cli import _load_json_arg
        f = tmp_path / "test.json"
        f.write_text('{"name": "from_file"}')
        result = _load_json_arg(f"@{f}")
        assert result == {"name": "from_file"}


# ─── CLI commands (subprocess) ──────────────────────────────────────────────

class TestCLICommands:
    def test_export_import_roundtrip(self, tmp_path):
        """Test that export strips server fields using the REAL _clean_for_api."""
        from cli_anything.n8n.n8n_cli import _clean_for_api, _load_json_arg
        # Simulate export data (what get_workflow returns)
        server_data = {
            "id": "abc123",
            "name": "Test WF",
            "nodes": [{"type": "n8n-nodes-base.manualTrigger"}],
            "connections": {},
            "settings": {},
            "createdAt": "2026-01-01",
            "updatedAt": "2026-01-02",
            "versionId": "v1",
            "shared": [{"role": "owner"}],
        }
        # Use the REAL function, not a reimplementation
        export_data = _clean_for_api(server_data)
        assert "id" not in export_data
        assert "createdAt" not in export_data
        assert "name" in export_data
        assert "nodes" in export_data

        # Write and read back
        out = tmp_path / "export.json"
        out.write_text(json.dumps(export_data, indent=2))
        loaded = _load_json_arg(f"@{out}")
        assert loaded["name"] == "Test WF"
        assert "id" not in loaded


class TestVersions:
    def test_save_and_list(self, tmp_path, monkeypatch):
        from cli_anything.n8n.core import versions as ver
        monkeypatch.setattr(ver, "DB_DIR", tmp_path)
        monkeypatch.setattr(ver, "DB_PATH", tmp_path / "versions.db")

        wf = {"name": "Test WF", "nodes": [], "connections": {}}
        v1 = ver.save_snapshot("wf1", wf, "update")
        assert v1 == 1
        v2 = ver.save_snapshot("wf1", {**wf, "name": "Updated"}, "patch")
        assert v2 == 2

        vers = ver.list_versions("wf1")
        assert len(vers) == 2
        assert vers[0]["version_number"] == 2

    def test_get_snapshot(self, tmp_path, monkeypatch):
        from cli_anything.n8n.core import versions as ver
        monkeypatch.setattr(ver, "DB_DIR", tmp_path)
        monkeypatch.setattr(ver, "DB_PATH", tmp_path / "versions.db")

        wf = {"name": "Original", "nodes": [{"name": "A"}]}
        ver.save_snapshot("wf1", wf, "update")
        snapshot = ver.get_snapshot("wf1", 1)
        assert snapshot["name"] == "Original"
        assert snapshot["nodes"][0]["name"] == "A"

    def test_prune(self, tmp_path, monkeypatch):
        from cli_anything.n8n.core import versions as ver
        monkeypatch.setattr(ver, "DB_DIR", tmp_path)
        monkeypatch.setattr(ver, "DB_PATH", tmp_path / "versions.db")

        for i in range(5):
            ver.save_snapshot("wf1", {"name": f"v{i}"}, "test")
        deleted = ver.prune_versions("wf1", keep=2)
        assert deleted == 3
        remaining = ver.list_versions("wf1")
        assert len(remaining) == 2

    def test_stats(self, tmp_path, monkeypatch):
        from cli_anything.n8n.core import versions as ver
        monkeypatch.setattr(ver, "DB_DIR", tmp_path)
        monkeypatch.setattr(ver, "DB_PATH", tmp_path / "versions.db")

        ver.save_snapshot("wf1", {"name": "A"}, "test")
        ver.save_snapshot("wf2", {"name": "B"}, "test")
        st = ver.stats()
        assert st["total_versions"] == 2
        assert st["workflows_tracked"] == 2


class TestFixers:
    def test_expression_format(self):
        from cli_anything.n8n.core.fixers import autofix
        wf = {"name": "Test", "nodes": [{"name": "Node1", "type": "n8n-nodes-base.set", "parameters": {"value": "{{$json.name}}"}}], "connections": {}}
        _, fixes = autofix(wf, apply=False)
        assert any(f.fix_type == "expression-format" for f in fixes)

    def test_expression_format_apply(self):
        from cli_anything.n8n.core.fixers import autofix
        wf = {"name": "Test", "nodes": [{"name": "Node1", "type": "n8n-nodes-base.set", "parameters": {"value": "{{$json.name}}"}}], "connections": {}}
        fixed, fixes = autofix(wf, apply=True)
        assert fixed["nodes"][0]["parameters"]["value"] == "={{$json.name}}"

    def test_webhook_missing_path(self):
        from cli_anything.n8n.core.fixers import autofix
        wf = {"name": "Test", "nodes": [{"name": "Webhook", "type": "n8n-nodes-base.webhook", "parameters": {}}], "connections": {}}
        _, fixes = autofix(wf, apply=False)
        assert any(f.fix_type == "webhook-missing-path" for f in fixes)

    def test_orphan_connection(self):
        from cli_anything.n8n.core.fixers import autofix
        wf = {"name": "Test", "nodes": [{"name": "A", "type": "test"}], "connections": {"NonExistent": {"main": [[{"node": "A", "type": "main", "index": 0}]]}}}
        fixed, fixes = autofix(wf, apply=True)
        assert "NonExistent" not in fixed["connections"]

    def test_no_issues(self):
        from cli_anything.n8n.core.fixers import autofix
        wf = {"name": "Test", "nodes": [{"name": "A", "type": "n8n-nodes-base.manualTrigger", "parameters": {}}], "connections": {}}
        _, fixes = autofix(wf, apply=False)
        assert len(fixes) == 0

    def test_null_nodes_no_crash(self):
        """Bug fix: autofix must not crash when nodes or connections are None."""
        from cli_anything.n8n.core.fixers import autofix
        wf = {"name": "Test", "nodes": None, "connections": None}
        _, fixes = autofix(wf, apply=False)
        assert isinstance(fixes, list)

    def test_expression_in_list_apply(self):
        """Bug fix: _set_nested must handle bracket notation for list items."""
        from cli_anything.n8n.core.fixers import autofix
        wf = {
            "name": "Test",
            "nodes": [{"name": "Set", "type": "n8n-nodes-base.set", "parameters": {
                "assignments": [{"name": "x", "value": "{{$json.y}}"}]
            }}],
            "connections": {},
        }
        fixed, fixes = autofix(wf, apply=True)
        # The fix should update the value inside the list, not create a corrupted key
        assert "assignments[0]" not in fixed["nodes"][0]["parameters"]
        assert fixed["nodes"][0]["parameters"]["assignments"][0]["value"] == "={{$json.y}}"


class TestNodes:
    @patch("cli_anything.n8n.core.nodes.requests.get")
    def test_search_nodes(self, mock_get):
        from cli_anything.n8n.core import nodes as nd
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"total": 100, "objects": [{"package": {"name": "n8n-nodes-test", "version": "1.0.0", "description": "Test", "publisher": {"username": "dev"}}}]}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        result = nd.search_nodes("test")
        assert result["total"] == 100

    @patch("cli_anything.n8n.core.nodes.requests.get")
    def test_get_node_info(self, mock_get):
        from cli_anything.n8n.core import nodes as nd
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"name": "n8n-nodes-test", "description": "Test pkg", "dist-tags": {"latest": "1.0.0"}, "versions": {"1.0.0": {"license": "MIT", "n8n": {"nodes": [{"type": "testNode"}], "credentials": []}, "keywords": []}}, "author": {"name": "dev"}}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        result = nd.get_node_info("n8n-nodes-test")
        assert result["name"] == "n8n-nodes-test"
        assert len(result["n8n_nodes"]) == 1


class TestScaffolds:
    def test_list_patterns(self):
        from cli_anything.n8n.core.scaffolds import list_patterns
        patterns = list_patterns()
        assert len(patterns) == 5
        names = {p["name"] for p in patterns}
        assert "webhook" in names
        assert "ai-agent" in names

    def test_get_scaffold(self):
        from cli_anything.n8n.core.scaffolds import get_scaffold
        wf = get_scaffold("webhook")
        assert wf["name"] == "Webhook Processing"
        assert len(wf["nodes"]) > 0
        assert "connections" in wf

    def test_get_scaffold_custom_name(self):
        from cli_anything.n8n.core.scaffolds import get_scaffold
        wf = get_scaffold("api", name="My API Flow")
        assert wf["name"] == "My API Flow"

    def test_get_scaffold_invalid(self):
        from cli_anything.n8n.core.scaffolds import get_scaffold
        with pytest.raises(ValueError, match="Unknown pattern"):
            get_scaffold("nonexistent")


class TestExpressions:
    def test_valid_expression(self):
        from cli_anything.n8n.core.expressions import validate_expression
        result = validate_expression("={{$json.name}}")
        assert result.valid
        assert len(result.issues) == 0

    def test_mismatched_braces(self):
        from cli_anything.n8n.core.expressions import validate_expression
        result = validate_expression("={{$json.name}")
        assert not result.valid
        assert any("Mismatched" in i for i in result.issues)

    def test_missing_equals_prefix(self):
        from cli_anything.n8n.core.expressions import validate_expression
        result = validate_expression("{{$json.name}}")
        assert result.valid  # valid but with warning
        assert any("prefix" in w for w in result.warnings)

    def test_json_bracket_without_quotes(self):
        from cli_anything.n8n.core.expressions import validate_expression
        result = validate_expression("={{$json[key]}}")
        assert any("quotes" in i for i in result.issues)


class TestTemplates:
    @patch("cli_anything.n8n.core.templates.requests.get")
    def test_search_templates(self, mock_get):
        from cli_anything.n8n.core import templates as tmpl
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"totalWorkflows": 5, "workflows": [{"id": 1, "name": "Test"}]}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        result = tmpl.search_templates("telegram")
        assert result["totalWorkflows"] == 5

    @patch("cli_anything.n8n.core.templates.requests.get")
    def test_get_template(self, mock_get):
        from cli_anything.n8n.core import templates as tmpl
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"workflow": {"name": "My Template", "nodes": []}}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        result = tmpl.get_template(123)
        assert result["workflow"]["name"] == "My Template"
