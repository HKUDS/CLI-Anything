from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from cli_anything.zotero.core.discovery import RuntimeContext
from cli_anything.zotero.utils import zotero_http, zotero_sqlite


_TREE_VIEW_ID_RE = re.compile(r"^[LC]\d+$")
_PDF_MAGIC = b"%PDF-"
_ATTACHMENT_RESULT_CREATED = "created"
_ATTACHMENT_RESULT_FAILED = "failed"
_ATTACHMENT_RESULT_SKIPPED = "skipped_duplicate"


def _require_connector(runtime: RuntimeContext) -> None:
    if not runtime.connector_available:
        raise RuntimeError(f"Zotero connector is not available: {runtime.connector_message}")


def _read_text_file(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="replace")


def _read_json_items(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON import file: {path}: {exc}") from exc
    if isinstance(payload, dict):
        payload = payload.get("items")
    if not isinstance(payload, list):
        raise RuntimeError("JSON import expects an array of official Zotero connector item objects")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise RuntimeError(f"JSON import item {index} is not an object")
        copied = dict(item)
        copied.setdefault("id", f"cli-anything-zotero-{index}")
        normalized.append(copied)
    return normalized


def _read_json_payload(path: Path, *, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON {label}: {path}: {exc}") from exc


def _default_user_library_target(runtime: RuntimeContext) -> str:
    sqlite_path = runtime.environment.sqlite_path
    if sqlite_path.exists():
        library_id = zotero_sqlite.default_library_id(sqlite_path)
        if library_id is not None:
            return f"L{library_id}"
    return "L1"


def _session_library_id(session: dict[str, Any] | None) -> int | None:
    session = session or {}
    current_library = session.get("current_library")
    if current_library is None:
        return None
    return zotero_sqlite.normalize_library_ref(current_library)


def _resolve_target(runtime: RuntimeContext, collection_ref: str | None, session: dict[str, Any] | None = None) -> dict[str, Any]:
    session = session or {}
    session_library_id = _session_library_id(session)
    if collection_ref:
        if _TREE_VIEW_ID_RE.match(collection_ref):
            kind = "library" if collection_ref.startswith("L") else "collection"
            return {"treeViewID": collection_ref, "source": "explicit", "kind": kind}
        collection = zotero_sqlite.resolve_collection(
            runtime.environment.sqlite_path,
            collection_ref,
            library_id=session_library_id,
        )
        if not collection:
            raise RuntimeError(f"Collection not found: {collection_ref}")
        return {
            "treeViewID": f"C{collection['collectionID']}",
            "source": "explicit",
            "kind": "collection",
            "collectionID": collection["collectionID"],
            "collectionKey": collection["key"],
            "collectionName": collection["collectionName"],
            "libraryID": collection["libraryID"],
        }

    current_collection = session.get("current_collection")
    if current_collection:
        if _TREE_VIEW_ID_RE.match(str(current_collection)):
            kind = "library" if str(current_collection).startswith("L") else "collection"
            return {"treeViewID": str(current_collection), "source": "session", "kind": kind}
        collection = zotero_sqlite.resolve_collection(
            runtime.environment.sqlite_path,
            current_collection,
            library_id=session_library_id,
        )
        if collection:
            return {
                "treeViewID": f"C{collection['collectionID']}",
                "source": "session",
                "kind": "collection",
                "collectionID": collection["collectionID"],
                "collectionKey": collection["key"],
                "collectionName": collection["collectionName"],
                "libraryID": collection["libraryID"],
            }

    if runtime.connector_available:
        selected = zotero_http.get_selected_collection(runtime.environment.port)
        if selected.get("id") is not None:
            return {
                "treeViewID": f"C{selected['id']}",
                "source": "selected",
                "kind": "collection",
                "collectionID": selected["id"],
                "collectionName": selected.get("name"),
                "libraryID": selected.get("libraryID"),
                "libraryName": selected.get("libraryName"),
            }
        return {
            "treeViewID": f"L{selected['libraryID']}",
            "source": "selected",
            "kind": "library",
            "libraryID": selected.get("libraryID"),
            "libraryName": selected.get("libraryName"),
        }

    return {
        "treeViewID": _default_user_library_target(runtime),
        "source": "user_library",
        "kind": "library",
    }


def _normalize_tags(tags: list[str] | tuple[str, ...]) -> list[str]:
    return [tag.strip() for tag in tags if tag and tag.strip()]


def _session_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _normalize_attachment_int(value: Any, *, name: str, minimum: int) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Attachment `{name}` must be an integer") from exc
    if normalized < minimum:
        comparator = "greater than or equal to" if minimum == 0 else f"at least {minimum}"
        raise RuntimeError(f"Attachment `{name}` must be {comparator}")
    return normalized


def _normalize_attachment_descriptor(
    raw: Any,
    *,
    index_label: str,
    attachment_label: str,
    default_delay_ms: int,
    default_timeout: int,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RuntimeError(f"{index_label} {attachment_label} must be an object")
    has_path = "path" in raw and raw.get("path") not in (None, "")
    has_url = "url" in raw and raw.get("url") not in (None, "")
    if has_path == has_url:
        raise RuntimeError(f"{index_label} {attachment_label} must include exactly one of `path` or `url`")
    title = str(raw.get("title") or "PDF").strip() or "PDF"
    delay_ms = _normalize_attachment_int(raw.get("delay_ms", default_delay_ms), name="delay_ms", minimum=0)
    timeout = _normalize_attachment_int(raw.get("timeout", default_timeout), name="timeout", minimum=1)
    if has_path:
        source = str(raw["path"]).strip()
        if not source:
            raise RuntimeError(f"{index_label} {attachment_label} path must not be empty")
        return {
            "source_type": "file",
            "source": source,
            "title": title,
            "delay_ms": delay_ms,
            "timeout": timeout,
        }
    source = str(raw["url"]).strip()
    if not source:
        raise RuntimeError(f"{index_label} {attachment_label} url must not be empty")
    return {
        "source_type": "url",
        "source": source,
        "title": title,
        "delay_ms": delay_ms,
        "timeout": timeout,
    }


def _extract_inline_attachment_plans(
    items: list[dict[str, Any]],
    *,
    default_delay_ms: int,
    default_timeout: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    stripped_items: list[dict[str, Any]] = []
    plans: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        copied = dict(item)
        raw_attachments = copied.pop("attachments", [])
        if raw_attachments in (None, []):
            stripped_items.append(copied)
            continue
        if not isinstance(raw_attachments, list):
            raise RuntimeError(f"JSON import item {index + 1} attachments must be an array")
        normalized = [
            _normalize_attachment_descriptor(
                descriptor,
                index_label=f"JSON import item {index + 1}",
                attachment_label=f"attachment {attachment_index + 1}",
                default_delay_ms=default_delay_ms,
                default_timeout=default_timeout,
            )
            for attachment_index, descriptor in enumerate(raw_attachments)
        ]
        plans.append({"index": index, "attachments": normalized})
        stripped_items.append(copied)
    return stripped_items, plans


def _read_attachment_manifest(
    path: Path,
    *,
    default_delay_ms: int,
    default_timeout: int,
) -> list[dict[str, Any]]:
    payload = _read_json_payload(path, label="attachment manifest")
    if not isinstance(payload, list):
        raise RuntimeError("Attachment manifest expects an array of {index, attachments} objects")
    manifest: list[dict[str, Any]] = []
    seen_indexes: set[int] = set()
    for entry_index, entry in enumerate(payload, start=1):
        label = f"manifest entry {entry_index}"
        if not isinstance(entry, dict):
            raise RuntimeError(f"{label} must be an object")
        if "index" not in entry:
            raise RuntimeError(f"{label} is missing required `index`")
        index = _normalize_attachment_int(entry["index"], name="index", minimum=0)
        if index in seen_indexes:
            raise RuntimeError(f"{label} reuses import index {index}")
        seen_indexes.add(index)
        attachments = entry.get("attachments")
        if not isinstance(attachments, list):
            raise RuntimeError(f"{label} attachments must be an array")
        normalized = [
            _normalize_attachment_descriptor(
                descriptor,
                index_label=label,
                attachment_label=f"attachment {attachment_index + 1}",
                default_delay_ms=default_delay_ms,
                default_timeout=default_timeout,
            )
            for attachment_index, descriptor in enumerate(attachments)
        ]
        expected_title = entry.get("expected_title")
        if expected_title is not None and not isinstance(expected_title, str):
            raise RuntimeError(f"{label} expected_title must be a string")
        manifest.append(
            {
                "index": index,
                "expected_title": expected_title,
                "attachments": normalized,
            }
        )
    return manifest


def _item_title(item: dict[str, Any]) -> str | None:
    for field in ("title", "bookTitle", "publicationTitle"):
        value = item.get(field)
        if value:
            return str(value)
    return None


def _normalize_url_for_dedupe(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    normalized_path = parsed.path or "/"
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), normalized_path, parsed.query, ""))


def _attachment_result(
    *,
    item_index: int,
    parent_connector_id: Any,
    descriptor: dict[str, Any],
    status: str,
    error: str | None = None,
) -> dict[str, Any]:
    payload = {
        "item_index": item_index,
        "parent_connector_id": parent_connector_id,
        "source_type": descriptor["source_type"],
        "source": descriptor["source"],
        "title": descriptor["title"],
        "status": status,
    }
    if error is not None:
        payload["error"] = error
    return payload


def _attachment_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "planned_count": len(results),
        "created_count": sum(1 for result in results if result["status"] == _ATTACHMENT_RESULT_CREATED),
        "failed_count": sum(1 for result in results if result["status"] == _ATTACHMENT_RESULT_FAILED),
        "skipped_count": sum(1 for result in results if result["status"] == _ATTACHMENT_RESULT_SKIPPED),
    }


def _ensure_pdf_bytes(content: bytes, *, source: str) -> None:
    if not content.startswith(_PDF_MAGIC):
        raise RuntimeError(f"Attachment source is not a PDF: {source}")


def _read_local_pdf(path_text: str) -> tuple[bytes, str]:
    path = Path(path_text).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Attachment file not found: {path}")
    resolved = path.resolve()
    content = resolved.read_bytes()
    _ensure_pdf_bytes(content, source=str(resolved))
    return content, resolved.as_uri()


def _download_remote_pdf(url: str, *, delay_ms: int, timeout: int) -> bytes:
    if delay_ms:
        time.sleep(delay_ms / 1000)
    request = urllib.request.Request(url, headers={"Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", response.getcode())
            if int(status) != 200:
                raise RuntimeError(f"Attachment download returned HTTP {status}: {url}")
            content = response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Attachment download returned HTTP {exc.code}: {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Attachment download failed for {url}: {exc.reason}") from exc
    _ensure_pdf_bytes(content, source=url)
    return content


def _perform_attachment_upload(
    runtime: RuntimeContext,
    *,
    session_id: str,
    connector_items: list[dict[str, Any]],
    plans: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    seen_by_item: dict[str, dict[str, set[str]]] = {}
    for plan in plans:
        item_index = int(plan["index"])
        attachments = list(plan.get("attachments") or [])
        imported_item = connector_items[item_index] if 0 <= item_index < len(connector_items) else None
        expected_title = plan.get("expected_title")
        if imported_item is None:
            message = f"Import returned no item at index {item_index}"
            results.extend(
                _attachment_result(
                    item_index=item_index,
                    parent_connector_id=None,
                    descriptor=descriptor,
                    status=_ATTACHMENT_RESULT_FAILED,
                    error=message,
                )
                for descriptor in attachments
            )
            continue
        imported_title = _item_title(imported_item)
        if expected_title is not None and imported_title != expected_title:
            message = (
                f"Imported item title mismatch at index {item_index}: "
                f"expected {expected_title!r}, got {imported_title!r}"
            )
            results.extend(
                _attachment_result(
                    item_index=item_index,
                    parent_connector_id=imported_item.get("id"),
                    descriptor=descriptor,
                    status=_ATTACHMENT_RESULT_FAILED,
                    error=message,
                )
                for descriptor in attachments
            )
            continue
        parent_connector_id = imported_item.get("id")
        if not parent_connector_id:
            message = f"Imported item at index {item_index} did not include a connector id"
            results.extend(
                _attachment_result(
                    item_index=item_index,
                    parent_connector_id=None,
                    descriptor=descriptor,
                    status=_ATTACHMENT_RESULT_FAILED,
                    error=message,
                )
                for descriptor in attachments
            )
            continue

        dedupe_state = seen_by_item.setdefault(
            str(parent_connector_id),
            {"paths": set(), "urls": set(), "hashes": set()},
        )
        for descriptor in attachments:
            try:
                if descriptor["source_type"] == "file":
                    canonical_path = str(Path(descriptor["source"]).expanduser().resolve())
                    if canonical_path in dedupe_state["paths"]:
                        results.append(
                            _attachment_result(
                                item_index=item_index,
                                parent_connector_id=parent_connector_id,
                                descriptor=descriptor,
                                status=_ATTACHMENT_RESULT_SKIPPED,
                            )
                        )
                        continue
                    content, metadata_url = _read_local_pdf(descriptor["source"])
                else:
                    normalized_url = _normalize_url_for_dedupe(descriptor["source"])
                    if normalized_url in dedupe_state["urls"]:
                        results.append(
                            _attachment_result(
                                item_index=item_index,
                                parent_connector_id=parent_connector_id,
                                descriptor=descriptor,
                                status=_ATTACHMENT_RESULT_SKIPPED,
                            )
                        )
                        continue
                    content = _download_remote_pdf(
                        descriptor["source"],
                        delay_ms=int(descriptor["delay_ms"]),
                        timeout=int(descriptor["timeout"]),
                    )
                    metadata_url = descriptor["source"]

                content_hash = hashlib.sha256(content).hexdigest()
                if content_hash in dedupe_state["hashes"]:
                    results.append(
                        _attachment_result(
                            item_index=item_index,
                            parent_connector_id=parent_connector_id,
                            descriptor=descriptor,
                            status=_ATTACHMENT_RESULT_SKIPPED,
                        )
                    )
                    continue

                zotero_http.connector_save_attachment(
                    runtime.environment.port,
                    session_id=session_id,
                    parent_item_id=parent_connector_id,
                    title=descriptor["title"],
                    url=metadata_url,
                    content=content,
                    timeout=int(descriptor["timeout"]),
                )
                dedupe_state["hashes"].add(content_hash)
                if descriptor["source_type"] == "file":
                    dedupe_state["paths"].add(canonical_path)
                else:
                    dedupe_state["urls"].add(normalized_url)
                results.append(
                    _attachment_result(
                        item_index=item_index,
                        parent_connector_id=parent_connector_id,
                        descriptor=descriptor,
                        status=_ATTACHMENT_RESULT_CREATED,
                    )
                )
            except Exception as exc:
                results.append(
                    _attachment_result(
                        item_index=item_index,
                        parent_connector_id=parent_connector_id,
                        descriptor=descriptor,
                        status=_ATTACHMENT_RESULT_FAILED,
                        error=str(exc),
                    )
                )
    return _attachment_summary(results), results


def enable_local_api(
    runtime: RuntimeContext,
    *,
    launch: bool = False,
    wait_timeout: int = 30,
) -> dict[str, Any]:
    profile_dir = runtime.environment.profile_dir
    if profile_dir is None:
        raise RuntimeError("Active Zotero profile could not be resolved")
    before = runtime.environment.local_api_enabled_configured
    written_path = runtime.environment.profile_dir / "user.js"
    from cli_anything.zotero.utils import zotero_paths  # local import to avoid cycle
    zotero_paths.ensure_local_api_enabled(profile_dir)
    payload = {
        "profile_dir": str(profile_dir),
        "user_js_path": str(written_path),
        "already_enabled": before,
        "enabled": True,
        "launched": False,
        "connector_ready": runtime.connector_available,
        "local_api_ready": runtime.local_api_available,
    }
    if launch:
        from cli_anything.zotero.core import discovery  # local import to avoid cycle
        refreshed = discovery.build_runtime_context(
            backend=runtime.backend,
            data_dir=str(runtime.environment.data_dir),
            profile_dir=str(profile_dir),
            executable=str(runtime.environment.executable) if runtime.environment.executable else None,
        )
        launch_payload = discovery.launch_zotero(refreshed, wait_timeout=wait_timeout)
        payload.update(
            {
                "launched": True,
                "launch": launch_payload,
                "connector_ready": launch_payload["connector_ready"],
                "local_api_ready": launch_payload["local_api_ready"],
            }
        )
    return payload


def import_file(
    runtime: RuntimeContext,
    path: str | Path,
    *,
    collection_ref: str | None = None,
    tags: list[str] | tuple[str, ...] = (),
    session: dict[str, Any] | None = None,
    attachments_manifest: str | Path | None = None,
    attachment_delay_ms: int = 0,
    attachment_timeout: int = 60,
) -> dict[str, Any]:
    _require_connector(runtime)
    source_path = Path(path).expanduser()
    if not source_path.exists():
        raise FileNotFoundError(f"Import file not found: {source_path}")
    content = _read_text_file(source_path)
    manifest_path = Path(attachments_manifest).expanduser() if attachments_manifest is not None else None
    plans = (
        _read_attachment_manifest(
            manifest_path,
            default_delay_ms=attachment_delay_ms,
            default_timeout=attachment_timeout,
        )
        if manifest_path is not None
        else []
    )
    session_id = _session_id("import-file")
    imported = zotero_http.connector_import_text(runtime.environment.port, content, session_id=session_id)
    target = _resolve_target(runtime, collection_ref, session=session)
    normalized_tags = _normalize_tags(list(tags))
    zotero_http.connector_update_session(
        runtime.environment.port,
        session_id=session_id,
        target=target["treeViewID"],
        tags=normalized_tags,
    )
    attachment_summary, attachment_results = _perform_attachment_upload(
        runtime,
        session_id=session_id,
        connector_items=imported,
        plans=plans,
    )
    return {
        "action": "import_file",
        "path": str(source_path),
        "status": "partial_success" if attachment_summary["failed_count"] else "success",
        "sessionID": session_id,
        "target": target,
        "tags": normalized_tags,
        "imported_count": len(imported),
        "items": imported,
        "attachment_summary": attachment_summary,
        "attachment_results": attachment_results,
    }


def import_json(
    runtime: RuntimeContext,
    path: str | Path,
    *,
    collection_ref: str | None = None,
    tags: list[str] | tuple[str, ...] = (),
    session: dict[str, Any] | None = None,
    attachment_delay_ms: int = 0,
    attachment_timeout: int = 60,
) -> dict[str, Any]:
    _require_connector(runtime)
    source_path = Path(path).expanduser()
    if not source_path.exists():
        raise FileNotFoundError(f"Import JSON file not found: {source_path}")
    items = _read_json_items(source_path)
    items, plans = _extract_inline_attachment_plans(
        items,
        default_delay_ms=attachment_delay_ms,
        default_timeout=attachment_timeout,
    )
    session_id = _session_id("import-json")
    zotero_http.connector_save_items(runtime.environment.port, items, session_id=session_id)
    target = _resolve_target(runtime, collection_ref, session=session)
    normalized_tags = _normalize_tags(list(tags))
    zotero_http.connector_update_session(
        runtime.environment.port,
        session_id=session_id,
        target=target["treeViewID"],
        tags=normalized_tags,
    )
    attachment_summary, attachment_results = _perform_attachment_upload(
        runtime,
        session_id=session_id,
        connector_items=items,
        plans=plans,
    )
    return {
        "action": "import_json",
        "path": str(source_path),
        "status": "partial_success" if attachment_summary["failed_count"] else "success",
        "sessionID": session_id,
        "target": target,
        "tags": normalized_tags,
        "submitted_count": len(items),
        "items": [
            {
                "id": item.get("id"),
                "itemType": item.get("itemType"),
                "title": item.get("title") or item.get("bookTitle") or item.get("publicationTitle"),
            }
            for item in items
        ],
        "attachment_summary": attachment_summary,
        "attachment_results": attachment_results,
    }
