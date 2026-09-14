from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "update_registry_dates.py"
SPEC = importlib.util.spec_from_file_location("update_registry_dates", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_resolve_harness_path_prefers_install_subdirectory_for_qgis():
    cli = {
        "name": "qgis",
        "install_cmd": "pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=QGIS/agent-harness",
        "skill_md": "QGIS/agent-harness/cli_anything/qgis/skills/SKILL.md",
    }

    path = MODULE.resolve_harness_path(cli, MODULE.REPO_ROOT)

    assert path == MODULE.REPO_ROOT / "QGIS" / "agent-harness"


def test_resolve_harness_path_handles_underscore_directory_names():
    cli = {
        "name": "unimol_tools",
        "install_cmd": "pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=unimol_tools/agent-harness",
        "skill_md": "skills/cli-anything-unimol-tools/SKILL.md",
    }

    path = MODULE.resolve_harness_path(cli, MODULE.REPO_ROOT)

    assert path == MODULE.REPO_ROOT / "unimol_tools" / "agent-harness"


def test_extract_external_source_url_from_cargo_git_install():
    cli = {
        "name": "clibrowser",
        "install_cmd": "cargo install --git https://github.com/allthingssecurity/clibrowser.git --tag v0.1.0 --locked",
        "source_url": None,
    }

    source_url = MODULE.extract_external_source_url(cli)

    assert source_url == "https://github.com/allthingssecurity/clibrowser"


def test_extract_npm_package_supports_scoped_package_names():
    cli = {
        "npm_package": "@sentry/cli",
        "install_cmd": "npm install -g @sentry/cli",
    }

    assert MODULE._extract_npm_package(cli) == "@sentry/cli"


@pytest.mark.parametrize(
    ("package_spec", "package_name"),
    [
        ("eslint", "eslint"),
        ("eslint@9.0.0", "eslint"),
        ("eslint@latest", "eslint"),
        ("@sentry/cli", "@sentry/cli"),
        ("@sentry/cli@2.42.0", "@sentry/cli"),
        ("@sentry/cli@latest", "@sentry/cli"),
    ],
)
def test_extract_npm_package_from_install_command(package_spec, package_name):
    cli = {"install_cmd": f"npm install -g {package_spec}"}

    assert MODULE._extract_npm_package(cli) == package_name


def test_get_npm_date_queries_package_without_version(monkeypatch):
    requested_urls = []

    def fetch_json(url):
        requested_urls.append(url)
        if url == "https://registry.npmjs.org/%40sentry%2Fcli":
            return {
                "dist-tags": {"latest": "2.43.0"},
                "time": {"2.43.0": "2026-09-01T12:00:00Z"},
            }
        return None

    monkeypatch.setattr(MODULE, "_fetch_json", fetch_json)
    cli = {"install_cmd": "npm install -g @sentry/cli@2.42.0"}

    assert MODULE.get_npm_date(cli) == "2026-09-01"
    assert requested_urls == ["https://registry.npmjs.org/%40sentry%2Fcli"]


def test_extract_pypi_package_supports_python_module_invocation():
    install_cmd = "python -m pip install py4csr"

    assert MODULE._extract_pypi_package(install_cmd) == "py4csr"


def test_extract_pypi_package_skips_index_option_values():
    install_cmd = (
        "python -m pip install --index-url https://mirror.example/simple "
        "--trusted-host mirror.example py4csr"
    )

    assert MODULE._extract_pypi_package(install_cmd) == "py4csr"


def test_extract_pypi_package_skips_editable_option_value():
    install_cmd = "pip install -e ./local/pkg py4csr"

    assert MODULE._extract_pypi_package(install_cmd) == "py4csr"


def test_extract_pypi_package_returns_none_for_editable_only_install():
    install_cmd = "pip install -e ."

    assert MODULE._extract_pypi_package(install_cmd) is None


def test_extract_pypi_package_strips_extras_and_version_specifier():
    install_cmd = "pip install 'requests[socks]>=2.32'"

    assert MODULE._extract_pypi_package(install_cmd) == "requests"
