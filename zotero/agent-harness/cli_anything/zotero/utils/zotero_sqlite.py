from __future__ import annotations

import html
import os
import random
import re
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any, Optional
from urllib.parse import unquote, urlparse


KEY_ALPHABET = "23456789ABCDEFGHIJKLMNPQRSTUVWXYZ"
NOTE_PREVIEW_LENGTH = 160
_TAG_RE = re.compile(r"<[^>]+>")


class AmbiguousReferenceError(RuntimeError):
    """Raised when a bare Zotero key matches records in multiple libraries."""


def connect_readonly(sqlite_path: Path | str) -> sqlite3.Connection:
    path = Path(sqlite_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Zotero database not found: {path}")
    uri = f"file:{path.as_posix()}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True, timeout=1.0)
    connection.row_factory = sqlite3.Row
    return connection


def connect_writable(sqlite_path: Path | str) -> sqlite3.Connection:
    path = Path(sqlite_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Zotero database not found: {path}")
    connection = sqlite3.connect(path, timeout=30.0)
    connection.row_factory = sqlite3.Row
    return connection


def _as_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _is_numeric_ref(value: Any) -> bool:
    try:
        int(str(value))
        return True
    except (TypeError, ValueError):
        return False


def normalize_library_ref(library_ref: str | int) -> int:
    text = str(library_ref).strip()
    if not text:
        raise RuntimeError("Library reference must not be empty")
    upper = text.upper()
    if upper.startswith("L") and upper[1:].isdigit():
        return int(upper[1:])
    if text.isdigit():
        return int(text)
    raise RuntimeError(f"Unsupported library reference: {library_ref}")


def _timestamp_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def generate_object_key(length: int = 8) -> str:
    chooser = random.SystemRandom()
    return "".join(chooser.choice(KEY_ALPHABET) for _ in range(length))


def backup_database(sqlite_path: Path | str) -> Path:
    source = Path(sqlite_path).resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    backup = source.with_name(f"{source.stem}.backup-{timestamp}{source.suffix}")
    shutil.copy2(source, backup)
    return backup


def note_html_to_text(note_html: str | None) -> str:
    if not note_html:
        return ""
    text = re.sub(r"(?i)<br\s*/?>", "\n", note_html)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"(?i)</div\s*>", "\n", text)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def note_preview(note_html: str | None, limit: int = NOTE_PREVIEW_LENGTH) -> str:
    text = note_html_to_text(note_html)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def fetch_libraries(sqlite_path: Path | str) -> list[dict[str, Any]]:
    with closing(connect_readonly(sqlite_path)) as conn:
        rows = conn.execute(
            """
            SELECT libraryID, type, editable, filesEditable, version, storageVersion, lastSync, archived
            FROM libraries
            ORDER BY libraryID
            """
        ).fetchall()
    return _as_dicts(rows)


def resolve_library(sqlite_path: Path | str, ref: str | int) -> Optional[dict[str, Any]]:
    library_id = normalize_library_ref(ref)
    with closing(connect_readonly(sqlite_path)) as conn:
        row = conn.execute(
            """
            SELECT libraryID, type, editable, filesEditable, version, storageVersion, lastSync, archived
            FROM libraries
            WHERE libraryID = ?
            """,
            (library_id,),
        ).fetchone()
    return dict(row) if row else None


def default_library_id(sqlite_path: Path | str) -> Optional[int]:
    libraries = fetch_libraries(sqlite_path)
    if not libraries:
        return None
    for library in libraries:
        if library["type"] == "user":
            return int(library["libraryID"])
    return int(libraries[0]["libraryID"])


def fetch_collections(sqlite_path: Path | str, library_id: int | None = None) -> list[dict[str, Any]]:
    with closing(connect_readonly(sqlite_path)) as conn:
        rows = conn.execute(
            """
            SELECT
                c.collectionID,
                c.key,
                c.collectionName,
                c.parentCollectionID,
                c.libraryID,
                c.version,
                COUNT(ci.itemID) AS itemCount
            FROM collections c
            LEFT JOIN collectionItems ci ON ci.collectionID = c.collectionID
            WHERE (? IS NULL OR c.libraryID = ?)
            GROUP BY c.collectionID, c.key, c.collectionName, c.parentCollectionID, c.libraryID, c.version
            ORDER BY c.collectionName COLLATE NOCASE
            """,
            (library_id, library_id),
        ).fetchall()
    return _as_dicts(rows)


def find_collections(sqlite_path: Path | str, query: str, *, library_id: int | None = None, limit: int = 20) -> list[dict[str, Any]]:
    query = query.strip()
    if not query:
        return []
    needle = query.lower()
    like_query = f"%{needle}%"
    prefix_query = f"{needle}%"
    with closing(connect_readonly(sqlite_path)) as conn:
        rows = conn.execute(
            """
            SELECT
                c.collectionID,
                c.key,
                c.collectionName,
                c.parentCollectionID,
                c.libraryID,
                c.version,
                COUNT(ci.itemID) AS itemCount
            FROM collections c
            LEFT JOIN collectionItems ci ON ci.collectionID = c.collectionID
            WHERE (? IS NULL OR c.libraryID = ?) AND LOWER(c.collectionName) LIKE ?
            GROUP BY c.collectionID, c.key, c.collectionName, c.parentCollectionID, c.libraryID, c.version
            ORDER BY
                CASE
                    WHEN LOWER(c.collectionName) = ? THEN 0
                    WHEN LOWER(c.collectionName) LIKE ? THEN 1
                    ELSE 2
                END,
                INSTR(LOWER(c.collectionName), ?),
                c.collectionName COLLATE NOCASE,
                c.collectionID
            LIMIT ?
            """,
            (library_id, library_id, like_query, needle, prefix_query, needle, int(limit)),
        ).fetchall()
    return _as_dicts(rows)


def build_collection_tree(collections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[int, dict[str, Any]] = {}
    roots: list[dict[str, Any]] = []
    for collection in collections:
        node = {**collection, "children": []}
        by_id[int(collection["collectionID"])] = node
    for collection in collections:
        node = by_id[int(collection["collectionID"])]
        parent_id = collection["parentCollectionID"]
        if parent_id is None:
            roots.append(node)
            continue
        parent = by_id.get(int(parent_id))
        if parent is None:
            roots.append(node)
        else:
            parent["children"].append(node)
    return roots


def _ambiguous_reference(ref: str | int, kind: str, rows: list[sqlite3.Row]) -> None:
    libraries = sorted({int(row["libraryID"]) for row in rows if "libraryID" in row.keys()})
    library_text = ", ".join(f"L{library_id}" for library_id in libraries) or "multiple libraries"
    raise AmbiguousReferenceError(
        f"Ambiguous {kind} reference: {ref}. Matches found in {library_text}. "
        "Set the library with `session use-library <id>` and retry."
    )


def resolve_collection(sqlite_path: Path | str, ref: str | int, *, library_id: int | None = None) -> Optional[dict[str, Any]]:
    with closing(connect_readonly(sqlite_path)) as conn:
        if _is_numeric_ref(ref):
            row = conn.execute(
                "SELECT collectionID, key, collectionName, parentCollectionID, libraryID, version FROM collections WHERE collectionID = ?",
                (int(ref),),
            ).fetchone()
        else:
            params: list[Any] = [str(ref)]
            sql = "SELECT collectionID, key, collectionName, parentCollectionID, libraryID, version FROM collections WHERE key = ?"
            if library_id is not None:
                sql += " AND libraryID = ?"
                params.append(int(library_id))
            sql += " ORDER BY libraryID, collectionID"
            rows = conn.execute(sql, params).fetchall()
            if not rows:
                return None
            if len(rows) > 1 and library_id is None:
                _ambiguous_reference(ref, "collection", rows)
            row = rows[0]
    return dict(row) if row else None


def fetch_item_collections(sqlite_path: Path | str, ref: str | int) -> list[dict[str, Any]]:
    item = resolve_item(sqlite_path, ref)
    if not item:
        return []
    with closing(connect_readonly(sqlite_path)) as conn:
        rows = conn.execute(
            """
            SELECT c.collectionID, c.key, c.collectionName, c.parentCollectionID, c.libraryID
            FROM collectionItems ci
            JOIN collections c ON c.collectionID = ci.collectionID
            WHERE ci.itemID = ?
            ORDER BY c.collectionName COLLATE NOCASE, c.collectionID
            """,
            (int(item["itemID"]),),
        ).fetchall()
    return _as_dicts(rows)


def _fetch_item_fields(conn: sqlite3.Connection, item_id: int) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT f.fieldName, v.value
        FROM itemData d
        JOIN fields f ON f.fieldID = d.fieldID
        JOIN itemDataValues v ON v.valueID = d.valueID
        WHERE d.itemID = ?
        ORDER BY f.fieldName COLLATE NOCASE
        """,
        (item_id,),
    ).fetchall()
    return {row["fieldName"]: row["value"] for row in rows}


def _fetch_item_creators(conn: sqlite3.Connection, item_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT c.creatorID, c.firstName, c.lastName, c.fieldMode, ic.creatorTypeID, ic.orderIndex
        FROM itemCreators ic
        JOIN creators c ON c.creatorID = ic.creatorID
        WHERE ic.itemID = ?
        ORDER BY ic.orderIndex
        """,
        (item_id,),
    ).fetchall()
    return _as_dicts(rows)


def _fetch_item_tags(conn: sqlite3.Connection, item_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT t.tagID, t.name, it.type
        FROM itemTags it
        JOIN tags t ON t.tagID = it.tagID
        WHERE it.itemID = ?
        ORDER BY t.name COLLATE NOCASE
        """,
        (item_id,),
    ).fetchall()
    return _as_dicts(rows)


def _base_item_select() -> str:
    return """
        SELECT
            i.itemID,
            i.key,
            i.libraryID,
            i.itemTypeID,
            it.typeName,
            i.dateAdded,
            i.dateModified,
            i.version,
            COALESCE(
                (
                    SELECT v.value
                    FROM itemData d
                    JOIN fields f ON f.fieldID = d.fieldID
                    JOIN itemDataValues v ON v.valueID = d.valueID
                    WHERE d.itemID = i.itemID AND f.fieldName = 'title'
                    LIMIT 1
                ),
                n.title,
                ''
            ) AS title,
            n.parentItemID AS noteParentItemID,
            n.note AS noteContent,
            a.parentItemID AS attachmentParentItemID,
            an.parentItemID AS annotationParentItemID,
            an.text AS annotationText,
            an.comment AS annotationComment,
            a.linkMode,
            a.contentType,
            a.path AS attachmentPath
        FROM items i
        JOIN itemTypes it ON it.itemTypeID = i.itemTypeID
        LEFT JOIN itemNotes n ON n.itemID = i.itemID
        LEFT JOIN itemAttachments a ON a.itemID = i.itemID
        LEFT JOIN itemAnnotations an ON an.itemID = i.itemID
    """


def _normalize_item(conn: sqlite3.Connection, row: sqlite3.Row, include_related: bool = False) -> dict[str, Any]:
    item = dict(row)
    item["fields"] = _fetch_item_fields(conn, int(row["itemID"])) if include_related else {}
    item["creators"] = _fetch_item_creators(conn, int(row["itemID"])) if include_related else []
    item["tags"] = _fetch_item_tags(conn, int(row["itemID"])) if include_related else []
    item["isAttachment"] = row["typeName"] == "attachment"
    item["isNote"] = row["typeName"] == "note"
    item["isAnnotation"] = row["typeName"] == "annotation"
    item["parentItemID"] = row["attachmentParentItemID"] or row["noteParentItemID"] or row["annotationParentItemID"]
    item["noteText"] = note_html_to_text(row["noteContent"])
    item["notePreview"] = note_preview(row["noteContent"])
    return item


def fetch_items(
    sqlite_path: Path | str,
    *,
    library_id: int | None = None,
    collection_id: int | None = None,
    parent_item_id: int | None = None,
    tag: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    where = ["1=1"]
    params: list[Any] = []
    if library_id is not None:
        where.append("i.libraryID = ?")
        params.append(library_id)
    if collection_id is not None:
        where.append("EXISTS (SELECT 1 FROM collectionItems ci WHERE ci.itemID = i.itemID AND ci.collectionID = ?)")
        params.append(collection_id)
    if parent_item_id is None:
        where.append("COALESCE(a.parentItemID, n.parentItemID, an.parentItemID) IS NULL")
    else:
        where.append("COALESCE(a.parentItemID, n.parentItemID, an.parentItemID) = ?")
        params.append(parent_item_id)
    if tag is not None:
        where.append(
            """
            EXISTS (
                SELECT 1
                FROM itemTags it2
                JOIN tags t2 ON t2.tagID = it2.tagID
                WHERE it2.itemID = i.itemID AND (t2.name = ? OR t2.tagID = ?)
            )
            """
        )
        params.extend([tag, int(tag) if _is_numeric_ref(tag) else -1])
    sql = _base_item_select() + f"\nWHERE {' AND '.join(where)}\nORDER BY i.dateModified DESC, i.itemID DESC"
    if limit is not None:
        sql += f"\nLIMIT {int(limit)}"
    with closing(connect_readonly(sqlite_path)) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [_normalize_item(conn, row, include_related=False) for row in rows]


def find_items_by_title(
    sqlite_path: Path | str,
    query: str,
    *,
    library_id: int | None = None,
    collection_id: int | None = None,
    limit: int = 20,
    exact_title: bool = False,
) -> list[dict[str, Any]]:
    query = query.strip()
    if not query:
        return []
    title_expr = """
        LOWER(
            COALESCE(
                (
                    SELECT v.value
                    FROM itemData d
                    JOIN fields f ON f.fieldID = d.fieldID
                    JOIN itemDataValues v ON v.valueID = d.valueID
                    WHERE d.itemID = i.itemID AND f.fieldName = 'title'
                    LIMIT 1
                ),
                n.title,
                ''
            )
        )
    """
    where = ["1=1"]
    params: list[Any] = []
    if library_id is not None:
        where.append("i.libraryID = ?")
        params.append(library_id)
    if collection_id is not None:
        where.append("EXISTS (SELECT 1 FROM collectionItems ci WHERE ci.itemID = i.itemID AND ci.collectionID = ?)")
        params.append(collection_id)
    where.append("COALESCE(a.parentItemID, n.parentItemID, an.parentItemID) IS NULL")
    if exact_title:
        where.append(f"{title_expr} = ?")
        params.append(query.lower())
    else:
        where.append(f"{title_expr} LIKE ?")
        params.append(f"%{query.lower()}%")
    sql = (
        "SELECT * FROM ("
        + _base_item_select()
        + f"\nWHERE {' AND '.join(where)}\n) AS base\n"
        + """
        ORDER BY
            CASE
                WHEN LOWER(title) = ? THEN 0
                WHEN LOWER(title) LIKE ? THEN 1
                ELSE 2
            END,
            INSTR(LOWER(title), ?),
            dateModified DESC,
            itemID DESC
        LIMIT ?
        """
    )
    params.extend([query.lower(), f"{query.lower()}%", query.lower(), int(limit)])
    with closing(connect_readonly(sqlite_path)) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [_normalize_item(conn, row, include_related=False) for row in rows]


def resolve_item(sqlite_path: Path | str, ref: str | int, *, library_id: int | None = None) -> Optional[dict[str, Any]]:
    params: list[Any]
    if _is_numeric_ref(ref):
        where = "i.itemID = ?"
        params = [int(ref)]
    else:
        where = "i.key = ?"
        params = [str(ref)]
        if library_id is not None:
            where += " AND i.libraryID = ?"
            params.append(int(library_id))
    with closing(connect_readonly(sqlite_path)) as conn:
        rows = conn.execute(_base_item_select() + f"\nWHERE {where}\nORDER BY i.libraryID, i.itemID", params).fetchall()
        if not rows:
            return None
        if len(rows) > 1 and library_id is None and not _is_numeric_ref(ref):
            _ambiguous_reference(ref, "item", rows)
        return _normalize_item(conn, rows[0], include_related=True)


def fetch_item_children(sqlite_path: Path | str, ref: str | int) -> list[dict[str, Any]]:
    item = resolve_item(sqlite_path, ref)
    if not item:
        return []
    return fetch_items(sqlite_path, parent_item_id=int(item["itemID"]))


def fetch_item_notes(sqlite_path: Path | str, ref: str | int) -> list[dict[str, Any]]:
    children = fetch_item_children(sqlite_path, ref)
    return [child for child in children if child["typeName"] == "note"]


def fetch_item_attachments(sqlite_path: Path | str, ref: str | int) -> list[dict[str, Any]]:
    children = fetch_item_children(sqlite_path, ref)
    return [child for child in children if child["typeName"] == "attachment"]


def resolve_attachment_real_path(item: dict[str, Any], data_dir: Path | str) -> Optional[str]:
    raw_path = item.get("attachmentPath")
    if not raw_path:
        return None
    raw_path = str(raw_path)
    data_dir = Path(data_dir)
    if raw_path.startswith("storage:"):
        filename = raw_path.split(":", 1)[1]
        return str((data_dir / "storage" / item["key"] / filename).resolve())
    if raw_path.startswith("file://"):
        parsed = urlparse(raw_path)
        decoded_path = unquote(parsed.path)
        if parsed.netloc and parsed.netloc.lower() != "localhost":
            normalized_unc_path = decoded_path.replace("/", "\\")
            unc_path = f"\\\\{parsed.netloc}{normalized_unc_path}"
            return str(PureWindowsPath(unc_path))
        if re.match(r"^/[A-Za-z]:", decoded_path):
            return str(PureWindowsPath(decoded_path.lstrip("/")))
        return decoded_path if os.name != "nt" else str(PureWindowsPath(decoded_path))
    path = Path(raw_path)
    if path.is_absolute():
        return str(path)
    return str((data_dir / raw_path).resolve())


def fetch_saved_searches(sqlite_path: Path | str, library_id: int | None = None) -> list[dict[str, Any]]:
    with closing(connect_readonly(sqlite_path)) as conn:
        rows = conn.execute(
            """
            SELECT savedSearchID, savedSearchName, clientDateModified, libraryID, key, version
            FROM savedSearches
            WHERE (? IS NULL OR libraryID = ?)
            ORDER BY savedSearchName COLLATE NOCASE
            """,
            (library_id, library_id),
        ).fetchall()
        searches = _as_dicts(rows)
        for search in searches:
            condition_rows = conn.execute(
                """
                SELECT searchConditionID, condition, operator, value, required
                FROM savedSearchConditions
                WHERE savedSearchID = ?
                ORDER BY searchConditionID
                """,
                (search["savedSearchID"],),
            ).fetchall()
            search["conditions"] = _as_dicts(condition_rows)
    return searches


def resolve_saved_search(sqlite_path: Path | str, ref: str | int, *, library_id: int | None = None) -> Optional[dict[str, Any]]:
    searches = fetch_saved_searches(sqlite_path, library_id=library_id)
    if _is_numeric_ref(ref):
        for search in searches:
            if str(search["savedSearchID"]) == str(ref):
                return search
        return None

    matches = [search for search in searches if search["key"] == str(ref)]
    if not matches:
        return None
    if len(matches) > 1 and library_id is None:
        libraries = sorted({int(search["libraryID"]) for search in matches})
        library_text = ", ".join(f"L{library_id_value}" for library_id_value in libraries)
        raise AmbiguousReferenceError(
            f"Ambiguous saved search reference: {ref}. Matches found in {library_text}. "
            "Set the library with `session use-library <id>` and retry."
        )
    return matches[0]


def fetch_tags(sqlite_path: Path | str, library_id: int | None = None) -> list[dict[str, Any]]:
    with closing(connect_readonly(sqlite_path)) as conn:
        rows = conn.execute(
            """
            SELECT t.tagID, t.name, COUNT(it.itemID) AS itemCount
            FROM tags t
            JOIN itemTags it ON it.tagID = t.tagID
            JOIN items i ON i.itemID = it.itemID
            WHERE (? IS NULL OR i.libraryID = ?)
            GROUP BY t.tagID, t.name
            ORDER BY t.name COLLATE NOCASE
            """,
            (library_id, library_id),
        ).fetchall()
    return _as_dicts(rows)


def fetch_tag_items(sqlite_path: Path | str, tag_ref: str | int, library_id: int | None = None) -> list[dict[str, Any]]:
    tag_name: str | None = None
    with closing(connect_readonly(sqlite_path)) as conn:
        if _is_numeric_ref(tag_ref):
            row = conn.execute("SELECT name FROM tags WHERE tagID = ?", (int(tag_ref),)).fetchone()
        else:
            row = conn.execute("SELECT name FROM tags WHERE name = ?", (str(tag_ref),)).fetchone()
        if row:
            tag_name = row["name"]
    if tag_name is None:
        return []
    return fetch_items(sqlite_path, library_id=library_id, tag=tag_name)


def create_collection_record(
    sqlite_path: Path | str,
    *,
    name: str,
    library_id: int,
    parent_collection_id: int | None = None,
) -> dict[str, Any]:
    if not name.strip():
        raise RuntimeError("Collection name must not be empty")
    backup_path = backup_database(sqlite_path)
    timestamp = _timestamp_text()
    with closing(connect_writable(sqlite_path)) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                """
                INSERT INTO collections (
                    collectionName,
                    parentCollectionID,
                    clientDateModified,
                    libraryID,
                    key,
                    version,
                    synced
                )
                VALUES (?, ?, ?, ?, ?, 0, 0)
                """,
                (name.strip(), parent_collection_id, timestamp, int(library_id), generate_object_key()),
            )
            collection_id = int(cursor.lastrowid)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    created = resolve_collection(sqlite_path, collection_id)
    assert created is not None
    created["backupPath"] = str(backup_path)
    return created


def add_item_to_collection_record(
    sqlite_path: Path | str,
    *,
    item_id: int,
    collection_id: int,
) -> dict[str, Any]:
    backup_path = backup_database(sqlite_path)
    with closing(connect_writable(sqlite_path)) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT 1 FROM collectionItems WHERE collectionID = ? AND itemID = ?",
                (int(collection_id), int(item_id)),
            ).fetchone()
            created = False
            order_index = None
            if not existing:
                row = conn.execute(
                    "SELECT COALESCE(MAX(orderIndex), -1) + 1 AS nextIndex FROM collectionItems WHERE collectionID = ?",
                    (int(collection_id),),
                ).fetchone()
                order_index = int(row["nextIndex"]) if row else 0
                conn.execute(
                    "INSERT INTO collectionItems (collectionID, itemID, orderIndex) VALUES (?, ?, ?)",
                    (int(collection_id), int(item_id), order_index),
                )
                created = True
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {
        "backupPath": str(backup_path),
        "created": created,
        "collectionID": int(collection_id),
        "itemID": int(item_id),
        "orderIndex": order_index,
    }


def move_item_between_collections_record(
    sqlite_path: Path | str,
    *,
    item_id: int,
    target_collection_id: int,
    source_collection_ids: list[int],
) -> dict[str, Any]:
    backup_path = backup_database(sqlite_path)
    with closing(connect_writable(sqlite_path)) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT 1 FROM collectionItems WHERE collectionID = ? AND itemID = ?",
                (int(target_collection_id), int(item_id)),
            ).fetchone()
            added_to_target = False
            if not existing:
                row = conn.execute(
                    "SELECT COALESCE(MAX(orderIndex), -1) + 1 AS nextIndex FROM collectionItems WHERE collectionID = ?",
                    (int(target_collection_id),),
                ).fetchone()
                next_index = int(row["nextIndex"]) if row else 0
                conn.execute(
                    "INSERT INTO collectionItems (collectionID, itemID, orderIndex) VALUES (?, ?, ?)",
                    (int(target_collection_id), int(item_id), next_index),
                )
                added_to_target = True

            removed = 0
            for source_collection_id in source_collection_ids:
                if int(source_collection_id) == int(target_collection_id):
                    continue
                cursor = conn.execute(
                    "DELETE FROM collectionItems WHERE collectionID = ? AND itemID = ?",
                    (int(source_collection_id), int(item_id)),
                )
                removed += int(cursor.rowcount)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {
        "backupPath": str(backup_path),
        "itemID": int(item_id),
        "targetCollectionID": int(target_collection_id),
        "removedCount": removed,
        "addedToTarget": added_to_target,
    }
