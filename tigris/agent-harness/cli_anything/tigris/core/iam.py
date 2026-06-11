"""IAM commands -- policies and users.

Wraps `tigris iam policies` and `tigris iam users`. Together with
`access-key assign`, IAM policies let agents/orgs grant narrow, auditable
permissions to programmatic clients.
"""

import json as json_mod
import click

from ..utils.tigris_backend import TigrisBackend, TigrisCliError


@click.group("iam")
@click.pass_context
def iam_group(ctx):
    """IAM — policies and users (wraps `tigris iam`)."""
    pass


# ── policies ──────────────────────────────────────────────────────────


@iam_group.group("policy")
@click.pass_context
def policy_group(ctx):
    """Manage IAM policies."""
    pass


@policy_group.command("list")
@click.pass_context
def list_policies(ctx):
    """List all IAM policies."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        policies = backend.list_iam_policies()
        if use_json:
            click.echo(json_mod.dumps(policies, indent=2))
        else:
            if not policies:
                skin.info("No IAM policies found.")
                return
            if isinstance(policies, list):
                headers = ["Name", "ARN / ID", "Created"]
                rows = []
                for p in policies:
                    if not isinstance(p, dict):
                        rows.append([str(p), "", ""])
                        continue
                    rows.append([
                        str(p.get("name") or "?"),
                        str(p.get("arn") or p.get("id") or ""),
                        str(p.get("created") or p.get("createdAt") or ""),
                    ])
                skin.table(headers, rows)
            else:
                click.echo(policies)
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to list policies: {e}")
        raise SystemExit(1)


@policy_group.command("create")
@click.argument("name")
@click.option("--document", required=True,
              help="Path to a JSON policy document")
@click.pass_context
def create_policy(ctx, name, document):
    """Create a new IAM policy from a JSON document."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        result = backend.create_iam_policy(name, document)
        if use_json:
            click.echo(json_mod.dumps(result or {"name": name, "status": "created"}, indent=2))
        else:
            skin.success(f"Policy '{name}' created from {document}")
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to create policy: {e}")
        raise SystemExit(1)


# ── users ─────────────────────────────────────────────────────────────


@iam_group.group("user")
@click.pass_context
def user_group(ctx):
    """Manage organization users and invitations."""
    pass


@user_group.command("list")
@click.pass_context
def list_users(ctx):
    """List all users in the current organization."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        users = backend.list_iam_users()
        if use_json:
            click.echo(json_mod.dumps(users, indent=2))
        else:
            if not users:
                skin.info("No users found.")
                return
            if isinstance(users, list):
                headers = ["Email", "Role", "Status"]
                rows = []
                for u in users:
                    if not isinstance(u, dict):
                        rows.append([str(u), "", ""])
                        continue
                    rows.append([
                        str(u.get("email") or "?"),
                        str(u.get("role") or ""),
                        str(u.get("status") or ""),
                    ])
                skin.table(headers, rows)
            else:
                click.echo(users)
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to list users: {e}")
        raise SystemExit(1)


@user_group.command("invite")
@click.argument("email")
@click.option("--role", default="member",
              help="Role to assign on join (default: member)")
@click.pass_context
def invite_user(ctx, email, role):
    """Invite a user by email."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        result = backend.invite_iam_user(email, role=role)
        if use_json:
            click.echo(json_mod.dumps(
                result or {"email": email, "role": role, "status": "invited"},
                indent=2,
            ))
        else:
            skin.success(f"Invited {email} as {role}")
    except TigrisCliError as e:
        _emit_error(use_json, skin, f"Failed to invite user: {e}")
        raise SystemExit(1)


def _emit_error(use_json: bool, skin, message: str) -> None:
    if use_json:
        click.echo(json_mod.dumps({"error": message}, indent=2))
    elif skin:
        skin.error(message)
    else:
        click.echo(message, err=True)
