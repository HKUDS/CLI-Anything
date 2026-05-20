"""Presigned URL commands -- get, put.

Wraps `tigris presign <path> --method get|put --expires-in <sec>`.
"""

import json as json_mod
import click

from ..utils.tigris_backend import TigrisBackend, TigrisCliError


@click.group("presign")
@click.pass_context
def presign_group(ctx):
    """Generate presigned URLs (wraps `tigris presign`)."""
    pass


def _presign(ctx, bucket: str, key: str, method: str, expires: int,
             access_key: str | None) -> None:
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        url = backend.presign(bucket, key, method=method,
                              expires_in=expires, access_key=access_key)
        if use_json:
            click.echo(json_mod.dumps(
                {"url": url, "method": method.upper(), "expires_in": expires},
                indent=2,
            ))
        else:
            skin.success(f"Presigned {method.upper()} for {bucket}/{key} ({expires}s)")
            click.echo(url)
    except TigrisCliError as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to presign: {e}")
        raise SystemExit(1)


@presign_group.command("get")
@click.option("--bucket", required=True, help="Bucket name")
@click.option("--key", required=True, help="Object key")
@click.option("--expires", default=3600, type=int,
              help="URL lifetime in seconds (default: 3600)")
@click.option("--access-key", default=None,
              help="Access key ID to sign with (default: resolved automatically)")
@click.pass_context
def presign_get(ctx, bucket, key, expires, access_key):
    """Presigned URL for downloading an object."""
    _presign(ctx, bucket, key, "get", expires, access_key)


@presign_group.command("put")
@click.option("--bucket", required=True, help="Bucket name")
@click.option("--key", required=True, help="Object key")
@click.option("--expires", default=3600, type=int,
              help="URL lifetime in seconds (default: 3600)")
@click.option("--access-key", default=None,
              help="Access key ID to sign with (default: resolved automatically)")
@click.pass_context
def presign_put(ctx, bucket, key, expires, access_key):
    """Presigned URL for uploading an object."""
    _presign(ctx, bucket, key, "put", expires, access_key)
