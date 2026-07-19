"""Reject non-finite values in OBS geometry validators."""

from __future__ import annotations

import math

import pytest

from cli_anything.obs_studio.utils.obs_utils import (
    validate_crop,
    validate_position,
    validate_size,
)


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
