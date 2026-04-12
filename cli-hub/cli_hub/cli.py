"""cli-hub — CLI entry point."""

import click

from cli_hub import __version__
from cli_hub.registry import fetch_registry, get_cli, search_clis, list_categories
from cli_hub.installer import install_cli, uninstall_cli, get_installed, update_cli
from cli_hub.analytics import track_install, track_uninstall, track_visit, track_first_run, _detect_is_agent


@click.group(invoke_without_command=True)
@click.option("--version", is_flag=True, help="Show version.")
@click.pass_context
def main(ctx, version):
    """cli-hub — Download and manage CLI-Anything harnesses."""
    track_first_run()
    track_visit(is_agent=_detect_is_agent())
    if version:
        click.echo(f"cli-hub {__version__}")
        return
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.argument("name")
def install(name):
    """Install a CLI harness by name."""
    click.echo(f"Installing {name}...")
    success, msg = install_cli(name)
    if success:
        cli = get_cli(name)
        track_install(name, cli["version"] if cli else "unknown")
        click.secho(f"✓ {msg}", fg="green")
        click.echo(f"  Run it with: {cli['entry_point']}" if cli else "")
    else:
        click.secho(f"✗ {msg}", fg="red", err=True)
        raise SystemExit(1)


@main.command()
@click.argument("name")
def uninstall(name):
    """Uninstall a CLI harness by name."""
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
    """Update a CLI harness to the latest version."""
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
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def list_clis(category, as_json):
    """List all available CLI harnesses."""
    try:
        registry = fetch_registry()
    except Exception as e:
        click.secho(f"Failed to fetch registry: {e}", fg="red", err=True)
        raise SystemExit(1)

    clis = registry["clis"]
    if category:
        clis = [c for c in clis if c.get("category", "").lower() == category.lower()]

    installed = get_installed()

    if as_json:
        import json
        click.echo(json.dumps(clis, indent=2))
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
            desc = cli["description"][:60]
            click.echo(f"  {marker} {name} {desc}")

    total = len(clis)
    inst = sum(1 for c in clis if c["name"] in installed)
    click.echo(f"\n  {total} CLIs available, {inst} installed")
    cats = list_categories(registry)
    click.echo(f"  Categories: {', '.join(cats)}")


@main.command()
@click.argument("query")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def search(query, as_json):
    """Search CLIs by name, description, or category."""
    results = search_clis(query)

    if as_json:
        import json
        click.echo(json.dumps(results, indent=2))
        return

    if not results:
        click.echo(f"No CLIs matching '{query}'.")
        return

    installed = get_installed()
    for cli in results:
        marker = click.style("●", fg="green") if cli["name"] in installed else " "
        name = click.style(cli["name"], bold=True)
        cat = click.style(f"[{cli.get('category', '')}]", fg="blue")
        click.echo(f"  {marker} {name} {cat} — {cli['description'][:70]}")
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

    click.secho(f"\n  {cli['display_name']}", bold=True)
    click.echo(f"  {cli['description']}")
    click.echo(f"  Category:    {cli.get('category', 'N/A')}")
    click.echo(f"  Version:     {cli['version']}")
    click.echo(f"  Requires:    {cli.get('requires') or 'nothing'}")
    click.echo(f"  Entry point: {cli['entry_point']}")
    click.echo(f"  Homepage:    {cli.get('homepage', 'N/A')}")
    click.echo(f"  Contributor: {cli.get('contributor', 'N/A')}")
    status = click.style("installed", fg="green") if is_installed else "not installed"
    click.echo(f"  Status:      {status}")
    click.echo(f"\n  Install: cli-hub install {cli['name']}")
    click.echo()


if __name__ == "__main__":
    main()
