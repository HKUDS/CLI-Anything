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
    name = "unity-legacy-cli"
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


def test_edit_rejects_non_finite_values(editor):
    _, command = editor
    name = f"CliAnything-{uuid4().hex}"
    cube = command("gameobject", "create", name, "--primitive", "Cube")["data"]["objectId"]
    for value in ("NaN", "Infinity", "-Infinity"):
        failure = command("component", "set", "--id", str(cube), "--component", "Transform",
                          "--property", "position", "--value", f"[{value},0,0]", expected_code=1)
        assert "finite" in failure["error"], failure
    applied = command("component", "set", "--id", str(cube), "--component", "Transform",
                      "--property", "position", "--value", "[1,2,3]")["data"]
    assert applied["before"] == [0, 0, 0], applied

    material = f"Assets/{name}.mat"
    command("material", "create", material, "--shader", "Standard")
    failure = command("material", "set", material, "--property", "_Metallic", "--value", "NaN",
                      expected_code=1)
    assert "finite" in failure["error"], failure
    failure = command("material", "set", material, "--property", "_Color", "--value", "0,Infinity,0,1",
                      expected_code=1)
    assert "finite" in failure["error"], failure
    properties = command("material", "inspect", "--asset", material)["data"]["material"]["properties"]
    metallic = next(item for item in properties if item["name"] == "_Metallic")
    assert metallic["value"]["number"] == 0, metallic


def test_ui_toolkit_inspect_is_bounded_and_create_is_atomic(editor):
    project, command = editor
    name = f"CliAnything-{uuid4().hex}"
    folder = f"Assets/{name}"
    for index in range(3):
        command("ui", "toolkit", "create", "--uxml", f"{folder}/Entry{index}.uxml",
                "--uss", f"{folder}/Entry{index}.uss")
    inspected = command("ui", "toolkit", "inspect", folder, "--limit", "1")["data"]
    assert len(inspected["uxml"]) == 1, inspected
    assert len(inspected["uss"]) == 1, inspected
    assert inspected["uxmlTruncated"] is True, inspected
    assert inspected["ussTruncated"] is True, inspected
    assert inspected["truncated"] is True, inspected

    blocked = f"{folder}/Blocked.uss"
    (project / blocked).mkdir()
    failure = command("ui", "toolkit", "create", "--uxml", f"{folder}/BlockedPair.uxml",
                      "--uss", blocked, "--force", expected_code=1)
    assert "directory" in failure["error"], failure
    assert not (project / folder / "BlockedPair.uxml").exists()

    pair_uxml = f"{folder}/Pair.uxml"
    command("ui", "toolkit", "create", "--uxml", pair_uxml, "--uss", f"{folder}/Pair.uss")
    original = (project / pair_uxml).read_bytes()
    (project / folder / "Blocker").write_text("not a folder", encoding="utf-8")
    failure = command("ui", "toolkit", "create", "--uxml", pair_uxml,
                      "--uss", f"{folder}/Blocker/Nested.uss", "--force", expected_code=1)
    assert "Blocker" in failure["error"], failure
    assert (project / pair_uxml).read_bytes() == original
    assert not (project / folder / "Blocker" / "Nested.uss").exists()
