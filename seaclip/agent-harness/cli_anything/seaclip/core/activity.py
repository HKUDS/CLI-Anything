"""Activity feed commands for SeaClip CLI."""

import json as json_mod

import click

from ..utils.seaclip_backend import SeaClipBackend


@click.group("activity")
def activity_group():
    """View the activity feed."""


@activity_group.command("list")
@click.option("--limit", default=20, type=int, help="Number of activity items to fetch")
@click.pass_context
def activity_list(ctx, limit):
    """List recent activity."""
    backend: SeaClipBackend = ctx.obj["backend"]
    skin = ctx.obj.get("skin")
    as_json = ctx.obj.get("json", False)

    try:
        activities = backend.list_activity(limit=limit)
    except Exception as e:
        if as_json:
            click.echo(json_mod.dumps({"error": str(e)}))
        elif skin:
            skin.error(f"Failed to list activity: {e}")
        raise SystemExit(1)

    if as_json:
        click.echo(json_mod.dumps(activities, indent=2))
        return

    if skin:
        if not activities:
            skin.info("No activity found.")
            return
        headers = ["Time", "Type", "Detail"]
        rows = []
        for a in activities:
            rows.append([
                str(a.get("timestamp", ""))[:19],
                str(a.get("type", "")),
                str(a.get("detail", a.get("message", "")))[:50],
            ])
        skin.table(headers, rows)
