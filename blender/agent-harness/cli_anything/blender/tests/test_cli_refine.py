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


@pytest.mark.xfail(strict=True, reason="core.lighting.list_cameras omits 'look_at' from its summary dict")
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
