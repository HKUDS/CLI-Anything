"""Scheduler commands for SeaClip CLI."""

import json as json_mod

import click

from ..utils.seaclip_backend import SeaClipBackend


@click.group("scheduler")
def scheduler_group():
    """Manage schedule configurations."""


@scheduler_group.command("list")
@click.pass_context
def scheduler_list(ctx):
    """List all schedule configurations."""
    backend: SeaClipBackend = ctx.obj["backend"]
    skin = ctx.obj.get("skin")
    as_json = ctx.obj.get("json", False)

    try:
        schedules = backend.list_schedules()
    except Exception as e:
        if as_json:
            click.echo(json_mod.dumps({"error": str(e)}))
        elif skin:
            skin.error(f"Failed to list schedules: {e}")
        raise SystemExit(1)

    if as_json:
        click.echo(json_mod.dumps(schedules, indent=2))
        return

    if skin:
        if not schedules:
            skin.info("No schedules configured.")
            return
        headers = ["ID", "Name", "Cron", "Enabled"]
        rows = []
        for s in schedules:
            rows.append([
                str(s.get("id", ""))[:8],
                str(s.get("name", "")),
                str(s.get("cron", "")),
                str(s.get("enabled", "")),
            ])
        skin.table(headers, rows)


@scheduler_group.command("add")
@click.option("--name", required=True, help="Schedule name")
@click.option("--cron", required=True, help="Cron expression")
@click.option("--repo", default=None, help="Repository URL")
@click.pass_context
def scheduler_add(ctx, name, cron, repo):
    """Add a new schedule configuration."""
    backend: SeaClipBackend = ctx.obj["backend"]
    skin = ctx.obj.get("skin")
    as_json = ctx.obj.get("json", False)

    config = {"name": name, "cron": cron}
    if repo:
        config["repo"] = repo

    try:
        result = backend.add_schedule(config)
    except Exception as e:
        if as_json:
            click.echo(json_mod.dumps({"error": str(e)}))
        elif skin:
            skin.error(f"Failed to add schedule: {e}")
        raise SystemExit(1)

    if as_json:
        click.echo(json_mod.dumps(result, indent=2))
    elif skin:
        skin.success(f"Schedule '{name}' added")


@scheduler_group.command("sync")
@click.argument("schedule_id")
@click.pass_context
def scheduler_sync(ctx, schedule_id):
    """Trigger a manual sync for a schedule."""
    backend: SeaClipBackend = ctx.obj["backend"]
    skin = ctx.obj.get("skin")
    as_json = ctx.obj.get("json", False)

    try:
        result = backend.sync_schedule(schedule_id)
    except Exception as e:
        if as_json:
            click.echo(json_mod.dumps({"error": str(e)}))
        elif skin:
            skin.error(f"Failed to sync schedule: {e}")
        raise SystemExit(1)

    if as_json:
        click.echo(json_mod.dumps(result, indent=2))
    elif skin:
        skin.success(f"Schedule {schedule_id[:8]} sync triggered")
