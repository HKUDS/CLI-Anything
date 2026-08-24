"""cli-anything-opencti — agent-native CLI for the OpenCTI threat intelligence platform.

Read + write harness over OpenCTI's GraphQL API (v7). Every command supports
--json for machine-readable output. Destructive operations require --force.
"""

from __future__ import annotations

import json
import shlex
import sys
from typing import Any

import click

from cli_anything.opencti.core import (
    cases,
    entities,
    indicators,
    observables,
    reports,
    relationships,
    system,
)
from cli_anything.opencti.utils.opencti_backend import (
    OpenCTIError,
    resolve_connection,
    save_config,
)
from cli_anything.opencti.utils.repl_skin import (
    error,
    output,
    print_banner,
    success,
    warn,
)

VERSION = "1.0.0"

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


def _conn(ctx: click.Context) -> dict[str, Any]:
    return {
        "base_url": ctx.obj["base_url"],
        "api_key": ctx.obj["api_key"],
        "timeout": ctx.obj.get("timeout"),
    }


def _json_flag(ctx: click.Context) -> bool:
    return bool(ctx.obj.get("as_json"))


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.option("--url", default=None, envvar="OPENCTI_BASE_URL",
              help="OpenCTI base URL (or set OPENCTI_BASE_URL)")
@click.option("--token", default=None, envvar="OPENCTI_API_KEY",
              help="OpenCTI API token (or set OPENCTI_API_KEY)")
@click.option("--timeout", default=None, type=int,
              envvar="OPENCTI_TIMEOUT", help="Request timeout in seconds")
@click.option("--json", "as_json", is_flag=True, default=False,
              help="JSON output for machine consumption")
@click.version_option(version=VERSION, prog_name="cli-anything-opencti")
@click.pass_context
def cli(ctx: click.Context, url: str | None, token: str | None,
        timeout: int | None, as_json: bool) -> None:
    """Agent-native CLI for the OpenCTI threat intelligence platform."""
    conn = resolve_connection(url, token)
    ctx.obj = {
        "base_url": conn["base_url"],
        "api_key": conn["api_key"],
        "timeout": timeout,
        "as_json": as_json,
    }
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── system ────────────────────────────────────────────────────────────

@cli.command("status")
@click.pass_context
def status_cmd(ctx: click.Context) -> None:
    """Platform reachability, version, and authenticated identity."""
    output(system.status(**_conn(ctx)), _json_flag(ctx))


@cli.command("whoami")
@click.pass_context
def whoami_cmd(ctx: click.Context) -> None:
    """Show the identity bound to the configured API token."""
    output(system.me(**_conn(ctx)), _json_flag(ctx))


# ── observable ────────────────────────────────────────────────────────

@cli.group("observable")
def observable_() -> None:
    """STIX cyber observables (IPs, domains, URLs, files, emails)."""


@observable_.command("search")
@click.argument("query")
@click.option("--type", "obs_types", default=None,
              help="Comma-separated types, e.g. ipv4-addr,domain-name")
@click.option("--limit", default=25, show_default=True, type=int)
@click.option("--all", "all_pages", is_flag=True, default=False,
              help="Follow pagination to the end")
@click.pass_context
def observable_search(ctx: click.Context, query: str, obs_types: str | None,
                      limit: int, all_pages: bool) -> None:
    """Search observables by value substring."""
    types = [t.strip() for t in obs_types.split(",")] if obs_types else None
    data = observables.list_observables(search=query, types=types, first=limit,
                                        all_pages=all_pages, **_conn(ctx))
    output(data, _json_flag(ctx))


@observable_.command("get")
@click.argument("observable_id")
@click.pass_context
def observable_get(ctx: click.Context, observable_id: str) -> None:
    """Fetch one observable by ID with full context."""
    data = observables.get_observable(observable_id, **_conn(ctx))
    if not data:
        raise click.ClickException(f"observable not found: {observable_id}")
    output(data, _json_flag(ctx))


@observable_.command("add")
@click.argument("obs_type",
                type=click.Choice(sorted(observables.ADD_INPUTS) +
                                  sorted(observables.FILE_TYPES),
                                  case_sensitive=False))
@click.argument("value")
@click.option("--score", type=int, default=None,
              help="OpenCTI detection score 0-100")
@click.option("--description", default=None)
@click.option("--label", "labels", default=None,
              help="Comma-separated labels (created on the fly)")
@click.option("--create-indicator/--no-create-indicator", default=False,
              help="Also generate an indicator from this observable")
@click.pass_context
def observable_add(ctx: click.Context, obs_type: str, value: str, score: int | None,
                   description: str | None, labels: str | None,
                   create_indicator: bool) -> None:
    """Create a cyber observable (ipv4-addr, domain-name, url, file-sha256, ...)."""
    label_list = [l.strip() for l in labels.split(",")] if labels else None
    data = observables.add_observable(
        obs_type.lower(), value, score=score, description=description,
        labels=label_list, create_indicator=create_indicator, **_conn(ctx))
    success(f"created {data['id']}")
    output(data, _json_flag(ctx))


# ── indicator ─────────────────────────────────────────────────────────

@cli.group("indicator")
def indicator_() -> None:
    """STIX indicators and their detection patterns."""


@indicator_.command("list")
@click.option("--search", default=None, help="Filter by name/pattern substring")
@click.option("--limit", default=25, show_default=True, type=int)
@click.option("--all", "all_pages", is_flag=True, default=False)
@click.pass_context
def indicator_list(ctx: click.Context, search: str | None, limit: int,
                   all_pages: bool) -> None:
    """List indicators, newest first."""
    data = indicators.list_indicators(search=search, first=limit,
                                      all_pages=all_pages, **_conn(ctx))
    output(data, _json_flag(ctx))


@indicator_.command("get")
@click.argument("indicator_id")
@click.pass_context
def indicator_get(ctx: click.Context, indicator_id: str) -> None:
    """Fetch one indicator with full context."""
    data = indicators.get_indicator(indicator_id, **_conn(ctx))
    if not data:
        raise click.ClickException(f"indicator not found: {indicator_id}")
    output(data, _json_flag(ctx))


@indicator_.command("search-pattern")
@click.argument("pattern")
@click.option("--limit", default=25, show_default=True, type=int)
@click.pass_context
def indicator_search_pattern(ctx: click.Context, pattern: str, limit: int) -> None:
    """Find indicators whose STIX pattern starts with PATTERN (e.g. [ipv4-addr:value = '1.2)."""
    data = indicators.search_by_pattern(pattern, first=limit, **_conn(ctx))
    output(data, _json_flag(ctx))


@indicator_.command("add")
@click.argument("name")
@click.option("--pattern", required=True,
              help="Detection pattern, e.g. [domain-name:value = 'evil.example']")
@click.option("--pattern-type", default="stix", show_default=True)
@click.option("--score", type=int, default=None)
@click.option("--description", default=None)
@click.option("--valid-until", default=None,
              help="ISO 8601 datetime after which the indicator expires")
@click.option("--label", "labels", default=None)
@click.pass_context
def indicator_add(ctx: click.Context, name: str, pattern: str, pattern_type: str,
                  score: int | None, description: str | None,
                  valid_until: str | None, labels: str | None) -> None:
    """Create an indicator from a detection pattern."""
    label_list = [l.strip() for l in labels.split(",")] if labels else None
    data = indicators.add_indicator(
        name, pattern, pattern_type=pattern_type, score=score,
        description=description, valid_until=valid_until, labels=label_list,
        **_conn(ctx))
    success(f"created {data['id']}")
    output(data, _json_flag(ctx))


# ── report ────────────────────────────────────────────────────────────

@cli.group("report")
def report_() -> None:
    """Threat intelligence reports."""


@report_.command("list")
@click.option("--search", default=None, help="Filter by name substring")
@click.option("--limit", default=25, show_default=True, type=int)
@click.option("--all", "all_pages", is_flag=True, default=False)
@click.pass_context
def report_list(ctx: click.Context, search: str | None, limit: int,
                all_pages: bool) -> None:
    """List reports, newest first."""
    data = reports.list_reports(search=search, first=limit,
                                all_pages=all_pages, **_conn(ctx))
    output(data, _json_flag(ctx))


@report_.command("get")
@click.argument("report_id")
@click.pass_context
def report_get(ctx: click.Context, report_id: str) -> None:
    """Fetch a report plus its contained objects."""
    data = reports.get_report(report_id, **_conn(ctx))
    if not data:
        raise click.ClickException(f"report not found: {report_id}")
    output(data, _json_flag(ctx))


@report_.command("add")
@click.argument("name")
@click.option("--published", default=None,
              help="ISO 8601 date/datetime (defaults to now server-side)")
@click.option("--description", default=None)
@click.option("--type", "report_types", default=None,
              help="Comma-separated report types, e.g. threat-report,malware-analysis")
@click.option("--label", "labels", default=None)
@click.pass_context
def report_add(ctx: click.Context, name: str, published: str | None,
               description: str | None, report_types: str | None,
               labels: str | None) -> None:
    """Create a threat intelligence report."""
    type_list = [t.strip() for t in report_types.split(",")] if report_types else None
    label_list = [l.strip() for l in labels.split(",")] if labels else None
    data = reports.add_report(name, published=published, description=description,
                              report_types=type_list, labels=label_list,
                              **_conn(ctx))
    success(f"created {data['id']}")
    output(data, _json_flag(ctx))


# ── relationship ──────────────────────────────────────────────────────

@cli.group("relationship")
def relationship_() -> None:
    """STIX core relationships between entities."""


@relationship_.command("list")
@click.option("--limit", default=25, show_default=True, type=int)
@click.option("--all", "all_pages", is_flag=True, default=False)
@click.pass_context
def relationship_list(ctx: click.Context, limit: int, all_pages: bool) -> None:
    """List recent STIX core relationships."""
    data = relationships.list_relationships(first=limit, all_pages=all_pages,
                                            **_conn(ctx))
    output(data, _json_flag(ctx))


@relationship_.command("add")
@click.argument("from_id")
@click.argument("to_id")
@click.argument("relationship_type")
@click.option("--description", default=None)
@click.option("--start-time", default=None, help="ISO 8601 datetime")
@click.option("--stop-time", default=None, help="ISO 8601 datetime")
@click.pass_context
def relationship_add(ctx: click.Context, from_id: str, to_id: str,
                     relationship_type: str, description: str | None,
                     start_time: str | None, stop_time: str | None) -> None:
    """Create a FROM -> TO relationship (e.g. indicator indicates observable)."""
    data = relationships.add_relationship(
        from_id, to_id, relationship_type.lower(), description=description,
        start_time=start_time, stop_time=stop_time, **_conn(ctx))
    success(f"created {data['id']}")
    output(data, _json_flag(ctx))


# ── case ──────────────────────────────────────────────────────────────

@cli.group("case")
def case_() -> None:
    """Cases: incidents, requests for information (RFI), RFT."""


_CASE_TYPE = click.Choice(["incident", "rfi", "rft"], case_sensitive=False)


@case_.command("list")
@click.option("--type", "case_type", type=_CASE_TYPE, default="incident",
              show_default=True)
@click.option("--search", default=None, help="Filter by name substring")
@click.option("--limit", default=25, show_default=True, type=int)
@click.option("--all", "all_pages", is_flag=True, default=False)
@click.pass_context
def case_list(ctx: click.Context, case_type: str, search: str | None,
              limit: int, all_pages: bool) -> None:
    """List cases of the chosen type."""
    data = cases.list_cases(case_type.lower(), search=search, first=limit,
                            all_pages=all_pages, **_conn(ctx))
    output(data, _json_flag(ctx))


@case_.command("get")
@click.argument("case_id")
@click.option("--type", "case_type", type=_CASE_TYPE, default="incident",
              show_default=True)
@click.pass_context
def case_get(ctx: click.Context, case_id: str, case_type: str) -> None:
    """Fetch a case with its contained objects."""
    data = cases.get_case(case_type.lower(), case_id, **_conn(ctx))
    if not data:
        raise click.ClickException(f"case not found: {case_id}")
    output(data, _json_flag(ctx))


@case_.command("add")
@click.option("--type", "case_type", type=_CASE_TYPE, default="incident",
              show_default=True)
@click.argument("name")
@click.option("--severity", default=None,
              type=click.Choice(["low", "medium", "high", "critical"], case_sensitive=False))
@click.option("--priority", default=None,
              type=click.Choice(["low", "medium", "high", "critical"], case_sensitive=False))
@click.option("--description", default=None)
@click.pass_context
def case_add(ctx: click.Context, case_type: str, name: str, severity: str | None,
             priority: str | None, description: str | None) -> None:
    """Create a case of the chosen type."""
    data = cases.add_case(case_type.lower(), name,
                          severity=severity.lower() if severity else None,
                          priority=priority.lower() if priority else None,
                          description=description, **_conn(ctx))
    success(f"created {data['id']}")
    output(data, _json_flag(ctx))


# ── entity ────────────────────────────────────────────────────────────

@cli.group("entity")
def entity_() -> None:
    """Named threat-intel entities (threat actors, malware, ...)."""


_ENTITY_TYPE = click.Choice(sorted(entities.ENTITY_TYPES), case_sensitive=False)


@entity_.command("list")
@click.argument("entity_type", type=_ENTITY_TYPE)
@click.option("--search", default=None, help="Filter by name substring")
@click.option("--limit", default=25, show_default=True, type=int)
@click.option("--all", "all_pages", is_flag=True, default=False)
@click.pass_context
def entity_list(ctx: click.Context, entity_type: str, search: str | None,
                limit: int, all_pages: bool) -> None:
    """List entities of the given type."""
    data = entities.list_entities(entity_type.lower(), search=search,
                                  first=limit, all_pages=all_pages, **_conn(ctx))
    output(data, _json_flag(ctx))


@entity_.command("get")
@click.argument("entity_type", type=_ENTITY_TYPE)
@click.argument("entity_id")
@click.pass_context
def entity_get(ctx: click.Context, entity_type: str, entity_id: str) -> None:
    """Fetch an entity with full context (includes inline STIX)."""
    data = entities.get_entity(entity_type.lower(), entity_id, **_conn(ctx))
    if not data:
        raise click.ClickException(f"{entity_type} not found: {entity_id}")
    output(data, _json_flag(ctx))


@entity_.command("add")
@click.argument("entity_type", type=_ENTITY_TYPE)
@click.argument("name")
@click.option("--description", default=None)
@click.option("--alias", "aliases", default=None,
              help="Comma-separated aliases")
@click.option("--label", "labels", default=None)
@click.pass_context
def entity_add(ctx: click.Context, entity_type: str, name: str,
               description: str | None, aliases: str | None,
               labels: str | None) -> None:
    """Create a named threat-intel entity."""
    alias_list = [a.strip() for a in aliases.split(",")] if aliases else None
    label_list = [l.strip() for l in labels.split(",")] if labels else None
    data = entities.add_entity(entity_type.lower(), name,
                               description=description, aliases=alias_list,
                               labels=label_list, **_conn(ctx))
    success(f"created {data['id']}")
    output(data, _json_flag(ctx))


# ── search / export ───────────────────────────────────────────────────

@cli.command("search")
@click.argument("query")
@click.option("--types", default=None,
              help="Comma-separated entity types to restrict the search")
@click.option("--limit", default=25, show_default=True, type=int)
@click.option("--all", "all_pages", is_flag=True, default=False)
@click.pass_context
def search_cmd(ctx: click.Context, query: str, types: str | None,
               limit: int, all_pages: bool) -> None:
    """Global keyword search across all STIX core objects."""
    type_list = [t.strip() for t in types.split(",")] if types else None
    data = entities.global_search(query, types=type_list, first=limit,
                                  all_pages=all_pages, **_conn(ctx))
    output(data, _json_flag(ctx))


@cli.command("export-stix")
@click.option("--id", "object_id", required=True, help="STIX object ID")
@click.option("-o", "--out", default=None, help="Write bundle JSON to file instead of stdout")
@click.pass_context
def export_stix_cmd(ctx: click.Context, object_id: str, out: str | None) -> None:
    """Export one object as its STIX 2.1 JSON representation."""
    from cli_anything.opencti.utils.opencti_backend import graphql_request

    q = """
    query ($id: String!) {
      stixObjectOrStixRelationship(id: $id) {
        ... on StixCoreObject { toStix }
        ... on StixCoreRelationship { toStix }
      }
    }"""
    result = graphql_request(q, {"id": object_id}, **_conn(ctx))[
        "stixObjectOrStixRelationship"
    ]
    raw = (result or {}).get("toStix")
    if not raw:
        raise click.ClickException(f"no STIX representation for {object_id}")
    payload = json.dumps(json.loads(raw), indent=2)
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(payload + "\n")
        success(f"wrote {out}")
    else:
        click.echo(payload)


@cli.command("delete")
@click.argument("object_id")
@click.option("--force", is_flag=True, default=False,
              help="Actually delete; without this the command only shows what would go")
@click.pass_context
def delete_cmd(ctx: click.Context, object_id: str, force: bool) -> None:
    """Delete a STIX core object by ID (destructive — requires --force)."""
    if not force:
        warn(f"dry-run: {object_id} would be deleted. Re-run with --force.")
        return
    result = entities.delete_object(object_id, **_conn(ctx))
    success(f"deleted {object_id}")
    output(result, _json_flag(ctx))


# ── config ────────────────────────────────────────────────────────────

@cli.group("config")
def config_() -> None:
    """Persist connection settings for future invocations."""


@config_.command("set")
@click.option("--url", required=True, help="OpenCTI base URL")
@click.option("--token", default=None, help="API token")
def config_set(url: str, token: str | None) -> None:
    """Save URL/token to ~/.cli-anything/opencti/config.json."""
    path = save_config(url, token)
    success(f"saved {path}")


@config_.command("test")
@click.option("--url", default=None, envvar="OPENCTI_BASE_URL")
@click.option("--token", default=None, envvar="OPENCTI_API_KEY")
def config_test(url: str | None, token: str | None) -> None:
    """Validate connectivity using current settings."""
    conn = resolve_connection(url, token)
    info = system.status(base_url=conn["base_url"], api_key=conn["api_key"])
    output(info, False)


@cli.command("completions")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def install_completions(shell: str) -> None:
    """Print shell-completion installation instructions."""
    hint = {
        "bash": 'eval "$(_CLI_ANYTHING_OPENCTI_COMPLETE=bash_source cli-anything-opencti)"',
        "zsh": 'eval "$(_CLI_ANYTHING_OPENCTI_COMPLETE=zsh_source cli-anything-opencti)"',
        "fish": "_CLI_ANYTHING_OPENCTI_COMPLETE=fish_source cli-anything-opencti | source",
    }[shell]
    click.echo(f'Add to your shell profile:\n  {hint}')


# ── REPL ──────────────────────────────────────────────────────────────

@cli.command("repl", hidden=True)
@click.pass_context
def repl(ctx: click.Context) -> None:
    """Interactive shell (default when run with no subcommand)."""
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import WordCompleter
        from prompt_toolkit.history import InMemoryHistory
    except ImportError:
        error("prompt-toolkit is required for REPL mode. Install: pip install prompt-toolkit")
        sys.exit(1)

    print_banner()

    words = ["help", "exit", "quit", "status", "whoami"]
    for name, cmd in cli.commands.items():
        if getattr(cmd, "hidden", False):
            continue
        words.append(name)
        if hasattr(cmd, "commands"):
            for sub in cmd.commands:
                words.append(f"{name} {sub}")
    completer = WordCompleter(words, ignore_case=True)

    session = PromptSession(history=InMemoryHistory(), completer=completer)
    while True:
        try:
            line = session.prompt("opencti> ").strip()
        except (EOFError, KeyboardInterrupt):
            click.echo("\nBye!")
            break
        if not line:
            continue
        if line in ("exit", "quit", "q"):
            click.echo("Bye!")
            break
        if line == "help":
            click.echo(cli.get_help(ctx))
            continue
        try:
            try:
                args = shlex.split(line)
            except ValueError:
                args = line.split()
            cli.main(args, standalone_mode=False, obj=ctx.obj)
        except click.exceptions.UsageError as exc:
            error(str(exc))
        except SystemExit:
            pass
        except Exception as exc:  # noqa: BLE001
            error(str(exc))


def main() -> None:
    """Entry point with unified error mapping."""
    try:
        cli()
    except OpenCTIError as exc:
        error(str(exc))
        sys.exit(1)
    except ValueError as exc:  # GraphQL errors surface here
        error(str(exc))
        sys.exit(1)
    except ConnectionError as exc:
        error(str(exc))
        sys.exit(1)
    except TimeoutError as exc:
        error(str(exc))
        sys.exit(1)
    except click.exceptions.Abort:
        sys.exit(130)


if __name__ == "__main__":
    main()
