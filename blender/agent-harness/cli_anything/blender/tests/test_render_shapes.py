"""Each primitive, rendered with look-at, shows the subject colour at centre."""
import pytest
from PIL import Image

from cli_anything.blender.tests.test_render_helpers import needs_blender, build_and_render, dominant


@needs_blender
@pytest.mark.parametrize("mesh", ["cube", "sphere", "cylinder", "cone"])
def test_shape_colour_at_centre(tmp_path, mesh):
    _, out = build_and_render(tmp_path, mesh=mesh, color=(1, 0, 0, 1))
    im = Image.open(out).convert("RGB")
    assert im.size == (320, 200)
    px = im.getpixel((160, 100))
    assert dominant(0, px), (mesh, px)
