"""
Account management commands for JumpServer CLI.

Manages asset accounts, templates, automations, and secrets.
"""
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


@click.group(name="account")
def account_group():
    """Manage asset accounts and credentials."""
    pass


# ─── Accounts CRUD ──────────────────────────────────────────


@account_group.command(name="list")
@click.option("--search", "-s", default=None, help="Search by username or name")
@click.option("--asset", "-a", default=None, help="Filter by asset ID")
@click.option("--secret-type", default=None, type=click.Choice(["password", "ssh_key"]), help="Secret type")
@click.option("--privileged/--unprivileged", default=None, help="Filter by privileged status")
@click.option("--active/--inactive", default=None, help="Filter by active status")
@click.option("--limit", default=20, help="Results per page")
@click.option("--offset", default=0, help="Pagination offset")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--columns", "-c", default="username,name,asset,secret_type,privileged,is_active", help="Comma-separated column names")
def list_accounts(search, asset, secret_type, privileged, active, limit, offset, output, columns):
    """List asset accounts."""
    session = Session.load()
    client = require_auth(session)

    params = {"limit": limit, "offset": offset}
    if search:
        params["search"] = search
    if asset:
        params["asset"] = asset
    if secret_type:
        params["secret_type"] = secret_type
    if privileged is not None:
        params["privileged"] = str(privileged).lower()
    if active is not None:
        params["is_active"] = str(active).lower()

    resp = client.get("accounts/accounts/", params=params)
    handle_api_error(resp, "list accounts")
    print_result(resp.json(), fmt=output, columns=columns)


@account_group.command(name="get")
@click.argument("account_id")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def get_account(account_id, output):
    """Get account details."""
    session = Session.load()
    client = require_auth(session)
    resp = client.get(f"accounts/accounts/{account_id}/")
    handle_api_error(resp, "get account")
    print_result(resp.json(), fmt=output)


@account_group.command(name="create")
@click.option("--asset", "-a", required=True, type=int, help="Asset ID")
@click.option("--username", required=True, help="Account username")
@click.option("--name", default=None, help="Display name")
@click.option("--secret-type", default="password", type=click.Choice(["password", "ssh_key"]), help="Secret type")
@click.option("--secret", default=None, help="Password or SSH private key")
@click.option("--privileged", is_flag=True, help="Is privileged account")
@click.option("--active/--inactive", default=True, help="Active status")
@click.option("--comment", default=None, help="Comment")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def create_account(asset, username, name, secret_type, secret, privileged, active, comment, output, dry_run):
    """Create a new asset account."""
    data = {
        "asset": asset,
        "username": username,
        "secret_type": secret_type,
        "privileged": privileged,
        "is_active": active,
    }
    if name:
        data["name"] = name
    if secret:
        data["secret"] = secret
    if comment:
        data["comment"] = comment

    if dry_run:
        print_result(
            {"action": "create account", "data": mask_sensitive_data(data)},
            fmt=output,
        )
        return

    session = Session.load()
    client = require_auth(session)
    resp = client.post("accounts/accounts/", data=data)
    handle_api_error(resp, "create account")
    print_result(resp.json(), fmt=output)
    if should_emit_human_text(output):
        click.echo(click.style(f"\n✓ Account '{username}' created.", fg="green"))


@account_group.command(name="update")
@click.argument("account_id")
@click.option("--username", default=None, help="New username")
@click.option("--name", default=None, help="New display name")
@click.option("--secret-type", default=None, type=click.Choice(["password", "ssh_key"]), help="New secret type")
@click.option("--secret", default=None, help="New password or SSH key")
@click.option("--privileged/--unprivileged", default=None, help="Set privileged status")
@click.option("--active/--inactive", default=None, help="Set active status")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def update_account(account_id, username, name, secret_type, secret, privileged, active, output, dry_run):
    """Update an asset account."""
    data = {}
    if username is not None:
        data["username"] = username
    if name is not None:
        data["name"] = name
    if secret_type is not None:
        data["secret_type"] = secret_type
    if secret is not None:
        data["secret"] = secret
    if privileged is not None:
        data["privileged"] = privileged
    if active is not None:
        data["is_active"] = active

    if dry_run:
        print_result(
            {
                "action": "update account",
                "id": account_id,
                "data": mask_sensitive_data(data),
            },
            fmt=output,
        )
        return

    session = Session.load()
    client = require_auth(session)
    resp = client.put(f"accounts/accounts/{account_id}/", data=data)
    handle_api_error(resp, "update account")
    print_result(resp.json(), fmt=output)
    if should_emit_human_text(output):
        click.echo(click.style(f"\n✓ Account '{account_id}' updated.", fg="green"))


@account_group.command(name="delete")
@click.argument("account_id")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def delete_account(account_id, force, dry_run):
    """Delete an asset account."""
    if dry_run:
        click.echo(f"[DRY RUN] Would delete account: {account_id}")
        return
    if not force:
        click.confirm(f"Delete account '{account_id}'?", abort=True)

    session = Session.load()
    client = require_auth(session)
    resp = client.delete(f"accounts/accounts/{account_id}/")
    handle_api_error(resp, "delete account")
    click.echo(click.style(f"✓ Account '{account_id}' deleted.", fg="green"))


# ─── Secrets ─────────────────────────────────────────────────


@account_group.group(name="secret")
def secret_group():
    """View account secrets/passwords."""
    pass


@secret_group.command(name="view")
@click.argument("account_id")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def view_secret(account_id, output):
    """View an account's password/secret (requires permission)."""
    session = Session.load()
    client = require_auth(session)
    resp = client.get(f"accounts/account-secrets/{account_id}/")
    handle_api_error(resp, "view secret")
    print_result(resp.json(), fmt=output)


@secret_group.command(name="history")
@click.argument("account_id")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def secret_history(account_id, output):
    """View password change history for an account."""
    session = Session.load()
    client = require_auth(session)
    resp = client.get(f"accounts/account-secrets/{account_id}/histories/")
    handle_api_error(resp, "get secret history")
    print_result(resp.json(), fmt=output)


# ─── Account Templates ──────────────────────────────────────


@account_group.group(name="template")
def template_group():
    """Manage account templates."""
    pass


@template_group.command(name="list")
@click.option("--search", "-s", default=None, help="Search by name")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def list_templates(search, output):
    """List account templates."""
    session = Session.load()
    client = require_auth(session)

    params = {}
    if search:
        params["search"] = search

    resp = client.get("accounts/account-templates/", params=params)
    handle_api_error(resp, "list templates")
    print_result(resp.json(), fmt=output)
