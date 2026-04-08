#!/usr/bin/env python3
"""RMS CLI — Teltonika RMS device management and monitoring.

Usage:
    cli-anything-rms devices list
    cli-anything-rms devices get <id>
    cli-anything-rms alerts list
    cli-anything-rms  # Interactive REPL
"""

from __future__ import annotations

import sys
import os
import json
import shlex
import functools
import click
from pathlib import Path

from cli_anything.rms.core.session import Session
from cli_anything.rms.utils.rms_backend import get_api_token, load_config, save_config

_json_output = False
_repl_mode = False
_token = None
_session = None


def _get_session():
    global _session
    if _session is None:
        sf = str(Path.home() / ".cli-anything-rms" / "session.json")
        _session = Session(session_file=sf)
    return _session


def _get_token():
    return _token or get_api_token()


def output(data, message: str = ""):
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
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (RuntimeError, ValueError) as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": type(e).__name__}))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)

    return wrapper


# ── Root CLI group ─────────────────────────────────────────────────────


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.option("--token", "token_opt", type=str, default=None, help="RMS API token")
@click.pass_context
def cli(ctx, use_json, token_opt):
    """Teltonika RMS CLI — manage devices, alerts, and more."""
    global _json_output, _token
    _json_output = use_json
    _token = token_opt
    ctx.ensure_object(dict)
    ctx.obj["token"] = token_opt

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── Devices ────────────────────────────────────────────────────────────


@cli.group()
def devices():
    """Device management."""


@devices.command("list")
@click.option("--status", type=click.Choice(["online", "offline"]), default=None)
@click.option("--tag", multiple=True, help="Filter by tag(s)")
@click.option("--limit", type=int, default=25)
@click.option("--offset", type=int, default=0)
@click.option("--sort", type=str, default=None, help="Sort field (prefix - for desc)")
@handle_error
def devices_list(status, tag, limit, offset, sort):
    """List devices."""
    from cli_anything.rms.core.devices import list_devices
    result = list_devices(_get_token(), status=status, tag=list(tag) if tag else None,
                          limit=limit, offset=offset, sort=sort)
    output(result, f"Devices ({result.get('meta', {}).get('total', '?')} total)")


@devices.command("get")
@click.argument("device_id")
@handle_error
def devices_get(device_id):
    """Get device details."""
    from cli_anything.rms.core.devices import get_device
    result = get_device(_get_token(), device_id)
    _get_session().set_last_device(device_id)
    output(result, f"Device {device_id}")


@devices.command("update")
@click.argument("device_id")
@click.option("--name", type=str, default=None)
@click.option("--tag", multiple=True)
@handle_error
def devices_update(device_id, name, tag):
    """Update device."""
    from cli_anything.rms.core.devices import update_device
    data = {}
    if name:
        data["name"] = name
    if tag:
        data["tags"] = list(tag)
    result = update_device(_get_token(), device_id, data)
    output(result, f"Updated device {device_id}")


@devices.command("delete")
@click.argument("device_id")
@handle_error
def devices_delete(device_id):
    """Delete device."""
    from cli_anything.rms.core.devices import delete_device
    result = delete_device(_get_token(), device_id)
    output(result, f"Deleted device {device_id}")


# ── Companies ──────────────────────────────────────────────────────────


@cli.group()
def companies():
    """Company management."""


@companies.command("list")
@click.option("--limit", type=int, default=25)
@click.option("--offset", type=int, default=0)
@handle_error
def companies_list(limit, offset):
    """List companies."""
    from cli_anything.rms.core.companies import list_companies
    result = list_companies(_get_token(), limit=limit, offset=offset)
    output(result, "Companies")


@companies.command("get")
@click.argument("company_id")
@handle_error
def companies_get(company_id):
    """Get company details."""
    from cli_anything.rms.core.companies import get_company
    result = get_company(_get_token(), company_id)
    output(result, f"Company {company_id}")


@companies.command("create")
@click.option("--name", required=True)
@handle_error
def companies_create(name):
    """Create company."""
    from cli_anything.rms.core.companies import create_company
    result = create_company(_get_token(), {"name": name})
    output(result, f"Created company: {name}")


@companies.command("update")
@click.argument("company_id")
@click.option("--name", type=str, default=None)
@handle_error
def companies_update(company_id, name):
    """Update company."""
    from cli_anything.rms.core.companies import update_company
    data = {}
    if name:
        data["name"] = name
    if not data:
        raise click.UsageError("No fields to update")
    result = update_company(_get_token(), company_id, data)
    output(result, f"Updated company {company_id}")


@companies.command("delete")
@click.argument("company_id")
@handle_error
def companies_delete(company_id):
    """Delete company."""
    from cli_anything.rms.core.companies import delete_company
    result = delete_company(_get_token(), company_id)
    output(result, f"Deleted company {company_id}")


# ── Users ──────────────────────────────────────────────────────────────


@cli.group()
def users():
    """User management."""


@users.command("list")
@click.option("--limit", type=int, default=25)
@click.option("--offset", type=int, default=0)
@handle_error
def users_list(limit, offset):
    """List users."""
    from cli_anything.rms.core.users import list_users
    result = list_users(_get_token(), limit=limit, offset=offset)
    output(result, "Users")


@users.command("get")
@click.argument("user_id")
@handle_error
def users_get(user_id):
    """Get user details."""
    from cli_anything.rms.core.users import get_user
    result = get_user(_get_token(), user_id)
    output(result, f"User {user_id}")


@users.command("invite")
@click.option("--email", required=True)
@click.option("--role", type=str, default=None)
@handle_error
def users_invite(email, role):
    """Invite user."""
    from cli_anything.rms.core.users import invite_user
    data = {"email": email}
    if role:
        data["role"] = role
    result = invite_user(_get_token(), data)
    output(result, f"Invited {email}")


@users.command("update")
@click.argument("user_id")
@click.option("--role", type=str, default=None)
@handle_error
def users_update(user_id, role):
    """Update user."""
    from cli_anything.rms.core.users import update_user
    data = {}
    if role:
        data["role"] = role
    if not data:
        raise click.UsageError("No fields to update")
    result = update_user(_get_token(), user_id, data)
    output(result, f"Updated user {user_id}")


@users.command("delete")
@click.argument("user_id")
@handle_error
def users_delete(user_id):
    """Delete user."""
    from cli_anything.rms.core.users import delete_user
    result = delete_user(_get_token(), user_id)
    output(result, f"Deleted user {user_id}")


# ── Tags ───────────────────────────────────────────────────────────────


@cli.group()
def tags():
    """Tag management."""


@tags.command("list")
@click.option("--limit", type=int, default=25)
@click.option("--offset", type=int, default=0)
@handle_error
def tags_list(limit, offset):
    """List tags."""
    from cli_anything.rms.core.tags import list_tags
    result = list_tags(_get_token(), limit=limit, offset=offset)
    output(result, "Tags")


@tags.command("get")
@click.argument("tag_id")
@handle_error
def tags_get(tag_id):
    """Get tag details."""
    from cli_anything.rms.core.tags import get_tag
    result = get_tag(_get_token(), tag_id)
    output(result, f"Tag {tag_id}")


@tags.command("create")
@click.option("--name", required=True)
@handle_error
def tags_create(name):
    """Create tag."""
    from cli_anything.rms.core.tags import create_tag
    result = create_tag(_get_token(), {"name": name})
    output(result, f"Created tag: {name}")


@tags.command("update")
@click.argument("tag_id")
@click.option("--name", type=str, default=None)
@handle_error
def tags_update(tag_id, name):
    """Update tag."""
    from cli_anything.rms.core.tags import update_tag
    data = {}
    if name:
        data["name"] = name
    if not data:
        raise click.UsageError("No fields to update")
    result = update_tag(_get_token(), tag_id, data)
    output(result, f"Updated tag {tag_id}")


@tags.command("delete")
@click.argument("tag_id")
@handle_error
def tags_delete(tag_id):
    """Delete tag."""
    from cli_anything.rms.core.tags import delete_tag
    result = delete_tag(_get_token(), tag_id)
    output(result, f"Deleted tag {tag_id}")


# ── Alerts ─────────────────────────────────────────────────────────────


@cli.group()
def alerts():
    """Alert management."""


@alerts.command("list")
@click.option("--device", "device_id", type=str, default=None, help="Filter by device ID")
@click.option("--limit", type=int, default=25)
@click.option("--offset", type=int, default=0)
@handle_error
def alerts_list(device_id, limit, offset):
    """List alerts."""
    from cli_anything.rms.core.alerts import list_alerts
    result = list_alerts(_get_token(), device_id=device_id, limit=limit, offset=offset)
    output(result, "Alerts")


@alerts.command("get")
@click.argument("alert_id")
@handle_error
def alerts_get(alert_id):
    """Get alert details."""
    from cli_anything.rms.core.alerts import get_alert
    result = get_alert(_get_token(), alert_id)
    output(result, f"Alert {alert_id}")


@alerts.command("delete")
@click.argument("alert_id")
@handle_error
def alerts_delete(alert_id):
    """Delete alert."""
    from cli_anything.rms.core.alerts import delete_alert
    result = delete_alert(_get_token(), alert_id)
    output(result, f"Deleted alert {alert_id}")


@alerts.group("configs")
def alert_configs():
    """Alert configuration management."""


@alert_configs.command("list")
@click.option("--limit", type=int, default=25)
@click.option("--offset", type=int, default=0)
@handle_error
def alert_configs_list(limit, offset):
    """List alert configurations."""
    from cli_anything.rms.core.alerts import list_alert_configs
    result = list_alert_configs(_get_token(), limit=limit, offset=offset)
    output(result, "Alert configurations")


@alert_configs.command("get")
@click.argument("config_id")
@handle_error
def alert_configs_get(config_id):
    """Get alert configuration."""
    from cli_anything.rms.core.alerts import get_alert_config
    result = get_alert_config(_get_token(), config_id)
    output(result, f"Alert config {config_id}")


@alert_configs.command("create")
@click.option("--data", "data_json", required=True, help="JSON configuration data")
@handle_error
def alert_configs_create(data_json):
    """Create alert configuration."""
    from cli_anything.rms.core.alerts import create_alert_config
    data = json.loads(data_json)
    result = create_alert_config(_get_token(), data)
    output(result, "Created alert configuration")


@alert_configs.command("update")
@click.argument("config_id")
@click.option("--data", "data_json", required=True, help="JSON configuration data")
@handle_error
def alert_configs_update(config_id, data_json):
    """Update alert configuration."""
    from cli_anything.rms.core.alerts import update_alert_config
    data = json.loads(data_json)
    result = update_alert_config(_get_token(), config_id, data)
    output(result, f"Updated alert config {config_id}")


@alert_configs.command("delete")
@click.argument("config_id")
@handle_error
def alert_configs_delete(config_id):
    """Delete alert configuration."""
    from cli_anything.rms.core.alerts import delete_alert_config
    result = delete_alert_config(_get_token(), config_id)
    output(result, f"Deleted alert config {config_id}")


# ── Configs (device configurations) ───────────────────────────────────


@cli.group()
def configs():
    """Device configuration management."""


@configs.command("list")
@click.option("--device", "device_id", type=str, default=None)
@click.option("--limit", type=int, default=25)
@click.option("--offset", type=int, default=0)
@handle_error
def configs_list(device_id, limit, offset):
    """List device configurations."""
    from cli_anything.rms.core.configs import list_configs
    result = list_configs(_get_token(), device_id=device_id, limit=limit, offset=offset)
    output(result, "Device configurations")


@configs.command("get")
@click.argument("config_id")
@handle_error
def configs_get(config_id):
    """Get device configuration."""
    from cli_anything.rms.core.configs import get_config
    result = get_config(_get_token(), config_id)
    output(result, f"Config {config_id}")


@configs.command("update")
@click.argument("config_id")
@click.option("--data", "data_json", required=True, help="JSON configuration data")
@handle_error
def configs_update(config_id, data_json):
    """Update device configuration."""
    from cli_anything.rms.core.configs import update_config
    data = json.loads(data_json)
    result = update_config(_get_token(), config_id, data)
    output(result, f"Updated config {config_id}")


# ── Remote Access ──────────────────────────────────────────────────────


@cli.group("remote-access")
def remote_access():
    """Remote access session management."""


@remote_access.command("list")
@click.option("--device", "device_id", type=str, default=None)
@click.option("--limit", type=int, default=25)
@click.option("--offset", type=int, default=0)
@handle_error
def remote_access_list(device_id, limit, offset):
    """List remote access sessions."""
    from cli_anything.rms.core.remote_access import list_sessions
    result = list_sessions(_get_token(), device_id=device_id, limit=limit, offset=offset)
    output(result, "Remote access sessions")


@remote_access.command("get")
@click.argument("session_id")
@handle_error
def remote_access_get(session_id):
    """Get remote access session."""
    from cli_anything.rms.core.remote_access import get_session
    result = get_session(_get_token(), session_id)
    output(result, f"Session {session_id}")


@remote_access.command("create")
@click.option("--device", "device_id", required=True, help="Device ID")
@click.option("--protocol", type=str, default=None)
@click.option("--port", type=int, default=None)
@handle_error
def remote_access_create(device_id, protocol, port):
    """Create remote access session."""
    from cli_anything.rms.core.remote_access import create_session
    data = {"device_id": device_id}
    if protocol:
        data["protocol"] = protocol
    if port:
        data["port"] = port
    result = create_session(_get_token(), data)
    output(result, "Created remote access session")


@remote_access.command("delete")
@click.argument("session_id")
@handle_error
def remote_access_delete(session_id):
    """Delete remote access session."""
    from cli_anything.rms.core.remote_access import delete_session
    result = delete_session(_get_token(), session_id)
    output(result, f"Deleted session {session_id}")


# ── Logs ───────────────────────────────────────────────────────────────


@cli.group()
def logs():
    """Device log management."""


@logs.command("list")
@click.option("--device", "device_id", type=str, default=None)
@click.option("--limit", type=int, default=25)
@click.option("--offset", type=int, default=0)
@handle_error
def logs_list(device_id, limit, offset):
    """List device logs."""
    from cli_anything.rms.core.logs import list_logs
    result = list_logs(_get_token(), device_id=device_id, limit=limit, offset=offset)
    output(result, "Device logs")


@logs.command("get")
@click.argument("log_id")
@handle_error
def logs_get(log_id):
    """Get log details."""
    from cli_anything.rms.core.logs import get_log
    result = get_log(_get_token(), log_id)
    output(result, f"Log {log_id}")


@logs.command("delete")
@click.argument("log_id")
@handle_error
def logs_delete(log_id):
    """Delete log."""
    from cli_anything.rms.core.logs import delete_log
    result = delete_log(_get_token(), log_id)
    output(result, f"Deleted log {log_id}")


# ── Location ───────────────────────────────────────────────────────────


@cli.group()
def location():
    """Device location."""


@location.command("get")
@click.argument("device_id")
@handle_error
def location_get(device_id):
    """Get device location."""
    from cli_anything.rms.core.location import get_location
    result = get_location(_get_token(), device_id)
    output(result, f"Location for device {device_id}")


@location.command("history")
@click.argument("device_id")
@click.option("--limit", type=int, default=25)
@click.option("--offset", type=int, default=0)
@handle_error
def location_history(device_id, limit, offset):
    """Get device location history."""
    from cli_anything.rms.core.location import list_location_history
    result = list_location_history(_get_token(), device_id, limit=limit, offset=offset)
    output(result, f"Location history for device {device_id}")


# ── Credits ────────────────────────────────────────────────────────────


@cli.group()
def credits():
    """Credit management."""


@credits.command("list")
@click.option("--limit", type=int, default=25)
@click.option("--offset", type=int, default=0)
@handle_error
def credits_list(limit, offset):
    """List credits."""
    from cli_anything.rms.core.credits import list_credits
    result = list_credits(_get_token(), limit=limit, offset=offset)
    output(result, "Credits")


@credits.command("transfer")
@click.option("--code", required=True, help="Transfer code")
@handle_error
def credits_transfer(code):
    """Transfer credits using a code."""
    from cli_anything.rms.core.credits import transfer_credits
    result = transfer_credits(_get_token(), {"code": code})
    output(result, "Credit transfer")


@credits.command("codes")
@click.option("--limit", type=int, default=25)
@click.option("--offset", type=int, default=0)
@handle_error
def credits_codes(limit, offset):
    """List credit transfer codes."""
    from cli_anything.rms.core.credits import list_transfer_codes
    result = list_transfer_codes(_get_token(), limit=limit, offset=offset)
    output(result, "Transfer codes")


# ── Files ──────────────────────────────────────────────────────────────


@cli.group()
def files():
    """File management."""


@files.command("list")
@click.option("--limit", type=int, default=25)
@click.option("--offset", type=int, default=0)
@handle_error
def files_list(limit, offset):
    """List files."""
    from cli_anything.rms.core.files import list_files
    result = list_files(_get_token(), limit=limit, offset=offset)
    output(result, "Files")


@files.command("get")
@click.argument("file_id")
@handle_error
def files_get(file_id):
    """Get file details."""
    from cli_anything.rms.core.files import get_file
    result = get_file(_get_token(), file_id)
    output(result, f"File {file_id}")


@files.command("upload")
@click.argument("file_path", type=click.Path(exists=True))
@handle_error
def files_upload(file_path):
    """Upload a file."""
    from cli_anything.rms.core.files import upload_file
    result = upload_file(_get_token(), file_path)
    output(result, f"Uploaded {file_path}")


@files.command("delete")
@click.argument("file_id")
@handle_error
def files_delete(file_id):
    """Delete file."""
    from cli_anything.rms.core.files import delete_file
    result = delete_file(_get_token(), file_id)
    output(result, f"Deleted file {file_id}")


# ── Reports ────────────────────────────────────────────────────────────


@cli.group()
def reports():
    """Report management."""


@reports.command("list")
@click.option("--limit", type=int, default=25)
@click.option("--offset", type=int, default=0)
@handle_error
def reports_list(limit, offset):
    """List reports."""
    from cli_anything.rms.core.reports import list_reports
    result = list_reports(_get_token(), limit=limit, offset=offset)
    output(result, "Reports")


@reports.command("get")
@click.argument("report_id")
@handle_error
def reports_get(report_id):
    """Get report."""
    from cli_anything.rms.core.reports import get_report
    result = get_report(_get_token(), report_id)
    output(result, f"Report {report_id}")


@reports.command("create")
@click.option("--template", "template_id", required=True, help="Report template ID")
@click.option("--name", type=str, default=None)
@handle_error
def reports_create(template_id, name):
    """Create report."""
    from cli_anything.rms.core.reports import create_report
    data = {"template_id": template_id}
    if name:
        data["name"] = name
    result = create_report(_get_token(), data)
    output(result, "Created report")


@reports.command("delete")
@click.argument("report_id")
@handle_error
def reports_delete(report_id):
    """Delete report."""
    from cli_anything.rms.core.reports import delete_report
    result = delete_report(_get_token(), report_id)
    output(result, f"Deleted report {report_id}")


@reports.group("templates")
def report_templates():
    """Report template management."""


@report_templates.command("list")
@click.option("--limit", type=int, default=25)
@click.option("--offset", type=int, default=0)
@handle_error
def report_templates_list(limit, offset):
    """List report templates."""
    from cli_anything.rms.core.reports import list_templates
    result = list_templates(_get_token(), limit=limit, offset=offset)
    output(result, "Report templates")


@report_templates.command("get")
@click.argument("template_id")
@handle_error
def report_templates_get(template_id):
    """Get report template."""
    from cli_anything.rms.core.reports import get_template
    result = get_template(_get_token(), template_id)
    output(result, f"Template {template_id}")


@report_templates.command("create")
@click.option("--data", "data_json", required=True, help="JSON template data")
@handle_error
def report_templates_create(data_json):
    """Create report template."""
    from cli_anything.rms.core.reports import create_template
    data = json.loads(data_json)
    result = create_template(_get_token(), data)
    output(result, "Created report template")


@report_templates.command("update")
@click.argument("template_id")
@click.option("--data", "data_json", required=True, help="JSON template data")
@handle_error
def report_templates_update(template_id, data_json):
    """Update report template."""
    from cli_anything.rms.core.reports import update_template
    data = json.loads(data_json)
    result = update_template(_get_token(), template_id, data)
    output(result, f"Updated template {template_id}")


@report_templates.command("delete")
@click.argument("template_id")
@handle_error
def report_templates_delete(template_id):
    """Delete report template."""
    from cli_anything.rms.core.reports import delete_template
    result = delete_template(_get_token(), template_id)
    output(result, f"Deleted template {template_id}")


# ── Hotspots ───────────────────────────────────────────────────────────


@cli.group()
def hotspots():
    """Device hotspot management."""


@hotspots.command("list")
@click.option("--device", "device_id", type=str, default=None)
@click.option("--limit", type=int, default=25)
@click.option("--offset", type=int, default=0)
@handle_error
def hotspots_list(device_id, limit, offset):
    """List hotspots."""
    from cli_anything.rms.core.hotspots import list_hotspots
    result = list_hotspots(_get_token(), device_id=device_id, limit=limit, offset=offset)
    output(result, "Hotspots")


@hotspots.command("get")
@click.argument("hotspot_id")
@handle_error
def hotspots_get(hotspot_id):
    """Get hotspot details."""
    from cli_anything.rms.core.hotspots import get_hotspot
    result = get_hotspot(_get_token(), hotspot_id)
    output(result, f"Hotspot {hotspot_id}")


@hotspots.command("create")
@click.option("--device", "device_id", required=True, help="Device ID")
@click.option("--name", required=True)
@handle_error
def hotspots_create(device_id, name):
    """Create hotspot."""
    from cli_anything.rms.core.hotspots import create_hotspot
    result = create_hotspot(_get_token(), {"device_id": device_id, "name": name})
    output(result, f"Created hotspot: {name}")


@hotspots.command("update")
@click.argument("hotspot_id")
@click.option("--name", type=str, default=None)
@handle_error
def hotspots_update(hotspot_id, name):
    """Update hotspot."""
    from cli_anything.rms.core.hotspots import update_hotspot
    data = {}
    if name:
        data["name"] = name
    if not data:
        raise click.UsageError("No fields to update")
    result = update_hotspot(_get_token(), hotspot_id, data)
    output(result, f"Updated hotspot {hotspot_id}")


@hotspots.command("delete")
@click.argument("hotspot_id")
@handle_error
def hotspots_delete(hotspot_id):
    """Delete hotspot."""
    from cli_anything.rms.core.hotspots import delete_hotspot
    result = delete_hotspot(_get_token(), hotspot_id)
    output(result, f"Deleted hotspot {hotspot_id}")


# ── Passwords ──────────────────────────────────────────────────────────


@cli.group()
def passwords():
    """Device password management."""


@passwords.command("get")
@click.argument("device_id")
@handle_error
def passwords_get(device_id):
    """Get device password."""
    from cli_anything.rms.core.passwords import get_password
    result = get_password(_get_token(), device_id)
    output(result, f"Password for device {device_id}")


@passwords.command("update")
@click.argument("device_id")
@click.option("--password", default=None, help="New password")
@click.option("--password-stdin", is_flag=True, help="Read password from stdin (safer than --password)")
@handle_error
def passwords_update(device_id, password, password_stdin):
    """Update device password."""
    import sys
    if password_stdin:
        password = sys.stdin.readline().rstrip("\n")
        if not password:
            raise RuntimeError("No password provided on stdin")
    if not password:
        raise RuntimeError("Provide --password or --password-stdin")
    from cli_anything.rms.core.passwords import update_password
    result = update_password(_get_token(), device_id, {"password": password})
    output(result, f"Updated password for device {device_id}")


# ── SMTP ───────────────────────────────────────────────────────────────


@cli.group()
def smtp():
    """SMTP configuration management."""


@smtp.command("list")
@click.option("--limit", type=int, default=25)
@click.option("--offset", type=int, default=0)
@handle_error
def smtp_list(limit, offset):
    """List SMTP configurations."""
    from cli_anything.rms.core.smtp import list_smtp_configs
    result = list_smtp_configs(_get_token(), limit=limit, offset=offset)
    output(result, "SMTP configurations")


@smtp.command("get")
@click.argument("config_id")
@handle_error
def smtp_get(config_id):
    """Get SMTP configuration."""
    from cli_anything.rms.core.smtp import get_smtp_config
    result = get_smtp_config(_get_token(), config_id)
    output(result, f"SMTP config {config_id}")


@smtp.command("create")
@click.option("--host", required=True)
@click.option("--port", type=int, default=None)
@click.option("--username", type=str, default=None)
@click.option("--password", type=str, default=None)
@click.option("--password-stdin", is_flag=True, help="Read password from stdin (safer than --password)")
@handle_error
def smtp_create(host, port, username, password, password_stdin):
    """Create SMTP configuration."""
    import sys as _sys
    if password_stdin:
        password = _sys.stdin.readline().rstrip("\n")
        if not password:
            raise RuntimeError("No password provided on stdin")
    from cli_anything.rms.core.smtp import create_smtp_config
    data = {"host": host}
    if port:
        data["port"] = port
    if username:
        data["username"] = username
    if password:
        data["password"] = password
    result = create_smtp_config(_get_token(), data)
    output(result, f"Created SMTP config: {host}")


@smtp.command("update")
@click.argument("config_id")
@click.option("--host", type=str, default=None)
@click.option("--port", type=int, default=None)
@click.option("--username", type=str, default=None)
@click.option("--password", type=str, default=None)
@click.option("--password-stdin", is_flag=True, help="Read password from stdin (safer than --password)")
@handle_error
def smtp_update(config_id, host, port, username, password, password_stdin):
    """Update SMTP configuration."""
    import sys as _sys
    if password_stdin:
        password = _sys.stdin.readline().rstrip("\n")
        if not password:
            raise RuntimeError("No password provided on stdin")
    from cli_anything.rms.core.smtp import update_smtp_config
    data = {}
    if host:
        data["host"] = host
    if port:
        data["port"] = port
    if username:
        data["username"] = username
    if password:
        data["password"] = password
    if not data:
        raise click.UsageError("No fields to update")
    result = update_smtp_config(_get_token(), config_id, data)
    output(result, f"Updated SMTP config {config_id}")


@smtp.command("delete")
@click.argument("config_id")
@handle_error
def smtp_delete(config_id):
    """Delete SMTP configuration."""
    from cli_anything.rms.core.smtp import delete_smtp_config
    result = delete_smtp_config(_get_token(), config_id)
    output(result, f"Deleted SMTP config {config_id}")


# ── Auth ───────────────────────────────────────────────────────────────


@cli.group()
def auth():
    """Authentication management."""


@auth.command("test")
@handle_error
def auth_test():
    """Test API connectivity."""
    from cli_anything.rms.utils.rms_backend import api_get
    token = _get_token()
    result = api_get("/devices", params={"limit": 1}, token=token)
    if result.get("success"):
        output({"status": "ok", "message": "API connection successful"}, "RMS API test passed")
    else:
        output({"status": "error", "errors": result.get("errors", [])}, "RMS API test failed")


@auth.command("status")
@handle_error
def auth_status():
    """Show current auth info."""
    token = _get_token()
    if token:
        masked = token[:8] + "..." + token[-4:] if len(token) > 12 else "***"
        output({"authenticated": True, "token": masked}, f"Token: {masked}")
    else:
        output({"authenticated": False}, "No token configured")


# ── Config ─────────────────────────────────────────────────────────────


@cli.group("config")
def config_group():
    """Local CLI configuration."""


@config_group.command("set")
@click.argument("key", type=click.Choice(["api_token", "default_limit"]))
@click.argument("value")
def config_set(key, value):
    """Set a configuration value."""
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)
    display = value[:10] + "..." if key == "api_token" and len(value) > 10 else value
    output({"key": key, "value": display}, f"Set {key} = {display}")


@config_group.command("get")
@click.argument("key", required=False)
def config_get(key):
    """Get a configuration value (or show all)."""
    cfg = load_config()
    if key:
        val = cfg.get(key)
        if val:
            if key == "api_token" and len(val) > 10:
                val = val[:10] + "..."
            output({"key": key, "value": val}, f"{key} = {val}")
        else:
            output({"key": key, "value": None}, f"{key} is not set")
    else:
        masked = {}
        for k, v in cfg.items():
            masked[k] = v[:10] + "..." if k == "api_token" and isinstance(v, str) and len(v) > 10 else v
        output(masked if masked else {}, "Configuration" if masked else "No configuration set")


@config_group.command("delete")
@click.argument("key")
def config_delete(key):
    """Delete a configuration value."""
    cfg = load_config()
    if key in cfg:
        del cfg[key]
        save_config(cfg)
        output({"deleted": key}, f"Deleted {key}")
    else:
        output({"error": f"{key} not found"}, f"{key} not found in config")


@config_group.command("path")
def config_path():
    """Show the config file path."""
    from cli_anything.rms.utils.rms_backend import CONFIG_FILE
    output({"path": str(CONFIG_FILE)}, f"Config file: {CONFIG_FILE}")


# ── Session ────────────────────────────────────────────────────────────


@cli.group("session")
def session_group():
    """Session management."""


@session_group.command("status")
@handle_error
def session_status():
    """Show session status."""
    s = _get_session()
    output(s.status(), "Session status")


@session_group.command("clear")
@handle_error
def session_clear():
    """Clear session."""
    s = _get_session()
    s.clear()
    output({"cleared": True}, "Session cleared")


@session_group.command("history")
@click.option("--limit", "-n", type=int, default=20)
@handle_error
def session_history(limit):
    """Show command history."""
    s = _get_session()
    history = s.history[-limit:]
    output(history, f"History ({len(history)} entries)")


# ── REPL ───────────────────────────────────────────────────────────────


@cli.command("repl", hidden=True)
@handle_error
def repl():
    """Enter interactive REPL mode."""
    global _repl_mode
    _repl_mode = True

    from cli_anything.rms.utils.repl_skin import ReplSkin

    skin = ReplSkin("rms", version="1.0.0")
    skin.print_banner()

    pt_session = skin.create_prompt_session()

    commands = {
        "devices list [--status S]": "List devices",
        "devices get <id>": "Get device details",
        "companies list": "List companies",
        "users list": "List users",
        "tags list": "List tags",
        "alerts list [--device ID]": "List alerts",
        "configs list [--device ID]": "List device configurations",
        "remote-access list": "List remote access sessions",
        "logs list [--device ID]": "List device logs",
        "location get <device-id>": "Get device location",
        "credits list": "List credits",
        "files list": "List files",
        "reports list": "List reports",
        "hotspots list": "List hotspots",
        "passwords get <device-id>": "Get device password",
        "smtp list": "List SMTP configs",
        "auth test": "Test API connectivity",
        "config set <key> <val>": "Set configuration",
        "config get [key]": "Show configuration",
        "session status": "Show session status",
        "help": "Show this help",
        "quit / exit": "Exit REPL",
    }

    while True:
        try:
            line = skin.get_input(pt_session, context="rms")
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

        if not line:
            continue
        if line in ("quit", "exit", "q"):
            skin.print_goodbye()
            break
        if line == "help":
            skin.help(commands)
            continue

        try:
            parts = shlex.split(line)
        except ValueError as e:
            skin.error(f"Parse error: {e}")
            continue

        try:
            cli.main(parts, standalone_mode=False)
        except SystemExit:
            pass
        except click.exceptions.UsageError as e:
            skin.error(str(e))
        except Exception as e:
            skin.error(str(e))


def main():
    cli()


if __name__ == "__main__":
    main()
