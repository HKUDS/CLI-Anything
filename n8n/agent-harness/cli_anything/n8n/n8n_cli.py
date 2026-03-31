"""cli-anything-n8n — CLI for n8n workflow automation.

Based on n8n Public API v1.1.1 (n8n >= 1.0.0).
Verified against n8n 2.43.0.
"""

from __future__ import annotations

import json
import sys
from typing import Any
from urllib.parse import urlparse

import click
import requests

from cli_anything.n8n.core import (
    credentials,
    executions,
    project,
    tags,
    variables,
    workflows,
)
from cli_anything.n8n.utils.repl_skin import error, output, print_banner, success, warn


CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}
VERSION = "1.1.0"


def _conn(ctx: click.Context) -> dict[str, str]:
    """Extract connection kwargs from Click context."""
    return {"base_url": ctx.obj["base_url"], "api_key": ctx.obj["api_key"]}


def _json_flag(ctx: click.Context) -> bool:
    return ctx.obj.get("as_json", False)


def _load_json_arg(value: str) -> Any:
    """Parse a JSON string or read from file if prefixed with @."""
    if value.startswith("@"):
        filepath = value[1:]
        try:
            with open(filepath) as f:
                return json.load(f)
        except FileNotFoundError:
            raise ValueError(f"File not found: {filepath}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {filepath}: {e}")
    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


# ─── Root ───────────────────────────────────────────────────────────────────

@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.option("--url", default=None, envvar="N8N_BASE_URL", help="n8n instance URL")
@click.option("--api-key", default=None, envvar="N8N_API_KEY", help="n8n API key")
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
@click.version_option(version=VERSION, prog_name="cli-anything-n8n")
@click.pass_context
def cli(ctx: click.Context, url: str | None, api_key: str | None, as_json: bool) -> None:
    """CLI harness for n8n workflow automation (API v1.1.1, n8n >= 1.0.0)."""
    ctx.ensure_object(dict)
    resolved_url, resolved_key = project.get_connection(url, api_key)
    ctx.obj["base_url"] = resolved_url
    ctx.obj["api_key"] = resolved_key
    ctx.obj["as_json"] = as_json
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ─── REPL ───────────────────────────────────────────────────────────────────

@cli.command("repl", hidden=True)
@click.pass_context
def repl(ctx: click.Context) -> None:
    """Start interactive REPL."""
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import InMemoryHistory
    except ImportError:
        click.echo("prompt-toolkit is required for REPL mode. Install: pip install prompt-toolkit")
        sys.exit(1)

    base_url = ctx.obj["base_url"]
    print_banner(base_url or "(not configured)")

    session = PromptSession(history=InMemoryHistory())
    while True:
        try:
            line = session.prompt("n8n> ").strip()
        except (EOFError, KeyboardInterrupt):
            click.echo("\nBye!")
            break
        if not line:
            continue
        if line in ("exit", "quit", "q"):
            click.echo("Bye!")
            break
        if line == "help":
            click.echo(cli.get_help(ctx))
            continue
        try:
            args = line.split()
            cli.main(args, standalone_mode=False, obj=ctx.obj)
        except click.exceptions.UsageError as exc:
            error(str(exc))
        except SystemExit:
            pass
        except Exception as exc:
            error(str(exc))


# ─── Config ─────────────────────────────────────────────────────────────────

@cli.group("config")
def config_() -> None:
    """Configuration management."""


@config_.command("show")
@click.pass_context
def config_show(ctx: click.Context) -> None:
    """Show current configuration (API key is always masked)."""
    cfg = project.load_config()
    masked = {**cfg}
    if masked.get("api_key"):
        key = masked["api_key"]
        masked["api_key"] = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "****"
    output(masked, _json_flag(ctx))


@config_.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx: click.Context, key: str, value: str) -> None:
    """Set a config value (base_url, api_key)."""
    cfg = project.load_config()
    if key not in ("base_url", "api_key"):
        error(f"Unknown config key: {key}. Use: base_url, api_key")
        return
    if key == "base_url":
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            error(f"Invalid URL: {value} (must include http:// or https://)")
            return
    cfg[key] = value
    path = project.save_config(cfg)
    success(f"Saved {key} to {path}")


# ─── Workflows ──────────────────────────────────────────────────────────────

@cli.group("workflow")
def workflow_() -> None:
    """Workflow management."""


@workflow_.command("list")
@click.option("--active/--inactive", default=None, help="Filter by active status")
@click.option("--tags", "tag_filter", default=None, help="Filter by tag names (comma-separated)")
@click.option("--name", default=None, help="Filter by name (contains)")
@click.option("--limit", default=50, type=int, help="Max results")
@click.option("--cursor", default=None, help="Pagination cursor")
@click.pass_context
def workflow_list(ctx: click.Context, active: bool | None, tag_filter: str | None, name: str | None, limit: int, cursor: str | None) -> None:
    """List workflows."""
    data = workflows.list_workflows(
        **_conn(ctx), active=active, tags=tag_filter, name=name, limit=limit, cursor=cursor,
    )
    output(data, _json_flag(ctx))


@workflow_.command("get")
@click.argument("workflow_id")
@click.pass_context
def workflow_get(ctx: click.Context, workflow_id: str) -> None:
    """Get workflow details."""
    data = workflows.get_workflow(workflow_id, **_conn(ctx))
    output(data, _json_flag(ctx))


@workflow_.command("create")
@click.argument("json_data")
@click.pass_context
def workflow_create(ctx: click.Context, json_data: str) -> None:
    """Create a workflow from JSON (inline or @file.json)."""
    data = workflows.create_workflow(_load_json_arg(json_data), **_conn(ctx))
    output(data, _json_flag(ctx))


@workflow_.command("update")
@click.argument("workflow_id")
@click.argument("json_data")
@click.pass_context
def workflow_update(ctx: click.Context, workflow_id: str, json_data: str) -> None:
    """Update a workflow."""
    data = workflows.update_workflow(workflow_id, _load_json_arg(json_data), **_conn(ctx))
    output(data, _json_flag(ctx))


@workflow_.command("delete")
@click.argument("workflow_id")
@click.confirmation_option(prompt="Are you sure you want to delete this workflow?")
@click.pass_context
def workflow_delete(ctx: click.Context, workflow_id: str) -> None:
    """Delete a workflow."""
    workflows.delete_workflow(workflow_id, **_conn(ctx))
    success(f"Workflow {workflow_id} deleted")


@workflow_.command("activate")
@click.argument("workflow_id")
@click.pass_context
def workflow_activate(ctx: click.Context, workflow_id: str) -> None:
    """Activate a workflow."""
    data = workflows.activate_workflow(workflow_id, **_conn(ctx))
    output(data, _json_flag(ctx))


@workflow_.command("deactivate")
@click.argument("workflow_id")
@click.pass_context
def workflow_deactivate(ctx: click.Context, workflow_id: str) -> None:
    """Deactivate a workflow."""
    data = workflows.deactivate_workflow(workflow_id, **_conn(ctx))
    output(data, _json_flag(ctx))


@workflow_.command("tags")
@click.argument("workflow_id")
@click.pass_context
def workflow_tags(ctx: click.Context, workflow_id: str) -> None:
    """Get workflow tags."""
    data = workflows.get_workflow_tags(workflow_id, **_conn(ctx))
    output(data, _json_flag(ctx))


@workflow_.command("set-tags")
@click.argument("workflow_id")
@click.argument("json_data", metavar="TAG_IDS_JSON")
@click.pass_context
def workflow_set_tags(ctx: click.Context, workflow_id: str, json_data: str) -> None:
    """Set workflow tags (JSON array of {id} objects)."""
    data = workflows.update_workflow_tags(workflow_id, _load_json_arg(json_data), **_conn(ctx))
    output(data, _json_flag(ctx))


@workflow_.command("transfer")
@click.argument("workflow_id")
@click.argument("project_id")
@click.pass_context
def workflow_transfer(ctx: click.Context, workflow_id: str, project_id: str) -> None:
    """Transfer a workflow to another project."""
    workflows.transfer_workflow(workflow_id, project_id, **_conn(ctx))
    success(f"Workflow {workflow_id} transferred to project {project_id}")


# ─── Executions ─────────────────────────────────────────────────────────────

@cli.group("execution")
def execution_() -> None:
    """Execution management."""


@execution_.command("list")
@click.option("--status", type=click.Choice(["error", "success", "waiting", "running", "new"]), default=None)
@click.option("--workflow-id", default=None, help="Filter by workflow ID")
@click.option("--limit", default=20, type=int)
@click.option("--cursor", default=None)
@click.option("--include-data", is_flag=True, default=False, help="Include execution data")
@click.pass_context
def execution_list(ctx: click.Context, status: str | None, workflow_id: str | None, limit: int, cursor: str | None, include_data: bool) -> None:
    """List executions."""
    data = executions.list_executions(
        **_conn(ctx), status=status, workflow_id=workflow_id, limit=limit, cursor=cursor, include_data=include_data,
    )
    output(data, _json_flag(ctx))


@execution_.command("get")
@click.argument("execution_id")
@click.option("--no-data", is_flag=True, default=False, help="Exclude execution data")
@click.pass_context
def execution_get(ctx: click.Context, execution_id: str, no_data: bool) -> None:
    """Get execution details."""
    data = executions.get_execution(execution_id, **_conn(ctx), include_data=not no_data)
    output(data, _json_flag(ctx))


@execution_.command("delete")
@click.argument("execution_id")
@click.pass_context
def execution_delete(ctx: click.Context, execution_id: str) -> None:
    """Delete an execution."""
    executions.delete_execution(execution_id, **_conn(ctx))
    success(f"Execution {execution_id} deleted")


@execution_.command("retry")
@click.argument("execution_id")
@click.pass_context
def execution_retry(ctx: click.Context, execution_id: str) -> None:
    """Retry a failed execution."""
    data = executions.retry_execution(execution_id, **_conn(ctx))
    output(data, _json_flag(ctx))


# ─── Credentials ────────────────────────────────────────────────────────────

@cli.group("credential")
def credential_() -> None:
    """Credential management (limited by n8n API — no list/update)."""


@credential_.command("create")
@click.argument("json_data")
@click.pass_context
def credential_create(ctx: click.Context, json_data: str) -> None:
    """Create a credential from JSON."""
    data = credentials.create_credential(_load_json_arg(json_data), **_conn(ctx))
    output(data, _json_flag(ctx))


@credential_.command("delete")
@click.argument("credential_id")
@click.confirmation_option(prompt="Are you sure you want to delete this credential?")
@click.pass_context
def credential_delete(ctx: click.Context, credential_id: str) -> None:
    """Delete a credential."""
    credentials.delete_credential(credential_id, **_conn(ctx))
    success(f"Credential {credential_id} deleted")


@credential_.command("schema")
@click.argument("credential_type")
@click.pass_context
def credential_schema(ctx: click.Context, credential_type: str) -> None:
    """Get credential schema for a type."""
    data = credentials.get_credential_schema(credential_type, **_conn(ctx))
    output(data, _json_flag(ctx))


@credential_.command("transfer")
@click.argument("credential_id")
@click.argument("project_id")
@click.pass_context
def credential_transfer(ctx: click.Context, credential_id: str, project_id: str) -> None:
    """Transfer a credential to another project."""
    credentials.transfer_credential(credential_id, project_id, **_conn(ctx))
    success(f"Credential {credential_id} transferred to project {project_id}")


# ─── Variables ──────────────────────────────────────────────────────────────

@cli.group("variable")
def variable_() -> None:
    """Variable management."""


@variable_.command("list")
@click.pass_context
def variable_list(ctx: click.Context) -> None:
    """List all variables."""
    data = variables.list_variables(**_conn(ctx))
    output(data, _json_flag(ctx))


@variable_.command("create")
@click.argument("key")
@click.argument("value")
@click.pass_context
def variable_create(ctx: click.Context, key: str, value: str) -> None:
    """Create a variable."""
    data = variables.create_variable(key, value, **_conn(ctx))
    output(data, _json_flag(ctx))


@variable_.command("update")
@click.argument("variable_id")
@click.argument("key")
@click.argument("value")
@click.pass_context
def variable_update(ctx: click.Context, variable_id: str, key: str, value: str) -> None:
    """Update a variable."""
    data = variables.update_variable(variable_id, key, value, **_conn(ctx))
    output(data, _json_flag(ctx))


@variable_.command("delete")
@click.argument("variable_id")
@click.pass_context
def variable_delete(ctx: click.Context, variable_id: str) -> None:
    """Delete a variable."""
    variables.delete_variable(variable_id, **_conn(ctx))
    success(f"Variable {variable_id} deleted")


# ─── Tags ───────────────────────────────────────────────────────────────────

@cli.group("tag")
def tag_() -> None:
    """Tag management."""


@tag_.command("list")
@click.option("--limit", default=50, type=int)
@click.pass_context
def tag_list(ctx: click.Context, limit: int) -> None:
    """List all tags."""
    data = tags.list_tags(**_conn(ctx), limit=limit)
    output(data, _json_flag(ctx))


@tag_.command("get")
@click.argument("tag_id")
@click.pass_context
def tag_get(ctx: click.Context, tag_id: str) -> None:
    """Get tag details."""
    data = tags.get_tag(tag_id, **_conn(ctx))
    output(data, _json_flag(ctx))


@tag_.command("create")
@click.argument("name")
@click.pass_context
def tag_create(ctx: click.Context, name: str) -> None:
    """Create a tag."""
    data = tags.create_tag(name, **_conn(ctx))
    output(data, _json_flag(ctx))


@tag_.command("update")
@click.argument("tag_id")
@click.argument("name")
@click.pass_context
def tag_update(ctx: click.Context, tag_id: str, name: str) -> None:
    """Update a tag name."""
    data = tags.update_tag(tag_id, name, **_conn(ctx))
    output(data, _json_flag(ctx))


@tag_.command("delete")
@click.argument("tag_id")
@click.pass_context
def tag_delete(ctx: click.Context, tag_id: str) -> None:
    """Delete a tag."""
    tags.delete_tag(tag_id, **_conn(ctx))
    success(f"Tag {tag_id} deleted")


# ─── Entry point ────────────────────────────────────────────────────────────

def main() -> None:
    try:
        cli(obj={})
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code
        try:
            body = exc.response.json()
            msg = body.get("message", str(body))
        except (ValueError, AttributeError):
            msg = exc.response.text or str(exc)
        error(f"{status} — {msg}")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        error("Cannot connect to n8n. Check your URL and network.")
        sys.exit(1)
    except ValueError as exc:
        error(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
