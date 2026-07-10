"""Export/build orchestration for EEZ Studio projects."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..utils import eez_studio_backend
from . import project as project_mod


def inspect_with_backend(project_path: str, source: str | None = None) -> dict[str, Any]:
    return eez_studio_backend.inspect_project(project_path, source=source)


def build_files(project_path: str, timeout: int = 300) -> dict[str, Any]:
    """Run a real configured EEZ Studio build-files command."""
    return eez_studio_backend.run_custom_build_command(project_path, timeout=timeout)


def simulator_build(
    project_path: str,
    output_dir: str,
    source: str | None = None,
    repository_name: str = "eez-framework",
    docker_volume_name: str = "eez-studio-cli-anything",
    timeout: int = 900,
) -> dict[str, Any]:
    return eez_studio_backend.build_full_simulator(
        project_path=project_path,
        output_dir=output_dir,
        source=source,
        repository_name=repository_name,
        docker_volume_name=docker_volume_name,
        timeout=timeout,
    )


def verify_simulator_output(output_dir: str) -> dict[str, Any]:
    output = Path(output_dir)
    required = ["index.html", "index.js", "index.wasm"]
    files: dict[str, dict[str, Any]] = {}
    for file_name in required:
        path = output / file_name
        if not path.is_file():
            raise RuntimeError(f"missing simulator artifact: {path}")
        files[file_name] = {"path": str(path), "bytes": path.stat().st_size}
        if path.stat().st_size <= 0:
            raise RuntimeError(f"empty simulator artifact: {path}")
    with open(output / "index.html", "rb") as handle:
        prefix = handle.read(32)
    if b"<!DOCTYPE html" not in prefix[:32] and b"<html" not in prefix.lower():
        raise RuntimeError("index.html does not look like HTML")
    with open(output / "index.wasm", "rb") as handle:
        magic = handle.read(4)
    if magic != b"\x00asm":
        raise RuntimeError("index.wasm does not have WebAssembly magic bytes")
    return {"output_dir": os.path.abspath(output_dir), "files": files}


def ensure_destination(project_path: str) -> dict[str, Any]:
    project = project_mod.load_project(project_path)
    return project_mod.ensure_destination_dir(project_path, project)
