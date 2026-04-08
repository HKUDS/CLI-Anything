"""Godot project export — build game binaries for target platforms.

Note: --export-all is available in Godot 4.3+. Earlier 4.x versions
use --export-release/--export-debug per preset. If export-all fails,
fall back to exporting each preset individually.
"""

from pathlib import Path

from cli_anything.godot.utils.godot_backend import run_godot, validate_project


def export_project(
    project_path: str,
    preset: str | None = None,
    output_path: str | None = None,
    debug: bool = False,
) -> dict:
    """Export a Godot project using a configured export preset.

    Args:
        project_path: Godot project directory.
        preset: Export preset name (from export_presets.cfg).
                If None, exports all presets.
        output_path: Output file path for the exported binary.
        debug: If True, use --export-debug instead of --export-release.

    Returns:
        Dict with status and output details.
    """
    if not validate_project(project_path):
        return {"status": "error", "message": f"Not a Godot project: {project_path}"}

    presets_file = Path(project_path) / "export_presets.cfg"
    if not presets_file.exists():
        return {
            "status": "error",
            "message": "No export_presets.cfg found. Configure export presets in the Godot editor first.",
        }

    if preset is None:
        args = ["--export-all", "--quit"]
    else:
        flag = "--export-debug" if debug else "--export-release"
        args = [flag, preset]
        if output_path:
            args.append(output_path)
        args.append("--quit")

    result = run_godot(
        args,
        project_path=project_path,
        headless=True,
        timeout=300,
    )

    return {
        "status": "ok" if result["returncode"] == 0 else "error",
        "preset": preset or "all",
        "debug": debug,
        "returncode": result["returncode"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }


def list_export_presets(project_path: str) -> dict:
    """Parse export_presets.cfg and list available presets.

    Returns:
        Dict with list of preset names and platforms.
    """
    presets_file = Path(project_path) / "export_presets.cfg"
    if not presets_file.exists():
        return {"status": "ok", "count": 0, "presets": []}

    text = presets_file.read_text(encoding="utf-8")
    presets = []
    current = {}

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("[preset.") and line.endswith("]") and ".options]" not in line:
            if current:
                presets.append(current)
            current = {}
        elif "=" in line and current is not None:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"')
            if key == "name":
                current["name"] = value
            elif key == "platform":
                current["platform"] = value
            elif key == "export_path":
                current["export_path"] = value

    if current:
        presets.append(current)

    return {"status": "ok", "count": len(presets), "presets": presets}
