"""REPL/one-shot parity tests.

Every case drives `_dispatch_repl` with a raw command string, so the tokenizer,
the `--json`/`--dangerous` handling and the option parsing all run for real —
calling the handlers with a pre-split list would skip exactly the bugs these
tests exist to catch.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from cli_anything.siyuan.siyuan_cli import _dispatch_repl


@pytest.fixture
def env():
    """(skin, ctx) with a client mock pre-wired to return JSON-safe values."""
    skin = MagicMock()
    ctx = MagicMock()
    cl = ctx.client
    cl.list_notebooks.return_value = [{"id": "nb1", "name": "N", "closed": False}]
    cl.create_notebook.return_value = {"id": "nb2", "name": "N2"}
    cl.list_docs_by_path.return_value = {"files": []}
    cl.list_doc_tree.return_value = {"files": []}
    cl.create_doc_with_md.return_value = "docid"
    cl.get_hpath_by_id.return_value = "/h"
    cl.get_block_kramdown.return_value = "kramdown"
    cl.get_child_blocks.return_value = []
    cl.get_block_attrs.return_value = {"custom-a": "1"}
    cl.get_version.return_value = "3.0.0"
    cl.get_tags.return_value = []
    cl.query_sql.return_value = []
    cl.search_blocks.return_value = {"blocks": [], "matchedBlockCount": 0}
    cl.export_md_content.return_value = {"hPath": "h", "content": "c"}
    cl.upload_asset.return_value = {"errFiles": None, "succMap": {}}
    cl.insert_block.return_value = []
    cl.prepend_block.return_value = []
    cl.append_block.return_value = []
    return skin, ctx


def run(env, cmd):
    """Dispatch a raw REPL line; return (skin, ctx, stdout)."""
    skin, ctx = env
    out: list[str] = []
    with patch("cli_anything.siyuan.siyuan_cli.click.echo", side_effect=out.append):
        _dispatch_repl(skin, ctx, cmd)
    return skin, ctx, "".join(out).strip()


# ── --json is honoured by every mutating command (one-shot parity) ─────

MUTATING = [
    "notebook create foo",
    "notebook rename nb1 nn",
    "notebook remove nb1 --dangerous",
    "notebook open nb1",
    "doc create nb1 /p --md x",
    "doc rename d1 t",
    "doc remove d1 --dangerous",
    "block insert p1 hi",
    "block prepend p1 hi",
    "block append p1 hi",
    "block update b1 hi",
    "block move b1 --previous b2",
    "block delete b1 --dangerous",
    "asset upload PLACEHOLDER",
    "attr set b1 custom-a=1",
    "attr unset b1 custom-a",
]


@pytest.mark.parametrize("cmd", MUTATING)
def test_json_mode_emits_json_for_mutations(env, tmp_path, cmd):
    """`--json <mutating command>` must print JSON, never bare UI text."""
    if "PLACEHOLDER" in cmd:
        src = tmp_path / "pic.png"
        src.write_bytes(b"p")
        cmd = cmd.replace("PLACEHOLDER", str(src))
    skin, _, out = run(env, "--json " + cmd)
    json.loads(out)  # raises if the command fell back to plain text


def test_json_mode_ignored_before_fix(env):
    """Guard the regression directly: `notebook rename` used to print no JSON."""
    _, _, out = run(env, "--json notebook rename nb1 nn")
    assert json.loads(out) == {"renamed": "nb1", "name": "nn"}


# ── the `--` terminator is gone for good ──────────────────────────────

def test_sql_keeps_leading_dashes(env):
    """A `--` token is part of the SQL statement, not a stripped terminator."""
    _, ctx, _ = run(env, "sql -- SELECT 1")
    ctx.client.query_sql.assert_called_once_with("-- SELECT 1")


def test_search_keeps_leading_dashes(env):
    _, ctx, _ = run(env, "search -- alpha")
    ctx.client.search_blocks.assert_called_once_with("-- alpha")


def test_bare_sql_reports_usage(env):
    """`sql` alone shows usage instead of "Unknown command" and no API call."""
    skin, ctx, _ = run(env, "sql")
    ctx.client.query_sql.assert_not_called()
    assert "Usage: sql" in str(skin.error.call_args)


def test_bare_search_reports_usage(env):
    skin, ctx, _ = run(env, "search")
    ctx.client.search_blocks.assert_not_called()
    assert "Usage: search" in str(skin.error.call_args)


# ── tag / version reachable from the REPL ─────────────────────────────

def test_tag_list_reaches_client(env):
    skin, ctx, out = run(env, "tag list")
    ctx.client.get_tags.assert_called_once_with()
    skin.error.assert_not_called()


def test_tag_list_json(env):
    _, _, out = run(env, "--json tag list")
    assert json.loads(out) == []


def test_tag_other_subcommand_reports_usage(env):
    skin, ctx, _ = run(env, "tag remove x")
    ctx.client.get_tags.assert_not_called()
    assert "Usage: tag list" in str(skin.error.call_args)


def test_version_reaches_client(env):
    skin, ctx, out = run(env, "version")
    ctx.client.get_version.assert_called_once_with()
    assert "3.0.0" in out or skin.success.called


def test_version_json(env):
    _, _, out = run(env, "--json version")
    assert json.loads(out) == {"version": "3.0.0"}


# ── dangling / misplaced options are errors, not values ───────────────

def test_dangling_dir_errors(env, tmp_path):
    """`--dir` with no value must not silently fall back to /assets/."""
    src = tmp_path / "pic.png"
    src.write_bytes(b"p")
    skin, ctx, _ = run(env, f"asset upload {src} --dir")
    ctx.client.upload_asset.assert_not_called()
    assert "--dir requires a value" in str(skin.error.call_args)


def test_dangling_previous_errors(env):
    skin, ctx, _ = run(env, "block move b1 --previous")
    ctx.client.move_block.assert_not_called()
    assert "--previous requires a value" in str(skin.error.call_args)


def test_flag_value_may_not_be_another_flag(env):
    """`--previous --parent p1` must not read "--parent" as an ID."""
    skin, ctx, _ = run(env, "block move b1 --previous --parent p1")
    ctx.client.move_block.assert_not_called()
    assert "requires a value" in str(skin.error.call_args)


def test_move_rejects_both_anchors(env):
    """One destination only, same as the one-shot command."""
    skin, ctx, _ = run(env, "block move b1 --previous b2 --parent p1")
    ctx.client.move_block.assert_not_called()
    assert "not both" in str(skin.error.call_args)


def test_move_missing_destination_errors(env):
    skin, ctx, _ = run(env, "block move b1")
    ctx.client.move_block.assert_not_called()
    assert "destination is required" in str(skin.error.call_args)


# ── anchor flags are never swallowed into block content ───────────────

@pytest.mark.parametrize("cmd,fn", [
    ("block insert p1 data --previous X", "insert_block"),
    ("block prepend p1 data --next X", "prepend_block"),
    ("block append p1 data --parent X", "append_block"),
    ("block update b1 data --previous X", "update_block"),
])
def test_stray_anchor_flag_is_rejected(env, cmd, fn):
    """A stray anchor used to land inside the block's content verbatim."""
    skin, ctx, _ = run(env, cmd)
    getattr(ctx.client, fn).assert_not_called()
    assert "not an option here" in str(skin.error.call_args)


def test_legacy_positional_parent_still_works(env):
    """The documented REPL form keeps working unchanged."""
    _, ctx, _ = run(env, "block insert p1 hello")
    ctx.client.insert_block.assert_called_once_with("markdown", "hello", parent_id="p1")


def test_doc_tree_depth_is_forwarded(env):
    """`--depth` used to be silently dropped."""
    _, ctx, _ = run(env, "doc tree nb1 --depth 2")
    ctx.client.list_doc_tree.assert_called_once_with("nb1", path="/", max_depth=2)


def test_doc_tree_path_and_depth(env):
    _, ctx, _ = run(env, "doc tree nb1 --path /a --depth 3")
    ctx.client.list_doc_tree.assert_called_once_with("nb1", path="/a", max_depth=3)


def test_doc_tree_bad_depth_errors(env):
    skin, ctx, _ = run(env, "doc tree nb1 --depth x")
    ctx.client.list_doc_tree.assert_not_called()
    assert "expects an integer" in str(skin.error.call_args)


def test_doc_list_defaults_to_root(env):
    """`doc list <notebook>` matches the one-shot default path."""
    _, ctx, _ = run(env, "doc list nb1")
    ctx.client.list_docs_by_path.assert_called_once_with("nb1", "/")


def test_notebook_open_sets_session(env):
    _, ctx, _ = run(env, "notebook open nb1")
    ctx.client.open_notebook.assert_called_once_with("nb1")
    kwargs = ctx.session.update.call_args.kwargs
    assert kwargs["current_notebook_id"] == "nb1"
    assert kwargs["current_notebook_name"] == "N"


# ── a known flag in the wrong command is an error, never content ──────

MISPLACED_FLAGS = [
    ("doc rename d1 --file x.md", "rename_doc_by_id"),
    ("doc rename d1 --depth 3", "rename_doc_by_id"),
    ("notebook create --parent x", "create_notebook"),
    ("notebook rename nb1 --md x", "rename_notebook"),
    ("attr unset b1 --md", "set_block_attrs"),
    ("doc list nb1 --depth 2", "list_docs_by_path"),
    ("doc list nb1 --path /x", "list_docs_by_path"),
    ("doc rename d1 --data-type dom", "rename_doc_by_id"),
    ("doc tree nb1 --previous x", "list_doc_tree"),
]


@pytest.mark.parametrize("cmd,fn", MISPLACED_FLAGS)
def test_misplaced_flag_is_rejected(env, cmd, fn):
    """These used to rename/repoint the target to the literal flag text."""
    skin, ctx, _ = run(env, cmd)
    getattr(ctx.client, fn).assert_not_called()
    assert "is not an option here" in str(skin.error.call_args)


def test_misplaced_flag_shows_the_real_signature(env):
    skin, _, _ = run(env, "doc rename d1 --file x.md")
    assert "Usage: doc rename <id> <title>" in str(skin.error.call_args)


def test_unrelated_command_rejects_dangerous(env):
    """--dangerous confirms deletion only, and says so."""
    skin, ctx, _ = run(env, "search --dangerous")
    ctx.client.search_blocks.assert_not_called()
    assert "not an option here" in str(skin.error.call_args)
    # The hint must be the real signature, not the flag echoed back as one.
    assert "Usage: search <query>" in str(skin.error.call_args)


# ── a name no command declares is a typo, never content ───────────────

UNKNOWN_FLAGS = [
    ("doc rename d1 --flie x", "rename_doc_by_id"),
    ("notebook create --nalme x", "create_notebook"),
    ("doc get d1 --depht 2", "get_hpath_by_id"),
    ("block delete b1 --dangerus", "delete_block"),
]


@pytest.mark.parametrize("cmd,fn", UNKNOWN_FLAGS)
def test_unknown_flag_is_rejected(env, cmd, fn):
    """A mistyped flag used to be written into the target as literal text.

    `doc rename d1 --flie x` really renamed the document to "--flie x"; the
    one-shot command answers "No such option".
    """
    skin, ctx, _ = run(env, cmd)
    getattr(ctx.client, fn).assert_not_called()
    assert "Unknown option" in str(skin.error.call_args)


def test_unknown_flag_reports_the_signature(env):
    skin, _, _ = run(env, "doc rename d1 --flie x")
    assert "Usage: doc rename <id> <title>" in str(skin.error.call_args)


def test_double_dash_inside_content_is_kept(env):
    """`--` is not an option — the REPL has no `--` terminator to strip."""
    _, ctx, _ = run(env, "block update b1 a -- b")
    ctx.client.update_block.assert_called_once_with("markdown", "a -- b", "b1")


# ── click's `--flag=value` spelling parses in the REPL too ────────────

def test_attached_value_updates_the_block(env, tmp_path):
    """`block update b1 --file=x.md` used to write the flag itself as content."""
    note = tmp_path / "note.md"
    note.write_text("from file", encoding="utf-8")
    _, ctx, _ = run(env, f"block update b1 --file={note}")
    ctx.client.update_block.assert_called_once_with("markdown", "from file", "b1")


def test_attached_value_reaches_doc_create(env):
    """`doc create nb1 /p --md=hi` used to create an empty document, silently."""
    _, ctx, _ = run(env, "doc create nb1 /p --md=hi")
    ctx.client.create_doc_with_md.assert_called_once_with("nb1", "/p", "hi")


def test_attached_values_reach_doc_tree(env):
    """Both options used to be dropped, falling back to "/" and no depth."""
    _, ctx, _ = run(env, "doc tree nb1 --depth=2 --path=/a")
    ctx.client.list_doc_tree.assert_called_once_with("nb1", path="/a", max_depth=2)


def test_attached_value_reaches_asset_upload(env, tmp_path):
    """`--dir=/x/` used to be read as a file name ("File not found")."""
    src = tmp_path / "pic.png"
    src.write_bytes(b"p")
    _, ctx, _ = run(env, f"asset upload {src} --dir=/assets/x/")
    ctx.client.upload_asset.assert_called_once_with([str(src)],
                                                    assets_dir_path="/assets/x/")


# ── --data-type is a REPL option, as it is one-shot ───────────────────

BLOCK_WRITES = [
    ("block insert p1 hi --data-type dom", "insert_block"),
    ("block prepend p1 hi --data-type dom", "prepend_block"),
    ("block append p1 hi --data-type=dom", "append_block"),
    ("block update b1 hi --data-type=dom", "update_block"),
]


@pytest.mark.parametrize("cmd,fn", BLOCK_WRITES)
def test_data_type_reaches_the_kernel(env, cmd, fn):
    """`--data-type dom` used to be refused as "not an option here".

    The type was hard-coded to "markdown", so a DOM payload was stored as
    markdown text — the one-shot command has always accepted the flag. The flag
    and its value are options, not block content.
    """
    _, ctx, _ = run(env, cmd)
    assert getattr(ctx.client, fn).call_args.args[:2] == ("dom", "hi")


def test_data_type_defaults_to_markdown(env):
    """Absent flag keeps the one-shot default."""
    _, ctx, _ = run(env, "block update b1 hi")
    ctx.client.update_block.assert_called_once_with("markdown", "hi", "b1")


def test_data_type_without_a_value_is_rejected(env):
    """`--data-type --json` must not store the type "--json"."""
    skin, ctx, _ = run(env, "block update b1 hi --data-type --json")
    ctx.client.update_block.assert_not_called()
    assert "requires a value" in str(skin.error.call_args)


def test_data_type_repeated_is_rejected(env):
    skin, ctx, _ = run(env, "block update b1 hi --data-type dom --data-type md")
    ctx.client.update_block.assert_not_called()
    assert "more than once" in str(skin.error.call_args)


def test_only_the_first_equals_splits(env):
    """The value may itself contain `=`, as on the command line."""
    _, ctx, _ = run(env, "doc create nb1 /p --md=a=b")
    ctx.client.create_doc_with_md.assert_called_once_with("nb1", "/p", "a=b")


def test_attached_empty_value_is_rejected(env):
    """`--depth=` is an empty value, not a missing option: no silent default."""
    skin, ctx, _ = run(env, "doc tree nb1 --depth=")
    ctx.client.list_doc_tree.assert_not_called()
    assert "--depth requires a value" in str(skin.error.call_args)


def test_attached_unknown_flag_is_still_rejected(env):
    skin, ctx, _ = run(env, "block update b1 --flie=x")
    ctx.client.update_block.assert_not_called()
    assert "Unknown option" in str(skin.error.call_args)


# ── missing arguments report a usage, not an internal error ───────────

def test_doc_list_without_notebook_reports_usage(env):
    """`doc list` used to raise IndexError ("list index out of range")."""
    skin, ctx, _ = run(env, "doc list")
    ctx.client.list_docs_by_path.assert_not_called()
    assert "Usage: doc list <notebook> [path]" in str(skin.error.call_args)


def test_doc_list_rejects_extra_positionals(env):
    skin, ctx, _ = run(env, "doc list nb1 /a /b")
    ctx.client.list_docs_by_path.assert_not_called()
    assert "Usage: doc list" in str(skin.error.call_args)


def test_doc_tree_rejects_positional_path(env):
    """`doc list` takes a positional path; `doc tree` needs --path.

    Falling through to "/" returned the wrong tree without a word.
    """
    skin, ctx, _ = run(env, "doc tree nb1 /a")
    ctx.client.list_doc_tree.assert_not_called()
    assert "--path" in str(skin.error.call_args)


@pytest.mark.parametrize("cmd,signature", [
    ("doc get", "doc get <id>"),
    ("doc create nb1", "doc create <notebook> <path>"),
    ("notebook rename nb1", "notebook rename <id> <name>"),
    ("block get", "block get <block_id>"),
])
def test_missing_argument_reports_the_signature(env, cmd, signature):
    skin, _, _ = run(env, cmd)
    assert f"Usage: {signature}" in str(skin.error.call_args)


@pytest.mark.parametrize("cmd,message", [
    ("attr remove b1", "Unknown attr command"),
    ("asset drop x", "Unknown asset command"),
    ("doc frobnicate", "Unknown doc command"),
    ("block frobnicate b1", "Unknown block command"),
])
def test_unknown_subcommand_is_distinguished_from_missing_args(env, cmd, message):
    """`Invalid doc command` used to cover a typo and a missing argument alike."""
    skin, _, _ = run(env, cmd)
    assert message in str(skin.error.call_args)


def test_doc_export_points_at_the_export_command(env):
    """`doc export` was a second spelling of `export md`; one command, one name."""
    skin, ctx, _ = run(env, "doc export d1")
    ctx.client.export_md_content.assert_not_called()
    assert "export md <doc-id>" in str(skin.error.call_args)


# ── repeated options ──────────────────────────────────────────────────

@pytest.mark.parametrize("cmd", [
    "doc tree nb1 --path /a --path /b",
    "doc tree nb1 --depth 1 --depth 2",
    "asset upload PLACEHOLDER --dir /a/ --dir /b/",
    "block move b1 --previous b2 --previous b3",
])
def test_repeated_option_is_rejected(env, tmp_path, cmd):
    """The first value used to win silently."""
    if "PLACEHOLDER" in cmd:
        src = tmp_path / "p.png"
        src.write_bytes(b"p")
        cmd = cmd.replace("PLACEHOLDER", str(src))
    skin, ctx, _ = run(env, cmd)
    assert "more than once" in str(skin.error.call_args)


# ── status goes through the dispatcher, so --json reaches it ──────────

def _wire_status(env):
    skin, ctx = env
    from cli_anything.siyuan.core.session import SessionState
    ctx.client.ping.return_value = True
    ctx.client.config.host = "127.0.0.1"
    ctx.client.config.port = 6806
    ctx.session.state = SessionState()
    return skin, ctx


def test_status_json_reaches_dispatch(env):
    """`--json status` used to fall through to "Unknown command: status"."""
    _wire_status(env)
    skin, _, out = run(env, "--json status")
    info = json.loads(out)
    assert info["connected"] is True
    assert info["siyuan_version"] == "3.0.0"
    assert info["host"] == "127.0.0.1"
    skin.error.assert_not_called()


def test_status_plain_reaches_dispatch(env):
    """`status` is dispatched (not special-cased in the loop) in both modes."""
    skin, _ = _wire_status(env)
    run(env, "status")
    skin.status_block.assert_called_once()
    skin.error.assert_not_called()


# ── extra positionals on a fixed-arity command ────────────────────────

EXTRA_POSITIONALS = [
    ("doc get d1 extra", "get_hpath_by_id"),
    ("doc remove d1 extra --dangerous", "remove_doc_by_id"),
    ("doc create nb1 /p extra", "create_doc_with_md"),
    ("block get b1 extra", "get_block_kramdown"),
    ("block children b1 extra", "get_child_blocks"),
    ("block delete b1 extra --dangerous", "delete_block"),
    ("attr get b1 extra", "get_block_attrs"),
    ("notebook list extra", "list_notebooks"),
    ("notebook open nb1 extra", "open_notebook"),
    ("export md d1 extra", "export_md_content"),
    ("version extra", "get_version"),
]


@pytest.mark.parametrize("cmd,fn", EXTRA_POSITIONALS)
def test_extra_positional_is_rejected(env, cmd, fn):
    """Every one of these used to drop the extra argument without a word."""
    skin, ctx, _ = run(env, cmd)
    getattr(ctx.client, fn).assert_not_called()
    assert "Unexpected argument" in str(skin.error.call_args)


@pytest.mark.parametrize("cmd", [
    "notebook create My Long Name",
    "doc rename d1 A Longer Title",
    "block insert p1 several words here",
    "block update b1 several words here",
    "attr unset b1 k1 k2 k3",
])
def test_variadic_positionals_still_accepted(env, cmd):
    """A joined name/title, block content and attribute keys stay variadic."""
    skin, _, _ = run(env, cmd)
    skin.error.assert_not_called()


def test_dangling_option_outranks_the_arity_check(env):
    """`--previous --parent p1` is a dangling option, not a stray `p1`."""
    skin, ctx, _ = run(env, "block move b1 --previous --parent p1")
    ctx.client.move_block.assert_not_called()
    assert "requires a value" in str(skin.error.call_args)


# ── group usage strings cannot drift from the help table ──────────────

def test_bare_doc_usage_drops_the_removed_export(env):
    """`doc export` is gone; a bare `doc` still advertised it."""
    skin, _, _ = run(env, "doc")
    message = str(skin.error.call_args)
    assert "export" not in message
    for sub in ("create", "list", "tree", "get", "rename", "remove"):
        assert sub in message


def test_bare_notebook_usage_lists_open(env):
    """A bare `notebook` omitted `open`."""
    skin, _, _ = run(env, "notebook")
    assert "open" in str(skin.error.call_args)


@pytest.mark.parametrize("group", ["notebook", "doc", "block", "attr"])
def test_group_usage_covers_every_help_entry(env, group):
    from cli_anything.siyuan.siyuan_cli import _build_repl_commands, _repl_group_usage
    usage = _repl_group_usage(group)
    subs = [s.split()[1] for s in _build_repl_commands()
            if s.startswith(f"{group} ") and not s.split()[1].startswith(("<", "["))]
    assert subs, f"no help entries for {group}"
    for sub in subs:
        assert sub in usage


def test_unknown_block_alias_points_at_children(env):
    """`block child` was an undocumented alias that also skipped the arity check."""
    skin, ctx, _ = run(env, "block child b1 extra")
    ctx.client.get_child_blocks.assert_not_called()
    assert "block children <block_id>" in str(skin.error.call_args)


def test_doc_create_rejects_empty_md_with_file(env, tmp_path):
    """`--md "" --file x` used to pick the file without saying so."""
    note = tmp_path / "note.md"
    note.write_text("from file", encoding="utf-8")
    skin, ctx, _ = run(env, f'doc create nb1 /p --md "" --file {note}')
    ctx.client.create_doc_with_md.assert_not_called()
    assert "not both" in str(skin.error.call_args)


def test_doc_create_rejects_repeated_md(env):
    skin, ctx, _ = run(env, "doc create nb1 /p --md a --md b")
    ctx.client.create_doc_with_md.assert_not_called()
    assert "more than once" in str(skin.error.call_args)


def test_doc_create_empty_md_alone_is_an_empty_doc(env):
    _, ctx, _ = run(env, 'doc create nb1 /p --md ""')
    ctx.client.create_doc_with_md.assert_called_once_with("nb1", "/p", "")


# ── free-text commands: the tail is text, not an option surface ───────

FREE_TEXT = [
    ("sql SELECT 1 --comment", "query_sql", "SELECT 1 --comment"),
    ("sql SELECT id FROM blocks WHERE content LIKE '--%' LIMIT 1",
     "query_sql", "SELECT id FROM blocks WHERE content LIKE '--%' LIMIT 1"),
    ("sql SELECT * FROM blocks WHERE content = '--file=x'",
     "query_sql", "SELECT * FROM blocks WHERE content = '--file=x'"),
    ("search --foo", "search_blocks", "--foo"),
    ("search -- alpha", "search_blocks", "-- alpha"),
    ("sql -- SELECT 1", "query_sql", "-- SELECT 1"),
]


@pytest.mark.parametrize("cmd,fn,expected", FREE_TEXT)
def test_free_text_keeps_flag_shaped_text(env, cmd, fn, expected):
    """A SQL comment or LIKE pattern has no other spelling — there is no `--`
    terminator to escape it, so the tail must reach the kernel verbatim."""
    skin, ctx, _ = run(env, cmd)
    getattr(ctx.client, fn).assert_called_once_with(expected)
    skin.error.assert_not_called()


def test_known_flag_still_errors_in_a_free_text_command(env):
    """The exemption is only for names nothing declares."""
    skin, ctx, _ = run(env, "sql select --depth from x")
    ctx.client.query_sql.assert_not_called()
    assert "not an option here" in str(skin.error.call_args)


def test_unknown_flag_still_errors_in_a_structured_command(env):
    skin, ctx, _ = run(env, "doc rename d1 --flie x")
    ctx.client.rename_doc_by_id.assert_not_called()
    assert "Unknown option" in str(skin.error.call_args)


# ── a statement keeps its quotes ──────────────────────────────────────

def test_sql_keeps_inner_quotes(env):
    """`WHERE '1' = '01'` used to reach the kernel as `WHERE 1 = 01`.

    That is a different query — it returns a row where the text comparison
    returns none — and nothing said so.
    """
    _, ctx, _ = run(env, "sql SELECT type FROM blocks WHERE '1' = '01' LIMIT 1")
    ctx.client.query_sql.assert_called_once_with(
        "SELECT type FROM blocks WHERE '1' = '01' LIMIT 1")


def test_sql_unwraps_one_wrapping_quote_pair(env):
    """The documented spelling wraps the statement; its quotes are not sent on."""
    _, ctx, _ = run(env, """sql "SELECT * FROM blocks WHERE content LIKE '%k%'" """.strip())
    ctx.client.query_sql.assert_called_once_with(
        "SELECT * FROM blocks WHERE content LIKE '%k%'")


def test_sql_does_not_unwrap_a_quoted_expression(env):
    """`"a" || "b"` starts and ends with a quote but is not one quoted token."""
    _, ctx, _ = run(env, 'sql "a" || "b"')
    ctx.client.query_sql.assert_called_once_with('"a" || "b"')


# ── a bare `--` is not an argument either ─────────────────────────────

@pytest.mark.parametrize("cmd,fn", [
    ("doc get -- d1", "get_hpath_by_id"),
    ("block get -- b1", "get_block_kramdown"),
    ("doc list -- nb1", "list_docs_by_path"),
    ("version --", "get_version"),
])
def test_bare_terminator_is_not_read_as_the_argument(env, cmd, fn):
    """`doc get -- d1` used to fetch the id "--" and drop `d1`.

    There is no `--` terminator to strip, so in a fixed-arity command it is
    refused rather than filling an argument slot.
    """
    skin, ctx, _ = run(env, cmd)
    getattr(ctx.client, fn).assert_not_called()
    assert "not a terminator" in str(skin.error.call_args)


def test_bare_terminator_in_a_block_write_is_still_content(env):
    """Block content is variadic, so `--` there stays text."""
    _, ctx, _ = run(env, "block update b1 a -- b")
    ctx.client.update_block.assert_called_once_with("markdown", "a -- b", "b1")


# ── unchanged guarantees ──────────────────────────────────────────────

def test_explicit_empty_content_still_allowed(env):
    """`block update b1 ""` remains an explicit clear, not a missing-content error."""
    _, ctx, _ = run(env, 'block update b1 ""')
    ctx.client.update_block.assert_called_once_with("markdown", "", "b1")


def test_missing_content_still_rejected(env):
    skin, ctx, _ = run(env, "block update b1")
    ctx.client.update_block.assert_not_called()
    assert "either as an argument or via --file" in str(skin.error.call_args)


def test_md_value_may_be_a_flag_like_token(env):
    _, ctx, _ = run(env, 'doc create nb1 /x --md "--json"')
    ctx.client.create_doc_with_md.assert_called_once_with("nb1", "/x", "--json")


def test_help_lists_every_dispatched_command_group(env):
    from cli_anything.siyuan.siyuan_cli import _build_repl_commands
    listed = _build_repl_commands()
    for entry in ("notebook open <id>", "doc rename <id> <title>",
                  "doc remove <id> --dangerous",
                  "block prepend <parent_id> <data> [--data-type <markdown|dom>] [--file <path>]",
                  "block append <parent_id> <data> [--data-type <markdown|dom>] [--file <path>]",
                  "block children <block_id>",
                  "block move <block_id> [--previous <id> | --parent <id>]",
                  "tag list", "version", "status"):
        assert entry in listed


def test_every_declared_flag_appears_in_its_signature():
    """The help line an error echoes must list the flags the command accepts.

    A flag missing from the signature leaves the usage hint advertising only
    half of what the command takes.
    """
    from cli_anything.siyuan.siyuan_cli import (
        _REPL_ALLOWED_FLAGS, _build_repl_commands)
    signatures = _build_repl_commands()
    for key, allowed in _REPL_ALLOWED_FLAGS.items():
        matching = [s for s in signatures if s.split()[:len(key.split())] == key.split()]
        assert matching, key
        silent = [f for f in sorted(allowed) if f not in matching[0]]
        assert not silent, f"{key}: {silent} missing from {matching[0]!r}"
