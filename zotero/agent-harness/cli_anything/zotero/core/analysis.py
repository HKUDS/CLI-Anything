from __future__ import annotations

import os
from typing import Any

from cli_anything.zotero.core import notes as notes_core
from cli_anything.zotero.core.catalog import get_item, item_attachments
from cli_anything.zotero.core.discovery import RuntimeContext
from cli_anything.zotero.core import rendering
from cli_anything.zotero.utils import openai_api


def _creator_line(item: dict[str, Any]) -> str:
    creators = item.get("creators") or []
    if not creators:
        return ""
    parts = []
    for creator in creators:
        full_name = " ".join(part for part in [creator.get("firstName"), creator.get("lastName")] if part)
        if not full_name:
            full_name = str(creator.get("creatorID", ""))
        parts.append(full_name)
    return ", ".join(parts)


def _link_payload(item: dict[str, Any]) -> dict[str, str]:
    fields = item.get("fields") or {}
    links: dict[str, str] = {}
    url = fields.get("url")
    doi = fields.get("DOI") or fields.get("doi")
    if url:
        links["url"] = str(url)
    if doi:
        links["doi"] = str(doi)
        links["doi_url"] = f"https://doi.org/{doi}"
    return links


def _prompt_context(payload: dict[str, Any]) -> str:
    item = payload["item"]
    fields = item.get("fields") or {}
    lines = [
        f"Title: {item.get('title') or ''}",
        f"Item Key: {item.get('key') or ''}",
        f"Item Type: {item.get('typeName') or ''}",
    ]
    creator_line = _creator_line(item)
    if creator_line:
        lines.append(f"Creators: {creator_line}")
    for field_name in sorted(fields):
        if field_name == "title":
            continue
        value = fields.get(field_name)
        if value not in (None, ""):
            lines.append(f"{field_name}: {value}")

    links = payload.get("links") or {}
    if links:
        lines.append("Links:")
        for key, value in links.items():
            lines.append(f"- {key}: {value}")

    attachments = payload.get("attachments") or []
    if attachments:
        lines.append("Attachments:")
        for attachment in attachments:
            lines.append(
                f"- {attachment.get('title') or attachment.get('key')}: "
                f"{attachment.get('resolvedPath') or attachment.get('path') or '<missing>'}"
            )

    notes = payload.get("notes") or []
    if notes:
        lines.append("Notes:")
        for note in notes:
            lines.append(f"- {note.get('title') or note.get('key')}: {note.get('noteText') or note.get('notePreview')}")

    exports = payload.get("exports") or {}
    if exports:
        lines.append("Exports:")
        for fmt, content in exports.items():
            lines.append(f"[{fmt}]")
            lines.append(content)

    return "\n".join(lines).strip()


def build_item_context(
    runtime: RuntimeContext,
    ref: str | int | None,
    *,
    include_notes: bool = False,
    include_bibtex: bool = False,
    include_csljson: bool = False,
    include_links: bool = False,
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item = get_item(runtime, ref, session=session)
    attachments = item_attachments(runtime, item["key"], session=session)
    notes: list[dict[str, Any]] = []
    if include_notes:
        notes = notes_core.get_item_notes(runtime, item["key"], session=session)

    exports: dict[str, str] = {}
    if include_bibtex:
        exports["bibtex"] = rendering.export_item(runtime, item["key"], "bibtex", session=session)["content"]
    if include_csljson:
        exports["csljson"] = rendering.export_item(runtime, item["key"], "csljson", session=session)["content"]

    payload = {
        "item": item,
        "attachments": attachments,
        "notes": notes,
        "exports": exports,
        "links": _link_payload(item) if include_links else {},
    }
    payload["prompt_context"] = _prompt_context(payload)
    return payload


def analyze_item(
    runtime: RuntimeContext,
    ref: str | int | None,
    *,
    question: str,
    model: str,
    include_notes: bool = False,
    include_bibtex: bool = False,
    include_csljson: bool = False,
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Use `item context` for model-independent output or configure the API key.")

    context_payload = build_item_context(
        runtime,
        ref,
        include_notes=include_notes,
        include_bibtex=include_bibtex,
        include_csljson=include_csljson,
        include_links=True,
        session=session,
    )
    input_text = (
        "Use the Zotero item context below to answer the user's question.\n\n"
        f"Question:\n{question.strip()}\n\n"
        f"Context:\n{context_payload['prompt_context']}"
    )
    response = openai_api.create_text_response(
        api_key=api_key,
        model=model,
        instructions=(
            "You are analyzing a Zotero bibliographic record. Stay grounded in the provided context. "
            "If the context is missing an answer, say so explicitly."
        ),
        input_text=input_text,
    )
    return {
        "itemKey": context_payload["item"]["key"],
        "model": model,
        "question": question,
        "answer": response["answer"],
        "responseID": response["response_id"],
        "context": context_payload,
    }
