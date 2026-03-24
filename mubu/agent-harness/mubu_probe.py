#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import gzip
import html
import json
import os
import re
import secrets
import string
import sys
from datetime import datetime, timezone
from json import JSONDecoder
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def candidate_appdata_roots(
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
    mount_root: Path = Path("/mnt/c/Users"),
) -> list[Path]:
    env = env or os.environ
    home = home or Path.home()
    candidates: list[Path] = []

    def add(path: str | Path | None) -> None:
        if not path:
            return
        candidate = Path(path).expanduser()
        if candidate not in candidates:
            candidates.append(candidate)

    add(env.get("APPDATA"))
    userprofile = env.get("USERPROFILE")
    if userprofile:
        add(Path(userprofile) / "AppData" / "Roaming")

    for username in (home.name, env.get("USER")):
        if username:
            add(mount_root / username / "AppData" / "Roaming")

    if mount_root.exists():
        for child in sorted(mount_root.iterdir()):
            if child.is_dir():
                add(child / "AppData" / "Roaming")

    return candidates


def default_mubu_data_root(
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
    mount_root: Path = Path("/mnt/c/Users"),
) -> Path:
    env = env or os.environ
    home = home or Path.home()
    for candidate in candidate_appdata_roots(env=env, home=home, mount_root=mount_root):
        if candidate.exists():
            return candidate / "Mubu" / "mubu_app_data" / "mubu_data"
    return home / ".config" / "mubu" / "mubu_data"


DEFAULT_MUBU_DATA_ROOT = Path(os.environ.get("MUBU_DATA_ROOT", str(default_mubu_data_root())))
DEFAULT_BACKUP_ROOT = Path(os.environ.get("MUBU_BACKUP_ROOT", str(DEFAULT_MUBU_DATA_ROOT / "backup")))
DEFAULT_LOG_ROOT = Path(os.environ.get("MUBU_LOG_ROOT", str(DEFAULT_MUBU_DATA_ROOT / "log")))
DEFAULT_STORAGE_ROOT = Path(os.environ.get("MUBU_STORAGE_ROOT", str(DEFAULT_MUBU_DATA_ROOT / ".storage")))
DEFAULT_API_HOST = os.environ.get("MUBU_API_HOST", "https://api2.mubu.com")
DEFAULT_PLATFORM = os.environ.get("MUBU_PLATFORM", "windows")
DEFAULT_PLATFORM_VERSION = os.environ.get("MUBU_PLATFORM_VERSION", "10.0.26100")

TAG_RE = re.compile(r"<[^>]+>")
ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
TIMESTAMP_RE = re.compile(r"^\[(?P<timestamp>[^\]]+)\]")
NET_REQUEST_RE = re.compile(r"Net request \d+ (?P<payload>\{.*\})$")
STORE_SET_RE = re.compile(r"Store set start (?P<doc_id>\S+) (?P<payload>\{.*\})$")
ANCHOR_RE = re.compile(r"<a\b(?P<attrs>[^>]*)>(?P<label>.*?)</a>", re.IGNORECASE | re.DOTALL)
TOKEN_ATTR_RE = re.compile(r'data-token="(?P<token>[^"]+)"')
HREF_DOC_RE = re.compile(r'href="https://mubu\.com/doc(?P<token>[^"?#/]+)"', re.IGNORECASE)
NODE_ID_ALPHABET = string.ascii_letters + string.digits
DAILY_TITLE_PATTERNS = (
    re.compile(r"^\d{2}\.\d{1,2}\.\d{1,2}(?:-\d{1,2}(?:\.\d{1,2})?)?$"),
    re.compile(r"^\d{4}[./-]\d{1,2}[./-]\d{1,2}$"),
    re.compile(r"^\d{4}年\d{1,2}月\d{1,2}日$"),
    re.compile(r"^\d{1,2}[./-]\d{1,2}$"),
    re.compile(r"^\d{1,2}月\d{1,2}日$"),
)
DEFAULT_DAILY_EXCLUDE_KEYWORDS = ("模板", "template")
DEFAULT_DAILY_FOLDER_KEYWORDS = ("daily", "diary", "journal", "日记", "日志", "每日", "每天", "日常")


def configured_daily_folder_ref(env: Mapping[str, str] | None = None) -> str | None:
    env = env or os.environ
    value = env.get("MUBU_DAILY_FOLDER", "")
    if not isinstance(value, str):
        return None
    resolved = value.strip()
    return resolved or None


def resolve_daily_folder_ref(
    folder_ref: str | None,
    env: Mapping[str, str] | None = None,
) -> str:
    value = (folder_ref or "").strip()
    if value:
        return value
    configured = configured_daily_folder_ref(env=env)
    if configured:
        return configured
    raise RuntimeError(
        "daily folder reference required; pass <folder_ref> explicitly "
        "or set MUBU_DAILY_FOLDER"
    )


def extract_plain_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(extract_plain_text(item.get("text", "")))
            else:
                parts.append(extract_plain_text(item))
        return "".join(parts).strip()
    if isinstance(value, dict):
        if "text" in value:
            return extract_plain_text(value.get("text"))
        return ""

    text = str(value)
    text = html.unescape(text)
    text = TAG_RE.sub("", text)
    text = ZERO_WIDTH_RE.sub("", text)
    return " ".join(text.split()).strip()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(errors="replace"))


def post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: int = 20,
) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {body[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"request failed for {url}: {exc}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON response from {url}: {body[:500]}") from exc


def parse_revision_generation(revision: str | None) -> int:
    if not revision:
        return 0
    head, _, _ = revision.partition("-")
    try:
        return int(head)
    except ValueError:
        return 0


def numeric_values(*values: Any) -> list[int]:
    result: list[int] = []
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            result.append(value)
    return result


def timestamp_ms_to_iso(value: int | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).astimezone().isoformat(timespec="seconds")


def normalized_lookup_key(value: str | None) -> str:
    return (value or "").strip().casefold()


def parse_event_timestamp_ms(value: str | None) -> int | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return int(dt.timestamp() * 1000)


def iter_json_objects_from_text(text: str) -> Iterable[dict[str, Any]]:
    decoder = JSONDecoder()
    cursor = 0
    while True:
        start = text.find('{"', cursor)
        if start == -1:
            break
        try:
            obj, consumed = decoder.raw_decode(text[start:])
        except Exception as e:
            cursor = start + 2
            continue
        if isinstance(obj, dict):
            yield obj
        cursor = start + consumed


def iter_storage_collection_files(storage_root: Path, pattern: str) -> Iterable[Path]:
    for path in sorted(storage_root.glob(pattern)):
        if path.is_file() and path.suffix in {".ldb", ".log"}:
            yield path


def load_collection_records(
    storage_root: Path,
    pattern: str,
    predicate,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in iter_storage_collection_files(storage_root, pattern):
        text = path.read_text(errors="ignore")
        for obj in iter_json_objects_from_text(text):
            if predicate(obj):
                records.append(obj)
    return records


def dedupe_latest_records(
    records: Iterable[dict[str, Any]],
    id_field: str = "id",
    timestamp_fields: Iterable[str] = (),
) -> list[dict[str, Any]]:
    latest_by_id: dict[str, dict[str, Any]] = {}
    timestamp_fields = tuple(timestamp_fields)

    def sort_key(item: dict[str, Any]) -> tuple[int, int]:
        return (
            parse_revision_generation(item.get("_rev") or item.get("rev")),
            max(numeric_values(*(item.get(field) for field in timestamp_fields)), default=0),
        )

    for record in records:
        record_id = record.get(id_field)
        if not isinstance(record_id, (str, int)):
            continue
        record_key = str(record_id)
        current = latest_by_id.get(record_key)
        if current is None or sort_key(record) >= sort_key(current):
            latest_by_id[record_key] = record

    return list(latest_by_id.values())


def parse_child_refs(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not isinstance(value, str) or not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    return []


def normalize_folder_record(raw: dict[str, Any]) -> dict[str, Any]:
    updated_at = max(numeric_values(raw.get("|n"), raw.get("|t"), raw.get("|v")), default=None)
    created_at = raw.get("|d") if isinstance(raw.get("|d"), int) else None
    children = parse_child_refs(raw.get("|p"))
    return {
        "folder_id": raw.get("id"),
        "name": raw.get("|o"),
        "parent_id": raw.get("|h") or "0",
        "children": children,
        "created_at": created_at,
        "created_at_iso": timestamp_ms_to_iso(created_at),
        "updated_at": updated_at,
        "updated_at_iso": timestamp_ms_to_iso(updated_at),
        "source": raw.get("|c"),
        "rev": raw.get("_rev"),
    }


def load_folders(storage_root: Path = DEFAULT_STORAGE_ROOT) -> list[dict[str, Any]]:
    records = load_collection_records(
        storage_root,
        "mubu_desktop_app-rxdb-2-folders*/*",
        lambda obj: "|o" in obj and isinstance(obj.get("id"), str),
    )
    return [normalize_folder_record(record) for record in dedupe_latest_records(records, timestamp_fields=["|n", "|t", "|v"])]


def normalize_document_meta_record(raw: dict[str, Any]) -> dict[str, Any]:
    created_at = raw.get("|e") if isinstance(raw.get("|e"), int) else None
    updated_at = max(numeric_values(raw.get("|m"), raw.get("|B"), raw.get("|z"), raw.get("|e")), default=None)
    return {
        "doc_id": raw.get("id"),
        "folder_id": raw.get("|h") or "0",
        "title": raw.get("|n"),
        "created_at": created_at,
        "created_at_iso": timestamp_ms_to_iso(created_at),
        "updated_at": updated_at,
        "updated_at_iso": timestamp_ms_to_iso(updated_at),
        "word_count": raw.get("|j") if isinstance(raw.get("|j"), int) else None,
        "source": raw.get("|d"),
        "rev": raw.get("_rev"),
    }


def load_document_metas(storage_root: Path = DEFAULT_STORAGE_ROOT) -> list[dict[str, Any]]:
    records = load_collection_records(
        storage_root,
        "mubu_desktop_app-rxdb-1-document_meta*/*",
        lambda obj: "|n" in obj and "|h" in obj and isinstance(obj.get("id"), str),
    )
    return [
        normalize_document_meta_record(record)
        for record in dedupe_latest_records(records, timestamp_fields=["|m", "|B", "|z", "|e"])
    ]


def build_folder_indexes(folders: Iterable[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    by_id = {folder["folder_id"]: folder for folder in folders if folder.get("folder_id")}
    path_cache: dict[str, str] = {}

    def build_path(folder_id: str | None) -> str:
        if not folder_id or folder_id == "0":
            return ""
        if folder_id in path_cache:
            return path_cache[folder_id]
        folder = by_id.get(folder_id)
        if not folder:
            return ""
        parent_path = build_path(folder.get("parent_id"))
        current = folder.get("name") or folder_id
        path_cache[folder_id] = f"{parent_path}/{current}" if parent_path else current
        return path_cache[folder_id]

    for folder_id in by_id:
        build_path(folder_id)

    return by_id, path_cache


def resolve_folder_reference(
    folders: Iterable[dict[str, Any]],
    folder_ref: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    folder_by_id, folder_paths = build_folder_indexes(folders)
    if folder_ref in folder_by_id:
        return folder_by_id[folder_ref], []

    normalized_ref = normalized_lookup_key(folder_ref)
    exact = [folder for folder in folder_by_id.values() if normalized_lookup_key(folder_paths.get(folder["folder_id"], "")) == normalized_ref]
    if len(exact) == 1:
        return exact[0], []
    if len(exact) > 1:
        return None, exact

    suffix = [
        folder
        for folder in folder_by_id.values()
        if normalized_lookup_key(folder_paths.get(folder["folder_id"], "")).endswith(normalized_ref)
    ]
    if len(suffix) == 1:
        return suffix[0], []
    if len(suffix) > 1:
        return None, suffix

    name_matches = [folder for folder in folder_by_id.values() if normalized_lookup_key(folder.get("name")) == normalized_ref]
    if len(name_matches) == 1:
        return name_matches[0], []
    if len(name_matches) > 1:
        return None, name_matches

    return None, []


def enrich_document_meta(
    meta: dict[str, Any],
    folder_paths: dict[str, str],
) -> dict[str, Any]:
    folder_path = folder_paths.get(meta.get("folder_id", ""), "")
    doc_path = folder_path
    if meta.get("title"):
        doc_path = f"{folder_path}/{meta['title']}" if folder_path else meta["title"]
    return {
        **meta,
        "folder_path": folder_path,
        "doc_path": doc_path,
    }


def document_meta_sort_key(meta: dict[str, Any]) -> tuple[int, int, str]:
    return (
        max(
            numeric_values(
                meta.get("updated_at"),
                meta.get("created_at"),
                meta.get("modified_at"),
            ),
            default=0,
        ),
        parse_revision_generation(meta.get("_rev") or meta.get("rev")),
        str(meta.get("doc_id") or ""),
    )


def dedupe_document_metas_by_logical_path(
    document_metas: Iterable[dict[str, Any]],
    folder_paths: dict[str, str],
) -> list[dict[str, Any]]:
    latest_by_path: dict[str, dict[str, Any]] = {}
    for meta in document_metas:
        enriched = enrich_document_meta(meta, folder_paths)
        logical_path = normalized_lookup_key(enriched.get("doc_path"))
        if not logical_path:
            logical_path = f"doc:{normalized_lookup_key(enriched.get('doc_id'))}"
        current = latest_by_path.get(logical_path)
        if current is None or document_meta_sort_key(enriched) >= document_meta_sort_key(current):
            latest_by_path[logical_path] = enriched
    return list(latest_by_path.values())


def folder_documents(
    document_metas: Iterable[dict[str, Any]],
    folders: Iterable[dict[str, Any]],
    folder_ref: str,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, list[dict[str, Any]]]:
    folder_by_id, folder_paths = build_folder_indexes(folders)
    folder, ambiguous = resolve_folder_reference(folder_by_id.values(), folder_ref)
    if folder is None:
        return [], None, ambiguous

    docs = [
        meta
        for meta in dedupe_document_metas_by_logical_path(document_metas, folder_paths)
        if meta.get("folder_id") == folder.get("folder_id")
    ]
    docs.sort(key=document_meta_sort_key, reverse=True)
    return docs, {**folder, "path": folder_paths.get(folder["folder_id"], "")}, []


def document_meta_by_id(
    document_metas: Iterable[dict[str, Any]],
    folders: Iterable[dict[str, Any]],
    doc_id: str,
) -> dict[str, Any] | None:
    _, folder_paths = build_folder_indexes(folders)
    matches = [
        enrich_document_meta(meta, folder_paths)
        for meta in document_metas
        if meta.get("doc_id") == doc_id
    ]
    if not matches:
        return None
    return max(matches, key=document_meta_sort_key)


def iter_nodes(nodes: Iterable[dict[str, Any]], path: tuple[int, ...] = ()) -> Iterable[tuple[tuple[int, ...], dict[str, Any]]]:
    for index, node in enumerate(nodes):
        current_path = path + (index,)
        yield current_path, node
        children = node.get("children") or []
        if isinstance(children, list):
            yield from iter_nodes(children, current_path)


def infer_title(data: dict[str, Any]) -> str:
    for _, node in iter_nodes(data.get("nodes", [])):
        title = extract_plain_text(node.get("text"))
        if title:
            return title
    return ""


def load_latest_backups(root: Path = DEFAULT_BACKUP_ROOT) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    if not root.exists():
        return documents

    for doc_dir in root.iterdir():
        if not doc_dir.is_dir():
            continue
        files = list(doc_dir.glob("*.json"))
        if not files:
            continue
        latest = max(files, key=lambda candidate: candidate.stat().st_mtime)
        data = load_json(latest)
        documents.append(
            {
                "doc_id": doc_dir.name,
                "backup_file": str(latest),
                "modified_at": latest.stat().st_mtime,
                "title": infer_title(data),
                "data": data,
            }
        )

    documents.sort(key=lambda item: item["modified_at"], reverse=True)
    return documents


def extract_doc_links(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, str):
        return []
    links: list[dict[str, Any]] = []
    for match in ANCHOR_RE.finditer(value):
        attrs = match.group("attrs")
        token_match = TOKEN_ATTR_RE.search(attrs) or HREF_DOC_RE.search(attrs)
        if not token_match:
            continue
        links.append(
            {
                "target_doc_id": token_match.group("token"),
                "label": extract_plain_text(match.group("label")),
            }
        )
    return links


def search_documents(documents: Iterable[dict[str, Any]], query: str, limit: int | None = None) -> list[dict[str, Any]]:
    normalized_query = query.lower()
    hits: list[dict[str, Any]] = []

    for document in documents:
        for path, node in iter_nodes(document["data"].get("nodes", [])):
            text = extract_plain_text(node.get("text"))
            note = extract_plain_text(node.get("note"))
            haystacks = [text.lower(), note.lower()]
            if not any(normalized_query in haystack for haystack in haystacks):
                continue

            hits.append(
                {
                    "doc_id": document["doc_id"],
                    "title": document["title"],
                    "backup_file": document["backup_file"],
                    "path": list(path),
                    "node_id": node.get("id"),
                    "text": text,
                    "note": note,
                }
            )
            if limit is not None and len(hits) >= limit:
                return hits

    return hits


def parse_client_sync_line(line: str) -> dict[str, Any] | None:
    timestamp_match = TIMESTAMP_RE.search(line)
    timestamp = timestamp_match.group("timestamp") if timestamp_match else None

    request_match = NET_REQUEST_RE.search(line)
    if request_match:
        payload = json.loads(request_match.group("payload"))
        data = payload.get("data") or {}
        if payload.get("pathname") == "/v3/api/colla/events":
            return {
                "timestamp": timestamp,
                "kind": "change_request" if data.get("type") == "CHANGE" else "colla_request",
                "pathname": payload.get("pathname"),
                "document_id": data.get("documentId"),
                "member_id": data.get("memberId"),
                "event_type": data.get("type"),
                "version": data.get("version"),
                "payload": payload,
            }

    store_match = STORE_SET_RE.search(line)
    if store_match:
        payload = json.loads(store_match.group("payload"))
        if payload.get("cachedChangeset") or payload.get("unAckChangeset"):
            return {
                "timestamp": timestamp,
                "kind": "store_set",
                "document_id": store_match.group("doc_id"),
                "cached_changeset": payload.get("cachedChangeset", []),
                "unack_changeset": payload.get("unAckChangeset", []),
                "payload": payload,
            }

    return None


def iter_log_files(log_root: Path) -> list[Path]:
    files = sorted(log_root.glob("client-sync*.log*"), key=lambda path: path.stat().st_mtime, reverse=True)
    return files


def read_log_text(path: Path) -> str:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", errors="replace") as handle:
            return handle.read()
    return path.read_text(errors="replace")


def load_change_events(log_root: Path = DEFAULT_LOG_ROOT, doc_id: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not log_root.exists():
        return events

    for path in iter_log_files(log_root):
        for line in read_log_text(path).splitlines():
            parsed = parse_client_sync_line(line)
            if not parsed:
                continue
            if doc_id and parsed.get("document_id") != doc_id:
                continue
            parsed = {"source_file": str(path), **parsed}
            events.append(parsed)

    events.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
    if limit is not None:
        events = events[:limit]
    return events


def recent_documents(
    backups: Iterable[dict[str, Any]],
    document_metas: Iterable[dict[str, Any]],
    folders: Iterable[dict[str, Any]],
    log_root: Path = DEFAULT_LOG_ROOT,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    folder_by_id, folder_paths = build_folder_indexes(folders)
    activity: dict[str, dict[str, Any]] = {}

    for backup in backups:
        doc_id = backup["doc_id"]
        item = activity.setdefault(doc_id, {"doc_id": doc_id})
        item.setdefault("title", backup.get("title"))
        item["backup_file"] = backup.get("backup_file")
        item["backup_modified_at"] = backup.get("modified_at")

    for meta in document_metas:
        doc_id = meta["doc_id"]
        item = activity.setdefault(doc_id, {"doc_id": doc_id})
        item["title"] = meta.get("title") or item.get("title")
        item["folder_id"] = meta.get("folder_id")
        item["folder_path"] = folder_paths.get(meta.get("folder_id", ""), "")
        item["created_at"] = meta.get("created_at")
        item["updated_at"] = meta.get("updated_at")
        item["word_count"] = meta.get("word_count")

    for event in load_change_events(log_root=log_root, limit=None):
        doc_id = event.get("document_id")
        if not doc_id:
            continue
        item = activity.setdefault(doc_id, {"doc_id": doc_id})
        event_ts = parse_event_timestamp_ms(event.get("timestamp"))
        current = item.get("last_event_at")
        if event_ts is not None and (current is None or event_ts >= current):
            item["last_event_at"] = event_ts
            item["last_event_at_iso"] = event.get("timestamp")
            item["last_event_type"] = event.get("event_type")

    recent = list(activity.values())
    for item in recent:
        item["sort_ts"] = max(
            numeric_values(
                item.get("last_event_at"),
                item.get("updated_at"),
                item.get("backup_modified_at"),
                item.get("created_at"),
            ),
            default=0,
        )
        folder_id = item.get("folder_id")
        if folder_id and "folder_path" not in item:
            item["folder_path"] = folder_paths.get(folder_id, "")
        if item.get("created_at") is not None:
            item["created_at_iso"] = timestamp_ms_to_iso(item.get("created_at"))
        if item.get("updated_at") is not None:
            item["updated_at_iso"] = timestamp_ms_to_iso(item.get("updated_at"))
        if item.get("backup_modified_at") is not None:
            item["backup_modified_at_iso"] = timestamp_ms_to_iso(int(item.get("backup_modified_at") * 1000))

    recent.sort(key=lambda item: item.get("sort_ts", 0), reverse=True)
    if limit is not None:
        recent = recent[:limit]
    return recent


def looks_like_daily_title(
    title: str | None,
    exclude_keywords: Iterable[str] = DEFAULT_DAILY_EXCLUDE_KEYWORDS,
) -> bool:
    if not isinstance(title, str):
        return False
    title = title.strip()
    if not title:
        return False
    if not any(pattern.match(title) for pattern in DAILY_TITLE_PATTERNS):
        return False
    lowered = title.casefold()
    return not any(keyword.casefold() in lowered for keyword in exclude_keywords)


def looks_like_daily_folder_name(
    name: str | None,
    keywords: Iterable[str] = DEFAULT_DAILY_FOLDER_KEYWORDS,
) -> bool:
    normalized_name = normalized_lookup_key(name)
    if not normalized_name:
        return False
    return any(keyword.casefold() in normalized_name for keyword in keywords)


def choose_current_daily_document(
    docs: Iterable[dict[str, Any]],
    allow_non_daily_titles: bool = False,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    sorted_docs = sorted(
        docs,
        key=lambda item: max(
            numeric_values(item.get("updated_at"), item.get("created_at")),
            default=0,
        ),
        reverse=True,
    )
    dated_docs = [doc for doc in sorted_docs if looks_like_daily_title(doc.get("title"))]
    candidates = dated_docs if dated_docs else (sorted_docs if allow_non_daily_titles else [])
    return (candidates[0] if candidates else None), candidates


def normalize_user_record(raw: dict[str, Any]) -> dict[str, Any]:
    updated_at = raw.get("|h") if isinstance(raw.get("|h"), int) else None
    return {
        "user_id": str(raw.get("id")),
        "token": raw.get("|u"),
        "display_name": raw.get("|i") or raw.get("|q"),
        "phone": raw.get("|n"),
        "photo": raw.get("|o"),
        "vip_end_date": raw.get("|w"),
        "remember": raw.get("|r"),
        "updated_at": updated_at,
        "updated_at_iso": timestamp_ms_to_iso(updated_at),
        "rev": raw.get("_rev"),
    }


def load_users(storage_root: Path = DEFAULT_STORAGE_ROOT) -> list[dict[str, Any]]:
    records = load_collection_records(
        storage_root,
        "mubu_desktop_app-rxdb-1-users*/*",
        lambda obj: isinstance(obj.get("id"), int) and isinstance(obj.get("|u"), str),
    )
    users = [
        normalize_user_record(record)
        for record in dedupe_latest_records(records, timestamp_fields=["|h"])
    ]
    users.sort(key=lambda item: item.get("updated_at") or 0, reverse=True)
    return users


def get_active_user(storage_root: Path = DEFAULT_STORAGE_ROOT) -> dict[str, Any] | None:
    users = load_users(storage_root)
    return users[0] if users else None


def build_api_headers(
    user: dict[str, Any],
    platform: str = DEFAULT_PLATFORM,
    platform_version: str = DEFAULT_PLATFORM_VERSION,
) -> dict[str, str]:
    return {
        "mubu-desktop": "true",
        "platform": platform,
        "platform-version": platform_version,
        "User-Agent": f"{platform} Mubu Electron",
        "token": user["token"],
        "userId": user["user_id"],
        "Content-Type": "application/json;",
    }


def fetch_user_info(user: dict[str, Any], api_host: str = DEFAULT_API_HOST) -> dict[str, Any]:
    return post_json(
        f"{api_host}/v3/api/user/info",
        {"enhance": True},
        build_api_headers(user),
    )


def fetch_document_versions(user: dict[str, Any], api_host: str = DEFAULT_API_HOST) -> dict[str, int]:
    response = post_json(
        f"{api_host}/v3/api/document/version/list",
        {},
        build_api_headers(user),
    )
    if response.get("code") != 0:
        raise RuntimeError(f"version list failed: {response}")
    return {
        item["docId"]: item["version"]
        for item in response.get("data", [])
        if isinstance(item, dict) and isinstance(item.get("docId"), str)
    }


def fetch_document_remote(doc_id: str, user: dict[str, Any], api_host: str = DEFAULT_API_HOST) -> dict[str, Any]:
    response = post_json(
        f"{api_host}/v3/api/document/get",
        {"docId": doc_id},
        build_api_headers(user),
    )
    if response.get("code") != 0:
        raise RuntimeError(f"document get failed for {doc_id}: {response}")
    return response["data"]


def latest_doc_member_context(events: Iterable[dict[str, Any]], doc_id: str) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
    latest_ts = -1
    for event in events:
        if event.get("document_id") != doc_id or not event.get("member_id"):
            continue
        ts = parse_event_timestamp_ms(event.get("timestamp")) or -1
        if ts >= latest_ts:
            latest_ts = ts
            latest = {
                "document_id": doc_id,
                "member_id": event.get("member_id"),
                "last_seen_at": event.get("timestamp"),
                "event_type": event.get("event_type"),
            }
    return latest


def resolve_mutation_member_context(
    events: Iterable[dict[str, Any]],
    doc_id: str,
    execute: bool,
) -> dict[str, Any] | None:
    context = latest_doc_member_context(events, doc_id)
    if context is not None:
        return context
    if execute:
        return None
    return {
        "document_id": doc_id,
        "member_id": None,
        "last_seen_at": None,
        "event_type": None,
        "source": "dry_run_placeholder",
        "execute_ready": False,
    }


def plain_text_to_html(value: str) -> str:
    escaped = html.escape(value).replace("\n", "<br>")
    return f"<span>{escaped}</span>"


def maybe_plain_text_to_html(value: str | None) -> str | None:
    if value is None:
        return None
    if value == "":
        return ""
    return plain_text_to_html(value)


def rich_text_to_html(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        raise ValueError(f"unsupported rich text value: {type(value)!r}")

    chunks: list[str] = []
    for segment in value:
        if not isinstance(segment, dict):
            raise ValueError(f"unsupported segment type: {type(segment)!r}")
        if segment.get("type", 1) != 1:
            raise ValueError(f"unsupported segment payload: {segment}")
        text = segment.get("text")
        if not isinstance(text, str):
            raise ValueError(f"segment missing plain text: {segment}")

        classes: list[str] = []
        style = segment.get("style")
        if isinstance(style, dict):
            if style.get("strikethrough"):
                classes.append("strikethrough")
            if style.get("bold"):
                classes.append("bold")
            if style.get("italic"):
                classes.append("italic")
            if style.get("underline"):
                classes.append("underline")

        class_attr = f' class="{" ".join(classes)}"' if classes else ""
        escaped = html.escape(text).replace("\n", "<br>")
        chunks.append(f"<span{class_attr}>{escaped}</span>")
    return "".join(chunks)


def serialize_node(node: dict[str, Any], max_depth: int | None = None, depth: int = 0) -> dict[str, Any]:
    result = {
        "id": node.get("id"),
        "text": extract_plain_text(node.get("text")),
        "note": extract_plain_text(node.get("note")),
        "modified": node.get("modified"),
    }
    if max_depth is None or depth < max_depth:
        result["children"] = [
            serialize_node(child, max_depth=max_depth, depth=depth + 1)
            for child in (node.get("children") or [])
        ]
    return result


def list_document_nodes(
    data: dict[str, Any],
    query: str | None = None,
    max_depth: int | None = None,
) -> list[dict[str, Any]]:
    normalized_query = normalized_lookup_key(query) if query else None
    payload: list[dict[str, Any]] = []

    for path, node in iter_nodes(data.get("nodes", [])):
        depth = len(path) - 1
        if max_depth is not None and depth > max_depth:
            continue

        text = extract_plain_text(node.get("text"))
        note = extract_plain_text(node.get("note"))
        if normalized_query:
            haystack = "\n".join([text, note]).casefold()
            if normalized_query not in haystack:
                continue

        modified = node.get("modified") if isinstance(node.get("modified"), int) else None
        children = node.get("children") or []
        child_count = len(children) if isinstance(children, list) else 0
        payload.append(
            {
                "node_id": node.get("id"),
                "path": ["nodes", *path],
                "api_path": node_path_to_api_path(("nodes", *path)),
                "depth": depth,
                "text": text,
                "note": note,
                "child_count": child_count,
                "modified": modified,
                "modified_at_iso": timestamp_ms_to_iso(modified),
            }
        )

    return payload


def show_document(
    documents: Iterable[dict[str, Any]],
    doc_id: str,
    max_depth: int | None = None,
    title_override: str | None = None,
    folder_path: str | None = None,
    doc_path: str | None = None,
) -> dict[str, Any] | None:
    for document in documents:
        if document["doc_id"] != doc_id:
            continue
        return {
            "doc_id": document["doc_id"],
            "title": title_override or document["title"],
            "backup_file": document["backup_file"],
            "modified_at": document["modified_at"],
            "folder_path": folder_path,
            "doc_path": doc_path,
            "view_type": document["data"].get("viewType"),
            "nodes": [
                serialize_node(node, max_depth=max_depth)
                for node in document["data"].get("nodes", [])
            ],
        }
    return None


def resolve_document_reference(
    document_metas: Iterable[dict[str, Any]],
    folders: Iterable[dict[str, Any]],
    doc_ref: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    _, folder_paths = build_folder_indexes(folders)
    metas = dedupe_document_metas_by_logical_path(document_metas, folder_paths)

    by_id = [meta for meta in metas if meta.get("doc_id") == doc_ref]
    if len(by_id) == 1:
        return by_id[0], []

    normalized_ref = normalized_lookup_key(doc_ref)

    exact_path = [meta for meta in metas if normalized_lookup_key(meta.get("doc_path")) == normalized_ref]
    if len(exact_path) == 1:
        return exact_path[0], []
    if len(exact_path) > 1:
        return None, exact_path

    suffix_path = [
        meta
        for meta in metas
        if normalized_lookup_key(meta.get("doc_path")).endswith(normalized_ref)
    ]
    if len(suffix_path) == 1:
        return suffix_path[0], []
    if len(suffix_path) > 1:
        return None, suffix_path

    title_matches = [meta for meta in metas if normalized_lookup_key(meta.get("title")) == normalized_ref]
    if len(title_matches) == 1:
        return title_matches[0], []
    if len(title_matches) > 1:
        return None, title_matches

    return None, []


def show_document_by_reference(
    documents: Iterable[dict[str, Any]],
    document_metas: Iterable[dict[str, Any]],
    folders: Iterable[dict[str, Any]],
    doc_ref: str,
    max_depth: int | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    meta, ambiguous = resolve_document_reference(document_metas, folders, doc_ref)
    if meta is None:
        return None, ambiguous
    return (
        show_document(
            documents,
            meta["doc_id"],
            max_depth=max_depth,
            title_override=meta.get("title"),
            folder_path=meta.get("folder_path"),
            doc_path=meta.get("doc_path"),
        ),
        [],
    )


def document_links(
    documents: Iterable[dict[str, Any]],
    doc_id: str,
    title_lookup: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    title_lookup = title_lookup or {}
    for document in documents:
        if document["doc_id"] != doc_id:
            continue
        links: list[dict[str, Any]] = []
        for path, node in iter_nodes(document["data"].get("nodes", [])):
            for field in ("text", "note"):
                for link in extract_doc_links(node.get(field)):
                    links.append(
                        {
                            "source_doc_id": doc_id,
                            "source_doc_title": title_lookup.get(doc_id) or document.get("title"),
                            "source_node_id": node.get("id"),
                            "source_path": list(path),
                            "source_field": field,
                            "source_text": extract_plain_text(node.get("text")),
                            "target_doc_id": link["target_doc_id"],
                            "target_title": title_lookup.get(link["target_doc_id"]),
                            "label": link["label"],
                        }
                    )
        return links
    return []


def resolve_node_reference_in_data(
    data: dict[str, Any],
    node_id: str | None = None,
    match_text: str | None = None,
    field: str = "text",
) -> tuple[dict[str, Any] | None, tuple[Any, ...] | None, list[dict[str, Any]]]:
    matches: list[dict[str, Any]] = []
    for path, node in iter_nodes(data.get("nodes", [])):
        if node_id and node.get("id") == node_id:
            return node, ("nodes", *path), []
        if match_text and extract_plain_text(node.get(field)) == match_text:
            matches.append({"node": node, "path": ("nodes", *path)})

    if node_id:
        return None, None, []
    if len(matches) == 1:
        return matches[0]["node"], matches[0]["path"], []
    if len(matches) > 1:
        return None, None, matches
    return None, None, []


def resolve_node_at_path(
    data: dict[str, Any],
    path: Iterable[Any],
) -> dict[str, Any] | None:
    parts = list(path)
    if not parts or parts[0] != "nodes":
        raise ValueError(f"unsupported node path root: {parts}")
    if len(parts) < 2:
        raise ValueError(f"node path missing index: {parts}")

    siblings = data.get("nodes")
    if not isinstance(siblings, list):
        return None

    current: dict[str, Any] | None = None
    for part in parts[1:]:
        if not isinstance(part, int):
            raise ValueError(f"unsupported node path segment: {parts}")
        if part < 0 or part >= len(siblings):
            return None
        current = siblings[part]
        children = current.get("children") or []
        siblings = children if isinstance(children, list) else []
    return current


def parent_context_for_path(
    data: dict[str, Any],
    path: Iterable[Any],
) -> tuple[dict[str, Any] | None, tuple[Any, ...] | None, int]:
    parts = tuple(path)
    if not parts or parts[0] != "nodes":
        raise ValueError(f"unsupported node path root: {parts}")
    if len(parts) < 2:
        raise ValueError(f"node path missing index: {parts}")

    index = parts[-1]
    if not isinstance(index, int):
        raise ValueError(f"unsupported node path index: {parts}")
    if len(parts) == 2:
        return None, None, index

    parent_path = parts[:-1]
    parent_node = resolve_node_at_path(data, parent_path)
    if parent_node is None:
        raise ValueError(f"parent node not found for path: {parts}")
    return parent_node, parent_path, index


def node_path_to_api_path(path: Iterable[Any]) -> list[Any]:
    parts = list(path)
    if not parts or parts[0] != "nodes":
        raise ValueError(f"unsupported node path root: {parts}")
    if "children" in parts:
        return parts

    api_path: list[Any] = ["nodes"]
    for index, part in enumerate(parts[1:]):
        if index == 0:
            api_path.append(part)
        else:
            api_path.extend(["children", part])
    return api_path


def generate_node_id(length: int = 10) -> str:
    return "".join(secrets.choice(NODE_ID_ALPHABET) for _ in range(length))


def build_text_update_request(
    doc_id: str,
    member_id: str | None,
    version: int,
    node: dict[str, Any],
    path: Iterable[Any],
    new_text: str,
    field: str = "text",
    modified_ms: int | None = None,
) -> dict[str, Any]:
    modified_ms = modified_ms or int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    if field not in {"text", "note"}:
        raise ValueError(f"unsupported field for text update: {field}")

    current_value = rich_text_to_html(node.get(field))
    updated_node = {
        "id": node.get("id"),
        field: plain_text_to_html(new_text),
        "modified": modified_ms,
        "forceUpdate": True,
    }
    original_node = {
        "id": node.get("id"),
        field: current_value,
        "modified": node.get("modified"),
    }
    return {
        "pathname": "/v3/api/colla/events",
        "method": "POST",
        "data": {
            "memberId": member_id,
            "type": "CHANGE",
            "version": version,
            "documentId": doc_id,
            "events": [
                {
                    "name": "update",
                    "updated": [
                        {
                            "updated": updated_node,
                            "original": original_node,
                            "path": list(path),
                        }
                    ],
                }
            ],
        },
    }


def build_create_child_request(
    doc_id: str,
    member_id: str | None,
    version: int,
    parent_node: dict[str, Any],
    parent_path: Iterable[Any],
    text: str,
    note: str | None = None,
    child_id: str | None = None,
    index: int | None = None,
    modified_ms: int | None = None,
) -> dict[str, Any]:
    modified_ms = modified_ms or int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    child_id = child_id or generate_node_id()

    children = parent_node.get("children") or []
    if not isinstance(children, list):
        children = []

    if index is None:
        index = len(children)
    if index < 0 or index > len(children):
        raise ValueError(f"child index out of range: {index}")

    node_payload = {
        "id": child_id,
        "taskStatus": 0,
        "text": maybe_plain_text_to_html(text) or "",
        "modified": modified_ms,
        "children": [],
    }
    note_html = maybe_plain_text_to_html(note)
    if note_html is not None:
        node_payload["note"] = note_html
    if text or (note is not None and note != ""):
        node_payload["forceUpdate"] = True

    create_path = node_path_to_api_path(parent_path) + ["children", index]
    return {
        "pathname": "/v3/api/colla/events",
        "method": "POST",
        "data": {
            "memberId": member_id,
            "type": "CHANGE",
            "version": version,
            "documentId": doc_id,
            "events": [
                {
                    "name": "create",
                    "created": [
                        {
                            "index": index,
                            "parentId": parent_node.get("id"),
                            "node": node_payload,
                            "path": create_path,
                        }
                    ],
                }
            ],
        },
    }


def build_delete_node_request(
    doc_id: str,
    member_id: str | None,
    version: int,
    node: dict[str, Any],
    path: Iterable[Any],
    parent_node: dict[str, Any] | None = None,
) -> dict[str, Any]:
    deleted_node = copy.deepcopy(node)
    children = deleted_node.get("children")
    if not isinstance(children, list):
        deleted_node["children"] = []

    raw_path = tuple(path)
    if len(raw_path) < 2:
        raise ValueError(f"node path missing index: {raw_path}")
    index = raw_path[-1]
    if not isinstance(index, int):
        raise ValueError(f"unsupported node path index: {raw_path}")

    return {
        "pathname": "/v3/api/colla/events",
        "method": "POST",
        "data": {
            "memberId": member_id,
            "type": "CHANGE",
            "version": version,
            "documentId": doc_id,
            "events": [
                {
                    "name": "delete",
                    "deleted": [
                        {
                            "parentId": parent_node.get("id") if parent_node else None,
                            "index": index,
                            "node": deleted_node,
                            "path": node_path_to_api_path(raw_path),
                        }
                    ],
                }
            ],
        },
    }


def perform_text_update(
    user: dict[str, Any],
    doc_id: str,
    member_id: str | None,
    version: int,
    node: dict[str, Any],
    path: Iterable[Any],
    new_text: str,
    field: str = "text",
    execute: bool = False,
    api_host: str = DEFAULT_API_HOST,
) -> dict[str, Any]:
    request_payload = build_text_update_request(
        doc_id=doc_id,
        member_id=member_id,
        version=version,
        node=node,
        path=path,
        new_text=new_text,
        field=field,
    )
    if not execute:
        return {
            "execute": False,
            "request": request_payload,
        }

    response = post_json(
        f"{api_host}{request_payload['pathname']}",
        request_payload["data"],
        build_api_headers(user),
    )
    return {
        "execute": True,
        "request": request_payload,
        "response": response,
    }


def perform_create_child(
    user: dict[str, Any],
    doc_id: str,
    member_id: str | None,
    version: int,
    parent_node: dict[str, Any],
    parent_path: Iterable[Any],
    text: str,
    note: str | None = None,
    index: int | None = None,
    execute: bool = False,
    api_host: str = DEFAULT_API_HOST,
) -> dict[str, Any]:
    request_payload = build_create_child_request(
        doc_id=doc_id,
        member_id=member_id,
        version=version,
        parent_node=parent_node,
        parent_path=parent_path,
        text=text,
        note=note,
        index=index,
    )
    if not execute:
        return {
            "execute": False,
            "request": request_payload,
        }

    response = post_json(
        f"{api_host}{request_payload['pathname']}",
        request_payload["data"],
        build_api_headers(user),
    )
    return {
        "execute": True,
        "request": request_payload,
        "response": response,
    }


def perform_delete_node(
    user: dict[str, Any],
    doc_id: str,
    member_id: str | None,
    version: int,
    node: dict[str, Any],
    path: Iterable[Any],
    parent_node: dict[str, Any] | None = None,
    execute: bool = False,
    api_host: str = DEFAULT_API_HOST,
) -> dict[str, Any]:
    request_payload = build_delete_node_request(
        doc_id=doc_id,
        member_id=member_id,
        version=version,
        node=node,
        path=path,
        parent_node=parent_node,
    )
    if not execute:
        return {
            "execute": False,
            "request": request_payload,
        }

    response = post_json(
        f"{api_host}{request_payload['pathname']}",
        request_payload["data"],
        build_api_headers(user),
    )
    return {
        "execute": True,
        "request": request_payload,
        "response": response,
    }


def dump_output(data: Any, as_json: bool) -> None:
    if as_json:
        json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return

    if isinstance(data, list):
        for item in data:
            print(json.dumps(item, ensure_ascii=False))
        return

    print(json.dumps(data, ensure_ascii=False, indent=2))


def ambiguous_error_message(kind: str, ref: str, matches: Iterable[dict[str, Any]], path_key: str) -> str:
    options = []
    for item in matches:
        label = item.get(path_key) or item.get("name") or item.get("title") or item.get("doc_id") or item.get("folder_id")
        options.append(str(label))
        if len(options) >= 5:
            break
    suffix = f" matches: {', '.join(options)}" if options else ""
    return f"ambiguous {kind} reference: {ref}.{suffix}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe local Mubu desktop backups and sync logs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    docs_parser = subparsers.add_parser("docs", help="List latest known document snapshots from local backups.")
    docs_parser.add_argument("--root", type=Path, default=DEFAULT_BACKUP_ROOT)
    docs_parser.add_argument("--limit", type=int, default=20)
    docs_parser.add_argument("--json", action="store_true")

    show_parser = subparsers.add_parser("show", help="Show the latest backup tree for one document.")
    show_parser.add_argument("doc_id")
    show_parser.add_argument("--root", type=Path, default=DEFAULT_BACKUP_ROOT)
    show_parser.add_argument("--max-depth", type=int, default=None)
    show_parser.add_argument("--json", action="store_true")

    search_parser = subparsers.add_parser("search", help="Search latest backups for matching node text or note content.")
    search_parser.add_argument("query")
    search_parser.add_argument("--root", type=Path, default=DEFAULT_BACKUP_ROOT)
    search_parser.add_argument("--limit", type=int, default=20)
    search_parser.add_argument("--json", action="store_true")

    changes_parser = subparsers.add_parser("changes", help="Parse recent client-sync change events from local logs.")
    changes_parser.add_argument("--log-root", type=Path, default=DEFAULT_LOG_ROOT)
    changes_parser.add_argument("--doc-id", default=None)
    changes_parser.add_argument("--limit", type=int, default=20)
    changes_parser.add_argument("--json", action="store_true")

    folders_parser = subparsers.add_parser("folders", help="List folder metadata from local RxDB storage.")
    folders_parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    folders_parser.add_argument("--query", default=None)
    folders_parser.add_argument("--limit", type=int, default=50)
    folders_parser.add_argument("--json", action="store_true")

    folder_docs_parser = subparsers.add_parser("folder-docs", help="List document metadata for one folder.")
    folder_docs_parser.add_argument("folder_id")
    folder_docs_parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    folder_docs_parser.add_argument("--limit", type=int, default=50)
    folder_docs_parser.add_argument("--json", action="store_true")

    path_docs_parser = subparsers.add_parser("path-docs", help="List documents for one folder path or folder id.")
    path_docs_parser.add_argument("folder_ref")
    path_docs_parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    path_docs_parser.add_argument("--limit", type=int, default=50)
    path_docs_parser.add_argument("--json", action="store_true")

    recent_parser = subparsers.add_parser("recent", help="List recently active documents using backups, metadata, and sync logs.")
    recent_parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    recent_parser.add_argument("--root", type=Path, default=DEFAULT_BACKUP_ROOT)
    recent_parser.add_argument("--log-root", type=Path, default=DEFAULT_LOG_ROOT)
    recent_parser.add_argument("--limit", type=int, default=20)
    recent_parser.add_argument("--json", action="store_true")

    links_parser = subparsers.add_parser("links", help="Extract outbound Mubu document links from one document backup.")
    links_parser.add_argument("doc_id")
    links_parser.add_argument("--root", type=Path, default=DEFAULT_BACKUP_ROOT)
    links_parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    links_parser.add_argument("--json", action="store_true")

    daily_parser = subparsers.add_parser("daily", help="Find Daily-style folders and list the documents inside them.")
    daily_parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    daily_parser.add_argument(
        "--query",
        default=None,
        help="Optional folder-name substring filter. Defaults to built-in daily-folder heuristics.",
    )
    daily_parser.add_argument("--limit", type=int, default=50)
    daily_parser.add_argument("--json", action="store_true")

    daily_current_parser = subparsers.add_parser(
        "daily-current",
        help="Resolve the current daily document from one Daily-style folder.",
    )
    daily_current_parser.add_argument("folder_ref", nargs="?")
    daily_current_parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    daily_current_parser.add_argument("--limit", type=int, default=5)
    daily_current_parser.add_argument(
        "--allow-non-daily-titles",
        action="store_true",
        help="Fallback to the latest document even if no date-like title is found.",
    )
    daily_current_parser.add_argument("--json", action="store_true")

    daily_nodes_parser = subparsers.add_parser(
        "daily-nodes",
        help="List live nodes from the current daily document in one step.",
    )
    daily_nodes_parser.add_argument("folder_ref", nargs="?")
    daily_nodes_parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    daily_nodes_parser.add_argument("--api-host", default=DEFAULT_API_HOST)
    daily_nodes_parser.add_argument("--query", default=None, help="Filter nodes by plain-text substring.")
    daily_nodes_parser.add_argument("--max-depth", type=int, default=None)
    daily_nodes_parser.add_argument("--limit", type=int, default=200)
    daily_nodes_parser.add_argument(
        "--allow-non-daily-titles",
        action="store_true",
        help="Fallback to the latest document even if no date-like title is found.",
    )
    daily_nodes_parser.add_argument("--json", action="store_true")

    open_path_parser = subparsers.add_parser("open-path", help="Open one document by full path, suffix path, title, or doc id.")
    open_path_parser.add_argument("doc_ref")
    open_path_parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    open_path_parser.add_argument("--root", type=Path, default=DEFAULT_BACKUP_ROOT)
    open_path_parser.add_argument("--max-depth", type=int, default=None)
    open_path_parser.add_argument("--json", action="store_true")

    doc_nodes_parser = subparsers.add_parser(
        "doc-nodes",
        help="List live document nodes with node ids and update-target paths.",
    )
    doc_nodes_parser.add_argument("doc_ref")
    doc_nodes_parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    doc_nodes_parser.add_argument("--api-host", default=DEFAULT_API_HOST)
    doc_nodes_parser.add_argument("--query", default=None, help="Filter nodes by plain-text substring.")
    doc_nodes_parser.add_argument("--max-depth", type=int, default=None)
    doc_nodes_parser.add_argument("--limit", type=int, default=200)
    doc_nodes_parser.add_argument("--json", action="store_true")

    create_child_parser = subparsers.add_parser(
        "create-child",
        help="Build or execute one child-node creation against the live Mubu API.",
    )
    create_child_parser.add_argument("doc_ref")
    create_child_parser.add_argument("--text", required=True, help="New child plain text.")
    create_child_parser.add_argument("--note", default=None, help="Optional plain-text note for the new child.")
    create_child_parser.add_argument("--parent-node-id", default=None, help="Target parent node by id.")
    create_child_parser.add_argument("--parent-match-text", default=None, help="Target parent node by exact current plain text.")
    create_child_parser.add_argument("--parent-field", choices=["text", "note"], default="text")
    create_child_parser.add_argument("--index", type=int, default=None, help="Insert position within the parent children list.")
    create_child_parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    create_child_parser.add_argument("--log-root", type=Path, default=DEFAULT_LOG_ROOT)
    create_child_parser.add_argument("--api-host", default=DEFAULT_API_HOST)
    create_child_parser.add_argument("--execute", action="store_true", help="Actually POST the CHANGE event.")
    create_child_parser.add_argument("--json", action="store_true")

    delete_node_parser = subparsers.add_parser(
        "delete-node",
        help="Build or execute one node deletion against the live Mubu API.",
    )
    delete_node_parser.add_argument("doc_ref")
    delete_node_parser.add_argument("--node-id", default=None, help="Target one node by id.")
    delete_node_parser.add_argument("--match-text", default=None, help="Target one node by exact current plain text.")
    delete_node_parser.add_argument("--field", choices=["text", "note"], default="text")
    delete_node_parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    delete_node_parser.add_argument("--log-root", type=Path, default=DEFAULT_LOG_ROOT)
    delete_node_parser.add_argument("--api-host", default=DEFAULT_API_HOST)
    delete_node_parser.add_argument("--execute", action="store_true", help="Actually POST the CHANGE event.")
    delete_node_parser.add_argument("--json", action="store_true")

    update_text_parser = subparsers.add_parser("update-text", help="Build or execute one text update against the live Mubu API.")
    update_text_parser.add_argument("doc_ref")
    update_text_parser.add_argument("--text", required=True, help="Replacement plain text.")
    update_text_parser.add_argument("--node-id", default=None, help="Target one node by id.")
    update_text_parser.add_argument("--match-text", default=None, help="Target one node by exact current plain text.")
    update_text_parser.add_argument("--field", choices=["text", "note"], default="text")
    update_text_parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    update_text_parser.add_argument("--log-root", type=Path, default=DEFAULT_LOG_ROOT)
    update_text_parser.add_argument("--api-host", default=DEFAULT_API_HOST)
    update_text_parser.add_argument("--execute", action="store_true", help="Actually POST the CHANGE event.")
    update_text_parser.add_argument("--json", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "docs":
        documents = load_latest_backups(args.root)
        payload = [
            {
                "doc_id": item["doc_id"],
                "title": item["title"],
                "backup_file": item["backup_file"],
                "modified_at": item["modified_at"],
            }
            for item in documents[: args.limit]
        ]
        dump_output(payload, args.json)
        return 0

    if args.command == "show":
        documents = load_latest_backups(args.root)
        metas = load_document_metas(DEFAULT_STORAGE_ROOT)
        folders = load_folders(DEFAULT_STORAGE_ROOT)
        meta = document_meta_by_id(metas, folders, args.doc_id)
        payload = show_document(
            documents,
            args.doc_id,
            max_depth=args.max_depth,
            title_override=meta.get("title") if meta else None,
            folder_path=meta.get("folder_path") if meta else None,
            doc_path=meta.get("doc_path") if meta else None,
        )
        if payload is None:
            parser.error(f"document not found: {args.doc_id}")
        dump_output(payload, args.json)
        return 0

    if args.command == "search":
        documents = load_latest_backups(args.root)
        payload = search_documents(documents, args.query, limit=args.limit)
        dump_output(payload, args.json)
        return 0

    if args.command == "changes":
        payload = load_change_events(args.log_root, doc_id=args.doc_id, limit=args.limit)
        dump_output(payload, args.json)
        return 0

    if args.command == "folders":
        folders = load_folders(args.storage_root)
        _, folder_paths = build_folder_indexes(folders)
        payload = []
        for folder in folders:
            if args.query and args.query.lower() not in (folder.get("name") or "").lower():
                continue
            payload.append({**folder, "path": folder_paths.get(folder["folder_id"], "")})
        payload.sort(key=lambda item: item.get("updated_at") or 0, reverse=True)
        dump_output(payload[: args.limit], args.json)
        return 0

    if args.command == "folder-docs":
        metas = load_document_metas(args.storage_root)
        folders = load_folders(args.storage_root)
        _, folder_paths = build_folder_indexes(folders)
        payload = [
            meta
            for meta in dedupe_document_metas_by_logical_path(metas, folder_paths)
            if meta.get("folder_id") == args.folder_id
        ]
        payload.sort(key=document_meta_sort_key, reverse=True)
        dump_output(payload[: args.limit], args.json)
        return 0

    if args.command == "path-docs":
        metas = load_document_metas(args.storage_root)
        folders = load_folders(args.storage_root)
        payload, folder, ambiguous = folder_documents(metas, folders, args.folder_ref)
        if folder is None:
            if ambiguous:
                parser.error(ambiguous_error_message("folder", args.folder_ref, ambiguous, "path"))
            parser.error(f"folder not found: {args.folder_ref}")
        dump_output(
            {
                "folder": folder,
                "documents": payload[: args.limit],
            },
            args.json,
        )
        return 0

    if args.command == "recent":
        payload = recent_documents(
            load_latest_backups(args.root),
            load_document_metas(args.storage_root),
            load_folders(args.storage_root),
            log_root=args.log_root,
            limit=args.limit,
        )
        dump_output(payload, args.json)
        return 0

    if args.command == "links":
        backups = load_latest_backups(args.root)
        metas = load_document_metas(args.storage_root)
        title_lookup = {meta["doc_id"]: meta.get("title") for meta in metas if meta.get("doc_id")}
        for backup in backups:
            title_lookup.setdefault(backup["doc_id"], backup.get("title"))
        payload = document_links(backups, args.doc_id, title_lookup=title_lookup)
        dump_output(payload, args.json)
        return 0

    if args.command == "daily":
        folders = load_folders(args.storage_root)
        metas = load_document_metas(args.storage_root)
        _, folder_paths = build_folder_indexes(folders)
        logical_metas = dedupe_document_metas_by_logical_path(metas, folder_paths)
        docs_by_folder: dict[str, list[dict[str, Any]]] = {}
        for meta in logical_metas:
            folder_id = meta.get("folder_id")
            if isinstance(folder_id, str):
                docs_by_folder.setdefault(folder_id, []).append(meta)
        if args.query:
            query = normalized_lookup_key(args.query)
            matched_folders = [
                folder
                for folder in folders
                if query in normalized_lookup_key(folder.get("name"))
            ]
        else:
            matched_folders = [
                folder
                for folder in folders
                if looks_like_daily_folder_name(folder.get("name"))
                or choose_current_daily_document(docs_by_folder.get(folder.get("folder_id"), []))[0] is not None
            ]
        matched_ids = {folder["folder_id"] for folder in matched_folders}
        docs = [
            meta
            for meta in logical_metas
            if meta.get("folder_id") in matched_ids
        ]
        docs.sort(key=document_meta_sort_key, reverse=True)
        payload = {
            "folders": [
                {**folder, "path": folder_paths.get(folder["folder_id"], "")}
                for folder in matched_folders
            ],
            "documents": docs[: args.limit],
        }
        dump_output(payload, args.json)
        return 0

    if args.command == "daily-current":
        metas = load_document_metas(args.storage_root)
        folders = load_folders(args.storage_root)
        try:
            folder_ref = resolve_daily_folder_ref(args.folder_ref)
        except RuntimeError as exc:
            parser.error(str(exc))
        docs, folder, ambiguous = folder_documents(metas, folders, folder_ref)
        if folder is None:
            if ambiguous:
                parser.error(ambiguous_error_message("folder", folder_ref, ambiguous, "path"))
            parser.error(f"folder not found: {folder_ref}")

        selected, candidates = choose_current_daily_document(
            docs,
            allow_non_daily_titles=args.allow_non_daily_titles,
        )
        if selected is None:
            parser.error(
                f"no current daily document found in {folder['path']}; "
                "rerun with --allow-non-daily-titles or inspect with path-docs"
            )

        payload = {
            "folder": folder,
            "selection": {
                "strategy": "latest_updated_date_titled_document"
                if not args.allow_non_daily_titles
                else "latest_updated_document_with_non_daily_fallback",
                "allow_non_daily_titles": args.allow_non_daily_titles,
                "candidate_count": len(candidates),
            },
            "document": selected,
            "candidates": candidates[: args.limit],
        }
        dump_output(payload, args.json)
        return 0

    if args.command == "daily-nodes":
        user = get_active_user(args.storage_root)
        if user is None:
            parser.error("no active user auth found in local storage")

        metas = load_document_metas(args.storage_root)
        folders = load_folders(args.storage_root)
        try:
            folder_ref = resolve_daily_folder_ref(args.folder_ref)
        except RuntimeError as exc:
            parser.error(str(exc))
        docs, folder, ambiguous = folder_documents(metas, folders, folder_ref)
        if folder is None:
            if ambiguous:
                parser.error(ambiguous_error_message("folder", folder_ref, ambiguous, "path"))
            parser.error(f"folder not found: {folder_ref}")

        selected, candidates = choose_current_daily_document(
            docs,
            allow_non_daily_titles=args.allow_non_daily_titles,
        )
        if selected is None:
            parser.error(
                f"no current daily document found in {folder['path']}; "
                "rerun with --allow-non-daily-titles or inspect with path-docs"
            )

        remote_doc = fetch_document_remote(selected["doc_id"], user, api_host=args.api_host)
        definition_raw = remote_doc.get("definition")
        if not isinstance(definition_raw, str):
            parser.error(f"document definition missing for: {selected['doc_id']}")
        definition = json.loads(definition_raw)
        nodes = list_document_nodes(
            definition,
            query=args.query,
            max_depth=args.max_depth,
        )
        payload = {
            "folder": folder,
            "selection": {
                "strategy": "latest_updated_date_titled_document"
                if not args.allow_non_daily_titles
                else "latest_updated_document_with_non_daily_fallback",
                "allow_non_daily_titles": args.allow_non_daily_titles,
                "candidate_count": len(candidates),
            },
            "document": {
                **selected,
                "base_version": remote_doc.get("baseVersion"),
            },
            "filters": {
                "query": args.query,
                "max_depth": args.max_depth,
                "limit": args.limit,
            },
            "total_matches": len(nodes),
            "nodes": nodes[: args.limit],
        }
        dump_output(payload, args.json)
        return 0

    if args.command == "open-path":
        documents = load_latest_backups(args.root)
        metas = load_document_metas(args.storage_root)
        folders = load_folders(args.storage_root)
        payload, ambiguous = show_document_by_reference(
            documents,
            metas,
            folders,
            args.doc_ref,
            max_depth=args.max_depth,
        )
        if payload is None:
            if ambiguous:
                parser.error(ambiguous_error_message("document", args.doc_ref, ambiguous, "doc_path"))
            parser.error(f"document not found: {args.doc_ref}")
        dump_output(payload, args.json)
        return 0

    if args.command == "doc-nodes":
        user = get_active_user(args.storage_root)
        if user is None:
            parser.error("no active user auth found in local storage")

        metas = load_document_metas(args.storage_root)
        folders = load_folders(args.storage_root)
        meta, ambiguous = resolve_document_reference(metas, folders, args.doc_ref)
        if meta is None:
            if ambiguous:
                parser.error(ambiguous_error_message("document", args.doc_ref, ambiguous, "doc_path"))
            parser.error(f"document not found: {args.doc_ref}")

        remote_doc = fetch_document_remote(meta["doc_id"], user, api_host=args.api_host)
        definition_raw = remote_doc.get("definition")
        if not isinstance(definition_raw, str):
            parser.error(f"document definition missing for: {meta['doc_id']}")
        definition = json.loads(definition_raw)

        nodes = list_document_nodes(
            definition,
            query=args.query,
            max_depth=args.max_depth,
        )
        payload = {
            "document": {
                "doc_id": meta["doc_id"],
                "title": meta.get("title"),
                "doc_path": meta.get("doc_path"),
                "base_version": remote_doc.get("baseVersion"),
            },
            "filters": {
                "query": args.query,
                "max_depth": args.max_depth,
                "limit": args.limit,
            },
            "total_matches": len(nodes),
            "nodes": nodes[: args.limit],
        }
        dump_output(payload, args.json)
        return 0

    if args.command == "create-child":
        if not args.parent_node_id and not args.parent_match_text:
            parser.error("create-child requires --parent-node-id or --parent-match-text")

        user = get_active_user(args.storage_root)
        if user is None:
            parser.error("no active user auth found in local storage")

        metas = load_document_metas(args.storage_root)
        folders = load_folders(args.storage_root)
        meta, ambiguous = resolve_document_reference(metas, folders, args.doc_ref)
        if meta is None:
            if ambiguous:
                parser.error(ambiguous_error_message("document", args.doc_ref, ambiguous, "doc_path"))
            parser.error(f"document not found: {args.doc_ref}")

        events = load_change_events(args.log_root, doc_id=meta["doc_id"], limit=None)
        member_context = resolve_mutation_member_context(events, meta["doc_id"], execute=args.execute)
        if member_context is None:
            parser.error(f"no member context found in sync logs for document: {meta['doc_id']}")

        remote_doc = fetch_document_remote(meta["doc_id"], user, api_host=args.api_host)
        definition_raw = remote_doc.get("definition")
        if not isinstance(definition_raw, str):
            parser.error(f"document definition missing for: {meta['doc_id']}")
        definition = json.loads(definition_raw)

        parent_node, parent_path, node_ambiguous = resolve_node_reference_in_data(
            definition,
            node_id=args.parent_node_id,
            match_text=args.parent_match_text,
            field=args.parent_field,
        )
        if parent_node is None or parent_path is None:
            if node_ambiguous:
                labels = [extract_plain_text(item["node"].get(args.parent_field)) for item in node_ambiguous[:5]]
                parser.error(f"ambiguous parent node reference in {meta['doc_id']}: {labels}")
            parser.error(f"parent node not found in {meta['doc_id']}")

        try:
            result = perform_create_child(
                user=user,
                doc_id=meta["doc_id"],
                member_id=member_context.get("member_id"),
                version=remote_doc.get("baseVersion", 0),
                parent_node=parent_node,
                parent_path=parent_path,
                text=args.text,
                note=args.note,
                index=args.index,
                execute=args.execute,
                api_host=args.api_host,
            )
        except ValueError as exc:
            parser.error(str(exc))

        created = result["request"]["data"]["events"][0]["created"][0]
        created_node = created["node"]
        payload = {
            "execute": args.execute,
            "document": {
                "doc_id": meta["doc_id"],
                "title": meta.get("title"),
                "doc_path": meta.get("doc_path"),
                "base_version": remote_doc.get("baseVersion"),
            },
            "member_context": member_context,
            "target_parent": {
                "node_id": parent_node.get("id"),
                "field": args.parent_field,
                "path": list(parent_path),
                "api_path": node_path_to_api_path(parent_path),
                "current_text": extract_plain_text(parent_node.get(args.parent_field)),
                "existing_child_count": len(parent_node.get("children") or []),
            },
            "new_child": {
                "node_id": created_node.get("id"),
                "index": created.get("index"),
                "path": created.get("path"),
                "text": args.text,
                "note": args.note,
            },
            "request": result["request"],
        }
        if member_context.get("member_id") is None:
            payload["warning"] = "dry-run request uses a placeholder member context because no recent sync log entry was found"

        if args.execute:
            payload["response"] = result["response"]
            refreshed = fetch_document_remote(meta["doc_id"], user, api_host=args.api_host)
            refreshed_definition = json.loads(refreshed.get("definition") or "{}")
            refreshed_node, _, _ = resolve_node_reference_in_data(
                refreshed_definition,
                node_id=created_node.get("id"),
            )
            payload["verification"] = {
                "base_version_after": refreshed.get("baseVersion"),
                "created_node_present": refreshed_node is not None,
                "node_text_after": extract_plain_text((refreshed_node or {}).get("text")),
                "node_note_after": extract_plain_text((refreshed_node or {}).get("note")),
            }

        dump_output(payload, args.json)
        return 0

    if args.command == "delete-node":
        if not args.node_id and not args.match_text:
            parser.error("delete-node requires --node-id or --match-text")

        user = get_active_user(args.storage_root)
        if user is None:
            parser.error("no active user auth found in local storage")

        metas = load_document_metas(args.storage_root)
        folders = load_folders(args.storage_root)
        meta, ambiguous = resolve_document_reference(metas, folders, args.doc_ref)
        if meta is None:
            if ambiguous:
                parser.error(ambiguous_error_message("document", args.doc_ref, ambiguous, "doc_path"))
            parser.error(f"document not found: {args.doc_ref}")

        events = load_change_events(args.log_root, doc_id=meta["doc_id"], limit=None)
        member_context = resolve_mutation_member_context(events, meta["doc_id"], execute=args.execute)
        if member_context is None:
            parser.error(f"no member context found in sync logs for document: {meta['doc_id']}")

        remote_doc = fetch_document_remote(meta["doc_id"], user, api_host=args.api_host)
        definition_raw = remote_doc.get("definition")
        if not isinstance(definition_raw, str):
            parser.error(f"document definition missing for: {meta['doc_id']}")
        definition = json.loads(definition_raw)

        node, path, node_ambiguous = resolve_node_reference_in_data(
            definition,
            node_id=args.node_id,
            match_text=args.match_text,
            field=args.field,
        )
        if node is None or path is None:
            if node_ambiguous:
                labels = [extract_plain_text(item["node"].get(args.field)) for item in node_ambiguous[:5]]
                parser.error(f"ambiguous node reference in {meta['doc_id']}: {labels}")
            parser.error(f"node not found in {meta['doc_id']}")

        try:
            parent_node, parent_path, index = parent_context_for_path(definition, path)
            result = perform_delete_node(
                user=user,
                doc_id=meta["doc_id"],
                member_id=member_context.get("member_id"),
                version=remote_doc.get("baseVersion", 0),
                node=node,
                path=path,
                parent_node=parent_node,
                execute=args.execute,
                api_host=args.api_host,
            )
        except ValueError as exc:
            parser.error(str(exc))

        deleted = result["request"]["data"]["events"][0]["deleted"][0]
        payload = {
            "execute": args.execute,
            "document": {
                "doc_id": meta["doc_id"],
                "title": meta.get("title"),
                "doc_path": meta.get("doc_path"),
                "base_version": remote_doc.get("baseVersion"),
            },
            "member_context": member_context,
            "target_node": {
                "node_id": node.get("id"),
                "field": args.field,
                "path": list(path),
                "api_path": node_path_to_api_path(path),
                "parent_node_id": deleted.get("parentId"),
                "parent_path": list(parent_path) if parent_path else None,
                "index": index,
                "current_text": extract_plain_text(node.get(args.field)),
                "child_count": len(node.get("children") or []),
            },
            "request": result["request"],
        }
        if member_context.get("member_id") is None:
            payload["warning"] = "dry-run request uses a placeholder member context because no recent sync log entry was found"

        if args.execute:
            payload["response"] = result["response"]
            refreshed = fetch_document_remote(meta["doc_id"], user, api_host=args.api_host)
            refreshed_definition = json.loads(refreshed.get("definition") or "{}")
            refreshed_node, _, _ = resolve_node_reference_in_data(
                refreshed_definition,
                node_id=node.get("id"),
                field=args.field,
            )
            payload["verification"] = {
                "base_version_after": refreshed.get("baseVersion"),
                "node_deleted": refreshed_node is None,
            }

        dump_output(payload, args.json)
        return 0

    if args.command == "update-text":
        if not args.node_id and not args.match_text:
            parser.error("update-text requires --node-id or --match-text")

        user = get_active_user(args.storage_root)
        if user is None:
            parser.error("no active user auth found in local storage")

        metas = load_document_metas(args.storage_root)
        folders = load_folders(args.storage_root)
        meta, ambiguous = resolve_document_reference(metas, folders, args.doc_ref)
        if meta is None:
            if ambiguous:
                parser.error(ambiguous_error_message("document", args.doc_ref, ambiguous, "doc_path"))
            parser.error(f"document not found: {args.doc_ref}")

        events = load_change_events(args.log_root, doc_id=meta["doc_id"], limit=None)
        member_context = resolve_mutation_member_context(events, meta["doc_id"], execute=args.execute)
        if member_context is None:
            parser.error(f"no member context found in sync logs for document: {meta['doc_id']}")

        remote_doc = fetch_document_remote(meta["doc_id"], user, api_host=args.api_host)
        definition_raw = remote_doc.get("definition")
        if not isinstance(definition_raw, str):
            parser.error(f"document definition missing for: {meta['doc_id']}")
        definition = json.loads(definition_raw)

        node, path, node_ambiguous = resolve_node_reference_in_data(
            definition,
            node_id=args.node_id,
            match_text=args.match_text,
            field=args.field,
        )
        if node is None or path is None:
            if node_ambiguous:
                labels = [extract_plain_text(item["node"].get(args.field)) for item in node_ambiguous[:5]]
                parser.error(f"ambiguous node reference in {meta['doc_id']}: {labels}")
            parser.error(f"node not found in {meta['doc_id']}")

        result = perform_text_update(
            user=user,
            doc_id=meta["doc_id"],
            member_id=member_context.get("member_id"),
            version=remote_doc.get("baseVersion", 0),
            node=node,
            path=path,
            new_text=args.text,
            field=args.field,
            execute=args.execute,
            api_host=args.api_host,
        )

        payload = {
            "execute": args.execute,
            "document": {
                "doc_id": meta["doc_id"],
                "title": meta.get("title"),
                "doc_path": meta.get("doc_path"),
                "base_version": remote_doc.get("baseVersion"),
            },
            "member_context": member_context,
            "target_node": {
                "node_id": node.get("id"),
                "field": args.field,
                "path": list(path),
                "current_text": extract_plain_text(node.get(args.field)),
                "new_text": args.text,
            },
            "request": result["request"],
        }
        if member_context.get("member_id") is None:
            payload["warning"] = "dry-run request uses a placeholder member context because no recent sync log entry was found"

        if args.execute:
            payload["response"] = result["response"]
            refreshed = fetch_document_remote(meta["doc_id"], user, api_host=args.api_host)
            refreshed_definition = json.loads(refreshed.get("definition") or "{}")
            refreshed_node, _, _ = resolve_node_reference_in_data(
                refreshed_definition,
                node_id=node.get("id"),
                field=args.field,
            )
            payload["verification"] = {
                "base_version_after": refreshed.get("baseVersion"),
                "node_text_after": extract_plain_text((refreshed_node or {}).get(args.field)),
                "matches_requested_text": extract_plain_text((refreshed_node or {}).get(args.field)) == args.text,
            }

        dump_output(payload, args.json)
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
