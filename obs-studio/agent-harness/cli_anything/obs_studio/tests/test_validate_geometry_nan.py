"""Reject non-finite values in OBS geometry validators."""

from __future__ import annotations

import pytest

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
