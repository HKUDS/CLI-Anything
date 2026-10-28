"""E2E tests that run a real Blender binary (skipped when none is found)."""

import os

import pytest

from cli_anything.blender.core.scene import create_scene
from cli_anything.blender.core.objects import add_object
from cli_anything.blender.core.materials import create_material, assign_material
from cli_anything.blender.core.lighting import add_camera, add_light
from cli_anything.blender.core.render import render_scene, find_blender_binary

try:
    find_blender_binary()
    HAVE_BLENDER = True
except FileNotFoundError:
    HAVE_BLENDER = False

pytestmark = pytest.mark.skipif(not HAVE_BLENDER, reason="Blender binary not found")


def _scene(engine="WORKBENCH"):
    return create_scene(name="e2e", resolution_x=320, resolution_y=200,
                        engine=engine, samples=4)


def test_render_executes_cube(tmp_path):
    proj = _scene()
    add_object(proj, mesh_type="cube", name="Cube")
    add_camera(proj, location=[6, -6, 4], rotation=[63, 0, 45], set_active=True)
    out = str(tmp_path / "cube.png")
    result = render_scene(proj, out, overwrite=True)
    assert result["returncode"] == 0
    assert os.path.getsize(out) > 0
    from PIL import Image
    assert Image.open(out).size == (320, 200)
