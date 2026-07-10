"""Auth commands -- login, logout, whoami.

Wraps `tigris login`, `tigris logout`, `tigris whoami`.
"""

import json as json_mod
import click

from ..utils.tigris_backend import TigrisBackend, TigrisCliError


@click.group("auth")
@click.pass_context
def auth_group(ctx):
    """Authentication (wraps `tigris login/logout/whoami`)."""
    pass


@auth_group.command("login")
@click.pass_context
def login(ctx):
    """Interactive OAuth login. Streams `tigris login` to your terminal."""
    backend: TigrisBackend = ctx.obj["backend"]
    skin = ctx.obj.get("skin")
    try:
        backend.login()
        if skin:
            skin.success("Logged in.")
    except TigrisCliError as e:
        if skin:
            skin.error(f"Login failed: {e}")
        raise SystemExit(1)


@auth_group.command("logout")
@click.pass_context
def logout(ctx):
    """Log out of the current Tigris session."""
    backend: TigrisBackend = ctx.obj["backend"]
    skin = ctx.obj.get("skin")
    try:
        backend.logout()
        if skin:
            skin.success("Logged out.")
    except TigrisCliError as e:
        if skin:
            skin.error(f"Logout failed: {e}")
        raise SystemExit(1)


@auth_group.command("whoami")
@click.pass_context
def whoami(ctx):
    """Print the currently authenticated user / organization."""
    backend: TigrisBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        info = backend.whoami()
        if use_json:
            click.echo(json_mod.dumps(info, indent=2))
        else:
            skin.section("Authentication")
            if isinstance(info, dict):
                for k, v in info.items():
                    skin.status(k, str(v))
            else:
                click.echo(info)
    except TigrisCliError as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"whoami failed: {e}")
        raise SystemExit(1)
