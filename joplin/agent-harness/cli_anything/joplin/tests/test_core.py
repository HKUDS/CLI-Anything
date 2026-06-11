"""Command-level unit tests for cli-anything-joplin.

These tests run without a real Joplin backend. They cover:

- harness project schema, save/open, history
- session state machine (set/get/snapshot/undo/redo/save)
- backend command runner (subprocess invocation, JSON parsing, error handling,
  verbatim stdout preservation, benign Node warning decision-only filtering)
- CLI JSON envelope contract across every command group (including stable
  error command IDs for multi-word subcommands)
- auto-save behavior, dry-run, project status reporting
- notes copy/move/rename, notebooks remove, todos group, attach, status,
  session history, tag tagnotes, backend version fallback layouts
"""

import json
import os

import pytest
from click.testing import CliRunner

from cli_anything.joplin import joplin_cli
from cli_anything.joplin.core import backend as backend_core
from cli_anything.joplin.core import config as config_core
from cli_anything.joplin.core import interop as interop_core
from cli_anything.joplin.core import notes as note_core
from cli_anything.joplin.core import notebooks as notebook_core
from cli_anything.joplin.core import project as project_mod
from cli_anything.joplin.core import sync as sync_core
from cli_anything.joplin.core import tags as tag_core
from cli_anything.joplin.core import todos as todo_core
from cli_anything.joplin.core.session import Session
from cli_anything.joplin.utils import joplin_backend


# ---------------------------------------------------------------------------
# Project schema / persistence
# ---------------------------------------------------------------------------


def test_create_project_schema():
    proj = project_mod.create_project(name="demo", backend_binary="joplin", backend_profile=None)
    assert proj["name"] == "demo"
    assert "backend" in proj
    assert "context" in proj
    assert isinstance(proj["history"], list)
    assert proj["context"]["current_notebook"] is None


def test_project_save_open_roundtrip(tmp_path):
    proj = project_mod.create_project(name="rt")
    p = tmp_path / "p.json"
    project_mod.save_project(proj, str(p))
    loaded = project_mod.open_project(str(p))
    assert loaded["name"] == "rt"


def test_project_save_open_unicode_roundtrip(tmp_path):
    proj = project_mod.create_project(name="笔记本-中文")
    proj["context"]["current_notebook"] = "笔记 A"
    p = tmp_path / "u.json"
    project_mod.save_project(proj, str(p))
    loaded = project_mod.open_project(str(p))
    assert loaded["name"] == "笔记本-中文"
    assert loaded["context"]["current_notebook"] == "笔记 A"


def test_project_add_history():
    proj = project_mod.create_project(name="h")
    project_mod.add_history(proj, "action", {"k": "v"})
    assert len(proj["history"]) == 1
    assert proj["history"][0]["action"] == "action"
    assert proj["history"][0]["payload"] == {"k": "v"}


def test_project_add_history_without_payload():
    proj = project_mod.create_project(name="h")
    project_mod.add_history(proj, "tick")
    assert proj["history"][0]["payload"] == {}


def test_project_save_creates_parent(tmp_path):
    proj = project_mod.create_project(name="nested")
    p = tmp_path / "a" / "b" / "p.json"
    project_mod.save_project(proj, str(p))
    assert p.exists()


def test_project_info_shape():
    proj = project_mod.create_project(name="info")
    project_mod.add_history(proj, "x")
    info = project_mod.project_info(proj)
    assert info["name"] == "info"
    assert info["history_count"] == 1
    assert "backend" in info
    assert "context" in info


# ---------------------------------------------------------------------------
# Session state machine
# ---------------------------------------------------------------------------


def test_session_set_get_has_project():
    sess = Session()
    assert not sess.has_project()
    proj = project_mod.create_project(name="s")
    sess.set_project(proj)
    assert sess.has_project()
    assert sess.get_project()["name"] == "s"


def test_session_get_project_without_project_raises():
    sess = Session()
    with pytest.raises(RuntimeError):
        sess.get_project()


def test_session_snapshot_undo_redo():
    sess = Session()
    proj = project_mod.create_project(name="s")
    sess.set_project(proj)
    sess.snapshot("before")
    sess.get_project()["context"]["current_notebook"] = "A"
    sess.undo()
    assert sess.get_project()["context"]["current_notebook"] is None
    sess.redo()
    assert sess.get_project()["context"]["current_notebook"] == "A"


def test_session_multiple_snapshots_undo_chain():
    sess = Session()
    proj = project_mod.create_project(name="chain")
    sess.set_project(proj)
    for i in range(3):
        sess.snapshot(f"step-{i}")
        sess.get_project()["context"]["current_notebook"] = f"book-{i}"
    assert sess.status()["undo_depth"] == 3
    sess.undo()
    sess.undo()
    sess.undo()
    assert sess.get_project()["context"]["current_notebook"] is None
    assert sess.status()["redo_depth"] == 3


def test_session_snapshot_clears_redo():
    sess = Session()
    proj = project_mod.create_project(name="redo-clear")
    sess.set_project(proj)
    sess.snapshot("a")
    sess.get_project()["context"]["current_notebook"] = "X"
    sess.undo()
    assert sess.status()["redo_depth"] == 1

    sess.snapshot("b")
    assert sess.status()["redo_depth"] == 0


def test_session_undo_empty_raises():
    sess = Session()
    with pytest.raises(RuntimeError):
        sess.undo()


def test_session_redo_empty_raises():
    sess = Session()
    with pytest.raises(RuntimeError):
        sess.redo()


def test_session_save_without_path_raises():
    sess = Session()
    sess.set_project(project_mod.create_project())
    with pytest.raises(RuntimeError):
        sess.save_session()


def test_session_save_with_path(tmp_path):
    sess = Session()
    sess.set_project(project_mod.create_project(name="save"), str(tmp_path / "x.json"))
    saved = sess.save_session()
    assert os.path.exists(saved)


def test_session_save_creates_missing_parent_directories(tmp_path):
    """Regression: saving to a not-yet-created nested path must not fail at
    the lock open before the data write runs."""
    sess = Session()
    nested = tmp_path / "deep" / "subdir" / "newly_created.json"
    sess.set_project(project_mod.create_project(name="nested"), str(nested))
    saved = sess.save_session()
    assert os.path.exists(saved)
    assert nested.parent.is_dir()


def test_session_save_real_lock_held_then_released(tmp_path):
    """The exclusive lock must be acquired and released correctly for a
    normal single-process save, so that a subsequent save on the same path
    can acquire it again without blocking."""
    project_path = tmp_path / "project.json"
    sess = Session()
    sess.set_project(project_mod.create_project(name="lock-test"), str(project_path))
    sess.save_session()

    # A second save on the same path must succeed (lock was released by the
    # first save). If _locked_save_json fails to release, this deadlocks or
    # raises, failing the test.
    sess.snapshot("change")
    sess.save_session()
    assert project_path.exists()


def test_session_save_lock_prevents_tmp_collision(tmp_path):
    """Two threads calling _locked_save_json on the same path concurrently
    must each write their own data atomically -- neither write should be lost
    and the file must remain valid JSON after both finish."""
    import threading

    project_path = tmp_path / "shared.json"

    # Pre-create the file so both threads are working on an existing path.
    sess0 = Session()
    sess0.set_project(project_mod.create_project(name="init"), str(project_path))
    sess0.save_session()

    errors: list[Exception] = []
    results: list[str] = []

    def writer(name: str) -> None:
        try:
            sess = Session()
            proj = project_mod.create_project(name=name)
            sess.set_project(proj, str(project_path))
            # Each writer saves from a snapshot so _modified is True.
            sess.snapshot(f"writer {name}")
            sess.save_session()
            results.append(name)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(f"writer-{i}",)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"Concurrent saves raised: {errors}"
    assert len(results) == 4, f"Not all writers completed: {results}"

    # The file must still be valid JSON after all concurrent writes.
    with open(project_path, encoding="utf-8") as fh:
        content = json.load(fh)
    assert isinstance(content, dict)
    assert "name" in content


def test_session_set_project_clears_undo_redo():
    sess = Session()
    sess.set_project(project_mod.create_project(name="a"))
    sess.snapshot("change")
    assert sess.status()["undo_depth"] == 1
    sess.set_project(project_mod.create_project(name="b"))
    assert sess.status()["undo_depth"] == 0
    assert sess.status()["redo_depth"] == 0
    assert sess.status()["modified"] is False


def test_session_status_shape():
    sess = Session()
    s = sess.status()
    assert set(s.keys()) >= {"has_project", "project_path", "modified", "undo_depth", "redo_depth"}


def test_session_mark_dirty_sets_modified_without_snapshot():
    sess = Session()
    sess.set_project(project_mod.create_project(name="dirty"))
    assert sess.status()["modified"] is False
    sess.mark_dirty()
    assert sess.status()["modified"] is True
    assert sess.status()["undo_depth"] == 0


def test_session_mark_dirty_without_project_raises():
    sess = Session()
    with pytest.raises(RuntimeError):
        sess.mark_dirty()


# ---------------------------------------------------------------------------
# Backend runner
# ---------------------------------------------------------------------------


def test_backend_find_joplin_missing(monkeypatch):
    monkeypatch.setattr(joplin_backend.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError):
        joplin_backend.find_joplin("joplin")


def test_backend_find_joplin_ok(monkeypatch):
    monkeypatch.setattr(joplin_backend.shutil, "which", lambda _: "/usr/bin/joplin")
    assert joplin_backend.find_joplin("joplin") == "/usr/bin/joplin"


def test_backend_run_command_invokes_subprocess(monkeypatch):
    class Proc:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(joplin_backend, "find_joplin", lambda _: "joplin")

    captured = {}

    def fake_run(cmd, capture_output, text, timeout, check):
        captured["cmd"] = cmd
        captured["timeout"] = timeout
        return Proc()

    monkeypatch.setattr(joplin_backend.subprocess, "run", fake_run)
    cfg = joplin_backend.BackendConfig(binary="joplin", profile="/tmp/p")
    out = joplin_backend.run_joplin_command(["ls"], cfg)
    assert out["returncode"] == 0
    assert captured["cmd"][:3] == ["joplin", "--profile", "/tmp/p"]
    assert captured["cmd"][-1] == "ls"


def test_backend_run_command_without_profile(monkeypatch):
    class Proc:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(joplin_backend, "find_joplin", lambda _: "joplin")

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return Proc()

    monkeypatch.setattr(joplin_backend.subprocess, "run", fake_run)
    cfg = joplin_backend.BackendConfig(binary="joplin", profile=None)
    joplin_backend.run_joplin_command(["ls"], cfg)
    assert "--profile" not in captured["cmd"]


def test_backend_run_command_error(monkeypatch):
    class Proc:
        returncode = 1
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr(joplin_backend, "find_joplin", lambda _: "joplin")
    monkeypatch.setattr(joplin_backend.subprocess, "run", lambda *a, **k: Proc())
    cfg = joplin_backend.BackendConfig(binary="joplin", profile=None)
    with pytest.raises(RuntimeError):
        joplin_backend.run_joplin_command(["ls"], cfg)


def test_backend_run_command_node_warning_passes(monkeypatch):
    """A non-zero exit caused purely by benign Node warnings must not raise."""
    _WARNING = "(node:1234) [DEP0040] DeprecationWarning: The `punycode` module is deprecated."

    class Proc:
        returncode = 1
        stdout = ""
        stderr = _WARNING

    monkeypatch.setattr(joplin_backend, "find_joplin", lambda _: "joplin")
    monkeypatch.setattr(joplin_backend.subprocess, "run", lambda *a, **k: Proc())
    cfg = joplin_backend.BackendConfig(binary="joplin", profile=None)
    result = joplin_backend.run_joplin_command(["ls"], cfg)
    assert result["returncode"] == 1
    # Raw streams are preserved verbatim — callers inspect them directly.
    assert result["stdout"] == ""
    assert result["stderr"] == _WARNING


def test_backend_run_command_node_warning_with_continuation_passes(monkeypatch):
    """Regression (P1): Node always appends a hint line after each warning:

        (node:…) [DEP0040] DeprecationWarning: …
        (Use `node --trace-deprecation …` to show where the warning was created)

    Before the fix, the continuation line was kept after scrubbing, making
    scrubbed_stderr non-empty, which caused run_joplin_command to raise even
    though the exit was caused only by benign Node noise.
    """
    _WARN = "(node:1234) [DEP0040] DeprecationWarning: The `punycode` module is deprecated."
    _HINT = "(Use `node --trace-deprecation ...` to show where the warning was created)"
    _STDERR = f"{_WARN}\n{_HINT}"

    class Proc:
        returncode = 1
        stdout = ""
        stderr = _STDERR

    monkeypatch.setattr(joplin_backend, "find_joplin", lambda _: "joplin")
    monkeypatch.setattr(joplin_backend.subprocess, "run", lambda *a, **k: Proc())
    cfg = joplin_backend.BackendConfig(binary="joplin", profile=None)
    # Must not raise — both lines are benign warning/hint noise.
    result = joplin_backend.run_joplin_command(["ls"], cfg)
    assert result["returncode"] == 1
    assert result["stderr"] == _STDERR  # raw stream still intact


def test_backend_run_json_parses_despite_warning_and_continuation_prefix(monkeypatch):
    """run_joplin_json must succeed when both the warning AND its hint line
    are emitted to stdout ahead of the JSON payload."""
    _WARN = "(node:7) [DEP0040] DeprecationWarning: The `punycode` module is deprecated."
    _HINT = "(Use `node --trace-deprecation ...` to show where the warning was created)"
    _JSON = '[{"title":"NoteA"}]'

    class Proc:
        returncode = 0
        stdout = f"{_WARN}\n{_HINT}\n{_JSON}"
        stderr = ""

    monkeypatch.setattr(joplin_backend, "find_joplin", lambda _: "joplin")
    monkeypatch.setattr(joplin_backend.subprocess, "run", lambda *a, **k: Proc())
    cfg = joplin_backend.BackendConfig(binary="joplin", profile=None)
    result = joplin_backend.run_joplin_json(["ls", "--format", "json"], cfg)
    assert isinstance(result["data"], list)
    assert result["data"][0]["title"] == "NoteA"


def test_backend_run_command_real_error_not_masked_by_warning_with_hint(monkeypatch):
    """A real Joplin error must surface even when stderr contains both the
    benign warning AND its continuation hint line before the error text."""

    class Proc:
        returncode = 1
        stdout = ""
        stderr = (
            "(node:1234) [DEP0040] DeprecationWarning: The `punycode` module is deprecated.\n"
            "(Use `node --trace-deprecation ...` to show where the warning was created)\n"
            "Error: Cannot find \"missing-note\"."
        )

    monkeypatch.setattr(joplin_backend, "find_joplin", lambda _: "joplin")
    monkeypatch.setattr(joplin_backend.subprocess, "run", lambda *a, **k: Proc())
    cfg = joplin_backend.BackendConfig(binary="joplin", profile=None)
    with pytest.raises(RuntimeError) as excinfo:
        joplin_backend.run_joplin_command(["cat", "missing-note"], cfg)
    assert "Cannot find" in str(excinfo.value)
    assert "DEP0040" not in str(excinfo.value)


def test_backend_run_command_real_error_alongside_warning_raises(monkeypatch):
    """Regression: a real Joplin error must surface even when stderr also
    contains the benign DEP0040 punycode deprecation warning."""

    class Proc:
        returncode = 1
        stdout = ""
        stderr = (
            "(node:1234) [DEP0040] DeprecationWarning: The `punycode` module is deprecated.\n"
            "Error: Cannot find \"missing-note\"."
        )

    monkeypatch.setattr(joplin_backend, "find_joplin", lambda _: "joplin")
    monkeypatch.setattr(joplin_backend.subprocess, "run", lambda *a, **k: Proc())
    cfg = joplin_backend.BackendConfig(binary="joplin", profile=None)
    with pytest.raises(RuntimeError) as excinfo:
        joplin_backend.run_joplin_command(["cat", "missing-note"], cfg)
    assert "Cannot find" in str(excinfo.value)
    # The benign warning line should be stripped from the surfaced error text.
    assert "DEP0040" not in str(excinfo.value)


def test_backend_run_command_nonzero_empty_output_raises(monkeypatch):
    """Regression for P1: a non-zero exit with empty stdout AND stderr must
    raise RuntimeError rather than returning ok=true silently.

    This covers real Joplin failures that produce no output at all (e.g.
    `rmnote` on a non-existent note in some builds, or a process killed by a
    signal without printing anything).
    """
    class Proc:
        returncode = 1
        stdout = ""
        stderr = ""

    monkeypatch.setattr(joplin_backend, "find_joplin", lambda _: "joplin")
    monkeypatch.setattr(joplin_backend.subprocess, "run", lambda *a, **k: Proc())
    cfg = joplin_backend.BackendConfig(binary="joplin", profile=None)
    with pytest.raises(RuntimeError) as excinfo:
        joplin_backend.run_joplin_command(["rmnote", "ghost-note"], cfg)
    msg = str(excinfo.value)
    assert "exit" in msg.lower() or "code" in msg.lower() or "1" in msg
    assert "rmnote" in msg


def test_backend_run_command_nonzero_exit2_empty_output_raises(monkeypatch):
    """Non-zero exit codes other than 1 (e.g. 2 = usage error, 127 = command
    not found) must also be treated as failures when output is empty."""
    class Proc:
        returncode = 2
        stdout = ""
        stderr = ""

    monkeypatch.setattr(joplin_backend, "find_joplin", lambda _: "joplin")
    monkeypatch.setattr(joplin_backend.subprocess, "run", lambda *a, **k: Proc())
    cfg = joplin_backend.BackendConfig(binary="joplin", profile=None)
    with pytest.raises(RuntimeError) as excinfo:
        joplin_backend.run_joplin_command(["ls"], cfg)
    assert "2" in str(excinfo.value)


def test_backend_run_command_warning_only_nonzero_still_succeeds(monkeypatch):
    """Verify the positive-proof path still works: if ALL output is purely
    benign Node warnings (and scrubbing reduces it to empty), a non-zero exit
    is accepted as a warning-only run rather than a failure."""
    _WARNING = "(node:1234) [DEP0040] DeprecationWarning: The `punycode` module is deprecated."
    _HINT = "(Use `node --trace-deprecation ...` to show where the warning was created)"

    class Proc:
        returncode = 1
        stdout = ""
        stderr = f"{_WARNING}\n{_HINT}"

    monkeypatch.setattr(joplin_backend, "find_joplin", lambda _: "joplin")
    monkeypatch.setattr(joplin_backend.subprocess, "run", lambda *a, **k: Proc())
    cfg = joplin_backend.BackendConfig(binary="joplin", profile=None)
    # Must NOT raise — the only content is benign warnings.
    result = joplin_backend.run_joplin_command(["ls"], cfg)
    assert result["returncode"] == 1
    assert result["stderr"] == f"{_WARNING}\n{_HINT}"


def test_backend_run_command_preserves_raw_stdout(monkeypatch):
    """run_joplin_command must pass stdout verbatim to callers.

    Multi-line note content, exported markdown, or JSON payloads with internal
    blank lines must not be altered.  The warning filter is only used internally
    for the error-decision branch.
    """
    _WARN = "(node:7) [DEP0040] DeprecationWarning: The `punycode` module is deprecated."
    _JSON = '[{"title":"NoteA"}]'
    _RAW = f"{_WARN}\n{_JSON}"

    class Proc:
        returncode = 0
        stdout = _RAW
        stderr = ""

    monkeypatch.setattr(joplin_backend, "find_joplin", lambda _: "joplin")
    monkeypatch.setattr(joplin_backend.subprocess, "run", lambda *a, **k: Proc())
    cfg = joplin_backend.BackendConfig(binary="joplin", profile=None)
    result = joplin_backend.run_joplin_command(["ls", "--format", "json"], cfg)
    # Verbatim: the warning line is still present in the raw result.
    assert result["stdout"] == _RAW


def test_backend_run_json_parses_despite_warning_prefix(monkeypatch):
    """run_joplin_json must produce valid JSON data even when a Node warning is
    emitted to stdout ahead of the JSON payload (a known Joplin-on-Node20 issue
    where the warning sometimes leaks through to stdout rather than stderr)."""
    _WARN = "(node:7) [DEP0040] DeprecationWarning: The `punycode` module is deprecated."
    _JSON = '[{"title":"NoteA"}]'

    class Proc:
        returncode = 0
        stdout = f"{_WARN}\n{_JSON}"
        stderr = ""

    monkeypatch.setattr(joplin_backend, "find_joplin", lambda _: "joplin")
    monkeypatch.setattr(joplin_backend.subprocess, "run", lambda *a, **k: Proc())
    cfg = joplin_backend.BackendConfig(binary="joplin", profile=None)
    result = joplin_backend.run_joplin_json(["ls", "--format", "json"], cfg)
    # The caller receives usable structured data.
    assert isinstance(result["data"], list)
    assert result["data"][0]["title"] == "NoteA"


def test_backend_run_command_preserves_multiline_note_body(monkeypatch):
    """Blank lines inside legitimate note content must survive verbatim."""
    _BODY = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."

    class Proc:
        returncode = 0
        stdout = _BODY
        stderr = ""

    monkeypatch.setattr(joplin_backend, "find_joplin", lambda _: "joplin")
    monkeypatch.setattr(joplin_backend.subprocess, "run", lambda *a, **k: Proc())
    cfg = joplin_backend.BackendConfig(binary="joplin", profile=None)
    result = joplin_backend.run_joplin_command(["cat", "MyNote"], cfg)
    assert result["stdout"] == _BODY


def test_backend_run_command_timeout(monkeypatch):
    import subprocess

    monkeypatch.setattr(joplin_backend, "find_joplin", lambda _: "joplin")

    def fake_run(*a, **k):
        raise subprocess.TimeoutExpired(cmd="joplin", timeout=1)

    monkeypatch.setattr(joplin_backend.subprocess, "run", fake_run)
    cfg = joplin_backend.BackendConfig(binary="joplin", profile=None)
    with pytest.raises(RuntimeError) as excinfo:
        joplin_backend.run_joplin_command(["ls"], cfg, timeout=1)
    assert "timed out" in str(excinfo.value)


def _server_help_supporting_all_flags():
    return (
        "server <command>\n"
        "    --exit-early  Allow the command to exit while the server is still running...\n"
        "    --quiet       Log less information to the console...\n"
    )


def test_backend_server_start_exit_early_uses_finite_timeout(monkeypatch):
    """P2 regression: server_start(exit_early=True) must pass a finite timeout."""
    captured = {}

    def fake(args, cfg, timeout=120):
        if args[:1] == ["help"]:
            return {"command": args, "returncode": 0, "stdout": _server_help_supporting_all_flags(), "stderr": ""}
        captured["args"] = args
        captured["timeout"] = timeout
        return {"command": args, "returncode": 0, "stdout": "", "stderr": ""}

    backend_core._FLAG_SUPPORT_CACHE.clear()
    monkeypatch.setattr(backend_core, "find_joplin", lambda _: "joplin")
    monkeypatch.setattr(backend_core, "run_joplin_command", fake)
    cfg = joplin_backend.BackendConfig()
    backend_core.server_start(cfg, exit_early=True)
    assert captured["args"] == ["server", "start", "--exit-early"]
    assert captured["timeout"] is not None
    assert captured["timeout"] > 0


def test_backend_server_start_no_exit_early_uses_no_timeout(monkeypatch):
    """P2 regression: server_start(exit_early=False) must pass timeout=None so
    a long-lived server process is never killed by a hard deadline."""
    captured = {}

    def fake(args, cfg, timeout=120):
        # exit_early=False must NOT probe (no flag to gate)
        if args[:1] == ["help"]:
            captured.setdefault("help_called", True)
        captured["args"] = args
        captured["timeout"] = timeout
        return {"command": args, "returncode": 0, "stdout": "", "stderr": ""}

    backend_core._FLAG_SUPPORT_CACHE.clear()
    monkeypatch.setattr(backend_core, "run_joplin_command", fake)
    cfg = joplin_backend.BackendConfig()
    backend_core.server_start(cfg, exit_early=False)
    assert captured["args"] == ["server", "start"]
    assert captured["timeout"] is None, (
        f"Expected timeout=None for --wait mode, got {captured['timeout']}"
    )
    assert "help_called" not in captured, "Should not probe help when no flag is needed"


def test_backend_server_start_refuses_when_exit_early_unsupported(monkeypatch):
    """Regression: on older Joplin builds that don't advertise --exit-early,
    refuse rather than silently send a flag Joplin would ignore (which would
    leave the harness blocked forever waiting for the foreground server)."""
    sent = []

    def fake(args, cfg, timeout=120):
        if args[:1] == ["help"]:
            # Old Joplin: usage only, no flags listed.
            return {"command": args, "returncode": 0, "stdout": "server <command>\n", "stderr": ""}
        sent.append(args)
        return {"command": args, "returncode": 0, "stdout": "", "stderr": ""}

    backend_core._FLAG_SUPPORT_CACHE.clear()
    monkeypatch.setattr(backend_core, "run_joplin_command", fake)
    cfg = joplin_backend.BackendConfig()
    with pytest.raises(RuntimeError) as excinfo:
        backend_core.server_start(cfg, exit_early=True)
    assert "--exit-early" in str(excinfo.value)
    assert "exit_early=False" in str(excinfo.value)
    assert sent == [], "Server start command must not be sent when probe fails"


def test_backend_server_start_refuses_when_quiet_unsupported(monkeypatch):
    """Same defensive check for --quiet."""
    sent = []

    def fake(args, cfg, timeout=120):
        if args[:1] == ["help"]:
            # Build that has --exit-early but not --quiet.
            return {"command": args, "returncode": 0, "stdout": "server\n    --exit-early ...\n", "stderr": ""}
        sent.append(args)
        return {"command": args, "returncode": 0, "stdout": "", "stderr": ""}

    backend_core._FLAG_SUPPORT_CACHE.clear()
    monkeypatch.setattr(backend_core, "run_joplin_command", fake)
    cfg = joplin_backend.BackendConfig()
    with pytest.raises(RuntimeError) as excinfo:
        backend_core.server_start(cfg, exit_early=True, quiet=True)
    assert "--quiet" in str(excinfo.value)
    assert sent == []


def test_backend_server_start_probe_cached_across_calls(monkeypatch):
    """The help probe must be cached per (binary, command, flag) so repeated
    server_start calls don't pay a subprocess cost each time."""
    help_calls = 0
    started = 0

    def fake(args, cfg, timeout=120):
        nonlocal help_calls, started
        if args[:1] == ["help"]:
            help_calls += 1
            return {"command": args, "returncode": 0, "stdout": _server_help_supporting_all_flags(), "stderr": ""}
        started += 1
        return {"command": args, "returncode": 0, "stdout": "", "stderr": ""}

    backend_core._FLAG_SUPPORT_CACHE.clear()
    monkeypatch.setattr(backend_core, "run_joplin_command", fake)
    cfg = joplin_backend.BackendConfig()
    for _ in range(3):
        backend_core.server_start(cfg, exit_early=True, quiet=True)
    # Two distinct flags (--exit-early, --quiet) => one probe each, both cached.
    assert help_calls == 2, f"expected 2 help probes total, got {help_calls}"
    assert started == 3


def test_backend_e2ee_decrypt_force_supported(monkeypatch):
    """When `joplin help e2ee` advertises -f, --force we send the long form."""
    captured = {}

    def fake(args, cfg, timeout=120):
        if args[:1] == ["help"]:
            return {"command": args, "returncode": 0,
                    "stdout": "e2ee\n    -f, --force  Do not ask for input on failure\n", "stderr": ""}
        captured["args"] = args
        return {"command": args, "returncode": 0, "stdout": "", "stderr": ""}

    backend_core._FLAG_SUPPORT_CACHE.clear()
    monkeypatch.setattr(backend_core, "run_joplin_command", fake)
    cfg = joplin_backend.BackendConfig()
    backend_core.e2ee_decrypt(cfg, force=True)
    assert captured["args"] == ["e2ee", "decrypt", "--force"]


def test_backend_e2ee_decrypt_force_refuses_when_unsupported(monkeypatch):
    """On builds that don't advertise --force, refuse rather than silently
    let the e2ee subprocess deadlock on an interactive master-password prompt."""
    sent = []

    def fake(args, cfg, timeout=120):
        if args[:1] == ["help"]:
            return {"command": args, "returncode": 0,
                    "stdout": "e2ee\n    -p, --password ...\n    -v, --verbose ...\n", "stderr": ""}
        sent.append(args)
        return {"command": args, "returncode": 0, "stdout": "", "stderr": ""}

    backend_core._FLAG_SUPPORT_CACHE.clear()
    monkeypatch.setattr(backend_core, "run_joplin_command", fake)
    cfg = joplin_backend.BackendConfig()
    with pytest.raises(RuntimeError) as excinfo:
        backend_core.e2ee_decrypt(cfg, force=True)
    assert "--force" in str(excinfo.value)
    assert "interactive" in str(excinfo.value).lower() or "prompt" in str(excinfo.value).lower()
    assert sent == []


def test_backend_e2ee_decrypt_no_force_skips_probe(monkeypatch):
    """force=False is the default; we must not probe help in the default path."""
    seen = []

    def fake(args, cfg, timeout=120):
        seen.append(args)
        return {"command": args, "returncode": 0, "stdout": "", "stderr": ""}

    backend_core._FLAG_SUPPORT_CACHE.clear()
    monkeypatch.setattr(backend_core, "run_joplin_command", fake)
    cfg = joplin_backend.BackendConfig()
    backend_core.e2ee_decrypt(cfg, encrypted_text="abc", retry_failed_items=True)
    assert seen == [["e2ee", "decrypt", "abc", "--retry-failed-items"]]


def test_backend_run_json_parse(monkeypatch):
    monkeypatch.setattr(
        joplin_backend,
        "run_joplin_command",
        lambda args, config, timeout=120: {"stdout": json.dumps({"a": 1}), "returncode": 0, "stderr": "", "command": args},
    )
    cfg = joplin_backend.BackendConfig()
    data = joplin_backend.run_joplin_json(["ls"], cfg)
    assert data["data"]["a"] == 1


def test_backend_run_json_fallback_text(monkeypatch):
    monkeypatch.setattr(
        joplin_backend,
        "run_joplin_command",
        lambda args, config, timeout=120: {"stdout": "plain text", "returncode": 0, "stderr": "", "command": args},
    )
    cfg = joplin_backend.BackendConfig()
    data = joplin_backend.run_joplin_json(["ls"], cfg)
    assert data["data"]["text"] == "plain text"


def test_backend_run_json_empty_stdout(monkeypatch):
    monkeypatch.setattr(
        joplin_backend,
        "run_joplin_command",
        lambda args, config, timeout=120: {"stdout": "", "returncode": 0, "stderr": "", "command": args},
    )
    cfg = joplin_backend.BackendConfig()
    data = joplin_backend.run_joplin_json(["ls"], cfg)
    assert data["data"] is None


# ---------------------------------------------------------------------------
# Core module argument shapes (white-box)
# ---------------------------------------------------------------------------


def test_notes_remove_passes_force_and_permanent(monkeypatch):
    captured = {}

    def fake(args, cfg, timeout=120):
        # The help-probe call goes through run_joplin_command too; emit a
        # stub that advertises --permanent so the probe returns True.
        if args[:1] == ["help"]:
            return {"returncode": 0, "stdout": "rmnote\n  --permanent  Deletes permanently.\n", "stderr": ""}
        captured["args"] = args
        return {"returncode": 0}

    note_core._PERMANENT_FLAG_SUPPORT_CACHE.clear()
    monkeypatch.setattr(note_core, "run_joplin_command", fake)
    note_core.remove_note(joplin_backend.BackendConfig(), "n1", force=True, permanent=True)
    assert "rmnote" in captured["args"]
    assert "--force" in captured["args"]
    assert "--permanent" in captured["args"]
    # Short forms must not be used: Joplin's published terminal reference for
    # rmnote pre-dates `--permanent`, and `-p` is also `--parent` elsewhere.
    assert "-p" not in captured["args"]


def test_notes_remove_without_permanent_skips_probe(monkeypatch):
    """When permanent=False we must NOT probe `joplin help` -- it would just
    be wasted subprocess work."""
    calls = []

    def fake(args, cfg, timeout=120):
        calls.append(args)
        return {"returncode": 0, "stdout": "", "stderr": ""}

    note_core._PERMANENT_FLAG_SUPPORT_CACHE.clear()
    monkeypatch.setattr(note_core, "run_joplin_command", fake)
    note_core.remove_note(joplin_backend.BackendConfig(), "n1", force=True, permanent=False)
    assert calls == [["rmnote", "n1", "--force"]]


def test_notes_remove_permanent_refuses_when_help_lacks_flag(monkeypatch):
    """Regression for P2: if the installed Joplin CLI doesn't advertise
    `--permanent` we must raise a clear error rather than send the flag
    (which Joplin would silently ignore, downgrading a permanent delete to
    a trash move)."""
    sent = []

    def fake(args, cfg, timeout=120):
        if args[:1] == ["help"]:
            # Old Joplin help output - no --permanent listed.
            return {"returncode": 0, "stdout": "rmnote\n  -f, --force  ...\n", "stderr": ""}
        sent.append(args)
        return {"returncode": 0}

    note_core._PERMANENT_FLAG_SUPPORT_CACHE.clear()
    monkeypatch.setattr(note_core, "run_joplin_command", fake)
    with pytest.raises(RuntimeError) as excinfo:
        note_core.remove_note(joplin_backend.BackendConfig(), "n1", force=True, permanent=True)
    msg = str(excinfo.value)
    assert "--permanent" in msg
    assert "Joplin terminal CLI" in msg
    # The actual rmnote command must not have been sent.
    assert sent == []


def test_notes_remove_permanent_support_cached(monkeypatch):
    """The help probe must be cached per binary so we don't pay a subprocess
    cost on every permanent delete."""
    help_calls = 0

    def fake(args, cfg, timeout=120):
        nonlocal help_calls
        if args[:1] == ["help"]:
            help_calls += 1
            return {"returncode": 0, "stdout": "--permanent  ...\n", "stderr": ""}
        return {"returncode": 0}

    note_core._PERMANENT_FLAG_SUPPORT_CACHE.clear()
    monkeypatch.setattr(note_core, "run_joplin_command", fake)
    cfg = joplin_backend.BackendConfig()
    note_core.remove_note(cfg, "n1", permanent=True)
    note_core.remove_note(cfg, "n2", permanent=True)
    note_core.remove_note(cfg, "n3", permanent=True)
    assert help_calls == 1


def test_notes_copy_with_notebook(monkeypatch):
    captured = {}

    def fake(args, cfg):
        captured["args"] = args
        return {"returncode": 0}

    monkeypatch.setattr(note_core, "run_joplin_command", fake)
    note_core.copy_note(joplin_backend.BackendConfig(), "n1", notebook="BookA")
    assert captured["args"] == ["cp", "n1", "BookA"]


def test_notes_copy_without_notebook(monkeypatch):
    captured = {}

    def fake(args, cfg):
        captured["args"] = args
        return {"returncode": 0}

    monkeypatch.setattr(note_core, "run_joplin_command", fake)
    note_core.copy_note(joplin_backend.BackendConfig(), "n1")
    assert captured["args"] == ["cp", "n1"]


def test_notes_move_args(monkeypatch):
    captured = {}

    monkeypatch.setattr(note_core, "run_joplin_command", lambda a, c: captured.setdefault("args", a) or {})
    note_core.move_note(joplin_backend.BackendConfig(), "n1", "BookB")
    assert captured["args"] == ["mv", "n1", "BookB"]


def test_notes_rename_args(monkeypatch):
    captured = {}

    monkeypatch.setattr(note_core, "run_joplin_command", lambda a, c: captured.setdefault("args", a) or {})
    note_core.rename_note(joplin_backend.BackendConfig(), "n1", "fresh")
    assert captured["args"] == ["ren", "n1", "fresh"]


def test_notes_get_verbose_passes_v(monkeypatch):
    captured = {}

    monkeypatch.setattr(note_core, "run_joplin_command", lambda a, c: captured.setdefault("args", a) or {})
    note_core.get_note(joplin_backend.BackendConfig(), "n1", verbose=True)
    assert captured["args"] == ["cat", "n1", "-v"]


def test_notes_list_uses_json_and_supported_ls_options(monkeypatch):
    captured = {}

    monkeypatch.setattr(note_core, "run_joplin_json", lambda a, c: captured.setdefault("args", a) or {})
    note_core.list_notes(
        joplin_backend.BackendConfig(),
        pattern="needle",
        limit=10,
        sort="updated_time",
        reverse=True,
        item_type="nt",
        long=True,
    )
    assert captured["args"] == [
        "ls",
        "needle",
        "-n",
        "10",
        "--sort",
        "updated_time",
        "--reverse",
        "--type",
        "nt",
        "--long",
        "--format",
        "json",
    ]


def test_notebooks_list_uses_json_and_ls_options(monkeypatch):
    captured = {}

    monkeypatch.setattr(notebook_core, "run_joplin_json", lambda a, c: captured.setdefault("args", a) or {})
    notebook_core.list_notebooks(
        joplin_backend.BackendConfig(),
        limit=3,
        sort="title",
        reverse=True,
        long=True,
    )
    assert captured["args"] == [
        "ls",
        "/",
        "--format",
        "json",
        "--limit",
        "3",
        "--sort",
        "title",
        "--reverse",
        "--long",
    ]


def test_notebooks_remove_passes_flags(monkeypatch):
    captured = {}

    def fake(args, cfg, timeout=120):
        captured.setdefault("args", args)
        return {"returncode": 0, "stdout": "", "stderr": ""}

    note_core._PERMANENT_FLAG_SUPPORT_CACHE.clear()
    monkeypatch.setattr(notebook_core, "run_joplin_command", fake)
    notebook_core.remove_notebook(joplin_backend.BackendConfig(), "BookA", force=True, permanent=False)
    assert captured["args"][:2] == ["rmbook", "BookA"]
    assert "--force" in captured["args"]
    assert "--permanent" not in captured["args"]
    assert "-p" not in captured["args"]


def test_notebooks_remove_permanent_refuses_when_help_lacks_flag(monkeypatch):
    """Same defensive check as for notes: refuse rather than silently move to
    trash on older Joplin CLI versions."""
    sent = []

    def fake(args, cfg, timeout=120):
        if args[:1] == ["help"]:
            return {"returncode": 0, "stdout": "rmbook\n  -f, --force  ...\n", "stderr": ""}
        sent.append(args)
        return {"returncode": 0}

    note_core._PERMANENT_FLAG_SUPPORT_CACHE.clear()
    # Both core modules probe through note_core helper; patch there too.
    monkeypatch.setattr(note_core, "run_joplin_command", fake)
    monkeypatch.setattr(notebook_core, "run_joplin_command", fake)
    with pytest.raises(RuntimeError) as excinfo:
        notebook_core.remove_notebook(joplin_backend.BackendConfig(), "BookA", force=True, permanent=True)
    assert "rmbook" in str(excinfo.value)
    assert "--permanent" in str(excinfo.value)
    assert sent == []


def test_notebooks_remove_permanent_long_form_when_supported(monkeypatch):
    """When help advertises --permanent we send the long form (NOT `-p`)."""
    captured = {}

    def fake(args, cfg, timeout=120):
        if args[:1] == ["help"]:
            return {"returncode": 0, "stdout": "--permanent ...\n", "stderr": ""}
        captured["args"] = args
        return {"returncode": 0}

    note_core._PERMANENT_FLAG_SUPPORT_CACHE.clear()
    monkeypatch.setattr(note_core, "run_joplin_command", fake)
    monkeypatch.setattr(notebook_core, "run_joplin_command", fake)
    notebook_core.remove_notebook(joplin_backend.BackendConfig(), "BookA", force=True, permanent=True)
    assert captured["args"] == ["rmbook", "BookA", "--force", "--permanent"]


def test_todos_args_correct(monkeypatch):
    captured = []

    def fake(args, cfg):
        captured.append(args)
        return {"returncode": 0}

    monkeypatch.setattr(todo_core, "run_joplin_command", fake)
    cfg = joplin_backend.BackendConfig()
    todo_core.create_todo(cfg, "Wash dishes")
    todo_core.toggle_todo(cfg, "Wash dishes")
    todo_core.clear_todo(cfg, "Wash dishes")
    todo_core.mark_done(cfg, "Wash dishes")
    todo_core.mark_undone(cfg, "Wash dishes")

    assert captured[0] == ["mktodo", "Wash dishes"]
    assert captured[1] == ["todo", "toggle", "Wash dishes"]
    assert captured[2] == ["todo", "clear", "Wash dishes"]
    assert captured[3] == ["done", "Wash dishes"]
    assert captured[4] == ["undone", "Wash dishes"]


def test_todos_list_uses_json_and_ls_options(monkeypatch):
    captured = {}

    monkeypatch.setattr(todo_core, "run_joplin_json", lambda a, c: captured.setdefault("args", a) or {})
    todo_core.list_todos(joplin_backend.BackendConfig(), limit=5, sort="created_time", reverse=True, long=True)
    assert captured["args"] == [
        "ls",
        "--type",
        "t",
        "--format",
        "json",
        "-n",
        "5",
        "--sort",
        "created_time",
        "--reverse",
        "--long",
    ]


def test_tags_tagnotes_uses_tag_list(monkeypatch):
    captured = {}

    monkeypatch.setattr(tag_core, "run_joplin_command", lambda a, c: captured.setdefault("args", a) or {})
    tag_core.tag_notes(joplin_backend.BackendConfig(), "work")
    assert captured["args"] == ["tag", "list", "work"]


def test_sync_import_config_and_backend_args(monkeypatch):
    # Non-help command invocations only; help probes are responded to inline
    # so they don't pollute the parity assertions below.
    captured = []

    def fake_command(args, cfg, timeout=120):
        if args[:1] == ["help"]:
            # Respond as if the modern Joplin CLI: advertise every flag we
            # may probe so server_start/e2ee_decrypt don't refuse.
            if args == ["help", "server"]:
                stdout = "server\n    --exit-early ...\n    --quiet ...\n"
            elif args == ["help", "e2ee"]:
                stdout = "e2ee\n    -f, --force ...\n"
            else:
                stdout = ""
            return {"command": args, "returncode": 0, "stdout": stdout, "stderr": ""}
        captured.append(args)
        return {"returncode": 0}

    backend_core._FLAG_SUPPORT_CACHE.clear()
    monkeypatch.setattr(sync_core, "run_joplin_command", fake_command)
    monkeypatch.setattr(interop_core, "run_joplin_command", fake_command)
    monkeypatch.setattr(config_core, "run_joplin_command", fake_command)
    monkeypatch.setattr(backend_core, "run_joplin_command", fake_command)

    cfg = joplin_backend.BackendConfig()
    sync_core.run_sync(cfg, target="2", upgrade=True, use_lock="0")
    interop_core.import_data(cfg, "in.enex", notebook="Inbox", fmt="enex", force=True, output_format="md")
    config_core.config_export(cfg, verbose=True)
    config_core.config_import_file(cfg, "settings.json")
    backend_core.version_info(cfg)
    backend_core.server_start(cfg, exit_early=True, quiet=True)
    backend_core.e2ee_decrypt_file(cfg, "encrypted.bin", output_dir="out")

    assert captured[0] == ["sync", "--target", "2", "--upgrade", "--use-lock", "0"]
    assert captured[1] == [
        "import",
        "in.enex",
        "Inbox",
        "--format",
        "enex",
        "--force",
        "--output-format",
        "md",
    ]
    assert captured[2] == ["config", "--export", "--verbose"]
    assert captured[3] == ["config", "--import-file", "settings.json"]
    assert captured[4] == ["version"]
    assert captured[5] == ["server", "start", "--exit-early", "--quiet"]
    assert captured[6] == ["e2ee", "decrypt-file", "encrypted.bin", "--output", "out"]


# ---------------------------------------------------------------------------
# backend version fallback for broken npm-global `joplin version`
# ---------------------------------------------------------------------------


def _write_joplin_package_json(path, version="3.6.2", description="Joplin CLI"):
    import json as _json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _json.dumps(
            {"name": "joplin", "version": version, "description": description}
        ),
        encoding="utf-8",
    )


def _force_version_failure(monkeypatch, message="Cannot find module '../package.json'"):
    def boom(args, cfg, timeout=120):
        assert args == ["version"]
        raise RuntimeError(message)

    monkeypatch.setattr(backend_core, "run_joplin_command", boom)


def test_backend_version_fallback_windows_shim_layout(tmp_path, monkeypatch):
    """Custom Windows prefix: `<prefix>/joplin.cmd` + sibling `node_modules`."""
    prefix = tmp_path / "joplin-cli"
    binary = prefix / "joplin.cmd"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text("@echo off", encoding="utf-8")
    _write_joplin_package_json(prefix / "node_modules" / "joplin" / "package.json")

    monkeypatch.setattr(backend_core, "find_joplin", lambda _b: str(binary))
    monkeypatch.setattr(backend_core, "_npm_global_root", lambda: None)
    _force_version_failure(monkeypatch)

    result = backend_core.version_info(joplin_backend.BackendConfig())
    assert result["returncode"] == 0
    assert result["stdout"] == "3.6.2"
    assert result["metadata"]["name"] == "joplin"
    assert "Fallback after broken Joplin version command" in result["stderr"]


def test_backend_version_fallback_unix_global_symlink(tmp_path, monkeypatch):
    """Unix npm default: `<prefix>/bin/joplin` symlink into `<prefix>/lib/node_modules/joplin/main.js`."""
    if not hasattr(os, "symlink"):
        pytest.skip("symlinks not supported on this platform")

    prefix = tmp_path / "usr-local"
    bin_dir = prefix / "bin"
    pkg_dir = prefix / "lib" / "node_modules" / "joplin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    pkg_dir.mkdir(parents=True, exist_ok=True)

    main_js = pkg_dir / "main.js"
    main_js.write_text("// joplin entry", encoding="utf-8")
    _write_joplin_package_json(pkg_dir / "package.json", version="3.5.1")

    binary = bin_dir / "joplin"
    try:
        os.symlink(main_js, binary)
    except (OSError, NotImplementedError):
        pytest.skip("could not create symlink (permission denied?)")

    monkeypatch.setattr(backend_core, "find_joplin", lambda _b: str(binary))
    monkeypatch.setattr(backend_core, "_npm_global_root", lambda: None)
    _force_version_failure(monkeypatch)

    result = backend_core.version_info(joplin_backend.BackendConfig())
    assert result["stdout"] == "3.5.1"
    assert result["metadata"]["name"] == "joplin"


def test_backend_version_fallback_unix_global_no_symlink(tmp_path, monkeypatch):
    """`<prefix>/bin/joplin` is a plain wrapper script (no symlink), package
    still lives at `<prefix>/lib/node_modules/joplin`."""
    prefix = tmp_path / "opt-node"
    bin_dir = prefix / "bin"
    pkg_dir = prefix / "lib" / "node_modules" / "joplin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    pkg_dir.mkdir(parents=True, exist_ok=True)
    _write_joplin_package_json(pkg_dir / "package.json", version="3.4.0")

    binary = bin_dir / "joplin"
    binary.write_text("#!/bin/sh\nexec node ../lib/node_modules/joplin/main.js \"$@\"\n", encoding="utf-8")

    monkeypatch.setattr(backend_core, "find_joplin", lambda _b: str(binary))
    monkeypatch.setattr(backend_core, "_npm_global_root", lambda: None)
    _force_version_failure(monkeypatch)

    result = backend_core.version_info(joplin_backend.BackendConfig())
    assert result["stdout"] == "3.4.0"


def test_backend_version_fallback_uses_npm_root_when_local_paths_miss(tmp_path, monkeypatch):
    """If none of the path-derived candidates exist, fall back to `npm root -g`."""
    binary = tmp_path / "stray-bin" / "joplin"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text("noop", encoding="utf-8")

    npm_root = tmp_path / "npm-global"
    _write_joplin_package_json(npm_root / "joplin" / "package.json", version="3.7.99")

    monkeypatch.setattr(backend_core, "find_joplin", lambda _b: str(binary))
    monkeypatch.setattr(backend_core, "_npm_global_root", lambda: npm_root)
    _force_version_failure(monkeypatch)

    result = backend_core.version_info(joplin_backend.BackendConfig())
    assert result["stdout"] == "3.7.99"


def test_backend_version_fallback_ignores_foreign_package_json(tmp_path, monkeypatch):
    """A non-Joplin `package.json` next to the binary must not impersonate metadata."""
    prefix = tmp_path / "shared-prefix"
    binary = prefix / "joplin.cmd"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text("@echo off", encoding="utf-8")

    foreign = prefix / "node_modules" / "joplin" / "package.json"
    foreign.parent.mkdir(parents=True, exist_ok=True)
    foreign.write_text('{"name": "something-else", "version": "0.0.1"}', encoding="utf-8")

    monkeypatch.setattr(backend_core, "find_joplin", lambda _b: str(binary))
    monkeypatch.setattr(backend_core, "_npm_global_root", lambda: None)
    _force_version_failure(monkeypatch)

    with pytest.raises(RuntimeError, match="package.json"):
        backend_core.version_info(joplin_backend.BackendConfig())


def test_backend_version_fallback_reraises_when_nothing_found(tmp_path, monkeypatch):
    binary = tmp_path / "nowhere" / "joplin"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text("noop", encoding="utf-8")

    monkeypatch.setattr(backend_core, "find_joplin", lambda _b: str(binary))
    monkeypatch.setattr(backend_core, "_npm_global_root", lambda: None)
    _force_version_failure(monkeypatch, message="Cannot find module '../package.json'")

    with pytest.raises(RuntimeError, match="package.json"):
        backend_core.version_info(joplin_backend.BackendConfig())


def test_backend_version_does_not_fallback_on_unrelated_error(tmp_path, monkeypatch):
    binary = tmp_path / "joplin.cmd"
    binary.write_text("@echo off", encoding="utf-8")
    monkeypatch.setattr(backend_core, "find_joplin", lambda _b: str(binary))
    _force_version_failure(monkeypatch, message="permission denied")

    with pytest.raises(RuntimeError, match="permission denied"):
        backend_core.version_info(joplin_backend.BackendConfig())


# ---------------------------------------------------------------------------
# Backend config resolution precedence
# ---------------------------------------------------------------------------


def test_backend_config_without_project_uses_defaults():
    joplin_cli._session = None
    cfg = joplin_cli._backend_config(None, None)
    assert cfg.binary == "joplin"
    assert cfg.profile is None


def test_backend_config_without_project_respects_cli_overrides():
    joplin_cli._session = None
    cfg = joplin_cli._backend_config("/custom/joplin", "/tmp/prof")
    assert cfg.binary == "/custom/joplin"
    assert cfg.profile == "/tmp/prof"


def test_backend_config_uses_project_backend_when_cli_omitted():
    """Regression: a project that persisted a custom backend binary and
    profile must keep using them when the user does not pass --binary /
    --profile explicitly."""
    joplin_cli._session = None
    sess = joplin_cli.get_session()
    proj = project_mod.create_project(
        name="custom",
        backend_binary="/opt/joplin-custom",
        backend_profile="/var/joplin-profile",
    )
    sess.set_project(proj)

    cfg = joplin_cli._backend_config(None, None)
    assert cfg.binary == "/opt/joplin-custom"
    assert cfg.profile == "/var/joplin-profile"


def test_backend_config_cli_overrides_beat_project_values():
    joplin_cli._session = None
    sess = joplin_cli.get_session()
    proj = project_mod.create_project(
        name="overridable",
        backend_binary="/opt/joplin-custom",
        backend_profile="/var/joplin-profile",
    )
    sess.set_project(proj)

    cfg = joplin_cli._backend_config("/usr/local/bin/joplin", "/tmp/other")
    assert cfg.binary == "/usr/local/bin/joplin"
    assert cfg.profile == "/tmp/other"


def test_backend_config_falls_back_to_default_binary_when_project_missing_backend():
    joplin_cli._session = None
    sess = joplin_cli.get_session()
    proj = project_mod.create_project(name="empty")
    proj["backend"] = {}
    sess.set_project(proj)

    cfg = joplin_cli._backend_config(None, None)
    assert cfg.binary == "joplin"
    assert cfg.profile is None


# ---------------------------------------------------------------------------
# JSON envelope shape
# ---------------------------------------------------------------------------


def test_json_envelope_shape():
    ok_payload = joplin_cli._json_envelope(True, "notes.list", data={"k": 1})
    assert ok_payload["ok"] is True
    assert ok_payload["command"] == "notes.list"
    assert ok_payload["data"]["k"] == 1
    assert ok_payload["error"] is None

    err = RuntimeError("boom")
    bad_payload = joplin_cli._json_envelope(False, "notes.create", data=None, error=err)
    assert bad_payload["ok"] is False
    assert bad_payload["command"] == "notes.create"
    assert bad_payload["data"] is None
    assert bad_payload["error"]["type"] == "RuntimeError"
    assert bad_payload["error"]["message"] == "boom"


# ---------------------------------------------------------------------------
# P2 regression: error envelope command ID consistency
# ---------------------------------------------------------------------------


def test_handle_error_command_id_simple_command(monkeypatch):
    """Single-word subcommand: `notes_list` → `notes.list`."""
    _mock_ok(monkeypatch)
    # Force the underlying core to raise so the error path fires.
    import cli_anything.joplin.core.notes as _note_core
    monkeypatch.setattr(_note_core, "list_notes", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    result = _json_invoke(monkeypatch, ["--json", "notes", "list"])
    assert result["ok"] is False
    assert result["command"] == "notes.list"


def test_handle_error_command_id_multi_word_subcommand_config(monkeypatch):
    """Multi-word subcommand: `config_import_file` must emit `config.import_file`,
    NOT `config.import.file`."""
    _mock_ok(monkeypatch)
    import cli_anything.joplin.core.config as _config_core
    monkeypatch.setattr(_config_core, "config_import_file", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no file")))
    result = _json_invoke(monkeypatch, ["--json", "config", "import-file", "settings.json"])
    assert result["ok"] is False
    assert result["command"] == "config.import_file", (
        f"Expected 'config.import_file', got '{result['command']}' — "
        "handle_error must use replace('_', '.', 1) not replace('_', '.')"
    )


def test_handle_error_command_id_multi_word_subcommand_backend(monkeypatch):
    """`backend_export_sync_status` must emit `backend.export_sync_status`."""
    _mock_ok(monkeypatch)
    import cli_anything.joplin.core.backend as _backend_core
    monkeypatch.setattr(_backend_core, "export_sync_status", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("err")))
    result = _json_invoke(monkeypatch, ["--json", "backend", "export-sync-status"])
    assert result["ok"] is False
    assert result["command"] == "backend.export_sync_status", (
        f"Expected 'backend.export_sync_status', got '{result['command']}'"
    )


def test_handle_error_command_id_e2ee_multi_word(monkeypatch):
    """`e2ee_target_status` → `e2ee.target_status`, `e2ee_decrypt_file` → `e2ee.decrypt_file`."""
    _mock_ok(monkeypatch)
    import cli_anything.joplin.core.backend as _backend_core

    monkeypatch.setattr(_backend_core, "e2ee_target_status", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("e2ee err")))
    r1 = _json_invoke(monkeypatch, ["--json", "e2ee", "target-status", "/some/path"])
    assert r1["command"] == "e2ee.target_status"

    monkeypatch.setattr(_backend_core, "e2ee_decrypt_file", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("e2ee err")))
    r2 = _json_invoke(monkeypatch, ["--json", "e2ee", "decrypt-file", "file.bin"])
    assert r2["command"] == "e2ee.decrypt_file"


# ---------------------------------------------------------------------------
# CLI JSON-contract integration (mocked backend)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_global_session():
    joplin_cli._session = None
    joplin_cli._json_output = False
    joplin_cli._repl_mode = False
    yield
    joplin_cli._session = None
    joplin_cli._json_output = False
    joplin_cli._repl_mode = False


def _mock_ok(monkeypatch):
    monkeypatch.setattr(joplin_cli, "_backend_config", lambda *a, **k: object())
    monkeypatch.setattr(joplin_cli.notebook_mod, "list_notebooks", lambda cfg, **kwargs: {"data": [{"title": "N1"}]})
    monkeypatch.setattr(joplin_cli.notebook_mod, "create_notebook", lambda cfg, title, parent=None: {"created": title})
    monkeypatch.setattr(joplin_cli.notebook_mod, "use_notebook", lambda cfg, notebook: {"used": notebook})
    monkeypatch.setattr(joplin_cli.notebook_mod, "remove_notebook", lambda cfg, notebook, force=True, permanent=False: {"removed": notebook})
    monkeypatch.setattr(joplin_cli.note_mod, "list_notes", lambda cfg, **kwargs: {"data": [{"title": "A"}]})
    monkeypatch.setattr(joplin_cli.note_mod, "create_note", lambda cfg, title: {"created": title})
    monkeypatch.setattr(joplin_cli.note_mod, "set_note_field", lambda cfg, note_ref, field, value: {"updated": note_ref})
    monkeypatch.setattr(joplin_cli.note_mod, "get_note", lambda cfg, note_ref, verbose=False: {"body": "x", "id": note_ref, "verbose": verbose})
    monkeypatch.setattr(joplin_cli.note_mod, "remove_note", lambda cfg, note_ref, force=True, permanent=False: {"removed": note_ref})
    monkeypatch.setattr(joplin_cli.note_mod, "copy_note", lambda cfg, note_ref, notebook=None: {"copied": note_ref})
    monkeypatch.setattr(joplin_cli.note_mod, "move_note", lambda cfg, item, notebook: {"moved": item, "to": notebook})
    monkeypatch.setattr(joplin_cli.note_mod, "rename_note", lambda cfg, item, new_name: {"renamed": item, "to": new_name})
    monkeypatch.setattr(joplin_cli.todo_mod, "list_todos", lambda cfg, **kwargs: {"data": [{"title": "T1"}]})
    monkeypatch.setattr(joplin_cli.todo_mod, "create_todo", lambda cfg, title: {"created": title})
    monkeypatch.setattr(joplin_cli.todo_mod, "toggle_todo", lambda cfg, pattern: {"toggled": pattern})
    monkeypatch.setattr(joplin_cli.todo_mod, "clear_todo", lambda cfg, pattern: {"cleared": pattern})
    monkeypatch.setattr(joplin_cli.todo_mod, "mark_done", lambda cfg, note_ref: {"done": note_ref})
    monkeypatch.setattr(joplin_cli.todo_mod, "mark_undone", lambda cfg, note_ref: {"undone": note_ref})
    monkeypatch.setattr(joplin_cli.tag_mod, "list_tags", lambda cfg: {"tags": ["t1"]})
    monkeypatch.setattr(joplin_cli.tag_mod, "add_tag", lambda cfg, tag, note: {"added": tag})
    monkeypatch.setattr(joplin_cli.tag_mod, "remove_tag", lambda cfg, tag, note: {"removed": tag})
    monkeypatch.setattr(joplin_cli.tag_mod, "note_tags", lambda cfg, note: {"tags": ["t1"]})
    monkeypatch.setattr(joplin_cli.tag_mod, "tag_notes", lambda cfg, tag: {"notes": ["NoteA"]})
    monkeypatch.setattr(joplin_cli.search_mod, "search", lambda cfg, pattern, notebook=None: {"hits": [pattern]})
    monkeypatch.setattr(joplin_cli.sync_mod, "run_sync", lambda cfg, **kwargs: {"synced": True})
    monkeypatch.setattr(joplin_cli.interop_mod, "import_data", lambda cfg, path, **kwargs: {"imported": path})
    monkeypatch.setattr(joplin_cli.interop_mod, "export_data", lambda cfg, path, fmt="jex", note=None, notebook=None: {"exported": path})
    monkeypatch.setattr(joplin_cli.config_mod, "config_get", lambda cfg, key, **kwargs: {key: "v"})
    monkeypatch.setattr(joplin_cli.config_mod, "config_set", lambda cfg, key, value: {key: value})
    monkeypatch.setattr(joplin_cli.config_mod, "config_list", lambda cfg, **kwargs: {"k": "v"})
    monkeypatch.setattr(joplin_cli.config_mod, "config_export", lambda cfg, **kwargs: {"exported": True})
    monkeypatch.setattr(joplin_cli.config_mod, "config_import_file", lambda cfg, file_path: {"imported": file_path})
    monkeypatch.setattr(joplin_cli.attach_mod, "attach_file", lambda cfg, note_ref, file_path: {"attached": file_path, "note": note_ref})
    monkeypatch.setattr(joplin_cli.status_mod, "get_status", lambda cfg: {"raw": "Sync status"})
    monkeypatch.setattr(joplin_cli.status_mod, "restore_items", lambda cfg, pattern: {"restored": pattern})
    monkeypatch.setattr(joplin_cli.backend_mod, "version_info", lambda cfg: {"version": "3.x"})
    monkeypatch.setattr(joplin_cli.backend_mod, "dump_database", lambda cfg: {"data": []})
    monkeypatch.setattr(joplin_cli.backend_mod, "keymap", lambda cfg: {"keymap": True})
    monkeypatch.setattr(joplin_cli.backend_mod, "geoloc", lambda cfg, note_ref: {"note": note_ref})
    monkeypatch.setattr(joplin_cli.backend_mod, "export_sync_status", lambda cfg: {"exported": True})
    monkeypatch.setattr(joplin_cli.backend_mod, "server_status", lambda cfg: {"status": "stopped"})
    monkeypatch.setattr(joplin_cli.backend_mod, "server_start", lambda cfg, exit_early=True, quiet=False: {"started": True})
    monkeypatch.setattr(joplin_cli.backend_mod, "server_stop", lambda cfg: {"stopped": True})
    monkeypatch.setattr(joplin_cli.backend_mod, "e2ee_status", lambda cfg: {"enabled": False})
    monkeypatch.setattr(joplin_cli.backend_mod, "e2ee_target_status", lambda cfg, target_path, verbose=False: {"target": target_path})
    monkeypatch.setattr(joplin_cli.backend_mod, "e2ee_decrypt", lambda cfg, **kwargs: {"decrypted": True})
    monkeypatch.setattr(joplin_cli.backend_mod, "e2ee_decrypt_file", lambda cfg, file_path, output_dir=None: {"file": file_path})


def _invoke(monkeypatch, args):
    runner = CliRunner()
    return runner.invoke(joplin_cli.cli, args)


def _json_invoke(monkeypatch, args):
    return json.loads(_invoke(monkeypatch, args).output)


def test_json_contract_notebooks_group(monkeypatch):
    _mock_ok(monkeypatch)
    assert _json_invoke(monkeypatch, ["--json", "notebooks", "list"])["command"] == "notebooks.list"
    assert _json_invoke(
        monkeypatch,
        ["--json", "notebooks", "list", "--limit", "5", "--sort", "title", "--reverse", "--long"],
    )["command"] == "notebooks.list"
    assert _json_invoke(monkeypatch, ["--json", "notebooks", "create", "BookA"])["command"] == "notebooks.create"
    assert _json_invoke(monkeypatch, ["--json", "notebooks", "use", "BookA"])["command"] == "notebooks.use"
    assert _json_invoke(monkeypatch, ["--json", "notebooks", "remove", "BookA"])["command"] == "notebooks.remove"


def test_json_contract_notes_group(monkeypatch):
    _mock_ok(monkeypatch)
    assert _json_invoke(monkeypatch, ["--json", "notes", "list"])["command"] == "notes.list"
    assert _json_invoke(
        monkeypatch,
        ["--json", "notes", "list", "--pattern", "A", "--limit", "5", "--sort", "updated_time", "--reverse", "--type", "nt", "--long"],
    )["command"] == "notes.list"
    assert _json_invoke(monkeypatch, ["--json", "notes", "create", "A"])["command"] == "notes.create"
    assert _json_invoke(monkeypatch, ["--json", "notes", "set", "A", "title", "B"])["command"] == "notes.set"
    assert _json_invoke(monkeypatch, ["--json", "notes", "get", "A"])["command"] == "notes.get"
    assert _json_invoke(monkeypatch, ["--json", "notes", "get", "A", "--verbose"])["command"] == "notes.get"
    assert _json_invoke(monkeypatch, ["--json", "notes", "remove", "A"])["command"] == "notes.remove"
    assert _json_invoke(monkeypatch, ["--json", "notes", "copy", "A"])["command"] == "notes.copy"
    assert _json_invoke(monkeypatch, ["--json", "notes", "copy", "A", "BookB"])["command"] == "notes.copy"
    assert _json_invoke(monkeypatch, ["--json", "notes", "move", "A", "BookC"])["command"] == "notes.move"
    assert _json_invoke(monkeypatch, ["--json", "notes", "rename", "A", "B"])["command"] == "notes.rename"


def test_json_contract_todos_group(monkeypatch):
    _mock_ok(monkeypatch)
    assert _json_invoke(monkeypatch, ["--json", "todos", "list"])["command"] == "todos.list"
    assert _json_invoke(
        monkeypatch,
        ["--json", "todos", "list", "--limit", "5", "--sort", "created_time", "--reverse", "--long"],
    )["command"] == "todos.list"
    assert _json_invoke(monkeypatch, ["--json", "todos", "create", "task"])["command"] == "todos.create"
    assert _json_invoke(monkeypatch, ["--json", "todos", "toggle", "task"])["command"] == "todos.toggle"
    assert _json_invoke(monkeypatch, ["--json", "todos", "clear", "task"])["command"] == "todos.clear"
    assert _json_invoke(monkeypatch, ["--json", "todos", "done", "task"])["command"] == "todos.done"
    assert _json_invoke(monkeypatch, ["--json", "todos", "undone", "task"])["command"] == "todos.undone"


def test_json_contract_tags_group(monkeypatch):
    _mock_ok(monkeypatch)
    assert _json_invoke(monkeypatch, ["--json", "tags", "list"])["command"] == "tags.list"
    assert _json_invoke(monkeypatch, ["--json", "tags", "add", "t1", "n1"])["command"] == "tags.add"
    assert _json_invoke(monkeypatch, ["--json", "tags", "remove", "t1", "n1"])["command"] == "tags.remove"
    assert _json_invoke(monkeypatch, ["--json", "tags", "notetags", "n1"])["command"] == "tags.notetags"
    assert _json_invoke(monkeypatch, ["--json", "tags", "tagnotes", "t1"])["command"] == "tags.tagnotes"


def test_json_contract_search_sync_interop(monkeypatch):
    _mock_ok(monkeypatch)
    assert _json_invoke(monkeypatch, ["--json", "search", "run", "keyword"])["data"]["hits"] == ["keyword"]
    assert _json_invoke(monkeypatch, ["--json", "sync", "run"])["data"]["synced"] is True
    assert _json_invoke(monkeypatch, ["--json", "sync", "run", "--target", "2", "--upgrade", "--use-lock", "0"])["command"] == "sync.run"
    assert _json_invoke(monkeypatch, ["--json", "interop", "import", "in.enex"])["data"]["imported"] == "in.enex"
    assert _json_invoke(
        monkeypatch,
        ["--json", "interop", "import", "in.enex", "--format", "enex", "--force", "--output-format", "md"],
    )["command"] == "interop.import"
    assert _json_invoke(monkeypatch, ["--json", "interop", "export", "out.jex"])["data"]["exported"] == "out.jex"


def test_json_contract_config_session_attach_status(monkeypatch):
    _mock_ok(monkeypatch)
    assert _json_invoke(monkeypatch, ["--json", "config", "get", "locale"])["command"] == "config.get"
    assert _json_invoke(monkeypatch, ["--json", "config", "get", "locale", "--verbose"])["command"] == "config.get"
    assert _json_invoke(monkeypatch, ["--json", "config", "set", "locale", "en_US"])["command"] == "config.set"
    assert _json_invoke(monkeypatch, ["--json", "config", "list"])["command"] == "config.list"
    assert _json_invoke(monkeypatch, ["--json", "config", "list", "--verbose"])["command"] == "config.list"
    assert _json_invoke(monkeypatch, ["--json", "config", "export"])["command"] == "config.export"
    assert _json_invoke(monkeypatch, ["--json", "config", "import-file", "settings.json"])["command"] == "config.import_file"
    assert _json_invoke(monkeypatch, ["--json", "session", "status"])["command"] == "session.status"
    assert _json_invoke(monkeypatch, ["--json", "attach", "add", "noteA", "file.png"])["command"] == "attach.add"
    assert _json_invoke(monkeypatch, ["--json", "status", "show"])["command"] == "status.show"
    assert _json_invoke(monkeypatch, ["--json", "status", "restore", "*"])["command"] == "status.restore"


def test_json_contract_backend_server_e2ee(monkeypatch):
    _mock_ok(monkeypatch)
    assert _json_invoke(monkeypatch, ["--json", "backend", "version"])["command"] == "backend.version"
    assert _json_invoke(monkeypatch, ["--json", "backend", "dump"])["command"] == "backend.dump"
    assert _json_invoke(monkeypatch, ["--json", "backend", "keymap"])["command"] == "backend.keymap"
    assert _json_invoke(monkeypatch, ["--json", "backend", "geoloc", "noteA"])["command"] == "backend.geoloc"
    assert _json_invoke(monkeypatch, ["--json", "backend", "export-sync-status"])["command"] == "backend.export_sync_status"
    assert _json_invoke(monkeypatch, ["--json", "server", "status"])["command"] == "server.status"
    assert _json_invoke(monkeypatch, ["--json", "server", "start", "--quiet"])["command"] == "server.start"
    assert _json_invoke(monkeypatch, ["--json", "server", "stop"])["command"] == "server.stop"
    assert _json_invoke(monkeypatch, ["--json", "e2ee", "status"])["command"] == "e2ee.status"
    assert _json_invoke(monkeypatch, ["--json", "e2ee", "target-status", "target", "--verbose"])["command"] == "e2ee.target_status"
    assert _json_invoke(monkeypatch, ["--json", "e2ee", "decrypt", "encrypted", "--force"])["command"] == "e2ee.decrypt"
    assert _json_invoke(monkeypatch, ["--json", "e2ee", "decrypt-file", "file.bin", "--output", "out"])["command"] == "e2ee.decrypt_file"


def test_json_contract_project_status(monkeypatch, tmp_path):
    _mock_ok(monkeypatch)
    runner = CliRunner()

    project_path = tmp_path / "status.json"
    project_mod.save_project(project_mod.create_project(name="status"), str(project_path))

    result = runner.invoke(joplin_cli.cli, ["--json", "--project", str(project_path), "project", "status"])
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["command"] == "project.status"
    assert payload["data"]["project"]["name"] == "status"
    assert payload["data"]["project_path"] == str(project_path)


def test_json_contract_session_history(monkeypatch, tmp_path):
    _mock_ok(monkeypatch)
    runner = CliRunner()
    project_path = tmp_path / "hist.json"
    project_mod.save_project(project_mod.create_project(name="hist"), str(project_path))
    # mutate the project so a history entry is added
    result = runner.invoke(joplin_cli.cli, ["--json", "--project", str(project_path), "notebooks", "create", "Books"])
    assert result.exit_code == 0

    history = json.loads(runner.invoke(joplin_cli.cli, ["--json", "--project", str(project_path), "session", "history"]).output)
    assert history["ok"] is True
    assert history["command"] == "session.history"
    assert any(h["action"] == "notebook.create" for h in history["data"])


def test_json_contract_full_workflow(monkeypatch):
    _mock_ok(monkeypatch)

    workflow = [
        (["notebooks", "create", "BookA"], "notebooks.create"),
        (["notebooks", "use", "BookA"], "notebooks.use"),
        (["notes", "create", "NoteA"], "notes.create"),
        (["notes", "set", "NoteA", "title", "NoteB"], "notes.set"),
        (["notes", "copy", "NoteB"], "notes.copy"),
        (["notes", "rename", "NoteB", "Renamed"], "notes.rename"),
        (["notes", "move", "Renamed", "BookA"], "notes.move"),
        (["tags", "add", "TagA", "Renamed"], "tags.add"),
        (["tags", "notetags", "Renamed"], "tags.notetags"),
        (["tags", "tagnotes", "TagA"], "tags.tagnotes"),
        (["tags", "remove", "TagA", "Renamed"], "tags.remove"),
        (["todos", "create", "Buy milk"], "todos.create"),
        (["todos", "toggle", "Buy milk"], "todos.toggle"),
        (["todos", "done", "Buy milk"], "todos.done"),
        (["todos", "undone", "Buy milk"], "todos.undone"),
        (["todos", "clear", "Buy milk"], "todos.clear"),
        (["search", "run", "Renamed"], "search.run"),
        (["sync", "run"], "sync.run"),
        (["interop", "import", "in.enex"], "interop.import"),
        (["interop", "export", "out.jex"], "interop.export"),
        (["attach", "add", "Renamed", "/tmp/a.png"], "attach.add"),
        (["config", "list"], "config.list"),
        (["status", "show"], "status.show"),
        (["session", "status"], "session.status"),
    ]
    runner = CliRunner()
    for args, expected_cmd in workflow:
        result = runner.invoke(joplin_cli.cli, ["--json", *args])
        payload = json.loads(result.output)
        assert payload["ok"] is True, f"Workflow step {args} failed: {result.output}"
        assert payload["command"] == expected_cmd


# ---------------------------------------------------------------------------
# Error contract
# ---------------------------------------------------------------------------


def _raises_runtime(msg: str):
    def raiser(*a, **k):
        raise RuntimeError(msg)

    return raiser


def test_json_error_contract_search(monkeypatch):
    monkeypatch.setattr(joplin_cli, "_backend_config", lambda *a, **k: object())
    monkeypatch.setattr(joplin_cli.search_mod, "search", _raises_runtime("search failed"))
    runner = CliRunner()
    result = runner.invoke(joplin_cli.cli, ["--json", "search", "run", "abc"])
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["error"]["type"] == "RuntimeError"
    assert payload["error"]["message"] == "search failed"


def test_json_error_contract_note_missing(monkeypatch):
    monkeypatch.setattr(joplin_cli, "_backend_config", lambda *a, **k: object())
    monkeypatch.setattr(joplin_cli.note_mod, "get_note", _raises_runtime("Cannot find note"))
    runner = CliRunner()
    result = runner.invoke(joplin_cli.cli, ["--json", "notes", "get", "missing-note"])
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["command"] == "notes.get"


def test_json_error_contract_backend_missing(monkeypatch):
    monkeypatch.setattr(joplin_cli, "_backend_config", lambda *a, **k: object())
    monkeypatch.setattr(joplin_cli.tag_mod, "add_tag", _raises_runtime("Joplin terminal binary not found in PATH"))
    runner = CliRunner()
    result = runner.invoke(joplin_cli.cli, ["--json", "tags", "add", "t1", "n1"])
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert "not found" in payload["error"]["message"]


def test_json_error_contract_invalid_format(monkeypatch):
    monkeypatch.setattr(joplin_cli, "_backend_config", lambda *a, **k: object())
    monkeypatch.setattr(joplin_cli.interop_mod, "export_data", _raises_runtime("Unknown format: bogus"))
    runner = CliRunner()
    result = runner.invoke(joplin_cli.cli, ["--json", "interop", "export", "out.foo", "--format", "bogus"])
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert "Unknown format" in payload["error"]["message"]


def test_project_status_requires_project(monkeypatch):
    _mock_ok(monkeypatch)
    runner = CliRunner()
    result = runner.invoke(joplin_cli.cli, ["--json", "project", "status"])
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["command"] == "project.status"
    assert payload["error"]["message"] == "No project loaded"


def test_project_save_requires_path(monkeypatch):
    _mock_ok(monkeypatch)
    runner = CliRunner()
    result = runner.invoke(joplin_cli.cli, ["--json", "project", "save"])
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["command"] == "project.save"
    assert payload["error"]["message"] == "No project loaded"


# ---------------------------------------------------------------------------
# Auto-save / dry-run
# ---------------------------------------------------------------------------


def test_one_shot_mutation_auto_saves_project(monkeypatch, tmp_path):
    _mock_ok(monkeypatch)
    runner = CliRunner()

    project_path = tmp_path / "autosave.json"
    project_mod.save_project(project_mod.create_project(name="auto"), str(project_path))
    before = project_mod.open_project(str(project_path))
    before_hist = len(before["history"])

    result = runner.invoke(
        joplin_cli.cli,
        ["--json", "--project", str(project_path), "notebooks", "create", "AutoBook"],
    )
    assert result.exit_code == 0

    after = project_mod.open_project(str(project_path))
    assert len(after["history"]) >= before_hist + 2
    actions = [h.get("action") for h in after["history"]]
    assert "snapshot" in actions
    assert "notebook.create" in actions


def test_dry_run_suppresses_auto_save(monkeypatch, tmp_path):
    _mock_ok(monkeypatch)
    runner = CliRunner()

    project_path = tmp_path / "dryrun.json"
    project_mod.save_project(project_mod.create_project(name="dry"), str(project_path))
    before = project_mod.open_project(str(project_path))

    result = runner.invoke(
        joplin_cli.cli,
        ["--json", "--dry-run", "--project", str(project_path), "notebooks", "create", "DryBook"],
    )
    assert result.exit_code == 0

    after = project_mod.open_project(str(project_path))
    assert len(after["history"]) == len(before["history"])


def test_todo_workflow_writes_history(monkeypatch, tmp_path):
    _mock_ok(monkeypatch)
    runner = CliRunner()

    project_path = tmp_path / "todos.json"
    project_mod.save_project(project_mod.create_project(name="todos"), str(project_path))

    for args in (
        ["todos", "create", "task"],
        ["todos", "toggle", "task"],
        ["todos", "done", "task"],
        ["todos", "undone", "task"],
        ["todos", "clear", "task"],
    ):
        result = runner.invoke(
            joplin_cli.cli,
            ["--json", "--project", str(project_path), *args],
        )
        assert result.exit_code == 0

    after = project_mod.open_project(str(project_path))
    actions = [h.get("action") for h in after["history"]]
    for expected in ("todo.create", "todo.toggle", "todo.done", "todo.undone", "todo.clear"):
        assert expected in actions


def test_notebook_remove_writes_history(monkeypatch, tmp_path):
    _mock_ok(monkeypatch)
    runner = CliRunner()

    project_path = tmp_path / "rmbook.json"
    project_mod.save_project(project_mod.create_project(name="rmbook"), str(project_path))

    result = runner.invoke(
        joplin_cli.cli,
        ["--json", "--project", str(project_path), "notebooks", "remove", "BookA"],
    )
    assert result.exit_code == 0

    after = project_mod.open_project(str(project_path))
    assert any(h.get("action") == "notebook.remove" for h in after["history"])


def test_session_save_keeps_undo_redo_consistent(tmp_path):
    sess = Session()
    project_path = tmp_path / "session.json"

    proj = project_mod.create_project(name="persist")
    sess.set_project(proj, str(project_path))
    sess.snapshot("set notebook")
    sess.get_project()["context"]["current_notebook"] = "NB1"

    saved = sess.save_session()
    assert os.path.exists(saved)
    assert sess.status()["modified"] is False
    assert sess.status()["undo_depth"] == 1

    sess.undo()
    assert sess.get_project()["context"]["current_notebook"] is None
    assert sess.status()["redo_depth"] == 1

    sess.redo()
    assert sess.get_project()["context"]["current_notebook"] == "NB1"

    saved2 = sess.save_session()
    assert os.path.exists(saved2)
