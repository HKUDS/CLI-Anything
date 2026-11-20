"""Optional search/fetch commands. Importing or showing help makes no requests."""

import asyncio
import json
import os
import shlex
import uuid
from urllib.parse import urlsplit

import click

from .utils import parallel_backend as backend
from .utils.repl_skin import ReplSkin


def _run(ctx, tool, arguments, json_output):
    if tool != "tools":
        arguments["session_id"] = ctx.obj["session_id"]
    try:
        payload = asyncio.run(backend.request(tool, arguments))
        output = json.dumps(
            payload,
            ensure_ascii=False,
            indent=None if json_output or ctx.obj["json"] else 2,
        )
        # Include formatting and the trailing newline in the final output bound.
        if len(output.encode("utf-8")) + 1 > backend.MAX_OUTPUT_BYTES:
            raise backend.BackendError(
                "Output exceeds the 1 MiB limit; request fewer URLs or omit --full-content"
            )
    except backend.BackendError as exc:
        if json_output or ctx.obj["json"]:
            click.echo(json.dumps({"error": str(exc)}))
            ctx.exit(1)
        raise click.ClickException(str(exc)) from exc
    # One payload only, preserving server warnings and partial fetch failures.
    click.echo(output)


@click.group(invoke_without_command=True)
@click.option(
    "--json", "json_output", is_flag=True, help="Compact machine-readable output."
)
@click.option(
    "--session-id",
    help="Reuse an opaque task ID across related search/fetch commands (max 100 characters).",
)
@click.version_option(package_name="cli-anything-parallel")
@click.pass_context
def main(ctx, json_output, session_id):
    """Search the web and extract pages with Parallel's free, rate-limited MCP.

    Queries, URLs, and supplied context go to Parallel. No API key is required.
    """
    if session_id is not None and (not session_id.strip() or len(session_id) > 100):
        raise click.BadParameter(
            "must contain 1-100 nonblank characters", param_hint="--session-id"
        )
    ctx.obj = {"json": json_output, "session_id": session_id or str(uuid.uuid4())}
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.argument("queries", nargs=-1, required=True)
@click.option("--objective", required=True, help="Describe the information you need.")
@click.option("--json", "json_output", is_flag=True)
@click.pass_context
def search(ctx, queries, objective, json_output):
    """Search using one to five queries, each at most 200 characters."""
    if not objective.strip():
        raise click.BadParameter("must not be blank", param_hint="--objective")
    if len(queries) > 5 or any(not q.strip() or len(q) > 200 for q in queries):
        raise click.BadParameter(
            "supply 1-5 nonblank queries of at most 200 characters",
            param_hint="QUERIES",
        )
    _run(
        ctx,
        "web_search",
        {"objective": objective, "search_queries": list(queries)},
        json_output,
    )


@main.command()
@click.argument("urls", nargs=-1, required=True)
@click.option(
    "--objective", help="Information wanted from the pages (max 200 characters)."
)
@click.option(
    "--query",
    "queries",
    multiple=True,
    help="Optional extraction keywords; repeat for multiple queries.",
)
@click.option(
    "--full-content",
    is_flag=True,
    help="Request full markdown, subject to output limits.",
)
@click.option("--json", "json_output", is_flag=True)
@click.pass_context
def fetch(ctx, urls, objective, queries, full_content, json_output):
    """Extract one to twenty public HTTP(S) URLs."""
    if len(urls) > 20:
        raise click.BadParameter("at most 20 URLs per call", param_hint="URLS")
    for url in urls:
        try:
            parsed = urlsplit(url)
            valid = (
                parsed.scheme in ("http", "https")
                and parsed.hostname
                and not parsed.username
                and not parsed.password
            )
        except ValueError:
            valid = False
        if not valid:
            raise click.BadParameter(
                "use HTTP(S) URLs without embedded credentials", param_hint="URLS"
            )
    if objective is not None and (not objective.strip() or len(objective) > 200):
        raise click.BadParameter(
            "must contain 1-200 nonblank characters", param_hint="--objective"
        )
    if any(not q.strip() for q in queries):
        raise click.BadParameter("must not be blank", param_hint="--query")
    args = {"urls": list(urls), "full_content": full_content}
    if objective is not None:
        args["objective"] = objective
    if queries:
        args["search_queries"] = list(queries)
    _run(ctx, "web_fetch", args, json_output)


@main.command()
@click.option("--json", "json_output", is_flag=True)
@click.pass_context
def tools(ctx, json_output):
    """Connect and list the server's available MCP tools."""
    _run(ctx, "tools", {}, json_output)


@main.command()
@click.option("--json", "json_output", is_flag=True)
@click.pass_context
def repl(ctx, json_output):
    """Run commands interactively, reusing one task ID until exit."""
    # This stateless REPL uses input(), so it has no persistent history.
    skin = ReplSkin("parallel", history_file=os.devnull)
    compact = json_output or ctx.obj["json"]
    if not compact:
        skin.print_banner()
    while True:
        try:
            line = input("" if compact else "parallel> ")
        except (EOFError, KeyboardInterrupt):
            break
        if line.strip() in ("exit", "quit"):
            break
        try:
            args = shlex.split(line)
            if not args:
                continue
            if args[0] not in ("search", "fetch", "tools", "help"):
                raise click.ClickException("Use search, fetch, tools, help, or exit")
            if args[0] == "help":
                args = ["--help"]
            main.main(
                [
                    "--session-id",
                    ctx.obj["session_id"],
                    *(["--json"] if compact else []),
                    *args,
                ],
                standalone_mode=False,
            )
        except (click.ClickException, ValueError) as exc:
            if compact:
                click.echo(json.dumps({"error": str(exc)}))
            else:
                click.echo(str(exc), err=True)
