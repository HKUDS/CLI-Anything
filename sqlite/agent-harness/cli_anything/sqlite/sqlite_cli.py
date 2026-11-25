"""One-shot and interactive commands for SQLite database workflows."""

import csv
from dataclasses import dataclass, field
import json
from pathlib import Path
import shlex
import sqlite3
import sys

import click

from cli_anything.sqlite import __version__
from cli_anything.sqlite.core import database
from cli_anything.sqlite.utils.repl_skin import ReplSkin


@dataclass
class Session:
    database: str | None = None
    json_output: bool = False
    timeout: float = 5.0
    history: list = field(default_factory=list)
    in_repl: bool = False
    command: str | None = None

    def path(self):
        if not self.database:
            raise ValueError("Select a database with --database PATH or database open PATH.")
        return self.database


def emit(session, value):
    click.echo(json.dumps(value, ensure_ascii=False, allow_nan=False,
                          indent=None if session.json_output else 2))


def json_input(value):
    try:
        return json.loads(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc


@click.group(invoke_without_command=True)
@click.option("--database", "db_path", type=click.Path(path_type=Path), help="Existing database to operate on.")
@click.option("--json", "json_output", is_flag=True, help="Emit compact JSON, including errors.")
@click.option("--timeout", type=click.FloatRange(min=0, min_open=True), default=5.0,
              show_default=True, help="SQLite operation/lock timeout in seconds.")
@click.version_option(__version__)
@click.pass_context
def cli(ctx, db_path, json_output, timeout):
    """Inspect, query, update, import/export and back up real SQLite databases.

    Query is always read-only. Execute, batch and import-csv commit atomically.
    Global options precede the command. No command starts an interactive REPL.
    """
    if ctx.obj is None:
        ctx.obj = Session()
    ctx.obj.command = ctx.invoked_subcommand or "repl"
    if db_path is not None:
        ctx.obj.database = str(db_path.expanduser().resolve())
    if json_output:
        ctx.obj.json_output = True
    if ctx.get_parameter_source("timeout") != click.core.ParameterSource.DEFAULT:
        ctx.obj.timeout = timeout
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.group("database")
def database_group():
    """Create, select, inspect, check and back up databases."""


@database_group.command("create")
@click.argument("path", type=click.Path(path_type=Path))
@click.pass_obj
def create(session, path):
    """Create a new database; an existing path is never replaced."""
    data = database.create(path)
    session.database = data["path"]
    emit(session, data)


@database_group.command("open")
@click.argument("path", type=click.Path(path_type=Path))
@click.pass_obj
def open_database(session, path):
    """Inspect a database and select it for subsequent REPL commands."""
    data = database.info(path, session.timeout)
    session.database = data["path"]
    emit(session, data)


@database_group.command("info")
@click.pass_obj
def info(session):
    """Show engine version, storage, journal mode and schema object count."""
    emit(session, database.info(session.path(), session.timeout))


@database_group.command("check")
@click.option("--full", is_flag=True, help="Use integrity_check instead of quick_check.")
@click.pass_obj
def check(session, full):
    """Check database integrity and foreign keys; exit 1 if a check fails."""
    data = database.check(session.path(), full, session.timeout)
    emit(session, data)
    if not data["ok"]:
        raise click.exceptions.Exit(1)


@database_group.command("backup")
@click.argument("output", type=click.Path(path_type=Path))
@click.pass_obj
def backup(session, output):
    """Save a consistent online backup to a new file, including committed WAL data."""
    emit(session, database.backup(session.path(), output, session.timeout))


@cli.group("schema")
def schema_group():
    """Inspect tables, views, indexes, columns and foreign keys."""


@schema_group.command("list")
@click.pass_obj
def schema_list(session):
    emit(session, database.schema(session.path(), timeout=session.timeout))


@schema_group.command("describe")
@click.argument("name")
@click.pass_obj
def schema_describe(session, name):
    emit(session, database.schema(session.path(), name, session.timeout))


@cli.command("query")
@click.argument("sql")
@click.option("--params", default="[]", help="JSON array or object of bound SQL parameters.")
@click.option("--limit", type=click.IntRange(1, 10000), default=1000, show_default=True)
@click.pass_obj
def query(session, sql, params, limit):
    """Run one read-only SQL statement and return bounded rows with column names."""
    emit(session, database.query(session.path(), sql, json_input(params), limit, session.timeout))


@cli.command("execute")
@click.argument("sql")
@click.option("--params", default="[]", help="JSON array or object of bound SQL parameters.")
@click.pass_obj
def execute(session, sql, params):
    """Execute and commit one SQL statement. This command can modify the database."""
    emit(session, database.execute(session.path(), sql, json_input(params), session.timeout))


@cli.command("batch")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_obj
def batch(session, file):
    """Commit a JSON array of {sql, params} statements as one transaction."""
    emit(session, database.batch(session.path(), json_input(file.read_text(encoding="utf-8")), session.timeout))


@cli.command("import-csv")
@click.argument("table")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_obj
def import_csv(session, table, file):
    """Atomically append UTF-8 CSV rows to an existing table, using its header columns."""
    emit(session, database.import_csv(session.path(), table, file, session.timeout))


@cli.command("export-csv")
@click.argument("sql")
@click.argument("output", type=click.Path(path_type=Path))
@click.option("--params", default="[]", help="JSON array or object of bound SQL parameters.")
@click.pass_obj
def export_csv(session, sql, output, params):
    """Stream a read-only query to a new UTF-8 CSV file, including a header."""
    emit(session, database.export_csv(session.path(), sql, output, json_input(params), session.timeout))


@cli.group("session")
def session_group():
    """Inspect the current in-memory REPL session."""


@session_group.command("status")
@click.pass_obj
def status(session):
    emit(session, {"database": session.database, "timeout": session.timeout,
                   "history_count": len(session.history)})


@session_group.command("history")
@click.pass_obj
def history(session):
    """Show recent command names and exit codes, excluding SQL and parameter values."""
    emit(session, {"history": session.history})


def invoke(args, session=None):
    """Return an exit code while preserving one JSON document on stdout per command."""
    session = session or Session(json_output="--json" in args)
    session.command = None
    try:
        code = cli.main(args=args, prog_name="cli-anything-sqlite", obj=session, standalone_mode=False)
        return code if isinstance(code, int) else 0
    except click.ClickException as exc:
        if session.json_output or "--json" in args:
            emit(Session(json_output=True), {"error": exc.format_message()})
        else:
            exc.show()
        return exc.exit_code
    except (ValueError, OSError, sqlite3.Error, sqlite3.Warning, csv.Error, OverflowError) as exc:
        if session.json_output or "--json" in args:
            emit(Session(json_output=True), {"error": str(exc)})
        else:
            click.echo(f"Error: {exc}", err=True)
        return 1
    except (KeyboardInterrupt, click.Abort):
        return 130


@cli.command("repl")
@click.pass_obj
def repl(session):
    """Start an interactive session; database selection persists until exit."""
    if session.in_repl:
        raise ValueError("Already in the REPL; enter a command or quit.")
    session.in_repl = True
    try:
        _repl_loop(session)
    finally:
        session.in_repl = False


def _repl_loop(session):
    interactive = sys.stdin.isatty() and not session.json_output
    skin = None
    prompt_session = None
    if interactive:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import InMemoryHistory

        # Preserve the shared skin without persisting SQL or parameter values.
        skin = ReplSkin("sqlite", version=__version__, history_file="")
        skin.print_banner()
        prompt_session = PromptSession(history=InMemoryHistory(), style=skin.get_prompt_style())
    # Use the unified skin on terminals; plain input also supports scripted REPLs.
    while True:
        try:
            line = (skin.get_input(prompt_session, project_name=Path(session.database).name if session.database else "")
                    if interactive else input())
        except (EOFError, KeyboardInterrupt):
            break
        if not line or not line.strip():
            continue
        if line.strip() in ("quit", "exit"):
            break
        try:
            args = shlex.split(line)
            if not args:
                continue
            code = invoke(["--help"] if args == ["help"] else args, session)
            session.history.append({"command": session.command or "<parse-error>", "exit_code": code})
            del session.history[:-100]
        except ValueError as exc:
            if session.json_output:
                emit(session, {"error": str(exc)})
            elif interactive:
                skin.error(str(exc))
            else:
                click.echo(f"Error: {exc}", err=True)
    if interactive:
        skin.print_goodbye()


def main():
    raise SystemExit(invoke(sys.argv[1:]))


if __name__ == "__main__":
    main()
