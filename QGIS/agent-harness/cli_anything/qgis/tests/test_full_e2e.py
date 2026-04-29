"""End-to-end and subprocess tests for cli-anything-qgis."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_PACKAGE_NAMESPACE_ROOT = Path(__file__).resolve().parents[2]
if str(_PACKAGE_NAMESPACE_ROOT) in sys.path:
    sys.path.remove(str(_PACKAGE_NAMESPACE_ROOT))

from cli_anything.qgis import qgis_cli
from cli_anything.qgis.core import project as project_mod
from cli_anything.qgis.qgis_cli import cli
from cli_anything.qgis.utils import qgis_backend as backend


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _resolve_cli(name: str) -> list[str]:
    """Resolve the CLI entry-point for subprocess tests.

    Prefers an installed command on PATH and falls back to ``python -m``
    unless ``CLI_ANYTHING_FORCE_INSTALLED=1`` is set.
    """
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    sibling = Path(sys.executable).parent / name
    if sibling.exists():
        print(f"[_resolve_cli] Using sibling command: {sibling}")
        return [str(sibling)]
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: python3 -m pip install -e .")
    module = "cli_anything.qgis.qgis_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


@pytest.fixture(autouse=True)
def clean_qgis_state(monkeypatch, tmp_path):
    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "offscreen"))

    backend.ensure_qgis_app()
    project = project_mod.current_project()
    project.clear()
    project.setFileName("")
    qgis_cli._session = None
    qgis_cli._json_output = False
    qgis_cli._repl_mode = False

    yield

    project.clear()
    project.setFileName("")
    qgis_cli._session = None
    qgis_cli._json_output = False
    qgis_cli._repl_mode = False


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _parse_json_output(raw: str) -> dict:
    return json.loads(raw)


def _invoke_json(runner: CliRunner, args: list[str]) -> dict:
    result = runner.invoke(cli, ["--json", *args])
    assert result.exit_code == 0, result.output
    return _parse_json_output(result.output)


def _subprocess_json(command: list[str], args: list[str], env: dict[str, str]) -> dict:
    completed = subprocess.run(
        [*command, "--json", *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return json.loads(completed.stdout)


def _build_cli_project(runner: CliRunner, tmp_path: Path, stem: str) -> dict[str, str]:
    project_path = tmp_path / f"{stem}.qgz"

    _invoke_json(runner, ["project", "new", "-o", str(project_path), "--title", stem])
    layer = _invoke_json(
        runner,
        [
            "--project",
            str(project_path),
            "layer",
            "create-vector",
            "--name",
            "areas",
            "--geometry",
            "polygon",
            "--field",
            "name:string",
            "--field",
            "score:int",
        ],
    )
    _invoke_json(
        runner,
        [
            "--project",
            str(project_path),
            "feature",
            "add",
            "--layer",
            "areas",
            "--wkt",
            "POLYGON((0 0,0 5,5 5,5 0,0 0))",
            "--attr",
            "name=ZoneA",
            "--attr",
            "score=5",
        ],
    )
    _invoke_json(runner, ["--project", str(project_path), "layout", "create", "--name", "Main"])
    _invoke_json(
        runner,
        [
            "--project",
            str(project_path),
            "layout",
            "add-map",
            "--layout",
            "Main",
            "--x",
            "10",
            "--y",
            "20",
            "--width",
            "180",
            "--height",
            "120",
        ],
    )
    _invoke_json(
        runner,
        [
            "--project",
            str(project_path),
            "layout",
            "add-label",
            "--layout",
            "Main",
            "--text",
            "Demo map",
            "--x",
            "10",
            "--y",
            "8",
            "--width",
            "100",
            "--height",
            "10",
        ],
    )

    return {
        "project_path": str(project_path),
        "layer_source": layer["source"],
    }


def _build_subprocess_project(command: list[str], tmp_path: Path, stem: str, env: dict[str, str]) -> dict[str, str]:
    project_path = tmp_path / f"{stem}.qgz"

    _subprocess_json(command, ["project", "new", "-o", str(project_path), "--title", stem], env)
    layer = _subprocess_json(
        command,
        [
            "--project",
            str(project_path),
            "layer",
            "create-vector",
            "--name",
            "areas",
            "--geometry",
            "polygon",
            "--field",
            "name:string",
            "--field",
            "score:int",
        ],
        env,
    )
    _subprocess_json(
        command,
        [
            "--project",
            str(project_path),
            "feature",
            "add",
            "--layer",
            "areas",
            "--wkt",
            "POLYGON((0 0,0 5,5 5,5 0,0 0))",
            "--attr",
            "name=ZoneA",
            "--attr",
            "score=5",
        ],
        env,
    )
    _subprocess_json(command, ["--project", str(project_path), "layout", "create", "--name", "Main"], env)
    _subprocess_json(
        command,
        [
            "--project",
            str(project_path),
            "layout",
            "add-map",
            "--layout",
            "Main",
            "--x",
            "10",
            "--y",
            "20",
            "--width",
            "180",
            "--height",
            "120",
        ],
        env,
    )
    _subprocess_json(
        command,
        [
            "--project",
            str(project_path),
            "layout",
            "add-label",
            "--layout",
            "Main",
            "--text",
            "Demo map",
            "--x",
            "10",
            "--y",
            "8",
            "--width",
            "100",
            "--height",
            "10",
        ],
        env,
    )

    return {
        "project_path": str(project_path),
        "layer_source": layer["source"],
    }


def _build_subprocess_point_project(
    command: list[str], tmp_path: Path, stem: str, env: dict[str, str]
) -> dict[str, str]:
    project_path = tmp_path / f"{stem}.qgz"

    _subprocess_json(command, ["project", "new", "-o", str(project_path), "--title", stem], env)
    layer = _subprocess_json(
        command,
        [
            "--project",
            str(project_path),
            "layer",
            "create-vector",
            "--name",
            "places",
            "--geometry",
            "point",
            "--field",
            "name:string",
            "--field",
            "score:int",
        ],
        env,
    )
    _subprocess_json(
        command,
        [
            "--project",
            str(project_path),
            "feature",
            "add",
            "--layer",
            "places",
            "--wkt",
            "POINT(116.397 39.907)",
            "--attr",
            "name=Beijing",
            "--attr",
            "score=5",
        ],
        env,
    )
    _subprocess_json(command, ["--project", str(project_path), "layout", "create", "--name", "Main"], env)

    return {
        "project_path": str(project_path),
        "layer_source": layer["source"],
    }


class TestRealCLIWorkflows:
    def test_scratch_project_to_pdf(self, runner: CliRunner, tmp_path: Path):
        build = _build_cli_project(runner, tmp_path, "pdf_workflow")
        pdf_path = tmp_path / "workflow.pdf"

        exported = _invoke_json(
            runner,
            [
                "--project",
                build["project_path"],
                "export",
                "pdf",
                str(pdf_path),
                "--layout",
                "Main",
                "--overwrite",
            ],
        )

        output_path = Path(exported["output"])
        assert output_path.exists()
        assert output_path.stat().st_size > 0
        assert output_path.read_bytes()[:5] == b"%PDF-"
        print(f"PDF artifact: {output_path}")

    def test_scratch_project_to_png(self, runner: CliRunner, tmp_path: Path):
        from qgis.PyQt.QtGui import QImage

        build = _build_cli_project(runner, tmp_path, "png_workflow")
        png_path = tmp_path / "workflow.png"

        exported = _invoke_json(
            runner,
            [
                "--project",
                build["project_path"],
                "export",
                "image",
                str(png_path),
                "--layout",
                "Main",
                "--overwrite",
            ],
        )

        output_path = Path(exported["output"])
        assert output_path.exists()
        assert output_path.read_bytes()[:8] == PNG_SIGNATURE

        image = QImage(str(output_path))
        assert not image.isNull()
        assert image.width() > 0
        assert image.height() > 0
        print(f"PNG artifact: {output_path}")

    def test_processing_passthrough_buffer(self, runner: CliRunner, tmp_path: Path):
        from qgis.core import QgsVectorLayer

        build = _build_cli_project(runner, tmp_path, "buffer_workflow")
        output_path = tmp_path / "buffer.geojson"

        data = _invoke_json(
            runner,
            [
                "--project",
                build["project_path"],
                "process",
                "run",
                "native:buffer",
                "--param",
                f"INPUT={build['layer_source']}",
                "--param",
                "DISTANCE=1",
                "--param",
                "SEGMENTS=8",
                "--param",
                "END_CAP_STYLE=0",
                "--param",
                "JOIN_STYLE=0",
                "--param",
                "MITER_LIMIT=2",
                "--param",
                "DISSOLVE=false",
                "--param",
                f"OUTPUT={output_path}",
            ],
        )

        result_path = Path(data["results"]["OUTPUT"])
        assert result_path.exists()

        backend.ensure_qgis_app()
        layer = QgsVectorLayer(str(result_path), "buffer", "ogr")
        assert layer.isValid()
        assert int(layer.featureCount()) > 0


class TestCLISubprocess:
    def test_help(self, tmp_path: Path):
        command = _resolve_cli("cli-anything-qgis")
        env = os.environ.copy()
        env["HOME"] = str(tmp_path / "home")
        env.setdefault("QT_QPA_PLATFORM", "offscreen")

        completed = subprocess.run([*command, "--help"], capture_output=True, text=True, check=False, env=env)
        assert completed.returncode == 0
        assert "QGIS CLI" in completed.stdout

    def test_process_help_json(self, tmp_path: Path):
        command = _resolve_cli("cli-anything-qgis")
        env = os.environ.copy()
        env["HOME"] = str(tmp_path / "home")
        env.setdefault("QT_QPA_PLATFORM", "offscreen")

        payload = _subprocess_json(command, ["process", "help", "native:printlayouttopdf"], env)
        assert payload["algorithm"]["id"] == "native:printlayouttopdf"

    def test_project_new_json(self, tmp_path: Path):
        command = _resolve_cli("cli-anything-qgis")
        env = os.environ.copy()
        env["HOME"] = str(tmp_path / "home")
        env.setdefault("QT_QPA_PLATFORM", "offscreen")

        project_path = tmp_path / "subprocess.qgz"
        payload = _subprocess_json(command, ["project", "new", "-o", str(project_path), "--title", "Subprocess"], env)
        assert payload["path"] == str(project_path.resolve())
        assert Path(payload["path"]).exists()

    def test_full_pdf_workflow(self, tmp_path: Path):
        command = _resolve_cli("cli-anything-qgis")
        env = os.environ.copy()
        env["HOME"] = str(tmp_path / "home")
        env.setdefault("QT_QPA_PLATFORM", "offscreen")

        build = _build_subprocess_project(command, tmp_path, "subprocess_pdf", env)
        pdf_path = tmp_path / "subprocess.pdf"
        exported = _subprocess_json(
            command,
            [
                "--project",
                build["project_path"],
                "export",
                "pdf",
                str(pdf_path),
                "--layout",
                "Main",
                "--overwrite",
            ],
            env,
        )

        output_path = Path(exported["output"])
        assert output_path.exists()
        assert output_path.stat().st_size > 0
        assert output_path.read_bytes()[:5] == b"%PDF-"
        print(f"Subprocess PDF artifact: {output_path}")

    def test_full_png_workflow(self, tmp_path: Path):
        command = _resolve_cli("cli-anything-qgis")
        env = os.environ.copy()
        env["HOME"] = str(tmp_path / "home")
        env.setdefault("QT_QPA_PLATFORM", "offscreen")

        build = _build_subprocess_project(command, tmp_path, "subprocess_png", env)
        png_path = tmp_path / "subprocess.png"
        exported = _subprocess_json(
            command,
            [
                "--project",
                build["project_path"],
                "export",
                "image",
                str(png_path),
                "--layout",
                "Main",
                "--overwrite",
            ],
            env,
        )

        output_path = Path(exported["output"])
        assert output_path.exists()
        assert output_path.read_bytes()[:8] == PNG_SIGNATURE
        print(f"Subprocess PNG artifact: {output_path}")

    def test_point_only_project_add_map_without_extent(self, tmp_path: Path):
        command = _resolve_cli("cli-anything-qgis")
        env = os.environ.copy()
        env["HOME"] = str(tmp_path / "home")
        env.setdefault("QT_QPA_PLATFORM", "offscreen")

        build = _build_subprocess_point_project(command, tmp_path, "subprocess_point", env)
        add_map = _subprocess_json(
            command,
            [
                "--project",
                build["project_path"],
                "layout",
                "add-map",
                "--layout",
                "Main",
                "--x",
                "10",
                "--y",
                "20",
                "--width",
                "180",
                "--height",
                "120",
            ],
            env,
        )
        assert any(item["type"] == "QgsLayoutItemMap" for item in add_map["items"])

        pdf_path = tmp_path / "subprocess_point.pdf"
        exported = _subprocess_json(
            command,
            [
                "--project",
                build["project_path"],
                "export",
                "pdf",
                str(pdf_path),
                "--layout",
                "Main",
                "--overwrite",
            ],
            env,
        )

        output_path = Path(exported["output"])
        assert output_path.exists()
        assert output_path.read_bytes()[:5] == b"%PDF-"
        print(f"Subprocess point-only PDF artifact: {output_path}")
