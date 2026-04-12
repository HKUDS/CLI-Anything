"""Server commands -- heartbeat and version."""

import json as json_mod
import click

from ..utils.chromadb_backend import ChromaDBBackend


@click.group("server")
@click.pass_context
def server_group(ctx):
    """Server health and version commands."""
    pass


@server_group.command("heartbeat")
@click.pass_context
def heartbeat(ctx):
    """Check ChromaDB server health."""
    backend: ChromaDBBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        result = backend.heartbeat()
        if use_json:
            click.echo(json_mod.dumps(result, indent=2))
        else:
            skin.success("ChromaDB server is alive")
            skin.status("Heartbeat", str(result.get("nanosecond_heartbeat", result)))
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Server unreachable: {e}")
        raise SystemExit(1)


@server_group.command("version")
@click.pass_context
def version(ctx):
    """Get ChromaDB server version."""
    backend: ChromaDBBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        result = backend.version()
        if use_json:
            click.echo(json_mod.dumps({"version": result}, indent=2))
        else:
            skin.status("Version", str(result))
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Server unreachable: {e}")
        raise SystemExit(1)
