import os
from types import SimpleNamespace

import pytest

from cli_anything.drawio.core.export import render_or_save
from cli_anything.drawio.core.session import Session
from cli_anything.drawio.utils import drawio_backend


@pytest.fixture
def windows_without_path(monkeypatch):
    monkeypatch.setattr(drawio_backend, "sys", SimpleNamespace(platform="win32"), raising=False)
    monkeypatch.setattr(drawio_backend.shutil, "which", lambda name: None)
    isfile = os.path.isfile
    monkeypatch.setattr(
        drawio_backend.os.path,
        "isfile",
        lambda path: path != "/Applications/draw.io.app/Contents/MacOS/draw.io" and isfile(path),
    )
    for name in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)", "LOCALAPPDATA"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize(
    ("variable", "subdirectory"),
    [
        ("ProgramFiles", ""),
        ("ProgramW6432", ""),
        ("ProgramFiles(x86)", ""),
        ("LOCALAPPDATA", "Programs"),
    ],
)
def test_find_drawio_in_windows_install_location(
    windows_without_path, monkeypatch, tmp_path, variable, subdirectory
):
    monkeypatch.setenv(variable, str(tmp_path))
    executable = tmp_path / subdirectory / "draw.io" / "draw.io.exe"
    executable.parent.mkdir(parents=True)
    executable.touch()
    assert os.path.normpath(drawio_backend.find_drawio()) == str(executable)


def test_find_drawio_prefers_path(windows_without_path, monkeypatch, tmp_path):
    executable = tmp_path / "draw.io.exe"
    monkeypatch.setattr(drawio_backend.shutil, "which", lambda name: str(executable))
    assert drawio_backend.find_drawio() == str(executable)


def test_missing_local_app_data_does_not_search_working_directory(
    windows_without_path, monkeypatch, tmp_path
):
    executable = tmp_path / "Programs" / "draw.io" / "draw.io.exe"
    executable.parent.mkdir(parents=True)
    executable.touch()
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError, match="winget install JGraph.Draw"):
        drawio_backend.find_drawio()


def test_export_saves_source_when_drawio_is_missing(windows_without_path, tmp_path):
    session = Session()
    session.new_project()
    output = tmp_path / "diagram.png"

    result = render_or_save(session, str(output))

    assert result["action"] == "export_fallback"
    assert result["drawio_file"] == str(output.with_suffix(".drawio"))
    assert output.with_suffix(".drawio").is_file()
    assert not output.exists()
