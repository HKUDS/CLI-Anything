"""
Authentication commands for JumpServer CLI.

Handles login, logout, status, and token management.
"""
import click

from cli_anything.jumpserver.core.session import Session
from cli_anything.jumpserver.core.output import format_output
from cli_anything.jumpserver.core.state import get_state
from cli_anything.jumpserver.utils import (
    require_auth,
    handle_api_error,
    print_result,
    should_emit_human_text,
)


@click.group(name="auth")
def auth_group():
    """Authentication and session management."""
    pass


@auth_group.command(name="login")
@click.option("--url", "-u", required=True, help="JumpServer base URL (e.g., https://jumpserver.example.com)", envvar="JUMPSERVER_URL")
@click.option("--key-id", default=None, help="AccessKey ID (JMS v4 访问密钥, 永久有效)", envvar="JUMPSERVER_KEY_ID")
@click.option("--key-secret", default=None, prompt=False, hide_input=True,
              help="AccessKey Secret (JMS v4 访问密钥 Secret；建议用环境变量 JUMPSERVER_KEY_SECRET 传入，避免留在 shell 历史)",
              envvar="JUMPSERVER_KEY_SECRET")
@click.option("--username", "-n", default=None, help="Username (password login)", envvar="JUMPSERVER_USERNAME")
@click.option("--password", "-p", default=None, help="Password (password login)", envvar="JUMPSERVER_PASSWORD")
@click.option("--org", default=None, help="Organization ID (for multi-org deployments)")
@click.option("--insecure", is_flag=True, help="Disable SSL verification")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.pass_context
def login(ctx, url, key_id, key_secret, username, password, org, insecure, output):
    """Authenticate to JumpServer and store session token.

    Modes: --key-id/--key-secret (AccessKey 访问密钥, permanent, recommended
    for JMS v4) or --username/--password (session token, expires ~1h).
    """
    if not (key_id and key_secret) and not (username and password):
        # Interactive AccessKey mode: prompt (hidden) so secrets never
        # appear on the command line, in env, or in shell history.
        click.echo("Enter your JumpServer 访问密钥 (AccessKey). "
                   "Create one in the Web UI: 头像 → 安全设置/API-Key → 访问密钥")
        key_id = click.prompt("AccessKey ID")
        key_secret = click.prompt("AccessKey Secret", hide_input=True)
    session = Session(
        base_url=url.rstrip("/"),
        verify_ssl=not insecure,
    )
    if org:
        session.org_id = org

    try:
        client = session.get_client()
        if key_id:
            session.token = key_secret.strip()
            session.access_key_id = key_id.strip()
            session.auth_scheme = "Signature"
            session.token_expiry = 0.0
            session.username = username or "accesskey"
            session.save()
        else:
            result = client.login(username, password)
        user_info = client.get_current_user()
        session._current_user = user_info
        session.save()

        data = {
            "status": "authenticated",
            "username": user_info.get("username", username),
            "name": user_info.get("name", ""),
            "role": user_info.get("role", ""),
            "org_id": session.org_id or "(default)",
            "url": session.base_url,
        }
        print_result(data, fmt=output)
        if should_emit_human_text(output):
            click.echo(click.style("\n✓ Login successful. Session saved.", fg="green"))

    except Exception as e:
        session.clear()
        raise click.ClickException(f"Login failed: {e}")


@auth_group.command(name="logout")
def logout():
    """Clear the current session and remove stored credentials."""
    session = Session.load()
    if session.is_authenticated():
        session.clear()
        click.echo(click.style("✓ Logged out. Session cleared.", fg="green"))
    else:
        click.echo("No active session found.")


@auth_group.command(name="status")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def status(output):
    """Show current authentication status."""
    session = Session.load()
    if not session.is_authenticated():
        print_result({"status": "not authenticated"}, fmt=output)
        return

    try:
        client = session.get_client()
        user = client.get_current_user()

        data = {
            "status": "authenticated",
            "username": user.get("username", "unknown"),
            "name": user.get("name", ""),
            "role": user.get("role", ""),
            "email": user.get("email", ""),
            "org_id": session.org_id or "default",
            "url": session.base_url,
            "token_expires_in": (
                f"{int(session.token_expiry - __import__('time').time())}s"
                if session.token_expiry
                else "unknown"
            ),
        }
        print_result(data, fmt=output)

    except Exception as e:
        data = {
            "status": "expired",
            "url": session.base_url,
            "username": session.username,
        }
        if should_emit_human_text(output):
            click.echo(f"Session exists but API check failed: {e}")
        print_result(data, fmt=output)


@auth_group.command(name="org")
@click.argument("org_id", required=False)
@click.option("--list", "list_orgs", is_flag=True, help="List available organizations")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def org(org_id, list_orgs, output):
    """Switch or list organizations (multi-org deployments)."""
    session = Session.load()
    client = require_auth(session)

    if list_orgs:
        resp = client.get("orgs/")
        handle_api_error(resp, "list organizations")
        data = resp.json()
        print_result(data, fmt=output)
        return

    if org_id:
        resp = client.get(f"orgs/{org_id}/")
        handle_api_error(resp, "get organization")
        org_data = resp.json()
        session.org_id = org_data.get("id", org_id)
        session.org_name = org_data.get("name", "")
        session.save()
        print_result(org_data, fmt=output)
        if should_emit_human_text(output):
            click.echo(click.style(f"\n✓ Switched to organization: {session.org_name}", fg="green"))
    else:
        current = {
            "org_id": session.org_id or "(default)",
            "org_name": session.org_name or "(default)",
        }
        print_result(current, fmt=output)
