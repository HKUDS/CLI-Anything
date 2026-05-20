"""Object commands -- list, put, get, delete, info, cp."""

import json as json_mod
import sys
import click

from ..utils.tigris_backend import TigrisBackend

TIGRIS_URI_SCHEME = "tigris://"


def _parse_tigris_uri(uri: str) -> tuple[str, str]:
    """Parse tigris://bucket/key/path into (bucket, key)."""
    if not uri.startswith(TIGRIS_URI_SCHEME):
        raise click.UsageError(
            f"Expected URI starting with {TIGRIS_URI_SCHEME}, got: {uri}"
        )
    rest = uri[len(TIGRIS_URI_SCHEME):]
    parts = rest.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise click.UsageError(
            f"Expected {TIGRIS_URI_SCHEME}<bucket>/<key>, got: {uri}"
        )
    return parts[0], parts[1]


@click.group("object")
@click.pass_context
def object_group(ctx):
    """Manage Tigris objects."""
    pass


@object_group.command("list")
@click.option("--bucket", required=True, help="Bucket name")
@click.option("--prefix", default=None, help="Filter objects by key prefix")
@click.option("--limit", default=100, type=int, help="Max number of results")
@click.pass_context
def list_objects(ctx, bucket, prefix, limit):
    """List objects in a bucket."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        objs = backend.list_objects(bucket, prefix=prefix, limit=limit)
        if use_json:
            click.echo(json_mod.dumps(objs, indent=2))
        else:
            if not objs:
                skin.info(f"No objects found in '{bucket}'.")
                return
            headers = ["Key", "Size", "Modified"]
            rows = [[o["key"], str(o["size"]), o["modified"]] for o in objs]
            skin.table(headers, rows)
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to list objects: {e}")
        raise SystemExit(1)


@object_group.command("put")
@click.option("--bucket", required=True, help="Bucket name")
@click.option("--key", required=True, help="Object key")
@click.option("--file", "file_path", default=None,
              help="Local file path to upload")
@click.option("--text", default=None, help="Inline text content to upload")
@click.option("--content-type", default=None, help="Object Content-Type header")
@click.pass_context
def put_object(ctx, bucket, key, file_path, text, content_type):
    """Upload an object from a file or inline text."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    if (file_path is None) == (text is None):
        msg = "Provide exactly one of --file or --text"
        if use_json:
            click.echo(json_mod.dumps({"error": msg}, indent=2))
        else:
            skin.error(msg)
        raise SystemExit(2)
    try:
        if file_path:
            result = backend.put_object_from_file(bucket, key, file_path)
        else:
            result = backend.put_object(
                bucket, key, text.encode("utf-8"),
                content_type=content_type or "text/plain",
            )
        if use_json:
            click.echo(json_mod.dumps(result, indent=2))
        else:
            skin.success(f"Uploaded {bucket}/{key}")
            skin.status("ETag", result.get("etag", "?"))
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to upload: {e}")
        raise SystemExit(1)


@object_group.command("get")
@click.option("--bucket", required=True, help="Bucket name")
@click.option("--key", required=True, help="Object key")
@click.option("--output", default=None,
              help="Local path to write to (default: stdout)")
@click.pass_context
def get_object(ctx, bucket, key, output):
    """Download an object to a file or to stdout."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        if output:
            result = backend.get_object_to_file(bucket, key, output)
            if use_json:
                click.echo(json_mod.dumps(result, indent=2))
            else:
                skin.success(f"Downloaded {bucket}/{key} -> {output}")
        else:
            data = backend.get_object(bucket, key)
            # Write raw bytes to stdout. JSON mode wraps as base64 only on
            # explicit request; for now stdout is the primary contract.
            sys.stdout.buffer.write(data)
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to download: {e}")
        raise SystemExit(1)


@object_group.command("delete")
@click.option("--bucket", required=True, help="Bucket name")
@click.option("--key", required=True, help="Object key")
@click.pass_context
def delete_object(ctx, bucket, key):
    """Delete an object."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        result = backend.delete_object(bucket, key)
        if use_json:
            click.echo(json_mod.dumps(result, indent=2))
        else:
            skin.success(f"Deleted {bucket}/{key}")
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to delete: {e}")
        raise SystemExit(1)


@object_group.command("info")
@click.option("--bucket", required=True, help="Bucket name")
@click.option("--key", required=True, help="Object key")
@click.pass_context
def object_info(ctx, bucket, key):
    """Get metadata for an object without downloading."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        info = backend.head_object(bucket, key)
        if use_json:
            click.echo(json_mod.dumps(info, indent=2))
        else:
            skin.section(f"Object: {bucket}/{key}")
            skin.status("Size", str(info.get("size", "?")))
            skin.status("Content-Type", info.get("content_type", "?"))
            skin.status("ETag", info.get("etag", "?"))
            skin.status("Modified", info.get("modified", "?"))
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to get object info: {e}")
        raise SystemExit(1)


@object_group.command("cp")
@click.argument("src")
@click.argument("dst")
@click.pass_context
def copy_object(ctx, src, dst):
    """Copy an object. SRC and DST are either local paths or tigris://bucket/key.

    Supported:
      local       -> tigris  (upload)
      tigris      -> local   (download)
      tigris      -> tigris  (server-side copy, no egress)
    """
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")

    src_is_tigris = src.startswith(TIGRIS_URI_SCHEME)
    dst_is_tigris = dst.startswith(TIGRIS_URI_SCHEME)

    try:
        if src_is_tigris and dst_is_tigris:
            sb, sk = _parse_tigris_uri(src)
            db, dk = _parse_tigris_uri(dst)
            result = backend.copy_object(sb, sk, db, dk)
        elif src_is_tigris and not dst_is_tigris:
            sb, sk = _parse_tigris_uri(src)
            result = backend.get_object_to_file(sb, sk, dst)
        elif not src_is_tigris and dst_is_tigris:
            db, dk = _parse_tigris_uri(dst)
            result = backend.put_object_from_file(db, dk, src)
        else:
            msg = "At least one of SRC or DST must be a tigris:// URI"
            if use_json:
                click.echo(json_mod.dumps({"error": msg}, indent=2))
            else:
                skin.error(msg)
            raise SystemExit(2)

        if use_json:
            click.echo(json_mod.dumps(result, indent=2))
        else:
            skin.success(f"Copied {src} -> {dst}")
    except SystemExit:
        raise
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to copy: {e}")
        raise SystemExit(1)
