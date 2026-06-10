"""
Settings and system commands for JumpServer CLI.

Manages system settings, license, and health checks.
"""
import click

from cli_anything.jumpserver.core.session import Session
from cli_anything.jumpserver.utils import (
    require_auth,
    handle_api_error,
    print_result,
)


@click.group(name="system")
def system_group():
    """Manage system settings and configuration."""
    pass


@system_group.command(name="settings")
@click.option("--search", "-s", default=None, help="Filter settings by name")
@click.option("--category", "-c", default=None, help="Filter by category")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def list_settings(search, category, output):
    """List system settings."""
    sess = Session.load()
    client = require_auth(sess)

    params = {}
    if search:
        params["search"] = search
    if category:
        params["category"] = category

    resp = client.get("settings/settings/", params=params)
    handle_api_error(resp, "get settings")
    print_result(resp.json(), fmt=output)


@system_group.command(name="health")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def health_check(output):
    """Check system health."""
    sess = Session.load()
    client = require_auth(sess)

    try:
        resp = client.get("health/")
        resp.raise_for_status()
        data = resp.json()
        print_result(data, fmt=output)
    except Exception as e:
        print_result({"status": "error", "message": str(e)}, fmt=output)


@system_group.command(name="info")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def system_info(output):
    """Show system information."""
    sess = Session.load()
    client = require_auth(sess)

    try:
        # Try to get public settings (no auth typically needed)
        resp = client.get("settings/public/")
        resp.raise_for_status()
        data = resp.json()

        info = {
            "url": sess.base_url,
            "org": sess.org_id or "default",
            "version": data.get("XPACK_VERSION", data.get("VERSION", "unknown")),
            "authenticated": sess.is_authenticated(),
            "username": sess.username if sess.is_authenticated() else "N/A",
        }
        print_result(info, fmt=output)
    except Exception:
        info = {
            "url": sess.base_url,
            "org": sess.org_id or "default",
            "authenticated": sess.is_authenticated(),
            "username": sess.username if sess.is_authenticated() else "N/A",
        }
        print_result(info, fmt=output)


# ─── Labels ───────────────────────────────────────────────────


@click.group(name="label")
def label_group():
    """Manage labels."""
    pass


@label_group.command(name="list")
@click.option("--search", "-s", default=None, help="Search by name")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def list_labels(search, output):
    """List labels."""
    sess = Session.load()
    client = require_auth(sess)

    params = {}
    if search:
        params["search"] = search

    resp = client.get("labels/labels/", params=params)
    handle_api_error(resp, "get labels")
    print_result(resp.json(), fmt=output)


# ─── RBAC ─────────────────────────────────────────────────────


@click.group(name="role")
def role_group():
    """Manage roles and permissions."""
    pass


@role_group.command(name="list")
@click.option("--search", "-s", default=None, help="Search by name")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def list_roles(search, output):
    """List roles."""
    sess = Session.load()
    client = require_auth(sess)

    params = {}
    if search:
        params["search"] = search

    resp = client.get("rbac/roles/", params=params)
    handle_api_error(resp, "get roles")
    print_result(resp.json(), fmt=output)


@role_group.command(name="bindings")
@click.option("--user", "-u", default=None, help="Filter by user ID")
@click.option("--role", "-r", default=None, help="Filter by role ID")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def list_bindings(user, role, output):
    """List role bindings."""
    sess = Session.load()
    client = require_auth(sess)

    params = {}
    if user:
        params["user"] = user
    if role:
        params["role"] = role

    resp = client.get("rbac/role-bindings/", params=params)
    handle_api_error(resp, "get role bindings")
    print_result(resp.json(), fmt=output)
