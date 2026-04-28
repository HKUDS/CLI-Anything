"""calibre backend wrappers around real calibre CLI tools."""

from __future__ import annotations

import json
import locale
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


INSTALL_HINT = (
    "calibre is not installed or not on PATH. Install calibre and ensure these commands are available: "
    "calibredb, ebook-convert, ebook-meta"
)


def _find_binary(*names: str) -> str:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError(INSTALL_HINT)


def find_calibredb() -> str:
    return _find_binary("calibredb")


def find_ebook_convert() -> str:
    return _find_binary("ebook-convert")


def find_ebook_meta() -> str:
    return _find_binary("ebook-meta")


def _run(cmd: list[str], timeout: int = 120) -> dict[str, Any]:
    encoding = locale.getpreferredencoding(False) or "utf-8"
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding=encoding,
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed (exit {result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout[-4000:]}\n"
            f"stderr:\n{result.stderr[-4000:]}"
        )
    return {
        "command": cmd,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def run_calibredb(args: list[str], library_path: str | None = None, timeout: int = 120) -> dict[str, Any]:
    exe = find_calibredb()
    cmd = [exe]
    if library_path:
        cmd.extend(["--with-library", os.path.abspath(library_path)])
    cmd.extend(args)
    return _run(cmd, timeout=timeout)


def calibredb_list(
    library_path: str,
    fields: str = "id,title,authors,formats",
    search: str | None = None,
    limit: int | None = None,
    sort_by: str | None = None,
    ascending: bool = False,
) -> list[dict[str, Any]]:
    args = ["list", "--for-machine", "--fields", fields]
    if search:
        args.extend(["--search", search])
    if limit is not None:
        args.extend(["--limit", str(limit)])
    if sort_by:
        args.extend(["--sort-by", sort_by])
    if ascending:
        args.append("--ascending")
    result = run_calibredb(args, library_path=library_path)
    return json.loads(result["stdout"] or "[]")


def calibredb_add(
    library_path: str,
    input_path: str,
    title: str | None = None,
    authors: str | None = None,
    tags: str | None = None,
    series: str | None = None,
    duplicate: bool = False,
) -> dict[str, Any]:
    abs_input = os.path.abspath(input_path)
    if not os.path.exists(abs_input):
        raise FileNotFoundError(f"Input file not found: {abs_input}")
    args = ["add"]
    if duplicate:
        args.append("--duplicates")
    if title:
        args.extend(["--title", title])
    if authors:
        args.extend(["--authors", authors])
    if tags:
        args.extend(["--tags", tags])
    if series:
        args.extend(["--series", series])
    args.append(abs_input)
    result = run_calibredb(args, library_path=library_path)
    return {"stdout": result["stdout"].strip(), "input": abs_input}


def calibredb_remove(library_path: str, book_id: int, permanent: bool = False) -> dict[str, Any]:
    args = ["remove"]
    if permanent:
        args.append("--permanent")
    args.append(str(book_id))
    result = run_calibredb(args, library_path=library_path)
    return {"removed": book_id, "stdout": result["stdout"].strip()}


def calibredb_show_metadata(library_path: str, book_id: int, as_opf: bool = False) -> dict[str, Any]:
    args = ["show_metadata"]
    if as_opf:
        args.append("--as-opf")
    args.append(str(book_id))
    result = run_calibredb(args, library_path=library_path)
    return {"book_id": book_id, "metadata": result["stdout"]}


def calibredb_export(
    library_path: str,
    book_ids: list[int],
    to_dir: str,
    single_dir: bool = False,
    formats: str | None = None,
) -> dict[str, Any]:
    out_dir = os.path.abspath(to_dir)
    os.makedirs(out_dir, exist_ok=True)
    args = ["export", "--to-dir", out_dir]
    if single_dir:
        args.append("--single-dir")
    if formats:
        args.extend(["--formats", formats])
    args.extend(str(x) for x in book_ids)
    result = run_calibredb(args, library_path=library_path)
    return {"output_dir": out_dir, "book_ids": book_ids, "stdout": result["stdout"].strip()}


def calibredb_catalog(library_path: str, output_path: str, search: str | None = None) -> dict[str, Any]:
    # calibredb's `catalog` subcommand is unusual: it requires the output filename
    # to appear immediately after `catalog` (before any options). Some calibre
    # builds treat `--with-library` as an option and will error if it appears
    # before the output filename.
    exe = find_calibredb()
    abs_output = os.path.abspath(output_path)
    abs_library = os.path.abspath(library_path)
    os.makedirs(os.path.dirname(abs_output), exist_ok=True)

    cmd = [exe, "catalog", abs_output, "--with-library", abs_library]
    if search:
        cmd.extend(["--search", search])
    result = _run(cmd, timeout=300)
    return {"output": abs_output, "stdout": result["stdout"].strip()}


def calibredb_backup_metadata(library_path: str, all_records: bool = False) -> dict[str, Any]:
    args = ["backup_metadata"]
    if all_records:
        args.append("--all")
    result = run_calibredb(args, library_path=library_path, timeout=300)
    return {"library_path": os.path.abspath(library_path), "stdout": result["stdout"].strip()}


def ebook_meta_show(book_path: str) -> dict[str, Any]:
    exe = find_ebook_meta()
    abs_path = os.path.abspath(book_path)
    result = _run([exe, abs_path])
    return {"path": abs_path, "metadata": result["stdout"]}


def ebook_meta_set(
    book_path: str,
    title: str | None = None,
    authors: str | None = None,
    cover: str | None = None,
    language: str | None = None,
    publisher: str | None = None,
    tags: str | None = None,
    comments: str | None = None,
) -> dict[str, Any]:
    exe = find_ebook_meta()
    abs_path = os.path.abspath(book_path)
    cmd = [exe, abs_path]
    if title:
        cmd.extend(["--title", title])
    if authors:
        cmd.extend(["--authors", authors])
    if cover:
        cmd.extend(["--cover", os.path.abspath(cover)])
    if language:
        cmd.extend(["--language", language])
    if publisher:
        cmd.extend(["--publisher", publisher])
    if tags:
        cmd.extend(["--tags", tags])
    if comments:
        cmd.extend(["--comments", comments])
    result = _run(cmd)
    return {"path": abs_path, "stdout": result["stdout"].strip()}


def ebook_convert(input_path: str, output_path: str, extra_args: list[str] | None = None) -> dict[str, Any]:
    exe = find_ebook_convert()
    abs_input = os.path.abspath(input_path)
    abs_output = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(abs_output), exist_ok=True)
    cmd = [exe, abs_input, abs_output]
    if extra_args:
        cmd.extend(extra_args)
    result = _run(cmd, timeout=600)
    return {
        "input": abs_input,
        "output": abs_output,
        "stdout": result["stdout"].strip(),
        "stderr": result["stderr"].strip(),
        "exists": os.path.exists(abs_output),
        "file_size": os.path.getsize(abs_output) if os.path.exists(abs_output) else 0,
    }


def write_opf_temp(title: str | None = None, authors: str | None = None, tags: str | None = None) -> str:
    parts = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<package xmlns:dc="http://purl.org/dc/elements/1.1/">',
        '  <metadata>',
    ]
    if title:
        parts.append(f'    <dc:title>{title}</dc:title>')
    if authors:
        for author in [x.strip() for x in authors.split('&') if x.strip()]:
            parts.append(f'    <dc:creator>{author}</dc:creator>')
    if tags:
        for tag in [x.strip() for x in tags.split(',') if x.strip()]:
            parts.append(f'    <dc:subject>{tag}</dc:subject>')
    parts.extend(['  </metadata>', '</package>'])
    fd, temp_path = tempfile.mkstemp(suffix='.opf', prefix='cli-anything-calibre-')
    os.close(fd)
    Path(temp_path).write_text('\n'.join(parts), encoding='utf-8')
    return temp_path


def calibredb_set_metadata(library_path: str, book_id: int, opf_path: str) -> dict[str, Any]:
    args = ["set_metadata", str(book_id), os.path.abspath(opf_path)]
    result = run_calibredb(args, library_path=library_path)
    return {"book_id": book_id, "opf_path": os.path.abspath(opf_path), "stdout": result["stdout"].strip()}


def detect_available_formats() -> list[str]:
    return ["epub", "mobi", "azw3", "pdf", "txt", "html", "docx"]
