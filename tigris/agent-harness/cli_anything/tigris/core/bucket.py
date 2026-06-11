"""Bucket commands -- list, create, delete, info."""

import json as json_mod
import click

from ..utils.tigris_backend import TigrisBackend, TigrisCliError


@click.group("bucket")
@click.pass_context
def bucket_group(ctx):
    """Manage Tigris buckets (wraps `tigris buckets`)."""
    pass


@bucket_group.command("list")
@click.pass_context
def list_buckets(ctx):
    """List all buckets in the current organization."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        buckets = backend.list_buckets()
        if use_json:
            click.echo(json_mod.dumps(buckets, indent=2))
        else:
            if not buckets:
                skin.info("No buckets found.")
                return
            if isinstance(buckets, list):
                # Normalize to a couple of expected fields if present.
                rows = []
                headers = ["Name", "Created"]
                for b in buckets:
                    name = b.get("name") or b.get("Name") or "?"
                    created = b.get("created") or b.get("CreationDate") or ""
                    rows.append([name, str(created)])
                skin.table(headers, rows)
            else:
                click.echo(buckets)
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to list buckets: {e}")
        raise SystemExit(1)


@bucket_group.command("create")
@click.option("--name", required=True, help="Bucket name to create")
@click.pass_context
def create_bucket(ctx, name):
    """Create a new bucket."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        result = backend.create_bucket(name)
        if use_json:
            click.echo(json_mod.dumps(result or {"name": name, "status": "created"}, indent=2))
        else:
            skin.success(f"Bucket '{name}' created")
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to create bucket: {e}")
        raise SystemExit(1)


@bucket_group.command("delete")
@click.option("--name", required=True, help="Bucket name to delete")
@click.option("--yes", is_flag=True, default=False,
              help="Required. Confirm bucket deletion and pass --yes to Tigris.")
@click.pass_context
def delete_bucket(ctx, name, yes):
    """Delete an empty bucket."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    if not yes:
        _emit_error(use_json, skin, "Refusing to delete bucket without --yes")
        raise SystemExit(1)
    try:
        result = backend.delete_bucket(name, yes=yes)
        if use_json:
            click.echo(json_mod.dumps(result or {"name": name, "status": "deleted"}, indent=2))
        else:
            skin.success(f"Bucket '{name}' deleted")
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to delete bucket: {e}")
        raise SystemExit(1)


@bucket_group.command("info")
@click.argument("name")
@click.pass_context
def bucket_info(ctx, name):
    """Get info about a bucket (`tigris buckets get`)."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        info = backend.head_bucket(name)
        if use_json:
            click.echo(json_mod.dumps(info or {"name": name}, indent=2))
        else:
            skin.section(f"Bucket: {name}")
            if isinstance(info, dict):
                for k, v in info.items():
                    skin.status(k, str(v))
            else:
                click.echo(info)
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to get bucket info: {e}")
        raise SystemExit(1)


def _emit_error(use_json: bool, skin, message: str) -> None:
    if use_json:
        click.echo(json_mod.dumps({"error": message}, indent=2))
    elif skin:
        skin.error(message)
    else:
        click.echo(message, err=True)
