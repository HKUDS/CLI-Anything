from __future__ import annotations

import html
import re
import uuid
from pathlib import Path
from typing import Any

from cli_anything.zotero.core.catalog import get_item
from cli_anything.zotero.core.discovery import RuntimeContext
from cli_anything.zotero.utils import zotero_http, zotero_sqlite


def _require_connector(runtime: RuntimeContext) -> None:
    if not runtime.connector_available:
        raise RuntimeError(f"Zotero connector is not available: {runtime.connector_message}")


def get_note(runtime: RuntimeContext, ref: str | int | None, session: dict[str, Any] | None = None) -> dict[str, Any]:
    if ref is None:
        raise RuntimeError("Note reference required")
    session = session or {}
    library_id = session.get("current_library")
    note = zotero_sqlite.resolve_item(
        runtime.environment.sqlite_path,
        ref,
        library_id=zotero_sqlite.normalize_library_ref(library_id) if library_id is not None else None,
    )
    if not note:
        raise RuntimeError(f"Note not found: {ref}")
    if note["typeName"] != "note":
        raise RuntimeError(f"Item is not a note: {ref}")
    return note


def get_item_notes(runtime: RuntimeContext, ref: str | int | None, session: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    parent_item = get_item(runtime, ref, session=session)
    return zotero_sqlite.fetch_item_notes(runtime.environment.sqlite_path, parent_item["itemID"])


def _html_paragraphs(text: str) -> str:
    paragraphs = [segment.strip() for segment in text.replace("\r\n", "\n").replace("\r", "\n").split("\n\n") if segment.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]
    rendered = []
    for paragraph in paragraphs:
        escaped = html.escape(paragraph).replace("\n", "<br/>")
        rendered.append(f"<p>{escaped}</p>")
    return "".join(rendered)


def _simple_markdown_to_safe_html(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    rendered: list[str] = []
    in_list = False
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if not paragraph:
            return
        rendered.append(f"<p>{_render_markdown_inline(' '.join(paragraph))}</p>")
        paragraph = []

    def flush_list() -> None:
        nonlocal in_list
        if in_list:
            rendered.append("</ul>")
            in_list = False

    for raw_line in lines:
        line = raw_line.rstrip()
        if not line.strip():
            flush_paragraph()
            flush_list()
            continue
        if line.startswith(("- ", "* ")):
            flush_paragraph()
            if not in_list:
                rendered.append("<ul>")
                in_list = True
            rendered.append(f"<li>{_render_markdown_inline(line[2:].strip())}</li>")
            continue
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if match:
            flush_paragraph()
            flush_list()
            level = len(match.group(1))
            rendered.append(f"<h{level}>{_render_markdown_inline(match.group(2).strip())}</h{level}>")
            continue
        flush_list()
        paragraph.append(line.strip())

    flush_paragraph()
    flush_list()
    return "".join(rendered)


def _render_markdown_inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    return escaped


def _normalize_note_html(content: str, fmt: str) -> str:
    fmt = fmt.lower()
    if fmt == "html":
        return content
    if fmt == "markdown":
        return _simple_markdown_to_safe_html(content)
    if fmt == "text":
        return _html_paragraphs(content)
    raise RuntimeError(f"Unsupported note format: {fmt}")


def add_note(
    runtime: RuntimeContext,
    item_ref: str | int,
    *,
    text: str | None = None,
    file_path: str | Path | None = None,
    fmt: str = "text",
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _require_connector(runtime)
    if (text is None and file_path is None) or (text is not None and file_path is not None):
        raise RuntimeError("Provide exactly one of `text` or `file_path`")

    parent_item = get_item(runtime, item_ref, session=session)
    if parent_item["typeName"] in {"note", "attachment", "annotation"}:
        raise RuntimeError("Child notes can only be attached to top-level bibliographic items")

    selected = zotero_http.get_selected_collection(runtime.environment.port)
    selected_library_id = selected.get("libraryID")
    if selected_library_id is not None and int(selected_library_id) != int(parent_item["libraryID"]):
        raise RuntimeError(
            "note add requires Zotero to have the same library selected as the parent item. "
            "Switch the Zotero UI to that library and retry."
        )

    if file_path is not None:
        content = Path(file_path).expanduser().read_text(encoding="utf-8")
    else:
        content = text or ""

    note_html = _normalize_note_html(content, fmt)
    session_id = f"note-add-{uuid.uuid4().hex}"
    zotero_http.connector_save_items(
        runtime.environment.port,
        [
            {
                "id": session_id,
                "itemType": "note",
                "note": note_html,
                "parentItem": parent_item["key"],
            }
        ],
        session_id=session_id,
    )
    return {
        "action": "note_add",
        "sessionID": session_id,
        "parentItemKey": parent_item["key"],
        "parentItemID": parent_item["itemID"],
        "format": fmt,
        "notePreview": zotero_sqlite.note_preview(note_html),
        "selectedLibraryID": selected_library_id,
    }
