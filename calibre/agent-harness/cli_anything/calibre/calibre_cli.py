"""Stateful CLI harness for calibre."""

from __future__ import annotations

import json
import os
import shlex
import sys
from typing import Optional

import click

from cli_anything.calibre.core.session import Session
from cli_anything.calibre.core import library as library_mod
from cli_anything.calibre.core import books as books_mod
from cli_anything.calibre.core import metadata as metadata_mod
from cli_anything.calibre.core import convert as convert_mod
from cli_anything.calibre.core import export as export_mod


_session: Optional[Session] = None
_json_output = False
_repl_mode = False


def get_session() -> Session:
    global _session
    if _session is None:
        _session = Session()
    return _session


def output(data, message: str = ""):
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
        return
    if message:
        click.echo(message)
    if isinstance(data, dict):
        _print_dict(data)
    elif isinstance(data, list):
        _print_list(data)
    elif data is not None:
        click.echo(str(data))


def _print_dict(d: dict, indent: int = 0):
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            click.echo(f"{prefix}{k}:")
            _print_dict(v, indent + 1)
        elif isinstance(v, list):
            click.echo(f"{prefix}{k}:")
            _print_list(v, indent + 1)
        else:
            click.echo(f"{prefix}{k}: {v}")


def _print_list(items: list, indent: int = 0):
    prefix = "  " * indent
    for i, item in enumerate(items):
        if isinstance(item, dict):
            click.echo(f"{prefix}[{i}]")
            _print_dict(item, indent + 1)
        else:
            click.echo(f"{prefix}- {item}")


def handle_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except FileNotFoundError as e:
            _emit_error(str(e), "file_not_found")
        except (ValueError, IndexError, RuntimeError) as e:
            _emit_error(str(e), type(e).__name__)
        except click.ClickException:
            raise
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def _emit_error(message: str, error_type: str):
    if _json_output:
        click.echo(json.dumps({"error": message, "type": error_type}))
    else:
        click.echo(f"Error: {message}", err=True)
    if not _repl_mode:
        raise SystemExit(1)


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.option("--library", "library_path", type=str, default=None, help="Path to a calibre library")
@click.pass_context
@handle_error
def cli(ctx, use_json, library_path):
    """calibre CLI — stateful ebook library operations from the command line."""
    global _json_output
    _json_output = use_json

    if library_path:
        info = library_mod.open_library(library_path)
        get_session().open_library(info["library_path"])

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.group()
def library():
    """Library management commands."""
    pass


@library.command("open")
@click.argument("path")
@handle_error
def library_open(path):
    """Open a calibre library."""
    info = library_mod.open_library(path)
    get_session().open_library(info["library_path"])
    output(info, f"Opened library: {info['library_path']}")


@library.command("info")
@handle_error
def library_info():
    """Show library information."""
    sess = get_session()
    info = library_mod.get_library_info(sess.require_library())
    output(info)


@library.command("list-fields")
@handle_error
def library_list_fields():
    """List supported fields."""
    output(library_mod.list_fields(), "Available fields:")


@library.command("stats")
@handle_error
def library_stats():
    """Show library statistics."""
    sess = get_session()
    output(library_mod.stats(sess.require_library()))


@cli.group()
def book():
    """Book management commands."""
    pass


@book.command("list")
@click.option("--search", type=str, default=None, help="Search query")
@click.option("--limit", type=int, default=50, help="Maximum results")
@click.option("--sort-by", type=str, default=None, help="Sort field")
@click.option("--ascending", is_flag=True, help="Sort ascending")
@handle_error
def book_list(search, limit, sort_by, ascending):
    """List books in the current library."""
    sess = get_session()
    books = books_mod.list_books(sess.require_library(), search=search, limit=limit, sort_by=sort_by, ascending=ascending)
    output(books, f"Found {len(books)} books")


@book.command("get")
@click.argument("book_id", type=int)
@handle_error
def book_get(book_id):
    """Show metadata for a library book."""
    sess = get_session()
    sess.select_book(book_id)
    output(books_mod.get_book(sess.require_library(), book_id))


@book.command("add")
@click.argument("input_path")
@click.option("--title", type=str, default=None)
@click.option("--authors", type=str, default=None)
@click.option("--tags", type=str, default=None)
@click.option("--series", type=str, default=None)
@click.option("--duplicate", is_flag=True, help="Allow duplicates")
@handle_error
def book_add(input_path, title, authors, tags, series, duplicate):
    """Add a book file to the current library."""
    sess = get_session()
    sess.snapshot("Add book")
    result = books_mod.add_book(sess.require_library(), input_path, title=title, authors=authors, tags=tags, series=series, duplicate=duplicate)
    added_id = books_mod.parse_added_id(result.get("stdout", ""))
    if added_id is not None:
        sess.select_book(added_id)
        result["book_id"] = added_id
    output(result, f"Added book: {os.path.abspath(input_path)}")


@book.command("remove")
@click.argument("book_id", type=int)
@click.option("--permanent", is_flag=True, help="Delete without placing in trash")
@handle_error
def book_remove(book_id, permanent):
    """Remove a book from the current library."""
    sess = get_session()
    sess.snapshot(f"Remove book {book_id}")
    result = books_mod.remove_book(sess.require_library(), book_id, permanent=permanent)
    if sess.current_book_id == book_id:
        sess.select_book(None)
    output(result, f"Removed book {book_id}")


@book.command("search")
@click.argument("query")
@click.option("--limit", type=int, default=50)
@handle_error
def book_search(query, limit):
    """Search books in the current library."""
    sess = get_session()
    result = books_mod.search_books(sess.require_library(), query, limit=limit)
    output(result, f"Found {len(result)} books")


@book.command("set-field")
@click.argument("book_id", type=int)
@click.option("--title", type=str, default=None)
@click.option("--authors", type=str, default=None)
@click.option("--tags", type=str, default=None)
@handle_error
def book_set_field(book_id, title, authors, tags):
    """Set selected book fields using an OPF payload."""
    sess = get_session()
    sess.snapshot(f"Set metadata for book {book_id}")
    result = books_mod.set_field(sess.require_library(), book_id, title=title, authors=authors, tags=tags)
    sess.select_book(book_id)
    output(result, f"Updated fields for book {book_id}")


@cli.group()
def meta():
    """Standalone ebook metadata commands."""
    pass


@meta.command("show")
@click.argument("book_path")
@handle_error
def meta_show(book_path):
    """Show metadata from an ebook file."""
    output(metadata_mod.show_metadata(book_path))


@meta.command("set")
@click.argument("book_path")
@click.option("--title", type=str, default=None)
@click.option("--authors", type=str, default=None)
@click.option("--cover", type=str, default=None)
@click.option("--language", type=str, default=None)
@click.option("--publisher", type=str, default=None)
@click.option("--tags", type=str, default=None)
@click.option("--comments", type=str, default=None)
@handle_error
def meta_set(book_path, title, authors, cover, language, publisher, tags, comments):
    """Set metadata on an ebook file."""
    output(metadata_mod.set_metadata(book_path, title=title, authors=authors, cover=cover, language=language, publisher=publisher, tags=tags, comments=comments), f"Updated metadata: {os.path.abspath(book_path)}")


@meta.command("set-cover")
@click.argument("book_path")
@click.argument("cover_path")
@handle_error
def meta_set_cover(book_path, cover_path):
    """Set the cover image for an ebook file."""
    output(metadata_mod.set_metadata(book_path, cover=cover_path), f"Updated cover: {os.path.abspath(book_path)}")


@meta.command("clear")
@click.argument("book_path")
@click.option("--comments", "clear_comments", is_flag=True)
@click.option("--tags", "clear_tags", is_flag=True)
@handle_error
def meta_clear(book_path, clear_comments, clear_tags):
    """Clear selected metadata fields."""
    output(metadata_mod.clear_metadata_fields(book_path, clear_comments=clear_comments, clear_tags=clear_tags))


@cli.group()
def convert():
    """Format conversion commands."""
    pass


@convert.command("formats")
@handle_error
def convert_formats():
    """List common output formats."""
    output(convert_mod.list_formats(), "Formats:")


@convert.command("presets")
@handle_error
def convert_presets():
    """List conversion presets."""
    output(convert_mod.list_presets())


@convert.command("run")
@click.argument("input_path")
@click.argument("output_path")
@click.option("--preset", type=str, default=None)
@click.option("--extra-arg", "extra_args", multiple=True, help="Extra ebook-convert argument")
@handle_error
def convert_run(input_path, output_path, preset, extra_args):
    """Convert an ebook file."""
    result = convert_mod.convert_book(input_path, output_path, preset=preset, extra_args=list(extra_args))
    output(result, f"Converted: {result['output']}")


@cli.group()
def export():
    """Export and backup commands."""
    pass


@export.command("book")
@click.argument("book_ids", nargs=-1, type=int)
@click.option("--to-dir", required=True, type=str)
@click.option("--single-dir", is_flag=True)
@click.option("--formats", type=str, default=None)
@handle_error
def export_book(book_ids, to_dir, single_dir, formats):
    """Export one or more books from the current library."""
    sess = get_session()
    if not book_ids:
        raise ValueError("At least one book id is required")
    result = export_mod.export_books(sess.require_library(), list(book_ids), to_dir, single_dir=single_dir, formats=formats)
    output(result, f"Exported to: {result['output_dir']}")


@export.command("catalog")
@click.argument("output_path")
@click.option("--search", type=str, default=None)
@handle_error
def export_catalog(output_path, search):
    """Build a catalog file."""
    sess = get_session()
    result = export_mod.build_catalog(sess.require_library(), output_path, search=search)
    output(result, f"Catalog created: {result['output']}")


@export.command("backup")
@click.option("--all", "all_records", is_flag=True)
@handle_error
def export_backup(all_records):
    """Backup metadata in the current library."""
    sess = get_session()
    result = export_mod.backup_metadata(sess.require_library(), all_records=all_records)
    output(result, "Metadata backup complete")


@cli.group()
def session():
    """Session management commands."""
    pass


@session.command("status")
@handle_error
def session_status():
    """Show session status."""
    output(get_session().status())


@session.command("undo")
@handle_error
def session_undo():
    """Undo the last session state change."""
    desc = get_session().undo()
    output({"undone": desc}, f"Undone: {desc}")


@session.command("redo")
@handle_error
def session_redo():
    """Redo the last undone session state change."""
    desc = get_session().redo()
    output({"redone": desc}, f"Redone: {desc}")


@session.command("history")
@handle_error
def session_history():
    """Show session history."""
    output(get_session().list_history(), "History:")


@session.command("save")
@handle_error
def session_save():
    """Persist the session file."""
    saved = get_session().save()
    output({"saved": saved}, f"Saved session: {saved}")


@cli.command()
@handle_error
def repl():
    """Start interactive REPL session."""
    from cli_anything.calibre.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True

    skin = ReplSkin("calibre", version="1.0.0")
    skin.print_banner()
    pt_session = skin.create_prompt_session()

    commands = {
        "library": "open|info|list-fields|stats",
        "book": "list|get|add|remove|search|set-field",
        "meta": "show|set|set-cover|clear",
        "convert": "formats|presets|run",
        "export": "book|catalog|backup",
        "session": "status|undo|redo|history|save",
        "help": "Show this help",
        "quit": "Exit REPL",
    }

    while True:
        sess = get_session()
        context = sess.library_path or "no-library"
        line = skin.get_input(pt_session, project_name=context, modified=sess.status()["modified"])
        if line is None:
            break
        line = line.strip()
        if not line:
            continue
        if line.lower() in {"quit", "exit"}:
            break
        if line.lower() == "help":
            skin.help(commands)
            continue
        try:
            args = shlex.split(line)
        except ValueError as e:
            skin.error(str(e))
            continue
        try:
            cli.main(args=args, standalone_mode=False)
        except SystemExit:
            pass
        except Exception as e:
            skin.error(str(e))

    skin.print_goodbye()


def main():
    cli()
