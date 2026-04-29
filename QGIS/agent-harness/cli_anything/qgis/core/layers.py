"""Layer lifecycle helpers for cli-anything-qgis."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from cli_anything.qgis.core import project as project_mod
from cli_anything.qgis.utils.qgis_backend import QgisBackendError, ensure_qgis_app

FIELD_TYPES = {
    "int": ("integer", "Int"),
    "integer": ("integer", "Int"),
    "double": ("double", "Double"),
    "float": ("double", "Double"),
    "string": ("string", "QString"),
    "str": ("string", "QString"),
    "bool": ("bool", "Bool"),
    "boolean": ("bool", "Bool"),
}

GEOMETRY_TYPES = {
    "point": "Point",
    "line": "LineString",
    "linestring": "LineString",
    "polygon": "Polygon",
}


def _field_type_enum(type_name: str):
    from qgis.PyQt.QtCore import QMetaType

    normalized = type_name.strip().lower()
    if normalized not in FIELD_TYPES:
        raise QgisBackendError(
            f"Unsupported field type: {type_name}. Use one of: int, double, string, bool"
        )

    enum_name = FIELD_TYPES[normalized][1]
    return getattr(QMetaType.Type, enum_name), FIELD_TYPES[normalized][0]


def parse_field_specs(field_specs: Iterable[str]) -> list[dict]:
    """Parse repeated name:type field specifications."""
    parsed: list[dict] = []
    seen_names: set[str] = set()

    for spec in field_specs:
        name, separator, raw_type = spec.partition(":")
        if not separator or not name.strip() or not raw_type.strip():
            raise QgisBackendError(
                f"Invalid field specification: {spec}. Use name:type, e.g. name:string"
            )

        field_name = name.strip()
        if field_name in seen_names:
            raise QgisBackendError(f"Duplicate field name: {field_name}")

        field_type, normalized_type = _field_type_enum(raw_type)
        parsed.append(
            {
                "name": field_name,
                "meta_type": field_type,
                "type": normalized_type,
            }
        )
        seen_names.add(field_name)

    return parsed


def _all_layers():
    return list(project_mod.current_project().mapLayers().values())


def get_layer(identifier: str):
    """Resolve a layer by id or exact name."""
    project = project_mod.current_project()
    if identifier in project.mapLayers():
        return project.mapLayer(identifier)

    matches = [layer for layer in project.mapLayers().values() if layer.name() == identifier]
    if not matches:
        raise QgisBackendError(f"Layer not found: {identifier}")
    if len(matches) > 1:
        raise QgisBackendError(
            f"Layer name is ambiguous: {identifier}. Use the layer id instead."
        )
    return matches[0]


def _layer_type_name(layer) -> str:
    from qgis.core import QgsMapLayerType

    if layer.type() == QgsMapLayerType.VectorLayer:
        return "vector"
    if layer.type() == QgsMapLayerType.RasterLayer:
        return "raster"
    return "other"


def _field_descriptions(layer) -> list[dict]:
    descriptions = []
    for field in layer.fields():
        descriptions.append(
            {
                "name": field.name(),
                "type": field.typeName() or str(field.type()),
            }
        )
    return descriptions


def layer_summary(layer) -> dict:
    """Return a stable summary for a QGIS layer."""
    from qgis.core import QgsMapLayerType, QgsWkbTypes

    layer_type = _layer_type_name(layer)
    summary = {
        "id": layer.id(),
        "name": layer.name(),
        "type": layer_type,
        "provider": layer.providerType(),
        "source": layer.source(),
        "crs": layer.crs().authid() if layer.crs().isValid() else None,
    }

    if layer.type() == QgsMapLayerType.VectorLayer:
        summary.update(
            {
                "geometry_type": QgsWkbTypes.displayString(layer.wkbType()),
                "feature_count": int(layer.featureCount()),
                "fields": _field_descriptions(layer),
            }
        )
    else:
        summary.update(
            {
                "geometry_type": None,
                "feature_count": None,
                "fields": [],
            }
        )

    return summary


def list_layers() -> dict:
    """List all layers in the active project."""
    layers = sorted((layer_summary(layer) for layer in _all_layers()), key=lambda item: item["name"])
    return {"count": len(layers), "layers": layers}


def layer_info(identifier: str) -> dict:
    """Return detailed information for a single layer."""
    return layer_summary(get_layer(identifier))


def create_vector_layer(
    name: str,
    geometry: str,
    crs: str,
    field_specs: Iterable[str],
) -> dict:
    """Create a GeoPackage-backed vector layer and add it to the current project."""
    ensure_qgis_app()
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsField,
        QgsVectorFileWriter,
        QgsVectorLayer,
    )

    if any(layer.name() == name for layer in _all_layers()):
        raise QgisBackendError(f"Layer already exists: {name}")

    geometry_key = geometry.strip().lower()
    if geometry_key not in GEOMETRY_TYPES:
        raise QgisBackendError(
            f"Unsupported geometry type: {geometry}. Use point, linestring, or polygon."
        )

    crs_value = QgsCoordinateReferenceSystem(crs)
    if not crs_value.isValid():
        raise QgisBackendError(f"Invalid CRS: {crs}")

    fields = parse_field_specs(field_specs)
    project = project_mod.current_project()
    datastore_path = project_mod.default_datastore_path()

    memory_layer = QgsVectorLayer(f"{GEOMETRY_TYPES[geometry_key]}?crs={crs}", name, "memory")
    if not memory_layer.isValid():
        raise QgisBackendError("Failed to create the in-memory source layer")

    provider = memory_layer.dataProvider()
    provider.addAttributes([QgsField(field["name"], field["meta_type"]) for field in fields])
    memory_layer.updateFields()

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = name
    if Path(datastore_path).exists():
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

    error_code, error_message, new_filename, new_layer = QgsVectorFileWriter.writeAsVectorFormatV3(
        memory_layer,
        datastore_path,
        project.transformContext(),
        options,
    )
    if error_code != QgsVectorFileWriter.NoError:
        raise QgisBackendError(error_message or f"Failed to write layer to {datastore_path}")

    stored_layer = QgsVectorLayer(
        f"{new_filename or datastore_path}|layername={new_layer or name}",
        name,
        "ogr",
    )
    if not stored_layer.isValid():
        raise QgisBackendError("Failed to reopen the GeoPackage-backed layer")

    project.addMapLayer(stored_layer)
    return layer_summary(stored_layer)


def remove_layer(identifier: str) -> dict:
    """Remove a layer from the active project."""
    project = project_mod.current_project()
    layer = get_layer(identifier)
    removed = layer_summary(layer)
    project.removeMapLayer(layer.id())
    return removed
