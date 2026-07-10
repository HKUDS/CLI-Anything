"""Backend wrapper for the real EEZ Studio source/Electron internals.

The harness edits native ``.eez-project`` JSON directly. Build/export commands
must call a real EEZ Studio checkout or executable. This module looks for a
built source tree via ``EEZ_STUDIO_SOURCE`` and invokes upstream Node modules.
If the backend is not installed, commands fail with concrete setup steps.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


INSTALL_MESSAGE = """EEZ Studio backend is not available.

Install/build the real target software and point this harness at it:
  git clone https://github.com/eez-open/studio.git
  cd studio
  npm install
  npm run build
  export EEZ_STUDIO_SOURCE=/absolute/path/to/studio

For full LVGL simulator builds, Docker must also be installed and running.
"""


def find_node() -> str:
    node = os.environ.get("EEZ_STUDIO_NODE") or shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required for EEZ Studio backend scripts.\n" + INSTALL_MESSAGE)
    return node


def find_source_tree(source: str | None = None) -> Path:
    candidates = []
    if source:
        candidates.append(Path(source))
    if os.environ.get("EEZ_STUDIO_SOURCE"):
        candidates.append(Path(os.environ["EEZ_STUDIO_SOURCE"]))
    for candidate in candidates:
        package_json = candidate / "package.json"
        if package_json.is_file():
            try:
                package = json.loads(package_json.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                package = {}
            if package.get("name") == "eezstudio":
                return candidate.resolve()
    raise RuntimeError(INSTALL_MESSAGE)


def backend_status(source: str | None = None) -> dict[str, Any]:
    try:
        source_tree = find_source_tree(source)
        package = json.loads((source_tree / "package.json").read_text(encoding="utf-8"))
        build_dir = source_tree / "build"
        docker_lib = build_dir / "project-editor" / "lvgl" / "docker-build" / "docker-build-lib.js"
        return {
            "available": True,
            "source": str(source_tree),
            "version": package.get("version"),
            "node": find_node(),
            "build_dir": str(build_dir),
            "docker_build_lib": str(docker_lib),
            "docker_build_lib_exists": docker_lib.is_file(),
        }
    except RuntimeError as exc:
        return {"available": False, "error": str(exc).strip()}


def _write_runner(script: str) -> str:
    handle = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
    try:
        handle.write(script)
        return handle.name
    finally:
        handle.close()


def _run_node(script: str, args: list[str], source: Path, timeout: int) -> dict[str, Any]:
    node = find_node()
    runner = _write_runner(script)
    env = os.environ.copy()
    node_path_parts = [
        str(source / "build"),
        str(source / "node_modules"),
        env.get("NODE_PATH", ""),
    ]
    env["NODE_PATH"] = os.pathsep.join(part for part in node_path_parts if part)
    try:
        result = subprocess.run(
            [node, runner] + args,
            cwd=str(source),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    finally:
        try:
            os.unlink(runner)
        except OSError:
            pass
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    if result.returncode != 0:
        raise RuntimeError(
            "EEZ Studio backend command failed "
            f"(exit {result.returncode}).\nstdout:\n{stdout[-2000:]}\nstderr:\n{stderr[-2000:]}"
        )
    try:
        return json.loads(stdout.splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise RuntimeError(f"EEZ Studio backend returned non-JSON output:\n{stdout[-2000:]}") from exc


def inspect_project(project_path: str, source: str | None = None, timeout: int = 60) -> dict[str, Any]:
    """Use EEZ Studio's docker build library to parse project build metadata."""
    source_tree = find_source_tree(source)
    docker_lib = source_tree / "build" / "project-editor" / "lvgl" / "docker-build" / "docker-build-lib.js"
    if not docker_lib.is_file():
        raise RuntimeError(
            "EEZ Studio is present but not built: "
            f"{docker_lib} does not exist.\nRun `npm run build` in EEZ_STUDIO_SOURCE."
        )
    script = r"""
const path = require("path");
const lib = require(path.join(process.cwd(), "build/project-editor/lvgl/docker-build/docker-build-lib.js"));
const projectPath = process.argv[2];
const logs = [];
function log(message, type) { logs.push({ message, type: type || "info" }); }
(async () => {
  const info = await lib.readProjectFile(projectPath, log);
  console.log(JSON.stringify({ ok: true, projectInfo: info, logs }));
})().catch(err => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
});
"""
    return _run_node(script, [os.path.abspath(project_path)], source_tree, timeout)


def build_full_simulator(
    project_path: str,
    output_dir: str,
    repository_name: str = "eez-framework",
    docker_volume_name: str = "eez-studio-cli-anything",
    docker_build_path: str | None = None,
    source: str | None = None,
    timeout: int = 900,
) -> dict[str, Any]:
    """Build the EEZ LVGL full simulator through upstream docker-build-lib."""
    source_tree = find_source_tree(source)
    docker_lib = source_tree / "build" / "project-editor" / "lvgl" / "docker-build" / "docker-build-lib.js"
    if not docker_lib.is_file():
        raise RuntimeError(
            "EEZ Studio is present but not built: "
            f"{docker_lib} does not exist.\nRun `npm run build` in EEZ_STUDIO_SOURCE."
        )
    docker_build = docker_build_path or str(source_tree / "packages" / "project-editor" / "lvgl" / "docker-build")
    script = r"""
const path = require("path");
const fs = require("fs");
const lib = require(path.join(process.cwd(), "build/project-editor/lvgl/docker-build/docker-build-lib.js"));
const [projectPath, outputDir, repositoryName, dockerVolumeName, dockerBuildPath] = process.argv.slice(2);
const logs = [];
function log(message, type) { logs.push({ message, type: type || "info" }); }
(async () => {
  const config = { repositoryName, dockerVolumeName, dockerBuildPath };
  lib.resetAbort();
  const info = await lib.readProjectFile(projectPath, log);
  const dockerOk = await lib.checkDocker(log);
  if (!dockerOk) throw new Error("Docker is required and not ready");
  const setup = await lib.setupProject(info, config, log);
  await lib.buildProject(info, config, log, setup.skipEmcmakeCmake);
  await lib.extractBuild(outputDir, config, log);
  const required = ["index.html", "index.js", "index.wasm"];
  for (const file of required) {
    const full = path.join(outputDir, file);
    if (!fs.existsSync(full) || fs.statSync(full).size <= 0) {
      throw new Error(`missing simulator artifact: ${file}`);
    }
  }
  console.log(JSON.stringify({ ok: true, outputDir, projectInfo: info, logs }));
})().catch(err => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
});
"""
    return _run_node(
        script,
        [
            os.path.abspath(project_path),
            os.path.abspath(output_dir),
            repository_name,
            docker_volume_name,
            docker_build,
        ],
        source_tree,
        timeout,
    )


def run_custom_build_command(project_path: str, timeout: int = 300) -> dict[str, Any]:
    """Run an explicitly provided EEZ build command.

    This supports future or locally patched EEZ Studio builds that expose a
    documented headless command. The command receives the project path appended
    as its final argument.
    """
    command = os.environ.get("EEZ_STUDIO_BUILD_COMMAND")
    if not command:
        raise RuntimeError(
            "No native EEZ build command configured. Set EEZ_STUDIO_BUILD_COMMAND "
            "or use `lvgl simulator-build` with EEZ_STUDIO_SOURCE.\n" + INSTALL_MESSAGE
        )
    args = shlex.split(command) + [os.path.abspath(project_path)]
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(
            f"EEZ_STUDIO_BUILD_COMMAND failed (exit {result.returncode}).\n"
            f"stdout:\n{result.stdout[-2000:]}\nstderr:\n{result.stderr[-2000:]}"
        )
    return {
        "ok": True,
        "method": "EEZ_STUDIO_BUILD_COMMAND",
        "command": args,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
