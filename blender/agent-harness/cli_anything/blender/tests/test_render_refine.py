"""Tests for camera look-at and Workbench material colours."""

import pytest

from cli_anything.blender.core.scene import create_scene
from cli_anything.blender.core.objects import add_object
from cli_anything.blender.core.materials import create_material, assign_material
from cli_anything.blender.core.lighting import add_camera, set_camera
from cli_anything.blender.core.render import render_scene, find_blender_binary
from cli_anything.blender.utils.bpy_gen import generate_full_script

try:
    find_blender_binary()
    HAVE_BLENDER = True
except FileNotFoundError:
    HAVE_BLENDER = False

needs_blender = pytest.mark.skipif(not HAVE_BLENDER, reason="Blender binary not found")


def _scene(engine="WORKBENCH"):
    return create_scene(name="t", resolution_x=320, resolution_y=200, engine=engine, samples=4)


def test_look_at_stored_and_validated():
    p = _scene()
    cam = add_camera(p, location=[5, -5, 5], look_at=[1, 2, 3])
    assert cam["look_at"] == [1.0, 2.0, 3.0]
    with pytest.raises(ValueError):
        add_camera(p, look_at=[1, 2])
    set_camera(p, 0, "look_at", "4,5,6")
    assert p["cameras"][0]["look_at"] == [4.0, 5.0, 6.0]
    set_camera(p, 0, "look_at", "off")
    assert p["cameras"][0]["look_at"] is None


def test_script_has_track_quat_only_with_look_at():
    p = _scene()
    add_camera(p, location=[5, -5, 5], look_at=[0, 0, 0], set_active=True)
    assert "to_track_quat('-Z', 'Y')" in generate_full_script(p, '/tmp/x.png')
    q = _scene()
    add_camera(q, location=[5, -5, 5], set_active=True)
    assert "to_track_quat" not in generate_full_script(q, '/tmp/x.png')


def test_workbench_script_uses_material_colours():
    p = _scene("WORKBENCH")
    create_material(p, name="Red", color=[1, 0, 0, 1])
    s = generate_full_script(p, '/tmp/x.png')
    assert "color_type = 'MATERIAL'" in s
    assert "mat_Red.diffuse_color = (1, 0, 0, 1)" in s
    c = _scene("CYCLES")
    assert "color_type" not in generate_full_script(c, '/tmp/x.png')


@needs_blender
def test_e2e_red_cube_look_at_centred(tmp_path):
    from PIL import Image
    p = _scene("WORKBENCH")
    add_object(p, mesh_type="cube", name="C", location=[10, 10, 0])
    create_material(p, name="Red", color=[1, 0, 0, 1])
    assign_material(p, 0, 0)
    add_camera(p, location=[16, 4, 6], look_at=[10, 10, 0], set_active=True)
    out = str(tmp_path / "r.png")
    assert render_scene(p, out, overwrite=True)["returncode"] == 0
    im = Image.open(out).convert("RGB")
    r, g, b = im.getpixel((160, 100))
    assert r > 60 and r > g + 40 and r > b + 40, (r, g, b)
    # subject centred: red pixels' centroid near the middle
    px = im.load(); xs = []
    for x in range(320):
        for y in range(200):
            rr, gg, bb = px[x, y]
            if rr > 60 and rr > gg + 40 and rr > bb + 40: xs.append(x)
    assert xs and abs(sum(xs) / len(xs) - 160) < 25
