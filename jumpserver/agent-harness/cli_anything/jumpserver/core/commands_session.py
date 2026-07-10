"""
Session and terminal management commands for JumpServer CLI.

Manages sessions, terminals, commands, and replays.
"""
import click

from cli_anything.jumpserver.core.session import Session
from cli_anything.jumpserver.utils import (
    require_auth,
    handle_api_error,
    print_result,
    should_emit_human_text,
)


@click.group(name="session")
def session_group():
    """Manage terminal sessions and replays."""
    pass


@session_group.command(name="list")
@click.option("--search", "-s", default=None, help="Search by user or asset")
@click.option("--user", "-u", default=None, help="Filter by user ID")
@click.option("--asset", "-a", default=None, help="Filter by asset ID")
@click.option("--protocol", "-p", default=None, type=click.Choice(["ssh", "rdp", "vnc", "telnet", "mysql", "redis", "http", "k8s"]), help="Protocol")
@click.option("--active/--finished", default=None, help="Filter by session status")
@click.option("--limit", default=20, help="Results per page")
@click.option("--offset", default=0, help="Pagination offset")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--columns", "-c", default="id,user,asset,account,protocol,is_finished,date_start", help="Comma-separated column names")
def list_sessions(search, user, asset, protocol, active, limit, offset, output, columns):
    """List terminal sessions."""
    session = Session.load()
    client = require_auth(session)

    params = {"limit": limit, "offset": offset}
    if search:
        params["search"] = search
    if user:
        params["user"] = user
    if asset:
        params["asset"] = asset
    if protocol:
        params["protocol"] = protocol
    if active is not None:
        params["is_finished"] = str(not active).lower()

    resp = client.get("terminal/sessions/", params=params)
    handle_api_error(resp, "list sessions")
    print_result(resp.json(), fmt=output, columns=columns)


@session_group.command(name="get")
@click.argument("session_id")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def get_session(session_id, output):
    """Get session details."""
    session = Session.load()
    client = require_auth(session)
    resp = client.get(f"terminal/sessions/{session_id}/")
    handle_api_error(resp, "get session")
    print_result(resp.json(), fmt=output)


@session_group.command(name="replay")
@click.argument("session_id")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def session_replay(session_id, output):
    """Get session replay URL/info."""
    session = Session.load()
    client = require_auth(session)
    resp = client.get(f"terminal/sessions/{session_id}/replay/")
    handle_api_error(resp, "get replay")
    data = resp.json()
    print_result(data, fmt=output)

    if should_emit_human_text(output) and isinstance(data, dict):
        replay_url = data.get("url", data.get("replay_url", ""))
        if replay_url:
            click.echo(f"\n  Replay URL: {session.base_url}{replay_url}")


@session_group.command(name="kill")
@click.argument("session_id")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def kill_session(session_id, force, dry_run):
    """Kill an active session."""
    if dry_run:
        click.echo(f"[DRY RUN] Would kill session: {session_id}")
        return
    if not force:
        click.confirm(f"Kill session '{session_id}'?", abort=True)

    session = Session.load()
    client = require_auth(session)
    resp = client.post("terminal/tasks/kill-session/", data={"session": session_id})
    handle_api_error(resp, "kill session")
    click.echo(click.style(f"✓ Kill signal sent for session '{session_id}'.", fg="green"))


# ─── Commands ─────────────────────────────────────────────────


@session_group.group(name="command")
def command_group():
    """View session command history."""
    pass


@command_group.command(name="list")
@click.option("--session", "-s", default=None, help="Filter by session ID")
@click.option("--user", "-u", default=None, help="Filter by user ID")
@click.option("--search", default=None, help="Search commands")
@click.option("--risk", default=None, type=click.Choice(["0", "1", "2", "3", "4", "5"]), help="Risk level (0-5)")
@click.option("--limit", default=50, help="Results per page")
@click.option("--offset", default=0, help="Pagination offset")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--columns", "-c", default="input,user,timestamp,risk_level", help="Comma-separated column names")
def list_commands(session, user, search, risk, limit, offset, output, columns):
    """List command records."""
    sess = Session.load()
    client = require_auth(sess)

    params = {"limit": limit, "offset": offset}
    if session:
        params["session"] = session
    if user:
        params["user"] = user
    if search:
        params["search"] = search
    if risk:
        params["risk_level"] = risk

    resp = client.get("terminal/commands/", params=params)
    handle_api_error(resp, "list commands")
    print_result(resp.json(), fmt=output, columns=columns)


# ─── Terminals ─────────────────────────────────────────────────


@session_group.group(name="terminal")
def terminal_group():
    """Manage terminal components."""
    pass


@terminal_group.command(name="list")
@click.option("--search", "-s", default=None, help="Search by name")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def list_terminals(search, output):
    """List terminal components (KoKo, Lion, etc.)."""
    sess = Session.load()
    client = require_auth(sess)

    params = {}
    if search:
        params["search"] = search

    resp = client.get("terminal/terminals/", params=params)
    handle_api_error(resp, "list terminals")
    print_result(resp.json(), fmt=output)


@terminal_group.command(name="status")
@click.argument("terminal_id")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def terminal_status(terminal_id, output):
    """Get terminal component status (CPU, memory, connections)."""
    sess = Session.load()
    client = require_auth(sess)
    resp = client.get(f"terminal/terminals/{terminal_id}/status/")
    handle_api_error(resp, "get terminal status")
    print_result(resp.json(), fmt=output)
