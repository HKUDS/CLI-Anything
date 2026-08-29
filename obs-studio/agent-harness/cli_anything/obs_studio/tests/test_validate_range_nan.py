"""validate_range must reject non-finite opacity-like values."""

from __future__ import annotations

import pytest

from cli_anything.obs_studio.utils.obs_utils import validate_range


def test_nan_rejected() -> None:
    with pytest.raises(ValueError, match="finite"):
        validate_range(float("nan"), 0.0, 1.0, "Opacity")


def test_inf_rejected() -> None:
    with pytest.raises(ValueError, match="finite"):
        validate_range(float("inf"), 0.0, 1.0, "Opacity")


def test_in_range_ok() -> None:
    assert validate_range(0.5, 0.0, 1.0, "Opacity") == 0.5
