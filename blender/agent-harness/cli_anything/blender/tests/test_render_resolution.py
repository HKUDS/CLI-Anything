"""Rendered PNG has exactly the requested resolution."""
import pytest
from PIL import Image

from cli_anything.blender.tests.test_render_helpers import needs_blender, build_and_render


@needs_blender
@pytest.mark.parametrize("res", [(160, 100), (320, 200), (640, 400)])
def test_png_size(tmp_path, res):
    _, out = build_and_render(tmp_path, res=res)
    assert Image.open(out).size == res
