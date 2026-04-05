"""cli-anything-n8n — CLI for n8n workflow automation.

Based on n8n Public API v1.1.1 (n8n >= 1.0.0).
Verified against n8n 2.43.0.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import click
import requests

from cli_anything.n8n.core import (
    credentials,
    executions,
    expressions,
    nodes,
    project,
    scaffolds,
    tags,
    templates,
    variables,
    versions,
    workflows,
)
from cli_anything.n8n.utils.repl_skin import error, output, print_banner, success, warn


CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}
VERSION = "2.3.0"


def _safe_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'[\s/\\]+', '_', name)
    return name[:60] or "workflow"

STATUS_COLORS = {
    "success": "green", "error": "red", "running": "yellow",
    "waiting": "cyan", "new": "blue",
}

# Fields to strip when sending workflow data to n8n API
_INTERNAL_FIELDS = frozenset({"id", "createdAt", "updatedAt", "versionId", "shared"})


def _conn(ctx: click.Context) -> dict[str, str]:
    """Extract connection kwargs from Click context."""
    return {"base_url": ctx.obj["base_url"], "api_key": ctx.obj["api_key"]}


def _json_flag(ctx: click.Context) -> bool:
    return ctx.obj.get("as_json", False)


def _clean_for_api(data: dict[str, Any]) -> dict[str, Any]:
    """Remove n8n internal fields before sending to API."""
    return {k: v for k, v in data.items() if k not in _INTERNAL_FIELDS}


def _auto_snapshot(workflow_id: str, conn: dict[str, str], trigger: str) -> None:
    """Save a version snapshot before modifying a workflow."""
    try:
        wf_data = workflows.get_workflow(workflow_id, **conn)
        ver = versions.save_snapshot(workflow_id, wf_data, trigger)
        click.secho(f"  (snapshot v{ver} saved)", fg="bright_black")
    except (requests.exceptions.RequestException, OSError):
        pass  # Non-critical — don't block the operation


def _load_json_arg(value: str) -> Any:
    """Parse a JSON string or read from file if prefixed with @."""
    if value.startswith("@"):
        filepath = Path(value[1:]).resolve()
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
        from prompt_toolkit.completion import WordCompleter
        from prompt_toolkit.history import InMemoryHistory
    except ImportError:
        click.echo("prompt-toolkit is required for REPL mode. Install: pip install prompt-toolkit")
        sys.exit(1)

    base_url = ctx.obj["base_url"]
    print_banner(base_url or "(not configured)")

    # Build completer from all CLI commands
    words = ["help", "exit", "quit", "status"]
    for name, cmd in cli.commands.items():
        if getattr(cmd, "hidden", False):
            continue
        words.append(name)
        if hasattr(cmd, "commands"):
            for sub in cmd.commands:
                words.append(f"{name} {sub}")
    completer = WordCompleter(words, ignore_case=True)

    session = PromptSession(history=InMemoryHistory(), completer=completer)
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
            import shlex
            try:
                args = shlex.split(line)
            except ValueError:
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
        masked["api_key"] = "****configured****"
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


@config_.command("test")
@click.pass_context
def config_test(ctx: click.Context) -> None:
    """Test connection to your n8n instance."""
    conn = _conn(ctx)
    if not conn["base_url"]:
        error("No URL configured. Run: cli-anything-n8n config set base_url https://...")
        return
    if not conn["api_key"]:
        error("No API key configured. Run: cli-anything-n8n config set api_key YOUR_KEY")
        return
    try:
        data = workflows.list_workflows(**conn, limit=1)
        count = len(data.get("data", [])) if isinstance(data, dict) else 0
        success(f"Connected to {conn['base_url']}")
        click.echo(f"    API is responding. Found workflows.")
    except requests.exceptions.ConnectionError:
        error(f"Cannot connect to {conn['base_url']}")
    except requests.exceptions.HTTPError as exc:
        status_code = exc.response.status_code
        if status_code == 401:
            error("API key is invalid or expired.")
        elif status_code == 403:
            error("API key does not have permission.")
        else:
            error(f"API returned {status_code}")


# ─── Shell Completions ─────────────────────────────────────────────────────

@cli.command("completions")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def install_completions(shell: str) -> None:
    """Generate shell completion script (bash, zsh, fish)."""
    import subprocess
    env_var = "_CLI_ANYTHING_N8N_COMPLETE"
    shell_map = {"bash": "bash_source", "zsh": "zsh_source", "fish": "fish_source"}
    result = subprocess.run(
        ["cli-anything-n8n"],
        capture_output=True, text=True, timeout=5,
        env={**__import__("os").environ, env_var: shell_map[shell]},
    )
    if result.stdout:
        click.echo(result.stdout)
        click.echo(f"\n# To install, run:", err=True)
        if shell == "bash":
            click.echo(f'# cli-anything-n8n completions bash >> ~/.bashrc', err=True)
        elif shell == "zsh":
            click.echo(f'# cli-anything-n8n completions zsh >> ~/.zshrc', err=True)
        elif shell == "fish":
            click.echo(f'# cli-anything-n8n completions fish > ~/.config/fish/completions/cli-anything-n8n.fish', err=True)
    else:
        success(f"Shell completions for {shell} generated. Paste output into your shell config.")


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


@workflow_.command("search")
@click.argument("query")
@click.option("--active/--inactive", default=None, help="Filter by active status")
@click.pass_context
def workflow_search(ctx: click.Context, query: str, active: bool | None) -> None:
    """Search workflows by name (case-insensitive)."""
    data = workflows.list_workflows(**_conn(ctx), limit=200, active=active)
    wf_list = data.get("data", []) if isinstance(data, dict) else data
    query_lower = query.lower()
    matches = [w for w in wf_list if query_lower in w.get("name", "").lower()]
    if _json_flag(ctx):
        output({"data": matches}, True)
    elif not matches:
        warn(f"No workflows matching '{query}'")
    else:
        click.secho(f"  Found {len(matches)} workflow(s) matching '{query}':\n", fg="cyan")
        for w in matches:
            status_str = click.style("active", fg="green") if w.get("active") else click.style("inactive", fg="bright_black")
            click.echo(f"    {w.get('id', '?'):>16s}  {status_str}  {w.get('name', '?')}")


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
    """Create a workflow from JSON (inline or @file.json). Workflows are created inactive."""
    payload = _load_json_arg(json_data)
    payload.pop("active", None)  # Never auto-activate on create
    data = workflows.create_workflow(payload, **_conn(ctx))
    output(data, _json_flag(ctx))


@workflow_.command("update")
@click.argument("workflow_id")
@click.argument("json_data")
@click.pass_context
def workflow_update(ctx: click.Context, workflow_id: str, json_data: str) -> None:
    """Update a workflow. Does not change active status — use activate/deactivate."""
    _auto_snapshot(workflow_id, _conn(ctx), "update")
    payload = _load_json_arg(json_data)
    payload.pop("active", None)  # Don't change active status via update
    data = workflows.update_workflow(workflow_id, payload, **_conn(ctx))
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


@workflow_.command("export")
@click.argument("workflow_id")
@click.option("-o", "--output", "out_path", default=None, help="Output file (default: <name>.json)")
@click.pass_context
def workflow_export(ctx: click.Context, workflow_id: str, out_path: str | None) -> None:
    """Export a workflow to a JSON file."""
    data = workflows.get_workflow(workflow_id, **_conn(ctx))
    if not out_path:
        name = _safe_filename(data.get("name", workflow_id))
        out_path = f"{name}.json"
    # Remove server-specific fields for portability
    export_data = _clean_for_api(data)
    Path(out_path).write_text(json.dumps(export_data, indent=2, default=str))
    success(f"Exported to {out_path}")


@workflow_.command("import")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--name", default=None, help="Override workflow name")
@click.pass_context
def workflow_import(ctx: click.Context, file_path: str, name: str | None) -> None:
    """Import a workflow from a JSON file."""
    with open(file_path) as f:
        data = json.load(f)
    # Remove fields that would conflict on import
    for field in ("id", "createdAt", "updatedAt", "versionId", "shared"):
        data.pop(field, None)
    data["active"] = False  # Never auto-activate imported workflows
    if name:
        data["name"] = name
    result = workflows.create_workflow(data, **_conn(ctx))
    success(f"Imported as workflow {result.get('id', '?')} — {result.get('name', '?')}")
    output(result, _json_flag(ctx))


@workflow_.command("backup-all")
@click.option("-d", "--dir", "out_dir", default="n8n-backup", help="Output directory (default: n8n-backup)")
@click.option("--active-only", is_flag=True, default=False, help="Only backup active workflows")
@click.pass_context
def workflow_backup_all(ctx: click.Context, out_dir: str, active_only: bool) -> None:
    """Backup ALL workflows to a folder (one JSON per workflow)."""
    conn = _conn(ctx)
    # Paginate to get ALL workflows, not just first page
    wf_list: list[dict] = []
    cursor = None
    while True:
        data = workflows.list_workflows(**conn, limit=100, cursor=cursor, active=True if active_only else None)
        page = data.get("data", []) if isinstance(data, dict) else data
        wf_list.extend(page)
        cursor = data.get("nextCursor") if isinstance(data, dict) else None
        if not cursor or not page:
            break

    if not wf_list:
        warn("No workflows found")
        return

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    click.echo(f"  Backing up {len(wf_list)} workflow(s) to {out_dir}/\n")
    ok, fail = 0, 0
    for w in wf_list:
        wf_id = w.get("id", "unknown")
        try:
            full = workflows.get_workflow(wf_id, **conn)
            export_data = _clean_for_api(full)
            name_safe = _safe_filename(full.get("name", wf_id))
            filename = f"{wf_id}_{name_safe}.json"
            (out_path / filename).write_text(json.dumps(export_data, indent=2, default=str))
            click.secho(f"    {wf_id}  {full.get('name', '?')}", fg="green")
            ok += 1
        except Exception as exc:
            click.secho(f"    {wf_id}  FAILED — {exc}", fg="red")
            fail += 1

    # Write manifest
    manifest = {"backup_date": time.strftime("%Y-%m-%dT%H:%M:%S"), "count": ok, "failed": fail, "workflows": [w.get("id") for w in wf_list]}
    (out_path / "_manifest.json").write_text(json.dumps(manifest, indent=2))

    click.echo()
    success(f"Backed up {ok} workflows to {out_dir}/ ({fail} failed)")


@workflow_.command("restore-all")
@click.argument("backup_dir", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, default=False, help="Show what would be imported without doing it")
@click.pass_context
def workflow_restore_all(ctx: click.Context, backup_dir: str, dry_run: bool) -> None:
    """Restore workflows from a backup folder."""
    conn = _conn(ctx)
    backup_path = Path(backup_dir)
    json_files = sorted(backup_path.glob("*.json"))
    json_files = [f for f in json_files if f.name != "_manifest.json"]

    if not json_files:
        warn(f"No JSON files found in {backup_dir}/")
        return

    click.echo(f"  {'[DRY RUN] ' if dry_run else ''}Restoring {len(json_files)} workflow(s) from {backup_dir}/\n")
    ok, fail = 0, 0
    for f in json_files:
        try:
            data = json.loads(f.read_text())
            name = data.get("name", f.stem)
            if dry_run:
                click.echo(f"    Would import: {name}")
                ok += 1
                continue
            for field in ("id", "createdAt", "updatedAt", "versionId", "shared"):
                data.pop(field, None)
            data["active"] = False  # Never auto-activate restored workflows
            result = workflows.create_workflow(data, **conn)
            click.secho(f"    {result.get('id', '?')}  {name}", fg="green")
            ok += 1
        except Exception as exc:
            click.secho(f"    {f.name}  FAILED — {exc}", fg="red")
            fail += 1

    click.echo()
    if dry_run:
        success(f"Would restore {ok} workflows ({fail} would fail)")
    else:
        success(f"Restored {ok} workflows ({fail} failed)")


@workflow_.command("diff")
@click.argument("source")
@click.argument("target")
@click.pass_context
def workflow_diff(ctx: click.Context, source: str, target: str) -> None:
    """Compare two workflows. Use workflow IDs or @file.json paths.

    Examples: diff ABC123 DEF456, diff ABC123 @local.json, diff @a.json @b.json
    """
    import difflib
    conn = _conn(ctx)

    def _load(ref: str) -> dict:
        if ref.startswith("@"):
            return _load_json_arg(ref)
        return workflows.get_workflow(ref, **conn)

    def _clean(data: dict) -> dict:
        return _clean_for_api(data)

    src = _clean(_load(source))
    tgt = _clean(_load(target))

    src_lines = json.dumps(src, indent=2, sort_keys=True, default=str).splitlines(keepends=True)
    tgt_lines = json.dumps(tgt, indent=2, sort_keys=True, default=str).splitlines(keepends=True)

    src_label = source if source.startswith("@") else f"workflow:{source}"
    tgt_label = target if target.startswith("@") else f"workflow:{target}"

    diff = list(difflib.unified_diff(src_lines, tgt_lines, fromfile=src_label, tofile=tgt_label, lineterm=""))

    if not diff:
        success("Workflows are identical")
        return

    for line in diff:
        if line.startswith("+++") or line.startswith("---"):
            click.secho(line, fg="cyan", bold=True)
        elif line.startswith("+"):
            click.secho(line, fg="green")
        elif line.startswith("-"):
            click.secho(line, fg="red")
        elif line.startswith("@@"):
            click.secho(line, fg="cyan")
        else:
            click.echo(line)


@workflow_.command("bulk-activate")
@click.option("--tag", default=None, help="Activate all workflows with this tag")
@click.option("--search", default=None, help="Activate all workflows matching name")
@click.pass_context
def workflow_bulk_activate(ctx: click.Context, tag: str | None, search: str | None) -> None:
    """Activate multiple workflows by tag or name search."""
    if not tag and not search:
        error("Provide --tag or --search to select workflows")
        return
    conn = _conn(ctx)
    data = workflows.list_workflows(**conn, tags=tag, limit=200)
    wf_list = data.get("data", []) if isinstance(data, dict) else data
    if search:
        q = search.lower()
        wf_list = [w for w in wf_list if q in w.get("name", "").lower()]
    inactive = [w for w in wf_list if not w.get("active")]
    if not inactive:
        warn("No inactive workflows found matching criteria")
        return
    click.echo(f"  Activating {len(inactive)} workflow(s)...")
    ok, fail = 0, 0
    for w in inactive:
        try:
            workflows.activate_workflow(w.get("id", ""), **conn)
            click.secho(f"    {w.get('id', '?')}  {w.get('name', '?')}", fg="green")
            ok += 1
        except Exception as exc:
            click.secho(f"    {w.get('id', '?')}  {w.get('name', '?')} — {exc}", fg="red")
            fail += 1
    success(f"Activated {ok}, failed {fail}")


@workflow_.command("bulk-deactivate")
@click.option("--tag", default=None, help="Deactivate all workflows with this tag")
@click.option("--search", default=None, help="Deactivate all workflows matching name")
@click.pass_context
def workflow_bulk_deactivate(ctx: click.Context, tag: str | None, search: str | None) -> None:
    """Deactivate multiple workflows by tag or name search."""
    if not tag and not search:
        error("Provide --tag or --search to select workflows")
        return
    conn = _conn(ctx)
    data = workflows.list_workflows(**conn, tags=tag, limit=200)
    wf_list = data.get("data", []) if isinstance(data, dict) else data
    if search:
        q = search.lower()
        wf_list = [w for w in wf_list if q in w.get("name", "").lower()]
    active = [w for w in wf_list if w.get("active")]
    if not active:
        warn("No active workflows found matching criteria")
        return
    click.echo(f"  Deactivating {len(active)} workflow(s)...")
    ok, fail = 0, 0
    for w in active:
        try:
            workflows.deactivate_workflow(w.get("id", ""), **conn)
            click.secho(f"    {w['id']}  {w.get('name', '?')}", fg="bright_black")
            ok += 1
        except Exception as exc:
            click.secho(f"    {w.get('id', '?')}  {w.get('name', '?')} — {exc}", fg="red")
            fail += 1
    success(f"Deactivated {ok}, failed {fail}")


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


@execution_.command("errors")
@click.option("--workflow-id", default=None, help="Filter by workflow ID")
@click.option("--limit", default=10, type=int, help="Number of errors to show")
@click.option("--details", is_flag=True, default=False, help="Include error message details")
@click.pass_context
def execution_errors(ctx: click.Context, workflow_id: str | None, limit: int, details: bool) -> None:
    """Show recent failed executions (shortcut for list --status error)."""
    conn = _conn(ctx)
    data = executions.list_executions(**conn, status="error", workflow_id=workflow_id, limit=limit, include_data=details)
    err_list = data.get("data", []) if isinstance(data, dict) else data

    if _json_flag(ctx):
        output(data, True)
        return

    if not err_list:
        success("No errors found!")
        return

    click.secho(f"\n  {len(err_list)} recent error(s):\n", fg="red", bold=True)
    for e in err_list:
        eid = e.get("id", "?")
        wf_id = e.get("workflowId", "?")
        started = str(e.get("startedAt", ""))[:19].replace("T", " ")
        stopped = str(e.get("stoppedAt", ""))[:19].replace("T", " ")
        click.echo(f"    {click.style(eid, fg='red'):>12s}  wf:{wf_id:<16s}  {started} -> {stopped}")

        if details and isinstance(e.get("data"), dict):
            run_data = e["data"].get("resultData", {})
            error_msg = run_data.get("error", {}).get("message", "")
            if error_msg:
                click.secho(f"              {error_msg[:120]}", fg="bright_black")
    click.echo()


@execution_.command("watch")
@click.option("--workflow-id", default=None, help="Filter by workflow ID")
@click.option("--interval", default=5, type=int, help="Poll interval in seconds (default: 5)")
@click.option("--limit", default=5, type=int, help="Number of executions to show")
@click.pass_context
def execution_watch(ctx: click.Context, workflow_id: str | None, interval: int, limit: int) -> None:
    """Watch executions in real-time (poll mode). Press Ctrl+C to stop."""
    import shutil
    if interval < 1:
        error("--interval must be at least 1 second")
        return
    conn = _conn(ctx)
    click.secho(f"  Watching executions (every {interval}s). Ctrl+C to stop.\n", fg="cyan")
    seen: set[str] = set()
    try:
        while True:
            data = executions.list_executions(**conn, workflow_id=workflow_id, limit=limit)
            rows = data.get("data", []) if isinstance(data, dict) else data
            term_w = shutil.get_terminal_size().columns
            click.echo(f"\033[2J\033[H", nl=False)  # clear screen
            click.secho(f"  n8n executions — {time.strftime('%H:%M:%S')} (every {interval}s, Ctrl+C to stop)\n", fg="cyan")
            if not rows:
                click.secho("  No executions found.", fg="bright_black")
            else:
                for row in rows:
                    eid = str(row.get("id", ""))
                    status = row.get("status", "?")
                    wf_id = row.get("workflowId", "?")
                    started = str(row.get("startedAt", ""))[:19].replace("T", " ")
                    is_new = eid not in seen
                    seen.add(eid)
                    color = {"success": "green", "error": "red", "running": "yellow", "waiting": "cyan"}.get(status, "white")
                    marker = " *" if is_new else "  "
                    line = f"{marker} {eid:>8s}  {click.style(status.ljust(8), fg=color)}  wf:{wf_id:<16s}  {started}"
                    click.echo(line[:term_w])
            time.sleep(interval)
    except KeyboardInterrupt:
        click.echo("\n  Stopped.")


# ─── Status Dashboard ──────────────────────────────────────────────────────

@cli.command("status")
@click.pass_context
def status_dashboard(ctx: click.Context) -> None:
    """Show a quick overview of your n8n instance."""
    conn = _conn(ctx)
    as_json = _json_flag(ctx)

    wf_data = workflows.list_workflows(**conn, limit=200)
    wf_list = wf_data.get("data", []) if isinstance(wf_data, dict) else wf_data
    active_wfs = [w for w in wf_list if w.get("active")]
    inactive_wfs = [w for w in wf_list if not w.get("active")]

    exec_data = executions.list_executions(**conn, limit=10)
    exec_list = exec_data.get("data", []) if isinstance(exec_data, dict) else exec_data
    errors = [e for e in exec_list if e.get("status") == "error"]

    if as_json:
        output({
            "workflows": {"total": len(wf_list), "active": len(active_wfs), "inactive": len(inactive_wfs)},
            "recent_executions": len(exec_list),
            "recent_errors": len(errors),
            "last_error": errors[0] if errors else None,
        }, True)
        return

    click.echo()
    click.secho("  n8n Status Dashboard", fg="cyan", bold=True)
    click.secho("  " + "=" * 40, fg="cyan")
    click.echo()

    click.secho("  Workflows", fg="cyan", bold=True)
    click.echo(f"    Total:    {len(wf_list)}")
    click.secho(f"    Active:   {len(active_wfs)}", fg="green")
    click.echo(f"    Inactive: {len(inactive_wfs)}")
    click.echo()

    click.secho("  Recent Executions (last 10)", fg="cyan", bold=True)
    if not exec_list:
        click.secho("    No executions found.", fg="bright_black")
    else:
        for e in exec_list:
            status = e.get("status", "?")
            color = {"success": "green", "error": "red", "running": "yellow", "waiting": "cyan"}.get(status, "white")
            started = str(e.get("startedAt", ""))[:19].replace("T", " ")
            click.echo(f"    {e.get('id', '?'):>8s}  {click.style(status.ljust(8), fg=color)}  wf:{e.get('workflowId', '?'):<16s}  {started}")
    click.echo()

    if errors:
        click.secho(f"  Errors: {len(errors)} in last 10 executions", fg="red", bold=True)
        last = errors[0]
        click.echo(f"    Last error: execution {last.get('id')} (wf:{last.get('workflowId')}) at {str(last.get('startedAt', ''))[:19]}")
    else:
        click.secho("  No errors in recent executions", fg="green")
    click.echo()


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


# ─── Templates (n8n.io) ─────────────────────────────────────────────────────

@cli.group("template")
def template_() -> None:
    """Browse and deploy templates from n8n.io (2,700+ templates)."""


@template_.command("search")
@click.argument("query")
@click.option("--limit", default=10, type=int, help="Max results")
@click.pass_context
def template_search(ctx: click.Context, query: str, limit: int) -> None:
    """Search templates on n8n.io by keyword."""
    data = templates.search_templates(query, limit=limit)
    wfs = data.get("workflows", [])

    if _json_flag(ctx):
        output(data, True)
        return

    total = data.get("totalWorkflows", 0)
    click.secho(f"\n  {total} templates found for '{query}' (showing {len(wfs)}):\n", fg="cyan")
    for w in wfs:
        views = w.get("totalViews", 0)
        nodes = len(w.get("nodes", w.get("workflowInfo", {}).get("nodeCount", 0)) if isinstance(w.get("nodes"), list) else [])
        click.echo(f"    {click.style(str(w.get('id', '?')), fg='cyan'):>8s}  {w.get('name', '?')[:60]}")
        click.secho(f"             {views:,} views  by {w.get('user', {}).get('username', '?')}", fg="bright_black")
    click.echo()


@template_.command("get")
@click.argument("template_id", type=int)
@click.pass_context
def template_get(ctx: click.Context, template_id: int) -> None:
    """Get template details from n8n.io."""
    data = templates.get_template(template_id)
    wf = data.get("workflow", {})
    if _json_flag(ctx):
        output(data, True)
        return
    click.secho(f"\n  Template #{template_id}: {wf.get('name', '?')}", fg="cyan", bold=True)
    click.echo(f"  Nodes: {len(wf.get('nodes', []))}")
    click.echo(f"  Views: {wf.get('totalViews', 0):,}")
    desc = data.get("description", "")
    if desc:
        click.echo(f"  Description: {desc[:200]}")
    click.echo()


@template_.command("deploy")
@click.argument("template_id", type=int)
@click.option("--name", default=None, help="Override workflow name")
@click.pass_context
def template_deploy(ctx: click.Context, template_id: int, name: str | None) -> None:
    """Deploy a template from n8n.io directly to your n8n instance."""
    conn = _conn(ctx)
    click.echo(f"  Fetching template #{template_id} from n8n.io...")
    data = templates.get_template(template_id)
    wf_data = data.get("workflow", {}).get("workflow", data.get("workflow", {}))

    # Clean for import — never auto-activate
    for field in ("id", "createdAt", "updatedAt", "versionId", "shared"):
        wf_data.pop(field, None)
    wf_data["active"] = False
    if name:
        wf_data["name"] = name
    elif not wf_data.get("name"):
        wf_data["name"] = f"Template #{template_id}"

    result = workflows.create_workflow(wf_data, **conn)
    success(f"Deployed as workflow {result.get('id', '?')} — {result.get('name', '?')}")
    output(result, _json_flag(ctx))


# ─── Workflow Validate ──────────────────────────────────────────────────────

@workflow_.command("validate")
@click.argument("source")
@click.pass_context
def workflow_validate(ctx: click.Context, source: str) -> None:
    """Validate a workflow structure. Use workflow ID or @file.json."""
    conn = _conn(ctx)

    if source.startswith("@"):
        data = _load_json_arg(source)
    else:
        data = workflows.get_workflow(source, **conn)

    issues: list[str] = []
    warnings: list[str] = []

    # Check basic structure
    if not data.get("name"):
        issues.append("Missing workflow name")
    if not data.get("nodes"):
        issues.append("No nodes defined")
    if not isinstance(data.get("connections", {}), dict):
        issues.append("Invalid connections format (must be object)")

    nodes = data.get("nodes", [])
    node_names = {n.get("name") for n in nodes}

    # Check each node
    trigger_count = 0
    for node in nodes:
        if not node.get("type"):
            issues.append(f"Node '{node.get('name', '?')}' has no type")
        if not node.get("name"):
            issues.append(f"Node of type '{node.get('type', '?')}' has no name")
        node_type_lower = node.get("type", "").lower()
        if "trigger" in node_type_lower or "webhook" in node_type_lower:
            trigger_count += 1

    if trigger_count == 0:
        warnings.append("No trigger node found — workflow cannot be activated")
    if trigger_count > 1:
        warnings.append(f"Multiple trigger nodes ({trigger_count}) — only one should be active")

    # Check connections reference existing nodes
    for source_node, conns in data.get("connections", {}).items():
        if source_node not in node_names:
            issues.append(f"Connection from non-existent node: '{source_node}'")
        if isinstance(conns, dict):
            for conn_type, outputs in conns.items():
                if isinstance(outputs, list):
                    for output_list in outputs:
                        if isinstance(output_list, list):
                            for target in output_list:
                                target_name = target.get("node", "")
                                if target_name and target_name not in node_names:
                                    issues.append(f"Connection to non-existent node: '{target_name}'")

    # Check for duplicate node names
    seen_names: set[str] = set()
    for node in nodes:
        name = node.get("name", "")
        if name in seen_names:
            issues.append(f"Duplicate node name: '{name}'")
        seen_names.add(name)

    if _json_flag(ctx):
        output({"valid": len(issues) == 0, "issues": issues, "warnings": warnings}, True)
        return

    if issues:
        click.secho(f"\n  INVALID — {len(issues)} issue(s):\n", fg="red", bold=True)
        for i in issues:
            click.secho(f"    {i}", fg="red")
    else:
        click.secho(f"\n  VALID", fg="green", bold=True)

    if warnings:
        click.secho(f"\n  {len(warnings)} warning(s):", fg="yellow")
        for w in warnings:
            click.secho(f"    {w}", fg="yellow")

    if not issues and not warnings:
        click.echo(f"  {len(nodes)} nodes, {trigger_count} trigger(s)")
    click.echo()


# ─── Workflow Autofix ───────────────────────────────────────────────────────

@workflow_.command("autofix")
@click.argument("source")
@click.option("--apply", is_flag=True, default=False, help="Apply fixes (default: preview only)")
@click.option("--save", "save_path", default=None, help="Save fixed workflow to file instead of updating n8n")
@click.pass_context
def workflow_autofix(ctx: click.Context, source: str, apply: bool, save_path: str | None) -> None:
    """Auto-fix common workflow issues. Preview by default, --apply to save.

    Fixes: expression format, webhook paths, broken connections, duplicate names,
    connection types, unused error outputs.
    """
    from cli_anything.n8n.core.fixers import autofix

    conn = _conn(ctx)
    if source.startswith("@"):
        wf_data = _load_json_arg(source)
        wf_id = None
    else:
        wf_data = workflows.get_workflow(source, **conn)
        wf_id = source

    import copy
    wf_copy = copy.deepcopy(wf_data)
    fixed_wf, fixes = autofix(wf_copy, apply=True)

    if _json_flag(ctx):
        output({"fixes": [{"type": f.fix_type, "description": f.description, "confidence": f.confidence, "node": f.node_name} for f in fixes], "total": len(fixes), "applied": apply or bool(save_path)}, True)
        return

    if not fixes:
        success("No issues found!")
        return

    click.secho(f"\n  Found {len(fixes)} issue(s):\n", fg="yellow", bold=True)
    for f in fixes:
        color = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "bright_black"}.get(f.confidence, "white")
        node_str = f" [{f.node_name}]" if f.node_name else ""
        click.echo(f"    {click.style(f.confidence, fg=color):>8s}  {f.fix_type:30s}{node_str}")
        click.secho(f"             {f.description}", fg="bright_black")

    if save_path:
        Path(save_path).write_text(json.dumps(fixed_wf, indent=2, default=str))
        success(f"Fixed workflow saved to {save_path}")
    elif apply and wf_id:
        _auto_snapshot(wf_id, conn, "autofix")
        update_data = _clean_for_api(fixed_wf)
        workflows.update_workflow(wf_id, update_data, **conn)
        success(f"Applied {len(fixes)} fix(es) to workflow {wf_id}")
    elif apply and not wf_id:
        error("Cannot apply fixes to a file source. Use --save instead.")
    else:
        warn("Preview only. Use --apply to fix in n8n, or --save to save to file.")
    click.echo()


# ─── Workflow Patch (incremental updates) ───────────────────────────────────

@workflow_.command("patch")
@click.argument("workflow_id")
@click.option("--rename", default=None, help="Rename the workflow")
@click.option("--enable-node", default=None, help="Enable a disabled node by name")
@click.option("--disable-node", default=None, help="Disable a node by name")
@click.option("--remove-node", default=None, help="Remove a node by name (and its connections)")
@click.option("--connect", nargs=2, default=None, help="Connect two nodes: --connect SOURCE TARGET")
@click.option("--disconnect", nargs=2, default=None, help="Disconnect two nodes: --disconnect SOURCE TARGET")
@click.pass_context
def workflow_patch(ctx: click.Context, workflow_id: str, rename: str | None, enable_node: str | None, disable_node: str | None, remove_node: str | None, connect: tuple[str, str] | None, disconnect: tuple[str, str] | None) -> None:
    """Apply incremental changes to a workflow without replacing it entirely."""
    conn = _conn(ctx)
    wf = workflows.get_workflow(workflow_id, **conn)
    nodes = wf.get("nodes", [])
    connections = wf.get("connections", {})
    changed = False

    if rename:
        wf["name"] = rename
        changed = True
        success(f"Renamed to '{rename}'")

    if enable_node:
        for n in nodes:
            if n.get("name") == enable_node:
                n["disabled"] = False
                changed = True
                success(f"Enabled node '{enable_node}'")
                break
        else:
            error(f"Node '{enable_node}' not found")
            return

    if disable_node:
        for n in nodes:
            if n.get("name") == disable_node:
                n["disabled"] = True
                changed = True
                success(f"Disabled node '{disable_node}'")
                break
        else:
            error(f"Node '{disable_node}' not found")
            return

    if remove_node:
        original_len = len(nodes)
        wf["nodes"] = [n for n in nodes if n.get("name") != remove_node]
        if len(wf["nodes"]) == original_len:
            error(f"Node '{remove_node}' not found")
            return
        # Clean connections
        connections.pop(remove_node, None)
        for src_conns in connections.values():
            if isinstance(src_conns, dict):
                for outputs in src_conns.values():
                    if isinstance(outputs, list):
                        for output_list in outputs:
                            if isinstance(output_list, list):
                                output_list[:] = [t for t in output_list if isinstance(t, dict) and t.get("node") != remove_node]
        changed = True
        success(f"Removed node '{remove_node}' and its connections")

    if connect:
        src, tgt = connect
        node_names = {n.get("name") for n in wf["nodes"]}
        if src not in node_names:
            error(f"Source node '{src}' not found")
            return
        if tgt not in node_names:
            error(f"Target node '{tgt}' not found")
            return
        src_conns = connections.setdefault(src, {})
        main_outputs = src_conns.setdefault("main", [[]])
        if not main_outputs or not isinstance(main_outputs[0], list):
            main_outputs.insert(0, [])
        main_outputs[0].append({"node": tgt, "type": "main", "index": 0})
        changed = True
        success(f"Connected '{src}' -> '{tgt}'")

    if disconnect:
        src, tgt = disconnect
        if src in connections and isinstance(connections[src], dict):
            for outputs in connections[src].values():
                if isinstance(outputs, list):
                    for output_list in outputs:
                        if isinstance(output_list, list):
                            output_list[:] = [t for t in output_list if isinstance(t, dict) and t.get("node") != tgt]
            changed = True
            success(f"Disconnected '{src}' -> '{tgt}'")
        else:
            error(f"No connections from '{src}'")
            return

    if not changed:
        error("No operations specified. Use --rename, --enable-node, --disable-node, --remove-node, --connect, or --disconnect")
        return

    _auto_snapshot(workflow_id, conn, "patch")
    update_data = _clean_for_api(wf)
    result = workflows.update_workflow(workflow_id, update_data, **conn)
    output(result, _json_flag(ctx))


# ─── Health Check ───────────────────────────────────────────────────────────

@cli.command("health")
@click.option("--diagnostic", is_flag=True, default=False, help="Show detailed diagnostic info")
@click.pass_context
def health_check(ctx: click.Context, diagnostic: bool) -> None:
    """Check n8n instance health and connectivity."""
    conn = _conn(ctx)
    base_url = conn["base_url"]

    if not base_url:
        error("No URL configured.")
        return

    results: dict[str, Any] = {"url": base_url, "status": "unknown"}

    # Test connectivity and measure response time
    start = time.time()
    try:
        wf_data = workflows.list_workflows(**conn, limit=1)
        elapsed = round((time.time() - start) * 1000)
        results["status"] = "connected"
        results["response_ms"] = elapsed

        wf_list = wf_data.get("data", []) if isinstance(wf_data, dict) else wf_data
        results["has_workflows"] = len(wf_list) > 0
    except requests.exceptions.ConnectionError:
        results["status"] = "unreachable"
    except requests.exceptions.HTTPError as exc:
        results["status"] = f"error_{exc.response.status_code}"

    # Try to get n8n version via healthz endpoint
    try:
        resp = requests.get(f"{base_url}/healthz", timeout=5)
        if resp.ok:
            health = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            results["n8n_status"] = health.get("status", "ok")
    except (requests.exceptions.RequestException, ValueError):
        pass  # healthz is optional

    if diagnostic:
        import os
        results["diagnostic"] = {
            "base_url": base_url,
            "api_key_set": bool(conn.get("api_key")),
            "timeout": os.environ.get("N8N_TIMEOUT", "30"),
            "python": sys.version.split()[0],
            "cli_version": VERSION,
        }

    if _json_flag(ctx):
        output(results, True)
        return

    click.echo()
    click.secho("  n8n Health Check", fg="cyan", bold=True)
    click.secho("  " + "=" * 40, fg="cyan")
    click.echo()

    click.echo(f"  Instance:  {base_url}")

    if results["status"] == "connected":
        click.secho(f"  Status:    Connected", fg="green")
        click.echo(f"  Response:  {results.get('response_ms', '?')}ms")
    elif results["status"] == "unreachable":
        click.secho(f"  Status:    Unreachable", fg="red")
    else:
        click.secho(f"  Status:    {results['status']}", fg="red")

    if diagnostic and "diagnostic" in results:
        diag = results["diagnostic"]
        click.echo()
        click.secho("  Diagnostic", fg="cyan", bold=True)
        click.echo(f"  API Key:   {'configured' if diag['api_key_set'] else 'NOT SET'}")
        click.echo(f"  Timeout:   {diag['timeout']}s")
        click.echo(f"  Python:    {diag['python']}")
        click.echo(f"  CLI:       v{diag['cli_version']}")

    click.echo()


# ─── Workflow Versions ──────────────────────────────────────────────────────

@workflow_.group("versions")
def workflow_versions_() -> None:
    """Version history and rollback (local snapshots)."""


@workflow_versions_.command("list")
@click.argument("workflow_id")
@click.option("--limit", default=20, type=int)
@click.pass_context
def versions_list(ctx: click.Context, workflow_id: str, limit: int) -> None:
    """List stored versions for a workflow."""
    vers = versions.list_versions(workflow_id, limit=limit)
    if _json_flag(ctx):
        output(vers, True)
        return
    if not vers:
        warn(f"No versions stored for workflow {workflow_id}")
        click.echo("  Versions are saved automatically when you use: update, patch, autofix --apply")
        return
    click.secho(f"\n  {len(vers)} version(s) for workflow {workflow_id}:\n", fg="cyan")
    for v in vers:
        click.echo(f"    v{v['version_number']:>3d}  {v['created_at']}  {click.style(v['trigger'], fg='cyan'):>12s}  {v['workflow_name']}")
    click.echo()


@workflow_versions_.command("rollback")
@click.argument("workflow_id")
@click.option("--version", "ver_num", type=int, default=None, help="Version number to rollback to (default: previous)")
@click.pass_context
def versions_rollback(ctx: click.Context, workflow_id: str, ver_num: int | None) -> None:
    """Rollback a workflow to a previous version."""
    conn = _conn(ctx)

    if ver_num is None:
        vers = versions.list_versions(workflow_id, limit=1)
        if not vers:
            error(f"No versions found for workflow {workflow_id}")
            return
        ver_num = vers[0]["version_number"]

    snapshot = versions.get_snapshot(workflow_id, ver_num)
    if not snapshot:
        error(f"Version {ver_num} not found for workflow {workflow_id}")
        return

    # Save current state before rollback
    _auto_snapshot(workflow_id, conn, "pre-rollback")

    # Apply the rollback — deactivate first, then update
    try:
        workflows.deactivate_workflow(workflow_id, **conn)
    except Exception:
        pass  # May already be inactive
    update_data = _clean_for_api(snapshot)
    update_data.pop("active", None)
    workflows.update_workflow(workflow_id, update_data, **conn)
    success(f"Rolled back workflow {workflow_id} to version {ver_num} (deactivated — use activate to enable)")


@workflow_versions_.command("show")
@click.argument("workflow_id")
@click.argument("version_number", type=int)
@click.pass_context
def versions_show(ctx: click.Context, workflow_id: str, version_number: int) -> None:
    """Show a specific version's snapshot."""
    snapshot = versions.get_snapshot(workflow_id, version_number)
    if not snapshot:
        error(f"Version {version_number} not found")
        return
    output(snapshot, _json_flag(ctx))


@workflow_versions_.command("diff")
@click.argument("workflow_id")
@click.argument("version_a", type=int)
@click.argument("version_b", type=int)
@click.pass_context
def versions_diff(ctx: click.Context, workflow_id: str, version_a: int, version_b: int) -> None:
    """Compare two versions of a workflow."""
    if version_a == version_b:
        warn(f"Both versions are the same ({version_a}). Nothing to diff.")
        return
    import difflib
    snap_a = versions.get_snapshot(workflow_id, version_a)
    snap_b = versions.get_snapshot(workflow_id, version_b)
    if not snap_a:
        error(f"Version {version_a} not found")
        return
    if not snap_b:
        error(f"Version {version_b} not found")
        return

    def _clean(d: dict) -> str:
        clean = {k: v for k, v in d.items() if k not in ("id", "createdAt", "updatedAt", "versionId", "shared")}
        return json.dumps(clean, indent=2, sort_keys=True, default=str)

    lines_a = _clean(snap_a).splitlines(keepends=True)
    lines_b = _clean(snap_b).splitlines(keepends=True)
    diff = difflib.unified_diff(lines_a, lines_b, fromfile=f"v{version_a}", tofile=f"v{version_b}", lineterm="")

    any_diff = False
    for line in diff:
        any_diff = True
        if line.startswith("+++") or line.startswith("---"):
            click.secho(line, fg="cyan", bold=True)
        elif line.startswith("+"):
            click.secho(line, fg="green")
        elif line.startswith("-"):
            click.secho(line, fg="red")
        elif line.startswith("@@"):
            click.secho(line, fg="cyan")
        else:
            click.echo(line)

    if not any_diff:
        success("Versions are identical")


@workflow_versions_.command("prune")
@click.argument("workflow_id")
@click.option("--keep", default=10, type=int, help="Number of recent versions to keep")
def versions_prune(workflow_id: str, keep: int) -> None:
    """Delete old versions, keeping the N most recent."""
    deleted = versions.prune_versions(workflow_id, keep=keep)
    success(f"Pruned {deleted} old version(s), kept {keep} most recent")


@workflow_versions_.command("stats")
@click.pass_context
def versions_stats(ctx: click.Context) -> None:
    """Show version storage statistics."""
    st = versions.stats()
    if _json_flag(ctx):
        output(st, True)
        return
    click.echo(f"\n  Versions DB: {st['db_path']}")
    click.echo(f"  Workflows tracked: {st['workflows_tracked']}")
    click.echo(f"  Total versions: {st['total_versions']}")
    size_kb = st['db_size_bytes'] / 1024
    click.echo(f"  DB size: {size_kb:.1f} KB")
    click.echo()


# ─── Workflow Test (webhook trigger) ────────────────────────────────────────

@workflow_.command("test")
@click.argument("workflow_id")
@click.option("--data", "test_data", default=None, help="JSON data to send (inline or @file.json)")
@click.pass_context
def workflow_test(ctx: click.Context, workflow_id: str, test_data: str | None) -> None:
    """Test a workflow by triggering its webhook (workflow must be active with a webhook trigger)."""
    conn = _conn(ctx)
    wf = workflows.get_workflow(workflow_id, **conn)

    # Find webhook trigger node
    webhook_node = None
    for node in wf.get("nodes", []):
        node_type = node.get("type", "").lower()
        if "webhook" in node_type:
            webhook_node = node
            break

    if not webhook_node:
        error("No webhook trigger found in this workflow. Only webhook-triggered workflows can be tested via CLI.")
        return

    if not wf.get("active"):
        error(f"Workflow is not active. Run: cli-anything-n8n workflow activate {workflow_id}")
        return

    # Build webhook URL (allow : for path params like /:id, strip only dangerous chars)
    webhook_path = webhook_node.get("parameters", {}).get("path", "")
    if not webhook_path:
        webhook_id = webhook_node.get("webhookId", "")
        webhook_path = webhook_id or workflow_id
    webhook_path = re.sub(r'[^a-zA-Z0-9_\-/:.]', '', webhook_path).strip("/")

    base = conn["base_url"].rstrip("/")
    webhook_url = f"{base}/webhook/{webhook_path}"

    # Use the HTTP method configured on the webhook node (default POST)
    http_method = webhook_node.get("parameters", {}).get("httpMethod", "POST").upper()
    payload = _load_json_arg(test_data) if test_data else {}

    click.echo(f"  Triggering webhook ({http_method}): {webhook_url}")
    resp = requests.request(http_method, webhook_url, json=payload if http_method in ("POST", "PUT", "PATCH") else None, params=payload if http_method == "GET" else None, timeout=30)

    if _json_flag(ctx):
        try:
            output(resp.json(), True)
        except (ValueError, AttributeError):
            output({"status": resp.status_code, "body": resp.text}, True)
        return

    if resp.ok:
        success(f"Webhook responded {resp.status_code}")
        try:
            output(resp.json(), False)
        except (ValueError, AttributeError):
            click.echo(f"  Response: {resp.text[:200]}")
    else:
        error(f"Webhook returned {resp.status_code}")


# ─── Nodes (npm registry) ───────────────────────────────────────────────────

@cli.group("node")
def node_() -> None:
    """Search and explore n8n community nodes (via npm)."""


@node_.command("search")
@click.argument("query")
@click.option("--limit", default=15, type=int, help="Max results")
@click.pass_context
def node_search(ctx: click.Context, query: str, limit: int) -> None:
    """Search n8n community nodes on npm (26,000+ packages)."""
    data = nodes.search_nodes(query, limit=limit)

    if _json_flag(ctx):
        output(data, True)
        return

    pkgs = data.get("packages", [])
    if not pkgs:
        warn(f"No node packages found for '{query}'")
        return

    click.secho(f"\n  {data.get('total', '?'):,} packages found for '{query}' (showing {len(pkgs)}):\n", fg="cyan")
    for p in pkgs:
        click.echo(f"    {click.style(p.get('name', '?'), fg='cyan')}")
        click.secho(f"      v{p.get('version', '?')}  by {p.get('author', '?')}  —  {p.get('description', '')}", fg="bright_black")
    click.echo(f"\n  Use: cli-anything-n8n node info <package-name> for details")
    click.echo()


@node_.command("info")
@click.argument("package_name")
@click.pass_context
def node_info(ctx: click.Context, package_name: str) -> None:
    """Get detailed info about an n8n node package from npm."""
    data = nodes.get_node_info(package_name)

    if _json_flag(ctx):
        output(data, True)
        return

    click.secho(f"\n  {data.get('name', '?')} v{data.get('version', '?')}", fg="cyan", bold=True)
    click.echo(f"  {data.get('description', '')}")
    click.echo(f"  Author: {data.get('author', '?')}")
    click.echo(f"  License: {data.get('license', '?')}")
    if data.get("homepage"):
        click.echo(f"  Homepage: {data.get('homepage', '')}")
    click.echo(f"  npm: {data.get('npm_url', '')}")

    if data.get("n8n_nodes"):
        click.secho(f"\n  Nodes provided ({len(data.get('n8n_nodes', []))}):", fg="cyan")
        for n in data["n8n_nodes"]:
            click.echo(f"    - {n}")

    if data.get("n8n_credentials"):
        click.secho(f"\n  Credentials:", fg="cyan")
        for c in data["n8n_credentials"]:
            click.echo(f"    - {c}")

    click.secho(f"\n  Install:", fg="green")
    click.echo(f"    {data.get('install_cmd', 'N/A')}")
    click.echo()


# ─── Scaffold ───────────────────────────────────────────────────────────────

@workflow_.command("scaffold")
@click.argument("pattern", type=click.Choice(["webhook", "api", "database", "ai-agent", "scheduled"]))
@click.option("--name", default=None, help="Custom workflow name")
@click.option("--deploy", is_flag=True, default=False, help="Deploy directly to n8n")
@click.option("-o", "--output", "out_path", default=None, help="Save to file")
@click.pass_context
def workflow_scaffold(ctx: click.Context, pattern: str, name: str | None, deploy: bool, out_path: str | None) -> None:
    """Generate a workflow from a proven pattern.

    Patterns: webhook, api, database, ai-agent, scheduled.
    """
    wf = scaffolds.get_scaffold(pattern, name=name)

    if _json_flag(ctx) and not deploy and not out_path:
        output(wf, True)
        return

    if deploy:
        result = workflows.create_workflow(wf, **_conn(ctx))
        success(f"Deployed '{wf['name']}' as workflow {result.get('id', '?')}")
        output(result, _json_flag(ctx))
    elif out_path:
        Path(out_path).write_text(json.dumps(wf, indent=2, default=str))
        success(f"Saved scaffold to {out_path}")
    else:
        click.secho(f"\n  Pattern: {pattern}", fg="cyan", bold=True)
        click.echo(f"  Name: {wf['name']}")
        click.echo(f"  Nodes: {len(wf['nodes'])}")
        for n in wf["nodes"]:
            click.echo(f"    - {n['name']} ({n['type']})")
        click.echo(f"\n  Use --deploy to create in n8n, --output to save to file, or --json to see full JSON")
        click.echo()


@workflow_.command("patterns")
@click.pass_context
def workflow_patterns(ctx: click.Context) -> None:
    """List available scaffold patterns."""
    patterns = scaffolds.list_patterns()
    if _json_flag(ctx):
        output(patterns, True)
        return
    click.secho("\n  Available workflow patterns:\n", fg="cyan", bold=True)
    for p in patterns:
        click.echo(f"    {click.style(p.get('name', '?'), fg='cyan'):>20s}  {p.get('description', '')}")
    click.echo(f"\n  Usage: cli-anything-n8n workflow scaffold <pattern> [--deploy]")
    click.echo()


# ─── Expression Validator ───────────────────────────────────────────────────

@cli.command("expression")
@click.argument("expr")
@click.pass_context
def expression_validate(ctx: click.Context, expr: str) -> None:
    """Validate an n8n expression (e.g., '={{$json.name}}')."""
    result = expressions.validate_expression(expr)

    if _json_flag(ctx):
        output({"valid": result.valid, "expression": result.expression, "issues": result.issues, "warnings": result.warnings}, True)
        return

    if result.valid and not result.warnings:
        success(f"Expression is valid: {expr}")
        return

    if result.issues:
        click.secho(f"\n  INVALID expression:\n", fg="red", bold=True)
        for issue in result.issues:
            click.secho(f"    {issue}", fg="red")

    if result.warnings:
        click.secho(f"\n  Warnings:", fg="yellow")
        for w in result.warnings:
            click.secho(f"    {w}", fg="yellow")

    if result.valid:
        success("Expression is syntactically valid (with warnings)")
    click.echo()


# ─── Entry point ────────────────────────────────────────────────────────────

def main() -> None:
    try:
        cli(obj={})
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code
        try:
            body = exc.response.json()
            msg = str(body.get("message", "Request failed"))[:200]
        except (ValueError, AttributeError):
            msg = "Request failed"
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
