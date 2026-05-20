"""Snapshot commands -- list, take.

Wraps `tigris snapshots list/take`. Snapshots are point-in-time, read-only
copies of a bucket's state — one of Tigris's agent-storage primitives that
generic S3-compatible providers don't ship.
"""

import json as json_mod
import click

from ..utils.tigris_backend import TigrisBackend, TigrisCliError


@click.group("snapshot")
@click.pass_context
def snapshot_group(ctx):
    """Manage bucket snapshots (wraps `tigris snapshots`)."""
    pass


@snapshot_group.command("list")
@click.argument("bucket")
@click.pass_context
def list_snapshots(ctx, bucket):
    """List snapshots for a bucket."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        snaps = backend.list_snapshots(bucket)
        if use_json:
            click.echo(json_mod.dumps(snaps, indent=2))
        else:
            if not snaps:
                skin.info(f"No snapshots found for '{bucket}'.")
                return
            if isinstance(snaps, list):
                headers = ["Name / ID", "Created"]
                rows = []
                for s in snaps:
                    if not isinstance(s, dict):
                        rows.append([str(s), ""])
                        continue
                    rows.append([
                        str(s.get("name") or s.get("id") or "?"),
                        str(s.get("created") or s.get("createdAt") or ""),
                    ])
                skin.table(headers, rows)
            else:
                click.echo(snaps)
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to list snapshots: {e}")
        raise SystemExit(1)


@snapshot_group.command("take")
@click.argument("bucket")
@click.option("--name", default=None, help="Optional snapshot label/name")
@click.pass_context
def take_snapshot(ctx, bucket, name):
    """Take a point-in-time snapshot of a bucket."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        result = backend.take_snapshot(bucket, name=name)
        if use_json:
            click.echo(json_mod.dumps(result or {"bucket": bucket, "status": "snapshot_taken"}, indent=2))
        else:
            skin.success(f"Snapshot taken for '{bucket}'" + (f" ({name})" if name else ""))
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to take snapshot: {e}")
        raise SystemExit(1)


def _emit_error(use_json: bool, skin, message: str) -> None:
    if use_json:
        click.echo(json_mod.dumps({"error": message}, indent=2))
    elif skin:
        skin.error(message)
    else:
        click.echo(message, err=True)
