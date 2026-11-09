"""One-shot CLI and REPL for local native Turso files."""
from dataclasses import dataclass
import json
from pathlib import Path
import shlex
import sys

import click

from . import __version__
from .core.session import SessionStore, database_path
from .core.values import TursoError, parameters, parse_json
from .utils.turso_backend import Database, create_database, dependency_info
from .utils.repl_skin import ReplSkin


@dataclass
class Runtime:
    database: str | None = None
    session: SessionStore | None = None
    as_json: bool = False
    in_repl: bool = False

    def select(self, path):
        if self.session:
            self.session.save(path)
        self.database = path

    def backend(self):
        if self.database is None:
            raise TursoError("No database selected. Use --database PATH or db create/open PATH.")
        return Database(self.database)


def emit(state, result, *, error=False):
    data = {"ok": not error, "database": state.database, **result}
    if state.as_json:
        click.echo(json.dumps(data, ensure_ascii=True, allow_nan=False), err=error)
    else:
        click.echo(json.dumps(data, ensure_ascii=True, allow_nan=False, indent=2), err=error)


def execute(args, state):
    try:
        result = cli.main(args=args, obj=state, standalone_mode=False)
        return result if isinstance(result, int) else 0
    except (TursoError, OSError, ValueError, click.ClickException) as exc:
        if "--json" in args:
            state.as_json = True
        result = {"error": str(exc)}
        if getattr(exc, "operation_index", None) is not None:
            result["operation_index"] = exc.operation_index
        emit(state, result, error=True)
        return 2 if isinstance(exc, click.UsageError) else 1
    except click.exceptions.Exit as exc:
        return exc.exit_code


@click.group(invoke_without_command=True)
@click.option("--database", type=click.Path(dir_okay=False), help="Existing local database file; never implicitly created.")
@click.option("--session", type=click.Path(dir_okay=False), help="Optional explicit selection JSON file (Unix).")
@click.option("--json", "as_json", is_flag=True, help="JSON results on stdout; JSON errors on stderr.")
@click.version_option(__version__)
@click.pass_context
def cli(ctx, database, session, as_json):
    """Operate local Turso using the required native pyturso 0.8.3 SDK.

    No subcommand starts the REPL. SQL commits per command; transaction run
    accepts structured CRUD operations. This is a trusted local SQL tool.
    """
    state = ctx.obj
    state.as_json = state.as_json or as_json
    if session:
        state.session = SessionStore(session)
        state.database = state.session.load()
    if database:
        state.database = database_path(database)
    if ctx.invoked_subcommand is None:
        return ctx.invoke(repl)


@cli.command()
@click.pass_obj
def doctor(state):
    """Discover the required SDK/native extension without opening a database."""
    emit(state, dependency_info())


@cli.command()
@click.pass_obj
def status(state):
    """Show selected identity and native engine version (if selected)."""
    emit(state, state.backend().info() if state.database else {"selected": False})


@cli.group()
def db():
    """Create/open/close the selected local database."""


@db.command("create")
@click.argument("path", type=click.Path(dir_okay=False))
@click.pass_obj
def db_create(state, path):
    """Create a new database; refuse any existing destination."""
    # Reject aliases before reserving a DB that session persistence could clobber.
    resolved = database_path(path, exists=False)
    if state.session and str(state.session.path) == resolved:
        raise TursoError("Session path and database path must differ")
    result = create_database(resolved)
    state.select(result["database"])
    emit(state, result)


@db.command("open")
@click.argument("path", type=click.Path(dir_okay=False))
@click.pass_obj
def db_open(state, path):
    """Verify and select an existing database (read-write native connection)."""
    backend = Database(path)
    result = backend.info()
    state.select(backend.path)
    emit(state, result)


@db.command("close")
@click.pass_obj
def db_close(state):
    """Clear selection; connections already close after each command."""
    state.select(None)
    emit(state, {"selected": False})


@cli.command()
@click.argument("statement")
@click.option("--params", default="[]", show_default=True, help="JSON positional array or named parameter object.")
@click.option("--limit", type=click.IntRange(1, 10000), default=100, show_default=True)
@click.pass_obj
def sql(state, statement, params, limit):
    """Execute exactly one SQL statement and explicitly commit.

    The limit caps output rows, not execution cost. Results are drained before
    commit. Transaction-control SQL cannot span commands; use transaction run.
    """
    emit(state, state.backend().sql(statement, parameters(parse_json(params)), limit))


@cli.command()
@click.pass_obj
def schema(state):
    """Inspect sqlite_schema, ordered by type/name (up to 10000 objects)."""
    emit(state, state.backend().schema())


@cli.group()
def table():
    """Inspect tables and perform bound CRUD. DDL uses sql."""


@table.command("list")
@click.pass_obj
def table_list(state):
    emit(state, state.backend().tables())


@table.command("describe")
@click.argument("name")
@click.pass_obj
def table_describe(state, name):
    emit(state, state.backend().describe(name))


@table.command("rows")
@click.argument("name")
@click.option("--where", default="{}", help="JSON equality filters; NULL uses IS NULL.")
@click.option("--limit", type=click.IntRange(1, 10000), default=100, show_default=True)
@click.pass_obj
def table_rows(state, name, where, limit):
    emit(state, state.backend().rows(name, parse_json(where), limit))


@table.command("insert")
@click.argument("name")
@click.option("--values", required=True, help="JSON object of column values.")
@click.pass_obj
def table_insert(state, name, values):
    emit(state, state.backend().mutate({"op": "insert", "table": name, "values": parse_json(values)}))


@table.command("update")
@click.argument("name")
@click.option("--values", required=True)
@click.option("--where", default="{}")
@click.option("--all", "all_rows", is_flag=True, help="Explicitly update every row.")
@click.pass_obj
def table_update(state, name, values, where, all_rows):
    emit(state, state.backend().mutate({"op": "update", "table": name, "values": parse_json(values),
                                      "where": parse_json(where), "all": all_rows}))


@table.command("delete")
@click.argument("name")
@click.option("--where", default="{}")
@click.option("--all", "all_rows", is_flag=True, help="Explicitly delete every row.")
@click.pass_obj
def table_delete(state, name, where, all_rows):
    emit(state, state.backend().mutate({"op": "delete", "table": name,
                                      "where": parse_json(where), "all": all_rows}))


@cli.group()
def transaction():
    """Atomic structured table CRUD; no raw SQL scripts or nested transactions."""


@transaction.command("run")
@click.argument("manifest", type=click.Path(dir_okay=False))
@click.pass_obj
def transaction_run(state, manifest):
    """Run a JSON array of insert/update/delete objects in BEGIN IMMEDIATE."""
    operations = parse_json(Path(manifest).read_text(encoding="utf-8"))
    emit(state, state.backend().transaction(operations))


@cli.command("export")
@click.argument("name")
@click.option("--output", required=True, type=click.Path(dir_okay=False))
@click.option("--format", "fmt", type=click.Choice(["json", "csv"]), default="json", show_default=True)
@click.option("--limit", type=click.IntRange(1, 10000), default=100, show_default=True)
@click.pass_obj
def export_table(state, name, output, fmt, limit):
    """Export bounded table rows to a new file. Not a database backup."""
    emit(state, state.backend().export(name, output, fmt, limit))


@cli.command()
@click.pass_obj
def repl(state):
    """Run the same commands with shared selection; JSON pipes emit JSON lines."""
    if state.in_repl:
        raise TursoError("Already in the REPL")
    state.in_repl = True
    try:
        return _repl_loop(state)
    finally:
        state.in_repl = False


def _repl_loop(state):
    interactive = sys.stdin.isatty() and sys.stdout.isatty() and not state.as_json
    skin = ReplSkin("turso", version=__version__, history_file="/dev/null")
    prompt = None
    if interactive:
        skin.print_banner()
        prompt = skin.create_prompt_session()
    had_error = False
    while True:
        try:
            line = skin.get_input(prompt, project_name=Path(state.database).name if state.database else None) if interactive else input()
        except (EOFError, KeyboardInterrupt):
            break
        try:
            args = shlex.split(line)
            if not args:
                continue
            if args in (["quit"], ["exit"]):
                break
            if args == ["help"]:
                if state.as_json:
                    emit(state, {"commands": list(cli.commands), "syntax": "same as CLI; quote SQL/JSON arguments"})
                else:
                    click.echo(cli.get_help(click.Context(cli, info_name="cli-anything-turso")))
                continue
            if args[0] == "repl":
                raise TursoError("Already in the REPL")
            had_error = bool(execute(args, state)) or had_error
        except (ValueError, TursoError) as exc:
            emit(state, {"error": str(exc)}, error=True)
            had_error = True
    if interactive:
        skin.print_goodbye()
    return 1 if had_error else 0


def main():
    raise SystemExit(execute(sys.argv[1:], Runtime()))


if __name__ == "__main__":
    main()
