"""Metadata operations for standalone ebook files."""

from __future__ import annotations

from typing import Any

from cli_anything.calibre.utils import calibre_backend as backend


def show_metadata(book_path: str) -> dict[str, Any]:
    return backend.ebook_meta_show(book_path)


def set_metadata(
    book_path: str,
    title: str | None = None,
    authors: str | None = None,
    cover: str | None = None,
    language: str | None = None,
    publisher: str | None = None,
    tags: str | None = None,
    comments: str | None = None,
) -> dict[str, Any]:
    return backend.ebook_meta_set(
        book_path,
        title=title,
        authors=authors,
        cover=cover,
        language=language,
        publisher=publisher,
        tags=tags,
        comments=comments,
    )


def clear_metadata_fields(book_path: str, clear_comments: bool = False, clear_tags: bool = False) -> dict[str, Any]:
    comments = "" if clear_comments else None
    tags = "" if clear_tags else None
    return backend.ebook_meta_set(book_path, comments=comments, tags=tags)
