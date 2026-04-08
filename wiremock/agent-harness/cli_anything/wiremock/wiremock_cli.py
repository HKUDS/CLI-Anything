import json
import requests
import click
from cli_anything.wiremock.utils.client import WireMockClient
from cli_anything.wiremock.utils.output import error, print_json, print_table, success
from cli_anything.wiremock.core.recording import RecordingManager
from cli_anything.wiremock.core.requests_log import RequestsLog
from cli_anything.wiremock.core.scenarios import ScenariosManager
from cli_anything.wiremock.core.session import Session
from cli_anything.wiremock.core.settings import SettingsManager
from cli_anything.wiremock.core.stubs import StubsManager

@click.group()
@click.option(
    "--host",
    default=None,
    envvar="WIREMOCK_HOST",
    help="WireMock host (default: localhost)",
)
@click.option(
    "--port",
    default=None,
    type=int,
    envvar="WIREMOCK_PORT",
    help="WireMock port (default: 8080)",
)
@click.option(
    "--scheme",
    default=None,
    envvar="WIREMOCK_SCHEME",
    help="http or https (default: http)",
)
@click.option(
    "--user", default=None, envvar="WIREMOCK_USER", help="Admin basic auth username"
)
@click.option(
    "--password",
    default=None,
    envvar="WIREMOCK_PASSWORD",
    help="Admin basic auth password",
)
@click.option(
    "--json",
    "json_mode",
    is_flag=True,
    envvar="WIREMOCK_JSON",
    help="Output as JSON",
)
@click.pass_context
def cli(ctx, host, port, scheme, user, password, json_mode):
    """WireMock CLI — manage stubs, requests, scenarios, and recordings."""
    session = Session.from_env()
    if host is not None:
        session.host = host
    if port is not None:
        session.port = port
    if scheme is not None:
        session.scheme = scheme
    if user is not None:
        session.username = user
    if password is not None:
        session.password = password
    client = WireMockClient(
        host=session.host,
        port=session.port,
        scheme=session.scheme,
        auth=session.auth(),
    )
    ctx.obj = client
    ctx.meta["json_mode"] = json_mode


# ---------------------------------------------------------------------------
# STUB COMMANDS
# ---------------------------------------------------------------------------


@cli.group()
def stub():
    """Manage HTTP stub mappings."""


@stub.command("list")
@click.option("--limit", type=int, default=None)
@click.option("--offset", type=int, default=None)
@click.pass_context
def stub_list(ctx, limit, offset):
    """List all stub mappings."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    mgr = StubsManager(client)
    try:
        data = mgr.list(limit=limit, offset=offset)
        if json_mode:
            print_json(data)
        else:
            mappings = data.get("mappings", [])
            rows = [
                (
                    m.get("id", "")[:8] + "...",
                    m.get("name", ""),
                    m.get("request", {}).get("method", ""),
                    m.get("request", {}).get("url", ""),
                    m.get("response", {}).get("status", ""),
                )
                for m in mappings
            ]
            print_table(
                ["ID", "Name", "Method", "URL", "Status"],
                rows,
                title=f"Stubs ({data.get('total', 0)} total)",
            )
    except Exception as e:
        error(str(e), json_mode)


@stub.command("get")
@click.argument("stub_id")
@click.pass_context
def stub_get(ctx, stub_id):
    """Get a stub mapping by ID."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        data = StubsManager(client).get(stub_id)
        if json_mode:
            print_json(data)
        else:
            success(
                f"Stub {data.get('id', stub_id)[:8]}... "
                f"{data.get('request', {}).get('method', '')} "
                f"{data.get('request', {}).get('url', '')}",
                data,
            )
    except Exception as e:
        error(str(e), json_mode)


@stub.command("create")
@click.argument("mapping_json")
@click.pass_context
def stub_create(ctx, mapping_json):
    """Create a stub mapping from JSON string or @file."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        if mapping_json.startswith("@"):
            with open(mapping_json[1:], encoding="utf-8") as f:
                mapping = json.load(f)
        else:
            mapping = json.loads(mapping_json)
        data = StubsManager(client).create(mapping)
        if json_mode:
            print_json(data)
        else:
            success(f"Created stub {data.get('id')}", data)
    except Exception as e:
        error(str(e), json_mode)


@stub.command("quick")
@click.argument("method")
@click.argument("url")
@click.argument("status", type=int)
@click.option("--body", default=None, help="Response body")
@click.option("--content-type", default="application/json")
@click.pass_context
def stub_quick(ctx, method, url, status, body, content_type):
    """Quickly create a stub: METHOD URL STATUS [--body TEXT]."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        data = StubsManager(client).quick_stub(method, url, status, body, content_type)
        if json_mode:
            print_json(data)
        else:
            success(f"Created stub {data.get('id')}", data)
    except Exception as e:
        error(str(e), json_mode)


@stub.command("delete")
@click.argument("stub_id")
@click.pass_context
def stub_delete(ctx, stub_id):
    """Delete a stub mapping by ID."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        StubsManager(client).delete(stub_id)
        if json_mode:
            print_json({"status": "ok"})
        else:
            success(f"Deleted stub {stub_id}")
    except Exception as e:
        error(str(e), json_mode)


@stub.command("reset")
@click.pass_context
def stub_reset(ctx):
    """Reset all stubs to defaults."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        StubsManager(client).reset()
        if json_mode:
            print_json({"status": "ok"})
        else:
            success("Stubs reset to default mappings")
    except Exception as e:
        error(str(e), json_mode)


@stub.command("save")
@click.pass_context
def stub_save(ctx):
    """Persist stubs to disk."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        StubsManager(client).save()
        if json_mode:
            print_json({"status": "ok"})
        else:
            success("Mappings saved to disk")
    except Exception as e:
        error(str(e), json_mode)


@stub.command("import")
@click.argument("file_path")
@click.pass_context
def stub_import(ctx, file_path):
    """Import stubs from a JSON file."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        result = StubsManager(client).import_stubs(data)
        if json_mode:
            print_json(result)
        else:
            success("Stubs imported", result)
    except Exception as e:
        error(str(e), json_mode)


# ---------------------------------------------------------------------------
# REQUEST COMMANDS
# ---------------------------------------------------------------------------


@cli.group()
def request():
    """Inspect and verify served requests."""


@request.command("list")
@click.option("--limit", type=int, default=None)
@click.pass_context
def request_list(ctx, limit):
    """List recent served requests."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        data = RequestsLog(client).list(limit=limit)
        if json_mode:
            print_json(data)
        else:
            events = data.get("serveEvents", [])
            rows = [
                (
                    e.get("id", "")[:8] + "...",
                    e.get("request", {}).get("method", ""),
                    e.get("request", {}).get("url", ""),
                    e.get("responseDefinition", {}).get("status", ""),
                    e.get("wasMatched", ""),
                )
                for e in events
            ]
            print_table(
                ["ID", "Method", "URL", "Status", "Matched"],
                rows,
                title=f"Requests ({data.get('total', 0)} total)",
            )
    except Exception as e:
        error(str(e), json_mode)


@request.command("find")
@click.argument("pattern_json")
@click.pass_context
def request_find(ctx, pattern_json):
    """Find requests matching a pattern JSON."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        pattern = json.loads(pattern_json)
        data = RequestsLog(client).find(pattern)
        if json_mode:
            print_json(data)
        else:
            requests_list = data.get("requests", [])
            rows = [
                (
                    r.get("request", {}).get("method", ""),
                    r.get("request", {}).get("url", ""),
                    r.get("responseDefinition", {}).get("status", ""),
                )
                for r in requests_list
            ]
            print_table(
                ["Method", "URL", "Status"],
                rows,
                title=f"Matching requests ({len(requests_list)})",
            )
    except Exception as e:
        error(str(e), json_mode)


@request.command("count")
@click.argument("pattern_json")
@click.pass_context
def request_count(ctx, pattern_json):
    """Count requests matching a pattern JSON."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        pattern = json.loads(pattern_json)
        data = RequestsLog(client).count(pattern)
        if json_mode:
            print_json(data)
        else:
            click.echo(f"Count: {data.get('count', 0)}")
    except Exception as e:
        error(str(e), json_mode)


@request.command("unmatched")
@click.pass_context
def request_unmatched(ctx):
    """List unmatched requests."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        data = RequestsLog(client).unmatched()
        if json_mode:
            print_json(data)
        else:
            requests_list = data.get("requests", [])
            rows = [
                (
                    r.get("request", {}).get("method", ""),
                    r.get("request", {}).get("url", ""),
                )
                for r in requests_list
            ]
            print_table(
                ["Method", "URL"],
                rows,
                title=f"Unmatched requests ({len(requests_list)})",
            )
    except Exception as e:
        error(str(e), json_mode)


@request.command("reset")
@click.pass_context
def request_reset(ctx):
    """Clear the request journal."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        RequestsLog(client).reset()
        if json_mode:
            print_json({"status": "ok"})
        else:
            success("Request journal cleared")
    except Exception as e:
        error(str(e), json_mode)


# ---------------------------------------------------------------------------
# SCENARIO COMMANDS
# ---------------------------------------------------------------------------


@cli.group()
def scenario():
    """Manage state machine scenarios."""


@scenario.command("list")
@click.pass_context
def scenario_list(ctx):
    """List all scenarios."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        data = ScenariosManager(client).list()
        if json_mode:
            print_json(data)
        else:
            scenarios = data.get("scenarios", [])
            rows = [
                (
                    s.get("name", ""),
                    s.get("state", ""),
                    s.get("possibleStates", ""),
                )
                for s in scenarios
            ]
            print_table(
                ["Name", "Current State", "Possible States"],
                rows,
                title="Scenarios",
            )
    except Exception as e:
        error(str(e), json_mode)


@scenario.command("set")
@click.argument("name")
@click.argument("state")
@click.pass_context
def scenario_set(ctx, name, state):
    """Set a scenario state."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        ScenariosManager(client).set_state(name, state)
        if json_mode:
            print_json({"status": "ok"})
        else:
            success(f"Scenario '{name}' set to state '{state}'")
    except Exception as e:
        error(str(e), json_mode)


@scenario.command("reset")
@click.pass_context
def scenario_reset(ctx):
    """Reset all scenarios."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        ScenariosManager(client).reset_all()
        if json_mode:
            print_json({"status": "ok"})
        else:
            success("All scenarios reset")
    except Exception as e:
        error(str(e), json_mode)


# ---------------------------------------------------------------------------
# RECORD COMMANDS
# ---------------------------------------------------------------------------


@cli.group()
def record():
    """Record traffic from a real backend."""


@record.command("start")
@click.argument("target_url")
@click.option(
    "--match-header", multiple=True, help="Headers to capture (can repeat)"
)
@click.pass_context
def record_start(ctx, target_url, match_header):
    """Start recording traffic proxied to TARGET_URL."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        data = RecordingManager(client).start(
            target_url, list(match_header) or None
        )
        if json_mode:
            print_json(data)
        else:
            success(f"Recording started → {target_url}", data)
    except Exception as e:
        error(str(e), json_mode)


@record.command("stop")
@click.pass_context
def record_stop(ctx):
    """Stop recording and return captured stubs."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        data = RecordingManager(client).stop()
        if json_mode:
            print_json(data)
        else:
            count = len(data.get("mappings", []))
            success(f"Recording stopped. {count} stubs captured.", data)
    except Exception as e:
        error(str(e), json_mode)


@record.command("status")
@click.pass_context
def record_status(ctx):
    """Check recording status."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        data = RecordingManager(client).status()
        if json_mode:
            print_json(data)
        else:
            click.echo(f"Status: {data.get('status', 'unknown')}")
    except Exception as e:
        error(str(e), json_mode)


@record.command("snapshot")
@click.pass_context
def record_snapshot(ctx):
    """Take a snapshot of current traffic as stubs."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        data = RecordingManager(client).snapshot()
        if json_mode:
            print_json(data)
        else:
            count = len(data.get("mappings", []))
            success(f"Snapshot: {count} stubs captured", data)
    except Exception as e:
        error(str(e), json_mode)


# ---------------------------------------------------------------------------
# SETTINGS COMMANDS
# ---------------------------------------------------------------------------


@cli.group()
def settings():
    """Manage global WireMock settings."""


@settings.command("get")
@click.pass_context
def settings_get(ctx):
    """Get current global settings."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        data = SettingsManager(client).get()
        print_json(data)
    except Exception as e:
        error(str(e), json_mode)


@settings.command("version")
@click.pass_context
def settings_version(ctx):
    """Show WireMock server version."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        data = SettingsManager(client).get_version()
        if json_mode:
            print_json(data)
        else:
            click.echo(f"WireMock version: {data.get('version', 'unknown')}")
    except Exception as e:
        error(str(e), json_mode)


# ---------------------------------------------------------------------------
# TOP-LEVEL COMMANDS
# ---------------------------------------------------------------------------


@cli.command()
@click.pass_context
def status(ctx):
    """Check if WireMock server is running."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    alive = client.is_alive()
    if json_mode:
        print_json(
            {
                "status": "running" if alive else "stopped",
                "host": client.host,
                "port": client.port,
            }
        )
    else:
        icon = "✓" if alive else "✗"
        state = "running" if alive else "stopped"
        click.echo(f"{icon} WireMock at {client.host}:{client.port} is {state}")


@cli.command("reset")
@click.pass_context
def reset_all(ctx):
    """Full reset: stubs + requests + scenarios."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        r = client.post("/reset")
        r.raise_for_status()
        if json_mode:
            print_json({"status": "ok"})
        else:
            success("Full reset complete")
    except Exception as e:
        error(str(e), json_mode)


@cli.command("shutdown")
@click.confirmation_option(prompt="Shutdown the WireMock server?")
@click.pass_context
def shutdown(ctx):
    """Shutdown the WireMock server."""
    client = ctx.obj
    json_mode = ctx.meta.get("json_mode", False)
    try:
        r = client.post("/shutdown")
        r.raise_for_status()
        if json_mode:
            print_json({"status": "ok", "message": "Shutdown signal sent"})
        else:
            click.echo("Shutdown signal sent")
    except (ConnectionError, requests.exceptions.ConnectionError):
        # Server drops connection on successful shutdown — this is expected
        if json_mode:
            print_json({"status": "ok", "message": "Shutdown signal sent"})
        else:
            click.echo("Shutdown signal sent (server connection closed)")
    except Exception as e:
        error(str(e), json_mode)


if __name__ == "__main__":
    cli()
