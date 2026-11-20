"""Dependency failures must not be reported as successful empty geometry."""

from importlib.metadata import requires
from types import SimpleNamespace

import numpy as np
import pytest

from cli_anything.threemf.utils import threemf_backend as backend
from cli_anything.threemf.tests.test_core import _make_cube_mesh


def _failing_section_mesh(stage, error):
    class Section:
        @property
        def discrete(self):
            raise error

    def section(**kwargs):
        if stage == "section":
            raise error
        return Section()

    return SimpleNamespace(bounds=np.array([[0, 0, 0], [10, 10, 10]]), section=section)


@pytest.mark.parametrize("stage", ["section", "discrete"])
@pytest.mark.parametrize("error_type", [ImportError, ModuleNotFoundError])
def test_cross_sections_surface_dependency_failures(monkeypatch, stage, error_type):
    error = error_type("No module named 'networkx'")
    monkeypatch.setattr(
        backend, "mesh_to_trimesh", lambda _: _failing_section_mesh(stage, error)
    )

    with pytest.raises(error_type, match="networkx") as caught:
        backend.cross_section_circles(_make_cube_mesh(), num_planes=1)
    assert caught.value is error


@pytest.mark.parametrize("stage", ["section", "discrete"])
def test_cross_sections_still_skip_degenerate_geometry(monkeypatch, stage):
    monkeypatch.setattr(
        backend,
        "mesh_to_trimesh",
        lambda _: _failing_section_mesh(stage, ValueError("degenerate contour")),
    )

    assert backend.cross_section_circles(_make_cube_mesh(), num_planes=2) == []


def test_installed_harness_declares_networkx():
    dependencies = requires("cli-anything-3mf") or []
    assert any(requirement.lower().startswith("networkx") for requirement in dependencies)


@pytest.mark.parametrize("json_output", [False, True])
def test_inspect_reports_missing_dependency(monkeypatch, tmp_path, json_output):
    import json
    from click.testing import CliRunner
    from cli_anything.threemf import threemf_cli
    from cli_anything.threemf.tests.test_core import _make_threemf_data

    source = tmp_path / "part.3mf"
    source.touch()
    monkeypatch.setattr(threemf_cli.parser, "parse_3mf", lambda _: _make_threemf_data())
    monkeypatch.setattr(
        backend,
        "mesh_to_trimesh",
        lambda _: _failing_section_mesh("discrete", ModuleNotFoundError("No module named 'networkx'")),
    )
    args = (["--json"] if json_output else []) + ["inspect", str(source)]
    result = CliRunner().invoke(threemf_cli.cli, args)

    assert result.exit_code == 1
    assert "networkx" in result.output
    assert "hole_count" not in result.output
    if json_output:
        assert json.loads(result.output)["type"] == "ModuleNotFoundError"
