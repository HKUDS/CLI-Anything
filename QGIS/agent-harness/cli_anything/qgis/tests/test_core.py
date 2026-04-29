"""Core tests for cli-anything-qgis using PyQGIS and focused backend mocks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_PACKAGE_NAMESPACE_ROOT = Path(__file__).resolve().parents[2]
if str(_PACKAGE_NAMESPACE_ROOT) in sys.path:
    sys.path.remove(str(_PACKAGE_NAMESPACE_ROOT))

from cli_anything.qgis.core import export as export_mod
from cli_anything.qgis.core import features as features_mod
from cli_anything.qgis.core import layers as layers_mod
from cli_anything.qgis.core import layouts as layouts_mod
from cli_anything.qgis.core import processing as processing_mod
from cli_anything.qgis.core import project as project_mod
from cli_anything.qgis.core.session import Session
from cli_anything.qgis.utils import qgis_backend as backend
from cli_anything.qgis.utils.qgis_backend import QgisBackendError, QgisProcessError


@pytest.fixture(autouse=True)
def clean_qgis_project():
    backend.ensure_qgis_app()
    project = project_mod.current_project()
    project.clear()
    project.setFileName("")
    yield
    project.clear()
    project.setFileName("")


def _create_polygon_project(tmp_path: Path, name: str = "demo") -> Path:
    project_path = tmp_path / f"{name}.qgz"
    project_mod.create_project(str(project_path), title=name.title(), crs="EPSG:4326")
    layers_mod.create_vector_layer(
        "areas",
        "polygon",
        "EPSG:4326",
        ["name:string", "active:bool", "count:int"],
    )
    features_mod.add_feature(
        "areas",
        "POLYGON((0 0,0 5,5 5,5 0,0 0))",
        ["name=ZoneA", "active=true", "count=3"],
    )
    project_mod.save_project()
    return project_path


def test_project_create_save_open_and_info(tmp_path: Path):
    project_path = tmp_path / "sample.qgz"

    created = project_mod.create_project(str(project_path), title="Sample", crs="EPSG:4326")
    assert created["path"] == str(project_path.resolve())
    assert created["title"] == "Sample"
    assert created["crs"] == "EPSG:4326"
    assert created["layer_count"] == 0
    assert created["layout_count"] == 0
    assert created["datastore_path"] == str((tmp_path / "sample_data.gpkg").resolve())

    updated = project_mod.set_project_crs("EPSG:3857")
    assert updated["crs"] == "EPSG:3857"

    saved = project_mod.save_project()
    assert Path(saved["path"]).exists()

    renamed_path = tmp_path / "renamed.qgz"
    renamed = project_mod.save_project(str(renamed_path))
    assert renamed["path"] == str(renamed_path.resolve())
    assert Path(renamed["path"]).exists()

    reopened = project_mod.open_project(str(renamed_path))
    assert reopened["path"] == str(renamed_path.resolve())
    assert reopened["crs"] == "EPSG:3857"
    assert reopened["title"] == "Sample"


def test_default_datastore_path(tmp_path: Path):
    project_path = tmp_path / "city.qgz"
    expected = tmp_path / "city_data.gpkg"
    assert project_mod.default_datastore_path(str(project_path)) == str(expected)


def test_parse_field_and_param_specs():
    fields = layers_mod.parse_field_specs(["name:string", "score:int", "active:bool"])
    assert [field["name"] for field in fields] == ["name", "score", "active"]
    assert [field["type"] for field in fields] == ["string", "integer", "bool"]

    params = processing_mod.parse_param_specs(["INPUT=areas", "DISTANCE=10"])
    assert params == ["INPUT=areas", "DISTANCE=10"]

    with pytest.raises(QgisBackendError):
        layers_mod.parse_field_specs(["name:string", "name:int"])

    with pytest.raises(QgisBackendError):
        processing_mod.parse_param_specs(["NOT_A_PARAM"])


def test_layer_create_list_info_and_remove(tmp_path: Path):
    project_mod.create_project(str(tmp_path / "layers.qgz"), title="Layers", crs="EPSG:4326")

    created = layers_mod.create_vector_layer(
        "places",
        "point",
        "EPSG:4326",
        ["name:string", "score:int"],
    )
    assert created["name"] == "places"
    assert created["provider"] == "ogr"
    assert created["type"] == "vector"
    assert {"name", "score"}.issubset({field["name"] for field in created["fields"]})

    listing = layers_mod.list_layers()
    assert listing["count"] == 1
    assert listing["layers"][0]["name"] == "places"

    info = layers_mod.layer_info("places")
    assert info["id"] == created["id"]
    assert info["source"].endswith("layers_data.gpkg|layername=places")

    removed = layers_mod.remove_layer("places")
    assert removed["name"] == "places"
    assert layers_mod.list_layers()["count"] == 0


def test_feature_add_and_list(tmp_path: Path):
    project_mod.create_project(str(tmp_path / "features.qgz"), title="Features", crs="EPSG:4326")
    layers_mod.create_vector_layer(
        "points",
        "point",
        "EPSG:4326",
        ["name:string", "count:int", "rating:double", "active:bool"],
    )

    added = features_mod.add_feature(
        "points",
        "POINT(1 2)",
        ["name=HQ", "count=7", "rating=2.5", "active=true"],
    )
    attrs = added["feature"]["attributes"]
    assert attrs["name"] == "HQ"
    assert attrs["count"] == 7
    assert float(attrs["rating"]) == pytest.approx(2.5)
    assert bool(attrs["active"]) is True

    listing = features_mod.list_features("points", limit=1)
    assert listing["feature_count"] == 1
    assert len(listing["features"]) == 1
    assert listing["features"][0]["geometry_wkt"].startswith("Point")


def test_feature_add_rejects_invalid_boolean(tmp_path: Path):
    project_mod.create_project(str(tmp_path / "invalid_bool.qgz"), title="InvalidBool", crs="EPSG:4326")
    layers_mod.create_vector_layer("points", "point", "EPSG:4326", ["active:bool"])

    with pytest.raises(QgisBackendError):
        features_mod.add_feature("points", "POINT(0 0)", ["active=maybe"])


def test_layout_create_add_items_and_remove(tmp_path: Path):
    _create_polygon_project(tmp_path, name="layout_demo")

    created = layouts_mod.create_layout("Main", page_size="A4", orientation="portrait")
    assert created["name"] == "Main"

    with_map = layouts_mod.add_map_item("Main", 10, 20, 180, 120)
    assert any(item["type"] == "QgsLayoutItemMap" for item in with_map["items"])

    with_label = layouts_mod.add_label_item("Main", "Demo map", 10, 8, 80, 10, font_size=16)
    assert any(item["type"] == "QgsLayoutItemLabel" for item in with_label["items"])

    listing = layouts_mod.list_layouts()
    assert listing["count"] == 1
    assert listing["layouts"][0]["name"] == "Main"

    removed = layouts_mod.remove_layout("Main")
    assert removed["name"] == "Main"
    assert layouts_mod.list_layouts()["count"] == 0


def test_layout_add_map_accepts_point_only_project(tmp_path: Path):
    project_mod.create_project(str(tmp_path / "point_layout.qgz"), title="PointLayout", crs="EPSG:4326")
    layers_mod.create_vector_layer("points", "point", "EPSG:4326", ["name:string"])
    features_mod.add_feature("points", "POINT(1 2)", ["name=HQ"])

    layouts_mod.create_layout("Main", page_size="A4", orientation="portrait")
    with_map = layouts_mod.add_map_item("Main", 10, 20, 180, 120)

    assert any(item["type"] == "QgsLayoutItemMap" for item in with_map["items"])


def test_export_presets_describe_supported_formats():
    presets = export_mod.export_presets()
    formats = {item["name"]: item["algorithm"] for item in presets["formats"]}
    assert formats == {
        "pdf": "native:printlayouttopdf",
        "image": "native:printlayouttoimage",
    }


def test_session_save_load_and_status(tmp_path: Path):
    session_path = tmp_path / "session.json"
    session = Session(str(session_path))
    session.set_project_path("/tmp/demo.qgz")
    session.record("project info", {"project": "/tmp/demo.qgz"}, {"path": "/tmp/demo.qgz"})

    reloaded = Session(str(session_path))
    assert reloaded.current_project_path == "/tmp/demo.qgz"
    assert reloaded.history_count == 1
    assert reloaded.history(limit=1)[0]["command"] == "project info"

    status = reloaded.status(modified=True)
    assert status == {
        "current_project_path": "/tmp/demo.qgz",
        "project_name": "demo.qgz",
        "modified": True,
        "history_count": 1,
    }


def test_project_path_argument_normalizes(tmp_path: Path):
    project_path = tmp_path / "demo.qgz"
    expected = f"--PROJECT_PATH={project_path.resolve()}"
    assert backend.project_path_argument(project_path) == expected
    assert backend.project_path_argument(None) is None


def test_find_qgis_process_missing_raises_clear_error():
    with mock.patch("cli_anything.qgis.utils.qgis_backend.shutil.which", return_value=None):
        with pytest.raises(QgisBackendError, match="qgis_process is not installed"):
            backend.find_qgis_process()


def test_run_process_json_normalizes_backend_failure():
    payload = {"log": [{"message": "buffer failed"}]}
    completed = subprocess.CompletedProcess(
        args=["/usr/bin/qgis_process", "--json", "run", "native:buffer"],
        returncode=1,
        stdout=json.dumps(payload),
        stderr="",
    )

    with mock.patch("cli_anything.qgis.utils.qgis_backend.find_qgis_process", return_value="/usr/bin/qgis_process"):
        with mock.patch("cli_anything.qgis.utils.qgis_backend.subprocess.run", return_value=completed):
            with pytest.raises(QgisProcessError, match="buffer failed") as exc_info:
                backend.run_process_json(["run", "native:buffer"])

    assert exc_info.value.returncode == 1
    assert exc_info.value.payload == payload
