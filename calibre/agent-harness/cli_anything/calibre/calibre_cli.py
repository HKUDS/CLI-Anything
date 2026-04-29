"""cli-anything-calibre — Main CLI entry point.

Provides a Click-based command-line interface for the Calibre e-book manager.
Wraps calibredb, ebook-convert, and ebook-meta as the real backend.

Usage:
    cli-anything-calibre                          # Enter interactive REPL
    cli-anything-calibre library connect <path>   # Set active library
    cli-anything-calibre books list               # List books
    cli-anything-calibre books search "author:asimov"
    cli-anything-calibre meta set 42 title "New Title"
    cli-anything-calibre formats convert 42 EPUB MOBI
"""

import json
import shlex
import sys
from pathlib import Path

import click

from cli_anything.calibre import __version__
from cli_anything.calibre.core import session as _session
from cli_anything.calibre.core import library as _library
from cli_anything.calibre.core import metadata as _metadata
from cli_anything.calibre.core import formats as _formats
from cli_anything.calibre.core import custom as _custom
from cli_anything.calibre.core import export as _export


# ── Output helpers ─────────────────────────────────────────────────────────


def _out(data, as_json: bool):
    """Print data as JSON or human-readable depending on --json flag."""
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        if isinstance(data, list):
            for item in data:
                click.echo(item)
        elif isinstance(data, dict):
            for k, v in data.items():
                if k not in ("stdout", "stderr", "raw_opf"):
                    click.echo(f"  {k}: {v}")
        else:
            click.echo(str(data))


def _err(msg: str):
    click.echo(f"  ✗ {msg}", err=True)


def _ok(msg: str):
    click.echo(f"  ✓ {msg}")


# ── Root group ─────────────────────────────────────────────────────────────


@click.group(invoke_without_command=True)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--library", "library_path", default=None,
              help="Override active library path for this command")
@click.version_option(__version__, prog_name="cli-anything-calibre")
@click.pass_context
def main(ctx, as_json, library_path):
    """cli-anything-calibre — Calibre e-book manager CLI harness.

    If no subcommand is given, enters the interactive REPL.
    """
    ctx.ensure_object(dict)
    sess = _session.load_session()
    if library_path:
        sess["library_path"] = library_path
    ctx.obj["session"] = sess
    ctx.obj["as_json"] = as_json

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── REPL ───────────────────────────────────────────────────────────────────


@main.command()
@click.pass_context
def repl(ctx):
    """Enter the interactive REPL session."""
    from cli_anything.calibre.utils.repl_skin import ReplSkin

    sess = ctx.obj["session"] if ctx.obj else _session.load_session()
    skin = ReplSkin("calibre", version=__version__)
    skin.print_banner()

    pt_session = skin.create_prompt_session()

    repl_commands = {
        "library connect <path>": "Set active library",
        "library info":           "Show library statistics",
        "books list":             "List books",
        "books search <query>":   "Search books",
        "books add <files>":      "Add books to library",
        "books remove <ids>":     "Remove books",
        "books show <id>":        "Show book metadata",
        "books export <ids>":     "Export books to directory",
        "books export-chapters <id>": "Export chapters as PDFs",
        "meta get <id>":          "Get book metadata",
        "meta set <id> <f> <v>":  "Set metadata field",
        "formats list <id>":      "List book formats",
        "formats convert <id>":   "Convert book format",
        "custom list":            "List custom columns",
        "help":                   "Show this help",
        "quit":                   "Exit REPL",
    }

    while True:
        lib_path = _session.get_library_path(sess)
        project_name = Path(lib_path).name if lib_path else ""

        try:
            raw = skin.get_input(pt_session, project_name=project_name)
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

        raw = raw.strip()
        if not raw:
            continue
        if raw in ("quit", "exit", "q"):
            skin.print_goodbye()
            break
        if raw in ("help", "?"):
            skin.help(repl_commands)
            continue

        # Parse and dispatch via Click
        args = shlex.split(raw)
        try:
            main.main(args=args, obj={"session": sess, "as_json": False},
                      standalone_mode=False)
        except SystemExit:
            pass
        except Exception as exc:
            skin.error(str(exc))


# ── library group ──────────────────────────────────────────────────────────


@main.group()
def library():
    """Library management commands."""


@library.command("connect")
@click.argument("path")
@click.pass_context
def library_connect(ctx, path):
    """Set the active Calibre library path."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    resolved = str(Path(path).expanduser().resolve())
    if not Path(resolved).exists():
        _err(f"Path does not exist: {resolved}")
        sys.exit(1)

    sess = _session.set_library_path(resolved, sess)
    if ctx.obj:
        ctx.obj["session"] = sess

    result = {"library_path": resolved, "status": "connected"}
    if as_json:
        _out(result, True)
    else:
        _ok(f"Library connected: {resolved}")


@library.command("info")
@click.pass_context
def library_info(ctx):
    """Show library statistics."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    try:
        lib_path = _session.require_library(sess)
        info = _library.library_info(lib_path)
    except (RuntimeError, FileNotFoundError) as e:
        _err(str(e))
        sys.exit(1)

    if as_json:
        _out(info, True)
    else:
        _ok(f"Library: {info['library_path']}")
        click.echo(f"  books:   {info['book_count']}")
        click.echo(f"  db size: {info['db_size_bytes']:,} bytes")
        if info["format_counts"]:
            click.echo("  formats:")
            for fmt, cnt in sorted(info["format_counts"].items()):
                click.echo(f"    {fmt}: {cnt}")


@library.command("check")
@click.pass_context
def library_check(ctx):
    """Verify library integrity using calibredb check_library."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    try:
        lib_path = _session.require_library(sess)
        result = _library.check_library(lib_path)
    except RuntimeError as e:
        _err(str(e))
        sys.exit(1)

    _out(result, as_json)
    if not as_json:
        if result["ok"]:
            _ok("Library is healthy")
        else:
            _err(f"{len(result['issues'])} issues found")


# ── books group ────────────────────────────────────────────────────────────


@main.group()
def books():
    """Book management commands."""


@books.command("list")
@click.option("--search", "-s", default="", help="Calibre search query")
@click.option("--sort", default="title", help="Sort field (title, authors, date, etc.)")
@click.option("--limit", "-n", default=50, help="Maximum number of results")
@click.option("--fields", "-f", default=None,
              help="Comma-separated fields to display")
@click.pass_context
def books_list(ctx, search, sort, limit, fields):
    """List books in the library."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    field_list = fields.split(",") if fields else None

    try:
        lib_path = _session.require_library(sess)
        book_list = _library.list_books(lib_path, search=search, sort_by=sort,
                                        limit=limit, fields=field_list)
    except RuntimeError as e:
        _err(str(e))
        sys.exit(1)

    if as_json:
        _out(book_list, True)
    else:
        if not book_list:
            click.echo("  No books found.")
        else:
            # Determine columns from actual returned fields (id is always first)
            actual_fields = list(book_list[0].keys())
            non_id_fields = [f for f in actual_fields if f != "id"]

            # Build header dynamically
            header = f"  {'ID':<5} " + " ".join(f"{f.capitalize():<30}" for f in non_id_fields)
            sep = f"  {'─'*5} " + " ".join(f"{'─'*30}" for _ in non_id_fields)
            click.echo(header)
            click.echo(sep)
            for b in book_list:
                row = f"  {b.get('id', ''):<5} " + " ".join(
                    f"{str(b.get(f, ''))[:30]:<30}" for f in non_id_fields
                )
                click.echo(row)


@books.command("search")
@click.argument("query")
@click.option("--limit", "-n", default=100, help="Max results")
@click.pass_context
def books_search(ctx, query, limit):
    """Search books using Calibre query language. Returns book IDs."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    try:
        lib_path = _session.require_library(sess)
        ids = _library.search_books(lib_path, query, limit=limit)
    except RuntimeError as e:
        _err(str(e))
        sys.exit(1)

    if as_json:
        _out({"query": query, "ids": ids, "count": len(ids)}, True)
    else:
        if ids:
            _ok(f"{len(ids)} books found: {', '.join(str(i) for i in ids)}")
        else:
            click.echo("  No books match the query.")


@books.command("show")
@click.argument("book_id", type=int)
@click.pass_context
def books_show(ctx, book_id):
    """Show full metadata for a book."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    try:
        lib_path = _session.require_library(sess)
        meta = _metadata.get_metadata(lib_path, book_id)
    except RuntimeError as e:
        _err(str(e))
        sys.exit(1)

    if as_json:
        _out(meta, True)
    else:
        for k, v in meta.items():
            if k not in ("raw_opf",):
                click.echo(f"  {k:<20}: {v}")


@books.command("add")
@click.argument("files", nargs=-1, required=True)
@click.option("--automerge", default="ignore",
              type=click.Choice(["ignore", "overwrite", "new_record"]),
              help="How to handle duplicates")
@click.pass_context
def books_add(ctx, files, automerge):
    """Add book files to the library."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    try:
        lib_path = _session.require_library(sess)
        result = _library.add_books(lib_path, list(files), automerge=automerge)
    except RuntimeError as e:
        _err(str(e))
        sys.exit(1)

    if as_json:
        _out(result, True)
    else:
        _ok(f"Added {result['count']} book(s): IDs {result['added_ids']}")
        if result["duplicates"]:
            for d in result["duplicates"]:
                click.echo(f"  ⚠ {d}")


@books.command("remove")
@click.argument("book_ids")
@click.option("--permanent", is_flag=True, help="Delete permanently (bypass trash)")
@click.pass_context
def books_remove(ctx, book_ids, permanent):
    """Remove books from the library. BOOK_IDS is a comma-separated list."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    ids = [int(i.strip()) for i in book_ids.split(",") if i.strip().isdigit()]
    if not ids:
        _err("No valid book IDs provided")
        sys.exit(1)

    try:
        lib_path = _session.require_library(sess)
        result = _library.remove_books(lib_path, ids, permanent=permanent)
    except RuntimeError as e:
        _err(str(e))
        sys.exit(1)

    if as_json:
        _out(result, True)
    else:
        action = "permanently deleted" if permanent else "moved to trash"
        _ok(f"{result['count']} book(s) {action}")


@books.command("export-chapters")
@click.argument("book_id", type=int)
@click.option("--to-dir", "-d", required=True, help="Output directory for chapter PDFs")
@click.option(
    "--chapters", "-c", default=None,
    help="Chapter range to export, e.g. '3-7' or '5' (default: all chapters)",
)
@click.pass_context
def books_export_chapters(ctx, book_id, to_dir, chapters):
    """Export each chapter of a book as a separate PDF file.

    Requires the book to have an EPUB format in the library.
    If it doesn't, convert it first with:  formats convert BOOK_ID <FMT> EPUB

    \b
    Examples:
      books export-chapters 42 --to-dir ./pdfs
      books export-chapters 42 --to-dir ./pdfs --chapters 1-5
      books export-chapters 42 --to-dir ./pdfs --chapters 3
    """
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    chapter_range = None
    if chapters:
        if "-" in chapters:
            parts = chapters.split("-", 1)
            try:
                chapter_range = (int(parts[0]), int(parts[1]))
            except ValueError:
                _err("Invalid --chapters range. Use '1-5' or a single number like '3'.")
                sys.exit(1)
        else:
            try:
                n = int(chapters)
                chapter_range = (n, n)
            except ValueError:
                _err("Invalid --chapters value. Use '1-5' or a single number like '3'.")
                sys.exit(1)

    try:
        lib_path = _session.require_library(sess)
        result = _export.export_chapters_pdf(lib_path, book_id, to_dir, chapter_range)
    except (RuntimeError, FileNotFoundError) as e:
        _err(str(e))
        sys.exit(1)

    if as_json:
        _out(result, True)
    else:
        _ok(
            f"Exported {result['exported_chapters']}/{result['total_chapters']} "
            f"chapters to {to_dir}"
        )
        for pdf in result["exported_pdfs"]:
            click.echo(f"  [{pdf['index']:03d}] {pdf['title']}  ({pdf['size']:,} bytes)")


@books.command("export")
@click.argument("book_ids", default="")
@click.option("--to-dir", "-d", required=True, help="Output directory")
@click.option("--formats", "-f", default=None,
              help="Comma-separated formats to export (e.g. 'EPUB,MOBI')")
@click.option("--all", "export_all", is_flag=True,
              help="Export all books in library (ignores book_ids)")
@click.pass_context
def books_export(ctx, book_ids, to_dir, formats, export_all):
    """Export books to a directory.

    BOOK_IDS is comma-separated (e.g. '42,43,44').
    Use --all to export entire library instead.
    """
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    if export_all:
        ids = []
    else:
        ids = [int(i.strip()) for i in book_ids.split(",") if i.strip().isdigit()]
        if not ids:
            _err("No valid book IDs (or use --all to export entire library)")
            sys.exit(1)

    format_list = formats.split(",") if formats else None

    try:
        lib_path = _session.require_library(sess)
        result = _export.export_books(
            lib_path, ids, to_dir,
            formats=format_list,
            export_all=export_all,
        )
    except RuntimeError as e:
        _err(str(e))
        sys.exit(1)

    if as_json:
        _out(result, True)
    else:
        action = "all books" if export_all else f"book IDs {ids}"
        _ok(f"Exported {result['count']} file(s) ({action}) to {to_dir}")


# ── meta group ─────────────────────────────────────────────────────────────


@main.group()
def meta():
    """Metadata editing commands."""


@meta.command("get")
@click.argument("book_id", type=int)
@click.argument("field", default=None, required=False)
@click.pass_context
def meta_get(ctx, book_id, field):
    """Get metadata for a book. Optionally specify a single FIELD."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    try:
        lib_path = _session.require_library(sess)
        meta_dict = _metadata.get_metadata(lib_path, book_id)
    except RuntimeError as e:
        _err(str(e))
        sys.exit(1)

    if field:
        value = meta_dict.get(field)
        if as_json:
            _out({"book_id": book_id, "field": field, "value": value}, True)
        else:
            click.echo(f"  {field}: {value}")
    else:
        if as_json:
            _out(meta_dict, True)
        else:
            for k, v in meta_dict.items():
                if k != "raw_opf":
                    click.echo(f"  {k:<20}: {v}")


@meta.command("set")
@click.argument("book_id", type=int)
@click.argument("field")
@click.argument("value")
@click.pass_context
def meta_set(ctx, book_id, field, value):
    """Set a metadata FIELD on a book to VALUE."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    try:
        lib_path = _session.require_library(sess)
        result = _metadata.set_metadata(lib_path, book_id, field, value)
    except RuntimeError as e:
        _err(str(e))
        sys.exit(1)

    if as_json:
        _out(result, True)
    else:
        _ok(f"Set {field} = {value!r} on book {book_id}")


@meta.command("embed")
@click.argument("book_ids")
@click.pass_context
def meta_embed(ctx, book_ids):
    """Embed library metadata into the actual book files. BOOK_IDS is comma-separated."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    ids = [int(i.strip()) for i in book_ids.split(",") if i.strip().isdigit()]
    if not ids:
        _err("No valid book IDs")
        sys.exit(1)

    try:
        lib_path = _session.require_library(sess)
        result = _metadata.embed_metadata(lib_path, ids)
    except RuntimeError as e:
        _err(str(e))
        sys.exit(1)

    if as_json:
        _out(result, True)
    else:
        _ok(f"Embedded metadata into {result['count']} book(s)")


# ── formats group ──────────────────────────────────────────────────────────


@main.group()
def formats():
    """Format management and conversion commands."""


@formats.command("list")
@click.argument("book_id", type=int)
@click.pass_context
def formats_list(ctx, book_id):
    """List available formats for a book."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    try:
        lib_path = _session.require_library(sess)
        result = _formats.list_formats(lib_path, book_id)
    except RuntimeError as e:
        _err(str(e))
        sys.exit(1)

    if as_json:
        _out(result, True)
    else:
        if result["formats"]:
            _ok(f"Book {book_id} formats: {', '.join(result['formats'])}")
        else:
            click.echo(f"  Book {book_id} has no formats in the library.")


@formats.command("add")
@click.argument("book_id", type=int)
@click.argument("file_path")
@click.pass_context
def formats_add(ctx, book_id, file_path):
    """Add a format file to a book in the library."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    try:
        lib_path = _session.require_library(sess)
        result = _formats.add_format(lib_path, book_id, file_path)
    except (RuntimeError, FileNotFoundError) as e:
        _err(str(e))
        sys.exit(1)

    if as_json:
        _out(result, True)
    else:
        _ok(f"Added {result['format']} to book {book_id}")


@formats.command("remove")
@click.argument("book_id", type=int)
@click.argument("fmt")
@click.pass_context
def formats_remove(ctx, book_id, fmt):
    """Remove a format from a book."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    try:
        lib_path = _session.require_library(sess)
        result = _formats.remove_format(lib_path, book_id, fmt)
    except RuntimeError as e:
        _err(str(e))
        sys.exit(1)

    if as_json:
        _out(result, True)
    else:
        _ok(f"Removed {fmt.upper()} from book {book_id}")


@formats.command("convert")
@click.argument("book_id", type=int)
@click.argument("input_fmt")
@click.argument("output_fmt")
@click.option("--output", "-o", default=None,
              help="Output file path (defaults to temp dir, auto-added to library)")
@click.option("--no-add", is_flag=True,
              help="Do not add converted file back to library")
@click.option("--option", "-x", multiple=True,
              help="Extra ebook-convert options (can repeat)")
@click.pass_context
def formats_convert(ctx, book_id, input_fmt, output_fmt, output, no_add, option):
    """Convert a book from INPUT_FMT to OUTPUT_FMT using ebook-convert."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    try:
        lib_path = _session.require_library(sess)
        result = _formats.convert_format(
            lib_path, book_id, input_fmt, output_fmt,
            output_path=output,
            extra_options=list(option),
            add_to_library=not no_add,
        )
    except (RuntimeError, FileNotFoundError) as e:
        _err(str(e))
        sys.exit(1)

    if as_json:
        _out(result, True)
    else:
        _ok(f"Converted book {book_id}: {input_fmt} → {output_fmt}")
        click.echo(f"  Output: {result['output_path']} ({result['output_size']:,} bytes)")


# ── custom group ───────────────────────────────────────────────────────────


@main.group()
def custom():
    """Custom column management commands."""


@custom.command("list")
@click.pass_context
def custom_list(ctx):
    """List all custom columns in the library."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    try:
        lib_path = _session.require_library(sess)
        columns = _custom.list_custom_columns(lib_path)
    except RuntimeError as e:
        _err(str(e))
        sys.exit(1)

    if as_json:
        _out(columns, True)
    else:
        if not columns:
            click.echo("  No custom columns defined.")
        else:
            for col in columns:
                click.echo(f"  {col.get('raw', col)}")


@custom.command("add")
@click.argument("label")
@click.argument("name")
@click.argument("datatype")
@click.option("--multiple", is_flag=True, help="Allow multiple values")
@click.pass_context
def custom_add(ctx, label, name, datatype, multiple):
    """Add a custom LABEL column with NAME and DATATYPE.

    Valid datatypes: rating, text, comments, datetime, int, float,
                     bool, series, enumeration, composite
    """
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    try:
        lib_path = _session.require_library(sess)
        result = _custom.add_custom_column(lib_path, label, name, datatype, multiple)
    except (RuntimeError, ValueError) as e:
        _err(str(e))
        sys.exit(1)

    if as_json:
        _out(result, True)
    else:
        _ok(f"Created custom column {result['label']} ({datatype})")


@custom.command("remove")
@click.argument("label")
@click.pass_context
def custom_remove(ctx, label):
    """Remove a custom column by LABEL."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    try:
        lib_path = _session.require_library(sess)
        result = _custom.remove_custom_column(lib_path, label)
    except RuntimeError as e:
        _err(str(e))
        sys.exit(1)

    if as_json:
        _out(result, True)
    else:
        _ok(f"Removed custom column {result['label']}")


@custom.command("set")
@click.argument("book_id", type=int)
@click.argument("label")
@click.argument("value")
@click.pass_context
def custom_set(ctx, book_id, label, value):
    """Set a custom field LABEL to VALUE for a book."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    try:
        lib_path = _session.require_library(sess)
        result = _custom.set_custom_field(lib_path, book_id, label, value)
    except RuntimeError as e:
        _err(str(e))
        sys.exit(1)

    if as_json:
        _out(result, True)
    else:
        _ok(f"Set {result['label']} = {value!r} on book {book_id}")


# ── catalog command ────────────────────────────────────────────────────────


@main.command()
@click.argument("output_path")
@click.option("--format", "catalog_format", default="epub",
              type=click.Choice(["epub", "csv", "opds"]),
              help="Catalog format")
@click.option("--title", default="My Calibre Library", help="Catalog title")
@click.pass_context
def catalog(ctx, output_path, catalog_format, title):
    """Generate a catalog of the library at OUTPUT_PATH."""
    as_json = ctx.obj.get("as_json", False) if ctx.obj else False
    sess = ctx.obj.get("session", {}) if ctx.obj else {}

    try:
        lib_path = _session.require_library(sess)
        result = _export.generate_catalog(lib_path, output_path, catalog_format, title)
    except RuntimeError as e:
        _err(str(e))
        sys.exit(1)

    if as_json:
        _out(result, True)
    else:
        _ok(f"Catalog generated: {result['output_path']} ({result['file_size']:,} bytes)")


if __name__ == "__main__":
    main()
