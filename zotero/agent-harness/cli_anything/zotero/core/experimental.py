from __future__ import annotations

from typing import Any

from cli_anything.zotero.core.discovery import RuntimeContext
from cli_anything.zotero.utils import zotero_sqlite


def _require_offline(runtime: RuntimeContext) -> None:
    if runtime.connector_available:
        raise RuntimeError("Experimental SQLite write commands require Zotero to be closed")


def _session_library_id(session: dict[str, Any] | None = None) -> int | None:
    session = session or {}
    current_library = session.get("current_library")
    if current_library is None:
        return None
    return zotero_sqlite.normalize_library_ref(current_library)


def _require_user_library(runtime: RuntimeContext, library_id: int) -> None:
    library = zotero_sqlite.resolve_library(runtime.environment.sqlite_path, library_id)
    if not library:
        raise RuntimeError(f"Library not found: {library_id}")
    if library["type"] != "user":
        raise RuntimeError("Experimental SQLite write commands currently support only the local user library")


def _user_library_id(runtime: RuntimeContext, library_ref: str | None, session: dict[str, Any] | None = None) -> int:
    session = session or {}
    candidate = library_ref or session.get("current_library")
    if candidate:
        library_id = zotero_sqlite.normalize_library_ref(candidate)
    else:
        library_id = zotero_sqlite.default_library_id(runtime.environment.sqlite_path)
        if library_id is None:
            raise RuntimeError("No Zotero libraries found")

    libraries = zotero_sqlite.fetch_libraries(runtime.environment.sqlite_path)
    library = next((entry for entry in libraries if int(entry["libraryID"]) == int(library_id)), None)
    if not library:
        raise RuntimeError(f"Library not found: {library_id}")
    if library["type"] != "user":
        raise RuntimeError("Experimental SQLite write commands currently support only the local user library")
    return int(library_id)


def create_collection(
    runtime: RuntimeContext,
    name: str,
    *,
    parent_ref: str | None = None,
    library_ref: str | None = None,
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _require_offline(runtime)
    parent = None
    if parent_ref:
        parent = zotero_sqlite.resolve_collection(
            runtime.environment.sqlite_path,
            parent_ref,
            library_id=_session_library_id(session),
        )
        if not parent:
            raise RuntimeError(f"Parent collection not found: {parent_ref}")

    library_id = int(parent["libraryID"]) if parent else _user_library_id(runtime, library_ref, session=session)
    if parent and library_ref is not None and library_id != _user_library_id(runtime, library_ref, session=session):
        raise RuntimeError("Parent collection and explicit library do not match")

    created = zotero_sqlite.create_collection_record(
        runtime.environment.sqlite_path,
        name=name,
        library_id=library_id,
        parent_collection_id=int(parent["collectionID"]) if parent else None,
    )
    created["action"] = "collection_create"
    created["experimental"] = True
    return created


def add_item_to_collection(
    runtime: RuntimeContext,
    item_ref: str,
    collection_ref: str,
    *,
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _require_offline(runtime)
    library_id = _session_library_id(session)
    item = zotero_sqlite.resolve_item(runtime.environment.sqlite_path, item_ref, library_id=library_id)
    if not item:
        raise RuntimeError(f"Item not found: {item_ref}")
    if item.get("parentItemID") is not None:
        raise RuntimeError("Only top-level items can be added directly to collections")
    _require_user_library(runtime, int(item["libraryID"]))

    collection = zotero_sqlite.resolve_collection(runtime.environment.sqlite_path, collection_ref, library_id=library_id)
    if not collection:
        raise RuntimeError(f"Collection not found: {collection_ref}")
    if int(item["libraryID"]) != int(collection["libraryID"]):
        raise RuntimeError("Item and collection must belong to the same library")

    result = zotero_sqlite.add_item_to_collection_record(
        runtime.environment.sqlite_path,
        item_id=int(item["itemID"]),
        collection_id=int(collection["collectionID"]),
    )
    result.update(
        {
            "action": "item_add_to_collection",
            "experimental": True,
            "itemKey": item["key"],
            "collectionKey": collection["key"],
        }
    )
    return result


def move_item_to_collection(
    runtime: RuntimeContext,
    item_ref: str,
    collection_ref: str,
    *,
    from_refs: list[str] | tuple[str, ...] | None = None,
    all_other_collections: bool = False,
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _require_offline(runtime)
    if not from_refs and not all_other_collections:
        raise RuntimeError("Provide `from_refs` or set `all_other_collections=True`")

    library_id = _session_library_id(session)
    item = zotero_sqlite.resolve_item(runtime.environment.sqlite_path, item_ref, library_id=library_id)
    if not item:
        raise RuntimeError(f"Item not found: {item_ref}")
    if item.get("parentItemID") is not None:
        raise RuntimeError("Only top-level items can be moved directly between collections")
    _require_user_library(runtime, int(item["libraryID"]))

    target = zotero_sqlite.resolve_collection(runtime.environment.sqlite_path, collection_ref, library_id=library_id)
    if not target:
        raise RuntimeError(f"Target collection not found: {collection_ref}")
    if int(item["libraryID"]) != int(target["libraryID"]):
        raise RuntimeError("Item and target collection must belong to the same library")

    current_memberships = zotero_sqlite.fetch_item_collections(runtime.environment.sqlite_path, item["itemID"])
    current_by_id = {int(collection["collectionID"]): collection for collection in current_memberships}
    if all_other_collections:
        source_collection_ids = [collection_id for collection_id in current_by_id if collection_id != int(target["collectionID"])]
    else:
        source_collection_ids = []
        for ref in from_refs or []:
            collection = zotero_sqlite.resolve_collection(runtime.environment.sqlite_path, ref, library_id=library_id)
            if not collection:
                raise RuntimeError(f"Source collection not found: {ref}")
            source_collection_ids.append(int(collection["collectionID"]))

    result = zotero_sqlite.move_item_between_collections_record(
        runtime.environment.sqlite_path,
        item_id=int(item["itemID"]),
        target_collection_id=int(target["collectionID"]),
        source_collection_ids=source_collection_ids,
    )
    result.update(
        {
            "action": "item_move_to_collection",
            "experimental": True,
            "itemKey": item["key"],
            "targetCollectionKey": target["key"],
            "sourceCollectionIDs": source_collection_ids,
        }
    )
    return result
