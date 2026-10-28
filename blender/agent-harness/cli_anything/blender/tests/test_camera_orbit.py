"""8 cameras on a circle, all look-at: red cube centroid stays near centre."""
import math
import pytest
from PIL import Image

from cli_anything.blender.tests.test_render_helpers import needs_blender, build_and_render, dominant

R, Z = 9.0, 3.0


@needs_blender
@pytest.mark.parametrize("k", range(8))
def test_orbit_centroid(tmp_path, k):
    a = 2 * math.pi * k / 8
    cam = (round(R * math.cos(a), 3), round(R * math.sin(a), 3), Z)
    _, out = build_and_render(tmp_path, color=(1, 0, 0, 1), cam=cam)
    im = Image.open(out).convert("RGB")
    w, h = im.size
    px = im.load()
    xs = ys = n = 0
    for y in range(h):
        for x in range(w):
            if dominant(0, px[x, y]):
                xs += x; ys += y; n += 1
    assert n > 100, (cam, n)
    cx, cy = xs / n, ys / n
    assert abs(cx - w / 2) <= 30 and abs(cy - h / 2) <= 30, (cam, cx, cy)
