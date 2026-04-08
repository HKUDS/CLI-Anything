"""Agent commands for SeaClip CLI."""

import json as json_mod

import click

from ..utils.seaclip_backend import SeaClipBackend


@click.group("agent")
def agent_group():
    """Manage pipeline agents."""


@agent_group.command("list")
@click.pass_context
def agent_list(ctx):
    """List all pipeline agents."""
    backend: SeaClipBackend = ctx.obj["backend"]
    skin = ctx.obj.get("skin")
    as_json = ctx.obj.get("json", False)

    try:
        agents = backend.list_agents()
    except Exception as e:
        if as_json:
            click.echo(json_mod.dumps({"error": str(e)}))
        elif skin:
            skin.error(f"Failed to list agents: {e}")
        raise SystemExit(1)

    if as_json:
        click.echo(json_mod.dumps(agents, indent=2))
        return

    if skin:
        if not agents:
            skin.info("No agents found.")
            return
        headers = ["Name", "Label", "Status"]
        rows = []
        for a in agents:
            rows.append([
                str(a.get("name", "")),
                str(a.get("label", "")),
                str(a.get("status", "")),
            ])
        skin.table(headers, rows)
