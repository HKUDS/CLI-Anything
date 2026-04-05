"""E2E tests — require a running n8n instance.

Set N8N_BASE_URL and N8N_API_KEY env vars to run these tests.
Verified against n8n 2.43.0 (API v1.1.1).
Skip with: pytest -m "not e2e"
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid

import pytest
import requests as req

from cli_anything.n8n.core import credentials, tags, variables, workflows


pytestmark = pytest.mark.e2e

N8N_URL = os.environ.get("N8N_BASE_URL", "")
N8N_KEY = os.environ.get("N8N_API_KEY", "")


def _skip_if_no_n8n():
    if not N8N_URL or not N8N_KEY:
        pytest.skip("N8N_BASE_URL and N8N_API_KEY required for E2E tests")


def _resolve_cli() -> list[str]:
    import shutil
    if shutil.which("cli-anything-n8n"):
        return ["cli-anything-n8n"]
    return [sys.executable, "-m", "cli_anything.n8n"]


# ─── Subprocess tests (no n8n needed) ──────────────────────────────────────

class TestCLISubprocess:
    def test_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "n8n workflow automation" in result.stdout

    def test_version(self):
        result = subprocess.run(
            [*_resolve_cli(), "--version"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "2.3.0" in result.stdout

    def test_workflow_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "workflow", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "list" in result.stdout
        assert "set-tags" in result.stdout
        assert "transfer" in result.stdout
        assert "export" in result.stdout
        assert "import" in result.stdout

    def test_status_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "status", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "overview" in result.stdout.lower()

    def test_execution_watch_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "execution", "watch", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "interval" in result.stdout

    def test_config_test_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "config", "test", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "connection" in result.stdout.lower()

    def test_workflow_search_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "workflow", "search", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "QUERY" in result.stdout

    def test_workflow_bulk_activate_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "workflow", "bulk-activate", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "--tag" in result.stdout
        assert "--search" in result.stdout

    def test_workflow_backup_all_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "workflow", "backup-all", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "--dir" in result.stdout

    def test_workflow_restore_all_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "workflow", "restore-all", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "--dry-run" in result.stdout

    def test_workflow_diff_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "workflow", "diff", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "SOURCE" in result.stdout

    def test_execution_errors_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "execution", "errors", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "--details" in result.stdout

    def test_template_search_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "template", "search", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "QUERY" in result.stdout

    def test_template_deploy_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "template", "deploy", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "TEMPLATE_ID" in result.stdout

    def test_workflow_validate_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "workflow", "validate", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "SOURCE" in result.stdout

    def test_workflow_test_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "workflow", "test", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "WORKFLOW_ID" in result.stdout

    def test_workflow_autofix_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "workflow", "autofix", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "--apply" in result.stdout

    def test_workflow_patch_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "workflow", "patch", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "--rename" in result.stdout
        assert "--enable-node" in result.stdout
        assert "--remove-node" in result.stdout
        assert "--connect" in result.stdout

    def test_health_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "health", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "--diagnostic" in result.stdout

    def test_workflow_versions_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "workflow", "versions", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "rollback" in result.stdout
        assert "prune" in result.stdout
        assert "stats" in result.stdout

    def test_workflow_scaffold_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "workflow", "scaffold", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "webhook" in result.stdout
        assert "ai-agent" in result.stdout

    def test_workflow_patterns(self):
        result = subprocess.run(
            [*_resolve_cli(), "workflow", "patterns"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "webhook" in result.stdout
        assert "database" in result.stdout

    def test_expression_validate_valid(self):
        result = subprocess.run(
            [*_resolve_cli(), "expression", "={{$json.name}}"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "valid" in result.stdout.lower()

    def test_expression_validate_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "expression", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0

    def test_node_search_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "node", "search", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "QUERY" in result.stdout

    def test_node_info_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "node", "info", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "PACKAGE_NAME" in result.stdout

    def test_completions_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "completions", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "bash" in result.stdout

    def test_credential_help(self):
        result = subprocess.run(
            [*_resolve_cli(), "credential", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "create" in result.stdout
        assert "schema" in result.stdout
        assert "transfer" in result.stdout
        # "list" command should not appear as a subcommand
        lines = [l.strip() for l in result.stdout.splitlines()]
        subcommands = [l for l in lines if l and not l.startswith("Usage") and not l.startswith("-") and not l.startswith("Options") and not l.startswith("Credential")]
        assert not any(l.startswith("list") for l in subcommands)

    def test_config_show_json(self):
        result = subprocess.run(
            [*_resolve_cli(), "--json", "config", "show"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0

    def test_no_table_command(self):
        result = subprocess.run(
            [*_resolve_cli(), "table", "--help"], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode != 0  # table command removed


# ─── E2E tests (n8n required) ──────────────────────────────────────────────

class TestWorkflowsE2E:
    def test_list_workflows(self):
        _skip_if_no_n8n()
        result = workflows.list_workflows(base_url=N8N_URL, api_key=N8N_KEY, limit=5)
        assert "data" in result

    def test_workflow_crud(self):
        _skip_if_no_n8n()
        wf = workflows.create_workflow(
            {"name": "CLI-Anything Test WF", "nodes": [], "connections": {}, "settings": {}},
            base_url=N8N_URL, api_key=N8N_KEY,
        )
        wf_id = wf["id"]

        try:
            detail = workflows.get_workflow(wf_id, base_url=N8N_URL, api_key=N8N_KEY)
            assert detail["name"] == "CLI-Anything Test WF"

            updated = workflows.update_workflow(
                wf_id,
                {"name": "CLI-Anything Test WF Updated", "nodes": [], "connections": {}, "settings": {}},
                base_url=N8N_URL, api_key=N8N_KEY,
            )
            assert updated["name"] == "CLI-Anything Test WF Updated"
        finally:
            workflows.delete_workflow(wf_id, base_url=N8N_URL, api_key=N8N_KEY)

        try:
            workflows.get_workflow(wf_id, base_url=N8N_URL, api_key=N8N_KEY)
            assert False, "Workflow should have been deleted"
        except req.exceptions.HTTPError as e:
            assert e.response.status_code == 404


class TestCredentialsE2E:
    def test_get_schema(self):
        _skip_if_no_n8n()
        result = credentials.get_credential_schema("httpBasicAuth", base_url=N8N_URL, api_key=N8N_KEY)
        assert isinstance(result, (dict, list))


class TestVariablesE2E:
    def test_list_variables(self):
        _skip_if_no_n8n()
        try:
            result = variables.list_variables(base_url=N8N_URL, api_key=N8N_KEY)
            assert isinstance(result, (list, dict))
        except req.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                pytest.skip("Variables API requires Enterprise license")
            raise


class TestTagsE2E:
    def test_list_tags(self):
        _skip_if_no_n8n()
        result = tags.list_tags(base_url=N8N_URL, api_key=N8N_KEY)
        assert isinstance(result, (list, dict))

    def test_tag_lifecycle(self):
        _skip_if_no_n8n()
        unique_name = f"CLITEST{uuid.uuid4().hex[:8].upper()}"

        tag = tags.create_tag(unique_name, base_url=N8N_URL, api_key=N8N_KEY)
        tag_id = tag["id"]

        try:
            all_tags = tags.list_tags(base_url=N8N_URL, api_key=N8N_KEY)
            data = all_tags.get("data", all_tags) if isinstance(all_tags, dict) else all_tags
            names = [t["name"] for t in data if isinstance(t, dict)]
            assert unique_name in names

            updated_name = f"{unique_name}UPD"
            updated = tags.update_tag(tag_id, updated_name, base_url=N8N_URL, api_key=N8N_KEY)
            assert updated["name"] == updated_name
        finally:
            tags.delete_tag(tag_id, base_url=N8N_URL, api_key=N8N_KEY)
