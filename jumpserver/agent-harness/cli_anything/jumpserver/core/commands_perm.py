"""
Permission management commands for JumpServer CLI.

Manages asset permissions, user/asset/node relations.
"""
import click

from cli_anything.jumpserver.core.session import Session
from cli_anything.jumpserver.utils import (
    require_auth,
    handle_api_error,
    parse_ids,
    print_result,
    should_emit_human_text,
)


@click.group(name="perm")
def perm_group():
    """Manage asset permissions."""
    pass


@perm_group.command(name="list")
@click.option("--search", "-s", default=None, help="Search by name")
@click.option("--user", "-u", default=None, help="Filter by user ID")
@click.option("--active/--inactive", default=None, help="Filter by active status")
@click.option("--limit", default=20, help="Results per page")
@click.option("--offset", default=0, help="Pagination offset")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--columns", "-c", default="name,users_amount,assets_amount,is_active,date_expired", help="Comma-separated column names")
def list_perms(search, user, active, limit, offset, output, columns):
    """List asset permissions."""
    session = Session.load()
    client = require_auth(session)

    params = {"limit": limit, "offset": offset}
    if search:
        params["search"] = search
    if user:
        params["user"] = user
    if active is not None:
        params["is_active"] = str(active).lower()

    resp = client.get("perms/asset-permissions/", params=params)
    handle_api_error(resp, "list permissions")
    print_result(resp.json(), fmt=output, columns=columns)


@perm_group.command(name="get")
@click.argument("perm_id")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def get_perm(perm_id, output):
    """Get permission details."""
    session = Session.load()
    client = require_auth(session)
    resp = client.get(f"perms/asset-permissions/{perm_id}/")
    handle_api_error(resp, "get permission")
    print_result(resp.json(), fmt=output)


@perm_group.command(name="create")
@click.option("--name", required=True, help="Permission rule name")
@click.option("--users", default=None, help="Comma-separated user IDs")
@click.option("--user-groups", default=None, help="Comma-separated user group IDs")
@click.option("--assets", default=None, help="Comma-separated asset IDs")
@click.option("--nodes", default=None, help="Comma-separated node IDs")
@click.option("--actions", default="all", help="Actions (all, connect, upload, download, clipboard_copy, clipboard_paste)")
@click.option("--date-start", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--date-expired", default=None, help="Expiry date (YYYY-MM-DD)")
@click.option("--active/--inactive", default=True, help="Active status")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def create_perm(name, users, user_groups, assets, nodes, actions, date_start, date_expired, active, output, dry_run):
    """Create a new asset permission."""
    data = {
        "name": name,
        "is_active": active,
    }
    if users:
        data["users"] = parse_ids(users)
    if user_groups:
        data["user_groups"] = parse_ids(user_groups)
    if assets:
        data["assets"] = parse_ids(assets)
    if nodes:
        data["nodes"] = parse_ids(nodes)
    if actions:
        data["actions"] = parse_ids(actions)
    if date_start:
        data["date_start"] = date_start
    if date_expired:
        data["date_expired"] = date_expired

    if dry_run:
        print_result({"action": "create permission", "data": data}, fmt=output)
        return

    session = Session.load()
    client = require_auth(session)
    resp = client.post("perms/asset-permissions/", data=data)
    handle_api_error(resp, "create permission")
    print_result(resp.json(), fmt=output)
    if should_emit_human_text(output):
        click.echo(click.style(f"\n✓ Permission '{name}' created.", fg="green"))


@perm_group.command(name="update")
@click.argument("perm_id")
@click.option("--name", default=None, help="New name")
@click.option("--users", default=None, help="Comma-separated user IDs")
@click.option("--user-groups", default=None, help="Comma-separated user group IDs")
@click.option("--assets", default=None, help="Comma-separated asset IDs")
@click.option("--nodes", default=None, help="Comma-separated node IDs")
@click.option("--actions", default=None, help="Actions")
@click.option("--active/--inactive", default=None, help="Set active status")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def update_perm(perm_id, name, users, user_groups, assets, nodes, actions, active, output, dry_run):
    """Update an asset permission."""
    data = {}
    if name is not None:
        data["name"] = name
    if users is not None:
        data["users"] = parse_ids(users)
    if user_groups is not None:
        data["user_groups"] = parse_ids(user_groups)
    if assets is not None:
        data["assets"] = parse_ids(assets)
    if nodes is not None:
        data["nodes"] = parse_ids(nodes)
    if actions is not None:
        data["actions"] = parse_ids(actions)
    if active is not None:
        data["is_active"] = active

    if dry_run:
        print_result({"action": "update permission", "id": perm_id, "data": data}, fmt=output)
        return

    session = Session.load()
    client = require_auth(session)
    resp = client.put(f"perms/asset-permissions/{perm_id}/", data=data)
    handle_api_error(resp, "update permission")
    print_result(resp.json(), fmt=output)
    if should_emit_human_text(output):
        click.echo(click.style(f"\n✓ Permission '{perm_id}' updated.", fg="green"))


@perm_group.command(name="delete")
@click.argument("perm_id")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def delete_perm(perm_id, force, dry_run):
    """Delete an asset permission."""
    if dry_run:
        click.echo(f"[DRY RUN] Would delete permission: {perm_id}")
        return
    if not force:
        click.confirm(f"Delete permission '{perm_id}'?", abort=True)

    session = Session.load()
    client = require_auth(session)
    resp = client.delete(f"perms/asset-permissions/{perm_id}/")
    handle_api_error(resp, "delete permission")
    click.echo(click.style(f"✓ Permission '{perm_id}' deleted.", fg="green"))


@perm_group.command(name="users")
@click.argument("perm_id")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def perm_users(perm_id, output):
    """List users assigned to a permission."""
    session = Session.load()
    client = require_auth(session)
    resp = client.get(f"perms/asset-permissions/{perm_id}/users/all/")
    handle_api_error(resp, "get permission users")
    print_result(resp.json(), fmt=output)


@perm_group.command(name="assets")
@click.argument("perm_id")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def perm_assets(perm_id, output):
    """List assets authorized by a permission."""
    session = Session.load()
    client = require_auth(session)
    resp = client.get(f"perms/asset-permissions/{perm_id}/assets/all/")
    handle_api_error(resp, "get permission assets")
    print_result(resp.json(), fmt=output)
