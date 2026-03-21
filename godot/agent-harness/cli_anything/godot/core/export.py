"""Godot CLI - Export operations via godot headless."""

import json
import os
import re
import subprocess
from typing import Dict, Any, Optional, List


def _run_godot(args: list, timeout: int = 300) -> tuple:
    """Run godot with --headless flag and return (stdout, stderr, returncode)."""
    cmd = ["godot", "--headless"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout, result.stderr, result.returncode
    except FileNotFoundError:
        try:
            cmd = ["godot4", "--headless"] + args
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            return result.stdout, result.stderr, result.returncode
        except FileNotFoundError:
            raise RuntimeError(
                "godot/godot4 not found. Install with: apt install godot"
            )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"godot timed out after {timeout}s")


def presets_list(project_dir: str) -> List[Dict[str, Any]]:
    """List export presets.

    Args:
        project_dir: Path to project directory.

    Returns:
        List of export preset dicts.
    """
    presets_file = os.path.join(project_dir, "export_presets.cfg")
    if not os.path.exists(presets_file):
        return []

    presets = []
    current_preset = None

    try:
        with open(presets_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(";"):
                    continue

                preset_match = re.match(r"\[preset\.(\d+)\]", line)
                if preset_match:
                    if current_preset:
                        presets.append(current_preset)
                    current_preset = {
                        "index": int(preset_match.group(1)),
                        "name": "",
                        "platform": "",
                        "export_path": "",
                        "export_filter": "",
                    }
                elif current_preset and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip().split(".")[-1]
                    value = value.strip().strip('"')
                    if key == "name":
                        current_preset["name"] = value
                    elif key == "platform":
                        current_preset["platform"] = value
                    elif key == "export_path":
                        current_preset["export_path"] = value
                    elif key == "export_filter":
                        current_preset["export_filter"] = value

            if current_preset:
                presets.append(current_preset)

    except Exception:
        pass

    return presets


def run_preset(
    project_dir: str, preset: str, output: str = None, timeout: int = 300
) -> Dict[str, Any]:
    """Run an export preset.

    Args:
        project_dir: Path to project directory.
        preset: Preset name or index.
        output: Output file/directory path.
        timeout: Export timeout.

    Returns:
        Dict with export results.
    """
    project_path = os.path.join(project_dir, "project.godot")
    if not os.path.exists(project_path):
        raise FileNotFoundError(f"project.godot not found in: {project_dir}")

    args = ["--path", os.path.abspath(project_dir)]

    if preset.isdigit():
        args.extend(["--export-release", preset])
    else:
        args.extend(["--export-release", preset])

    if output:
        args.append(os.path.abspath(output))

    stdout, stderr, rc = _run_godot(args, timeout=timeout)

    result = {
        "status": "success" if rc == 0 else "failed",
        "project_dir": os.path.abspath(project_dir),
        "preset": preset,
        "stdout": stdout.strip()[:2000],
        "stderr": stderr.strip()[:2000],
    }

    if output and os.path.exists(output):
        result["output"] = os.path.abspath(output)
        result["output_size_bytes"] = os.path.getsize(output)

    return result


def export_all(project_dir: str, output_dir: str, timeout: int = 600) -> Dict[str, Any]:
    """Export all presets.

    Args:
        project_dir: Path to project directory.
        output_dir: Output directory for all exports.
        timeout: Export timeout.

    Returns:
        Dict with export results.
    """
    project_path = os.path.join(project_dir, "project.godot")
    if not os.path.exists(project_path):
        raise FileNotFoundError(f"project.godot not found in: {project_dir}")

    os.makedirs(output_dir, exist_ok=True)

    presets = presets_list(project_dir)
    if not presets:
        return {
            "status": "no_presets",
            "project_dir": os.path.abspath(project_dir),
            "message": "No export presets found",
        }

    results = []
    success_count = 0
    fail_count = 0

    for preset in presets:
        preset_name = preset["name"]
        if not preset_name:
            continue

        output_file = os.path.join(output_dir, preset_name.replace(" ", "_"))

        result = run_preset(
            project_dir, preset_name, output_file, timeout=timeout // len(presets)
        )
        results.append(result)

        if result["status"] == "success":
            success_count += 1
        else:
            fail_count += 1

    return {
        "status": "completed",
        "project_dir": os.path.abspath(project_dir),
        "output_dir": os.path.abspath(output_dir),
        "total_presets": len(presets),
        "success_count": success_count,
        "fail_count": fail_count,
        "results": results,
    }


def build(
    project_dir: str, export_preset: str, output: str, timeout: int = 300
) -> Dict[str, Any]:
    """Build/export the project.

    Args:
        project_dir: Path to project directory.
        export_preset: Export preset name.
        output: Output file path.
        timeout: Build timeout.

    Returns:
        Dict with build results.
    """
    project_path = os.path.join(project_dir, "project.godot")
    if not os.path.exists(project_path):
        raise FileNotFoundError(f"project.godot not found in: {project_dir}")

    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)

    args = [
        "--path",
        os.path.abspath(project_dir),
        "--export-release",
        export_preset,
        os.path.abspath(output),
    ]

    stdout, stderr, rc = _run_godot(args, timeout=timeout)

    result = {
        "status": "success" if rc == 0 else "failed",
        "project_dir": os.path.abspath(project_dir),
        "preset": export_preset,
        "output": os.path.abspath(output),
    }

    if rc != 0:
        result["error"] = stderr.strip()[:500]
    elif os.path.exists(output):
        result["output_size_bytes"] = os.path.getsize(output)

    return result


def debug_run(project_dir: str, port: int = 6007, timeout: int = 30) -> Dict[str, Any]:
    """Run with remote debug.

    Args:
        project_dir: Path to project directory.
        port: Debug port.
        timeout: Run timeout.

    Returns:
        Dict with debug run results.
    """
    project_path = os.path.join(project_dir, "project.godot")
    if not os.path.exists(project_path):
        raise FileNotFoundError(f"project.godot not found in: {project_dir}")

    args = [
        "--path",
        os.path.abspath(project_dir),
        "--remote-debug",
        f"tcp://0.0.0.0:{port}",
        "--quit",
    ]

    stdout, stderr, rc = _run_godot(args, timeout=timeout)

    return {
        "status": "success" if rc == 0 else "failed",
        "project_dir": os.path.abspath(project_dir),
        "debug_port": port,
        "stdout": stdout.strip()[:2000],
        "stderr": stderr.strip()[:2000],
    }
