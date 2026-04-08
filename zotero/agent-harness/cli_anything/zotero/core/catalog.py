from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from cli_anything.zotero.core.discovery import RuntimeContext
from cli_anything.zotero.utils import zotero_http, zotero_sqlite


def _require_sqlite(runtime: RuntimeContext) -> Path:
    sqlite_path = runtime.environment.sqlite_path
    if not sqlite_path.exists():
        raise FileNotFoundError(f"Zotero SQLite database not found: {sqlite_path}")
    return sqlite_path


def resolve_library_id(runtime: RuntimeContext, library_ref: str | int | None) -> int | None:
    if library_ref is None:
        return None
    sqlite_path = _require_sqlite(runtime)
    library = zotero_sqlite.resolve_library(sqlite_path, library_ref)
    if not library:
        raise RuntimeError(f"Library not found: {library_ref}")
    return int(library["libraryID"])


def _default_library(runtime: RuntimeContext, session: dict[str, Any] | None = None) -> int:
    session = session or {}
    current_library_id = resolve_library_id(runtime, session.get("current_library"))
    if current_library_id is not None:
        return current_library_id
    library_id = zotero_sqlite.default_library_id(_require_sqlite(runtime))
    if library_id is None:
        raise RuntimeError("No Zotero libraries found in the local database")
    return library_id


def local_api_scope(runtime: RuntimeContext, library_id: int) -> str:
    library = zotero_sqlite.resolve_library(_require_sqlite(runtime), library_id)
    if not library:
        raise RuntimeError(f"Library not found: {library_id}")
    if library["type"] == "user":
        return "/api/users/0"
    if library["type"] == "group":
        return f"/api/groups/{int(library['libraryID'])}"
    raise RuntimeError(f"Unsupported library type for Zotero Local API: {library['type']}")


def list_libraries(runtime: RuntimeContext) -> list[dict[str, Any]]:
    return zotero_sqlite.fetch_libraries(_require_sqlite(runtime))


def list_collections(runtime: RuntimeContext, session: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return zotero_sqlite.fetch_collections(_require_sqlite(runtime), library_id=_default_library(runtime, session))


def find_collections(runtime: RuntimeContext, query: str, *, limit: int = 20, session: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return zotero_sqlite.find_collections(_require_sqlite(runtime), query, library_id=_default_library(runtime, session), limit=limit)


def collection_tree(runtime: RuntimeContext, session: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return zotero_sqlite.build_collection_tree(list_collections(runtime, session=session))


def get_collection(runtime: RuntimeContext, ref: str | int | None, session: dict[str, Any] | None = None) -> dict[str, Any]:
    session = session or {}
    resolved = ref if ref is not None else session.get("current_collection")
    if resolved is None:
        raise RuntimeError("Collection reference required or set it in session first")
    collection = zotero_sqlite.resolve_collection(
        _require_sqlite(runtime),
        resolved,
        library_id=resolve_library_id(runtime, session.get("current_library")),
    )
    if not collection:
        raise RuntimeError(f"Collection not found: {resolved}")
    return collection


def collection_items(runtime: RuntimeContext, ref: str | int | None, session: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    collection = get_collection(runtime, ref, session=session)
    return zotero_sqlite.fetch_items(_require_sqlite(runtime), library_id=int(collection["libraryID"]), collection_id=int(collection["collectionID"]))


def use_selected_collection(runtime: RuntimeContext) -> dict[str, Any]:
    if not runtime.connector_available:
        raise RuntimeError(f"Zotero connector is not available: {runtime.connector_message}")
    return zotero_http.get_selected_collection(runtime.environment.port)


def list_items(runtime: RuntimeContext, session: dict[str, Any] | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    return zotero_sqlite.fetch_items(_require_sqlite(runtime), library_id=_default_library(runtime, session), limit=limit)


def find_items(
    runtime: RuntimeContext,
    query: str,
    *,
    collection_ref: str | None = None,
    limit: int = 20,
    exact_title: bool = False,
    session: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    sqlite_path = _require_sqlite(runtime)
    collection = None
    if collection_ref:
        collection = get_collection(runtime, collection_ref, session=session)
    library_id = int(collection["libraryID"]) if collection else _default_library(runtime, session)

    if not exact_title and runtime.local_api_available:
        scope = local_api_scope(runtime, library_id)
        path = f"{scope}/collections/{collection['key']}/items/top" if collection else f"{scope}/items/top"
        payload = zotero_http.local_api_get_json(
            runtime.environment.port,
            path,
            params={"format": "json", "q": query, "limit": limit},
        )
        results: list[dict[str, Any]] = []
        for record in payload if isinstance(payload, list) else []:
            key = record.get("key") if isinstance(record, dict) else None
            if not key:
                continue
            resolved = zotero_sqlite.resolve_item(sqlite_path, key, library_id=library_id)
            if resolved:
                results.append(resolved)
        if results:
            return results[:limit]

    collection_id = int(collection["collectionID"]) if collection else None
    return zotero_sqlite.find_items_by_title(
        sqlite_path,
        query,
        library_id=library_id,
        collection_id=collection_id,
        limit=limit,
        exact_title=exact_title,
    )


def get_item(runtime: RuntimeContext, ref: str | int | None, session: dict[str, Any] | None = None) -> dict[str, Any]:
    session = session or {}
    resolved = ref if ref is not None else session.get("current_item")
    if resolved is None:
        raise RuntimeError("Item reference required or set it in session first")
    item = zotero_sqlite.resolve_item(
        _require_sqlite(runtime),
        resolved,
        library_id=resolve_library_id(runtime, session.get("current_library")),
    )
    if not item:
        raise RuntimeError(f"Item not found: {resolved}")
    return item


def item_children(runtime: RuntimeContext, ref: str | int | None, session: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    item = get_item(runtime, ref, session=session)
    return zotero_sqlite.fetch_item_children(_require_sqlite(runtime), item["itemID"])


def item_notes(runtime: RuntimeContext, ref: str | int | None, session: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    item = get_item(runtime, ref, session=session)
    return zotero_sqlite.fetch_item_notes(_require_sqlite(runtime), item["itemID"])


def item_attachments(runtime: RuntimeContext, ref: str | int | None, session: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    item = get_item(runtime, ref, session=session)
    attachments = zotero_sqlite.fetch_item_attachments(_require_sqlite(runtime), item["itemID"])
    for attachment in attachments:
        attachment["resolvedPath"] = zotero_sqlite.resolve_attachment_real_path(attachment, runtime.environment.data_dir)
    return attachments


def item_file(runtime: RuntimeContext, ref: str | int | None, session: dict[str, Any] | None = None) -> dict[str, Any]:
    item = get_item(runtime, ref, session=session)
    target = item
    if item["typeName"] != "attachment":
        attachments = item_attachments(runtime, item["itemID"])
        if not attachments:
            raise RuntimeError(f"No attachment file found for item: {item['key']}")
        target = attachments[0]
    resolved_path = zotero_sqlite.resolve_attachment_real_path(target, runtime.environment.data_dir)
    return {
        "itemID": target["itemID"],
        "key": target["key"],
        "title": target.get("title", ""),
        "contentType": target.get("contentType"),
        "path": target.get("attachmentPath"),
        "resolvedPath": resolved_path,
        "exists": bool(resolved_path and Path(resolved_path).exists()),
    }


def list_searches(runtime: RuntimeContext, session: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return zotero_sqlite.fetch_saved_searches(_require_sqlite(runtime), library_id=_default_library(runtime, session))


def get_search(runtime: RuntimeContext, ref: str | int | None, session: dict[str, Any] | None = None) -> dict[str, Any]:
    if ref is None:
        raise RuntimeError("Search reference required")
    session = session or {}
    search = zotero_sqlite.resolve_saved_search(
        _require_sqlite(runtime),
        ref,
        library_id=resolve_library_id(runtime, session.get("current_library")),
    )
    if not search:
        raise RuntimeError(f"Saved search not found: {ref}")
    return search


def search_items(runtime: RuntimeContext, ref: str | int | None, session: dict[str, Any] | None = None) -> Any:
    if not runtime.local_api_available:
        raise RuntimeError("search items requires the Zotero Local API to be running and enabled")
    search = get_search(runtime, ref, session=session)
    scope = local_api_scope(runtime, int(search["libraryID"]))
    return zotero_http.local_api_get_json(
        runtime.environment.port,
        f"{scope}/searches/{search['key']}/items",
        params={"format": "json"},
    )


def list_tags(runtime: RuntimeContext, session: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return zotero_sqlite.fetch_tags(_require_sqlite(runtime), library_id=_default_library(runtime, session))


def tag_items(runtime: RuntimeContext, tag_ref: str | int, session: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return zotero_sqlite.fetch_tag_items(_require_sqlite(runtime), tag_ref, library_id=_default_library(runtime, session))


def list_styles(runtime: RuntimeContext) -> list[dict[str, Any]]:
    styles_dir = runtime.environment.styles_dir
    if not styles_dir.exists():
        return []
    styles: list[dict[str, Any]] = []
    for path in sorted(styles_dir.glob("*.csl")):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            styles.append({"path": str(path), "id": None, "title": path.stem, "valid": False})
            continue
        style_id = None
        title = None
        for element in root.iter():
            tag = element.tag.split("}", 1)[-1]
            if tag == "id" and style_id is None:
                style_id = (element.text or "").strip() or None
            if tag == "title" and title is None:
                title = (element.text or "").strip() or None
        styles.append({"path": str(path), "id": style_id, "title": title or path.stem, "valid": True})
    return styles
