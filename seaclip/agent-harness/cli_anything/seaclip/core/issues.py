"""Issue commands for SeaClip CLI."""

import json as json_mod

import click

from ..utils.seaclip_backend import SeaClipBackend


@click.group("issue")
def issue_group():
    """Manage SeaClip issues."""


@issue_group.command("list")
@click.option("--status", default=None, help="Filter by status (backlog, todo, in_progress, done)")
@click.option("--priority", default=None, help="Filter by priority (low, medium, high, critical)")
@click.option("--search", default=None, help="Search issues by keyword")
@click.option("--limit", default=None, type=int, help="Limit number of results")
@click.pass_context
def issue_list(ctx, status, priority, search, limit):
    """List issues from the board."""
    backend: SeaClipBackend = ctx.obj["backend"]
    skin = ctx.obj.get("skin")
    as_json = ctx.obj.get("json", False)

    try:
        issues = backend.list_issues(status=status, priority=priority, search=search, limit=limit)
    except Exception as e:
        if as_json:
            click.echo(json_mod.dumps({"error": str(e)}))
        elif skin:
            skin.error(f"Failed to list issues: {e}")
        raise SystemExit(1)

    if as_json:
        click.echo(json_mod.dumps(issues, indent=2))
        return

    if skin:
        if not issues:
            skin.info("No issues found.")
            return
        headers = ["ID", "Title", "Status", "Priority"]
        rows = []
        for i in issues:
            rows.append([
                str(i.get("id", ""))[:8],
                str(i.get("title", ""))[:40],
                str(i.get("status", "")),
                str(i.get("priority", "")),
            ])
        skin.table(headers, rows)


@issue_group.command("create")
@click.option("--title", required=True, help="Issue title")
@click.option("--description", default="", help="Issue description")
@click.option("--priority", default="medium", help="Priority (low, medium, high, critical)")
@click.pass_context
def issue_create(ctx, title, description, priority):
    """Create a new issue."""
    backend: SeaClipBackend = ctx.obj["backend"]
    skin = ctx.obj.get("skin")
    as_json = ctx.obj.get("json", False)

    try:
        result = backend.create_issue(title=title, description=description, priority=priority)
    except Exception as e:
        if as_json:
            click.echo(json_mod.dumps({"error": str(e)}))
        elif skin:
            skin.error(f"Failed to create issue: {e}")
        raise SystemExit(1)

    if as_json:
        click.echo(json_mod.dumps(result, indent=2))
    elif skin:
        skin.success(f"Issue created: {result.get('id', 'unknown')}")


@issue_group.command("move")
@click.argument("issue_id")
@click.option("--column", required=True, help="Target column")
@click.pass_context
def issue_move(ctx, issue_id, column):
    """Move an issue to a different column."""
    backend: SeaClipBackend = ctx.obj["backend"]
    skin = ctx.obj.get("skin")
    as_json = ctx.obj.get("json", False)

    try:
        result = backend.move_issue(issue_id, column)
    except Exception as e:
        if as_json:
            click.echo(json_mod.dumps({"error": str(e)}))
        elif skin:
            skin.error(f"Failed to move issue: {e}")
        raise SystemExit(1)

    if as_json:
        click.echo(json_mod.dumps(result, indent=2))
    elif skin:
        skin.success(f"Issue {issue_id[:8]} moved to {column}")


@issue_group.command("status")
@click.argument("issue_id")
@click.option("--set", "new_status", required=True, help="New status value")
@click.pass_context
def issue_status(ctx, issue_id, new_status):
    """Update issue status."""
    backend: SeaClipBackend = ctx.obj["backend"]
    skin = ctx.obj.get("skin")
    as_json = ctx.obj.get("json", False)

    try:
        result = backend.update_issue_status(issue_id, new_status)
    except Exception as e:
        if as_json:
            click.echo(json_mod.dumps({"error": str(e)}))
        elif skin:
            skin.error(f"Failed to update status: {e}")
        raise SystemExit(1)

    if as_json:
        click.echo(json_mod.dumps(result, indent=2))
    elif skin:
        skin.success(f"Issue {issue_id[:8]} status set to {new_status}")


@issue_group.command("delete")
@click.argument("issue_id")
@click.pass_context
def issue_delete(ctx, issue_id):
    """Delete an issue."""
    backend: SeaClipBackend = ctx.obj["backend"]
    skin = ctx.obj.get("skin")
    as_json = ctx.obj.get("json", False)

    try:
        result = backend.delete_issue(issue_id)
    except Exception as e:
        if as_json:
            click.echo(json_mod.dumps({"error": str(e)}))
        elif skin:
            skin.error(f"Failed to delete issue: {e}")
        raise SystemExit(1)

    if as_json:
        click.echo(json_mod.dumps(result, indent=2))
    elif skin:
        skin.success(f"Issue {issue_id[:8]} deleted")
