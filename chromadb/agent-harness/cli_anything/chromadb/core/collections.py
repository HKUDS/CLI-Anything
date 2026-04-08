"""Collection commands -- list, create, delete, info."""

import json as json_mod
import click

from ..utils.chromadb_backend import ChromaDBBackend


@click.group("collection")
@click.pass_context
def collection_group(ctx):
    """Manage ChromaDB collections."""
    pass


@collection_group.command("list")
@click.pass_context
def list_collections(ctx):
    """List all collections."""
    backend: ChromaDBBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        collections = backend.list_collections()
        if use_json:
            click.echo(json_mod.dumps(collections, indent=2))
        else:
            if not collections:
                skin.info("No collections found.")
                return
            headers = ["Name", "ID", "Metadata"]
            rows = []
            for c in collections:
                name = c.get("name", "?")
                cid = c.get("id", "?")
                meta = json_mod.dumps(c.get("metadata") or {})
                rows.append([name, cid, meta])
            skin.table(headers, rows)
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to list collections: {e}")
        raise SystemExit(1)


@collection_group.command("create")
@click.option("--name", required=True, help="Collection name")
@click.option("--metadata", default=None, help="Metadata as JSON string")
@click.pass_context
def create_collection(ctx, name, metadata):
    """Create a new collection."""
    backend: ChromaDBBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        meta = json_mod.loads(metadata) if metadata else None
        result = backend.create_collection(name, metadata=meta)
        if use_json:
            click.echo(json_mod.dumps(result, indent=2))
        else:
            skin.success(f"Collection '{name}' created")
            skin.status("ID", result.get("id", "?"))
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to create collection: {e}")
        raise SystemExit(1)


@collection_group.command("delete")
@click.option("--name", required=True, help="Collection name to delete")
@click.pass_context
def delete_collection(ctx, name):
    """Delete a collection."""
    backend: ChromaDBBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        backend.delete_collection(name)
        if use_json:
            click.echo(json_mod.dumps({"status": "deleted", "name": name}, indent=2))
        else:
            skin.success(f"Collection '{name}' deleted")
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to delete collection: {e}")
        raise SystemExit(1)


@collection_group.command("info")
@click.argument("name")
@click.pass_context
def collection_info(ctx, name):
    """Get info about a collection."""
    backend: ChromaDBBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        info = backend.get_collection(name)
        if use_json:
            click.echo(json_mod.dumps(info, indent=2))
        else:
            skin.section(f"Collection: {name}")
            skin.status("ID", info.get("id", "?"))
            skin.status("Name", info.get("name", "?"))
            meta = info.get("metadata") or {}
            skin.status("Metadata", json_mod.dumps(meta))
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to get collection info: {e}")
        raise SystemExit(1)
