import os
from types import SimpleNamespace

import pytest

from cli_anything.drawio.utils import drawio_backend


@pytest.fixture
def windows_without_path(monkeypatch):
    monkeypatch.setattr(drawio_backend, "sys", SimpleNamespace(platform="win32"), raising=False)
    monkeypatch.setattr(drawio_backend.shutil, "which", lambda name: None)
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
