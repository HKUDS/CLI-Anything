"""Shared helpers for extra render tests (Workbench, look-at)."""
import pytest

from cli_anything.blender.core.scene import create_scene
from cli_anything.blender.core.objects import add_object
from cli_anything.blender.core.materials import create_material, assign_material
from cli_anything.blender.core.lighting import add_camera
from cli_anything.blender.core.render import render_scene, find_blender_binary

try:
    find_blender_binary()
    HAVE_BLENDER = True
except FileNotFoundError:
    HAVE_BLENDER = False

needs_blender = pytest.mark.skipif(not HAVE_BLENDER, reason="Blender binary not found")


def build_and_render(tmp_path, mesh="cube", color=(1, 0, 0, 1), cam=(0, -9, 3),
                     res=(320, 200), name="r.png"):
    p = create_scene(name="x", resolution_x=res[0], resolution_y=res[1],
                     engine="WORKBENCH", samples=4)
    add_object(p, mesh_type=mesh, name="S", location=[0, 0, 0])
    create_material(p, name="m", color=list(color))
    assign_material(p, 0, 0)
    add_camera(p, location=list(cam), look_at=[0, 0, 0], set_active=True)
    out = str(tmp_path / name)
    assert render_scene(p, out, overwrite=True)["returncode"] == 0
    return p, out


def dominant(idx, px):
    others = [v for i, v in enumerate(px) if i != idx]
    return px[idx] > 60 and all(px[idx] > o + 40 for o in others)
