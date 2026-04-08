"""ChromaDB CLI-Anything harness -- Click CLI + REPL."""

import json as json_mod
import shlex
import sys

import click

from .utils.chromadb_backend import ChromaDBBackend
from .utils.repl_skin import ReplSkin
from .core.server import server_group
from .core.collections import collection_group
from .core.documents import document_group
from .core.query import query_group


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, default=False,
              help="Output in JSON format")
@click.option("--host", default="http://localhost:8000",
              help="ChromaDB server URL (default: http://localhost:8000)")
@click.pass_context
def cli(ctx, use_json, host):
    """CLI-Anything harness for ChromaDB vector database."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = use_json
    ctx.obj["backend"] = ChromaDBBackend(base_url=host)
    ctx.obj["skin"] = ReplSkin("chromadb", version="1.0.0")

    if ctx.invoked_subcommand is None:
        _run_repl(ctx)


cli.add_command(server_group)
cli.add_command(collection_group)
cli.add_command(document_group)
cli.add_command(query_group)


# ── REPL Commands Map (for help display) ─────────────────────────────

_REPL_COMMANDS = {
    "server heartbeat":                "Check server health",
    "server version":                  "Get server version",
    "collection list":                 "List all collections",
    "collection create --name NAME":   "Create a new collection",
    "collection delete --name NAME":   "Delete a collection",
    "collection info NAME":            "Get collection info",
    "document add --collection C ...": "Add document(s)",
    "document get --collection C":     "Get documents",
    "document delete --collection C":  "Delete document(s)",
    "document count --collection C":   "Count documents",
    "query search --collection C --text T": "Semantic search",
    "help":                            "Show this help",
    "quit / exit":                     "Exit the REPL",
}


def _run_repl(ctx):
    """Launch the interactive REPL."""
    skin: ReplSkin = ctx.obj["skin"]
    skin.print_banner()

    session = skin.create_prompt_session()

    while True:
        try:
            user_input = skin.get_input(session, context="chromadb")
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

        if not user_input:
            continue

        cmd = user_input.strip().lower()

        if cmd in ("quit", "exit", "q"):
            skin.print_goodbye()
            break

        if cmd in ("help", "h", "?"):
            skin.help(_REPL_COMMANDS)
            continue

        # Parse the input and dispatch through Click
        try:
            args = shlex.split(user_input)
        except ValueError as e:
            skin.error(f"Parse error: {e}")
            continue

        try:
            # Create a fresh context for each REPL command
            cli.main(args=args, obj=ctx.obj, standalone_mode=False)
        except SystemExit:
            # Click raises SystemExit on errors; swallow in REPL
            pass
        except click.exceptions.UsageError as e:
            skin.error(str(e))
        except Exception as e:
            skin.error(f"Error: {e}")


def main():
    """Entry point."""
    cli(auto_envvar_prefix="CHROMADB_CLI")


if __name__ == "__main__":
    main()
