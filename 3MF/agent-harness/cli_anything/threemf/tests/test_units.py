"""Unit-normalisation regression tests for the 3MF parser (issue #661).

The 3MF core specification defines the model unit for its vertex
coordinates, while every geometry routine in this package (bounds,
tolerances, ``resize --diameter``) works in millimetres.
``parse_3mf`` therefore normalises vertices to millimetres and
``write_3mf`` converts them back to the archive unit.
"""

from __future__ import annotations

import zipfile

import numpy as np
import pytest
from cli_anything.threemf.core import parser as parser_mod
from cli_anything.threemf.core.parser import UNIT_TO_MM, parse_3mf, write_3mf

MODEL_PATH = "3D/3dmodel.model"


def _cube_xml(unit: str | None, size: float) -> str:
    corners = [
        (0, 0, 0), (size, 0, 0), (size, size, 0), (0, size, 0),
        (0, 0, size), (size, 0, size), (size, size, size), (0, size, size),
    ]
    verts = "\n".join(
        f'          <vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in corners
    )
    tris = [
        (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
    ]
    tri_xml = "\n".join(
        f'          <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tris
    )
    unit_attr = "" if unit is None else f' unit="{unit}"'
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<model{unit_attr} xmlns="{parser_mod.NS_CORE}">
  <resources>
    <object id="1" name="cube" type="model">
      <mesh>
        <vertices>
{verts}
        </vertices>
        <triangles>
{tri_xml}
        </triangles>
      </mesh>
    </object>
  </resources>
  <build><item objectid="1"/></build>
</model>"""


def _write_cube(path, unit: str | None, size: float = 1.0) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MODEL_PATH, _cube_xml(unit, size))


def _written_vertices(path):
    with zipfile.ZipFile(path, "r") as zf:
        root = parser_mod.ET.fromstring(zf.read(MODEL_PATH))
    ns = parser_mod._detect_namespace(root)
    # <model><resources><object><mesh><vertices>
    mesh = root.find(f".//{parser_mod._tag('mesh', ns)}")
    assert mesh is not None
    verts_el = mesh.find(parser_mod._tag("vertices", ns))
    assert verts_el is not None
    pairs = []
    for v in verts_el.iterfind(parser_mod._tag("vertex", ns)):
        pairs.append((float(v.get("x")), float(v.get("y")), float(v.get("z"))))
    return root.get("unit"), np.array(pairs, dtype=np.float64)


@pytest.mark.parametrize("unit,factor", sorted(UNIT_TO_MM.items()))
def test_parse_normalises_each_core_unit_to_millimetres(tmp_path, unit, factor):
    src = tmp_path / "cube.3mf"
    _write_cube(src, unit, size=1.0)

    data = parse_3mf(str(src))

    assert data.unit == unit
    assert np.isclose(data.meshes[0].vertices.max(), factor, rtol=1e-9)


def test_parse_keeps_archive_unit_and_normalises_inch_to_mm(tmp_path):
    src = tmp_path / "inch.3mf"
    _write_cube(src, "inch", size=1.0)

    data = parse_3mf(str(src))

    assert data.unit == "inch"
    assert np.allclose(data.meshes[0].vertices.max(axis=0), 25.4)


def test_parse_defaults_to_millimetres_without_unit_attribute(tmp_path):
    src = tmp_path / "default.3mf"
    _write_cube(src, None, size=2.0)

    data = parse_3mf(str(src))

    assert data.unit == "millimeter"
    assert np.isclose(data.meshes[0].vertices.max(), 2.0)


def test_write_converts_millimetres_back_to_archive_unit(tmp_path):
    src = tmp_path / "inch.3mf"
    dst = tmp_path / "copy.3mf"
    _write_cube(src, "inch", size=1.0)

    write_3mf(parse_3mf(str(src)), str(dst))

    written_unit, vertices = _written_vertices(dst)
    assert written_unit == "inch"
    assert np.allclose(vertices.max(axis=0), 1.0)
    assert np.allclose(vertices.min(axis=0), 0.0)


def test_unsupported_unit_raises_a_clear_error(tmp_path):
    src = tmp_path / "yard.3mf"
    _write_cube(src, "yard", size=1.0)

    with pytest.raises(ValueError, match="Unsupported 3MF model unit 'yard'"):
        parse_3mf(str(src))
