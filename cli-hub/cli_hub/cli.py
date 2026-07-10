"""cli-hub — CLI entry point."""

import os
import shutil
import sys
import json as json_mod
from pathlib import Path

import click

from cli_hub import __version__
from cli_hub.registry import fetch_all_clis, get_cli, search_clis, list_categories
from cli_hub.matrix import (
    all_recipes,
    capability_matches,
    fetch_all_matrices,
    get_matrix,
    get_recipe,
    preflight_matrix,
    provider_install_hint,
    search_capabilities,
    search_matrices,
)
from cli_hub.matrix_skill import get_rendered_matrix_skill_path, render_matrix_skill_file
from cli_hub.installer import (
    doctor_matrix,
    get_installed,
    install_cli,
    install_matrix,
    plan_matrix_install,
    uninstall_cli,
    update_cli,
)
from cli_hub.analytics import (
    detect_invocation_context,
    track_first_run,
    track_install,
    track_launch,
    track_matrix_discover,
    track_matrix_info,
    track_matrix_install,
    track_matrix_preflight,
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


# Exit-code contract for the matrix command family (F2.3 / F2.4):
#   0 success · 1 failure or not-found · 2 usage error · 3 partial / gaps
EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_PARTIAL = 3


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
    """cli-hub — Download and manage CLI-Anything CLIs, public CLIs, and curated matrices."""
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


def _plural(count, singular, plural=None):
    """Return a compact count label with basic pluralization."""
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


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


@main.command("can")
@click.argument("query")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def can(query, as_json):
    """Find a capability across all matrices for a task (e.g. cli-hub can "transcribe audio")."""
    hits = search_capabilities(query)
    track_matrix_discover("can", query=query, results=len(hits))

    if as_json:
        click.echo(json_mod.dumps({"query": query, "matched_capabilities": hits}, indent=2))
        raise SystemExit(EXIT_OK if hits else EXIT_FAIL)

    if not hits:
        click.echo(f"No capability matches '{query}'.")
        click.echo("  Browse matrices: cli-hub matrix list")
        raise SystemExit(EXIT_FAIL)

    for hit in hits:
        cap = click.style(hit["capability_id"], bold=True)
        loc = click.style(f"({hit['matrix']} [{hit['matrix_id']}])", fg="cyan")
        click.echo(f"\n  {cap}  {loc}")
        click.echo(f"    {hit['intent'][:88]}")

        chips = []
        for provider in hit["providers"][:5]:
            if provider.get("agent_installable"):
                chips.append(click.style(f"○ {provider['name']} (agent)", fg="bright_black"))
            elif provider["available"]:
                chips.append(click.style(f"✓ {provider['name']}", fg="green"))
            else:
                missing = [item for values in provider["missing"].values() for item in values]
                miss = f" (missing: {', '.join(missing)})" if missing else ""
                chips.append(click.style(f"✗ {provider['name']}{miss}", fg="yellow"))
        if chips:
            click.echo("    local: " + " · ".join(chips))
        click.echo(
            f"    next: cli-hub matrix preflight {hit['matrix']} -c {hit['capability_id']}"
        )


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

    track_matrix_discover("list", results=len(matrices))
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
    """Search matrices by name, capabilities, providers, recipes, or gaps."""
    results = search_matrices(query)
    track_matrix_discover("search", query=query, results=len(results))
    query_lower = query.lower()

    if as_json:
        enriched = []
        for matrix_item in results:
            entry = dict(matrix_item)
            entry["matched_capabilities"] = capability_matches(matrix_item, query_lower)
            enriched.append(entry)
        click.echo(json_mod.dumps(enriched, indent=2))
        return

    if not results:
        click.echo(f"No matrices matching '{query}'.")
        click.echo(f"  Try capability search: cli-hub can \"{query}\"")
        return

    installed = get_installed()
    for matrix_item in results:
        cli_names = matrix_item.get("clis", [])
        installed_count = sum(1 for c in cli_names if c in installed)
        total = len(cli_names)
        name_str = click.style(matrix_item["name"], bold=True)
        matrix_label = click.style(f"[{matrix_item.get('matrix_id', 'matrix')}]", fg="cyan")
        click.echo(f"\n  {name_str} {matrix_label} - {matrix_item['description'][:65]}")
        click.echo(f"    CLIs: {installed_count}/{total} installed")

        matched = capability_matches(matrix_item, query_lower)
        for hit in matched:
            star = click.style("✦", fg="cyan")
            click.echo(
                f"    {star} matched capability: {click.style(hit['capability_id'], bold=True)} "
                f"({hit['match_field']})"
            )
            click.echo(f"        {hit['intent'][:80]}")
            click.echo(f"        providers: {hit['providers_summary']}")

        if matched:
            first = matched[0]["capability_id"]
            click.echo(
                f"    Install: cli-hub matrix install {matrix_item['name']} "
                f"--capability {first}"
            )
        else:
            click.echo(f"    Install: cli-hub matrix install {matrix_item['name']}")


@matrix.command("info")
@click.argument("name")
@click.option("--json", "as_json", is_flag=True, help="Output matrix metadata as JSON.")
def matrix_info(name, as_json):
    """Show details for a specific matrix."""
    matrix_item = get_matrix(name)
    if not matrix_item:
        click.secho(f"Matrix '{name}' not found.", fg="red", err=True)
        raise SystemExit(1)

    track_matrix_info(matrix_item["name"], kind="info")
    installed = get_installed()
    cli_names = matrix_item.get("clis", [])
    installed_count = sum(1 for cli_name in cli_names if cli_name in installed)

    if as_json:
        payload = dict(matrix_item)
        payload["_installed"] = {
            "count": installed_count,
            "total": len(cli_names),
            "clis": [cli_name for cli_name in cli_names if cli_name in installed],
        }
        click.echo(json_mod.dumps(payload, indent=2))
        return

    click.secho(f"\n  {matrix_item['display_name']}", bold=True)
    click.echo(f"  {matrix_item['description']}")
    click.echo(f"  Matrix:      {matrix_item.get('matrix', 'N/A')} {matrix_item.get('matrix_id', '')}".rstrip())
    if matrix_item.get("schema_version"):
        click.echo(f"  Schema:      v{matrix_item['schema_version']}")
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

    capabilities = matrix_item.get("capabilities", [])
    if capabilities:
        click.echo("\n  Capabilities:")
        for capability in capabilities:
            providers = capability.get("providers", [])
            cli_provider_count = sum(
                1 for provider in providers
                if provider.get("kind") in {"harness-cli", "public-cli"}
            )
            offline_count = sum(1 for provider in providers if provider.get("offline"))
            click.echo(
                f"    - {capability['id']}: "
                f"{_plural(len(providers), 'provider')} "
                f"({_plural(cli_provider_count, 'CLI')}, {offline_count} offline)"
            )
            if capability.get("intent"):
                click.echo(f"      {capability['intent']}")

    recipes = matrix_item.get("recipes", [])
    if recipes:
        click.echo("\n  Recipes:")
        for recipe in recipes:
            capability_count = len(recipe.get("capabilities_used", []))
            click.echo(f"    - {recipe['id']}: {capability_count} capabilities - {recipe.get('description', '')}")

    known_gaps = matrix_item.get("known_gaps", [])
    if known_gaps:
        click.echo("\n  Known Gaps:")
        for gap in known_gaps:
            click.echo(f"    - {gap.get('capability', 'unknown')}: {gap.get('reason', '')}")

    click.echo(f"\n  Install: cli-hub matrix install {matrix_item['name']}")
    if capabilities:
        click.echo(f"  Preflight: cli-hub matrix preflight {matrix_item['name']}")
    click.echo()


@matrix.command("preflight")
@click.argument("name")
@click.option("--capability", "-c", default=None, help="Only check one capability id.")
@click.option("--recipe", default=None, help="Only check the capabilities used by one recipe.")
@click.option("--offline", is_flag=True, help="Only consider offline-capable providers.")
@click.option("--fix-hints", is_flag=True, help="Show an install command under each missing provider.")
@click.option("--summary", "summary_only", is_flag=True, help="Print only the two-line summary.")
@click.option("--json", "as_json", is_flag=True, help="Output provider availability as JSON.")
def matrix_preflight(name, capability, recipe, offline, fix_hints, summary_only, as_json):
    """Check which matrix providers are available in the current environment.

    Exit codes: 0 all capabilities covered · 3 one or more capability gaps ·
    1 matrix not found · 2 unknown capability/recipe.
    """
    matrix_item = get_matrix(name)
    if not matrix_item:
        click.secho(f"Matrix '{name}' not found.", fg="red", err=True)
        raise SystemExit(EXIT_FAIL)

    if capability and recipe:
        click.secho("Use only one of --capability or --recipe.", fg="red", err=True)
        raise SystemExit(EXIT_USAGE)

    capability_ids = None
    if recipe:
        recipe_item = get_recipe(matrix_item, recipe)
        if recipe_item is None:
            valid = ", ".join(r.get("id", "") for r in matrix_item.get("recipes", []))
            click.secho(f"Recipe '{recipe}' not found. Valid: {valid or '(none)'}", fg="red", err=True)
            raise SystemExit(EXIT_USAGE)
        capability_ids = recipe_item.get("capabilities_used", [])
    if capability and capability not in {c.get("id") for c in matrix_item.get("capabilities", [])}:
        valid = ", ".join(c.get("id", "") for c in matrix_item.get("capabilities", []))
        click.secho(f"Capability '{capability}' not found. Valid: {valid or '(none)'}", fg="red", err=True)
        raise SystemExit(EXIT_USAGE)

    payload = preflight_matrix(
        matrix_item, capability_id=capability, offline=offline, capability_ids=capability_ids
    )

    _preflight_summary = payload.get("summary", {})
    track_matrix_preflight(
        matrix_item["name"],
        scope=_matrix_scope_kind(capability, recipe, None),
        covered=_preflight_summary.get("covered", 0),
        capabilities=_preflight_summary.get("capabilities", 0),
        gaps=_preflight_summary.get("gaps", 0),
    )

    if as_json:
        click.echo(json_mod.dumps(payload, indent=2))
        raise SystemExit(EXIT_PARTIAL if payload["summary"].get("gaps", 0) else EXIT_OK)

    capabilities = payload["capabilities"]
    if not capabilities:
        target = capability or recipe or "capabilities"
        click.secho(f"No capability data found for {target}.", fg="yellow")
        raise SystemExit(EXIT_FAIL)

    summary = payload["summary"]
    cli_names = matrix_item.get("clis", [])
    click.secho(f"\n  {payload['matrix']['display_name']} Preflight", bold=True)
    mode = "offline providers only" if offline else "all providers"
    scope_suffix = f" · recipe {recipe}" if recipe else (f" · capability {capability}" if capability else "")
    click.echo(
        f"  {summary['covered']}/{summary['capabilities']} capabilities covered "
        f"({summary['available_providers']}/{_plural(summary['providers'], 'provider')} "
        f"available, {mode}{scope_suffix})"
    )
    if summary.get("gaps"):
        click.secho(f"  {_plural(summary['gaps'], 'capability')} with no usable provider", fg="yellow")
    agent_installable = summary.get("agent_installable_providers", 0)
    if agent_installable:
        verb = "is" if agent_installable == 1 else "are"
        click.echo(
            f"  {_plural(agent_installable, 'agent-installable skill provider')} "
            f"{verb} not counted as installed or missing"
        )

    if not summary_only:
        for capability_result in capabilities:
            click.echo(f"\n  {capability_result['id']}")
            click.echo(f"    {capability_result['intent']}")

            for provider in capability_result["providers"][:4]:
                if provider.get("agent_installable"):
                    marker = click.style("○", fg="bright_black")
                elif provider["available"]:
                    marker = click.style("✓", fg="green")
                else:
                    marker = click.style("·", fg="yellow")
                missing = [
                    item
                    for values in provider["missing"].values()
                    for item in values
                ]
                if provider.get("agent_installable"):
                    suffix = " agent-installable"
                elif provider["available"]:
                    suffix = ""
                else:
                    suffix = f" missing: {', '.join(missing) or 'requirements'}"
                click.echo(
                    f"    {marker} {provider['name']} "
                    f"[{provider['kind']}; {provider['quality_tier']}; {provider['cost_tier']}]{suffix}"
                )
                if fix_hints and not provider["available"] and not provider.get("agent_installable"):
                    hint = provider_install_hint(provider, cli_names)
                    if hint:
                        click.echo(click.style(f"      ↳ install: {hint}", fg="bright_black"))

    raise SystemExit(EXIT_PARTIAL if summary.get("gaps") else EXIT_OK)


_NOT_MANAGED_LABELS = {
    "python": "Python libraries",
    "native": "native binaries",
    "api": "cloud APIs (need keys)",
    "agent-skill": "agent skills (agent-installed)",
    "public-unmanaged": "third-party CLIs (brew/npm/pip)",
}


def _render_dry_run(payload):
    """Print a no-side-effect install plan (F2.1)."""
    matrix_item = payload["matrix"]
    summary = payload["summary"]
    click.secho(f"\n  Install plan: {matrix_item['name']} ({payload['scope_label']})", bold=True)

    skips = [p for p in payload["plan"] if p["action"] == "skip"]
    installs = [p for p in payload["plan"] if p["action"] == "install"]
    errors = [p for p in payload["plan"] if p["action"] == "error"]

    if skips:
        names = ", ".join(p["name"] for p in skips)
        click.secho(f"  ✓ Already installed, will skip ({len(skips)}): {names}", fg="green")
    for via in ("pip", "npm", "uv", "bundled", "command"):
        group = [p for p in installs if p["via"] == via]
        if group:
            names = ", ".join(p["name"] for p in group)
            click.echo(f"  + Will install via {via} ({len(group)}): {names}")
    if errors:
        names = ", ".join(p["name"] for p in errors)
        click.secho(f"  ! Not in CLI registry ({len(errors)}): {names}", fg="yellow")

    not_managed = payload.get("not_managed", {})
    if not_managed:
        click.echo("  ! Not installed by this command (use preflight + install hints):")
        for category, names in not_managed.items():
            label = _NOT_MANAGED_LABELS.get(category, category)
            click.echo(f"      {label}: {', '.join(names)}")

    if not payload["plan"]:
        click.secho("  Nothing to install for this scope via cli-hub.", fg="yellow")
        click.echo("  These providers are public/native/API — see: "
                   f"cli-hub matrix preflight {matrix_item['name']} --fix-hints")

    click.echo(f"\n  {summary['to_install']} to install, {summary['to_skip']} to skip"
               + (f", {summary['unresolved']} unresolved" if summary["unresolved"] else ""))
    click.echo(f"  Run: cli-hub matrix install {matrix_item['name']}"
               + _scope_args(payload["scope"]))


def _matrix_scope_kind(capability, recipe, only):
    """Compact scope label for analytics breakdowns (not the echoed flags)."""
    if capability:
        return "capability"
    if recipe:
        return "recipe"
    if only:
        return "only"
    return "full"


def _scope_args(scope):
    """Reconstruct the scope flags for an echoed command line."""
    scope_type = scope.get("type")
    if scope_type == "capability":
        return f" --capability {scope['value']}"
    if scope_type == "recipe":
        return f" --recipe {scope['value']}"
    if scope_type == "only":
        return f" --only {','.join(scope['value'])}"
    return ""


@matrix.command("install")
@click.argument("name")
@click.option("--capability", "-c", default=None, help="Install only the CLIs behind one capability.")
@click.option("--recipe", default=None, help="Install only the CLIs used by one recipe.")
@click.option("--only", default=None, help="Install a comma-separated subset of the matrix CLIs.")
@click.option("--dry-run", is_flag=True, help="Show the install plan without installing anything.")
@click.option("--resume", is_flag=True, help="Retry only the CLIs that failed in the last install.")
@click.option(
    "--skill-only",
    is_flag=True,
    help="Render the matrix skill (SKILL.md + references/ + scripts/) without installing member CLIs.",
)
@click.option("--json", "as_json", is_flag=True, help="Output the plan or result as JSON.")
def matrix_install(name, capability, recipe, only, dry_run, resume, skill_only, as_json):
    """Install the CLIs in a matrix (optionally scoped to a capability, recipe, or subset).

    Exit codes: 0 success · 3 partial failure · 1 total failure or not found ·
    2 usage error.
    """
    if skill_only:
        matrix_item = get_matrix(name)
        if not matrix_item:
            click.secho(f"Matrix '{name}' not found.", fg="red", err=True)
            raise SystemExit(EXIT_FAIL)
        rendered_skill_path = render_matrix_skill_file(matrix_item, installed=get_installed())
        track_matrix_install(
            matrix_item["name"],
            scope=_matrix_scope_kind(capability, recipe, only),
            status="skill_only",
        )
        click.echo(f"  Local matrix skill: {rendered_skill_path}")
        click.echo(f"  Install CLIs: cli-hub matrix install {matrix_item['name']}")
        return

    if dry_run:
        ok, payload = plan_matrix_install(name, capability=capability, recipe=recipe, only=only)
        if not ok:
            if as_json:
                click.echo(json_mod.dumps({"error": payload["error"]}, indent=2))
            else:
                click.secho(f"✗ {payload['error']}", fg="red", err=True)
            raise SystemExit(EXIT_USAGE if payload.get("arg_error") else EXIT_FAIL)
        track_matrix_install(
            payload["matrix"]["name"],
            scope=_matrix_scope_kind(capability, recipe, only),
            status="dry_run",
            dry_run=True,
        )
        if as_json:
            data = {k: payload[k] for k in ("scope", "scope_label", "plan", "not_managed", "summary")}
            data["matrix"] = payload["matrix"]["name"]
            click.echo(json_mod.dumps(data, indent=2))
        else:
            _render_dry_run(payload)
        return

    success, payload = install_matrix(
        name, capability=capability, recipe=recipe, only=only, resume=resume
    )
    if payload.get("error"):
        track_matrix_install(
            name,
            scope=_matrix_scope_kind(capability, recipe, only),
            status="usage_error" if payload.get("arg_error") else "error",
        )
        if as_json:
            click.echo(json_mod.dumps({"error": payload["error"]}, indent=2))
        else:
            click.secho(f"✗ {payload['error']}", fg="red", err=True)
        raise SystemExit(EXIT_USAGE if payload.get("arg_error") else EXIT_FAIL)

    matrix_item = payload["matrix"]
    summary = payload["summary"]

    if summary["failed"]:
        _install_status = "partial" if (summary["installed"] or summary["skipped"]) else "failed"
    elif payload.get("nothing_to_resume"):
        _install_status = "noop"
    else:
        _install_status = "ok"
    track_matrix_install(
        matrix_item["name"],
        scope=_matrix_scope_kind(capability, recipe, only),
        status=_install_status,
        installed=summary["installed"],
        skipped=summary["skipped"],
        failed=summary["failed"],
    )

    if as_json:
        data = {
            "matrix": matrix_item["name"],
            "scope": payload.get("scope"),
            "results": payload["results"],
            "summary": summary,
            "rendered_skill_path": payload.get("rendered_skill_path"),
        }
        click.echo(json_mod.dumps(data, indent=2))
    else:
        if payload.get("nothing_to_resume"):
            click.secho(f"  Nothing to resume — last install of {name} had no failures.", fg="green")
            return
        scope_label = payload.get("scope_label", "full matrix")
        click.echo(f"Installing matrix {name} ({scope_label})...")
        if not payload["results"]:
            click.secho("  No cli-hub-managed CLIs in this scope.", fg="yellow")
            click.echo(f"  Check provider availability: cli-hub matrix preflight {name} --fix-hints")
        for result in payload["results"]:
            status = result["status"]
            prefix = "✓" if status in {"installed", "skipped"} else "✗"
            color = "green" if status in {"installed", "skipped"} else "red"
            click.secho(f"  {prefix} {result['name']}: {result['message']}",
                        fg=color, err=status == "failed")

        click.echo(
            f"\n  Summary: {summary['installed']} installed, "
            f"{summary['skipped']} skipped, {summary['failed']} failed"
        )
        if summary["failed"]:
            click.echo(f"  Retry failures: cli-hub matrix install {matrix_item['name']} --resume")
        if matrix_item.get("skill_md"):
            click.echo(f"  Matrix skill: {matrix_item['skill_md']}")
        if payload.get("rendered_skill_path"):
            click.echo(f"  Local matrix skill: {payload['rendered_skill_path']}")
        click.echo(f"  Inspect:      cli-hub matrix info {matrix_item['name']}")

    if summary["failed"]:
        # Partial failure (some installed) vs. total failure get distinct exit codes.
        raise SystemExit(EXIT_PARTIAL if summary["installed"] or summary["skipped"] else EXIT_FAIL)


@matrix.command("doctor")
@click.argument("name")
@click.option("--json", "as_json", is_flag=True, help="Output the audit as JSON.")
def matrix_doctor(name, as_json):
    """Audit install completeness for a matrix's CLIs and suggest fixes (F2.3).

    Exit codes: 0 healthy · 3 some CLIs missing or broken · 1 matrix not found.
    """
    healthy, payload = doctor_matrix(name)
    if payload.get("error"):
        if as_json:
            click.echo(json_mod.dumps({"error": payload["error"]}, indent=2))
        else:
            click.secho(f"✗ {payload['error']}", fg="red", err=True)
        raise SystemExit(EXIT_FAIL)

    track_matrix_info(payload["matrix"]["name"], kind="doctor")

    if as_json:
        data = {k: payload[k] for k in ("last_run", "checks", "summary")}
        data["matrix"] = payload["matrix"]["name"]
        click.echo(json_mod.dumps(data, indent=2))
        raise SystemExit(EXIT_OK if healthy else EXIT_PARTIAL)

    matrix_item = payload["matrix"]
    summary = payload["summary"]
    click.secho(f"\n  {matrix_item['display_name']} Doctor", bold=True)
    if payload.get("last_run"):
        click.echo(f"  Last install: {payload['last_run']}")
    for check in payload["checks"]:
        if check["status"] == "ok":
            marker = click.style("✓", fg="green")
        elif check["status"] == "broken":
            marker = click.style("!", fg="yellow")
        else:
            marker = click.style("·", fg="bright_black")
        click.echo(f"  {marker} {check['name']}: {check['detail']}")
        if check["fix"]:
            click.echo(click.style(f"      ↳ fix: {check['fix']}", fg="bright_black"))

    click.echo(f"\n  Summary: {summary['ok']} ok, {summary['broken']} broken, "
               f"{summary['not_installed']} not installed")
    raise SystemExit(EXIT_OK if healthy else EXIT_PARTIAL)


@matrix.command("recipes")
@click.option("--search", "query", default=None, help="Filter recipes by id, description, or capability.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def matrix_recipes(query, as_json):
    """List task-oriented recipes across all matrices (F1.4)."""
    recipes = all_recipes(query)
    track_matrix_discover("recipes", query=query or "", results=len(recipes))

    if as_json:
        click.echo(json_mod.dumps({"query": query, "recipes": recipes}, indent=2))
        return

    if not recipes:
        target = f" matching '{query}'" if query else ""
        click.echo(f"No recipes found{target}.")
        return

    for recipe in recipes:
        name_str = click.style(recipe["id"], bold=True)
        loc = click.style(f"({recipe['matrix']})", fg="cyan")
        click.echo(f"\n  {name_str}  {loc}")
        if recipe["description"]:
            click.echo(f"    {recipe['description']}")
        caps = ", ".join(recipe["capabilities_used"])
        click.echo(f"    capabilities: {caps}")
        click.echo(
            f"    Preflight: cli-hub matrix preflight {recipe['matrix']} --recipe {recipe['id']}"
        )


if __name__ == "__main__":
    main()
