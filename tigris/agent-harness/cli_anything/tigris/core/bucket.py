"""Bucket commands -- list, create, delete, info."""

import json as json_mod
import click

from ..utils.tigris_backend import TigrisBackend


@click.group("bucket")
@click.pass_context
def bucket_group(ctx):
    """Manage Tigris buckets."""
    pass


@bucket_group.command("list")
@click.pass_context
def list_buckets(ctx):
    """List all buckets."""
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
            headers = ["Name", "Created"]
            rows = [[b["name"], b["created"]] for b in buckets]
            skin.table(headers, rows)
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to list buckets: {e}")
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
            click.echo(json_mod.dumps(result, indent=2))
        else:
            skin.success(f"Bucket '{name}' created")
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to create bucket: {e}")
        raise SystemExit(1)


@bucket_group.command("delete")
@click.option("--name", required=True, help="Bucket name to delete")
@click.pass_context
def delete_bucket(ctx, name):
    """Delete an empty bucket."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        result = backend.delete_bucket(name)
        if use_json:
            click.echo(json_mod.dumps(result, indent=2))
        else:
            skin.success(f"Bucket '{name}' deleted")
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to delete bucket: {e}")
        raise SystemExit(1)


@bucket_group.command("info")
@click.argument("name")
@click.pass_context
def bucket_info(ctx, name):
    """Get info about a bucket."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        info = backend.head_bucket(name)
        if use_json:
            click.echo(json_mod.dumps(info, indent=2))
        else:
            skin.section(f"Bucket: {name}")
            skin.status("Exists", str(info.get("exists", False)))
            skin.status("Endpoint", info.get("endpoint", "?"))
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to get bucket info: {e}")
        raise SystemExit(1)
