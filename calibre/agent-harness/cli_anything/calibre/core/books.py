"""Book operations for cli-anything-calibre."""

from __future__ import annotations

import os
import re
from typing import Any

from cli_anything.calibre.utils import calibre_backend as backend


def _book_to_summary(book: dict[str, Any]) -> dict[str, Any]:
    data = dict(book)
    if isinstance(data.get("authors"), list):
        data["authors_text"] = ", ".join(data["authors"])
    if isinstance(data.get("formats"), list):
        data["formats_text"] = ", ".join(data["formats"])
    return data


def list_books(
    library_path: str,
    search: str | None = None,
    limit: int | None = 100,
    sort_by: str | None = None,
    ascending: bool = False,
) -> list[dict[str, Any]]:
    books = backend.calibredb_list(
        library_path,
        fields="id,title,authors,formats,series,tags,publisher,languages",
        search=search,
        limit=limit,
        sort_by=sort_by,
        ascending=ascending,
    )
    return [_book_to_summary(book) for book in books]


def get_book(library_path: str, book_id: int) -> dict[str, Any]:
    meta = backend.calibredb_show_metadata(library_path, book_id, as_opf=False)
    return {
        "book_id": book_id,
        "metadata": meta["metadata"],
    }


def add_book(
    library_path: str,
    input_path: str,
    title: str | None = None,
    authors: str | None = None,
    tags: str | None = None,
    series: str | None = None,
    duplicate: bool = False,
) -> dict[str, Any]:
    return backend.calibredb_add(
        library_path,
        input_path,
        title=title,
        authors=authors,
        tags=tags,
        series=series,
        duplicate=duplicate,
    )


def remove_book(library_path: str, book_id: int, permanent: bool = False) -> dict[str, Any]:
    return backend.calibredb_remove(library_path, book_id, permanent=permanent)


def search_books(library_path: str, query: str, limit: int | None = 100) -> list[dict[str, Any]]:
    return list_books(library_path, search=query, limit=limit)


def set_field(
    library_path: str,
    book_id: int,
    title: str | None = None,
    authors: str | None = None,
    tags: str | None = None,
) -> dict[str, Any]:
    opf_path = backend.write_opf_temp(title=title, authors=authors, tags=tags)
    try:
        result = backend.calibredb_set_metadata(library_path, book_id, opf_path)
    finally:
        try:
            os.remove(opf_path)
        except OSError:
            pass
    return result


def parse_added_id(stdout: str) -> int | None:
    match = re.search(r"id:\s*(\d+)", stdout, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"book ids?:\s*([^\n]+)", stdout, re.IGNORECASE)
    if match:
        digits = re.findall(r"\d+", match.group(1))
        if digits:
            return int(digits[0])
    return None
