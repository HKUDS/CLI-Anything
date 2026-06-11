"""Access key commands -- list, create, get, delete, assign, rotate.

Wraps `tigris access-keys`. Scoped per-bucket roles are one of Tigris's
agent-storage primitives — combine with `snapshot` and per-agent buckets to
give each agent its own least-privilege credentials.
"""

import json as json_mod
import click

from ..utils.tigris_backend import TigrisBackend, TigrisCliError


@click.group("access-key")
@click.pass_context
def access_key_group(ctx):
    """Manage Tigris access keys (wraps `tigris access-keys`)."""
    pass


@access_key_group.command("list")
@click.pass_context
def list_keys(ctx):
    """List all access keys in the current organization."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        keys = backend.list_access_keys()
        if use_json:
            click.echo(json_mod.dumps(keys, indent=2))
        else:
            if not keys:
                skin.info("No access keys found.")
                return
            if isinstance(keys, list):
                headers = ["ID", "Name", "Created"]
                rows = []
                for k in keys:
                    if not isinstance(k, dict):
                        rows.append([str(k), "", ""])
                        continue
                    rows.append([
                        str(k.get("id") or k.get("accessKeyId") or "?"),
                        str(k.get("name") or ""),
                        str(k.get("created") or k.get("createdAt") or ""),
                    ])
                skin.table(headers, rows)
            else:
                click.echo(keys)
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to list access keys: {e}")
        raise SystemExit(1)


@access_key_group.command("create")
@click.argument("name")
@click.pass_context
def create_key(ctx, name):
    """Create a new access key. Secret is shown only once."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        result = backend.create_access_key(name)
        if use_json:
            click.echo(json_mod.dumps(result, indent=2))
        else:
            skin.success(f"Access key '{name}' created — secret shown ONCE, save it now")
            if isinstance(result, dict):
                for k, v in result.items():
                    skin.status(k, str(v))
            else:
                click.echo(result)
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to create access key: {e}")
        raise SystemExit(1)


@access_key_group.command("get")
@click.argument("key_id")
@click.pass_context
def get_key(ctx, key_id):
    """Show details for an access key."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        info = backend.get_access_key(key_id)
        if use_json:
            click.echo(json_mod.dumps(info, indent=2))
        else:
            skin.section(f"Access key: {key_id}")
            if isinstance(info, dict):
                for k, v in info.items():
                    skin.status(k, str(v))
            else:
                click.echo(info)
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to get access key: {e}")
        raise SystemExit(1)


@access_key_group.command("delete")
@click.argument("key_id")
@click.option("--yes", is_flag=True, default=False,
              help="Required. Confirm access-key deletion and pass --yes to Tigris.")
@click.pass_context
def delete_key(ctx, key_id, yes):
    """Permanently delete an access key."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    if not yes:
        _emit_error(use_json, skin, "Refusing to delete access key without --yes")
        raise SystemExit(1)
    try:
        result = backend.delete_access_key(key_id, yes=yes)
        if use_json:
            click.echo(json_mod.dumps(result or {"id": key_id, "status": "deleted"}, indent=2))
        else:
            skin.success(f"Access key {key_id} deleted")
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to delete access key: {e}")
        raise SystemExit(1)


@access_key_group.command("assign")
@click.argument("key_id")
@click.option("--bucket", required=True, help="Bucket to scope the key to")
@click.option("--role", required=True,
              help="Role to grant (e.g. Editor, Viewer)")
@click.pass_context
def assign_key(ctx, key_id, bucket, role):
    """Assign a per-bucket role to an access key (scoped credentials)."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        result = backend.assign_access_key(key_id, bucket=bucket, role=role)
        if use_json:
            click.echo(json_mod.dumps(
                result or {"id": key_id, "bucket": bucket, "role": role,
                           "status": "assigned"}, indent=2,
            ))
        else:
            skin.success(f"Key {key_id} assigned {role} on {bucket}")
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to assign access key: {e}")
        raise SystemExit(1)


@access_key_group.command("rotate")
@click.argument("key_id")
@click.option("--yes", is_flag=True, default=False,
              help="Required. Confirm secret rotation and pass --yes to Tigris.")
@click.pass_context
def rotate_key(ctx, key_id, yes):
    """Rotate an access key's secret."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    if not yes:
        _emit_error(use_json, skin, "Refusing to rotate access key without --yes")
        raise SystemExit(1)
    try:
        result = backend.rotate_access_key(key_id, yes=yes)
        if use_json:
            click.echo(json_mod.dumps(result or {"id": key_id, "status": "rotated"}, indent=2))
        else:
            skin.success(f"Access key {key_id} rotated — new secret shown ONCE")
            if isinstance(result, dict):
                for k, v in result.items():
                    skin.status(k, str(v))
            else:
                click.echo(result)
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to rotate access key: {e}")
        raise SystemExit(1)


def _emit_error(use_json: bool, skin, message: str) -> None:
    if use_json:
        click.echo(json_mod.dumps({"error": message}, indent=2))
    elif skin:
        skin.error(message)
    else:
        click.echo(message, err=True)
