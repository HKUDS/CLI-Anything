import json
from pathlib import Path

from click.testing import CliRunner

from cli_anything.eez_studio import eez_studio_cli
from cli_anything.eez_studio.core import project as project_mod
from cli_anything.eez_studio.core import scpi as scpi_mod
from cli_anything.eez_studio.core.session import Session
from cli_anything.eez_studio.utils import eez_studio_backend
from cli_anything.eez_studio.eez_studio_cli import cli


def test_create_project_has_native_sections():
    project = project_mod.create_project(name="Panel", display_width=480, display_height=272)
    info = project_mod.project_info(project)
    assert project["settings"]["general"]["projectType"] == "lvgl"
    assert project["settings"]["general"]["lvglVersion"] == project_mod.DEFAULT_LVGL_VERSION
    assert project["settings"]["build"]["destinationFolder"] == "src/ui"
    assert project["userPages"][0]["components"][0]["type"] == "LVGLScreenWidget"
    assert info["page_count"] == 1


def test_save_load_round_trip(tmp_path):
    path = tmp_path / "panel.eez-project"
    project = project_mod.create_project(name="RoundTrip")
    result = project_mod.save_project(project, path)
    loaded = project_mod.load_project(path)
    assert result["bytes"] > 0
    assert loaded["settings"]["general"]["projectName"] == "RoundTrip"


def test_set_general_and_destination():
    project = project_mod.create_project()
    project_mod.set_general(project, "displayWidth", "1024")
    project_mod.set_build_destination(project, "firmware/ui")
    assert project["settings"]["general"]["displayWidth"] == 1024
    assert project["settings"]["build"]["destinationFolder"] == "firmware/ui"


def test_add_page_and_widgets():
    project = project_mod.create_project()
    project_mod.add_page(project, "Settings")
    project_mod.add_label(project, "Settings", "Voltage", name="voltage_label")
    project_mod.add_button(project, "Settings", "Apply", name="apply_button")
    widgets = project_mod.list_widgets(project, "Settings")
    assert len(project_mod.list_pages(project)) == 2
    assert any(widget["type"] == "LVGLLabelWidget" for widget in widgets)
    assert any(widget["type"] == "LVGLButtonWidget" for widget in widgets)


def test_scpi_subsystem_command_parameter():
    project = project_mod.create_project()
    scpi_mod.add_subsystem(project, "SOURCE")
    scpi_mod.add_command(project, "SOURCE", ":VOLTage?", response_type="nr3")
    scpi_mod.add_parameter(project, "SOURCE", ":VOLTage?", "channel", "nr1", optional=True)
    commands = scpi_mod.list_commands(project, "SOURCE")
    assert commands[0]["query"] is True
    assert commands[0]["parameters"] == 1


def test_session_undo_redo():
    session = Session("test")
    session.set_project(project_mod.create_project(), None)
    session.checkpoint()
    project_mod.add_label(session.project, "Main", "Ready")
    assert len(project_mod.list_widgets(session.project)) == 2
    assert session.undo() is True
    assert len(project_mod.list_widgets(session.project)) == 1
    assert session.redo() is True
    assert len(project_mod.list_widgets(session.project)) == 2


def test_cli_json_project_new(tmp_path):
    path = tmp_path / "cli.eez-project"
    runner = CliRunner()
    result = runner.invoke(cli, ["--json", "project", "new", "-o", str(path), "--name", "CLI"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["project_name"] == "CLI"
    assert path.is_file()


def test_cli_json_mutation_autosaves(tmp_path):
    path = tmp_path / "auto.eez-project"
    runner = CliRunner()
    result = runner.invoke(cli, ["--json", "project", "new", "-o", str(path)])
    assert result.exit_code == 0, result.output
    result = runner.invoke(cli, ["--json", "--project", str(path), "lvgl", "add-label", "--text", "Ready"])
    assert result.exit_code == 0, result.output
    loaded = project_mod.load_project(path)
    assert any(widget["text"] == "Ready" for widget in project_mod.list_widgets(loaded))


def test_repl_dispatch_preserves_open_session_mutation_and_undo(tmp_path):
    path = tmp_path / "repl.eez-project"
    runner = CliRunner()
    session = Session("repl-test")
    eez_studio_cli._session = session
    eez_studio_cli._repl_mode = True
    eez_studio_cli._json_output = False
    try:
        result = runner.invoke(cli, ["--json", "project", "new", "-o", str(path), "--name", "REPL"])
        assert result.exit_code == 0, result.output
        assert eez_studio_cli.get_session() is session
        assert session.project_path == str(path.resolve())

        result = runner.invoke(cli, ["--json", "--project", str(path), "lvgl", "add-label", "--text", "Unsaved"])
        assert result.exit_code == 0, result.output
        assert session.is_modified is True
        assert any(widget["text"] == "Unsaved" for widget in project_mod.list_widgets(session.project or {}))
        assert not any(widget.get("text") == "Unsaved" for widget in project_mod.list_widgets(project_mod.load_project(path)))

        result = runner.invoke(cli, ["--json", "--project", str(path), "session", "undo"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["undone"] is True
        assert not any(widget.get("text") == "Unsaved" for widget in project_mod.list_widgets(session.project or {}))
    finally:
        eez_studio_cli._session = None
        eez_studio_cli._repl_mode = False
        eez_studio_cli._json_output = False


def test_custom_build_command_uses_shlex_for_quoted_args(tmp_path, monkeypatch):
    project_path = tmp_path / "quoted project.eez-project"
    project_path.write_text("{}", encoding="utf-8")
    tool_path = tmp_path / "tool with spaces"
    captured = {}

    class Result:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(args, capture_output, text, timeout):
        captured["args"] = args
        captured["capture_output"] = capture_output
        captured["text"] = text
        captured["timeout"] = timeout
        return Result()

    monkeypatch.setenv("EEZ_STUDIO_BUILD_COMMAND", f'"{tool_path}" --flag "two words"')
    monkeypatch.setattr(eez_studio_backend.subprocess, "run", fake_run)

    result = eez_studio_backend.run_custom_build_command(str(project_path), timeout=12)

    assert captured["args"] == [str(tool_path), "--flag", "two words", str(project_path.resolve())]
    assert captured["capture_output"] is True
    assert captured["text"] is True
    assert captured["timeout"] == 12
    assert result["command"] == captured["args"]
