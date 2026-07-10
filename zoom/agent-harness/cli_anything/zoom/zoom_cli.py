#!/usr/bin/env python3
"""Zoom CLI — Manage Zoom meetings, participants, and recordings from the command line.

This CLI wraps the Zoom REST API v2 via OAuth2. It covers the full
meeting lifecycle: authentication, meeting CRUD, participant management,
recording retrieval, and reporting.

Usage:
    # Setup OAuth credentials
    cli-anything-zoom auth setup --client-id <ID> --client-secret <SECRET>

    # Login via browser
    cli-anything-zoom auth login

    # Create a meeting
    cli-anything-zoom meeting create --topic "Standup" --duration 30

    # List meetings
    cli-anything-zoom meeting list

    # Interactive REPL
    cli-anything-zoom repl
"""

import sys
import os
import json
import shlex
import webbrowser
import click
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli_anything.zoom.core import auth as auth_mod
from cli_anything.zoom.core import meetings as meet_mod
from cli_anything.zoom.core import participants as part_mod
from cli_anything.zoom.core import recordings as rec_mod

# Global state
_json_output = False
_repl_mode = False


def output(data, message: str = ""):
    """Print output in JSON or human-readable format."""
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        if isinstance(data, dict):
            _print_dict(data)
        elif isinstance(data, list):
            _print_list(data)
        else:
            click.echo(str(data))


def _print_dict(d: dict, indent: int = 0):
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            click.echo(f"{prefix}{k}:")
            _print_dict(v, indent + 1)
        elif isinstance(v, list):
            click.echo(f"{prefix}{k}:")
            _print_list(v, indent + 1)
        else:
            click.echo(f"{prefix}{k}: {v}")


def _print_list(items: list, indent: int = 0):
    prefix = "  " * indent
    for i, item in enumerate(items):
        if isinstance(item, dict):
            click.echo(f"{prefix}[{i}]")
            _print_dict(item, indent + 1)
        else:
            click.echo(f"{prefix}- {item}")


def handle_error(func):
    """Decorator for consistent error handling."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if _json_output:
                click.echo(json.dumps({
                    "error": str(e),
                    "type": type(e).__name__,
                }))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


# ── Main CLI Group ──────────────────────────────────────────────
@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.pass_context
def cli(ctx, use_json):
    """Zoom CLI — Meeting management from the command line.

    Run without a subcommand to enter interactive REPL mode.
    """
    global _json_output
    _json_output = use_json

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── Auth Commands ───────────────────────────────────────────────
@cli.group()
def auth():
    """Authentication and OAuth2 setup."""
    pass


@auth.command("setup")
@click.option("--client-id", required=True, help="Zoom OAuth app Client ID")
@click.option("--client-secret", required=True, help="Zoom OAuth app Client Secret")
@click.option("--redirect-uri", default="http://localhost:4199/callback",
              help="OAuth redirect URI")
@handle_error
def auth_setup(client_id, client_secret, redirect_uri):
    """Configure OAuth app credentials."""
    result = auth_mod.setup_oauth(client_id, client_secret, redirect_uri)
    output(result, "OAuth app configured successfully.")


@auth.command("login")
@click.option("--code", default=None,
              help="Authorization code (for manual flow)")
@handle_error
def auth_login(code):
    """Login via OAuth2 browser flow.

    Opens a browser for Zoom authorization. After approving,
    tokens are saved locally for subsequent API calls.

    Use --code if you need to manually paste the authorization code.
    """
    if code:
        result = auth_mod.login_with_code(code)
    else:
        result = auth_mod.login()
    output(result, "Login successful.")


@auth.command("status")
@handle_error
def auth_status():
    """Check authentication status."""
    result = auth_mod.get_auth_status()
    output(result)


@auth.command("logout")
@handle_error
def auth_logout():
    """Remove saved tokens."""
    result = auth_mod.logout()
    output(result, "Logged out.")


# ── Meeting Commands ────────────────────────────────────────────
@cli.group()
def meeting():
    """Meeting management commands."""
    pass


@meeting.command("create")
@click.option("--topic", "-t", required=True, help="Meeting topic/title")
@click.option("--start-time", "-s", default=None,
              help="Start time (ISO 8601, e.g., 2025-01-15T10:00:00Z)")
@click.option("--duration", "-d", type=int, default=60, help="Duration in minutes")
@click.option("--timezone", default="UTC", help="Timezone (e.g., Asia/Shanghai)")
@click.option("--agenda", default="", help="Meeting description/agenda")
@click.option("--password", default=None, help="Meeting password")
@click.option("--auto-recording", type=click.Choice(["none", "local", "cloud"]),
              default="none", help="Auto-recording mode")
@click.option("--waiting-room", is_flag=True, help="Enable waiting room")
@click.option("--join-before-host", is_flag=True, help="Allow join before host")
@click.option("--no-mute", is_flag=True, help="Don't mute participants on entry")
@handle_error
def meeting_create(topic, start_time, duration, timezone, agenda, password,
                   auto_recording, waiting_room, join_before_host, no_mute):
    """Create a new Zoom meeting."""
    result = meet_mod.create_meeting(
        topic=topic,
        start_time=start_time,
        duration=duration,
        timezone=timezone,
        agenda=agenda,
        password=password,
        auto_recording=auto_recording,
        waiting_room=waiting_room,
        join_before_host=join_before_host,
        mute_upon_entry=not no_mute,
    )
    output(result, f"Meeting created: {topic}")


@meeting.command("list")
@click.option("--status", "-s",
              type=click.Choice(["upcoming", "scheduled", "live", "pending"]),
              default="upcoming", help="Meeting status filter")
@click.option("--page-size", type=int, default=30, help="Results per page")
@handle_error
def meeting_list(status, page_size):
    """List meetings."""
    result = meet_mod.list_meetings(status=status, page_size=page_size)
    output(result, f"Meetings ({status}):")


@meeting.command("info")
@click.argument("meeting_id")
@handle_error
def meeting_info(meeting_id):
    """Get meeting details."""
    result = meet_mod.get_meeting(meeting_id)
    output(result)


@meeting.command("update")
@click.argument("meeting_id")
@click.option("--topic", "-t", default=None, help="New topic")
@click.option("--start-time", "-s", default=None, help="New start time")
@click.option("--duration", "-d", type=int, default=None, help="New duration")
@click.option("--timezone", default=None, help="New timezone")
@click.option("--agenda", default=None, help="New agenda")
@click.option("--password", default=None, help="New password")
@click.option("--auto-recording", type=click.Choice(["none", "local", "cloud"]),
              default=None, help="Auto-recording mode")
@handle_error
def meeting_update(meeting_id, topic, start_time, duration, timezone,
                   agenda, password, auto_recording):
    """Update a meeting."""
    result = meet_mod.update_meeting(
        meeting_id=meeting_id,
        topic=topic,
        start_time=start_time,
        duration=duration,
        timezone=timezone,
        agenda=agenda,
        password=password,
        auto_recording=auto_recording,
    )
    output(result, f"Meeting {meeting_id} updated.")


@meeting.command("delete")
@click.argument("meeting_id")
@click.option("--confirm", is_flag=True, help="Skip confirmation")
@handle_error
def meeting_delete(meeting_id, confirm):
    """Delete a meeting."""
    if not confirm and not _repl_mode:
        click.confirm(f"Delete meeting {meeting_id}?", abort=True)
    result = meet_mod.delete_meeting(meeting_id)
    output(result, f"Meeting {meeting_id} deleted.")


@meeting.command("join")
@click.argument("meeting_id")
@handle_error
def meeting_join(meeting_id):
    """Open meeting join URL in browser."""
    urls = meet_mod.get_join_url(meeting_id)
    join_url = urls.get("join_url", "")
    if not join_url:
        raise RuntimeError("No join URL available for this meeting.")
    webbrowser.open(join_url)
    output(urls, f"Opening meeting in browser...")


@meeting.command("start")
@click.argument("meeting_id")
@handle_error
def meeting_start(meeting_id):
    """Open meeting start URL in browser (host only)."""
    urls = meet_mod.get_join_url(meeting_id)
    start_url = urls.get("start_url", "")
    if not start_url:
        raise RuntimeError("No start URL available for this meeting.")
    webbrowser.open(start_url)
    output(urls, f"Starting meeting in browser...")


# ── Participant Commands ────────────────────────────────────────
@cli.group()
def participant():
    """Participant management commands."""
    pass


@participant.command("add")
@click.argument("meeting_id")
@click.option("--email", "-e", required=True, help="Participant email")
@click.option("--first-name", default="", help="First name")
@click.option("--last-name", default="", help="Last name")
@handle_error
def participant_add(meeting_id, email, first_name, last_name):
    """Register a participant for a meeting."""
    result = part_mod.add_registrant(
        meeting_id, email=email,
        first_name=first_name, last_name=last_name,
    )
    output(result, f"Registered: {email}")


@participant.command("add-batch")
@click.argument("meeting_id")
@click.argument("csv_file", type=click.Path(exists=True))
@handle_error
def participant_add_batch(meeting_id, csv_file):
    """Batch register participants from a CSV file.

    CSV format: email,first_name,last_name (header row required)
    """
    import csv
    registrants = []
    with open(csv_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            registrants.append({
                "email": row.get("email", ""),
                "first_name": row.get("first_name", ""),
                "last_name": row.get("last_name", ""),
            })

    result = part_mod.add_batch_registrants(meeting_id, registrants)
    output(result, f"Batch registration: {result['registered']} succeeded, {result['failed']} failed")


@participant.command("list")
@click.argument("meeting_id")
@click.option("--status", "-s",
              type=click.Choice(["approved", "pending", "denied"]),
              default="approved", help="Registration status filter")
@handle_error
def participant_list(meeting_id, status):
    """List registered participants."""
    result = part_mod.list_registrants(meeting_id, status=status)
    output(result, f"Registrants ({status}):")


@participant.command("remove")
@click.argument("meeting_id")
@click.argument("registrant_id")
@handle_error
def participant_remove(meeting_id, registrant_id):
    """Cancel a participant's registration."""
    result = part_mod.remove_registrant(meeting_id, registrant_id)
    output(result, "Registration cancelled.")


@participant.command("attended")
@click.argument("meeting_id", metavar="MEETING_UUID")
@handle_error
def participant_attended(meeting_id):
    """List participants who attended a past meeting.

    Requires the meeting UUID (not the numeric ID).
    """
    result = part_mod.list_past_participants(meeting_id)
    output(result, "Past participants:")


# ── Recording Commands ──────────────────────────────────────────
@cli.group()
def recording():
    """Cloud recording management."""
    pass


@recording.command("list")
@click.option("--from", "from_date", default="", help="Start date (YYYY-MM-DD)")
@click.option("--to", "to_date", default="", help="End date (YYYY-MM-DD)")
@click.option("--page-size", type=int, default=30, help="Results per page")
@handle_error
def recording_list(from_date, to_date, page_size):
    """List cloud recordings."""
    result = rec_mod.list_recordings(
        from_date=from_date, to_date=to_date, page_size=page_size,
    )
    output(result, "Cloud recordings:")


@recording.command("files")
@click.argument("meeting_id")
@handle_error
def recording_files(meeting_id):
    """List recording files for a specific meeting."""
    result = rec_mod.get_meeting_recordings(meeting_id)
    output(result)


@recording.command("download")
@click.argument("download_url")
@click.argument("output_path")
@click.option("--overwrite", is_flag=True, help="Overwrite existing file")
@handle_error
def recording_download(download_url, output_path, overwrite):
    """Download a recording file.

    DOWNLOAD_URL: The download URL from 'recording files' output.
    OUTPUT_PATH: Local file path to save the recording.
    """
    result = rec_mod.download_recording(download_url, output_path, overwrite)
    output(result, f"Downloaded to: {output_path}")


@recording.command("delete")
@click.argument("meeting_id")
@click.option("--confirm", is_flag=True, help="Skip confirmation")
@handle_error
def recording_delete(meeting_id, confirm):
    """Delete all recordings for a meeting."""
    if not confirm and not _repl_mode:
        click.confirm(f"Delete recordings for meeting {meeting_id}?", abort=True)
    result = rec_mod.delete_recording(meeting_id)
    output(result, "Recordings deleted.")


# ── REPL ─────────────────────────────────────────────────────────
@cli.command()
@handle_error
def repl():
    """Start interactive REPL session."""
    from cli_anything.zoom.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True

    skin = ReplSkin("zoom", version="1.0.1")
    skin.print_banner()

    pt_session = skin.create_prompt_session()

    _repl_commands = {
        "auth":        "setup|login|status|logout",
        "meeting":     "create|list|info|update|delete|join|start",
        "participant": "add|add-batch|list|remove|attended",
        "recording":   "list|files|download|delete",
        "help":        "Show this help",
        "quit":        "Exit REPL",
    }

    # Check auth status on start
    try:
        status = auth_mod.get_auth_status()
        if status.get("authenticated"):
            skin.success(f"Authenticated as: {status.get('user', 'unknown')}")
        elif status.get("configured"):
            skin.warning("OAuth configured but not logged in. Run: auth login")
        else:
            skin.info("Not configured. Run: auth setup --client-id <ID> --client-secret <SECRET>")
    except Exception:
        skin.info("Run 'auth setup' to configure OAuth credentials.")

    while True:
        try:
            # Determine context for prompt
            try:
                status = auth_mod.get_auth_status()
                context = status.get("user", "") if status.get("authenticated") else ""
            except Exception:
                context = ""

            line = skin.get_input(pt_session, context=context)
            if not line:
                continue
            if line.lower() in ("quit", "exit", "q"):
                skin.print_goodbye()
                break
            if line.lower() == "help":
                skin.help(_repl_commands)
                continue

            # Parse and execute command (shlex handles quoted strings with spaces)
            try:
                args = shlex.split(line)
            except ValueError:
                args = line.split()
            try:
                cli.main(args, standalone_mode=False)
            except SystemExit:
                pass
            except click.exceptions.UsageError as e:
                skin.warning(f"Usage error: {e}")
            except Exception as e:
                skin.error(f"{e}")

        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

    _repl_mode = False


# ── Entry Point ──────────────────────────────────────────────────
def main():
    cli()


if __name__ == "__main__":
    main()
