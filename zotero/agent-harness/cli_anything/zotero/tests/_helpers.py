from __future__ import annotations

import json
import re
import sqlite3
import threading
from contextlib import closing, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


def sample_pdf_bytes(label: str = "sample") -> bytes:
    body = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Count 1 /Kids [3 0 R] >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 32 120 Td ({label}) Tj ET
endstream
endobj
trailer
<< /Root 1 0 R >>
%%EOF
"""
    return body.encode("utf-8")


def create_sample_environment(base: Path) -> dict[str, Path]:
    profile_root = base / "AppData" / "Roaming" / "Zotero" / "Zotero"
    profile_dir = profile_root / "Profiles" / "test.default"
    data_dir = base / "ZoteroData"
    install_dir = base / "Program Files" / "Zotero"
    storage_dir = data_dir / "storage" / "ATTACHKEY"
    styles_dir = data_dir / "styles"
    translators_dir = data_dir / "translators"

    profile_dir.mkdir(parents=True, exist_ok=True)
    storage_dir.mkdir(parents=True, exist_ok=True)
    styles_dir.mkdir(parents=True, exist_ok=True)
    translators_dir.mkdir(parents=True, exist_ok=True)
    install_dir.mkdir(parents=True, exist_ok=True)

    profiles_ini = """[Profile0]
Name=default
IsRelative=1
Path=Profiles/test.default
Default=1

[General]
StartWithLastProfile=1
Version=2
"""
    (profile_root / "profiles.ini").write_text(profiles_ini, encoding="utf-8")

    data_dir_pref = str(data_dir).replace("\\", "\\\\")
    prefs_js = (
        'user_pref("extensions.zotero.useDataDir", true);\n'
        f'user_pref("extensions.zotero.dataDir", "{data_dir_pref}");\n'
        'user_pref("extensions.zotero.httpServer.port", 23119);\n'
        'user_pref("extensions.zotero.httpServer.localAPI.enabled", false);\n'
    )
    (profile_dir / "prefs.js").write_text(prefs_js, encoding="utf-8")

    application_ini = """[App]
Vendor=Zotero
Name=Zotero
Version=7.0.32
BuildID=20260114201345
"""
    (install_dir / "app").mkdir(exist_ok=True)
    (install_dir / "app" / "application.ini").write_text(application_ini, encoding="utf-8")
    (install_dir / "zotero.exe").write_text("", encoding="utf-8")

    sqlite_path = data_dir / "zotero.sqlite"
    conn = sqlite3.connect(sqlite_path)
    try:
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE libraries (libraryID INTEGER PRIMARY KEY, type TEXT, editable INTEGER, filesEditable INTEGER, version INTEGER, storageVersion INTEGER, lastSync INTEGER, archived INTEGER);
            CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT, templateItemTypeID INTEGER, display INTEGER);
            CREATE TABLE items (itemID INTEGER PRIMARY KEY, itemTypeID INTEGER, dateAdded TEXT, dateModified TEXT, clientDateModified TEXT, libraryID INTEGER, key TEXT, version INTEGER, synced INTEGER);
            CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT, fieldFormatID INTEGER);
            CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
            CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER);
            CREATE TABLE creators (creatorID INTEGER PRIMARY KEY, firstName TEXT, lastName TEXT, fieldMode INTEGER);
            CREATE TABLE itemCreators (itemID INTEGER, creatorID INTEGER, creatorTypeID INTEGER, orderIndex INTEGER);
            CREATE TABLE tags (tagID INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE itemTags (itemID INTEGER, tagID INTEGER, type INTEGER);
            CREATE TABLE collections (collectionID INTEGER PRIMARY KEY, collectionName TEXT, parentCollectionID INTEGER, clientDateModified TEXT, libraryID INTEGER, key TEXT, version INTEGER, synced INTEGER);
            CREATE TABLE collectionItems (collectionID INTEGER, itemID INTEGER, orderIndex INTEGER);
            CREATE TABLE itemNotes (itemID INTEGER PRIMARY KEY, parentItemID INTEGER, note TEXT, title TEXT);
            CREATE TABLE itemAttachments (itemID INTEGER PRIMARY KEY, parentItemID INTEGER, linkMode INTEGER, contentType TEXT, charsetID INTEGER, path TEXT, syncState INTEGER, storageModTime INTEGER, storageHash TEXT, lastProcessedModificationTime INTEGER);
            CREATE TABLE itemAnnotations (itemID INTEGER PRIMARY KEY, parentItemID INTEGER, type INTEGER, authorName TEXT, text TEXT, comment TEXT, color TEXT, pageLabel TEXT, sortIndex TEXT, position TEXT, isExternal INTEGER);
            CREATE TABLE savedSearches (savedSearchID INTEGER PRIMARY KEY, savedSearchName TEXT, clientDateModified TEXT, libraryID INTEGER, key TEXT, version INTEGER, synced INTEGER);
            CREATE TABLE savedSearchConditions (savedSearchID INTEGER, searchConditionID INTEGER, condition TEXT, operator TEXT, value TEXT, required INTEGER);
            CREATE UNIQUE INDEX items_library_key ON items(libraryID, key);
            CREATE UNIQUE INDEX collections_library_key ON collections(libraryID, key);
            CREATE UNIQUE INDEX saved_searches_library_key ON savedSearches(libraryID, key);
            """
        )
        cur.executemany(
            "INSERT INTO libraries VALUES (?, ?, 1, 1, 1, 1, 0, 0)",
            [(1, "user"), (2, "group")],
        )
        cur.executemany(
            "INSERT INTO itemTypes VALUES (?, ?, NULL, 1)",
            [(1, "journalArticle"), (2, "attachment"), (3, "note")],
        )
        cur.executemany(
            "INSERT INTO items VALUES (?, ?, '2026-01-01', '2026-01-02', '2026-01-02', ?, ?, 1, 1)",
            [
                (1, 1, 1, "REG12345"),
                (2, 2, 1, "ATTACHKEY"),
                (3, 3, 1, "NOTEKEY"),
                (4, 1, 1, "REG67890"),
                (5, 1, 2, "GROUPKEY"),
                (6, 1, 1, "DUPITEM1"),
                (7, 1, 2, "DUPITEM1"),
                (8, 2, 1, "LINKATT1"),
            ],
        )
        cur.executemany("INSERT INTO fields VALUES (?, ?, 0)", [(1, "title"), (2, "DOI"), (3, "url")])
        cur.executemany(
            "INSERT INTO itemDataValues VALUES (?, ?)",
            [
                (1, "Sample Title"),
                (2, "Second Item"),
                (3, "10.1000/sample"),
                (4, "https://example.com/paper"),
                (5, "Group Title"),
                (6, "User Duplicate Title"),
                (7, "Group Duplicate Title"),
            ],
        )
        cur.executemany(
            "INSERT INTO itemData VALUES (?, ?, ?)",
            [(1, 1, 1), (4, 1, 2), (1, 2, 3), (1, 3, 4), (5, 1, 5), (6, 1, 6), (7, 1, 7)],
        )
        cur.executemany(
            "INSERT INTO creators VALUES (?, ?, ?, 0)",
            [(1, "Ada", "Lovelace"), (2, "Grace", "Hopper")],
        )
        cur.executemany("INSERT INTO itemCreators VALUES (?, ?, 1, 0)", [(1, 1), (5, 2)])
        cur.executemany("INSERT INTO tags VALUES (?, ?)", [(1, "sample-tag"), (2, "group-tag")])
        cur.executemany("INSERT INTO itemTags VALUES (?, ?, 0)", [(1, 1), (4, 1), (5, 2)])
        cur.executemany(
            "INSERT INTO collections VALUES (?, ?, ?, '2026-01-02', ?, ?, 1, 1)",
            [
                (1, "Sample Collection", None, 1, "COLLAAAA"),
                (2, "Archive Collection", None, 1, "COLLBBBB"),
                (3, "Nested Collection", 1, 1, "COLLCCCC"),
                (4, "User Duplicate Collection", None, 1, "DUPCOLL1"),
                (10, "Group Collection", None, 2, "GCOLLAAA"),
                (11, "Group Duplicate Collection", None, 2, "DUPCOLL1"),
            ],
        )
        cur.executemany(
            "INSERT INTO collectionItems VALUES (?, ?, ?)",
            [(1, 1, 0), (1, 4, 1), (2, 4, 0), (4, 6, 0), (10, 5, 0), (11, 7, 0)],
        )
        cur.execute("INSERT INTO itemNotes VALUES (3, 1, '<div>Example note</div>', 'Example note')")
        cur.execute(
            "INSERT INTO itemAttachments VALUES (2, 1, 0, 'application/pdf', NULL, 'storage:paper.pdf', 0, 0, '', 0)"
        )
        cur.execute(
            "INSERT INTO itemAttachments VALUES (8, 4, 2, 'application/pdf', NULL, 'file:///C:/Users/Public/linked.pdf', 0, 0, '', 0)"
        )
        cur.executemany(
            "INSERT INTO savedSearches VALUES (?, ?, '2026-01-02', ?, ?, 1, 1)",
            [
                (1, "Important", 1, "SEARCHKEY"),
                (2, "User Duplicate Search", 1, "DUPSEARCH"),
                (3, "Group Search", 2, "GSEARCHKEY"),
                (4, "Group Duplicate Search", 2, "DUPSEARCH"),
            ],
        )
        cur.executemany(
            "INSERT INTO savedSearchConditions VALUES (?, 1, 'title', 'contains', ?, 1)",
            [(1, "Sample"), (2, "Duplicate"), (3, "Group"), (4, "Duplicate")],
        )
        conn.commit()
    finally:
        conn.close()

    (storage_dir / "paper.pdf").write_bytes(sample_pdf_bytes("sample"))
    (styles_dir / "sample-style.csl").write_text(
        """<style xmlns="http://purl.org/net/xbiblio/csl" version="1.0">
  <info>
    <title>Sample Style</title>
    <id>http://www.zotero.org/styles/sample-style</id>
  </info>
</style>
""",
        encoding="utf-8",
    )

    return {
        "profile_root": profile_root,
        "profile_dir": profile_dir,
        "data_dir": data_dir,
        "sqlite_path": sqlite_path,
        "install_dir": install_dir,
        "executable": install_dir / "zotero.exe",
        "styles_dir": styles_dir,
    }


def _next_id(conn: sqlite3.Connection, table: str, column: str) -> int:
    row = conn.execute(f"SELECT COALESCE(MAX({column}), 0) + 1 AS next_id FROM {table}").fetchone()
    assert row is not None
    return int(row["next_id"])


def _item_type_id(conn: sqlite3.Connection, type_name: str) -> int:
    row = conn.execute("SELECT itemTypeID FROM itemTypes WHERE typeName = ?", (type_name,)).fetchone()
    if row:
        return int(row["itemTypeID"])
    fallback = conn.execute("SELECT itemTypeID FROM itemTypes WHERE typeName = 'journalArticle'").fetchone()
    assert fallback is not None
    return int(fallback["itemTypeID"])


def _field_id(conn: sqlite3.Connection, field_name: str) -> int:
    row = conn.execute("SELECT fieldID FROM fields WHERE fieldName = ?", (field_name,)).fetchone()
    if row:
        return int(row["fieldID"])
    field_id = _next_id(conn, "fields", "fieldID")
    conn.execute("INSERT INTO fields VALUES (?, ?, 0)", (field_id, field_name))
    return field_id


def _set_item_field(conn: sqlite3.Connection, item_id: int, field_name: str, value: str) -> None:
    value_id = _next_id(conn, "itemDataValues", "valueID")
    conn.execute("INSERT INTO itemDataValues VALUES (?, ?)", (value_id, value))
    conn.execute("INSERT INTO itemData VALUES (?, ?, ?)", (item_id, _field_id(conn, field_name), value_id))


def _item_key(prefix: str, item_id: int) -> str:
    return f"{prefix}{item_id:05d}"


def _safe_pdf_filename(source_url: str) -> str:
    parsed = urlparse(source_url)
    candidate = Path(unquote(parsed.path or "")).name or "attachment.pdf"
    candidate = re.sub(r"[^A-Za-z0-9._-]+", "-", candidate).strip("-") or "attachment.pdf"
    if not candidate.lower().endswith(".pdf"):
        candidate += ".pdf"
    return candidate


def _split_ris_records(content: str) -> list[str]:
    records: list[str] = []
    current: list[str] = []
    for line in content.splitlines():
        current.append(line)
        if line.startswith("ER  -"):
            record = "\n".join(current).strip()
            if record:
                records.append(record)
            current = []
    if current:
        record = "\n".join(current).strip()
        if record:
            records.append(record)
    return records or [content]


def _ris_title(record: str) -> str:
    match = re.search(r"(?m)^TI  - (.+)$", record)
    return match.group(1).strip() if match else "Imported Sample"


@contextmanager
def fake_zotero_http_server(
    *,
    local_api_root_status: int = 200,
    sqlite_path: Path | str | None = None,
    data_dir: Path | str | None = None,
):
    calls: list[dict[str, object]] = []
    sqlite_file = Path(sqlite_path) if sqlite_path is not None else None
    zotero_data_dir = Path(data_dir) if data_dir is not None else None
    sessions: dict[str, dict[str, object]] = {}

    def db_connect() -> sqlite3.Connection:
        if sqlite_file is None:
            raise RuntimeError("sqlite_path is required for this fake server operation")
        conn = sqlite3.connect(sqlite_file)
        conn.row_factory = sqlite3.Row
        return conn

    def create_top_level_item(
        item_payload: dict[str, object],
        *,
        connector_id: str,
        library_id: int = 1,
    ) -> dict[str, object]:
        if sqlite_file is None:
            return {"connector_id": connector_id}
        with closing(db_connect()) as conn:
            item_id = _next_id(conn, "items", "itemID")
            key = _item_key("IMP", item_id)
            item_type = str(item_payload.get("itemType") or "journalArticle")
            title = str(item_payload.get("title") or item_payload.get("bookTitle") or item_payload.get("publicationTitle") or "")
            item_type_id = _item_type_id(conn, item_type)
            conn.execute(
                "INSERT INTO items VALUES (?, ?, '2026-03-27', '2026-03-27', '2026-03-27', ?, ?, 1, 1)",
                (item_id, item_type_id, library_id, key),
            )
            if title:
                _set_item_field(conn, item_id, "title", title)
            conn.commit()
            return {
                "connector_id": connector_id,
                "itemID": item_id,
                "key": key,
                "title": title,
                "libraryID": library_id,
                "itemType": item_type,
            }

    def create_note_item(item_payload: dict[str, object], *, connector_id: str) -> dict[str, object]:
        if sqlite_file is None:
            return {"connector_id": connector_id}
        parent_key = str(item_payload.get("parentItem") or "")
        note_html = str(item_payload.get("note") or "")
        with closing(db_connect()) as conn:
            parent = conn.execute("SELECT itemID, libraryID FROM items WHERE key = ?", (parent_key,)).fetchone()
            if parent is None:
                raise RuntimeError(f"Unknown parent item for note: {parent_key}")
            item_id = _next_id(conn, "items", "itemID")
            key = _item_key("NOT", item_id)
            conn.execute(
                "INSERT INTO items VALUES (?, ?, '2026-03-27', '2026-03-27', '2026-03-27', ?, ?, 1, 1)",
                (item_id, _item_type_id(conn, "note"), int(parent["libraryID"]), key),
            )
            conn.execute(
                "INSERT INTO itemNotes VALUES (?, ?, ?, ?)",
                (item_id, int(parent["itemID"]), note_html, "Imported note"),
            )
            conn.commit()
            return {
                "connector_id": connector_id,
                "itemID": item_id,
                "key": key,
                "title": "Imported note",
                "libraryID": int(parent["libraryID"]),
                "itemType": "note",
            }

    def create_attachment_item(*, parent_item_id: int, title: str, source_url: str, content: bytes) -> dict[str, object]:
        if sqlite_file is None or zotero_data_dir is None:
            return {"title": title, "url": source_url}
        with closing(db_connect()) as conn:
            parent = conn.execute("SELECT libraryID FROM items WHERE itemID = ?", (parent_item_id,)).fetchone()
            if parent is None:
                raise RuntimeError(f"Unknown parent item id: {parent_item_id}")
            attachment_id = _next_id(conn, "items", "itemID")
            attachment_key = _item_key("ATT", attachment_id)
            filename = _safe_pdf_filename(source_url)
            storage_dir = zotero_data_dir / "storage" / attachment_key
            storage_dir.mkdir(parents=True, exist_ok=True)
            (storage_dir / filename).write_bytes(content)
            conn.execute(
                "INSERT INTO items VALUES (?, ?, '2026-03-27', '2026-03-27', '2026-03-27', ?, ?, 1, 1)",
                (attachment_id, _item_type_id(conn, "attachment"), int(parent["libraryID"]), attachment_key),
            )
            _set_item_field(conn, attachment_id, "title", title)
            _set_item_field(conn, attachment_id, "url", source_url)
            conn.execute(
                "INSERT INTO itemAttachments VALUES (?, ?, 1, 'application/pdf', NULL, ?, 0, 0, '', 0)",
                (attachment_id, parent_item_id, f"storage:{filename}"),
            )
            conn.commit()
            return {
                "itemID": attachment_id,
                "key": attachment_key,
                "path": str(storage_dir / filename),
            }

    def apply_session_update(session_id: str, target: str, tags_text: str) -> None:
        if sqlite_file is None:
            return
        session = sessions.get(session_id)
        if not session:
            return
        item_ids = [entry["itemID"] for entry in session["items"].values() if entry.get("itemID")]
        if not item_ids:
            return
        collection_id: int | None = None
        if target.startswith("C") and target[1:].isdigit():
            collection_id = int(target[1:])
        tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()]
        with closing(db_connect()) as conn:
            if collection_id is not None:
                order_index = int(
                    conn.execute(
                        "SELECT COALESCE(MAX(orderIndex), -1) + 1 AS next_order FROM collectionItems WHERE collectionID = ?",
                        (collection_id,),
                    ).fetchone()["next_order"]
                )
                for item_id in item_ids:
                    exists = conn.execute(
                        "SELECT 1 FROM collectionItems WHERE collectionID = ? AND itemID = ?",
                        (collection_id, item_id),
                    ).fetchone()
                    if exists is None:
                        conn.execute("INSERT INTO collectionItems VALUES (?, ?, ?)", (collection_id, item_id, order_index))
                        order_index += 1
            for tag in tags:
                row = conn.execute("SELECT tagID FROM tags WHERE name = ?", (tag,)).fetchone()
                if row is None:
                    tag_id = _next_id(conn, "tags", "tagID")
                    conn.execute("INSERT INTO tags VALUES (?, ?)", (tag_id, tag))
                else:
                    tag_id = int(row["tagID"])
                for item_id in item_ids:
                    exists = conn.execute(
                        "SELECT 1 FROM itemTags WHERE itemID = ? AND tagID = ?",
                        (item_id, tag_id),
                    ).fetchone()
                    if exists is None:
                        conn.execute("INSERT INTO itemTags VALUES (?, ?, 0)", (item_id, tag_id))
            conn.commit()

    class Handler(BaseHTTPRequestHandler):
        def _json_response(self, status: int, payload) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _binary_response(self, status: int, payload: bytes, *, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _text_response(self, status: int, payload: str) -> None:
            body = payload.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A003
            return

        def _item_response(self, item_key: str, query: dict[str, list[str]]) -> None:
            fmt = query.get("format", [""])[0]
            include = query.get("include", [""])[0]
            if fmt == "json" and include == "citation":
                self._json_response(200, {"citation": f"({item_key} citation)"})
                return
            if fmt == "json" and include == "bib":
                self._json_response(200, {"bib": f"{item_key} bibliography"})
                return
            if fmt == "ris":
                self._text_response(200, f"TY  - JOUR\nID  - {item_key}\nER  - \n")
                return
            if fmt == "bibtex":
                self._text_response(200, f"@article{{{item_key.lower()}}}\n")
                return
            if fmt == "csljson":
                self._text_response(200, json.dumps([{"id": item_key}], ensure_ascii=False))
                return
            self._json_response(200, {"key": item_key})

        def do_GET(self):  # noqa: N802
            calls.append({"method": "GET", "path": self.path})
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)
            if path.startswith("/connector/ping"):
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if path == "/downloads/sample.pdf":
                self._binary_response(200, sample_pdf_bytes("download"), content_type="application/pdf")
                return
            if path == "/downloads/wrong-content-type.pdf":
                self._binary_response(200, sample_pdf_bytes("download"), content_type="text/plain")
                return
            if path == "/downloads/not-pdf":
                self._binary_response(200, b"not-a-pdf", content_type="text/plain")
                return
            if path == "/downloads/missing.pdf":
                self._text_response(404, "missing")
                return
            if path.startswith("/api/users/0/items/top"):
                self._json_response(
                    200,
                    [
                        {
                            "key": "REG12345",
                            "data": {
                                "title": "Sample Title",
                            },
                        }
                    ],
                )
                return
            if path.startswith("/api/users/0/collections/COLLAAAA/items/top"):
                self._json_response(
                    200,
                    [
                        {
                            "key": "REG12345",
                            "data": {
                                "title": "Sample Title",
                            },
                        }
                    ],
                )
                return
            if path.startswith("/api/groups/2/items/top"):
                self._json_response(200, [{"key": "GROUPKEY", "data": {"title": "Group Title"}}])
                return
            if path.startswith("/api/groups/2/collections/GCOLLAAA/items/top"):
                self._json_response(200, [{"key": "GROUPKEY", "data": {"title": "Group Title"}}])
                return
            if path.startswith("/api/groups/2/searches/GSEARCHKEY/items"):
                self._json_response(200, [{"key": "GROUPKEY"}])
                return
            if path.startswith("/api/users/0/searches/SEARCHKEY/items"):
                self._json_response(200, [{"key": "REG12345"}])
                return
            if path.startswith("/api/users/0/items/REG12345"):
                self._item_response("REG12345", query)
                return
            if path.startswith("/api/groups/2/items/GROUPKEY"):
                self._item_response("GROUPKEY", query)
                return
            if path.startswith("/api/"):
                self.send_response(local_api_root_status)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            decoded_body = body.decode("utf-8", errors="replace")
            metadata_header = self.headers.get("X-Metadata")
            call = {
                "method": "POST",
                "path": self.path,
                "body": decoded_body,
            }
            if metadata_header:
                try:
                    call["metadata"] = json.loads(metadata_header)
                except json.JSONDecodeError:
                    call["metadata"] = metadata_header
            if self.path.startswith("/connector/saveAttachment"):
                call["body_length"] = len(body)
                call["content_type"] = self.headers.get("Content-Type")
            calls.append(call)

            if self.path.startswith("/connector/getSelectedCollection"):
                self._json_response(
                    200,
                    {
                        "libraryID": 1,
                        "libraryName": "My Library",
                        "libraryEditable": True,
                        "filesEditable": True,
                        "editable": True,
                        "id": 1,
                        "name": "Sample Collection",
                        "targets": [{"id": "L1", "name": "My Library", "filesEditable": True, "level": 0}],
                    },
                )
                return

            if self.path.startswith("/connector/import"):
                parsed = urlparse(self.path)
                session_id = parse_qs(parsed.query).get("session", [""])[0]
                sessions.setdefault(session_id, {"items": {}})
                imported_items: list[dict[str, object]] = []
                for index, record in enumerate(_split_ris_records(decoded_body), start=1):
                    connector_id = f"imported-{index}"
                    title = _ris_title(record)
                    item_info = create_top_level_item(
                        {
                            "itemType": "journalArticle",
                            "title": title,
                        },
                        connector_id=connector_id,
                    )
                    sessions[session_id]["items"][connector_id] = item_info
                    imported_items.append(
                        {
                            "id": connector_id,
                            "itemType": "journalArticle",
                            "title": title,
                        }
                    )
                self._json_response(201, imported_items)
                return

            if self.path.startswith("/connector/saveItems"):
                payload = json.loads(decoded_body or "{}")
                session_id = str(payload.get("sessionID") or "")
                sessions.setdefault(session_id, {"items": {}})
                for item in payload.get("items", []):
                    connector_id = str(item.get("id") or f"connector-{len(sessions[session_id]['items']) + 1}")
                    if str(item.get("itemType") or "") == "note" and item.get("parentItem"):
                        item_info = create_note_item(item, connector_id=connector_id)
                    else:
                        item_info = create_top_level_item(item, connector_id=connector_id)
                    sessions[session_id]["items"][connector_id] = item_info
                self.send_response(201)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return

            if self.path.startswith("/connector/updateSession"):
                payload = json.loads(decoded_body or "{}")
                apply_session_update(
                    str(payload.get("sessionID") or ""),
                    str(payload.get("target") or ""),
                    str(payload.get("tags") or ""),
                )
                self._json_response(200, {})
                return

            if self.path.startswith("/connector/saveAttachment"):
                try:
                    metadata = json.loads(metadata_header or "{}")
                except json.JSONDecodeError:
                    self._json_response(400, {"error": "invalid metadata"})
                    return
                session_id = str(metadata.get("sessionID") or "")
                parent_connector_id = str(metadata.get("parentItemID") or "")
                session = sessions.get(session_id)
                if session is None:
                    self._json_response(400, {"error": "unknown session"})
                    return
                parent = session["items"].get(parent_connector_id)
                if parent is None:
                    self._json_response(400, {"error": "unknown parent connector id"})
                    return
                try:
                    attachment = create_attachment_item(
                        parent_item_id=int(parent["itemID"]),
                        title=str(metadata.get("title") or "PDF"),
                        source_url=str(metadata.get("url") or ""),
                        content=body,
                    )
                except RuntimeError as exc:
                    self._json_response(400, {"error": str(exc)})
                    return
                self._json_response(201, attachment)
                return

            if self.path.startswith("/v1/responses"):
                self._json_response(
                    200,
                    {
                        "id": "resp_fake",
                        "output": [
                            {
                                "type": "message",
                                "content": [
                                    {
                                        "type": "output_text",
                                        "text": "Analysis text",
                                    }
                                ],
                            }
                        ],
                    },
                )
                return

            self.send_response(404)
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {"port": server.server_address[1], "calls": calls, "sessions": sessions}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
