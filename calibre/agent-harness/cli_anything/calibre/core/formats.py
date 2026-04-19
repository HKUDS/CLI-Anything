"""Format management — wraps calibredb add_format, remove_format + ebook-convert."""

import os
import shutil
from pathlib import Path

from cli_anything.calibre.utils.calibre_backend import (
    run_calibredb,
    run_ebook_convert,
    find_calibredb,
    find_ebook_convert,
)


def list_formats(library_path: str, book_id: int) -> dict:
    """List available formats for a book.

    Uses the OPF metadata to find the book's folder, then scans for format files.
    """
    import re
    find_calibredb()

    # Get the raw calibredb list output for this book (formats field = full paths)
    result = run_calibredb(
        ["list", "--fields=id,formats", f"--search=id:{book_id}", "--limit=1"],
        library_path=library_path,
    )

    # Join all lines to handle line-wrapped paths
    raw = " ".join(result["stdout"].splitlines())

    # Extract file extensions from paths embedded in the output
    # calibredb shows: [/path/to/book.epub, /path/to/book.mobi]
    extensions = re.findall(r"\.([A-Za-z0-9]{2,6})\b", raw)
    skip = {"db", "opf", "jpg", "png", "gif", "webp"}
    formats = sorted(set(ext.upper() for ext in extensions if ext.lower() not in skip))

    return {
        "book_id": book_id,
        "formats": formats,
    }


def add_format(
    library_path: str,
    book_id: int,
    file_path: str,
) -> dict:
    """Add a new format file to an existing book in the library."""
    find_calibredb()

    if not Path(file_path).exists():
        raise FileNotFoundError(f"Format file not found: {file_path}")

    fmt = Path(file_path).suffix.lstrip(".").upper()

    result = run_calibredb(
        ["add_format", str(book_id), file_path],
        library_path=library_path,
    )
    return {
        "book_id": book_id,
        "format": fmt,
        "file_path": file_path,
        "stdout": result["stdout"],
    }


def remove_format(
    library_path: str,
    book_id: int,
    fmt: str,
) -> dict:
    """Remove a format from a book."""
    find_calibredb()

    result = run_calibredb(
        ["remove_format", str(book_id), fmt.upper()],
        library_path=library_path,
    )
    return {
        "book_id": book_id,
        "format": fmt.upper(),
        "stdout": result["stdout"],
    }


def convert_format(
    library_path: str,
    book_id: int,
    input_fmt: str,
    output_fmt: str,
    output_path: str | None = None,
    extra_options: list[str] | None = None,
    add_to_library: bool = True,
) -> dict:
    """
    Convert a book format using ebook-convert.

    1. Exports the input format file from the library
    2. Runs ebook-convert to produce the output format
    3. Optionally adds the converted file back to the library
    """
    find_calibredb()
    find_ebook_convert()

    import tempfile

    input_fmt = input_fmt.upper()
    output_fmt = output_fmt.upper()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Export only the target book and requested input format to get the source file
        export_result = run_calibredb(
            ["export", "--to-dir", tmpdir, "--formats", input_fmt, str(book_id)],
            library_path=library_path,
        )

        # Find the input format file
        input_file = None
        for f in Path(tmpdir).rglob(f"*.{input_fmt.lower()}"):
            input_file = str(f)
            break

        if not input_file:
            raise FileNotFoundError(
                f"Book {book_id} does not have format {input_fmt} in the library."
            )

        # Determine output path; default to cwd (mirrors calibredb export default)
        if output_path is None:
            input_stem = Path(input_file).stem
            output_path = str(Path.cwd() / f"{input_stem}.{output_fmt.lower()}")
        else:
            os.makedirs(Path(output_path).parent, exist_ok=True)

        # Run ebook-convert
        cmd = [input_file, output_path]
        if extra_options:
            cmd.extend(extra_options)

        convert_result = run_ebook_convert(cmd)

        if not Path(output_path).exists():
            raise RuntimeError(
                f"ebook-convert did not produce output at {output_path}\n"
                f"stderr: {convert_result['stderr']}"
            )

        output_size = Path(output_path).stat().st_size

        # Add back to library if requested
        added_id = None
        if add_to_library:
            add_result = run_calibredb(
                ["add_format", str(book_id), output_path],
                library_path=library_path,
            )

        return {
            "book_id": book_id,
            "input_format": input_fmt,
            "output_format": output_fmt,
            "output_path": output_path,
            "output_size": output_size,
            "added_to_library": add_to_library,
        }
