"""Query commands -- semantic search."""

import json as json_mod
import click

from ..utils.chromadb_backend import ChromaDBBackend


def _resolve_collection_id(backend: ChromaDBBackend, collection_name: str) -> str:
    """Resolve a collection name to its ID."""
    info = backend.get_collection(collection_name)
    return info["id"]


@click.group("query")
@click.pass_context
def query_group(ctx):
    """Semantic search against ChromaDB collections."""
    pass


@query_group.command("search")
@click.option("--collection", required=True, help="Collection name")
@click.option("--text", required=True, help="Search query text")
@click.option("--n-results", default=5, type=int, help="Number of results (default: 5)")
@click.pass_context
def search(ctx, collection, text, n_results):
    """Perform semantic search on a collection."""
    backend: ChromaDBBackend = ctx.obj["backend"]
    use_json = ctx.obj.get("json", False)
    skin = ctx.obj.get("skin")
    try:
        collection_id = _resolve_collection_id(backend, collection)
        result = backend.query(
            collection_id=collection_id,
            query_texts=[text],
            n_results=n_results,
        )
        if use_json:
            click.echo(json_mod.dumps(result, indent=2))
        else:
            skin.section(f"Search: \"{text}\" in {collection}")
            ids_list = result.get("ids", [[]])[0]
            docs_list = result.get("documents", [[]])[0]
            dists_list = result.get("distances", [[]])[0]
            metas_list = result.get("metadatas", [[]])[0]

            if not ids_list:
                skin.info("No results found.")
                return

            for i, doc_id in enumerate(ids_list):
                distance = dists_list[i] if i < len(dists_list) else "?"
                doc = docs_list[i] if i < len(docs_list) else ""
                meta = metas_list[i] if i < len(metas_list) else {}

                skin.info(f"[{i+1}] {doc_id}  (distance: {distance})")
                if meta:
                    skin.hint(f"    metadata: {json_mod.dumps(meta)}")
                preview = (doc[:120] + "...") if doc and len(doc) > 120 else (doc or "")
                if preview:
                    skin.hint(f"    {preview}")
                print()

            skin.info(f"{len(ids_list)} result(s) returned")
    except Exception as e:
        if use_json:
            click.echo(json_mod.dumps({"error": str(e)}, indent=2))
        else:
            skin.error(f"Query failed: {e}")
        raise SystemExit(1)
