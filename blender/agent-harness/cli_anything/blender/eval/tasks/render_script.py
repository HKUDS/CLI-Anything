"""Eval task: generate a valid Blender render script (no binary required)."""

import os

from cli_anything.blender.core.scene import create_scene
from cli_anything.blender.core.objects import add_object
from cli_anything.blender.core.render import render_scene

TASK = {
    "id": "render_script",
    "name": "Render script generation",
    "description": "Create a scene with a cube and generate a bpy render script",
    "prompt": "Create a scene with a cube and prepare a single-frame PNG render.",
}


def run(ctx):
    scene = create_scene(name="eval", resolution_x=640, resolution_y=480)
    add_object(scene, mesh_type="cube", location=[0, 0, 0])
    out = ctx.task_artifact_path("render.png")
    result = render_scene(scene, str(out))
    ctx.task_artifact_path("script_path.txt").write_text(
        result.get("script_path", ""), encoding="utf-8")
    return {"metrics": {"engine": result.get("engine")},
            "artifacts": [result.get("script_path", "")]}


def verify(ctx):
    marker = ctx.task_artifact_path("script_path.txt")
    if not marker.exists():
        return {"ok": False, "metrics": {}}
    script_path = marker.read_text(encoding="utf-8").strip()
    ok = bool(script_path) and os.path.exists(script_path)
    return {"ok": ok, "metrics": {"script_path": script_path}}
