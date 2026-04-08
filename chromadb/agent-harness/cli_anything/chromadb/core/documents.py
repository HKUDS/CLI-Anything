"""Document commands -- add, get, delete, count."""

import json as json_mod
import click

from ..utils.chromadb_backend import ChromaDBBackend


def _resolve_collection_id(backend: ChromaDBBackend, collection_name: str) -> str:
    """Resolve a collection name to its ID."""
    info = backend.get_collection(collection_name)
    return info["id"]


@click.group("document")
@click.pass_context
def document_group(ctx):
    """Manage documents in ChromaDB collections."""
    pass


@document_group.command("add")
@click.option("--collection", required=True, help="Collection name")
@click.option("--id", "doc_ids", multiple=True, required=True, help="Document ID (repeatable)")
@click.option("--document", "documents", multiple=True, required=True, help="Document text (repeatable)")
@click.option("--metadata", "metadatas", multiple=True, default=None, help="Metadata JSON string (repeatable)")
@click.pass_context
def add_documents(ctx, collection, doc_ids, documents, metadatas):
    """Add documents to a collection."""
    backend: ChromaDBBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        collection_id = _resolve_collection_id(backend, collection)
        parsed_meta = None
        if metadatas:
            parsed_meta = [json_mod.loads(m) for m in metadatas]
        result = backend.add_documents(
            collection_id=collection_id,
            ids=list(doc_ids),
            documents=list(documents),
            metadatas=parsed_meta,
        )
        if use_json:
            click.echo(json_mod.dumps(result, indent=2))
        else:
            skin.success(f"Added {len(doc_ids)} document(s) to '{collection}'")
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to add documents: {e}")
        raise SystemExit(1)


@document_group.command("get")
@click.option("--collection", required=True, help="Collection name")
@click.option("--id", "doc_ids", multiple=True, default=None, help="Document ID (repeatable)")
@click.option("--limit", default=None, type=int, help="Max documents to return")
@click.option("--offset", default=None, type=int, help="Offset for pagination")
@click.pass_context
def get_documents(ctx, collection, doc_ids, limit, offset):
    """Get documents from a collection."""
    backend: ChromaDBBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        collection_id = _resolve_collection_id(backend, collection)
        ids_list = list(doc_ids) if doc_ids else None
        result = backend.get_documents(
            collection_id=collection_id,
            ids=ids_list,
            limit=limit,
            offset=offset,
        )
        if use_json:
            click.echo(json_mod.dumps(result, indent=2))
        else:
            ids = result.get("ids", [])
            docs = result.get("documents", [])
            metas = result.get("metadatas", [])
            if not ids:
                skin.info("No documents found.")
                return
            headers = ["ID", "Document (preview)", "Metadata"]
            rows = []
            for i, doc_id in enumerate(ids):
                doc_text = (docs[i][:80] + "...") if docs[i] and len(docs[i]) > 80 else (docs[i] or "")
                meta = json_mod.dumps(metas[i]) if metas and i < len(metas) else "{}"
                rows.append([doc_id, doc_text, meta])
            skin.table(headers, rows)
            skin.info(f"Showing {len(ids)} document(s)")
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to get documents: {e}")
        raise SystemExit(1)


@document_group.command("delete")
@click.option("--collection", required=True, help="Collection name")
@click.option("--id", "doc_ids", multiple=True, required=True, help="Document ID to delete (repeatable)")
@click.pass_context
def delete_documents(ctx, collection, doc_ids):
    """Delete documents from a collection."""
    backend: ChromaDBBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        collection_id = _resolve_collection_id(backend, collection)
        result = backend.delete_documents(collection_id, list(doc_ids))
        if use_json:
            click.echo(json_mod.dumps(result, indent=2))
        else:
            skin.success(f"Deleted {len(doc_ids)} document(s) from '{collection}'")
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to delete documents: {e}")
        raise SystemExit(1)


@document_group.command("count")
@click.option("--collection", required=True, help="Collection name")
@click.pass_context
def count_documents(ctx, collection):
    """Count documents in a collection."""
    backend: ChromaDBBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        collection_id = _resolve_collection_id(backend, collection)
        count = backend.count_documents(collection_id)
        if use_json:
            click.echo(json_mod.dumps({"collection": collection, "count": count}, indent=2))
        else:
            skin.status("Collection", collection)
            skin.status("Documents", str(count))
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Failed to count documents: {e}")
        raise SystemExit(1)
