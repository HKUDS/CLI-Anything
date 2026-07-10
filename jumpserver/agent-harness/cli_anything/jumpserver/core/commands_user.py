"""
User management commands for JumpServer CLI.

Manages users, user groups, and user-group relations.
"""
import json

import click

from cli_anything.jumpserver.core.session import Session
from cli_anything.jumpserver.utils import (
    require_auth,
    handle_api_error,
    parse_ids,
    print_result,
    mask_sensitive_data,
    should_emit_human_text,
)


@click.group(name="user")
def user_group():
    """Manage users and user groups."""
    pass


# ─── Users CRUD ──────────────────────────────────────────────


@user_group.command(name="list")
@click.option("--search", "-s", default=None, help="Search by username or name")
@click.option("--source", default=None, help="Filter by source (local, ldap, oauth2, etc.)")
@click.option("--active/--inactive", default=None, help="Filter by active status")
@click.option("--limit", default=20, help="Results per page")
@click.option("--offset", default=0, help="Pagination offset")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--columns", "-c", default="username,name,role,source,is_active", help="Comma-separated column names")
def list_users(search, source, active, limit, offset, output, columns):
    """List users."""
    session = Session.load()
    client = require_auth(session)

    params = {"limit": limit, "offset": offset}
    if search:
        params["search"] = search
    if source:
        params["source"] = source
    if active is not None:
        params["is_active"] = str(active).lower()

    resp = client.get("users/users/", params=params)
    handle_api_error(resp, "list users")
    print_result(resp.json(), fmt=output, columns=columns)


@user_group.command(name="get")
@click.argument("user_id")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def get_user(user_id, output):
    """Get user details."""
    session = Session.load()
    client = require_auth(session)
    resp = client.get(f"users/users/{user_id}/")
    handle_api_error(resp, "get user")
    print_result(resp.json(), fmt=output)


@user_group.command(name="create")
@click.option("--name", required=True, help="Display name")
@click.option("--username", required=True, help="Login username")
@click.option("--email", required=True, help="Email address")
@click.option("--password", default=None, help="Password (required for local users)")
@click.option("--role", default="User", type=click.Choice(["Admin", "User", "Auditor"]), help="User role")
@click.option("--active/--inactive", default=True, help="Active status")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def create_user(name, username, email, password, role, active, output, dry_run):
    """Create a new user."""
    data = {
        "name": name,
        "username": username,
        "email": email,
        "role": role,
        "is_active": active,
    }
    if password:
        data["password"] = password

    if dry_run:
        print_result(
            {"action": "create user", "data": mask_sensitive_data(data)},
            fmt=output,
        )
        return

    session = Session.load()
    client = require_auth(session)
    resp = client.post("users/users/", data=data)
    handle_api_error(resp, "create user")
    print_result(resp.json(), fmt=output)
    if should_emit_human_text(output):
        click.echo(click.style(f"\n✓ User '{username}' created.", fg="green"))


@user_group.command(name="update")
@click.argument("user_id")
@click.option("--name", default=None, help="New display name")
@click.option("--email", default=None, help="New email")
@click.option("--role", default=None, type=click.Choice(["Admin", "User", "Auditor"]), help="New role")
@click.option("--active/--inactive", default=None, help="Set active status")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def update_user(user_id, name, email, role, active, output, dry_run):
    """Update a user."""
    data = {}
    if name is not None:
        data["name"] = name
    if email is not None:
        data["email"] = email
    if role is not None:
        data["role"] = role
    if active is not None:
        data["is_active"] = active

    if dry_run:
        print_result({"action": "update user", "id": user_id, "data": data}, fmt=output)
        return

    session = Session.load()
    client = require_auth(session)
    resp = client.put(f"users/users/{user_id}/", data=data)
    handle_api_error(resp, "update user")
    print_result(resp.json(), fmt=output)
    if should_emit_human_text(output):
        click.echo(click.style(f"\n✓ User '{user_id}' updated.", fg="green"))


@user_group.command(name="delete")
@click.argument("user_id")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def delete_user(user_id, force, dry_run):
    """Delete a user."""
    if dry_run:
        click.echo(f"[DRY RUN] Would delete user: {user_id}")
        return
    if not force:
        click.confirm(f"Delete user '{user_id}'?", abort=True)

    session = Session.load()
    client = require_auth(session)
    resp = client.delete(f"users/users/{user_id}/")
    handle_api_error(resp, "delete user")
    click.echo(click.style(f"✓ User '{user_id}' deleted.", fg="green"))


@user_group.command(name="reset-password")
@click.argument("user_id")
@click.option("--password", "-p", required=True, help="New password")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.option("--yes", is_flag=True, help="Alias for --force")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def reset_password(user_id, password, force, yes, output, dry_run):
    """Reset a user's password."""
    if dry_run:
        print_result(
            {
                "action": "reset password",
                "user_id": user_id,
                "data": mask_sensitive_data({"password": password}),
            },
            fmt=output,
        )
        return
    if not (force or yes):
        click.confirm(f"Reset password for user '{user_id}'?", abort=True)

    session = Session.load()
    client = require_auth(session)
    resp = client.post(f"users/users/{user_id}/password/reset/", data={"password": password})
    handle_api_error(resp, "reset password")
    if should_emit_human_text(output):
        click.echo(click.style(f"✓ Password reset for user '{user_id}'.", fg="green"))
    else:
        print_result(
            {"status": "ok", "action": "reset password", "user_id": user_id},
            fmt=output,
        )


@user_group.command(name="unblock")
@click.argument("user_id")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def unblock_user(user_id, output, dry_run):
    """Unblock a locked user."""
    if dry_run:
        click.echo(f"[DRY RUN] Would unblock user: {user_id}")
        return

    session = Session.load()
    client = require_auth(session)
    resp = client.post(f"users/users/{user_id}/unblock/")
    handle_api_error(resp, "unblock user")
    click.echo(click.style(f"✓ User '{user_id}' unblocked.", fg="green"))


# ─── User Groups ─────────────────────────────────────────────


@user_group.group(name="group")
def group_commands():
    """Manage user groups."""
    pass


@group_commands.command(name="list")
@click.option("--search", "-s", default=None, help="Search by name")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def list_groups(search, output):
    """List user groups."""
    session = Session.load()
    client = require_auth(session)

    params = {}
    if search:
        params["search"] = search

    resp = client.get("users/groups/", params=params)
    handle_api_error(resp, "list groups")
    print_result(resp.json(), fmt=output)


@group_commands.command(name="create")
@click.option("--name", required=True, help="Group name")
@click.option("--comment", default=None, help="Comment")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def create_group(name, comment, output, dry_run):
    """Create a user group."""
    data = {"name": name}
    if comment:
        data["comment"] = comment

    if dry_run:
        print_result({"action": "create group", "data": data}, fmt=output)
        return

    session = Session.load()
    client = require_auth(session)
    resp = client.post("users/groups/", data=data)
    handle_api_error(resp, "create group")
    print_result(resp.json(), fmt=output)
    if should_emit_human_text(output):
        click.echo(click.style(f"\n✓ Group '{name}' created.", fg="green"))


@group_commands.command(name="members")
@click.argument("group_id")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def group_members(group_id, output):
    """List members of a user group."""
    session = Session.load()
    client = require_auth(session)
    resp = client.get(f"users/groups/{group_id}/")
    handle_api_error(resp, "get group")
    data = resp.json()
    print_result(data, fmt=output)


# ─── Profile ─────────────────────────────────────────────────


@user_group.command(name="profile")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def profile(output):
    """Show current user profile."""
    session = Session.load()
    client = require_auth(session)
    resp = client.get("users/profile/")
    handle_api_error(resp, "get profile")
    print_result(resp.json(), fmt=output)


@user_group.command(name="my-assets")
@click.option("--search", "-s", default=None, help="Search by name or address")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def my_assets(search, output):
    """List assets the current user can access."""
    session = Session.load()
    client = require_auth(session)

    params = {}
    if search:
        params["search"] = search

    resp = client.get("perms/my/assets/", params=params)
    handle_api_error(resp, "list my assets")
    print_result(resp.json(), fmt=output)
