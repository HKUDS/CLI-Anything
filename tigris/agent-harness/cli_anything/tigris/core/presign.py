"""Presigned URL commands -- get, put.

Presigned URLs let agents grant time-limited access to a single object
without sharing credentials. Useful for hand-off to other tools or users.
"""

import json as json_mod
import click

from ..utils.tigris_backend import TigrisBackend


@click.group("presign")
@click.pass_context
def presign_group(ctx):
    """Generate presigned URLs for object access."""
    pass


@presign_group.command("get")
@click.option("--bucket", required=True, help="Bucket name")
@click.option("--key", required=True, help="Object key")
@click.option("--expires", default=3600, type=int,
              help="URL lifetime in seconds (default: 3600)")
@click.pass_context
def presign_get(ctx, bucket, key, expires):
    """Generate a presigned URL for downloading an object."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        url = backend.presign_get(bucket, key, expires_in=expires)
        if use_json:
            click.echo(json_mod.dumps(
                {"url": url, "method": "GET", "expires_in": expires}, indent=2
            ))
        else:
            skin.success(f"Presigned GET for {bucket}/{key} ({expires}s)")
            click.echo(url)
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to presign: {e}")
        raise SystemExit(1)


@presign_group.command("put")
@click.option("--bucket", required=True, help="Bucket name")
@click.option("--key", required=True, help="Object key")
@click.option("--expires", default=3600, type=int,
              help="URL lifetime in seconds (default: 3600)")
@click.option("--content-type", default=None,
              help="Required Content-Type for the upload")
@click.pass_context
def presign_put(ctx, bucket, key, expires, content_type):
    """Generate a presigned URL for uploading an object."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        url = backend.presign_put(
            bucket, key, expires_in=expires, content_type=content_type,
        )
        if use_json:
            click.echo(json_mod.dumps(
                {"url": url, "method": "PUT", "expires_in": expires,
                 "content_type": content_type}, indent=2
            ))
        else:
            skin.success(f"Presigned PUT for {bucket}/{key} ({expires}s)")
            click.echo(url)
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to presign: {e}")
        raise SystemExit(1)
