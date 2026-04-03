from __future__ import annotations

import json
import subprocess
from pathlib import Path


REGISTRY_PATH = Path(__file__).resolve().parents[1] / "workflow-registry.json"
PLUGIN_ROOT = REGISTRY_PATH.parent
COMMANDS_DIR = PLUGIN_ROOT / "commands"
README_PATH = PLUGIN_ROOT / "README.md"
QUICKSTART_PATH = PLUGIN_ROOT / "QUICKSTART.md"
PUBLISHING_PATH = PLUGIN_ROOT / "PUBLISHING.md"
VERIFY_SCRIPT = PLUGIN_ROOT / "verify-plugin.sh"
REQUIRED_FIELDS = {
    "command",
    "kind",
    "phaseSpan",
    "acceptedInputs",
    "artifactsOut",
    "publishType",
    "expectedFiles",
    "notes",
}


def load_registry() -> list[dict[str, object]]:
    assert REGISTRY_PATH.exists(), f"Missing workflow registry: {REGISTRY_PATH}"
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def command_docs() -> set[str]:
    return {path.stem for path in COMMANDS_DIR.glob("*.md")}


def assert_non_empty_string_list(values: object, field_name: str) -> None:
    assert isinstance(values, list), f"{field_name} must be a list"
    assert values, f"{field_name} must not be empty"
    for value in values:
        assert isinstance(value, str), f"{field_name} entries must be strings"
        assert value.strip(), f"{field_name} entries must not be blank"


def assert_expected_files_exist(values: object) -> None:
    assert_non_empty_string_list(values, "expectedFiles")
    for relative_path in values:
        path = PLUGIN_ROOT / relative_path
        assert path.exists(), f"Expected file does not exist: {path}"


def test_workflow_registry_parses() -> None:
    registry = load_registry()

    assert isinstance(registry, list)
    assert registry


def test_workflow_registry_contains_expected_commands() -> None:
    registry = load_registry()
    registry_commands = {entry["command"] for entry in registry}
    assert len(registry_commands) == len(registry), "Duplicate registry commands found"

    assert registry_commands == command_docs()


def test_workflow_registry_entries_have_required_fields() -> None:
    registry = load_registry()

    for entry in registry:
        assert REQUIRED_FIELDS.issubset(entry), entry
        assert isinstance(entry["command"], str) and entry["command"]
        assert isinstance(entry["kind"], str) and entry["kind"]
        assert isinstance(entry["phaseSpan"], str) and entry["phaseSpan"]
        assert_non_empty_string_list(entry["acceptedInputs"], "acceptedInputs")
        assert_non_empty_string_list(entry["artifactsOut"], "artifactsOut")
        assert isinstance(entry["publishType"], str) and entry["publishType"]
        assert_expected_files_exist(entry["expectedFiles"])
        assert isinstance(entry["notes"], str) and entry["notes"]


def test_workflow_registry_keeps_command_docs_in_sync() -> None:
    registry = load_registry()
    registry_docs = {
        Path(relative_path).stem
        for entry in registry
        for relative_path in entry["expectedFiles"]
        if relative_path.startswith("commands/") and relative_path.endswith(".md")
    }

    assert registry_docs == command_docs()


def test_verify_plugin_script_green_path() -> None:
    completed = subprocess.run(
        ["bash", str(VERIFY_SCRIPT)],
        cwd=PLUGIN_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "workflow-registry.json" in completed.stdout
    assert "commands/list.md" in completed.stdout
    assert "All checks passed" in completed.stdout


def test_docs_reflect_registry_vocabulary() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    quickstart = QUICKSTART_PATH.read_text(encoding="utf-8")
    publishing = PUBLISHING_PATH.read_text(encoding="utf-8")

    assert "Support for 4 commands" not in readme
    assert "Support for 5 commands: cli-anything, refine, test, validate, list" in readme
    assert "/cli-anything gimp" not in quickstart
    assert "/cli-anything /home/user/gimp" in quickstart
    assert "Initial release with 4 commands and complete 6-phase methodology" not in publishing
    assert "Initial release with 5 commands and complete 7-phase methodology" in publishing
