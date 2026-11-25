import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest


def _resolve_cli():
    name = "cli-anything-unity2020"
    executable = shutil.which(name)
    if executable:
        print(f"Using installed command: {executable}")
        return [executable]
    if os.environ.get("CLI_ANYTHING_FORCE_INSTALLED") == "1":
        raise RuntimeError(f"{name} not found on PATH. Install the harness first.")
    return [sys.executable, "-m", "cli_anything.unity2020.unity2020_cli"]


@pytest.fixture
def editor():
    project = os.environ.get("CLI_ANYTHING_UNITY_PROJECT")
    if not project:
        pytest.fail("Set CLI_ANYTHING_UNITY_PROJECT to a disposable project open in Unity Edit Mode.")
    project = Path(project).resolve()
    cli = _resolve_cli()

    def command(*args, input_text=None, expected_code=0):
        process = subprocess.run(
            [*cli, "--project", str(project), "--json", "--timeout", "35", *args],
            capture_output=True, input=input_text, encoding="utf-8", timeout=45,
        )
        assert process.returncode == expected_code, (process.stdout, process.stderr)
        return json.loads(process.stdout)

    status = command("status")["data"]
    assert Path(status["projectPath"]) == project
    assert not status["isPlaying"]
    return project, command


def test_batch_reads_and_stops_at_failure(editor):
    _, command = editor
    request = [{"Command": "status"}, {"Command": "console.read", "Limit": 3},
               {"Command": "build.info"}, {"Command": "unknown"}, {"Command": "status"}]
    response = command("batch", "-", input_text=json.dumps(request), expected_code=1)
    results = response["data"]["results"]
    assert [entry["ok"] for entry in results] == [True, True, True, False]
    assert isinstance(results[1]["data"]["logs"], list)
    assert results[0]["data"]["buildTarget"] == results[2]["data"]["activeBuildTarget"]


def test_edit_save_and_render_in_unity(editor):
    project, command = editor
    name = f"CliAnything-{uuid4().hex}"
    asset_folder = f"Assets/{name}"
    scene = f"{asset_folder}/Example.unity"
    prefab = f"{asset_folder}/Cube.prefab"
    image = f"Temp/{name}.png"
    active = next(item for item in command("scenes")["data"]["scenes"] if item["active"])
    if not active["path"]:
        command("scene", "save", "--output", f"Assets/{name}-Initial.unity")
    command("scene", "create", scene, "--template", "default", "--additive")
    cube = command("gameobject", "create", "ExampleCube", "--primitive", "Cube")["data"]["objectId"]
    created = command("prefab", "create", prefab, "--id", str(cube))["data"]
    info = command("asset", "info", prefab)["data"]
    assert created["guid"] == info["guid"]
    assert (project / prefab).is_file()
    cameras = command("camera", "list")["data"]["cameras"]
    camera = next(item for item in cameras if item["scene"] == scene)
    command("camera", "capture", "--id", str(camera["objectId"]), "--width", "160", "--height", "90", "--output", image)
    output = project / image
    with output.open("rb") as file:
        header = file.read(24)
    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", header[16:24]) == (160, 90)
    print(f"Unity rendered {output}")
