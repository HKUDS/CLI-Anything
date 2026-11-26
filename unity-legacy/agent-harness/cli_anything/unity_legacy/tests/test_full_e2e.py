import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

PROBE_SOURCE = """using UnityEngine;

public class CliAnythingNumericProbe : MonoBehaviour
{
    public decimal Amount;
    public long Big;
    public float Speed;
    public Vector2 Offset;
}
"""


def _bridge_request(project, command, arguments, timeout=15):
    """Send one request in the CLI's wire format and return the raw reply.

    ``ask_editor`` parses replies with binary floats, so a wide number such as a
    ``decimal`` member reads back rounded through the CLI. This helper inspects
    the bridge's own JSON to verify what was actually stored.
    """
    queue = project / "Library" / "UnityCli"
    queue.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    with tempfile.TemporaryDirectory(prefix="request-", dir=queue) as directory:
        job = Path(directory)
        staging = job / "request.tmp"
        staging.write_text(json.dumps({
            "Command": command,
            "ExpiresAt": int((time.time() + timeout) * 1000),
            **arguments,
        }), encoding="utf-8")
        staging.replace(job / "request.json")
        response = job / "response.json"
        while time.monotonic() < deadline:
            if response.is_file():
                return json.loads(response.read_text(encoding="utf-8"), parse_float=Decimal)
            time.sleep(0.02)
    raise AssertionError("bridge did not reply to the raw request")


def _wait_for_editor(project, timeout_seconds=180):
    cli = _resolve_cli()
    deadline = time.monotonic() + timeout_seconds
    last = None
    while time.monotonic() < deadline:
        process = subprocess.run(
            [*cli, "--project", str(project), "--json", "--timeout", "5", "status"],
            capture_output=True, encoding="utf-8", timeout=20,
        )
        if process.returncode == 0:
            return
        last = (process.stdout, process.stderr)
        time.sleep(1)
    raise AssertionError(f"Editor did not respond after script import: {last}")


def _resolve_cli():
    name = "unity-legacy-cli"
    executable = shutil.which(name)
    if executable:
        print(f"Using installed command: {executable}")
        return [executable]
    if os.environ.get("CLI_ANYTHING_FORCE_INSTALLED") == "1":
        raise RuntimeError(f"{name} not found on PATH. Install the harness first.")
    return [sys.executable, "-m", "cli_anything.unity_legacy.unity_legacy_cli"]


@pytest.fixture
def editor():
    project = os.environ.get("CLI_ANYTHING_UNITY_PROJECT")
    if not project:
        pytest.fail("Set CLI_ANYTHING_UNITY_PROJECT to a disposable project open in Unity Edit Mode.")
    project = Path(project).resolve()
    cli = _resolve_cli()

    def command(*args, input_text=None, expected_code=0, parse_float=None):
        process = subprocess.run(
            [*cli, "--project", str(project), "--json", "--timeout", "35", *args],
            capture_output=True, input=input_text, encoding="utf-8", timeout=45,
        )
        assert process.returncode == expected_code, (process.stdout, process.stderr)
        return json.loads(process.stdout, parse_float=parse_float)

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
    failure = command("material", "set", material, "--property", "_Metallic", "--value", "1e100",
                      expected_code=1)
    assert "finite" in failure["error"], failure
    failure = command("material", "set", material, "--property", "_Color", "--value", "1e100,0,0,1",
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


def test_creation_and_float_parsers_reject_invalid_values(editor):
    _, command = editor
    name = f"CliAnything-{uuid4().hex}"
    for option, value in (("--position", "NaN,0,0"), ("--rotation", "Infinity,0,0"),
                          ("--scale", "1e100,1,1")):
        failure = command("gameobject", "create", name, "--primitive", "Cube", option, value,
                          expected_code=1)
        assert "finite" in failure["error"] or "float range" in failure["error"], failure
    names = [node["name"] for node in command("scene", "hierarchy", "--limit", "2000")["data"]["nodes"]]
    assert name not in names

    source_name = f"{name}-Source"
    source = command("gameobject", "create", source_name, "--primitive", "Cube")["data"]["objectId"]
    failure = command("gameobject", "duplicate", "--id", str(source), "--offset", "NaN,0,0",
                      expected_code=1)
    assert "finite" in failure["error"], failure
    names = [node["name"] for node in command("scene", "hierarchy", "--limit", "2000")["data"]["nodes"]]
    assert [node for node in names if node.startswith(source_name)] == [source_name]

    camera = command("gameobject", "create", f"{name}-Camera")["data"]["objectId"]
    command("component", "add", "--id", str(camera), "--component", "Camera")
    before = command("camera", "inspect", "--id", str(camera))["data"]
    for option, value, reason in (("--fov", "NaN", "finite"), ("--depth", "1e100", "float range"),
                                  ("--near", "-Infinity", "finite")):
        failure = command("camera", "set", "--id", str(camera), option, value, expected_code=1)
        assert reason in failure["error"], failure
    after = command("camera", "inspect", "--id", str(camera))["data"]
    assert after["fieldOfView"] == before["fieldOfView"]
    assert after["depth"] == before["depth"]
    assert after["nearClipPlane"] == before["nearClipPlane"]

    canvas = command("ui", "canvas", "create", "--name", f"{name}-Canvas")["data"]["objectId"]
    element_name = f"{name}-Element"
    failure = command("ui", "element", "create", "panel", "--parent-id", str(canvas),
                      "--name", element_name, "--width", "NaN", expected_code=1)
    assert "finite" in failure["error"], failure
    failure = command("ui", "element", "create", "panel", "--parent-id", str(canvas),
                      "--name", element_name, "--anchor-min", "1e100", "0", expected_code=1)
    assert "float range" in failure["error"], failure
    listed = command("ui", "list", "--filter", element_name)["data"]
    assert listed["totalElements"] == 0, listed


def test_component_set_preserves_typed_precision(editor):
    project, command = editor
    probe_script = project / "Assets/CliAnythingNumericProbe.cs"
    if not probe_script.is_file():
        probe_script.write_text(PROBE_SOURCE, encoding="utf-8")
        command("asset", "import", "Assets/CliAnythingNumericProbe.cs")
        _wait_for_editor(project)

    target = command("gameobject", "create", f"CliAnything-{uuid4().hex}")["data"]["objectId"]
    command("component", "add", "--id", str(target), "--component", "CliAnythingNumericProbe")

    def set_value(property_name, value, expected_code=0):
        return command("component", "set", "--id", str(target), "--component",
                       "CliAnythingNumericProbe", "--property", property_name,
                       "--value", value, expected_code=expected_code, parse_float=Decimal)

    literal = "1234567890.123456789012345678"
    applied = set_value("Amount", literal)
    assert applied["ok"], applied

    # The CLI's reply parsing uses binary floats, so read the bridge's own JSON
    # to verify the stored decimal; the request mirrors the CLI's Value + ValueText.
    stored = _bridge_request(project, "component.set", {
        "ObjectId": target,
        "ComponentType": "CliAnythingNumericProbe",
        "Property": "Amount",
        "Value": float(literal),
        "ValueText": literal,
    })
    assert stored["ok"], stored
    assert stored["data"]["after"] == Decimal(literal), stored

    big = set_value("Big", "9007199254740993")["data"]
    assert big["after"] == 9007199254740993, big

    failure = set_value("Speed", "1e100", expected_code=1)
    assert "Unity float" in failure["error"], failure
    assert set_value("Speed", "0.25")["data"]["after"] == Decimal("0.25")

    failure = set_value("Offset", "[1e100,0]", expected_code=1)
    assert "Unity float" in failure["error"], failure
    offset = set_value("Offset", "[1.5,2.5]")["data"]
    assert offset["before"] == [0, 0], offset
    assert offset["after"] == [Decimal("1.5"), Decimal("2.5")], offset
