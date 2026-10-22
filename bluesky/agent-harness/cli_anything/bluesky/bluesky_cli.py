"""cli-anything-bluesky - Bluesky (AT Protocol) harness.

Post, read, and search from an agent-native CLI. Every command supports
--json. Auth uses Bluesky App Passwords; the session token lives in a 0600
file and is never passed on the command line.
"""

from __future__ import annotations

import json
import os
import sys

import click

from cli_anything.bluesky.core import backend


def _emit(ctx, payload: dict) -> None:
    if ctx.obj and ctx.obj.get("json"):
        click.echo(json.dumps(payload, indent=2, default=str))
    else:
        for k, v in payload.items():
            click.echo(f"{k}: {v}")


def _fail(msg: str) -> None:
    click.echo(f"error: {msg}", err=True)
    sys.exit(2)


@click.group()
@click.option("--json", "as_json", is_flag=True, help="machine-readable output")
@click.pass_context
def main(ctx: click.Context, as_json: bool) -> None:
    """Bluesky (AT Protocol) - agent-native CLI."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = as_json


@main.command()
@click.argument("text")
@click.pass_context
def post(ctx: click.Context, text: str) -> None:
    """Post one skeet. Requires a prior login."""
    try:
        _emit(ctx, backend.post(text))
    except backend.BackendError as e:
        _fail(str(e))


@main.command()
@click.option("--limit", default=50, help="posts to fetch (max 100)")
@click.pass_context
def timeline(ctx: click.Context, limit: int) -> None:
    """Your home timeline."""
    try:
        feed = backend.timeline(limit)
        posts = [
            {
                "author": (item.get("post") or {}).get("author", {}).get("handle"),
                "text": (item.get("post") or {}).get("record", {}).get("text"),
                "uri": (item.get("post") or {}).get("uri"),
            }
            for item in feed.get("feed", [])
        ]
        _emit(ctx, {"count": len(posts), "posts": posts})
    except backend.BackendError as e:
        _fail(str(e))


@main.command()
@click.argument("actor", required=False, default="")
@click.pass_context
def profile(ctx: click.Context, actor: str) -> None:
    """Profile by handle (defaults to the logged-in user)."""
    try:
        if not actor:
            actor = backend.load_session().get("handle", "")
        _emit(ctx, backend.profile(actor))
    except backend.BackendError as e:
        _fail(str(e))


@main.command()
@click.argument("query")
@click.option("--limit", default=25)
@click.pass_context
def search(ctx: click.Context, query: str, limit: int) -> None:
    """Search posts."""
    try:
        res = backend.search_posts(query, limit)
        posts = [
            {
                "author": (p.get("author") or {}).get("handle"),
                "text": (p.get("record") or {}).get("text"),
                "uri": p.get("uri"),
            }
            for p in res.get("posts", [])
        ]
        _emit(ctx, {"count": len(posts), "posts": posts})
    except backend.BackendError as e:
        _fail(str(e))


@main.command()
@click.option("--handle", default=None, help="your handle (or BSKY_HANDLE env)")
@click.option("--app-password", default=None, help="App Password (or BSKY_APP_PASSWORD env; prompted if absent)")
@click.pass_context
def login(ctx: click.Context, handle: str | None, app_password: str | None) -> None:
    """Create a session with a Bluesky App Password.

    Settings -> App Passwords on bsky.app. Never your account password.
    """
    handle = handle or os.environ.get("BSKY_HANDLE")
    app_password = app_password or os.environ.get("BSKY_APP_PASSWORD")
    if not handle:
        handle = click.prompt("handle (e.g. you.bsky.social)")
    if not app_password:
        app_password = click.prompt("app password", hide_input=True, confirmation_prompt=False)
    try:
        _emit(ctx, backend.login(handle, app_password))
    except backend.BackendError as e:
        _fail(str(e))


@main.command()
@click.pass_context
def whoami(ctx: click.Context) -> None:
    """Show the current session's handle and did."""
    try:
        session = backend.load_session()
        _emit(ctx, {"handle": session.get("handle"), "did": session.get("did")})
    except backend.BackendError as e:
        _fail(str(e))


@main.command()
@click.pass_context
def endpoints(ctx: click.Context) -> None:
    """List the XRPC endpoints this harness drives."""
    _emit(ctx, {"endpoints": backend.ENDPOINTS})


if __name__ == "__main__":
    main()
