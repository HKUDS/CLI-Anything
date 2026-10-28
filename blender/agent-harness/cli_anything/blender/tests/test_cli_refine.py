"""CLI-level tests for camera look-at and render --script-only."""

import json
import os

import pytest
from click.testing import CliRunner

from cli_anything.blender import blender_cli
from cli_anything.blender.blender_cli import cli


@pytest.fixture(autouse=True)
def fresh_session():
    """The CLI keeps a module-global session; reset it around each test."""
    blender_cli._session = None
    blender_cli._json_output = False
    yield
    blender_cli._session = None
    blender_cli._json_output = False


def _run(runner, *args):
    return runner.invoke(cli, list(args))


def _new_scene(runner):
    r = _run(runner, "scene", "new", "--name", "t")
    assert r.exit_code == 0, r.output


def test_camera_add_then_look_at_updates_list():
    runner = CliRunner()
    _new_scene(runner)
    r = _run(runner, "camera", "add", "--look-at", "1,2,3")
    assert r.exit_code == 0, r.output
    r = _run(runner, "camera", "look-at", "0", "4,5,6")
    assert r.exit_code == 0, r.output
    r = _run(runner, "--json", "camera", "list")
    assert r.exit_code == 0, r.output
    data = json.loads(r.output[r.output.index("["):])
    assert data[0]["look_at"] == [4, 5, 6]


def test_camera_look_at_bad_target_fails():
    runner = CliRunner()
    _new_scene(runner)
    assert _run(runner, "camera", "add").exit_code == 0
    r = _run(runner, "camera", "look-at", "0", "1,2")
    assert r.exit_code != 0, r.output


def test_render_script_only_writes_script_no_png(tmp_path):
    runner = CliRunner()
    _new_scene(runner)
    out = tmp_path / "out.png"
    r = _run(runner, "render", "execute", str(out), "--script-only")
    assert r.exit_code == 0, r.output
    assert (tmp_path / "_render_script.py").is_file()
    assert not out.exists()


def test_camera_look_at_equal_to_location_fails_cleanly():
    runner = CliRunner()
    _new_scene(runner)
    assert _run(runner, "camera", "add", "--location", "1,2,3").exit_code == 0
    r = _run(runner, "camera", "look-at", "0", "1,2,3")
    assert r.exit_code != 0, r.output
    assert "Traceback" not in r.output
    assert r.exception is None or isinstance(r.exception, SystemExit)
