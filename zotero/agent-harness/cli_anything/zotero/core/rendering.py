from __future__ import annotations

from typing import Any

from cli_anything.zotero.core.catalog import get_item, local_api_scope
from cli_anything.zotero.core.discovery import RuntimeContext
from cli_anything.zotero.utils import zotero_http


SUPPORTED_EXPORT_FORMATS = ("ris", "bibtex", "biblatex", "csljson", "csv", "mods", "refer")


def _require_local_api(runtime: RuntimeContext) -> None:
    if not runtime.local_api_available:
        raise RuntimeError(
            "Zotero Local API is not available. Start Zotero and enable "
            "`extensions.zotero.httpServer.localAPI.enabled` first."
        )


def _resolve_item(runtime: RuntimeContext, ref: str | int | None, session: dict[str, Any] | None = None) -> dict[str, Any]:
    item = get_item(runtime, ref, session=session)
    return item


def export_item(runtime: RuntimeContext, ref: str | int | None, fmt: str, session: dict[str, Any] | None = None) -> dict[str, Any]:
    _require_local_api(runtime)
    if fmt not in SUPPORTED_EXPORT_FORMATS:
        raise RuntimeError(f"Unsupported export format: {fmt}")
    item = _resolve_item(runtime, ref, session=session)
    key = str(item["key"])
    scope = local_api_scope(runtime, int(item["libraryID"]))
    body = zotero_http.local_api_get_text(runtime.environment.port, f"{scope}/items/{key}", params={"format": fmt})
    return {"itemKey": key, "libraryID": int(item["libraryID"]), "format": fmt, "content": body}


def citation_item(
    runtime: RuntimeContext,
    ref: str | int | None,
    *,
    style: str | None = None,
    locale: str | None = None,
    linkwrap: bool = False,
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _require_local_api(runtime)
    item = _resolve_item(runtime, ref, session=session)
    key = str(item["key"])
    params: dict[str, Any] = {"format": "json", "include": "citation"}
    if style:
        params["style"] = style
    if locale:
        params["locale"] = locale
    if linkwrap:
        params["linkwrap"] = "1"
    scope = local_api_scope(runtime, int(item["libraryID"]))
    payload = zotero_http.local_api_get_json(runtime.environment.port, f"{scope}/items/{key}", params=params)
    citation = payload.get("citation") if isinstance(payload, dict) else (payload[0].get("citation") if payload else None)
    return {
        "itemKey": key,
        "libraryID": int(item["libraryID"]),
        "style": style,
        "locale": locale,
        "linkwrap": linkwrap,
        "citation": citation,
    }


def bibliography_item(
    runtime: RuntimeContext,
    ref: str | int | None,
    *,
    style: str | None = None,
    locale: str | None = None,
    linkwrap: bool = False,
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _require_local_api(runtime)
    item = _resolve_item(runtime, ref, session=session)
    key = str(item["key"])
    params: dict[str, Any] = {"format": "json", "include": "bib"}
    if style:
        params["style"] = style
    if locale:
        params["locale"] = locale
    if linkwrap:
        params["linkwrap"] = "1"
    scope = local_api_scope(runtime, int(item["libraryID"]))
    payload = zotero_http.local_api_get_json(runtime.environment.port, f"{scope}/items/{key}", params=params)
    bibliography = payload.get("bib") if isinstance(payload, dict) else (payload[0].get("bib") if payload else None)
    return {
        "itemKey": key,
        "libraryID": int(item["libraryID"]),
        "style": style,
        "locale": locale,
        "linkwrap": linkwrap,
        "bibliography": bibliography,
    }
