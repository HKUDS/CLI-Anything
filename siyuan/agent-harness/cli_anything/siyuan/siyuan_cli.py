"""cli-anything-siyuan — SiYuan (思源笔记) CLI harness.

Connects to a running SiYuan kernel via its HTTP API and provides
commands for notebooks, documents, blocks, search, and export.
"""

import json
import os
import sys
from typing import Any

import click

from cli_anything.siyuan.core.client import (
    SiYuanClient,
    SiYuanClientError,
    SiYuanConfig,
    load_config,
)
from cli_anything.siyuan.core.session import SessionManager


def _read_stdin() -> str:
    """Read stdin as raw bytes and decode robustly.

    PowerShell pipes text using ``$OutputEncoding`` (ASCII on Windows
    PowerShell 5.1 by default), which mangles CJK characters to ``?`` before
    Python ever sees them — that case is unrecoverable, so use ``--file``
    instead.  When the pipe is configured with a CJK code page (e.g. GBK on
    Chinese Windows), the bytes arrive GBK-encoded; we fall back from UTF-8 to
    GB18030 so those still decode correctly.

    GB18030 bytes that also form valid UTF-8 (e.g. 毛 = ``c3 ab``) decode as
    UTF-8 mojibake without raising, so the fallback never runs.  Set
    ``SIYUAN_STDIN_ENCODING`` to pin the pipe encoding explicitly when the
    sender is a CJK code page.
    """
    if sys.stdin.isatty():
        raise click.UsageError(
            "stdin pipe expected (e.g. echo 'content' | sy block insert --parent pid)"
        )
    raw = sys.stdin.buffer.read()
    pinned = os.environ.get("SIYUAN_STDIN_ENCODING", "").strip()
    if pinned:
        try:
            return raw.decode(pinned)
        except LookupError:
            raise click.UsageError(f"Unknown SIYUAN_STDIN_ENCODING: {pinned!r}")
        except UnicodeDecodeError as e:
            raise click.UsageError(f"stdin is not valid {pinned}: {e}")
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    # Neither candidate fits; decoding with errors="replace" would store
    # mojibake silently, so refuse and name the way out.
    raise click.UsageError(
        "stdin is neither UTF-8 nor GB18030. Set SIYUAN_STDIN_ENCODING to the "
        "pipe's encoding, or pass the content with --file."
    )


def _read_file(path: str) -> str:
    """Read content directly from a file as UTF-8.

    Reading from a file bypasses the PowerShell pipe encoding problem entirely,
    so CJK content survives intact.  Prefer this over stdin piping on Windows.
    """
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read()
    except OSError as e:
        raise click.UsageError(f"Cannot read file '{path}': {e}")
    except UnicodeDecodeError:
        raise click.UsageError(f"File '{path}' is not valid UTF-8.")


def _confirm_dangerous(dangerous: bool, action: str) -> None:
    """Refuse a destructive operation unless explicitly confirmed via --dangerous."""
    if not dangerous:
        raise click.ClickException(
            f"Refusing to {action} without confirmation. "
            "This is a destructive operation — pass --dangerous to confirm."
        )


def _parse_attr_pairs(pairs: tuple[str, ...]) -> dict[str, str]:
    """Parse KEY=VALUE arguments into an attribute dict.

    A value may itself contain '='; only the first one splits key from value.
    """
    attrs: dict[str, str] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            raise click.UsageError(f"Expected KEY=VALUE, got: {pair}")
        attrs[key] = value
    return attrs


def _single_use(fallback: Any) -> Any:
    """Build a callback that refuses an option given more than once.

    click's default for a non-`multiple` option is last-wins, while the REPL
    rejects a repeated option — both entry points should agree. Declaring the
    option `multiple=True` is what makes the repetition visible; the callback
    then collapses the tuple back to the single value the command expects.
    """
    def callback(ctx: click.Context, param: click.Parameter,
                 value: tuple[Any, ...]) -> Any:
        if len(value) > 1:
            raise click.UsageError(f"Option {param.opts[0]} is given more than once.")
        return value[0] if value else fallback
    return callback


def _resolve_block_data(data: str | None, file_path: str | None) -> str:
    """Resolve block content from the argument, --file, or a stdin pipe.

    Exactly one source is used; an explicit empty argument is content (it
    clears the block), while an absent one falls through to the pipe and is
    rejected when that is empty too. `--file` is checked for presence, not
    truthiness: `--file=` names no file and must not quietly become the pipe.
    """
    if file_path is not None:
        if data is not None:
            raise click.UsageError(
                "Provide block data either as an argument or via --file, not both.")
        return _read_file(file_path)
    if data is not None:
        return data
    piped = _read_stdin()
    if not piped:
        raise click.UsageError(
            "No block content provided: give it as an argument, via --file, "
            "or pipe a non-empty stdin.")
    return piped


# ── Click context ─────────────────────────────────────────────────────

class SiYuanContext:
    def __init__(self, client: SiYuanClient | None = None,
                 session: SessionManager | None = None,
                 json_output: bool = False):
        self.json_output = json_output
        self.client = client
        self.session = session or SessionManager()


class _CatchErrors(click.Group):
    """Click Group that converts SiYuanClientError to clean CLI errors."""

    def invoke(self, ctx: click.Context) -> object:
        try:
            return super().invoke(ctx)
        except SiYuanClientError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)


@click.group(cls=_CatchErrors, invoke_without_command=True)
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
@click.option("--host", multiple=True, default=None, callback=_single_use(""), help="SiYuan host (default: 127.0.0.1)")
@click.option("--port", multiple=True, default=None, type=int, callback=_single_use(0), help="SiYuan port (default: 6806)")
@click.option("--token", multiple=True, default=None, callback=_single_use(""), help="SiYuan API token")
@click.option("--config", "config_path", multiple=True, default=None, callback=_single_use(""), help="Config file path")
@click.pass_context
def cli(ctx: click.Context, json_output: bool, host: str, port: int,
        token: str, config_path: str):
    """CLI for SiYuan (思源笔记) — interact with your knowledge base.

    Connects to a running SiYuan instance via its HTTP API.
    Default: http://127.0.0.1:6806

    Configure connection via ~/.siyuan-cli.json, env vars
    (SIYUAN_HOST, SIYUAN_PORT, SIYUAN_TOKEN), or CLI flags.
    """
    # Force UTF-8 output to handle CJK characters on Windows (must stay out of
    # the docstring slot: click reads help from __doc__).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')

    session = SessionManager()
    session.load()
    cfg = load_config(config_path or None)
    if host or port or token:
        cfg = SiYuanConfig(
            host=host or cfg.host,
            port=port or cfg.port,
            token=token or cfg.token,
        )
    client = SiYuanClient(cfg)
    ctx.obj = SiYuanContext(client=client, session=session, json_output=json_output)

    if ctx.invoked_subcommand is None:
        if not client.ping():
            click.echo("Error: Cannot connect to SiYuan. Is it running?", err=True)
            click.echo("  Configure via: --host --port --token", err=True)
            click.echo("  Or set: SIYUAN_HOST, SIYUAN_PORT, SIYUAN_TOKEN", err=True)
            sys.exit(1)
        ctx.invoke(repl)


def _walk_tree(items: list[dict], depth: int = 0) -> list[dict]:
    """Recursively flatten a doc tree, setting depth on each entry.

    Returns new dicts; does not mutate the originals.
    """
    result: list[dict] = []
    for t in items:
        entry = {**t, "depth": depth}
        result.append(entry)
        children = t.get("children")
        if children:
            result.extend(_walk_tree(children, depth + 1))
    return result


def _open_notebook(client: SiYuanClient, session: SessionManager,
                   notebook_id: str) -> str:
    """Open a notebook, remember it in the session, and return its name.

    Shared by the one-shot and REPL entry points so both set the session
    fields the same way.
    """
    client.open_notebook(notebook_id)
    name = notebook_id
    for nb in client.list_notebooks():
        if nb.get("id") == notebook_id:
            name = nb.get("name", notebook_id)
            break
    session.update(current_notebook_id=notebook_id, current_notebook_name=name)
    return name


def _status_info(client: SiYuanClient, session: SessionManager) -> dict[str, Any]:
    """Live connection and session facts, shared by the two `status` commands."""
    connected = client.ping()
    version = ""
    if connected:
        try:
            version = client.get_version()
        except SiYuanClientError:
            version = ""
    state = session.state
    return {
        "connected": connected,
        "siyuan_version": version,
        "host": client.config.host,
        "port": client.config.port,
        "current_notebook": state.current_notebook_name or "",
        "current_doc": state.current_doc_path or "",
    }


# ── REPL ───────────────────────────────────────────────────────────────

def _build_repl_commands() -> dict[str, str]:
    """REPL command signatures and one-line descriptions.

    The signatures are also the usage strings reported on a bad invocation
    (`_repl_signature`), so this table is the single source for both the
    `help` listing and the error hints.
    """
    return {
        "notebook list": "List all notebooks",
        "notebook create <name>": "Create a notebook",
        "notebook rename <id> <name>": "Rename a notebook",
        "notebook remove <id> --dangerous": "Remove a notebook (destructive)",
        "notebook open <id>": "Open a notebook",
        "doc create <notebook> <path> [--md <content> | --file <path>]": "Create a document",
        "doc list <notebook> [path]": "List documents at path",
        "doc tree <notebook> [--path <path>] [--depth N]": "List document tree",
        "doc get <id>": "Get document path by ID",
        "doc rename <id> <title>": "Rename a document",
        "doc remove <id> --dangerous": "Remove a document (destructive)",
        "block insert <parent_id> <data> [--data-type <markdown|dom>] [--file <path>]": "Insert a block; content is <data> or --file",
        "block prepend <parent_id> <data> [--data-type <markdown|dom>] [--file <path>]": "Insert as the first child",
        "block append <parent_id> <data> [--data-type <markdown|dom>] [--file <path>]": "Insert as the last child",
        "block update <block_id> <data> [--data-type <markdown|dom>] [--file <path>]": "Update a block; content is <data> or --file",
        "block move <block_id> [--previous <id> | --parent <id>]": "Move a block (one destination)",
        "block delete <block_id> --dangerous": "Delete a block (destructive)",
        "block get <block_id>": "Get block kramdown source",
        "block children <block_id>": "Get child blocks",
        "asset upload <file> [<file>...] [--dir <dir>]": "Upload files as assets",
        "attr get <block-id>": "Show a block's attributes",
        "attr set <block-id> KEY=VALUE": "Set block attributes (empty value removes)",
        "attr unset <block-id> KEY [KEY...]": "Remove block attributes",
        "sql <stmt>": "Execute SQL query",
        "search <query>": "Full-text search",
        "export md <doc-id>": "Export doc as Markdown",
        "tag list": "List all tags",
        "version": "Show SiYuan kernel version",
        "status": "Show connection and session status",
        "help": "Show this help",
        "quit": "Exit REPL",
    }


def _repl_group_commands() -> frozenset[str]:
    """The commands whose second token is a subcommand.

    Derived from the help table rather than listed twice: a signature like
    `sql <stmt>` is single-word (`<stmt>` is a placeholder, not a verb), so a
    stray token after `sql` is an extra argument, not a subcommand.
    """
    groups = set()
    for signature in _build_repl_commands():
        words = signature.split()
        if len(words) > 1 and not words[1].startswith(("<", "[")):
            groups.add(words[0])
    return frozenset(groups)


_REPL_GROUP_COMMANDS = _repl_group_commands()


def _repl_group_usage(group: str) -> str:
    """`Usage: <group> <a>|<b>|…`, derived from the help table.

    Hand-written lists drifted (a bare `notebook` still offered no `open`, and
    `doc` still offered the removed `export`).
    """
    subs = [signature.split()[1] for signature in _build_repl_commands()
            if signature.startswith(f"{group} ")
            and not signature.split()[1].startswith(("<", "["))]
    return f"Usage: {group} <{'|'.join(subs)}>"


def _repl_signature(key: str) -> str:
    """Return the help-table signature for a "<command> [<verb>]" key, or ""."""
    words = key.split()
    for signature in _build_repl_commands():
        if signature.split()[:len(words)] == words:
            return signature
    return ""


def _repl_reject(skin: Any, key: str, unknown: str) -> None:
    """Report a subcommand that is either incomplete or does not exist.

    A known subcommand with missing arguments gets its real signature; an
    unknown one gets `unknown`. `Invalid doc command` for both was what made
    a missing argument indistinguishable from a typo.
    """
    signature = _repl_signature(key)
    skin.error(f"Usage: {signature}" if signature else unknown)


def _repl_positionals(tokens: list[str], value_flags: tuple[str, ...]) -> list[str]:
    """Tokens that are neither an option nor an option's value."""
    out: list[str] = []
    i = 0
    while i < len(tokens):
        if tokens[i] in value_flags:
            i += 2 if i + 1 < len(tokens) else 1
        else:
            out.append(tokens[i])
            i += 1
    return out


# Every flag the CLI defines. In the REPL a flag is an option wherever it
# appears, so one turning up in a command that does not declare it is a
# mistake, never content: `doc rename d1 --file x` used to retitle the
# document to the literal "--file x".
_REPL_KNOWN_FLAGS = frozenset({
    "--json", "--host", "--port", "--token", "--config", "--dangerous",
    "--md", "--file", "--data-type", "--dir", "--path", "--depth",
    "--previous", "--parent", "--next",
})

# Flags that consume the next token. `--md`/`--file` carry content, so a
# flag-shaped value is still data (`--md "--json"` writes the literal text);
# the rest treat a flag-shaped value as a dangling option instead.
_REPL_CONTENT_FLAGS = frozenset({"--md", "--file"})
_REPL_STRICT_VALUE_FLAGS = frozenset({
    "--dir", "--path", "--depth", "--previous", "--parent", "--data-type",
})
# Every flag that takes a value, which is also the set click's `--flag=value`
# spelling applies to.
_REPL_VALUE_FLAGS = _REPL_CONTENT_FLAGS | _REPL_STRICT_VALUE_FLAGS

# Commands whose arguments are free text rather than an option surface. Every
# token after the command reaches the kernel verbatim, so a flag-shaped one is
# not an option there: a SQL comment (`SELECT 1 --comment`) or a LIKE pattern
# (`content LIKE '--foo%'`) has no other spelling — there is no `--` terminator
# to escape it. Known flags still error in these commands (a misplaced
# `--depth` is a mistake), so only the unknown-name check is lifted.
_REPL_FREE_TEXT_COMMANDS = frozenset({"sql", "search"})


def _is_flag_token(token: str) -> bool:
    """True when a token names an option rather than being content.

    A bare `--` is not: the REPL has no `--` terminator, so it stays part of a
    SQL statement (`sql -- SELECT 1`). Anything longer after the dashes names
    something, and a name nothing declares is a typo, never text.
    """
    return token.startswith("--") and len(token) > 2


def _normalize_flag_assignments(parts: list[str]) -> list[str]:
    """Split click's `--flag=value` spelling into two tokens.

    click accepts an attached value on the command line, so the REPL has to
    accept it too: read as one bare word it fell into a positional slot and was
    written into the notebook (`block update b1 --file=x.md` stored the literal
    text `--file=x.md`, `doc create nb1 /p --md=hi` created an empty document).
    Only a value-taking flag is split, so a flag-shaped *value* stays whole.
    """
    out: list[str] = []
    for token in parts:
        head, sep, value = token.partition("=")
        if sep and head in _REPL_VALUE_FLAGS:
            out.extend((head, value))
        else:
            out.append(token)
    return out


# "<command>" or "<command> <verb>" -> the flags that command declares
_REPL_ALLOWED_FLAGS: dict[str, frozenset[str]] = {
    "notebook remove": frozenset({"--dangerous"}),
    "doc create": frozenset({"--md", "--file"}),
    "doc tree": frozenset({"--path", "--depth"}),
    "doc remove": frozenset({"--dangerous"}),
    "block insert": frozenset({"--file", "--data-type"}),
    "block prepend": frozenset({"--file", "--data-type"}),
    "block append": frozenset({"--file", "--data-type"}),
    "block update": frozenset({"--file", "--data-type"}),
    "block delete": frozenset({"--dangerous"}),
    "block move": frozenset({"--previous", "--parent"}),
    "asset upload": frozenset({"--dir"}),
}

# Exact positional count per command. Commands whose last argument is variadic
# (a joined name/title, block content, an SQL statement) are left out.
_REPL_MAX_POSITIONALS: dict[str, int] = {
    "notebook list": 0,
    "notebook open": 1,
    "notebook remove": 1,
    "doc create": 2,
    "doc list": 2,
    "doc tree": 1,
    "doc get": 1,
    "doc remove": 1,
    "block move": 1,
    "block delete": 1,
    "block get": 1,
    "block children": 1,
    "attr get": 1,
    "export md": 1,
    "tag list": 0,
    "version": 0,
    "status": 0,
}


@cli.command()
@click.pass_context
def repl(ctx: click.Context):
    """Start interactive REPL mode."""
    from cli_anything.siyuan.utils.repl_skin import ReplSkin

    obj: SiYuanContext = ctx.obj

    try:
        kernel_version = obj.client.get_version()
    except SiYuanClientError:
        kernel_version = "?"
    skin = ReplSkin("siyuan", version=kernel_version)
    skin.print_banner()

    try:
        pt_session = skin.create_prompt_session()
    except Exception as e:
        # prompt_toolkit needs a real console; a piped stdin (or a Windows shell
        # without a console buffer) would otherwise surface a raw traceback.
        skin.error(f"REPL needs an interactive console ({e}).")
        skin.info("Use one-shot commands instead, e.g. `cli-anything-siyuan notebook list`.")
        return
    commands = _build_repl_commands()

    state = obj.session.state

    while True:
        ctx_str = ""
        if state.current_notebook_name:
            ctx_str = state.current_notebook_name
        try:
            user_input = skin.get_input(
                pt_session,
                project_name=state.current_doc_path or "",
                modified=False,
                context=ctx_str,
            )
        except (KeyboardInterrupt, EOFError):
            obj.session.flush()
            break

        if not user_input:
            continue

        # `help`/`quit` are REPL-local, so they never reach the dispatcher.
        word = user_input.strip()
        if word in ("quit", "exit", "q"):
            obj.session.flush()
            break

        if word == "help":
            skin.help(commands)
            continue

        try:
            _dispatch_repl(skin, obj, user_input)
        except SiYuanClientError as e:
            skin.error(str(e))
        except Exception as e:
            skin.error(f"Error: {e}")

    skin.print_goodbye()


class _UnmatchedQuote(ValueError):
    """Raised when the REPL input has an unclosed quote."""


def _tokenize_repl(line: str) -> list[str]:
    r"""Split a REPL line into tokens, keeping literal backslashes.

    shlex (posix) treats ``\`` outside quotes as an escape, so a Windows path
    like ``--file C:\data\note.md`` silently loses its backslashes. Here single
    quotes are fully literal and double quotes only treat ``\\``/``\"`` as
    escapes; everything else (including bare ``\``) is kept verbatim.
    """
    tokens: list[str] = []
    cur: list[str] = []
    quote = ""
    quoted = False
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if quote:
            if ch == quote:
                quote = ""
            elif quote == '"' and ch == "\\" and i + 1 < n and line[i + 1] in '\\"':
                cur.append(line[i + 1])
                i += 1
            else:
                cur.append(ch)
        elif ch in "'\"":
            quote = ch
            quoted = True
        elif ch in " \t":
            if cur or quoted:
                tokens.append("".join(cur))
                cur = []
                quoted = False
        else:
            cur.append(ch)
        i += 1
    if cur or quoted:
        tokens.append("".join(cur))
    if quote:
        raise _UnmatchedQuote(line)
    return tokens


def _dispatch_repl(skin: Any, ctx: SiYuanContext, cmd: str) -> None:
    """Parse REPL command and route to the appropriate handler."""
    try:
        parts = _tokenize_repl(cmd.strip())
    except _UnmatchedQuote:
        skin.error("Unmatched quote in command — add the closing quote or remove it.")
        return
    if not parts:
        return

    client = ctx.client
    session = ctx.session

    # Each flag has exactly one meaning; a known flag in the wrong place errors
    # rather than being silently treated as content. A token that is the value
    # of an option is data, not a flag.
    json_mode = parts[0] == "--json"
    if json_mode:
        parts = parts[1:]
    if not parts:
        return

    # click accepts `--flag=value`, so the REPL does too. The free-text commands
    # are exempt: their tail is one argument, and a SQL fragment such as
    # `content = '--file=y'` must not be split into options.
    if parts[0] not in _REPL_FREE_TEXT_COMMANDS:
        parts = _normalize_flag_assignments(parts)

    value_idx: set[int] = set()
    dangling: list[str] = []
    j = 0
    while j < len(parts) - 1:
        if parts[j] not in _REPL_VALUE_FLAGS:
            j += 1
        elif parts[j] in _REPL_CONTENT_FLAGS or not parts[j + 1].startswith("--"):
            value_idx.add(j + 1)
            j += 2
        else:
            # Dangling: `--previous --parent p1` must not eat "--parent", or
            # "p1" is left looking like a stray positional. Reported before the
            # checks below so the nearest cause wins over the flag it collided
            # with: `--data-type --json` is a missing value, not a misplaced
            # `--json`.
            if parts[j] in _REPL_STRICT_VALUE_FLAGS:
                dangling.append(parts[j])
            j += 1
    if dangling:
        skin.error(f"Option {dangling[0]} requires a value.")
        return
    stray = {p for k, p in enumerate(parts) if k not in value_idx}
    if "--json" in stray:
        skin.error("--json must come before the command (e.g. `--json notebook list`)")
        return

    command = parts[0]
    # A verb exists only after a group command, and a flag where the verb would
    # be is not one: `search --dangerous` must report the usage of `search`,
    # and `version extra` must treat `extra` as an argument, not a subcommand.
    verb = (parts[1] if command in _REPL_GROUP_COMMANDS and len(parts) > 1
            and not parts[1].startswith("--") else "")
    key = f"{command} {verb}" if verb else command
    allowed = _REPL_ALLOWED_FLAGS.get(key, frozenset())

    dangerous = False
    if "--dangerous" in stray and "--dangerous" in allowed:
        dangerous = True
        parts = [p for k, p in enumerate(parts)
                 if not (k not in value_idx and p == "--dangerous")]
        stray = stray - {"--dangerous"}

    # A flag is an option wherever it appears, so a name this command does not
    # declare is a mistake, never content — whether the command knows the flag
    # at all (`doc list nb1 --depth 2` queried the path "--depth") or the token
    # is a typo (`doc rename d1 --flie x` retitled the document to "--flie x").
    misplaced = sorted(p for p in stray
                       if _is_flag_token(p) and p in _REPL_KNOWN_FLAGS
                       and p not in allowed)
    if misplaced:
        hint = f" (accepts {', '.join(sorted(allowed))})" if allowed else ""
        skin.error(f"{misplaced[0]} is not an option here{hint}. "
                   f"Usage: {_repl_signature(key) or key}")
        return
    unknown = [] if command in _REPL_FREE_TEXT_COMMANDS else sorted(
        p for p in stray if _is_flag_token(p) and p not in _REPL_KNOWN_FLAGS)
    if unknown:
        skin.error(f"Unknown option: {unknown[0]}. "
                   f"Usage: {_repl_signature(key) or key}")
        return

    # Fixed-arity commands reject leftover positionals: `doc list nb1 a b` and
    # `doc get d1 extra` used to drop the extra argument without a word. The
    # filter has to agree with `_is_flag_token`, or a bare `--` is dropped from
    # the count while the handler still reads it as the argument itself.
    limit = _REPL_MAX_POSITIONALS.get(key)
    if limit is not None:
        positionals = [p for k, p in enumerate(parts)
                       if k not in value_idx and not _is_flag_token(p)]
        # The REPL has no `--` terminator, so one here can only be a mistake:
        # `doc list -- nb1` listed the notebook named "--". Variadic commands
        # keep it as content (`block update b1 a -- b`).
        if "--" in positionals:
            skin.error(f"A bare `--` is not a terminator here. "
                       f"Usage: {_repl_signature(key) or key}")
            return
        extra = positionals[1 + (1 if verb else 0) + limit:]
        if extra:
            skin.error(f"Unexpected argument: {extra[0]}. "
                       f"Usage: {_repl_signature(key) or key}")
            return

    try:
        if command == "notebook":
            _handle_notebook_repl(skin, client, session, parts, json_mode, dangerous)
        elif command == "doc":
            _handle_doc_repl(skin, client, session, parts, json_mode, dangerous)
        elif command == "block":
            _handle_block_repl(skin, client, parts, json_mode, dangerous)
        elif command == "asset":
            _handle_asset_repl(skin, client, parts, json_mode)
        elif command == "attr":
            _handle_attr_repl(skin, client, parts, json_mode)
        elif command == "sql":
            _handle_sql_repl(skin, client, _free_text_remainder(cmd, command), json_mode)
        elif command == "search":
            _handle_search_repl(skin, client, _free_text_remainder(cmd, command), json_mode)
        elif command == "tag":
            _handle_tag_repl(skin, client, parts, json_mode)
        elif command == "version":
            _handle_version_repl(skin, client, json_mode)
        elif command == "status":
            _handle_status_repl(skin, client, session, json_mode)
        elif command == "export":
            if len(parts) < 2:
                skin.error(f"Usage: {_repl_signature('export md')}")
                return
            _handle_export_repl(skin, client, parts, json_mode)
        else:
            skin.error(f"Unknown command: {command}")
    except click.UsageError as e:
        # Option parsing problems (dangling option, conflicting anchors) are
        # user errors, not crashes.
        skin.error(str(e))


# ── REPL sub-handlers ──────────────────────────────────────────────────

def _handle_notebook_repl(skin: Any, client: SiYuanClient,
                          session: SessionManager, parts: list[str],
                          json_mode: bool, dangerous: bool = False) -> None:
    if len(parts) < 2:
        skin.error(_repl_group_usage("notebook"))
        return
    sub = parts[1]
    if sub == "list":
        notebooks = client.list_notebooks()
        if json_mode:
            click.echo(json.dumps(notebooks, ensure_ascii=False))
        else:
            skin.table(["ID", "Name", "Icon", "Closed"],
                       [[n["id"], n["name"], n.get("icon", ""), str(n.get("closed", ""))]
                        for n in notebooks])
    elif sub == "create" and len(parts) >= 3:
        name = " ".join(parts[2:])
        nb = client.create_notebook(name)
        session.update(current_notebook_id=nb["id"], current_notebook_name=nb["name"])
        client.open_notebook(nb["id"])
        if json_mode:
            click.echo(json.dumps(nb, ensure_ascii=False))
        else:
            skin.success(f'Created notebook: {nb["name"]} ({nb["id"]})')
    elif sub == "open" and len(parts) >= 3:
        name = _open_notebook(client, session, parts[2])
        if json_mode:
            click.echo(json.dumps({"opened": parts[2], "name": name}, ensure_ascii=False))
        else:
            skin.success(f"Opened notebook: {name} ({parts[2]})")
    elif sub == "rename" and len(parts) >= 4:
        name = " ".join(parts[3:])
        client.rename_notebook(parts[2], name)
        if json_mode:
            click.echo(json.dumps({"renamed": parts[2], "name": name}, ensure_ascii=False))
        else:
            skin.success("Renamed")
    elif sub == "remove" and len(parts) >= 3:
        if not dangerous:
            skin.error("Refusing to remove a notebook without confirmation. Add --dangerous.")
            return
        client.remove_notebook(parts[2])
        if json_mode:
            click.echo(json.dumps({"removed": parts[2]}, ensure_ascii=False))
        else:
            skin.success("Removed")
    else:
        _repl_reject(skin, f"notebook {sub}", f"Unknown notebook command: {sub}")


def _handle_doc_repl(skin: Any, client: SiYuanClient,
                     session: SessionManager, parts: list[str],
                     json_mode: bool, dangerous: bool = False) -> None:
    if len(parts) < 2:
        skin.error(_repl_group_usage("doc"))
        return
    sub = parts[1]
    if sub == "create" and len(parts) >= 4:
        parsed = _parse_repl_content_source(parts, 2, skin, ("--md", "--file"))
        if parsed is None:
            return
        rest, values = parsed
        # Stripping --md/--file may have removed the positionals themselves
        # (e.g. `doc create nb1 --file note.md`); recheck before indexing.
        if len(rest) < 2:
            skin.error(f"Usage: {_repl_signature('doc create')}")
            return
        # Presence, not truthiness: `--md "" --file note.md` gave both sources
        # and used to pick the file without saying so.
        if "--md" in values and "--file" in values:
            skin.error("Use either --md or --file, not both.")
            return
        content = values.get("--md", "")
        if "--file" in values:
            content = _read_file(values["--file"])
        nb_id = rest[0]
        doc_path = rest[1]
        doc_id = client.create_doc_with_md(nb_id, doc_path, content)
        session.update(current_doc_id=doc_id, current_doc_path=doc_path)
        if json_mode:
            click.echo(json.dumps({"id": doc_id}, ensure_ascii=False))
        else:
            skin.success(f"Created doc: {doc_id}")
    elif sub == "list" and len(parts) >= 3:
        docs = client.list_docs_by_path(parts[2], parts[3] if len(parts) >= 4 else "/")
        items = docs.get("files", []) if isinstance(docs, dict) else docs
        if json_mode:
            click.echo(json.dumps(items, ensure_ascii=False))
        else:
            skin.table(["ID", "Name", "Type"],
                       [[d.get("id", ""), d.get("name", ""), d.get("type", "")]
                        for d in items])
    elif sub == "tree" and len(parts) >= 3:
        path = _repl_opt(parts[3:], "--path") or "/"
        depth = _repl_int(parts[3:], "--depth", -1)
        tree = client.list_doc_tree(parts[2], path=path, max_depth=depth)
        if isinstance(tree, dict):
            items = tree.get("files") or tree.get("tree") or []
        else:
            items = tree
        if json_mode:
            click.echo(json.dumps(items, ensure_ascii=False))
        else:
            skin.table(["ID", "Name", "Path"],
                       [[t.get("id", ""), "  " * t.get("depth", 0) + t.get("name", ""), t.get("path", "")]
                        for t in _walk_tree(items)])
    elif sub == "get" and len(parts) >= 3:
        hpath = client.get_hpath_by_id(parts[2])
        if json_mode:
            click.echo(json.dumps({"hpath": hpath}, ensure_ascii=False))
        else:
            skin.success(f"Path: {hpath}")
    elif sub == "rename" and len(parts) >= 4:
        title = " ".join(parts[3:])
        client.rename_doc_by_id(parts[2], title)
        if json_mode:
            click.echo(json.dumps({"renamed": parts[2], "title": title}, ensure_ascii=False))
        else:
            skin.success("Renamed")
    elif sub == "remove" and len(parts) >= 3:
        if not dangerous:
            skin.error("Refusing to remove a document without confirmation. Add --dangerous.")
            return
        client.remove_doc_by_id(parts[2])
        if json_mode:
            click.echo(json.dumps({"removed": parts[2]}, ensure_ascii=False))
        else:
            skin.success("Removed")
    elif sub == "export":
        # Documents are exported through the `export` command; `doc export`
        # used to be a second spelling of the same thing.
        skin.error(f"Usage: {_repl_signature('export md')} (export lives in the "
                   f"`export` command, not `doc`)")
    else:
        _repl_reject(skin, f"doc {sub}", f"Unknown doc command: {sub}")


def _parse_repl_content_source(parts: list[str], start: int, skin: Any,
                               flags: tuple[str, ...] = ("--file",),
                               ) -> tuple[list[str], dict[str, str]] | None:
    """Split parts[start:] into (positionals, option values).

    `flags` are the options the command declares. Each is an option anywhere in
    the content slot and takes the next token as its value, so that value is
    literal data (`--md "--json"` writes the text) when the flag carries content.
    A strict value-taking flag is not a content slot though: its value must be a
    real token (`--data-type --json` is a missing value, not the type "--json").
    Every other token, including a flag-shaped one, is content. Returns None
    after reporting a dangling or repeated option, which the caller must not
    guess around.
    """
    rest: list[str] = []
    values: dict[str, str] = {}
    i = start
    while i < len(parts):
        p = parts[i]
        if p not in flags:
            rest.append(p)
            i += 1
            continue
        if i + 1 >= len(parts):
            skin.error(f"Option {p} requires a value.")
            return None
        value = parts[i + 1]
        # A strict option's value is a value, not more options and not nothing:
        # `--previous --parent p1` must not read "--parent" as an ID, and an
        # empty one (`--data-type=`) must not fall through to the default. A
        # content option keeps its literal value, empty included, because an
        # explicit empty argument is meaningful there.
        if p in _REPL_STRICT_VALUE_FLAGS and (not value or _is_flag_token(value)):
            skin.error(f"Option {p} requires a value.")
            return None
        if p in values:
            skin.error(f"Option {p} is given more than once.")
            return None
        values[p] = value
        i += 2
    return rest, values


def _parse_repl_block_write(parts: list[str], skin: Any,
                            usage: str) -> tuple[str, str, str] | None:
    """Parse `<block_id> [<data> | --file <path>] [--data-type <type>]`.

    Returns (target_id, data, data_type), or None after reporting the error. A
    stray flag never gets this far: `_dispatch_repl` rejects a flag the command
    does not declare before dispatching, so an anchor cannot be swallowed as
    content.
    """
    parsed = _parse_repl_content_source(parts, 2, skin, ("--file", "--data-type"))
    if parsed is None:
        return None
    rest, values = parsed
    file_path = values.get("--file", "")
    # Presence, not truthiness: the parser already refused an empty value, so a
    # missing key is the only way to get the default.
    data_type = values.get("--data-type", "markdown")
    if not rest:
        skin.error(f"Usage: {usage}")
        return None
    target_id = rest[0]
    has_data_arg = len(rest) > 1
    data = " ".join(rest[1:]) if has_data_arg else ""
    if file_path:
        if has_data_arg:
            skin.error("Provide block data either as an argument or via --file, not both.")
            return None
        try:
            data = _read_file(file_path)
        except click.UsageError as e:
            skin.error(str(e))
            return None
    elif not has_data_arg:
        skin.error("Provide block data either as an argument or via --file.")
        return None
    return target_id, data, data_type


def _repl_opt(tokens: list[str], name: str) -> str:
    """Return the value following `name` in REPL tokens, or "" when absent.

    Raises UsageError when the flag is dangling, repeated, or its value is
    itself a flag: `--previous --parent p1` must not read "--parent" as an ID.
    An empty value (`--depth=` gave one) is rejected too — the caller treats
    "" as "not given" and would fall back to its default in silence.
    """
    if name not in tokens:
        return ""
    if tokens.count(name) > 1:
        raise click.UsageError(f"Option {name} is given more than once.")
    i = tokens.index(name)
    value = tokens[i + 1] if i + 1 < len(tokens) else ""
    if not value or value.startswith("--"):
        raise click.UsageError(f"Option {name} requires a value.")
    return value


def _repl_int(tokens: list[str], name: str, default: int) -> int:
    """Return the integer value of `name`, or `default` when absent."""
    raw = _repl_opt(tokens, name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise click.UsageError(f"Option {name} expects an integer, got {raw!r}")


def _handle_block_repl(skin: Any, client: SiYuanClient,
                       parts: list[str], json_mode: bool,
                       dangerous: bool = False) -> None:
    if len(parts) < 2:
        skin.error(_repl_group_usage("block"))
        return
    sub = parts[1]
    if sub in ("insert", "prepend", "append", "update"):
        usage = _repl_signature(f"block {sub}")
        parsed = _parse_repl_block_write(parts, skin, usage)
        if parsed is None:
            return
        target_id, data, data_type = parsed
        if sub == "insert":
            result = client.insert_block(data_type, data, parent_id=target_id)
            if json_mode:
                click.echo(json.dumps(result, ensure_ascii=False))
            else:
                skin.success("Block inserted")
        elif sub == "prepend":
            result = client.prepend_block(data_type, data, target_id)
            if json_mode:
                click.echo(json.dumps(result, ensure_ascii=False))
            else:
                skin.success("Block prepended")
        elif sub == "append":
            result = client.append_block(data_type, data, target_id)
            if json_mode:
                click.echo(json.dumps(result, ensure_ascii=False))
            else:
                skin.success("Block appended")
        else:
            client.update_block(data_type, data, target_id)
            if json_mode:
                click.echo(json.dumps({"updated": target_id}, ensure_ascii=False))
            else:
                skin.success("Block updated")
    elif sub == "move":
        if len(parts) < 3:
            skin.error(f"Usage: {_repl_signature('block move')}")
            return
        block_id = parts[2]
        previous = _repl_opt(parts[3:], "--previous")
        parent = _repl_opt(parts[3:], "--parent")
        if not previous and not parent:
            skin.error("A destination is required: --previous <id> or --parent <id>")
            return
        if previous and parent:
            skin.error("Give either --previous or --parent, not both")
            return
        client.move_block(block_id, previous_id=previous, parent_id=parent)
        if json_mode:
            click.echo(json.dumps({"moved": block_id, "previousID": previous,
                                   "parentID": parent}, ensure_ascii=False))
        else:
            skin.success("Block moved")
    elif sub == "delete" and len(parts) >= 3:
        if not dangerous:
            skin.error("Refusing to delete a block without confirmation. Add --dangerous.")
            return
        client.delete_block(parts[2])
        if json_mode:
            click.echo(json.dumps({"deleted": parts[2]}, ensure_ascii=False))
        else:
            skin.success("Block deleted")
    elif sub == "get" and len(parts) >= 3:
        kramdown = client.get_block_kramdown(parts[2])
        if json_mode:
            click.echo(json.dumps({"kramdown": kramdown}, ensure_ascii=False))
        else:
            click.echo(kramdown)
    elif sub == "children" and len(parts) >= 3:
        children = client.get_child_blocks(parts[2])
        if json_mode:
            click.echo(json.dumps(children, ensure_ascii=False))
        else:
            skin.table(["ID", "Type", "SubType"],
                       [[c.get("id", ""), c.get("type", ""), c.get("subType", "")]
                        for c in children])
    elif sub == "child":
        # `block child` was an undocumented second spelling of `children`, and
        # being unlisted it also slipped past the positional-count check.
        skin.error(f"Usage: {_repl_signature('block children')} (the subcommand "
                   f"is `children`)")
    else:
        _repl_reject(skin, f"block {sub}", f"Unknown block command: {sub}")


def _handle_asset_repl(skin: Any, client: SiYuanClient,
                       parts: list[str], json_mode: bool) -> None:
    usage = f"Usage: {_repl_signature('asset upload')}"
    if len(parts) < 2:
        skin.error(usage)
        return
    if parts[1] != "upload":
        _repl_reject(skin, f"asset {parts[1]}", f"Unknown asset command: {parts[1]}")
        return
    assets_dir = _repl_opt(parts[2:], "--dir") or "/assets/"
    files = _repl_positionals(parts[2:], ("--dir",))
    if not files:
        skin.error(usage)
        return
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        skin.error("File not found: " + ", ".join(missing))
        return
    result = client.upload_asset(files, assets_dir_path=assets_dir)
    succ = result.get("succMap", {}) if isinstance(result, dict) else {}
    errs = result.get("errFiles", []) if isinstance(result, dict) else []
    if json_mode:
        click.echo(json.dumps({"succMap": succ, "errFiles": errs}, ensure_ascii=False))
    else:
        for src, dest in succ.items():
            click.echo(f"{dest}\t<- {src}")
        skin.success(f"Uploaded {len(succ)} asset(s)")
    if errs:
        skin.error("Upload failed for: " + ", ".join(errs))


def _handle_attr_repl(skin: Any, client: SiYuanClient,
                      parts: list[str], json_mode: bool) -> None:
    if len(parts) < 3:
        skin.error(_repl_group_usage("attr"))
        return
    sub, block_id = parts[1], parts[2]
    if sub == "get":
        attrs = client.get_block_attrs(block_id)
        if json_mode:
            click.echo(json.dumps(attrs, ensure_ascii=False))
        elif not attrs:
            skin.info("No attributes")
        else:
            skin.table(["Attribute", "Value"],
                       [[k, attrs[k]] for k in sorted(attrs)])
    elif sub == "set":
        if len(parts) < 4:
            skin.error(f"Usage: {_repl_signature('attr set')}")
            return
        try:
            attrs = _parse_attr_pairs(tuple(parts[3:]))
        except click.UsageError as e:
            skin.error(str(e))
            return
        client.set_block_attrs(block_id, attrs)
        if json_mode:
            click.echo(json.dumps({"updated": block_id, "attrs": attrs}, ensure_ascii=False))
        else:
            skin.success(f"Set {len(attrs)} attribute(s)")
    elif sub == "unset":
        if len(parts) < 4:
            skin.error(f"Usage: {_repl_signature('attr unset')}")
            return
        keys = list(parts[3:])
        client.set_block_attrs(block_id, {key: "" for key in keys})
        if json_mode:
            click.echo(json.dumps({"updated": block_id, "removed": keys}, ensure_ascii=False))
        else:
            skin.success(f"Removed {len(keys)} attribute(s)")
    else:
        _repl_reject(skin, f"attr {sub}", f"Unknown attr command: {sub}")


def _free_text_remainder(line: str, command: str) -> str:
    """The rest of the line after the command, exactly as typed.

    Tokenizing drops the quotes a statement needs — `WHERE '1' = '01'` reached
    the kernel as `WHERE 1 = 01`, a different query with a different answer.
    The token list is still used to validate flags; only the text sent on is
    taken verbatim.

    The documented spelling wraps the whole statement in quotes
    (`sql "SELECT … LIKE '%k%'"`), so one wrapping pair is unwrapped the way the
    tokenizer used to — but only when the remainder really is that single
    quoted token, never for `"a" || "b"`.
    """
    text = line.strip()
    if text.startswith("--json"):
        text = text[len("--json"):].lstrip()
    if not text.startswith(command):
        return ""  # unreachable: the tokenizer found this command first
    text = text[len(command):].lstrip()
    if len(text) > 1 and text[0] in "\"'" and text[-1] == text[0]:
        try:
            tokens = _tokenize_repl(text)
        except _UnmatchedQuote:
            return text
        if len(tokens) == 1 and tokens[0] == text[1:-1]:
            return tokens[0]
    return text


def _handle_sql_repl(skin: Any, client: SiYuanClient,
                     stmt: str, json_mode: bool) -> None:
    if not stmt:
        skin.error(f"Usage: {_repl_signature('sql')}")
        return
    results = client.query_sql(stmt)
    if json_mode:
        click.echo(json.dumps(results, ensure_ascii=False))
    elif not results:
        skin.info("No results")
    else:
        headers = list(results[0].keys())
        rows = [[str(r.get(h, "")) for h in headers] for r in results]
        skin.table(headers, rows)


def _handle_search_repl(skin: Any, client: SiYuanClient,
                        query: str, json_mode: bool) -> None:
    if not query:
        skin.error(f"Usage: {_repl_signature('search')}")
        return
    data = client.search_blocks(query)
    blocks = data.get("blocks", []) if isinstance(data, dict) else data
    matched = data.get("matchedBlockCount") if isinstance(data, dict) else None
    if json_mode:
        click.echo(json.dumps(blocks, ensure_ascii=False))
    elif not blocks:
        skin.info("No results")
    else:
        skin.table(["ID", "Content"],
                   [[r.get("id", ""), r.get("content", "")[:80]] for r in blocks])
        if matched is not None and matched > len(blocks):
            skin.info(f"...showing {len(blocks)} of {matched} matches; use `sql` for complete results")


def _handle_export_repl(skin: Any, client: SiYuanClient,
                        parts: list[str], json_mode: bool) -> None:
    if parts[1] == "md" and len(parts) >= 3:
        md = client.export_md_content(parts[2])
        if json_mode:
            click.echo(json.dumps(md, ensure_ascii=False))
        else:
            skin.section(md.get("hPath", ""))
            click.echo(md.get("content", ""))
    else:
        _repl_reject(skin, f"export {parts[1]}", f"Unknown export command: {parts[1]}")


def _handle_tag_repl(skin: Any, client: SiYuanClient,
                     parts: list[str], json_mode: bool) -> None:
    if len(parts) < 2 or parts[1] != "list":
        _repl_reject(skin, f"tag {parts[1]}" if len(parts) > 1 else "tag",
                     "Usage: tag list")
        return
    tags = client.get_tags()
    if json_mode:
        click.echo(json.dumps(tags, ensure_ascii=False))
    else:
        _print_tags(tags)


def _handle_version_repl(skin: Any, client: SiYuanClient,
                         json_mode: bool) -> None:
    ver = client.get_version()
    if json_mode:
        click.echo(json.dumps({"version": ver}, ensure_ascii=False))
    else:
        skin.success(f"SiYuan version: {ver}")


def _handle_status_repl(skin: Any, client: SiYuanClient,
                        session: SessionManager, json_mode: bool) -> None:
    info = _status_info(client, session)
    if json_mode:
        click.echo(json.dumps(info, ensure_ascii=False))
    else:
        version = info["siyuan_version"]
        skin.status_block({
            "Connected": str(info["connected"]),
            "SiYuan": f"v{version}" if version else "(unknown)",
            "Host": f"{info['host']}:{info['port']}",
            "Notebook": info["current_notebook"] or "(none)",
            "Document": info["current_doc"] or "(none)",
        }, title="Status")


# ── Notebook commands ──────────────────────────────────────────────────

@cli.group()
def notebook():
    """Manage notebooks (笔记本)."""


@notebook.command("list")
@click.pass_obj
def notebook_list(ctx: SiYuanContext):
    """List all notebooks."""
    notebooks = ctx.client.list_notebooks()
    if ctx.json_output:
        click.echo(json.dumps(notebooks, ensure_ascii=False))
    else:
        click.echo(f"{'ID':<30} {'Name':<30} {'Closed':<8}")
        click.echo("-" * 70)
        for nb in notebooks:
            click.echo(f"{nb['id']:<30} {nb['name']:<30} {str(nb.get('closed', '')):<8}")


@notebook.command("create")
@click.argument("name")
@click.pass_obj
def notebook_create(ctx: SiYuanContext, name: str):
    """Create a new notebook."""
    nb = ctx.client.create_notebook(name)
    if ctx.json_output:
        click.echo(json.dumps(nb, ensure_ascii=False))
    else:
        click.echo(f"Created notebook: {nb['name']} ({nb['id']})")


@notebook.command("remove")
@click.argument("notebook_id")
@click.option("--dangerous", is_flag=True, help="Explicit confirmation to delete.")
@click.pass_obj
def notebook_remove(ctx: SiYuanContext, notebook_id: str, dangerous: bool):
    """Remove a notebook by ID (requires --dangerous confirmation)."""
    _confirm_dangerous(dangerous, "remove this notebook")
    ctx.client.remove_notebook(notebook_id)
    if ctx.json_output:
        click.echo(json.dumps({"removed": notebook_id}, ensure_ascii=False))
    else:
        click.echo(f"Removed notebook: {notebook_id}")


@notebook.command("rename")
@click.argument("notebook_id")
@click.argument("name")
@click.pass_obj
def notebook_rename(ctx: SiYuanContext, notebook_id: str, name: str):
    """Rename a notebook."""
    ctx.client.rename_notebook(notebook_id, name)
    if ctx.json_output:
        click.echo(json.dumps({"renamed": notebook_id, "name": name}, ensure_ascii=False))
    else:
        click.echo(f"Renamed notebook {notebook_id} to: {name}")


@notebook.command("open")
@click.argument("notebook_id")
@click.pass_obj
def notebook_open(ctx: SiYuanContext, notebook_id: str):
    """Open a notebook."""
    name = _open_notebook(ctx.client, ctx.session, notebook_id)
    ctx.session.flush()
    if ctx.json_output:
        click.echo(json.dumps({"opened": notebook_id, "name": name}, ensure_ascii=False))
    else:
        click.echo(f"Opened notebook: {name} ({notebook_id})")


# ── Document commands ──────────────────────────────────────────────────

@cli.group()
def doc():
    """Manage documents (文档)."""


@doc.command("create")
@click.argument("notebook_id")
@click.argument("path")
@click.option("--md", multiple=True, default=None, callback=_single_use(None), help="Markdown content.")
@click.option("--file", "file_path", multiple=True, default=None, callback=_single_use(None), help="Read markdown content from a UTF-8 file (avoids PowerShell pipe encoding issues).")
@click.pass_obj
def doc_create(ctx: SiYuanContext, notebook_id: str, path: str,
               md: str | None, file_path: str | None):
    """Create a document with optional Markdown content.

    Prefer --file for content with CJK or special characters
    (backticks, quotes, parentheses) to avoid shell escaping:
      sy doc create nb1 /test --file note.md
    """
    # Presence, not truthiness: `--md "" --file note.md` gave both sources and
    # used to pick the file without saying so.
    if md is not None and file_path is not None:
        raise click.UsageError("Use either --md or --file, not both.")
    if file_path is not None:
        md = _read_file(file_path)
    doc_id = ctx.client.create_doc_with_md(notebook_id, path, md or "")
    if ctx.json_output:
        click.echo(json.dumps({"id": doc_id}, ensure_ascii=False))
    else:
        click.echo(f"Created doc: {doc_id}")


@doc.command("list")
@click.argument("notebook_id")
@click.argument("path", default="/")
@click.pass_obj
def doc_list(ctx: SiYuanContext, notebook_id: str, path: str):
    """List documents at a path."""
    docs = ctx.client.list_docs_by_path(notebook_id, path)
    items = docs.get("files", []) if isinstance(docs, dict) else docs
    if ctx.json_output:
        click.echo(json.dumps(items, ensure_ascii=False))
    else:
        click.echo(f"{'ID':<30} {'Name':<30} {'Type':<10}")
        click.echo("-" * 70)
        for d in items:
            click.echo(f"{d.get('id', ''):<30} {d.get('name', ''):<30} {d.get('type', ''):<10}")


@doc.command("tree")
@click.argument("notebook_id")
@click.option("--path", multiple=True, default=None, callback=_single_use("/"), help="Root path")
@click.option("--depth", multiple=True, default=None, type=int, callback=_single_use(-1), help="Max depth")
@click.pass_obj
def doc_tree(ctx: SiYuanContext, notebook_id: str, path: str, depth: int):
    """List document tree."""
    tree = ctx.client.list_doc_tree(notebook_id, path=path, max_depth=depth)
    if isinstance(tree, dict):
        items = tree.get("files") or tree.get("tree") or []
    else:
        items = tree
    if ctx.json_output:
        click.echo(json.dumps(items, ensure_ascii=False))
    else:
        for t in _walk_tree(items):
            indent = "  " * t.get("depth", 0)
            click.echo(f"{indent}{t.get('name', '')}  ({t.get('id', '')})")


@doc.command("get")
@click.argument("doc_id")
@click.pass_obj
def doc_get(ctx: SiYuanContext, doc_id: str):
    """Get document info by ID."""
    hpath = ctx.client.get_hpath_by_id(doc_id)
    if ctx.json_output:
        click.echo(json.dumps({"hpath": hpath}, ensure_ascii=False))
    else:
        click.echo(f"Path: {hpath}")


@doc.command("rename")
@click.argument("doc_id")
@click.argument("title")
@click.pass_obj
def doc_rename(ctx: SiYuanContext, doc_id: str, title: str):
    """Rename a document."""
    ctx.client.rename_doc_by_id(doc_id, title)
    if ctx.json_output:
        click.echo(json.dumps({"renamed": doc_id, "title": title}, ensure_ascii=False))
    else:
        click.echo(f"Renamed {doc_id} to: {title}")


@doc.command("remove")
@click.argument("doc_id")
@click.option("--dangerous", is_flag=True, help="Explicit confirmation to delete.")
@click.pass_obj
def doc_remove(ctx: SiYuanContext, doc_id: str, dangerous: bool):
    """Remove a document (requires --dangerous confirmation)."""
    _confirm_dangerous(dangerous, "remove this document")
    ctx.client.remove_doc_by_id(doc_id)
    if ctx.json_output:
        click.echo(json.dumps({"removed": doc_id}, ensure_ascii=False))
    else:
        click.echo(f"Removed: {doc_id}")


# ── Block commands ─────────────────────────────────────────────────────

@cli.group()
def block():
    """Manage blocks (内容块)."""


@block.command("insert")
@click.argument("data", required=False)
@click.option("--previous", multiple=True, default=None, callback=_single_use(""), help="Previous block ID")
@click.option("--parent", multiple=True, default=None, callback=_single_use(""), help="Parent block ID")
@click.option("--next", "next_", multiple=True, default=None, callback=_single_use(""), help="Next block ID")
@click.option("--data-type", multiple=True, default=None, callback=_single_use("markdown"), help="Data type (markdown/dom)")
@click.option("--file", "file_path", multiple=True, default=None, callback=_single_use(None), help="Read block data from a UTF-8 file (avoids PowerShell pipe encoding issues).")
@click.pass_obj
def block_insert(ctx: SiYuanContext, data: str | None, previous: str, parent: str, next_: str, data_type: str, file_path: str | None):
    """Insert a block. Reads from stdin when no data is given (empty pipe is rejected).

    Give exactly one anchor: --parent, --previous or --next. With two the
    kernel applies nextID > previousID > parentID and drops the rest, so the
    block would land elsewhere than asked.
    """
    anchors = [name for name, value in
               (("--parent", parent), ("--previous", previous), ("--next", next_)) if value]
    if not anchors:
        raise click.UsageError("An anchor is required: --parent, --previous, or --next")
    if len(anchors) > 1:
        # The kernel applies nextID > previousID > parentID and silently drops
        # the rest, so a second anchor would place the block somewhere else
        # than the caller asked for.
        raise click.UsageError(
            f"Give exactly one anchor, not {len(anchors)}: {', '.join(anchors)}")
    data = _resolve_block_data(data, file_path)
    result = ctx.client.insert_block(data_type, data, parent_id=parent, previous_id=previous, next_id=next_)
    if ctx.json_output:
        click.echo(json.dumps(result, ensure_ascii=False))
    else:
        click.echo("Block inserted")


@block.command("prepend")
@click.argument("parent_id")
@click.argument("data", required=False)
@click.option("--data-type", multiple=True, default=None, callback=_single_use("markdown"), help="Data type (markdown/dom)")
@click.option("--file", "file_path", multiple=True, default=None, callback=_single_use(None), help="Read block data from a UTF-8 file (avoids PowerShell pipe encoding issues).")
@click.pass_obj
def block_prepend(ctx: SiYuanContext, parent_id: str, data: str | None, data_type: str, file_path: str | None):
    """Insert a block as the first child of a container block. Reads from stdin when no data is given."""
    data = _resolve_block_data(data, file_path)
    result = ctx.client.prepend_block(data_type, data, parent_id)
    if ctx.json_output:
        click.echo(json.dumps(result, ensure_ascii=False))
    else:
        click.echo(f"Block prepended to: {parent_id}")


@block.command("append")
@click.argument("parent_id")
@click.argument("data", required=False)
@click.option("--data-type", multiple=True, default=None, callback=_single_use("markdown"), help="Data type (markdown/dom)")
@click.option("--file", "file_path", multiple=True, default=None, callback=_single_use(None), help="Read block data from a UTF-8 file (avoids PowerShell pipe encoding issues).")
@click.pass_obj
def block_append(ctx: SiYuanContext, parent_id: str, data: str | None, data_type: str, file_path: str | None):
    """Insert a block as the last child of a container block. Reads from stdin when no data is given."""
    data = _resolve_block_data(data, file_path)
    result = ctx.client.append_block(data_type, data, parent_id)
    if ctx.json_output:
        click.echo(json.dumps(result, ensure_ascii=False))
    else:
        click.echo(f"Block appended to: {parent_id}")


@block.command("update")
@click.argument("block_id")
@click.argument("data", required=False)
@click.option("--data-type", multiple=True, default=None, callback=_single_use("markdown"), help="Data type")
@click.option("--file", "file_path", multiple=True, default=None, callback=_single_use(None), help="Read block data from a UTF-8 file (avoids PowerShell pipe encoding issues).")
@click.pass_obj
def block_update(ctx: SiYuanContext, block_id: str, data: str | None, data_type: str, file_path: str | None):
    """Update a block's content. Reads from stdin when no data is given."""
    data = _resolve_block_data(data, file_path)
    ctx.client.update_block(data_type, data, block_id)
    if ctx.json_output:
        click.echo(json.dumps({"updated": block_id}, ensure_ascii=False))
    else:
        click.echo(f"Updated block: {block_id}")


@block.command("delete")
@click.argument("block_id")
@click.option("--dangerous", is_flag=True, help="Explicit confirmation to delete.")
@click.pass_obj
def block_delete(ctx: SiYuanContext, block_id: str, dangerous: bool):
    """Delete a block (requires --dangerous confirmation)."""
    _confirm_dangerous(dangerous, "delete this block")
    ctx.client.delete_block(block_id)
    if ctx.json_output:
        click.echo(json.dumps({"deleted": block_id}, ensure_ascii=False))
    else:
        click.echo(f"Deleted block: {block_id}")


@block.command("get")
@click.argument("block_id")
@click.pass_obj
def block_get(ctx: SiYuanContext, block_id: str):
    """Get block kramdown source."""
    kramdown = ctx.client.get_block_kramdown(block_id)
    if ctx.json_output:
        click.echo(json.dumps({"kramdown": kramdown}, ensure_ascii=False))
    else:
        click.echo(kramdown)


@block.command("children")
@click.argument("block_id")
@click.pass_obj
def block_children(ctx: SiYuanContext, block_id: str):
    """Get child blocks."""
    children = ctx.client.get_child_blocks(block_id)
    if ctx.json_output:
        click.echo(json.dumps(children, ensure_ascii=False))
    else:
        for c in children:
            click.echo(f"{c.get('id', ''):<30} {c.get('type', ''):<8} {c.get('subType', '')}")


@block.command("move")
@click.argument("block_id")
@click.option("--previous", multiple=True, default=None, callback=_single_use(""), help="Land right after this block ID (same level). To land at the end of a document use `block append` instead.")
@click.option("--parent", multiple=True, default=None, callback=_single_use(""), help="Land inside this block, as its first child. The parent must be a container block (document, list, super block) — paragraph-like leaf blocks reject children.")
@click.pass_obj
def block_move(ctx: SiYuanContext, block_id: str, previous: str, parent: str):
    """Move a block to a new position.

    --previous keeps the block at its own level (moves it after a sibling);
    --parent nests it as the first child of a container block. Exactly one
    destination is needed. `block append` is the way to land at the end of a
    document — this command is for relocating a block that already exists.
    """
    if not previous and not parent:
        raise click.UsageError("A destination is required: --previous <id> or --parent <id>")
    if previous and parent:
        raise click.UsageError("Give either --previous or --parent, not both")
    ctx.client.move_block(block_id, previous_id=previous, parent_id=parent)
    if ctx.json_output:
        click.echo(json.dumps({"moved": block_id, "previousID": previous, "parentID": parent}, ensure_ascii=False))
    else:
        destination = f"after {previous}" if previous else f"into {parent}"
        click.echo(f"Moved block: {block_id} ({destination})")


# ── Asset commands ─────────────────────────────────────────────────────

@cli.group()
def asset():
    """Manage assets (资源文件)."""


@asset.command("upload")
@click.argument("files", nargs=-1, required=True)
@click.option("--dir", "assets_dir", multiple=True, default=None, callback=_single_use("/assets/"),
              help="Target directory inside the workspace (default: /assets/).")
@click.pass_obj
def asset_upload(ctx: SiYuanContext, files: tuple[str, ...], assets_dir: str):
    """Upload local files and print the asset paths to reference in markdown.

    Example:
      sy asset upload pic.png cover.jpg --dir /assets/notes/
    """
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        raise click.UsageError("File not found: " + ", ".join(missing))
    result = ctx.client.upload_asset(list(files), assets_dir_path=assets_dir)
    succ = result.get("succMap", {}) if isinstance(result, dict) else {}
    errs = result.get("errFiles", []) if isinstance(result, dict) else []
    if ctx.json_output:
        click.echo(json.dumps({"succMap": succ, "errFiles": errs}, ensure_ascii=False))
    else:
        for src, dest in succ.items():
            click.echo(f"{dest}\t<- {src}")
    if errs:
        raise click.ClickException("Upload failed for: " + ", ".join(errs))


# ── Attribute commands ─────────────────────────────────────────────────

@cli.group()
def attr():
    """Read and write block attributes (块属性)."""


@attr.command("get")
@click.argument("block_id")
@click.pass_obj
def attr_get(ctx: SiYuanContext, block_id: str):
    """Show every attribute of a block."""
    attrs = ctx.client.get_block_attrs(block_id)
    if ctx.json_output:
        click.echo(json.dumps(attrs, ensure_ascii=False))
    elif not attrs:
        click.echo("No attributes")
    else:
        for key in sorted(attrs):
            click.echo(f"{key}: {attrs[key]}")


@attr.command("set")
@click.argument("block_id")
@click.argument("pairs", nargs=-1, required=True)
@click.pass_obj
def attr_set(ctx: SiYuanContext, block_id: str, pairs: tuple[str, ...]):
    """Set block attributes, each given as KEY=VALUE.

    Built-in keys: name (命名), alias (别名), memo (备注), bookmark (书签);
    custom keys must be prefixed with "custom-". An empty value removes the key.

    Example:
      sy attr set <block-id> custom-status=todo name=待核验
    """
    attrs = _parse_attr_pairs(pairs)
    ctx.client.set_block_attrs(block_id, attrs)
    if ctx.json_output:
        click.echo(json.dumps({"updated": block_id, "attrs": attrs}, ensure_ascii=False))
    else:
        click.echo(f"Set {len(attrs)} attribute(s) on {block_id}")


@attr.command("unset")
@click.argument("block_id")
@click.argument("keys", nargs=-1, required=True)
@click.pass_obj
def attr_unset(ctx: SiYuanContext, block_id: str, keys: tuple[str, ...]):
    """Remove attributes by key (the kernel drops a key set to an empty value)."""
    ctx.client.set_block_attrs(block_id, {key: "" for key in keys})
    if ctx.json_output:
        click.echo(json.dumps({"updated": block_id, "removed": list(keys)}, ensure_ascii=False))
    else:
        click.echo(f"Removed {len(keys)} attribute(s) from {block_id}")


# ── SQL command ────────────────────────────────────────────────────────

@cli.command()
@click.argument("stmt")
@click.pass_obj
def sql(ctx: SiYuanContext, stmt: str):
    """Execute a SQL query on the block database.

    Example: sql "SELECT * FROM blocks WHERE content LIKE '%keyword%' LIMIT 10"
    """
    results = ctx.client.query_sql(stmt)
    if ctx.json_output:
        click.echo(json.dumps(results, ensure_ascii=False))
    elif not results:
        click.echo("No results")
    else:
        for r in results:
            click.echo(json.dumps(r, ensure_ascii=False))


# ── Search commands ────────────────────────────────────────────────────

@cli.command()
@click.argument("query")
@click.pass_obj
def search(ctx: SiYuanContext, query: str):
    """Full-text search across all blocks."""
    data = ctx.client.search_blocks(query)
    blocks = data.get("blocks", []) if isinstance(data, dict) else data
    matched = data.get("matchedBlockCount") if isinstance(data, dict) else None
    if ctx.json_output:
        click.echo(json.dumps(blocks, ensure_ascii=False))
    elif not blocks:
        click.echo("No results")
    else:
        shown = blocks[:20]
        for r in shown:
            click.echo(f"- {r.get('id', '')}: {r.get('content', '')[:120]}")
        if matched is not None and matched > len(shown):
            click.echo(f"...showing {len(shown)} of {matched} matches; use `sql` for complete results")


# ── Export commands ────────────────────────────────────────────────────

@cli.group()
def export():
    """Export content from SiYuan."""


@export.command("md")
@click.argument("doc_id")
@click.pass_obj
def export_md(ctx: SiYuanContext, doc_id: str):
    """Export a document as Markdown."""
    md = ctx.client.export_md_content(doc_id)
    if ctx.json_output:
        click.echo(json.dumps(md, ensure_ascii=False))
    else:
        click.echo(f"# {md.get('hPath', '')}")
        click.echo("")
        click.echo(md.get("content", ""))


# ── System commands ────────────────────────────────────────────────────

@cli.command()
@click.pass_obj
def version(ctx: SiYuanContext):
    """Show SiYuan kernel version."""
    ver = ctx.client.get_version()
    if ctx.json_output:
        click.echo(json.dumps({"version": ver}, ensure_ascii=False))
    else:
        click.echo(f"SiYuan version: {ver}")


@cli.command()
@click.pass_obj
def status(ctx: SiYuanContext):
    """Show connection and session status."""
    info = _status_info(ctx.client, ctx.session)
    siyuan_ver = info["siyuan_version"]

    if ctx.json_output:
        click.echo(json.dumps(info, ensure_ascii=False))
    else:
        click.echo(f"  Connected:     {info['connected']}")
        click.echo(f"  SiYuan:        {f'v{siyuan_ver}' if siyuan_ver else '(unknown)'}")
        click.echo(f"  Host:          {info['host']}:{info['port']}")
        click.echo(f"  Notebook:      {info['current_notebook']}")
        click.echo(f"  Document:      {info['current_doc']}")


# ── Tag commands ───────────────────────────────────────────────────────

@cli.group()
def tag():
    """Manage tags (标签)."""


def _print_tags(tags: list[dict], indent: int = 0) -> None:
    """Recursively print tags with hierarchical indentation."""
    pad = "  " * indent
    for t in tags:
        if indent == 0:
            click.echo(f"{t.get('name', ''):<30} ({t.get('count', 0)})")
        else:
            click.echo(f"{pad}{t.get('name', ''):<{30 - 2 * indent}} ({t.get('count', 0)})")
        children = t.get("children")
        if children:
            _print_tags(children, indent + 1)


@tag.command("list")
@click.pass_obj
def tag_list(ctx: SiYuanContext):
    """List all tags (including nested tags)."""
    tags = ctx.client.get_tags()
    if ctx.json_output:
        click.echo(json.dumps(tags, ensure_ascii=False))
    else:
        _print_tags(tags)


if __name__ == "__main__":
    cli()
