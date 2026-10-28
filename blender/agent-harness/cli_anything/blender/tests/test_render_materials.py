"""Four different colours each dominate the centre pixel."""
import pytest
from PIL import Image

from cli_anything.blender.tests.test_render_helpers import needs_blender, build_and_render, dominant

# name -> (colour, dominant channel index)
COLOURS = {
    "red": ((1, 0, 0, 1), 0),
    "green": ((0, 1, 0, 1), 1),
    "blue": ((0, 0, 1, 1), 2),
    "yellow": ((1, 1, 0, 1), None),
}


@needs_blender
@pytest.mark.parametrize("cname", sorted(COLOURS))
def test_colour_dominates(tmp_path, cname):
    col, idx = COLOURS[cname]
    _, out = build_and_render(tmp_path, color=col)
    px = Image.open(out).convert("RGB").getpixel((160, 100))
    if idx is None:  # yellow: R and G high, B low
        assert px[0] > 60 and px[1] > 60 and px[2] + 40 < min(px[0], px[1]), px
    else:
        assert dominant(idx, px), (cname, px)
