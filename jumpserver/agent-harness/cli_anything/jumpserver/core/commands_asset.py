"""
Asset management commands for JumpServer CLI.

Manages hosts, devices, databases, nodes, platforms, gateways, and zones.
"""
import click

from cli_anything.jumpserver.core.session import Session
from cli_anything.jumpserver.utils import (
    require_auth,
    handle_api_error,
    parse_ids,
    print_result,
    should_emit_human_text,
)


@click.group(name="asset")
def asset_group():
    """Manage assets (hosts, devices, databases, nodes, etc.)."""
    pass


# ─── Assets CRUD ──────────────────────────────────────────────


@asset_group.command(name="list")
@click.option("--type", "-t", "asset_type", type=click.Choice(["host", "device", "database", "web", "cloud", "gpt", "ds", "custom"]), default="host", help="Asset type")
@click.option("--search", "-s", default=None, help="Search by name or address")
@click.option("--node", "-n", default=None, help="Filter by node ID")
@click.option("--platform", "-p", default=None, help="Filter by platform ID")
@click.option("--active/--inactive", default=None, help="Filter by active status")
@click.option("--limit", default=20, help="Results per page")
@click.option("--offset", default=0, help="Pagination offset")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--columns", "-c", default=None, help="Comma-separated column names")
def list_assets(asset_type, search, node, platform, active, limit, offset, output, columns):
    """List assets of a given type."""
    session = Session.load()
    client = require_auth(session)

    type_map = {
        "host": "hosts", "device": "devices", "database": "databases",
        "web": "webs", "cloud": "clouds", "gpt": "gpts",
        "ds": "directories", "custom": "customs",
    }
    endpoint = type_map.get(asset_type, "hosts")

    params = {"limit": limit, "offset": offset}
    if search:
        params["search"] = search
    if node:
        params["node"] = node
    if platform:
        params["platform"] = platform
    if active is not None:
        params["is_active"] = str(active).lower()

    resp = client.get(f"assets/{endpoint}/", params=params)
    handle_api_error(resp, "list assets")
    print_result(resp.json(), fmt=output, columns=columns)


@asset_group.command(name="get")
@click.argument("asset_id")
@click.option("--type", "-t", "asset_type", type=click.Choice(["host", "device", "database", "web", "cloud", "gpt", "ds", "custom"]), default="host", help="Asset type")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def get_asset(asset_id, asset_type, output):
    """Get details of a specific asset."""
    session = Session.load()
    client = require_auth(session)

    type_map = {
        "host": "hosts", "device": "devices", "database": "databases",
        "web": "webs", "cloud": "clouds", "gpt": "gpts",
        "ds": "directories", "custom": "customs",
    }
    endpoint = type_map.get(asset_type, "hosts")

    resp = client.get(f"assets/{endpoint}/{asset_id}/")
    handle_api_error(resp, "get asset")
    print_result(resp.json(), fmt=output)


@asset_group.command(name="create")
@click.option("--name", required=True, help="Asset name")
@click.option("--address", required=True, help="IP address or hostname")
@click.option("--platform", "-p", required=True, type=int, help="Platform ID")
@click.option("--type", "-t", "asset_type", type=click.Choice(["host", "device", "database", "web", "cloud", "gpt", "ds", "custom"]), default="host", help="Asset type")
@click.option("--nodes", default=None, help="Comma-separated node IDs")
@click.option("--comment", default=None, help="Comment")
@click.option("--domain", default=None, help="Domain (for domain assets)")
@click.option("--active/--inactive", default=True, help="Active status")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def create_asset(name, address, platform, asset_type, nodes, comment, domain, active, output, dry_run):
    """Create a new asset."""
    type_map = {
        "host": "hosts", "device": "devices", "database": "databases",
        "web": "webs", "cloud": "clouds", "gpt": "gpts",
        "ds": "directories", "custom": "customs",
    }
    endpoint = type_map.get(asset_type, "hosts")

    data = {
        "name": name,
        "address": address,
        "platform": platform,
        "is_active": active,
    }
    if nodes:
        data["nodes"] = parse_ids(nodes)
    if comment:
        data["comment"] = comment
    if domain:
        data["domain"] = domain

    if dry_run:
        print_result({"action": "create", "endpoint": f"assets/{endpoint}/", "data": data}, fmt=output)
        return

    session = Session.load()
    client = require_auth(session)

    resp = client.post(f"assets/{endpoint}/", data=data)
    handle_api_error(resp, "create asset")
    print_result(resp.json(), fmt=output)
    if should_emit_human_text(output):
        click.echo(click.style(f"\n✓ Asset '{name}' created.", fg="green"))


@asset_group.command(name="update")
@click.argument("asset_id")
@click.option("--type", "-t", "asset_type", type=click.Choice(["host", "device", "database", "web", "cloud", "gpt", "ds", "custom"]), default="host", help="Asset type")
@click.option("--name", default=None, help="New name")
@click.option("--address", default=None, help="New address")
@click.option("--comment", default=None, help="New comment")
@click.option("--active/--inactive", default=None, help="Set active status")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def update_asset(asset_id, asset_type, name, address, comment, active, output, dry_run):
    """Update an existing asset."""
    session = Session.load()
    client = require_auth(session)

    type_map = {
        "host": "hosts", "device": "devices", "database": "databases",
        "web": "webs", "cloud": "clouds", "gpt": "gpts",
        "ds": "directories", "custom": "customs",
    }
    endpoint = type_map.get(asset_type, "hosts")

    data = {}
    if name is not None:
        data["name"] = name
    if address is not None:
        data["address"] = address
    if comment is not None:
        data["comment"] = comment
    if active is not None:
        data["is_active"] = active

    if dry_run:
        print_result({"action": "update", "endpoint": f"assets/{endpoint}/{asset_id}/", "data": data}, fmt=output)
        return

    resp = client.put(f"assets/{endpoint}/{asset_id}/", data=data)
    handle_api_error(resp, "update asset")
    print_result(resp.json(), fmt=output)
    if should_emit_human_text(output):
        click.echo(click.style(f"\n✓ Asset '{asset_id}' updated.", fg="green"))


@asset_group.command(name="delete")
@click.argument("asset_id")
@click.option("--type", "-t", "asset_type", type=click.Choice(["host", "device", "database", "web", "cloud", "gpt", "ds", "custom"]), default="host", help="Asset type")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def delete_asset(asset_id, asset_type, force, dry_run):
    """Delete an asset."""
    if dry_run:
        click.echo(f"[DRY RUN] Would delete {asset_type} asset: {asset_id}")
        return

    if not force:
        click.confirm(f"Delete {asset_type} asset '{asset_id}'?", abort=True)

    session = Session.load()
    client = require_auth(session)

    type_map = {
        "host": "hosts", "device": "devices", "database": "databases",
        "web": "webs", "cloud": "clouds", "gpt": "gpts",
        "ds": "directories", "custom": "customs",
    }
    endpoint = type_map.get(asset_type, "hosts")

    resp = client.delete(f"assets/{endpoint}/{asset_id}/")
    handle_api_error(resp, "delete asset")
    click.echo(click.style(f"✓ Asset '{asset_id}' deleted.", fg="green"))


# ─── Nodes ────────────────────────────────────────────────────


@asset_group.group(name="node")
def node_group():
    """Manage asset nodes (tree organization)."""
    pass


@node_group.command(name="list")
@click.option("--parent", "-p", default=None, help="Parent node ID or key")
@click.option("--search", "-s", default=None, help="Search by name")
@click.option("--tree", is_flag=True, help="Show full tree")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def list_nodes(parent, search, tree, output):
    """List asset nodes."""
    session = Session.load()
    client = require_auth(session)

    if tree:
        resp = client.get("assets/nodes/children/tree/")
    elif parent:
        resp = client.get(f"assets/nodes/{parent}/children/")
    else:
        params = {}
        if search:
            params["search"] = search
        resp = client.get("assets/nodes/", params=params)

    handle_api_error(resp, "list nodes")
    data = resp.json()
    print_result(data, fmt=output)

    if should_emit_human_text(output) and isinstance(data, list):
        _print_node_tree(data)


def _print_node_tree(nodes, indent=0):
    """Helper to print node tree structure."""
    for node in nodes:
        prefix = "  " * indent + ("├── " if indent > 0 else "")
        name = node.get("name", node.get("value", str(node)))
        node_id = node.get("id", "")
        click.echo(f"{prefix}{name} ({node_id})")
        children = node.get("children", [])
        if children:
            _print_node_tree(children, indent + 1)


@node_group.command(name="create")
@click.option("--name", required=True, help="Node name")
@click.option("--parent", "-p", default=None, help="Parent node ID")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def create_node(name, parent, output, dry_run):
    """Create a new asset node."""
    session = Session.load()
    client = require_auth(session)

    data = {"value": name}
    if parent:
        data["parent"] = parent

    if dry_run:
        print_result({"action": "create node", "data": data}, fmt=output)
        return

    resp = client.post("assets/nodes/", data=data)
    handle_api_error(resp, "create node")
    print_result(resp.json(), fmt=output)
    if should_emit_human_text(output):
        click.echo(click.style(f"\n✓ Node '{name}' created.", fg="green"))


@node_group.command(name="delete")
@click.argument("node_id")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def delete_node(node_id, force, dry_run):
    """Delete an asset node."""
    if dry_run:
        click.echo(f"[DRY RUN] Would delete node: {node_id}")
        return
    if not force:
        click.confirm(f"Delete node '{node_id}'?", abort=True)

    session = Session.load()
    client = require_auth(session)
    resp = client.delete(f"assets/nodes/{node_id}/")
    handle_api_error(resp, "delete node")
    click.echo(click.style(f"✓ Node '{node_id}' deleted.", fg="green"))


@node_group.command(name="add-assets")
@click.argument("node_id")
@click.option("--assets", "-a", required=True, help="Comma-separated asset IDs")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def add_assets_to_node(node_id, assets, output, dry_run):
    """Add assets to a node."""
    asset_ids = parse_ids(assets)
    if dry_run:
        print_result({"action": "add assets to node", "node": node_id, "assets": asset_ids}, fmt=output)
        return

    session = Session.load()
    client = require_auth(session)
    resp = client.post(f"assets/nodes/{node_id}/assets/add/", data={"assets": asset_ids})
    handle_api_error(resp, "add assets to node")
    print_result(resp.json(), fmt=output)
    if should_emit_human_text(output):
        click.echo(click.style(f"\n✓ Assets added to node '{node_id}'.", fg="green"))


# ─── Platforms ─────────────────────────────────────────────────


@asset_group.group(name="platform")
def platform_group():
    """Manage asset platforms."""
    pass


@platform_group.command(name="list")
@click.option("--search", "-s", default=None, help="Search by name")
@click.option("--category", "-c", default=None, help="Filter by category")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def list_platforms(search, category, output):
    """List asset platforms."""
    session = Session.load()
    client = require_auth(session)

    params = {}
    if search:
        params["search"] = search
    if category:
        params["category"] = category

    resp = client.get("assets/platforms/", params=params)
    handle_api_error(resp, "list platforms")
    print_result(resp.json(), fmt=output)


# ─── Gateways ──────────────────────────────────────────────────


@asset_group.group(name="gateway")
def gateway_group():
    """Manage gateways."""
    pass


@gateway_group.command(name="list")
@click.option("--search", "-s", default=None, help="Search by name or address")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def list_gateways(search, output):
    """List gateways."""
    session = Session.load()
    client = require_auth(session)

    params = {}
    if search:
        params["search"] = search

    resp = client.get("assets/gateways/", params=params)
    handle_api_error(resp, "list gateways")
    print_result(resp.json(), fmt=output)


@gateway_group.command(name="test")
@click.argument("gateway_id")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def test_gateway(gateway_id, output):
    """Test gateway connectivity."""
    session = Session.load()
    client = require_auth(session)
    resp = client.get(f"assets/gateways/{gateway_id}/test-connective/")
    handle_api_error(resp, "test gateway")
    print_result(resp.json(), fmt=output)


# ─── Zones ─────────────────────────────────────────────────────


@asset_group.group(name="zone")
def zone_group():
    """Manage zones (network domains)."""
    pass


@zone_group.command(name="list")
@click.option("--search", "-s", default=None, help="Search by name")
@click.option("--output", "-o", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
def list_zones(search, output):
    """List zones."""
    session = Session.load()
    client = require_auth(session)

    params = {}
    if search:
        params["search"] = search

    resp = client.get("assets/zones/", params=params)
    handle_api_error(resp, "list zones")
    print_result(resp.json(), fmt=output)
