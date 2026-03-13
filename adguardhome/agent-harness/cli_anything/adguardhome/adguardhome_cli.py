"""cli-anything-adguardhome - CLI harness for AdGuardHome."""

import json
import sys
from pathlib import Path

import click

from cli_anything.adguardhome.core import blocking as blocking_core
from cli_anything.adguardhome.core import clients as clients_core
from cli_anything.adguardhome.core import dhcp as dhcp_core
from cli_anything.adguardhome.core import filtering as filtering_core
from cli_anything.adguardhome.core import log as log_core
from cli_anything.adguardhome.core import project
from cli_anything.adguardhome.core import rewrite as rewrite_core
from cli_anything.adguardhome.core import server as server_core
from cli_anything.adguardhome.core import stats as stats_core
from cli_anything.adguardhome.utils.adguardhome_backend import AdGuardHomeClient
from cli_anything.adguardhome.utils.repl_skin import ReplSkin

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


def make_client(ctx: click.Context) -> AdGuardHomeClient:
    obj = ctx.obj
    return AdGuardHomeClient(
        host=obj["host"],
        port=obj["port"],
        username=obj["username"],
        password=obj["password"],
        https=obj.get("use_https", False),
    )


def output(data, as_json: bool) -> None:
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
    elif isinstance(data, dict):
        for k, v in data.items():
            click.echo(f"{k}: {v}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                click.echo(json.dumps(item, default=str))
            else:
                click.echo(str(item))
    else:
        click.echo(str(data))


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------

@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.option("--host", default=None, help="AdGuardHome hostname/IP")
@click.option("--port", default=None, type=int, help="AdGuardHome port (default 3000)")
@click.option("--username", default=None, help="Basic Auth username")
@click.option("--password", default=None, help="Basic Auth password")
@click.option("--config", "config_path", default=None, type=click.Path(),
              help="Path to config file")
@click.option("--https", "use_https", is_flag=True, default=False,
              help="Use HTTPS (auto-detected for port 443)")
@click.option("--json", "as_json", is_flag=True, default=False,
              help="Output as JSON")
@click.pass_context
def cli(ctx: click.Context, host, port, username, password, config_path, use_https, as_json):
    """cli-anything-adguardhome - control AdGuardHome from the command line."""
    ctx.ensure_object(dict)

    cfg = project.load_config(Path(config_path) if config_path else None)
    ctx.obj["host"] = host or cfg["host"]
    ctx.obj["port"] = port or cfg["port"]
    ctx.obj["username"] = username or cfg["username"]
    ctx.obj["password"] = password or cfg["password"]
    ctx.obj["use_https"] = use_https or cfg.get("https", False)
    ctx.obj["as_json"] = as_json

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


def main():
    cli(obj={})


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------

@cli.command(hidden=True)
@click.pass_context
def repl(ctx: click.Context):
    """Interactive REPL mode."""
    skin = ReplSkin("adguardhome", version="1.0.0")
    skin.print_banner()

    host = ctx.obj["host"]
    port = ctx.obj["port"]
    skin.info(f"Connecting to {host}:{port}")

    pt_session = skin.create_prompt_session()

    while True:
        try:
            line = skin.get_input(pt_session, project_name=f"{host}:{port}")
        except (EOFError, KeyboardInterrupt):
            break

        line = line.strip()
        if not line:
            continue
        if line in ("exit", "quit"):
            break
        if line == "help":
            skin.help({
                "server status/version/restart": "Server management",
                "filter list/add/remove/enable/disable/refresh/status/toggle": "Filtering",
                "blocking parental/safebrowsing/safesearch status/enable/disable": "Blocking",
                "blocked-services list/set": "Blocked services",
                "clients list/add/remove/show": "Client management",
                "stats show/reset/config": "Statistics",
                "log show/config/clear": "Query log",
                "rewrite list/add/remove": "DNS rewrites",
                "dhcp status/leases/add-static/remove-static": "DHCP server",
                "tls status": "TLS configuration",
                "config show/save/test": "Connection config",
            })
            continue

        try:
            args = line.split()
            cli.main(args=args, obj=dict(ctx.obj), standalone_mode=False)
        except click.exceptions.UsageError as e:
            skin.error(str(e))
        except RuntimeError as e:
            skin.error(str(e))
        except SystemExit:
            pass
        except Exception as e:
            skin.error(f"Unexpected error: {e}")

    skin.print_goodbye()


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def config(ctx: click.Context):
    """Connection configuration."""


@config.command("show")
@click.pass_context
def config_show(ctx: click.Context):
    """Show current connection settings."""
    obj = ctx.obj
    data = {
        "host": obj["host"],
        "port": obj["port"],
        "username": obj["username"],
        "password": "***" if obj["password"] else "",
    }
    output(data, obj["as_json"])


@config.command("save")
@click.pass_context
def config_save(ctx: click.Context):
    """Save connection settings to config file."""
    obj = ctx.obj
    path = project.save_config(
        host=obj["host"], port=obj["port"],
        username=obj["username"], password=obj["password"],
    )
    result = {"saved": str(path)}
    output(result, obj["as_json"])


@config.command("test")
@click.pass_context
def config_test(ctx: click.Context):
    """Test connection to AdGuardHome."""
    client = make_client(ctx)
    data = server_core.get_status(client)
    result = {"connected": True, "host": ctx.obj["host"], "port": ctx.obj["port"], **data}
    output(result, ctx.obj["as_json"])


# ---------------------------------------------------------------------------
# server
# ---------------------------------------------------------------------------

@cli.group("server")
@click.pass_context
def server_(ctx: click.Context):
    """Server management."""


# Rename to avoid shadowing the module

@server_.command("status")
@click.pass_context
def server_status(ctx: click.Context):
    """Show server status."""
    client = make_client(ctx)
    data = server_core.get_status(client)
    output(data, ctx.obj["as_json"])


@server_.command("version")
@click.pass_context
def server_version(ctx: click.Context):
    """Show AdGuardHome version."""
    client = make_client(ctx)
    data = server_core.get_version(client)
    output(data, ctx.obj["as_json"])


@server_.command("restart")
@click.pass_context
def server_restart(ctx: click.Context):
    """Restart AdGuardHome."""
    client = make_client(ctx)
    data = server_core.restart(client)
    output(data or {"restarted": True}, ctx.obj["as_json"])


# ---------------------------------------------------------------------------
# filter
# ---------------------------------------------------------------------------

@cli.group("filter")
@click.pass_context
def filter_(ctx: click.Context):
    """Filtering rules management."""


@filter_.command("list")
@click.pass_context
def filter_list(ctx: click.Context):
    """List all filter subscriptions."""
    client = make_client(ctx)
    data = filtering_core.get_status(client)
    output(data, ctx.obj["as_json"])


@filter_.command("status")
@click.pass_context
def filter_status(ctx: click.Context):
    """Show filtering enabled/disabled state."""
    client = make_client(ctx)
    data = filtering_core.get_status(client)
    result = {"enabled": data.get("enabled"), "filters_count": len(data.get("filters", []))}
    output(result, ctx.obj["as_json"])


@filter_.command("toggle")
@click.argument("state", type=click.Choice(["on", "off"]))
@click.pass_context
def filter_toggle(ctx: click.Context, state: str):
    """Enable or disable filtering globally."""
    client = make_client(ctx)
    data = filtering_core.set_enabled(client, state == "on")
    output(data or {"filtering_enabled": state == "on"}, ctx.obj["as_json"])


@filter_.command("add")
@click.option("--url", required=True, help="Filter list URL")
@click.option("--name", required=True, help="Filter name")
@click.option("--whitelist", is_flag=True, default=False)
@click.pass_context
def filter_add(ctx: click.Context, url: str, name: str, whitelist: bool):
    """Add a new filter subscription."""
    client = make_client(ctx)
    data = filtering_core.add_filter(client, url=url, name=name, whitelist=whitelist)
    output(data or {"added": True, "url": url, "name": name}, ctx.obj["as_json"])


@filter_.command("remove")
@click.option("--url", required=True, help="Filter list URL to remove")
@click.option("--whitelist", is_flag=True, default=False)
@click.pass_context
def filter_remove(ctx: click.Context, url: str, whitelist: bool):
    """Remove a filter subscription."""
    client = make_client(ctx)
    data = filtering_core.remove_filter(client, url=url, whitelist=whitelist)
    output(data or {"removed": True, "url": url}, ctx.obj["as_json"])


@filter_.command("enable")
@click.option("--url", required=True)
@click.option("--name", required=True)
@click.option("--whitelist", is_flag=True, default=False)
@click.pass_context
def filter_enable(ctx: click.Context, url: str, name: str, whitelist: bool):
    """Enable a filter subscription."""
    client = make_client(ctx)
    data = filtering_core.set_filter_url(client, url=url, name=name, enabled=True,
                                    whitelist=whitelist)
    output(data or {"enabled": True, "url": url}, ctx.obj["as_json"])


@filter_.command("disable")
@click.option("--url", required=True)
@click.option("--name", required=True)
@click.option("--whitelist", is_flag=True, default=False)
@click.pass_context
def filter_disable(ctx: click.Context, url: str, name: str, whitelist: bool):
    """Disable a filter subscription."""
    client = make_client(ctx)
    data = filtering_core.set_filter_url(client, url=url, name=name, enabled=False,
                                    whitelist=whitelist)
    output(data or {"disabled": True, "url": url}, ctx.obj["as_json"])


@filter_.command("refresh")
@click.option("--whitelist", is_flag=True, default=False)
@click.pass_context
def filter_refresh(ctx: click.Context, whitelist: bool):
    """Trigger manual update of all filters."""
    client = make_client(ctx)
    data = filtering_core.refresh(client, whitelist=whitelist)
    output(data or {"refreshed": True}, ctx.obj["as_json"])


# ---------------------------------------------------------------------------
# blocking
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def blocking(ctx: click.Context):
    """Parental, safebrowsing, safesearch controls."""


@blocking.group()
def parental():
    """Parental control."""


@parental.command("status")
@click.pass_context
def parental_status(ctx: click.Context):
    client = make_client(ctx)
    output(blocking_core.parental_status(client), ctx.obj["as_json"])


@parental.command("enable")
@click.pass_context
def parental_enable(ctx: click.Context):
    client = make_client(ctx)
    output(blocking_core.parental_enable(client) or {"enabled": True}, ctx.obj["as_json"])


@parental.command("disable")
@click.pass_context
def parental_disable(ctx: click.Context):
    client = make_client(ctx)
    output(blocking_core.parental_disable(client) or {"disabled": True}, ctx.obj["as_json"])


@blocking.group()
def safebrowsing():
    """Safe browsing control."""


@safebrowsing.command("status")
@click.pass_context
def safebrowsing_status(ctx: click.Context):
    client = make_client(ctx)
    output(blocking_core.safebrowsing_status(client), ctx.obj["as_json"])


@safebrowsing.command("enable")
@click.pass_context
def safebrowsing_enable(ctx: click.Context):
    client = make_client(ctx)
    output(blocking_core.safebrowsing_enable(client) or {"enabled": True}, ctx.obj["as_json"])


@safebrowsing.command("disable")
@click.pass_context
def safebrowsing_disable(ctx: click.Context):
    client = make_client(ctx)
    output(blocking_core.safebrowsing_disable(client) or {"disabled": True}, ctx.obj["as_json"])


@blocking.group()
def safesearch():
    """Safe search control."""


@safesearch.command("status")
@click.pass_context
def safesearch_status(ctx: click.Context):
    client = make_client(ctx)
    output(blocking_core.safesearch_status(client), ctx.obj["as_json"])


@safesearch.command("enable")
@click.pass_context
def safesearch_enable(ctx: click.Context):
    client = make_client(ctx)
    output(blocking_core.safesearch_enable(client) or {"enabled": True}, ctx.obj["as_json"])


@safesearch.command("disable")
@click.pass_context
def safesearch_disable(ctx: click.Context):
    client = make_client(ctx)
    output(blocking_core.safesearch_disable(client) or {"disabled": True}, ctx.obj["as_json"])


# ---------------------------------------------------------------------------
# blocked-services
# ---------------------------------------------------------------------------

@cli.group("blocked-services")
@click.pass_context
def blocked_services(ctx: click.Context):
    """Blocked service categories."""


@blocked_services.command("list")
@click.pass_context
def blocked_services_list(ctx: click.Context):
    client = make_client(ctx)
    output(blocking_core.blocked_services_get(client), ctx.obj["as_json"])


@blocked_services.command("set")
@click.argument("services", nargs=-1, required=True)
@click.pass_context
def blocked_services_set(ctx: click.Context, services: tuple):
    client = make_client(ctx)
    output(blocking_core.blocked_services_set(client, list(services)) or {"set": list(services)},
           ctx.obj["as_json"])


# ---------------------------------------------------------------------------
# clients
# ---------------------------------------------------------------------------

@cli.group("clients")
@click.pass_context
def clients_(ctx: click.Context):
    """Known client management."""



@clients_.command("list")
@click.pass_context
def clients_list(ctx: click.Context):
    client = make_client(ctx)
    output(clients_core.list_clients(client), ctx.obj["as_json"])


@clients_.command("add")
@click.option("--name", required=True)
@click.option("--ip", required=True, help="Client IP address")
@click.pass_context
def clients_add(ctx: click.Context, name: str, ip: str):
    c = make_client(ctx)
    output(clients_core.add_client(c, name=name, ids=[ip]) or {"added": True, "name": name},
           ctx.obj["as_json"])


@clients_.command("remove")
@click.option("--name", required=True)
@click.pass_context
def clients_remove(ctx: click.Context, name: str):
    c = make_client(ctx)
    output(clients_core.delete_client(c, name=name) or {"removed": True, "name": name},
           ctx.obj["as_json"])


@clients_.command("show")
@click.option("--name", required=True)
@click.pass_context
def clients_show(ctx: click.Context, name: str):
    c = make_client(ctx)
    data = clients_core.list_clients(c)
    all_clients = data.get("clients", []) if isinstance(data, dict) else []
    found = next((cl for cl in all_clients if cl.get("name") == name), None)
    output(found or {"error": f"Client '{name}' not found"}, ctx.obj["as_json"])


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

@cli.group("stats")
@click.pass_context
def stats_(ctx: click.Context):
    """DNS query statistics."""



@stats_.command("show")
@click.pass_context
def stats_show(ctx: click.Context):
    client = make_client(ctx)
    output(stats_core.get_stats(client), ctx.obj["as_json"])


@stats_.command("reset")
@click.pass_context
def stats_reset(ctx: click.Context):
    client = make_client(ctx)
    output(stats_core.reset_stats(client) or {"reset": True}, ctx.obj["as_json"])


@stats_.command("config")
@click.option("--interval", type=int, default=None, help="Retention in days")
@click.pass_context
def stats_config(ctx: click.Context, interval):
    client = make_client(ctx)
    if interval is not None:
        output(stats_core.set_stats_config(client, interval), ctx.obj["as_json"])
    else:
        output(stats_core.get_stats_config(client), ctx.obj["as_json"])


# ---------------------------------------------------------------------------
# log
# ---------------------------------------------------------------------------

@cli.group("log")
@click.pass_context
def log_(ctx: click.Context):
    """Query log management."""



@log_.command("show")
@click.option("--limit", default=50, type=int)
@click.option("--offset", default=0, type=int)
@click.pass_context
def log_show(ctx: click.Context, limit: int, offset: int):
    client = make_client(ctx)
    output(log_core.get_log(client, limit=limit, offset=offset), ctx.obj["as_json"])


@log_.command("config")
@click.option("--enabled/--disabled", default=None)
@click.option("--interval", type=int, default=None)
@click.pass_context
def log_config(ctx: click.Context, enabled, interval):
    client = make_client(ctx)
    if enabled is not None:
        output(log_core.set_log_config(client, enabled=enabled,
                                  interval=interval or 90), ctx.obj["as_json"])
    else:
        output(log_core.get_log_config(client), ctx.obj["as_json"])


@log_.command("clear")
@click.pass_context
def log_clear(ctx: click.Context):
    client = make_client(ctx)
    output(log_core.clear_log(client) or {"cleared": True}, ctx.obj["as_json"])


# ---------------------------------------------------------------------------
# rewrite
# ---------------------------------------------------------------------------

@cli.group("rewrite")
@click.pass_context
def rewrite_(ctx: click.Context):
    """DNS rewrite rules."""



@rewrite_.command("list")
@click.pass_context
def rewrite_list(ctx: click.Context):
    client = make_client(ctx)
    output(rewrite_core.list_rewrites(client), ctx.obj["as_json"])


@rewrite_.command("add")
@click.option("--domain", required=True)
@click.option("--answer", required=True)
@click.pass_context
def rewrite_add(ctx: click.Context, domain: str, answer: str):
    client = make_client(ctx)
    output(rewrite_core.add_rewrite(client, domain=domain, answer=answer) or
           {"added": True, "domain": domain, "answer": answer}, ctx.obj["as_json"])


@rewrite_.command("remove")
@click.option("--domain", required=True)
@click.option("--answer", required=True)
@click.pass_context
def rewrite_remove(ctx: click.Context, domain: str, answer: str):
    client = make_client(ctx)
    output(rewrite_core.delete_rewrite(client, domain=domain, answer=answer) or
           {"removed": True, "domain": domain}, ctx.obj["as_json"])


# ---------------------------------------------------------------------------
# dhcp
# ---------------------------------------------------------------------------

@cli.group("dhcp")
@click.pass_context
def dhcp_(ctx: click.Context):
    """DHCP server management."""



@dhcp_.command("status")
@click.pass_context
def dhcp_status(ctx: click.Context):
    client = make_client(ctx)
    output(dhcp_core.get_status(client), ctx.obj["as_json"])


@dhcp_.command("leases")
@click.pass_context
def dhcp_leases(ctx: click.Context):
    client = make_client(ctx)
    output(dhcp_core.get_leases(client), ctx.obj["as_json"])


@dhcp_.command("add-static")
@click.option("--mac", required=True)
@click.option("--ip", required=True)
@click.option("--hostname", default="")
@click.pass_context
def dhcp_add_static(ctx: click.Context, mac: str, ip: str, hostname: str):
    client = make_client(ctx)
    output(dhcp_core.add_static_lease(client, mac=mac, ip=ip, hostname=hostname) or
           {"added": True, "mac": mac, "ip": ip}, ctx.obj["as_json"])


@dhcp_.command("remove-static")
@click.option("--mac", required=True)
@click.option("--ip", required=True)
@click.option("--hostname", default="")
@click.pass_context
def dhcp_remove_static(ctx: click.Context, mac: str, ip: str, hostname: str):
    client = make_client(ctx)
    output(dhcp_core.remove_static_lease(client, mac=mac, ip=ip, hostname=hostname) or
           {"removed": True, "mac": mac}, ctx.obj["as_json"])


# ---------------------------------------------------------------------------
# tls
# ---------------------------------------------------------------------------

@cli.group("tls")
@click.pass_context
def tls_(ctx: click.Context):
    """TLS/HTTPS configuration."""



@tls_.command("status")
@click.pass_context
def tls_status(ctx: click.Context):
    client = make_client(ctx)
    output(server_core.get_tls_status(client), ctx.obj["as_json"])
