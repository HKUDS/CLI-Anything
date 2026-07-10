from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from cli_anything.openrefine.utils.openrefine_backend import INSTALL_INSTRUCTIONS, OpenRefineBackend, OpenRefineError


def _resolve_cli(name):
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = "cli_anything.openrefine.openrefine_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


@pytest.fixture(scope="session")
def base_url():
    return os.environ.get("OPENREFINE_URL", "http://127.0.0.1:3333")


@pytest.fixture(scope="session")
def backend(base_url):
    client = OpenRefineBackend(base_url, timeout=15)
    try:
        deadline = time.time() + 10
        last = None
        while time.time() < deadline:
            try:
                client.ping()
                return client
            except Exception as exc:
                last = exc
                time.sleep(0.5)
        raise last or RuntimeError("unknown readiness failure")
    except Exception as exc:
        raise AssertionError(f"{INSTALL_INSTRUCTIONS}\nE2E backend check failed for {base_url}: {exc}") from exc


@pytest.fixture()
def sample_csv(tmp_path):
    path = tmp_path / "messy.csv"
    path.write_text("Name,City,Amount\n Alice ,NYC,1\nBob,SF,2\nAlice,NYC,3\n", encoding="utf-8")
    return path


@pytest.fixture()
def cli_base():
    return _resolve_cli("cli-anything-openrefine")


def _run(cli_base, args, check=True):
    result = subprocess.run(cli_base + args, capture_output=True, text=True, check=False)
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    if check and result.returncode != 0:
        raise AssertionError(f"Command failed: {args}\nstdout={result.stdout}\nstderr={result.stderr}")
    return result


def _project_id(payload):
    for key in ("project_id", "project", "projectID", "id"):
        if payload.get(key):
            return str(payload[key])
    if isinstance(payload.get("response"), dict):
        return _project_id(payload["response"])
    raise AssertionError(f"No project id in payload: {payload}")


def _cleanup(backend, project_id):
    try:
        backend.delete_project(project_id)
    except Exception as exc:
        print(f"cleanup failed for {project_id}: {exc}")


def test_e2e_backend_ping_reports_version(backend):
    payload = backend.ping()
    assert payload
    assert isinstance(payload, dict)


def test_e2e_import_csv_and_metadata(backend, sample_csv):
    created = backend.create_project(sample_csv, name="cli-anything-e2e-import")
    project_id = _project_id(created)
    try:
        metadata = backend.get_project_metadata(project_id)
        assert metadata
        assert "cli-anything-e2e" in json.dumps(metadata)
    finally:
        _cleanup(backend, project_id)


def test_e2e_get_rows_after_import(backend, sample_csv):
    created = backend.create_project(sample_csv, name="cli-anything-e2e-rows")
    project_id = _project_id(created)
    try:
        rows = backend.get_rows(project_id, limit=2)
        assert "rows" in rows
        assert len(rows["rows"]) >= 1
        assert "Alice" in json.dumps(rows)
    finally:
        _cleanup(backend, project_id)


def test_e2e_apply_text_transform_and_export_csv(backend, sample_csv, tmp_path):
    created = backend.create_project(sample_csv, name="cli-anything-e2e-transform")
    project_id = _project_id(created)
    try:
        operations = [{
            "op": "core/text-transform",
            "engineConfig": {"mode": "row-based", "facets": []},
            "columnName": "Name",
            "expression": "value.trim()",
            "onError": "keep-original",
            "repeat": False,
            "repeatCount": 10,
        }]
        backend.apply_operations(project_id, operations)
        output = backend.export_rows(project_id, tmp_path / "clean.csv")
        print(f"\n  CSV: {output} ({output.stat().st_size:,} bytes)")
        content = output.read_text(encoding="utf-8")
        assert " Alice " not in content
        assert "Alice" in content
    finally:
        _cleanup(backend, project_id)


def test_e2e_apply_mass_edit_normalizes_city(backend, sample_csv, tmp_path):
    created = backend.create_project(sample_csv, name="cli-anything-e2e-mass-edit")
    project_id = _project_id(created)
    try:
        operations = [{
            "op": "core/mass-edit",
            "engineConfig": {"mode": "row-based", "facets": []},
            "columnName": "City",
            "expression": "value",
            "edits": [{"from": ["NYC"], "fromBlank": False, "fromError": False, "to": "New York"}],
        }]
        backend.apply_operations(project_id, operations)
        output = backend.export_rows(project_id, tmp_path / "cities.csv")
        assert "New York" in output.read_text(encoding="utf-8")
    finally:
        _cleanup(backend, project_id)


def test_e2e_cli_help_subprocess(cli_base):
    result = _run(cli_base, ["--help"])
    assert "project" in result.stdout
    assert "data" in result.stdout


def test_e2e_cli_json_import_rows_export_workflow(backend, cli_base, sample_csv, tmp_path, base_url):
    session = tmp_path / "session.json"
    imported = _run(cli_base, ["--json", "--base-url", base_url, "--session", str(session), "project", "import", str(sample_csv), "--name", "cli-anything-e2e-cli"])
    payload = json.loads(imported.stdout)
    project_id = _project_id(payload)
    try:
        rows = _run(cli_base, ["--json", "--base-url", base_url, "--session", str(session), "data", "rows", "--limit", "2"])
        assert "Alice" in rows.stdout
        output = tmp_path / "cli-export.csv"
        exported = _run(cli_base, ["--json", "--base-url", base_url, "--session", str(session), "data", "export", str(output)])
        export_payload = json.loads(exported.stdout)
        assert export_payload["bytes"] > 0
        with output.open(newline="", encoding="utf-8") as handle:
            parsed = list(csv.reader(handle))
        assert parsed[0] == ["Name", "City", "Amount"]
    finally:
        _cleanup(backend, project_id)


def test_e2e_cli_build_apply_operation_file(backend, cli_base, sample_csv, tmp_path, base_url):
    session = tmp_path / "session.json"
    imported = _run(cli_base, ["--json", "--base-url", base_url, "--session", str(session), "project", "import", str(sample_csv), "--name", "cli-anything-e2e-ops"])
    project_id = _project_id(json.loads(imported.stdout))
    try:
        ops = tmp_path / "ops.json"
        _run(cli_base, ["--json", "ops", "text-transform", str(ops), "--column", "Name", "--expression", "value.trim()"])
        applied = _run(cli_base, ["--json", "--base-url", base_url, "--session", str(session), "data", "apply", str(ops)])
        assert json.loads(applied.stdout)["operation_count"] == 1
    finally:
        _cleanup(backend, project_id)


def test_e2e_cli_session_persistence(backend, cli_base, sample_csv, tmp_path, base_url):
    session = tmp_path / "session.json"
    imported = _run(cli_base, ["--json", "--base-url", base_url, "--session", str(session), "project", "import", str(sample_csv)])
    project_id = _project_id(json.loads(imported.stdout))
    try:
        shown = _run(cli_base, ["--json", "--session", str(session), "session", "show"])
        payload = json.loads(shown.stdout)
        assert payload["project_id"] == project_id
        assert payload["history"]
    finally:
        _cleanup(backend, project_id)


def test_e2e_backend_undo_redo_after_transform(backend, sample_csv):
    created = backend.create_project(sample_csv, name="cli-anything-e2e-undo")
    project_id = _project_id(created)
    try:
        backend.apply_operations(project_id, [{
            "op": "core/text-transform",
            "engineConfig": {"mode": "row-based", "facets": []},
            "columnName": "Name",
            "expression": "value.trim()",
            "onError": "keep-original",
            "repeat": False,
            "repeatCount": 10,
        }])
        assert backend.undo(project_id)
        assert backend.redo(project_id)
    finally:
        _cleanup(backend, project_id)


def test_e2e_cli_error_for_missing_project_is_json(cli_base, tmp_path, base_url):
    session = tmp_path / "empty-session.json"
    result = _run(cli_base, ["--json", "--base-url", base_url, "--session", str(session), "data", "rows"], check=False)
    assert result.returncode != 0
    payload = json.loads(result.stderr)
    assert payload["ok"] is False
    assert "No project selected" in payload["error"]


def test_e2e_recovery_delete_project_removes_from_listing(backend, sample_csv):
    created = backend.create_project(sample_csv, name="cli-anything-e2e-delete")
    project_id = _project_id(created)
    backend.delete_project(project_id)
    projects = backend.list_projects()
    assert project_id not in json.dumps(projects)
