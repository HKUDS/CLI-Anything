import os
import json
import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from cli_anything.freecad.freecad_cli import cli
from cli_anything.freecad.core.session import Session

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def temp_project(tmp_path):
    p = tmp_path / "test_project.json"
    return str(p)

def test_session_initial_state():
    session = Session()
    assert session.data["name"] == "Untitled"
    assert session.data["objects"] == []

def test_project_new(runner, temp_project):
    result = runner.invoke(cli, ["project", "new", "-o", temp_project, "--name", "TestProject"])
    if result.exit_code != 0:
        print(f"DEBUG: result.output = {result.output}")
        print(f"DEBUG: result.exception = {result.exception}")
    assert result.exit_code == 0
    assert "Created new project" in result.output
    
    with open(temp_project, "r") as f:
        data = json.load(f)
        assert data["name"] == "TestProject"

def test_sketch_add_circle(runner, temp_project):
    # Initialize project
    runner.invoke(cli, ["project", "new", "-o", temp_project])
    
    # Add circle
    result = runner.invoke(cli, ["--project", temp_project, "sketch", "add-circle", "--radius", "10"])
    assert result.exit_code == 0
    assert "Added circle" in result.output
    
    with open(temp_project, "r") as f:
        data = json.load(f)
        assert len(data["objects"]) == 1
        assert data["objects"][0]["type"] == "circle"
        assert data["objects"][0]["params"]["radius"] == 10.0

@patch("cli_anything.freecad.utils.freecad_backend.execute_freecad_python")
def test_export_render(mock_execute, runner, temp_project):
    mock_execute.return_value = {"success": True, "stdout": "OK", "stderr": ""}
    
    # Initialize project and add object
    runner.invoke(cli, ["project", "new", "-o", temp_project])
    runner.invoke(cli, ["--project", temp_project, "sketch", "add-circle", "--radius", "10"])
    
    # Export
    output_step = temp_project.replace(".json", ".step")
    result = runner.invoke(cli, ["--project", temp_project, "export", "render", "-o", output_step])
    
    assert result.exit_code == 0
    assert "Exported project" in result.output
    mock_execute.assert_called_once()
