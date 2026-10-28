"""Sun vs point light: render succeeds and centre pixel is not black."""
import os
import pytest
from PIL import Image

from cli_anything.blender.core.scene import create_scene
from cli_anything.blender.core.objects import add_object
from cli_anything.blender.core.materials import create_material, assign_material
from cli_anything.blender.core.lighting import add_camera, add_light
from cli_anything.blender.core.render import render_scene
from cli_anything.blender.tests.test_render_helpers import needs_blender


@needs_blender
@pytest.mark.parametrize("ltype,loc,rot,power", [
    ("SUN", [0, 0, 5], [30, 0, 20], 3.0),
    ("POINT", [3, -3, 5], None, 1000.0),
])
def test_light_centre_not_black(tmp_path, ltype, loc, rot, power):
    p = create_scene(name="l", resolution_x=320, resolution_y=200,
                     engine="WORKBENCH", samples=4)
    add_object(p, mesh_type="cube", name="C", location=[0, 0, 0])
    create_material(p, name="m", color=[0.8, 0.8, 0.8, 1])
    assign_material(p, 0, 0)
    add_camera(p, location=[0, -9, 3], look_at=[0, 0, 0], set_active=True)
    add_light(p, light_type=ltype, location=loc, rotation=rot, power=power)
    out = str(tmp_path / "r.png")
    assert render_scene(p, out, overwrite=True)["returncode"] == 0
    assert os.path.exists(out)
    px = Image.open(out).convert("RGB").getpixel((160, 100))
    assert sum(px) > 30, px
