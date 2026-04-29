from __future__ import annotations

import importlib.util
from pathlib import Path


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
