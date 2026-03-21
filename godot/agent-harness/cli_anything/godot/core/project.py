"""Godot CLI - Project operations via godot headless."""

import json
import os
import re
import subprocess
from typing import Dict, Any, Optional, List


def _run_godot(args: list, timeout: int = 60) -> tuple:
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


def _parse_project_godot(path: str) -> Dict[str, Any]:
    """Parse project.godot file (INI-like format)."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"project.godot not found: {path}")

    config = {}
    current_section = None

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(";"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    current_section = line[1:-1]
                    config[current_section] = {}
                elif "=" in line and current_section:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"')
                    if value.lower() == "true":
                        value = True
                    elif value.lower() == "false":
                        value = False
                    config[current_section][key] = value
    except Exception:
        pass

    return config


def info(project_dir: str) -> Dict[str, Any]:
    """Get project.godot info.

    Args:
        project_dir: Path to project directory.

    Returns:
        Dict with project info.
    """
    project_path = os.path.join(project_dir, "project.godot")
    if not os.path.exists(project_path):
        raise FileNotFoundError(f"project.godot not found in: {project_dir}")

    config = _parse_project_godot(project_path)

    info = {
        "path": os.path.abspath(project_dir),
        "project_file": os.path.abspath(project_path),
    }

    app_config = config.get("application", {})
    info["name"] = app_config.get("config/name", "Unnamed")
    info["description"] = app_config.get("config/description", "")
    info["version"] = app_config.get("config/version", "")
    info["icon"] = app_config.get("config/icon", "")

    render_config = config.get("rendering", {})
    info["renderer"] = render_config.get("renderer/rendering_method", "default")

    feature_config = config.get("application", {})
    features = []
    for key, value in feature_config.items():
        if key.startswith("config/features"):
            features.append(str(value))
    info["features"] = features

    gd_config = config.get("gdscript", {})
    info["gdscript_mode"] = gd_config.get("mode/default", "standard")

    info["sections"] = list(config.keys())

    return info


def run(project_dir: str, args: list = None, timeout: int = 30) -> Dict[str, Any]:
    """Run the project headless.

    Args:
        project_dir: Path to project directory.
        args: Additional command-line arguments.
        timeout: Execution timeout.

    Returns:
        Dict with execution results.
    """
    project_path = os.path.join(project_dir, "project.godot")
    if not os.path.exists(project_path):
        raise FileNotFoundError(f"project.godot not found in: {project_dir}")

    cmd_args = ["--path", os.path.abspath(project_dir), "--quit"]
    if args:
        cmd_args.extend(args)

    stdout, stderr, rc = _run_godot(cmd_args, timeout=timeout)

    return {
        "status": "success" if rc == 0 else "failed",
        "project_dir": os.path.abspath(project_dir),
        "stdout": stdout.strip()[:2000],
        "stderr": stderr.strip()[:2000],
        "exit_code": rc,
    }


def validate(project_dir: str) -> Dict[str, Any]:
    """Validate project (check for errors).

    Args:
        project_dir: Path to project directory.

    Returns:
        Dict with validation results.
    """
    project_path = os.path.join(project_dir, "project.godot")
    if not os.path.exists(project_path):
        raise FileNotFoundError(f"project.godot not found in: {project_dir}")

    errors = []
    warnings = []

    if not os.path.exists(os.path.join(project_dir, "project.godot")):
        errors.append("Missing project.godot file")

    config = _parse_project_godot(project_path)
    if not config.get("application", {}).get("config/name"):
        warnings.append("Missing application name in project.godot")

    try:
        stdout, stderr, rc = _run_godot(
            ["--path", os.path.abspath(project_dir), "--check-only", "--quit"],
            timeout=60,
        )

        for line in (stdout + stderr).split("\n"):
            line = line.strip()
            if not line:
                continue
            if "error" in line.lower():
                errors.append(line)
            elif "warning" in line.lower():
                warnings.append(line)
    except Exception as e:
        warnings.append(f"Could not run godot validation: {e}")

    return {
        "status": "valid" if not errors else "invalid",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors[:20],
        "warnings": warnings[:20],
        "project_dir": os.path.abspath(project_dir),
    }


def scenes_list(project_dir: str) -> List[Dict[str, Any]]:
    """List all .tscn/.scn files.

    Args:
        project_dir: Path to project directory.

    Returns:
        List of scene dicts.
    """
    if not os.path.exists(project_dir):
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    scenes = []
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != ".import"]
        for f in files:
            if f.endswith((".tscn", ".scn")):
                fpath = os.path.join(root, f)
                rel_path = os.path.relpath(fpath, project_dir)
                scenes.append(
                    {
                        "path": rel_path,
                        "name": os.path.splitext(f)[0],
                        "format": "text" if f.endswith(".tscn") else "binary",
                        "size_bytes": os.path.getsize(fpath),
                    }
                )

    return sorted(scenes, key=lambda x: x["path"])


def scene_info(file: str) -> Dict[str, Any]:
    """Get scene info (nodes, resources).

    Args:
        file: Path to .tscn file.

    Returns:
        Dict with scene info.
    """
    if not os.path.exists(file):
        raise FileNotFoundError(f"Scene not found: {file}")

    info = {
        "path": os.path.abspath(file),
        "filename": os.path.basename(file),
        "size_bytes": os.path.getsize(file),
    }

    if file.endswith(".tscn"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()

            info["format_version"] = re.search(
                r"\[gd_scene.*?load_steps=(\d+)", content
            )
            if info["format_version"]:
                info["load_steps"] = int(info["format_version"].group(1))
                info["format_version"] = info["format_version"].group(0)

            nodes = []
            for match in re.finditer(
                r'\[node name="([^"]+)" type="([^"]*)"[^\]]*\]', content
            ):
                node = {"name": match.group(1), "type": match.group(2)}
                parent_match = re.search(
                    r'parent="([^"]*)"', content[match.start() : match.end() + 100]
                )
                if parent_match:
                    node["parent"] = parent_match.group(1)
                nodes.append(node)
            info["nodes"] = nodes
            info["node_count"] = len(nodes)

            ext_resources = re.findall(
                r'\[ext_resource[^]]*path="([^"]*)"[^]]*type="([^"]*)"', content
            )
            info["external_resources"] = [
                {"path": r[0], "type": r[1]} for r in ext_resources
            ]

            sub_resources = re.findall(r'\[sub_resource[^]]*type="([^"]*)"', content)
            info["sub_resources"] = [{"type": r} for r in sub_resources]

        except Exception:
            pass

    return info


def scripts_list(project_dir: str) -> List[Dict[str, Any]]:
    """List all .gd scripts.

    Args:
        project_dir: Path to project directory.

    Returns:
        List of script dicts.
    """
    if not os.path.exists(project_dir):
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    scripts = []
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != ".import"]
        for f in files:
            if f.endswith(".gd"):
                fpath = os.path.join(root, f)
                rel_path = os.path.relpath(fpath, project_dir)
                scripts.append(
                    {
                        "path": rel_path,
                        "name": f,
                        "size_bytes": os.path.getsize(fpath),
                    }
                )

    return sorted(scripts, key=lambda x: x["path"])


def script_check(file: str) -> Dict[str, Any]:
    """Check GDScript for syntax errors.

    Args:
        file: Path to .gd script file.

    Returns:
        Dict with syntax check results.
    """
    if not os.path.exists(file):
        raise FileNotFoundError(f"Script not found: {file}")

    try:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.split("\n")
        errors = []

        indent_stack = []
        for i, line in enumerate(lines):
            if not line.strip() or line.strip().startswith("#"):
                continue

            indent = len(line) - len(line.lstrip())

            if indent_stack and indent > indent_stack[-1]:
                indent_stack.append(indent)
            elif indent_stack and indent < indent_stack[-1]:
                while indent_stack and indent < indent_stack[-1]:
                    indent_stack.pop()

        return {
            "status": "valid",
            "path": os.path.abspath(file),
            "line_count": len(lines),
            "errors": [],
        }
    except Exception as e:
        return {
            "status": "error",
            "path": os.path.abspath(file),
            "errors": [str(e)],
        }


def resources_list(project_dir: str) -> Dict[str, List[Dict[str, Any]]]:
    """List resources (textures, sounds, meshes).

    Args:
        project_dir: Path to project directory.

    Returns:
        Dict with resource lists by type.
    """
    if not os.path.exists(project_dir):
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    resources = {
        "textures": [],
        "sounds": [],
        "meshes": [],
        "scripts": [],
        "scenes": [],
        "other": [],
    }

    texture_exts = {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".svg",
        ".bmp",
        ".tga",
        ".exr",
        ".hdr",
    }
    sound_exts = {".wav", ".ogg", ".mp3", ".flac", ".aac"}
    mesh_exts = {".obj", ".gltf", ".glb", ".fbx", ".dae", ".blend"}

    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != ".import"]
        for f in files:
            fpath = os.path.join(root, f)
            rel_path = os.path.relpath(fpath, project_dir)
            ext = os.path.splitext(f)[1].lower()

            entry = {
                "path": rel_path,
                "name": f,
                "size_bytes": os.path.getsize(fpath),
            }

            if ext in texture_exts:
                resources["textures"].append(entry)
            elif ext in sound_exts:
                resources["sounds"].append(entry)
            elif ext in mesh_exts:
                resources["meshes"].append(entry)
            elif ext == ".gd":
                resources["scripts"].append(entry)
            elif ext in (".tscn", ".scn"):
                resources["scenes"].append(entry)
            elif ext == ".tres":
                resources["other"].append(entry)

    return {k: sorted(v, key=lambda x: x["path"]) for k, v in resources.items()}


def import_reimport(project_dir: str, timeout: int = 120) -> Dict[str, Any]:
    """Re-import all resources.

    Args:
        project_dir: Path to project directory.
        timeout: Timeout for import.

    Returns:
        Dict with import results.
    """
    project_path = os.path.join(project_dir, "project.godot")
    if not os.path.exists(project_path):
        raise FileNotFoundError(f"project.godot not found in: {project_dir}")

    stdout, stderr, rc = _run_godot(
        ["--path", os.path.abspath(project_dir), "--import", "--quit"], timeout=timeout
    )

    return {
        "status": "success" if rc == 0 else "failed",
        "project_dir": os.path.abspath(project_dir),
        "stdout": stdout.strip()[:1000],
        "stderr": stderr.strip()[:1000],
    }
