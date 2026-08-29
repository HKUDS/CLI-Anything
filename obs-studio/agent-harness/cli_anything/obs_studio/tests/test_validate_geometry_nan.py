"""Reject non-finite values in OBS geometry validators."""

from __future__ import annotations

import pytest
from decimal import Decimal
from fractions import Fraction


from cli_anything.obs_studio.core.sources import add_source, transform_source
from cli_anything.obs_studio.utils.obs_utils import (
    validate_crop,
    validate_position,
    validate_size,
)


def _project() -> dict:
    return {
        "scenes": [
            {
                "name": "Scene",
                "sources": [
                    {
                        "id": 0,
                        "name": "Cam",
                        "type": "browser",
                        "visible": True,
                        "locked": False,
                        "opacity": 1.0,
                        "rotation": 0.0,
                        "position": {"x": 0.0, "y": 0.0},
                        "size": {"width": 1920, "height": 1080},
                        "crop": {"top": 0, "bottom": 0, "left": 0, "right": 0},
                        "settings": {},
                    }
                ],
            }
        ]
    }


def test_validate_position_rejects_nan():
    with pytest.raises(ValueError, match="finite"):
        validate_position({"x": float("nan"), "y": 1.0})


def test_validate_size_rejects_nan():
    with pytest.raises(ValueError, match="finite"):
        validate_size({"width": float("nan"), "height": 1080})


def test_validate_crop_rejects_inf():
    with pytest.raises(ValueError, match="finite"):
        validate_crop({"left": float("inf"), "right": 0, "top": 0, "bottom": 0})


def test_validate_position_accepts_finite():
    assert validate_position({"x": 1.5, "y": -2.0}) == {"x": 1.5, "y": -2.0}

def test_validate_position_preserves_large_int():
    assert validate_position({"x": 2 ** 53 + 1, "y": -(2 ** 53 + 3)}) == {
        "x": 2 ** 53 + 1,
        "y": -(2 ** 53 + 3),
    }


def test_validate_size_preserves_large_int():
    assert validate_size(
        {"width": 2 ** 53 + 1, "height": 2 ** 53 + 3}
    ) == {"width": 2 ** 53 + 1, "height": 2 ** 53 + 3}



@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("+42", 42),
        ("1", 1),
        (str(2 ** 53 + 1), 2 ** 53 + 1),
    ],
)
def test_validate_size_preserves_decimal_integer_strings(value, expected):
    """Keep signed, boundary, and large size strings exact before int conversion."""
    assert validate_size({"width": value, "height": value}) == {
        "width": expected,
        "height": expected,
    }


@pytest.mark.parametrize("value", ["0", "-1"])
def test_validate_size_rejects_non_positive_decimal_integer_strings(value):
    """Reject size strings at and below the positive lower bound."""
    with pytest.raises(ValueError, match="positive"):
        validate_size({"width": value, "height": 1})

def test_validate_crop_preserves_large_int():
    assert validate_crop(
        {
            "top": 2 ** 53 + 1,
            "bottom": 2 ** 53 + 3,
            "left": 2 ** 53 + 5,
            "right": 2 ** 53 + 7,
        }
    ) == {
        "top": 2 ** 53 + 1,
        "bottom": 2 ** 53 + 3,
        "left": 2 ** 53 + 5,
        "right": 2 ** 53 + 7,
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("+42", 42),
        ("0", 0),
        (str(2 ** 53 + 1), 2 ** 53 + 1),
    ],
)
def test_validate_crop_preserves_decimal_integer_strings(value, expected):
    """Keep signed, boundary, and large crop strings exact before int conversion."""
    assert validate_crop(
        {"top": value, "bottom": value, "left": value, "right": value}
    ) == {
        "top": expected,
        "bottom": expected,
        "left": expected,
        "right": expected,
    }


def test_validate_crop_rejects_negative_decimal_integer_string():
    """Reject negative crop strings after exact integer parsing."""
    with pytest.raises(ValueError, match="non-negative"):
        validate_crop({"top": "-1"})


def test_add_source_rejects_nan_position():
    with pytest.raises(ValueError, match="finite"):
        add_source(
            _project(),
            "browser",
            position={"x": float("nan"), "y": 0},
        )


def test_transform_source_rejects_nan_position():
    with pytest.raises(ValueError, match="finite"):
        transform_source(_project(), 0, position={"x": float("nan")})
def test_validate_size_preserves_large_int_string():
    """Locks out regression where string integers were converted to float."""
    val = str(2 ** 53 + 1)
    assert validate_size({"width": val, "height": "1080"}) == {
        "width": 2 ** 53 + 1,
        "height": 1080,
    }


def test_validate_size_preserves_decimal_and_fraction():
    """Locks out regression where Decimal and Fraction were converted to float."""
    dec = Decimal(2 ** 53 + 1)
    frac = Fraction(2 ** 53 + 3, 1)
    assert validate_size({"width": dec, "height": frac}) == {
        "width": 2 ** 53 + 1,
        "height": 2 ** 53 + 3,
    }


def test_validate_size_rejects_float_strings():
    """Locks out regression where float strings '1.5' or '1e3' were truncated/accepted as size ints."""
    with pytest.raises(ValueError, match="integer"):
        validate_size({"width": "1.5", "height": 1080})
    with pytest.raises(ValueError, match="integer"):
        validate_size({"width": "1e3", "height": 1080})


def test_transform_source_atomic_validation_on_invalid_rotation():
    """Locks out regression where earlier fields were mutated prior to rotation validation."""
    proj = _project()
    orig_pos = dict(proj["scenes"][0]["sources"][0]["position"])
    with pytest.raises(ValueError, match="finite"):
        transform_source(
            proj,
            0,
            position={"x": 100.0, "y": 200.0},
            rotation=float("nan"),
        )
    assert proj["scenes"][0]["sources"][0]["position"] == orig_pos
