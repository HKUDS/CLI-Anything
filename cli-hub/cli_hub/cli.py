"""cli-hub — CLI entry point."""

import os
import shutil
import sys

import click

from cli_hub import __version__
from cli_hub.registry import fetch_all_clis, get_cli, search_clis, list_categories
from cli_hub.installer import install_cli, uninstall_cli, get_installed, update_cli
from cli_hub.analytics import detect_invocation_context, track_install, track_uninstall, track_visit, track_first_run


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
    """cli-hub — Download and manage CLI-Anything harnesses and public CLIs."""
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
        import json as json_mod
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
        import json as json_mod
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

    os.execvp(entry, [entry] + list(args))


if __name__ == "__main__":
    main()
