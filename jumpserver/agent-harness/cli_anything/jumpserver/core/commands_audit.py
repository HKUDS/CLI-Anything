"""
Audit and operations commands for JumpServer CLI.

Manages audit logs, login logs, operate logs, and job execution.
"""
import click

from cli_anything.jumpserver.core.session import Session
from cli_anything.jumpserver.utils import (
    require_auth,
    handle_api_error,
    print_result,
)


@click.group(name="audit")
def audit_group():
    """View audit logs and reports."""
    pass


# ─── Login Logs ──────────────────────────────────────────────


@audit_group.command(name="login")
@click.option("--search", "-s", default=None, help="Search by username")
@click.option("--status", default=None, type=click.Choice(["success", "failed"]), help="Login status")
@click.option("--limit", default=20, help="Results per page")
@click.option("--offset", default=0, help="Pagination offset")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def login_logs(search, status, limit, offset, output):
    """View user login audit logs."""
    sess = Session.load()
    client = require_auth(sess)

    params = {"limit": limit, "offset": offset}
    if search:
        params["search"] = search
    if status:
        params["status"] = "1" if status == "success" else "0"

    resp = client.get("audits/login-logs/", params=params)
    handle_api_error(resp, "get login logs")
    print_result(resp.json(), fmt=output)


# ─── Operate Logs ────────────────────────────────────────────


@audit_group.command(name="operate")
@click.option("--search", "-s", default=None, help="Search by user or resource")
@click.option("--user", "-u", default=None, help="Filter by user ID")
@click.option("--action", "-a", default=None, type=click.Choice(["create", "update", "delete"]), help="Action type")
@click.option("--resource", "-r", default=None, help="Resource type (e.g., Asset, User)")
@click.option("--limit", default=20, help="Results per page")
@click.option("--offset", default=0, help="Pagination offset")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--columns", "-c", default="user,action,resource_type,resource,datetime", help="Comma-separated column names")
def operate_logs(search, user, action, resource, limit, offset, output, columns):
    """View resource operation audit logs."""
    sess = Session.load()
    client = require_auth(sess)

    params = {"limit": limit, "offset": offset}
    if search:
        params["search"] = search
    if user:
        params["user"] = user
    if action:
        params["action"] = action
    if resource:
        params["resource_type"] = resource

    resp = client.get("audits/operate-logs/", params=params)
    handle_api_error(resp, "get operate logs")
    print_result(resp.json(), fmt=output, columns=columns)


# ─── FTP Logs ────────────────────────────────────────────────


@audit_group.command(name="ftp")
@click.option("--search", "-s", default=None, help="Search by user or filename")
@click.option("--user", "-u", default=None, help="Filter by user ID")
@click.option("--limit", default=20, help="Results per page")
@click.option("--offset", default=0, help="Pagination offset")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def ftp_logs(search, user, limit, offset, output):
    """View FTP file transfer audit logs."""
    sess = Session.load()
    client = require_auth(sess)

    params = {"limit": limit, "offset": offset}
    if search:
        params["search"] = search
    if user:
        params["user"] = user

    resp = client.get("audits/ftp-logs/", params=params)
    handle_api_error(resp, "get FTP logs")
    print_result(resp.json(), fmt=output)


# ─── Password Change Logs ─────────────────────────────────────


@audit_group.command(name="password")
@click.option("--search", "-s", default=None, help="Search by user")
@click.option("--limit", default=20, help="Results per page")
@click.option("--offset", default=0, help="Pagination offset")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def password_logs(search, limit, offset, output):
    """View password change audit logs."""
    sess = Session.load()
    client = require_auth(sess)

    params = {"limit": limit, "offset": offset}
    if search:
        params["search"] = search

    resp = client.get("audits/password-change-logs/", params=params)
    handle_api_error(resp, "get password change logs")
    print_result(resp.json(), fmt=output)


# ─── Activity Logs ────────────────────────────────────────────


@audit_group.command(name="activity")
@click.option("--limit", default=20, help="Results per page")
@click.option("--offset", default=0, help="Pagination offset")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def activity_logs(limit, offset, output):
    """View user activity logs."""
    sess = Session.load()
    client = require_auth(sess)

    params = {"limit": limit, "offset": offset}
    resp = client.get("audits/activities/", params=params)
    handle_api_error(resp, "get activity logs")
    print_result(resp.json(), fmt=output)


# ─── Ops / Job Management ────────────────────────────────────


@click.group(name="ops")
def ops_group():
    """Manage operations and job execution."""
    pass


@ops_group.command(name="job-list")
@click.option("--search", "-s", default=None, help="Search by name")
@click.option("--limit", default=20, help="Results per page")
@click.option("--offset", default=0, help="Pagination offset")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def job_list(search, limit, offset, output):
    """List execution jobs."""
    sess = Session.load()
    client = require_auth(sess)

    params = {"limit": limit, "offset": offset}
    if search:
        params["search"] = search

    resp = client.get("ops/jobs/", params=params)
    handle_api_error(resp, "list jobs")
    print_result(resp.json(), fmt=output)


@ops_group.command(name="job-log")
@click.argument("execution_id")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def job_log(execution_id, output):
    """Get job execution log."""
    sess = Session.load()
    client = require_auth(sess)
    resp = client.get(f"ops/job-executions/{execution_id}/")
    handle_api_error(resp, "get job execution")
    print_result(resp.json(), fmt=output)


@ops_group.command(name="adhoc-list")
@click.option("--search", "-s", default=None, help="Search by name")
@click.option("--limit", default=20, help="Results per page")
@click.option("--offset", default=0, help="Pagination offset")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def adhoc_list(search, limit, offset, output):
    """List ad-hoc command executions."""
    sess = Session.load()
    client = require_auth(sess)

    params = {"limit": limit, "offset": offset}
    if search:
        params["search"] = search

    resp = client.get("ops/adhocs/", params=params)
    handle_api_error(resp, "list adhoc executions")
    print_result(resp.json(), fmt=output)


@ops_group.command(name="playbook-list")
@click.option("--search", "-s", default=None, help="Search by name")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def playbook_list(search, output):
    """List Ansible playbooks."""
    sess = Session.load()
    client = require_auth(sess)

    params = {}
    if search:
        params["search"] = search

    resp = client.get("ops/playbooks/", params=params)
    handle_api_error(resp, "list playbooks")
    print_result(resp.json(), fmt=output)
