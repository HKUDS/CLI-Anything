"""Feature editing helpers for cli-anything-qgis."""

from __future__ import annotations

from cli_anything.qgis.core.layers import get_layer, layer_summary
from cli_anything.qgis.utils.qgis_backend import QgisBackendError, ensure_qgis_app


def _ensure_vector_layer(layer) -> None:
    from qgis.core import QgsMapLayerType

    if layer.type() != QgsMapLayerType.VectorLayer:
        raise QgisBackendError("This command only supports vector layers")


def _coerce_value(raw_value: str, field) -> object:
    from qgis.PyQt.QtCore import QMetaType

    meta_type = field.type()
    value = raw_value.strip()

    if meta_type == QMetaType.Type.Int:
        return int(value)
    if meta_type == QMetaType.Type.Double:
        return float(value)
    if meta_type == QMetaType.Type.Bool:
        lowered = value.lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
        raise QgisBackendError(f"Invalid boolean value: {raw_value}")
    return value


def _attribute_map(feature, layer) -> dict:
    result = {}
    for field in layer.fields():
        result[field.name()] = feature[field.name()]
    return result


def _feature_summary(feature, layer) -> dict:
    geometry = feature.geometry()
    return {
        "id": int(feature.id()),
        "geometry_wkt": geometry.asWkt() if geometry and not geometry.isNull() else None,
        "attributes": _attribute_map(feature, layer),
    }


def add_feature(layer_identifier: str, wkt: str, attr_specs: list[str]) -> dict:
    """Add a feature to a vector layer using WKT and key=value attributes."""
    ensure_qgis_app()
    from qgis.core import QgsFeature, QgsGeometry

    layer = get_layer(layer_identifier)
    _ensure_vector_layer(layer)

    geometry = QgsGeometry.fromWkt(wkt)
    if geometry.isNull():
        raise QgisBackendError(f"Invalid WKT geometry: {wkt}")

    provided_attrs: dict[str, object] = {}
    for spec in attr_specs:
        key, separator, raw_value = spec.partition("=")
        if not separator or not key.strip():
            raise QgisBackendError(
                f"Invalid attribute specification: {spec}. Use key=value."
            )
        field_index = layer.fields().indexFromName(key.strip())
        if field_index < 0:
            raise QgisBackendError(f"Unknown field: {key.strip()}")
        field = layer.fields()[field_index]
        provided_attrs[key.strip()] = _coerce_value(raw_value, field)

    feature = QgsFeature(layer.fields())
    feature.setGeometry(geometry)
    for field in layer.fields():
        feature[field.name()] = provided_attrs.get(field.name())

    added, features = layer.dataProvider().addFeatures([feature])
    if not added:
        raise QgisBackendError(f"Failed to add feature to layer: {layer.name()}")

    layer.updateExtents()
    added_feature = features[0] if features else feature
    return {
        "layer": layer_summary(layer),
        "feature": _feature_summary(added_feature, layer),
    }


def list_features(layer_identifier: str, limit: int = 20) -> dict:
    """List features from a vector layer."""
    layer = get_layer(layer_identifier)
    _ensure_vector_layer(layer)

    features = []
    for index, feature in enumerate(layer.getFeatures()):
        if limit and index >= limit:
            break
        features.append(_feature_summary(feature, layer))

    return {
        "layer": layer_summary(layer),
        "feature_count": int(layer.featureCount()),
        "features": features,
    }
