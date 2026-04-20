"""Library operations — wraps calibredb list, search, add, remove, export."""

import json
import os
from pathlib import Path
from typing import Any

from cli_anything.calibre.utils.calibre_backend import (
    run_calibredb,
    find_calibredb,
)


def library_info(library_path: str) -> dict:
    """Return library statistics: book count, format counts, total size."""
    find_calibredb()  # Ensure installed

    # Count books: search with empty string returns all book IDs
    result = run_calibredb(
        ["search", ""],
        library_path=library_path,
    )
    id_output = result["stdout"].strip()
    if id_output:
        book_ids = [p.strip() for p in id_output.split(",") if p.strip().isdigit()]
        book_count = len(book_ids)
    else:
        book_count = 0

    # Count format types by scanning library directory for book files
    format_counts: dict[str, int] = {}
    lib = Path(library_path)
    skip_exts = {".db", ".jpg", ".png", ".opf", ".sqlite", ""}
    for p in lib.rglob("*"):
        if p.is_file():
            ext = p.suffix.upper().lstrip(".")
            if ext and ext not in {"DB", "JPG", "PNG", "OPF", "SQLITE", "WEBP", "GIF"}:
                format_counts[ext] = format_counts.get(ext, 0) + 1

    db_path = lib / "metadata.db"
    db_size = db_path.stat().st_size if db_path.exists() else 0

    return {
        "library_path": library_path,
        "book_count": book_count,
        "format_counts": format_counts,
        "db_size_bytes": db_size,
    }


def list_books(
    library_path: str,
    search: str = "",
    sort_by: str = "title",
    ascending: bool = True,
    limit: int = 100,
    fields: list[str] | None = None,
) -> list[dict]:
    """List books in the library, optionally filtered and sorted."""
    find_calibredb()

    # Avoid including "formats" in default fields — calibredb outputs full paths
    # that can wrap across lines and break simple separator-based parsing.
    if fields is None:
        fields = ["id", "title", "authors", "tags", "series", "rating"]

    # Use a tab separator (least likely to appear in metadata fields)
    cmd = [
        "list",
        f"--fields={','.join(fields)}",
        "--separator=\t",
        f"--sort-by={sort_by}",
        f"--limit={limit}",
    ]
    if not ascending:
        cmd.append("--ascending=False")
    if search:
        cmd.extend(["--search", search])

    result = run_calibredb(cmd, library_path=library_path)

    books = []
    lines = result["stdout"].strip().splitlines()
    for line in lines:
        if "\t" not in line:
            continue
        parts = [p.strip() for p in line.split("\t")]
        try:
            book_id = int(parts[0])
        except ValueError:
            continue
        book = {"id": book_id}
        for i, field in enumerate(fields[1:], 1):
            book[field] = parts[i] if i < len(parts) else ""
        books.append(book)

    return books


def search_books(library_path: str, query: str, limit: int = 100) -> list[int]:
    """Search the library using Calibre query language, return book IDs."""
    find_calibredb()

    result = run_calibredb(
        ["search", "--", query],
        library_path=library_path,
    )

    output = result["stdout"].strip()
    if not output:
        return []

    ids = []
    for part in output.split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return ids[:limit]


def add_books(
    library_path: str,
    file_paths: list[str],
    automerge: str = "ignore",
) -> dict:
    """Add book files to the library. Returns added IDs and duplicates."""
    find_calibredb()

    cmd = ["add", f"--automerge={automerge}"] + file_paths
    result = run_calibredb(cmd, library_path=library_path)

    added_ids = []
    duplicates = []
    for line in result["stdout"].splitlines():
        line = line.strip()
        if line.startswith("Added book ids:"):
            raw = line.split(":", 1)[1].strip()
            for part in raw.split(","):
                part = part.strip()
                if part.isdigit():
                    added_ids.append(int(part))
        elif "duplicate" in line.lower():
            duplicates.append(line)

    return {
        "added_ids": added_ids,
        "duplicates": duplicates,
        "count": len(added_ids),
        "stdout": result["stdout"],
    }


def remove_books(
    library_path: str,
    book_ids: list[int],
    permanent: bool = False,
) -> dict:
    """Remove books from the library (to trash unless permanent=True)."""
    find_calibredb()

    ids_str = ",".join(str(i) for i in book_ids)
    cmd = ["remove"]
    if permanent:
        cmd.append("--permanent")
    cmd.append(ids_str)

    result = run_calibredb(cmd, library_path=library_path)
    return {
        "removed_ids": book_ids,
        "count": len(book_ids),
        "permanent": permanent,
        "stdout": result["stdout"],
    }


def check_library(library_path: str) -> dict:
    """Check library integrity, return issues found."""
    find_calibredb()

    result = run_calibredb(["check_library"], library_path=library_path)

    issues = []
    for line in result["stdout"].splitlines():
        line = line.strip()
        if line:
            issues.append(line)

    return {
        "library_path": library_path,
        "issues": issues,
        "ok": len(issues) == 0,
        "stdout": result["stdout"],
    }
