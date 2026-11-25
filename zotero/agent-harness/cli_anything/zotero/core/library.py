"""Library-wide read-only reports: duplicate detection, metadata audit, snapshot export."""

from __future__ import annotations

import csv
import io
import re
from typing import Any

from cli_anything.zotero.core import catalog
from cli_anything.zotero.core.discovery import RuntimeContext
from cli_anything.zotero.utils import zotero_sqlite

# "identifier" is satisfied by a DOI or a URL.
REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "journalArticle": ("creators", "date", "identifier", "publicationTitle", "abstractNote"),
    "conferencePaper": ("creators", "date", "identifier", "proceedingsTitle", "abstractNote"),
    "preprint": ("creators", "date", "identifier", "abstractNote"),
    "book": ("creators", "date", "publisher"),
    "bookSection": ("creators", "date", "publisher", "bookTitle"),
    "thesis": ("creators", "date", "university"),
    "report": ("creators", "date", "institution"),
    "webpage": ("date", "url"),
}
DEFAULT_REQUIRED = ("creators", "date")
PUBLICATION_FIELDS = ("publicationTitle", "proceedingsTitle", "bookTitle", "websiteTitle", "repository")
CSV_COLUMNS = ("key", "itemType", "title", "creators", "date", "DOI", "url", "publication", "collections", "tags", "extra")
MIN_TITLE_LENGTH = 12  # shorter normalized titles ("Introduction") match too many unrelated items
FORMULA_PREFIXES = ("=", "+", "-", "@", chr(9), chr(13))  # spreadsheets run cells that start with these

_ARXIV = re.compile(
    r"(?:arxiv(?:\.org/(?:abs|pdf)/|:)\s*|10\.48550/arxiv\.)"
    r"(\d{4}\.\d{4,5}|[a-z-]+(?:\.[a-z]{2})?/\d{7})(?:v\d+)?",
    re.IGNORECASE,
)


def records(runtime: RuntimeContext, session: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Regular, non-trashed top-level items of the active library, with fields, creators and tags."""
    sqlite_path = catalog._require_sqlite(runtime)
    return zotero_sqlite.fetch_library_records(sqlite_path, library_id=catalog._default_library(runtime, session))


def normalize_doi(value: str) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", text)
    return text if text.startswith("10.") else ""


def arxiv_id(fields: dict[str, Any]) -> str:
    for name in ("url", "extra", "archiveID", "DOI", "publicationTitle", "repository"):
        match = _ARXIV.search(str(fields.get(name) or ""))
        if match:
            return match.group(1).lower()
    return ""


def normalize_title(title: str) -> str:
    text = re.sub(r"[\W_]+", " ", (title or "").lower()).strip()
    return text if len(text) >= MIN_TITLE_LENGTH else ""


def _summary(item: dict[str, Any]) -> dict[str, Any]:
    fields = item["fields"]
    return {"key": item["key"], "title": item["title"], "itemType": item["typeName"],
            "date": fields.get("date", ""), "DOI": fields.get("DOI", "")}


def _compatible_clusters(keys: list[str], doi_of: dict[str, str]) -> list[list[str]]:
    """Split items that share a title into clusters that never mix two different DOIs.

    Two items with different non-empty DOIs are different works (parts, editions), however alike
    their titles are. An item without a DOI joins the first cluster.
    """
    clusters: list[tuple[set[str], list[str]]] = []
    for key in keys:
        doi = doi_of[key]
        for dois, members in clusters:
            if not doi or not dois or doi in dois:
                members.append(key)
                if doi:
                    dois.add(doi)
                break
        else:
            clusters.append(({doi} if doi else set(), [key]))
    return [members for _, members in clusters]


def find_duplicates(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Group items that share a DOI, an arXiv ID or a normalized title (transitively).

    A shared title does not link items whose DOIs differ.
    """
    parent = {i["key"]: i["key"] for i in items}

    def root(k: str) -> str:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    signals: dict[tuple[str, str], list[str]] = {}
    for item in items:
        fields = item["fields"]
        for reason, value in (("doi", normalize_doi(fields.get("DOI", ""))), ("arxiv", arxiv_id(fields)),
                              ("title", normalize_title(item["title"]))):
            if value:
                signals.setdefault((reason, value), []).append(item["key"])
    doi_of = {i["key"]: normalize_doi(i["fields"].get("DOI", "")) for i in items}
    reasons: dict[str, set[str]] = {}

    def link(keys: list[str], reason: str) -> None:
        for k in keys[1:]:
            parent[root(k)] = root(keys[0])
        for k in keys:
            reasons.setdefault(k, set()).add(reason)

    for (reason, _), keys in signals.items():
        if len(keys) < 2:
            continue
        if reason == "title":
            for cluster in _compatible_clusters(keys, doi_of):
                if len(cluster) > 1:
                    link(cluster, reason)
        else:
            link(keys, reason)
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if item["key"] in reasons:
            groups.setdefault(root(item["key"]), []).append(item)
    out = [{"reasons": sorted(set().union(*(reasons[i["key"]] for i in members))),
            "items": [_summary(i) for i in members]} for members in groups.values()]
    return {"items_scanned": len(items), "group_count": len(out), "groups": out}


def _missing(item: dict[str, Any], required: tuple[str, ...]) -> list[str]:
    fields = item["fields"]
    missing = []
    for name in required:
        if name == "creators":
            ok = bool(item["creators"])
        elif name == "identifier":
            ok = bool(str(fields.get("DOI", "")).strip() or str(fields.get("url", "")).strip())
        elif name == "title":
            ok = bool((item["title"] or "").strip())
        else:
            ok = bool(str(fields.get(name, "")).strip())
        if not ok:
            missing.append(name)
    return missing


def audit_metadata(items: list[dict[str, Any]], require: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Report items missing fields. `require` overrides the per-item-type defaults for every item."""
    incomplete = []
    by_field: dict[str, int] = {}
    for item in items:
        needed = ("title",) + (require if require else REQUIRED_FIELDS.get(item["typeName"], DEFAULT_REQUIRED))
        missing = _missing(item, needed)
        if missing:
            incomplete.append({**_summary(item), "missing": missing})
            for name in missing:
                by_field[name] = by_field.get(name, 0) + 1
    return {"items_scanned": len(items), "incomplete": len(incomplete),
            "missing_by_field": dict(sorted(by_field.items(), key=lambda kv: (-kv[1], kv[0]))),
            "items": incomplete}


def _creator_name(creator: dict[str, Any]) -> str:
    last, first = creator.get("lastName") or "", creator.get("firstName") or ""
    return last if creator.get("fieldMode") == 1 or not first else f"{last}, {first}"


def snapshot(runtime: RuntimeContext, session: dict[str, Any] | None = None) -> dict[str, Any]:
    """Collections and regular items of the active library as plain JSON-friendly data."""
    library_id = catalog._default_library(runtime, session)
    collections = zotero_sqlite.fetch_collections(catalog._require_sqlite(runtime), library_id)
    names = {c["key"]: c["collectionName"] for c in collections}
    rows = []
    for item in records(runtime, session):
        fields = item["fields"]
        rows.append({
            "key": item["key"], "itemType": item["typeName"], "title": item["title"],
            "creators": [_creator_name(c) for c in item["creators"]],
            "date": fields.get("date", ""), "DOI": fields.get("DOI", ""), "url": fields.get("url", ""),
            "publication": next((fields[f] for f in PUBLICATION_FIELDS if fields.get(f)), ""),
            "collections": [names[k] for k in item["collectionKeys"] if k in names],
            "tags": [t["name"] for t in item["tags"]], "extra": fields.get("extra", ""),
        })
    return {"libraryID": library_id, "collections": names, "items": rows}


def _csv_cell(value: Any) -> Any:
    """Neutralize spreadsheet formulas: a cell starting with = + - @ is prefixed with an apostrophe."""
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def snapshot_csv(data: dict[str, Any]) -> str:
    """CSV text for spreadsheets. Titles come from web imports, so formula-looking cells are defused."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in data["items"]:
        flat = {**row, "creators": "; ".join(row["creators"]), "collections": "; ".join(row["collections"]),
                "tags": "; ".join(row["tags"])}
        writer.writerow({k: _csv_cell(v) for k, v in flat.items()})
    return buffer.getvalue()
