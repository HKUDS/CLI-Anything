"""Eval task: render one frame with the real Blender binary (skipped if absent)."""

import shlex
import subprocess

from cli_anything.blender.core.scene import create_scene
from cli_anything.blender.core.objects import add_object
from cli_anything.blender.core.render import render_scene

TASK = {
    "id": "render_execute",
    "name": "Blender single-frame render",
    "description": "Render one PNG frame using the real Blender binary",
    "prompt": "Render a single PNG frame of a scene containing a cube.",
    "requires": ["blender"],
}


def run(ctx):
    scene = create_scene(name="eval", resolution_x=320, resolution_y=240, samples=8)
    add_object(scene, mesh_type="cube", location=[0, 0, 0])
    out = ctx.task_artifact_path("render.png")
    result = render_scene(scene, str(out))
    subprocess.run(shlex.split(result["command"]), check=True, timeout=600,
                   capture_output=True)
    return {"metrics": {"engine": result.get("engine")}, "artifacts": [str(out)]}


def verify(ctx):
    d = ctx.task_artifacts_dir()
    pngs = [p for p in d.glob("render*.png") if p.stat().st_size > 0]
    return {"ok": bool(pngs), "metrics": {"outputs": [p.name for p in pngs]}}
