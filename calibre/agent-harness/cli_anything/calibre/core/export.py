"""Export helpers for cli-anything-calibre."""

from __future__ import annotations

from typing import Any

from cli_anything.calibre.utils import calibre_backend as backend


def export_books(library_path: str, book_ids: list[int], to_dir: str, single_dir: bool = False, formats: str | None = None) -> dict[str, Any]:
    return backend.calibredb_export(library_path, book_ids, to_dir, single_dir=single_dir, formats=formats)


def build_catalog(library_path: str, output_path: str, search: str | None = None) -> dict[str, Any]:
    return backend.calibredb_catalog(library_path, output_path, search=search)


def backup_metadata(library_path: str, all_records: bool = False) -> dict[str, Any]:
    return backend.calibredb_backup_metadata(library_path, all_records=all_records)
