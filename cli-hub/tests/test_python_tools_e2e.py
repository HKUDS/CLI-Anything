"""Real, offline package-manager lifecycle tests using a local dependency-free wheel.

All uv tools, executables, caches, pip environments, and Hub state stay in pytest
temporary directories. No application harness or user-level package is installed.
"""

import json
import os
import shutil
import subprocess
import sys
import venv
import zipfile

import pytest

from cli_hub import installer, python_tools


@pytest.fixture
def local_harness(tmp_path, monkeypatch):
    wheel = tmp_path / "cli_anything_backend_smoke-1.0.0-py3-none-any.whl"
    info = "cli_anything_backend_smoke-1.0.0.dist-info"
    files = {
        "backend_smoke.py": 'def main():\n    print("BACKEND-SMOKE-OK")\n',
        f"{info}/METADATA": "Metadata-Version: 2.1\nName: cli-anything-backend-smoke\nVersion: 1.0.0\n",
        f"{info}/WHEEL": "Wheel-Version: 1.0\nGenerator: cli-hub-tests\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        f"{info}/entry_points.txt": "[console_scripts]\nbackend-smoke = backend_smoke:main\n",
    }
    files[f"{info}/RECORD"] = "".join(f"{path},,\n" for path in files) + f"{info}/RECORD,,\n"
    with zipfile.ZipFile(wheel, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    cli = {
        "name": "different-registry-slug", "display_name": "Backend Smoke", "version": "1.0.0",
        "entry_point": "backend-smoke", "_source": "harness",
        "install_cmd": f'pip install "{wheel.as_posix()}"',
    }
    monkeypatch.setattr(installer, "get_cli", lambda *a, **kw: cli.copy())
    monkeypatch.setattr(installer, "INSTALLED_FILE", tmp_path / "installed.json")
    for key, value in {
        "UV_TOOL_DIR": str(tmp_path / "uv-tools"),
        "UV_TOOL_BIN_DIR": str(tmp_path / "uv-bin"),
        "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
        "UV_PYTHON": sys.executable,
        "UV_PYTHON_DOWNLOADS": "never", "UV_OFFLINE": "1", "UV_NO_CONFIG": "1",
        "PIP_NO_INDEX": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_CONFIG_FILE": os.devnull,
    }.items():
        monkeypatch.setenv(key, value)
    return cli


@pytest.mark.skipif(shutil.which("uv") is None, reason="Real uv binary is required for this offline lifecycle test")
def test_real_uv_lifecycle_from_a_python_without_pip(local_harness, tmp_path):
    name = local_harness["name"]
    # uv tool environments do not need the caller's pip module at any point.
    ok, message = installer.install_cli(name)
    assert ok, message
    record = installer.get_installed()[name]
    assert record["python_backend"] == "uv"
    assert record["python_package"] == "cli-anything-backend-smoke"
    executable = tmp_path / "uv-bin" / ("backend-smoke.exe" if os.name == "nt" else "backend-smoke")
    launched = subprocess.run([str(executable)], capture_output=True, text=True, check=True)
    assert launched.stdout.strip() == "BACKEND-SMOKE-OK"
    ok, message = installer.update_cli(name)
    assert ok, message
    assert subprocess.run([str(executable)], capture_output=True, text=True, check=True).stdout.strip() == "BACKEND-SMOKE-OK"
    ok, message = installer.uninstall_cli(name)
    assert ok, message
    assert name not in installer.get_installed()
    assert not executable.exists()
    tools = subprocess.run([shutil.which("uv"), "tool", "list"], capture_output=True, text=True, check=True)
    assert "cli-anything-backend-smoke" not in tools.stdout


def test_real_pip_lifecycle_in_an_isolated_environment(local_harness, tmp_path, monkeypatch):
    environment = tmp_path / "pip-venv"
    venv.EnvBuilder(with_pip=True).create(environment)
    scripts = environment / ("Scripts" if os.name == "nt" else "bin")
    python = scripts / ("python.exe" if os.name == "nt" else "python")
    # Inject an interpreter for this test without changing the process-wide sys module.
    from types import SimpleNamespace
    monkeypatch.setattr(python_tools, "sys", SimpleNamespace(executable=str(python)))
    monkeypatch.setattr(installer, "_find_uv", lambda: None)
    name = local_harness["name"]
    ok, message = installer.install_cli(name)
    assert ok, message
    record = installer.get_installed()[name]
    assert record["python_backend"] == "pip"
    assert record["python_executable"] == str(python)
    executable = scripts / ("backend-smoke.exe" if os.name == "nt" else "backend-smoke")
    assert subprocess.run([str(executable)], capture_output=True, text=True, check=True).stdout.strip() == "BACKEND-SMOKE-OK"
    # A later Hub invocation in a different interpreter must still use this venv.
    monkeypatch.setattr(python_tools, "sys", SimpleNamespace(executable="not-the-owning-python"))
    assert installer.update_cli(name)[0]
    assert installer.uninstall_cli(name)[0]
    assert not executable.exists()
    assert json.loads(installer.INSTALLED_FILE.read_text()) == {}
