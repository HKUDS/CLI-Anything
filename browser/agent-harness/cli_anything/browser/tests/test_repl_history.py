"""History storage must not prevent the browser or shared REPL from starting."""

import importlib.util
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner
from prompt_toolkit.application import create_app_session
from prompt_toolkit.history import FileHistory, InMemoryHistory
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput

from cli_anything.browser import browser_cli
from cli_anything.browser.utils import repl_skin


@pytest.fixture(params=["browser", "template"])
def skin_module(request):
    if request.param == "browser":
        return repl_skin
    repo = Path(__file__).resolve().parents[5]
    spec = importlib.util.spec_from_file_location(
        "shared_repl_skin", repo / "cli-anything-plugin" / "repl_skin.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def history_paths(tmp_path, monkeypatch):
    home, temporary = tmp_path / "home", tmp_path / "temp"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CLI_ANYTHING_HISTORY_DIR", raising=False)
    # All storage in these tests stays inside pytest's temporary directory.
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(temporary))
    temporary.mkdir()
    return home, temporary


def test_default_preserves_existing_history(skin_module, history_paths):
    home, _ = history_paths
    path = home / ".cli-anything-browser" / "history"
    path.parent.mkdir(parents=True)
    FileHistory(str(path)).append_string("fs pwd")

    skin = skin_module.ReplSkin("browser")

    assert Path(skin.history_file) == path
    assert list(FileHistory(skin.history_file).load_history_strings()) == ["fs pwd"]


def test_override_expands_home_and_separates_harnesses(
    skin_module, history_paths, monkeypatch
):
    home, _ = history_paths
    monkeypatch.setenv("CLI_ANYTHING_HISTORY_DIR", "~/command-history")

    browser = skin_module.ReplSkin("browser")
    shotcut = skin_module.ReplSkin("shotcut")

    root = home / "command-history"
    assert Path(browser.history_file) == root / ".cli-anything-browser" / "history"
    assert Path(shotcut.history_file) == root / ".cli-anything-shotcut" / "history"
    assert not (home / ".cli-anything-browser").exists()


def test_explicit_history_file_takes_precedence(
    skin_module, history_paths, monkeypatch
):
    home, _ = history_paths
    monkeypatch.setenv("CLI_ANYTHING_HISTORY_DIR", str(home / "override"))
    explicit = str(home / "explicit-history")

    assert skin_module.ReplSkin("browser", history_file=explicit).history_file == explicit
    assert not home.exists()


def test_denied_home_falls_back_to_writable_temp(
    skin_module, history_paths, monkeypatch
):
    home, temporary = history_paths
    original_mkdir = Path.mkdir

    def deny_home(path, *args, **kwargs):
        if path == home / ".cli-anything-browser":
            raise PermissionError("profile is read-only")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", deny_home)
    skin = skin_module.ReplSkin("browser")

    assert Path(skin.history_file) == temporary / ".cli-anything-browser" / "history"
    FileHistory(skin.history_file).append_string("fs pwd")
    assert list(FileHistory(skin.history_file).load_history_strings()) == ["fs pwd"]
    assert not home.exists()


def test_invalid_override_falls_back_to_temp(
    skin_module, history_paths, monkeypatch
):
    home, temporary = history_paths
    invalid = temporary / "a-file"
    invalid.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("CLI_ANYTHING_HISTORY_DIR", str(invalid))

    skin = skin_module.ReplSkin("browser")

    assert Path(skin.history_file) == temporary / ".cli-anything-browser" / "history"
    assert not home.exists()
    assert invalid.read_text(encoding="utf-8") == "not a directory"


def test_unwritable_history_file_falls_back_to_temp(
    skin_module, history_paths, monkeypatch
):
    home, temporary = history_paths
    original_open = Path.open

    def deny_history(path, *args, **kwargs):
        if path == home / ".cli-anything-browser" / "history":
            raise PermissionError("history file is read-only")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_history)
    skin = skin_module.ReplSkin("browser")

    assert Path(skin.history_file) == temporary / ".cli-anything-browser" / "history"


def test_no_writable_storage_uses_in_memory_history(
    skin_module, history_paths, monkeypatch
):
    def deny_storage(*args, **kwargs):
        raise PermissionError("read-only")

    monkeypatch.setattr(Path, "mkdir", deny_storage)
    skin = skin_module.ReplSkin("browser")

    assert skin.history_file is None
    with create_app_session(input=DummyInput(), output=DummyOutput()):
        session = skin.create_prompt_session()
    assert isinstance(session.history, InMemoryHistory)
    session.history.append_string("fs pwd")
    assert session.history.get_strings() == ["fs pwd"]


@pytest.mark.parametrize("args", [[], ["--daemon"]])
def test_browser_repl_reaches_input_with_denied_home(
    args, history_paths, monkeypatch
):
    home, temporary = history_paths
    original_mkdir = Path.mkdir

    def deny_home(path, *a, **kw):
        if path == home / ".cli-anything-browser":
            raise PermissionError("profile is read-only")
        return original_mkdir(path, *a, **kw)

    monkeypatch.setattr(Path, "mkdir", deny_home)
    monkeypatch.setattr(browser_cli, "_availability_cached", None)
    monkeypatch.setattr(browser_cli, "_session", None)
    monkeypatch.setattr(browser_cli, "_repl_mode", False)
    monkeypatch.setattr(browser_cli.backend, "is_available", lambda: (True, "test"))
    monkeypatch.setattr(browser_cli.backend, "start_daemon", lambda: None)
    prompts = []

    def quit_prompt(self, session, **kwargs):
        prompts.append(kwargs["context"])
        assert isinstance(session.history, FileHistory)
        session.history.append_string("quit")
        return "quit"

    monkeypatch.setattr(repl_skin.ReplSkin, "get_input", quit_prompt)
    with create_app_session(input=DummyInput(), output=DummyOutput()):
        result = CliRunner().invoke(browser_cli.cli, args)

    assert result.exit_code == 0, result.output
    assert "cli-anything" in result.output
    assert prompts == ["/"]
    history = FileHistory(str(temporary / ".cli-anything-browser" / "history"))
    assert list(history.load_history_strings()) == ["quit"]
