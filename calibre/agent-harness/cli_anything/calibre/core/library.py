"""Library operations for cli-anything-calibre."""

from __future__ import annotations

import os
from typing import Any

from cli_anything.calibre.utils import calibre_backend as backend


def open_library(path: str) -> dict[str, Any]:
    abs_path = os.path.abspath(path)
    metadata_db = os.path.join(abs_path, "metadata.db")
    if not os.path.isdir(abs_path):
        raise FileNotFoundError(f"Library path not found: {abs_path}")
    if not os.path.exists(metadata_db):
        raise FileNotFoundError(f"Not a calibre library (missing metadata.db): {abs_path}")
    return {
        "library_path": abs_path,
        "metadata_db": metadata_db,
        "exists": True,
    }


def get_library_info(path: str) -> dict[str, Any]:
    books = backend.calibredb_list(path, fields="id,title,authors,formats", limit=100000)
    author_names = set()
    format_names = set()
    for book in books:
        for author in (book.get("authors") or []):
            author_names.add(author)
        formats = book.get("formats") or []
        if isinstance(formats, str):
            formats = [x.strip() for x in formats.split(",") if x.strip()]
        for fmt in formats:
            format_names.add(str(fmt).lower())
    return {
        "library_path": os.path.abspath(path),
        "book_count": len(books),
        "author_count": len(author_names),
        "formats": sorted(format_names),
    }


def list_fields() -> list[str]:
    return [
        "id", "title", "authors", "author_sort", "series", "series_index", "tags",
        "formats", "publisher", "rating", "languages", "pubdate", "timestamp",
        "last_modified", "identifiers", "comments", "size", "path", "uuid",
    ]


def stats(path: str) -> dict[str, Any]:
    info = get_library_info(path)
    books = backend.calibredb_list(path, fields="id,title,formats,authors", limit=100000)
    with_formats = sum(1 for book in books if book.get("formats"))
    without_formats = len(books) - with_formats
    return {
        **info,
        "with_formats": with_formats,
        "without_formats": without_formats,
    }
