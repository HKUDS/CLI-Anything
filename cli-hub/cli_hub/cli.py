"""cli-hub — CLI entry point."""

import os
import shutil
import sys
import json as json_mod
from pathlib import Path

import click

from cli_hub import __version__
from cli_hub.registry import fetch_all_clis, get_cli, search_clis, list_categories
from cli_hub.matrix import fetch_all_matrices, get_matrix, search_matrices
from cli_hub.matrix_skill import get_rendered_matrix_skill_path
from cli_hub.installer import install_cli, uninstall_cli, get_installed, update_cli, install_matrix
from cli_hub.analytics import (
    detect_invocation_context,
    track_first_run,
    track_install,
    track_launch,
    track_uninstall,
    track_visit,
)
from cli_hub.preview import (
    inspect_bundle,
    inspect_session,
    is_live_session_ref,
    load_session,
    open_in_browser,
    render_html,
    render_inspect_text,
    render_live_html,
    render_session_text,
    start_static_server,
)


def _invocation_command(ctx, version):
    """Return a compact label for the current invocation."""
    argv = sys.argv[1:]
    if version:
        return "--version"
    if ctx.invoked_subcommand:
        return ctx.invoked_subcommand
    if any(arg in ("--help", "-h") for arg in argv):
        return "--help"
    if argv:
        return argv[0]
    return "root"


@click.group(invoke_without_command=True)
@click.option("--version", is_flag=True, help="Show version.")
@click.pass_context
def main(ctx, version):
    """cli-hub — Download and manage CLI-Anything CLIs and curated matrices."""
    track_first_run()
    track_visit(command=_invocation_command(ctx, version), detection=detect_invocation_context())
    if version:
        click.echo(f"cli-hub {__version__}")
        return
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _source_tag(cli):
    """Return a styled source indicator for display."""
    source = cli.get("_source", "harness")
    if source == "public":
        manager = cli.get("package_manager") or cli.get("install_strategy") or "public"
        return click.style(f" {manager}", fg="yellow")
    return ""


@main.command()
@click.argument("name")
def install(name):
    """Install a CLI by name."""
    click.echo(f"Installing {name}...")
    success, msg = install_cli(name)
    if success:
        cli = get_cli(name)
        track_install(name, cli["version"] if cli else "unknown")
        click.secho(f"✓ {msg}", fg="green")
        if cli:
            click.echo(f"  Run it with: {cli['entry_point']}")
            click.echo(f"  Or launch:   cli-hub launch {cli['name']}")
            if cli.get("_source") == "public" and cli.get("npx_cmd"):
                click.echo(f"  Or use npx:  {cli['npx_cmd']}")
    else:
        click.secho(f"✗ {msg}", fg="red", err=True)
        raise SystemExit(1)


@main.command()
@click.argument("name")
def uninstall(name):
    """Uninstall a CLI by name."""
    success, msg = uninstall_cli(name)
    if success:
        track_uninstall(name)
        click.secho(f"✓ {msg}", fg="green")
    else:
        click.secho(f"✗ {msg}", fg="red", err=True)
        raise SystemExit(1)


@main.command()
@click.argument("name")
def update(name):
    """Update a CLI to the latest version."""
    click.echo(f"Updating {name}...")
    success, msg = update_cli(name)
    if success:
        cli = get_cli(name)
        track_install(name, cli["version"] if cli else "unknown")
        click.secho(f"✓ {msg}", fg="green")
    else:
        click.secho(f"✗ {msg}", fg="red", err=True)
        raise SystemExit(1)


@main.command("list")
@click.option("--category", "-c", default=None, help="Filter by category.")
@click.option("--source", "-s", default=None, type=click.Choice(["harness", "public", "npm", "all"], case_sensitive=False),
              help="Filter by source (harness, public, or all). 'npm' is kept as an alias for public.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def list_clis(category, source, as_json):
    """List all available CLIs."""
    try:
        all_clis = fetch_all_clis()
    except Exception as e:
        click.secho(f"Failed to fetch registry: {e}", fg="red", err=True)
        raise SystemExit(1)

    clis = all_clis
    if category:
        clis = [c for c in clis if c.get("category", "").lower() == category.lower()]
    if source == "npm":
        source = "public"
    if source and source != "all":
        clis = [c for c in clis if c.get("_source", "harness") == source]

    installed = get_installed()

    if as_json:
        click.echo(json_mod.dumps(clis, indent=2))
        return

    if not clis:
        click.echo("No CLIs found." + (f" Category '{category}' may not exist." if category else ""))
        return

    # Group by category
    by_cat = {}
    for cli in clis:
        cat = cli.get("category", "uncategorized")
        by_cat.setdefault(cat, []).append(cli)

    for cat in sorted(by_cat):
        click.secho(f"\n  {cat.upper()}", fg="blue", bold=True)
        for cli in sorted(by_cat[cat], key=lambda c: c["name"]):
            marker = click.style(" ●", fg="green") if cli["name"] in installed else "  "
            name = click.style(f"{cli['name']:20s}", bold=True)
            desc = cli["description"][:55]
            tag = _source_tag(cli)
            click.echo(f"  {marker} {name}{tag} {desc}")

    total = len(clis)
    inst = sum(1 for c in clis if c["name"] in installed)
    harness_count = sum(1 for c in clis if c.get("_source") == "harness")
    public_count = sum(1 for c in clis if c.get("_source") == "public")
    click.echo(f"\n  {total} CLIs available ({harness_count} harness, {public_count} public), {inst} installed")
    cats = list_categories()
    click.echo(f"  Categories: {', '.join(cats)}")


@main.command()
@click.argument("query")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def search(query, as_json):
    """Search CLIs by name, description, or category."""
    results = search_clis(query)

    if as_json:
        click.echo(json_mod.dumps(results, indent=2))
        return

    if not results:
        click.echo(f"No CLIs matching '{query}'.")
        return

    installed = get_installed()
    for cli in results:
        marker = click.style("●", fg="green") if cli["name"] in installed else " "
        name = click.style(cli["name"], bold=True)
        cat = click.style(f"[{cli.get('category', '')}]", fg="blue")
        tag = _source_tag(cli)
        click.echo(f"  {marker} {name} {cat}{tag} — {cli['description'][:65]}")
        click.echo(f"    Install: cli-hub install {cli['name']}")


@main.command()
@click.argument("name")
def info(name):
    """Show details for a specific CLI."""
    cli = get_cli(name)
    if not cli:
        click.secho(f"CLI '{name}' not found.", fg="red", err=True)
        raise SystemExit(1)

    installed = get_installed()
    is_installed = cli["name"] in installed
    source = cli.get("_source", "harness")

    click.secho(f"\n  {cli['display_name']}", bold=True)
    click.echo(f"  {cli['description']}")
    click.echo(f"  Category:    {cli.get('category', 'N/A')}")
    click.echo(f"  Source:      {source}")
    if source == "public":
        click.echo(f"  Install via: {cli.get('package_manager') or cli.get('install_strategy') or 'public'}")
        if cli.get("npm_package"):
            click.echo(f"  npm package: {cli['npm_package']}")
        if cli.get("npx_cmd"):
            click.echo(f"  npx command: {cli['npx_cmd']}")
        if cli.get("install_cmd"):
            click.echo(f"  Install cmd: {cli['install_cmd']}")
        if cli.get("install_notes"):
            click.echo(f"  Notes:       {cli['install_notes']}")
    click.echo(f"  Version:     {cli['version']}")
    click.echo(f"  Requires:    {cli.get('requires') or 'nothing'}")
    click.echo(f"  Entry point: {cli['entry_point']}")
    if cli.get("skill_md"):
        click.echo(f"  Skill:       {cli['skill_md']}")
    click.echo(f"  Homepage:    {cli.get('homepage', 'N/A')}")
    contributors = cli.get("contributors", [])
    if contributors:
        names = ", ".join(ct["name"] for ct in contributors)
        click.echo(f"  Contributors: {names}")
    status = click.style("installed", fg="green") if is_installed else "not installed"
    click.echo(f"  Status:      {status}")
    click.echo(f"\n  Install: cli-hub install {cli['name']}")
    click.echo()


@main.command()
@click.argument("name")
@click.argument("args", nargs=-1)
def launch(name, args):
    """Launch an installed CLI, passing through any extra arguments."""
    cli = get_cli(name)
    if not cli:
        click.secho(f"CLI '{name}' not found in registry.", fg="red", err=True)
        raise SystemExit(1)

    entry = cli["entry_point"]
    if not shutil.which(entry):
        click.secho(
            f"'{entry}' not found on PATH. Install it first: cli-hub install {name}",
            fg="red",
            err=True,
        )
        raise SystemExit(1)

    track_launch(name)
    os.execvp(entry, [entry] + list(args))


@main.group(name="previews", invoke_without_command=True)
@click.pass_context
def previews(ctx):
    """Inspect existing preview bundles or live sessions; this command does not publish previews."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@previews.command("inspect")
@click.argument("preview_ref")
@click.option("--json", "as_json", is_flag=True, help="Output preview metadata as JSON.")
def preview_inspect(preview_ref, as_json):
    """Inspect a preview bundle or live session."""
    if is_live_session_ref(preview_ref):
        payload = inspect_session(preview_ref)
        if as_json:
            click.echo(json_mod.dumps(payload, indent=2))
            return
        click.echo(render_session_text(preview_ref), nl=False)
        return
    if as_json:
        click.echo(json_mod.dumps(inspect_bundle(preview_ref), indent=2))
        return
    click.echo(render_inspect_text(preview_ref), nl=False)


@previews.command("html")
@click.argument("preview_ref")
@click.option("--output", "-o", "output_path", default=None, help="Output HTML path.")
@click.option("--poll-ms", default=1500, show_default=True, help="Polling interval for live session pages.")
def preview_html(preview_ref, output_path, poll_ms):
    """Render HTML for a preview bundle or live session."""
    if is_live_session_ref(preview_ref):
        session_dir, _session = load_session(preview_ref)
        if output_path is None:
            output_path = os.path.join(session_dir, "live.html")
        rendered = render_live_html(preview_ref, output_path, poll_ms=poll_ms)
        click.echo(rendered)
        return
    if output_path is None:
        payload = inspect_bundle(preview_ref)
        output_path = os.path.join(payload["bundle_dir"], "preview.html")
    rendered = render_html(preview_ref, output_path)
    click.echo(rendered)


def _serve_live_session(session_ref, poll_ms, auto_open, port):
    session_dir, session = load_session(session_ref)
    output_path = Path(session_dir) / "live.html"
    render_live_html(session_ref, str(output_path), poll_ms=poll_ms)
    server, base_url = start_static_server(str(session_dir), port=port)
    live_url = f"{base_url}/live.html"
    click.echo(f"Live preview URL: {live_url}")
    if auto_open:
        launched = open_in_browser(live_url)
        if launched.get("launched"):
            click.echo(f"Opened in {launched['browser']}: pid {launched['pid']}")
        else:
            click.echo(
                "Browser launch unavailable. Open this manually:\n"
                f"  {live_url}\n"
                f"  Suggested command: {session.get('watch_command') or f'cli-hub previews watch {session_dir} --open'}"
            )
    click.echo("Press Ctrl-C to stop the live preview server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        click.echo("\nStopped live preview server.")
    finally:
        server.server_close()


@previews.command("watch")
@click.argument("session_ref")
@click.option("--poll-ms", default=1500, show_default=True, help="Polling interval for the live page.")
@click.option("--port", default=0, show_default=True, help="Preferred localhost port. Use 0 for auto.")
@click.option("--open/--no-open", "auto_open", default=False, help="Open a separate browser window.")
def preview_watch(session_ref, poll_ms, port, auto_open):
    """Serve and watch a live preview session."""
    _serve_live_session(session_ref, poll_ms=poll_ms, auto_open=auto_open, port=port)


@previews.command("open")
@click.argument("preview_ref")
@click.option("--output", "-o", "output_path", default=None, help="Override the generated HTML path.")
@click.option("--poll-ms", default=1500, show_default=True, help="Polling interval when opening a live session.")
@click.option("--port", default=0, show_default=True, help="Preferred localhost port for live sessions.")
def preview_open(preview_ref, output_path, poll_ms, port):
    """Open a preview bundle or live session in a browser window."""
    if is_live_session_ref(preview_ref):
        _serve_live_session(preview_ref, poll_ms=poll_ms, auto_open=True, port=port)
        return
    if output_path is None:
        payload = inspect_bundle(preview_ref)
        output_path = os.path.join(payload["bundle_dir"], "preview.html")
    rendered = render_html(preview_ref, output_path)
    launched = open_in_browser(Path(rendered).resolve().as_uri())
    click.echo(rendered)
    if launched.get("launched"):
        click.echo(f"Opened in {launched['browser']}: pid {launched['pid']}")
    else:
        click.echo(f"Open this file manually: {rendered}")


@main.group(name="matrix", invoke_without_command=True)
@click.pass_context
def matrix(ctx):
    """Browse and install curated multi-CLI workflow matrices."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@matrix.command("list")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def list_matrices(as_json):
    """List all available matrices."""
    try:
        matrices = fetch_all_matrices()
    except Exception as e:
        click.secho(f"Failed to fetch matrix registry: {e}", fg="red", err=True)
        raise SystemExit(1)

    installed = get_installed()

    if as_json:
        click.echo(json_mod.dumps(matrices, indent=2))
        return

    if not matrices:
        click.echo("No matrices found.")
        return

    click.secho("\n  MATRICES", fg="blue", bold=True)
    for matrix_item in sorted(matrices, key=lambda s: s["name"]):
        installed_count = sum(1 for cli_name in matrix_item.get("clis", []) if cli_name in installed)
        total = len(matrix_item.get("clis", []))
        marker = click.style(" ●", fg="green") if total and installed_count == total else "  "
        name = click.style(f"{matrix_item['name']:20s}", bold=True)
        matrix_label = click.style(f"[{matrix_item.get('matrix_id', 'matrix')}]", fg="cyan")
        click.echo(f"  {marker} {name} {matrix_label} {matrix_item['description'][:65]}")
        click.echo(f"     Includes: {installed_count}/{total} CLIs installed")

    click.echo(f"\n  {len(matrices)} matrices available")


@matrix.command("search")
@click.argument("query")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def matrix_search(query, as_json):
    """Search matrices by name, description, or category."""
    results = search_matrices(query)

    if as_json:
        click.echo(json_mod.dumps(results, indent=2))
        return

    if not results:
        click.echo(f"No matrices matching '{query}'.")
        return

    installed = get_installed()
    for matrix_item in results:
        cli_names = matrix_item.get("clis", [])
        installed_count = sum(1 for c in cli_names if c in installed)
        total = len(cli_names)
        name_str = click.style(matrix_item["name"], bold=True)
        matrix_label = click.style(f"[{matrix_item.get('matrix_id', 'matrix')}]", fg="cyan")
        click.echo(f"  {name_str} {matrix_label} — {matrix_item['description'][:65]}")
        click.echo(f"    CLIs: {installed_count}/{total} installed")
        click.echo(f"    Install: cli-hub matrix install {matrix_item['name']}")


@matrix.command("info")
@click.argument("name")
def matrix_info(name):
    """Show details for a specific matrix."""
    matrix_item = get_matrix(name)
    if not matrix_item:
        click.secho(f"Matrix '{name}' not found.", fg="red", err=True)
        raise SystemExit(1)

    installed = get_installed()
    cli_names = matrix_item.get("clis", [])
    installed_count = sum(1 for cli_name in cli_names if cli_name in installed)

    click.secho(f"\n  {matrix_item['display_name']}", bold=True)
    click.echo(f"  {matrix_item['description']}")
    click.echo(f"  Matrix:      {matrix_item.get('matrix', 'N/A')} {matrix_item.get('matrix_id', '')}".rstrip())
    click.echo(f"  Category:    {matrix_item.get('category', 'N/A')}")
    click.echo(f"  CLIs:        {len(cli_names)}")
    click.echo(f"  Installed:   {installed_count}/{len(cli_names)}")
    if matrix_item.get("skill_md"):
        click.echo(f"  Skill:       {matrix_item['skill_md']}")
    rendered_skill_path = get_rendered_matrix_skill_path(matrix_item["name"])
    if rendered_skill_path.exists():
        click.echo(f"  Local skill: {rendered_skill_path}")
    if matrix_item.get("homepage"):
        click.echo(f"  Homepage:    {matrix_item['homepage']}")

    click.echo("\n  Members:")
    for cli_name in cli_names:
        status = click.style("installed", fg="green") if cli_name in installed else "not installed"
        click.echo(f"    - {cli_name} ({status})")

    stages = matrix_item.get("stages", [])
    if stages:
        click.echo("\n  Stage Coverage:")
        for stage in stages:
            members = ", ".join(stage.get("clis", []))
            goal = stage.get("goal", "")
            goal_suffix = f" -- {goal}" if goal else ""
            click.echo(f"    - {stage['name']}: {members}{goal_suffix}")

    click.echo(f"\n  Install: cli-hub matrix install {matrix_item['name']}")
    click.echo()


@matrix.command("install")
@click.argument("name")
def matrix_install(name):
    """Install every CLI in a matrix."""
    click.echo(f"Installing matrix {name}...")
    success, payload = install_matrix(name)
    if payload.get("error"):
        click.secho(f"✗ {payload['error']}", fg="red", err=True)
        raise SystemExit(1)

    matrix_item = payload["matrix"]
    for result in payload["results"]:
        status = result["status"]
        prefix = "✓" if status in {"installed", "skipped"} else "✗"
        color = "green" if status in {"installed", "skipped"} else "red"
        click.secho(f"  {prefix} {result['name']}: {result['message']}", fg=color, err=status == "failed")

    summary = payload["summary"]
    click.echo(
        f"\n  Summary: {summary['installed']} installed, "
        f"{summary['skipped']} skipped, {summary['failed']} failed"
    )
    if matrix_item.get("skill_md"):
        click.echo(f"  Matrix skill: {matrix_item['skill_md']}")
    if payload.get("rendered_skill_path"):
        click.echo(f"  Local matrix skill: {payload['rendered_skill_path']}")
    click.echo(f"  Inspect:      cli-hub matrix info {matrix_item['name']}")

    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
