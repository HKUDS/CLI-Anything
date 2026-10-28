"""Render matrix: 3 camera positions x 2 colours, Workbench cube with look-at."""

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

CAMERAS = [[7, -7, 5], [0, -9, 3], [-8, 5, 6]]
COLOURS = {"red": (1, 0, 0, 1), "green": (0, 1, 0, 1)}


def _dominant(name, px):
    r, g, b = px
    idx = {"red": 0, "green": 1}[name]
    others = [v for i, v in enumerate(px) if i != idx]
    return px[idx] > 60 and all(px[idx] > o + 40 for o in others)


@needs_blender
@pytest.mark.parametrize("cam_loc", CAMERAS, ids=lambda c: "cam%s" % ",".join(map(str, c)))
@pytest.mark.parametrize("cname", sorted(COLOURS))
def test_colour_dominates_centre(tmp_path, cam_loc, cname):
    from PIL import Image
    p = create_scene(name="m", resolution_x=320, resolution_y=200,
                     engine="WORKBENCH", samples=4)
    add_object(p, mesh_type="cube", name="C", location=[0, 0, 0])
    create_material(p, name=cname, color=list(COLOURS[cname]))
    assign_material(p, 0, 0)
    add_camera(p, location=cam_loc, look_at=[0, 0, 0], set_active=True)
    out = str(tmp_path / "r.png")
    assert render_scene(p, out, overwrite=True)["returncode"] == 0
    im = Image.open(out).convert("RGB")
    assert im.size == (320, 200)
    px = im.getpixel((160, 100))
    assert _dominant(cname, px), (cname, cam_loc, px)
