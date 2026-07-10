"""Object commands -- list, put, get, delete, info, cp."""

import json as json_mod
import click

from ..utils.tigris_backend import TigrisBackend, TigrisCliError


T3_SCHEMES = ("t3://", "tigris://")


def _is_remote(path: str) -> bool:
    return path.startswith(T3_SCHEMES)


def _parse_tigris_uri(uri: str) -> tuple[str, str]:
    """Parse t3://bucket/key or tigris://bucket/key into (bucket, key)."""
    for scheme in T3_SCHEMES:
        if uri.startswith(scheme):
            rest = uri[len(scheme):]
            parts = rest.split("/", 1)
            if len(parts) == 2 and parts[0] and parts[1]:
                return parts[0], parts[1]
            raise click.UsageError(
                f"Expected {scheme}<bucket>/<key>, got: {uri}"
            )
    raise click.UsageError(
        f"Expected URI starting with t3:// or tigris://, got: {uri}"
    )


@click.group("object")
@click.pass_context
def object_group(ctx):
    """Manage Tigris objects (wraps `tigris ls/cp/rm/stat`)."""
    pass


@object_group.command("list")
@click.option("--bucket", required=True, help="Bucket name")
@click.option("--prefix", default=None, help="Filter objects by key prefix")
@click.option("--limit", default=None, type=int,
              help="Limit to first N results (client-side trim)")
@click.pass_context
def list_objects(ctx, bucket, prefix, limit):
    """List objects in a bucket (`tigris ls`)."""
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
            if isinstance(objs, list):
                headers = ["Key", "Size", "Modified"]
                rows = []
                for o in objs:
                    if not isinstance(o, dict):
                        rows.append([str(o), "", ""])
                        continue
                    rows.append([
                        str(o.get("key") or o.get("Key") or "?"),
                        str(o.get("size") or o.get("Size") or ""),
                        str(o.get("modified") or o.get("LastModified") or ""),
                    ])
                skin.table(headers, rows)
            else:
                click.echo(objs)
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to list objects: {e}")
        raise SystemExit(1)


@object_group.command("put")
@click.option("--bucket", required=True, help="Bucket name")
@click.option("--key", required=True, help="Object key")
@click.option("--file", "file_path", default=None,
              help="Local file path to upload (uses `tigris cp`)")
@click.option("--text", default=None,
              help="Inline text content (staged to a tempfile then `tigris cp`)")
@click.pass_context
def put_object(ctx, bucket, key, file_path, text):
    """Upload an object from a file or inline text."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    if (file_path is None) == (text is None):
        msg = "Provide exactly one of --file or --text"
        _emit_error(use_json, skin, msg)
        raise SystemExit(2)
    try:
        if file_path:
            backend.put_object_from_file(bucket, key, file_path)
        else:
            backend.put_object_inline(bucket, key, text)
        if use_json:
            click.echo(json_mod.dumps(
                {"bucket": bucket, "key": key, "status": "uploaded"}, indent=2
            ))
        else:
            skin.success(f"Uploaded {bucket}/{key}")
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to upload: {e}")
        raise SystemExit(1)


@object_group.command("get")
@click.option("--bucket", required=True, help="Bucket name")
@click.option("--key", required=True, help="Object key")
@click.option("--output", required=True,
              help="Local path to write the object to")
@click.pass_context
def get_object(ctx, bucket, key, output):
    """Download an object to a local file (`tigris cp`)."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        backend.get_object_to_file(bucket, key, output)
        if use_json:
            click.echo(json_mod.dumps(
                {"bucket": bucket, "key": key, "path": output}, indent=2
            ))
        else:
            skin.success(f"Downloaded {bucket}/{key} -> {output}")
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to download: {e}")
        raise SystemExit(1)


@object_group.command("delete")
@click.option("--bucket", required=True, help="Bucket name")
@click.option("--key", required=True, help="Object key")
@click.pass_context
def delete_object(ctx, bucket, key):
    """Delete an object (`tigris rm`)."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        backend.delete_object(bucket, key)
        if use_json:
            click.echo(json_mod.dumps(
                {"bucket": bucket, "key": key, "status": "deleted"}, indent=2
            ))
        else:
            skin.success(f"Deleted {bucket}/{key}")
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to delete: {e}")
        raise SystemExit(1)


@object_group.command("info")
@click.option("--bucket", required=True, help="Bucket name")
@click.option("--key", required=True, help="Object key")
@click.pass_context
def object_info(ctx, bucket, key):
    """Get object metadata (`tigris stat`)."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        info = backend.head_object(bucket, key)
        if use_json:
            click.echo(json_mod.dumps(info or {"bucket": bucket, "key": key}, indent=2))
        else:
            skin.section(f"Object: {bucket}/{key}")
            if isinstance(info, dict):
                for k, v in info.items():
                    skin.status(k, str(v))
            else:
                click.echo(info)
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to get object info: {e}")
        raise SystemExit(1)


@object_group.command("cp")
@click.argument("src")
@click.argument("dst")
@click.option("--recursive", "-r", is_flag=True, help="Copy directories recursively")
@click.pass_context
def copy_object(ctx, src, dst, recursive):
    """Copy. SRC and DST are local paths or t3://bucket/key (or tigris://...).

    At least one side must be a t3:// or tigris:// URI.
    """
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")

    if not (_is_remote(src) or _is_remote(dst)):
        _emit_error(use_json, skin,
                    "At least one of SRC or DST must be t3:// or tigris://")
        raise SystemExit(2)

    try:
        backend.cp(src, dst, recursive=recursive)
        if use_json:
            click.echo(json_mod.dumps(
                {"src": src, "dst": dst, "status": "copied"}, indent=2
            ))
        else:
            skin.success(f"Copied {src} -> {dst}")
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to copy: {e}")
        raise SystemExit(1)


def _emit_error(use_json: bool, skin, message: str) -> None:
    if use_json:
        click.echo(json_mod.dumps({"error": message}, indent=2))
    elif skin:
        skin.error(message)
    else:
        click.echo(message, err=True)
