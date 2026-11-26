"""CLI regression tests for invalid resize input."""

from __future__ import annotations

import pytest
from cli_anything.threemf.threemf_cli import cli
from click.testing import CliRunner


@pytest.mark.parametrize("diameter", ["nan", "inf", "-inf"])
def test_resize_rejects_non_finite_diameter_without_overwriting_files(
    tmp_path, diameter: str
) -> None:
    source = tmp_path / "source.3mf"
    output = tmp_path / "existing-output.3mf"
    source_bytes = b"source archive sentinel"
    output_bytes = b"existing output sentinel"
    source.write_bytes(source_bytes)
    output.write_bytes(output_bytes)

    result = CliRunner().invoke(
        cli,
        [
            "resize",
            str(source),
            "--hole",
            "0",
            "--diameter",
            diameter,
            "--output",
            str(output),
            "--overwrite",
        ],
    )

    assert result.exit_code == 1
    assert "finite and positive" in result.output
    assert source.read_bytes() == source_bytes
    assert output.read_bytes() == output_bytes
