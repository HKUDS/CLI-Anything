"""Layout authoring helpers for cli-anything-qgis."""

from __future__ import annotations

from cli_anything.qgis.core import project as project_mod
from cli_anything.qgis.utils.qgis_backend import QgisBackendError, ensure_qgis_app

PAGE_SIZES = {"A4", "A3", "A2", "A1", "A0", "LETTER"}


def _layout_manager():
    return project_mod.current_project().layoutManager()


def _all_layouts():
    manager = _layout_manager()
    if hasattr(manager, "printLayouts"):
        return list(manager.printLayouts())
    if hasattr(manager, "layouts"):
        return list(manager.layouts())
    return []


def get_layout(name: str):
    """Resolve a print layout by exact name."""
    matches = [layout for layout in _all_layouts() if layout.name() == name]
    if not matches:
        raise QgisBackendError(f"Layout not found: {name}")
    if len(matches) > 1:
        raise QgisBackendError(f"Layout name is ambiguous: {name}")
    return matches[0]


def _item_summary(item) -> dict:
    rect = item.sceneBoundingRect()
    return {
        "type": type(item).__name__,
        "display_name": item.displayName() if hasattr(item, "displayName") else type(item).__name__,
        "x": round(rect.x(), 2),
        "y": round(rect.y(), 2),
        "width": round(rect.width(), 2),
        "height": round(rect.height(), 2),
    }


def layout_summary(layout) -> dict:
    """Return a stable summary for a print layout."""
    items = [_item_summary(item) for item in layout.items()]
    return {
        "name": layout.name(),
        "item_count": len(items),
        "items": items,
    }


def list_layouts() -> dict:
    """List print layouts in the active project."""
    layouts = sorted((layout_summary(layout) for layout in _all_layouts()), key=lambda item: item["name"])
    return {"count": len(layouts), "layouts": layouts}


def _combined_project_extent():
    from qgis.core import QgsMapLayerType, QgsRectangle

    extent = None
    for layer in project_mod.current_project().mapLayers().values():
        if layer.type() != QgsMapLayerType.VectorLayer and layer.type() != QgsMapLayerType.RasterLayer:
            continue
        layer_extent = layer.extent()
        if layer_extent.isNull() or not layer_extent.isFinite():
            continue
        if extent is None:
            extent = QgsRectangle(layer_extent)
        else:
            extent.combineExtentWith(layer_extent)

    if extent is None:
        raise QgisBackendError(
            "Could not determine a map extent. Add at least one layer or pass --extent explicitly."
        )

    if extent.width() == 0 and extent.height() == 0:
        extent.grow(1.0)

    return extent


def _parse_extent(extent: str):
    from qgis.core import QgsRectangle

    parts = [part.strip() for part in extent.split(",") if part.strip()]
    if len(parts) != 4:
        raise QgisBackendError(
            f"Invalid extent: {extent}. Use xmin,ymin,xmax,ymax."
        )
    xmin, ymin, xmax, ymax = map(float, parts)
    return QgsRectangle(xmin, ymin, xmax, ymax)


def create_layout(
    name: str,
    page_size: str = "A4",
    orientation: str = "portrait",
) -> dict:
    """Create a new print layout."""
    ensure_qgis_app()
    from qgis.core import QgsLayoutItemPage, QgsPrintLayout

    if any(layout.name() == name for layout in _all_layouts()):
        raise QgisBackendError(f"Layout already exists: {name}")

    normalized_page_size = page_size.strip().upper()
    if normalized_page_size not in PAGE_SIZES:
        raise QgisBackendError(
            f"Unsupported page size: {page_size}. Use one of: {', '.join(sorted(PAGE_SIZES))}"
        )

    normalized_orientation = orientation.strip().lower()
    if normalized_orientation not in {"portrait", "landscape"}:
        raise QgisBackendError("Orientation must be portrait or landscape")

    layout = QgsPrintLayout(project_mod.current_project())
    layout.initializeDefaults()
    layout.setName(name)
    page = layout.pageCollection().page(0)
    page_orientation = (
        QgsLayoutItemPage.Landscape
        if normalized_orientation == "landscape"
        else QgsLayoutItemPage.Portrait
    )
    if not page.setPageSize(normalized_page_size, page_orientation):
        raise QgisBackendError(f"Failed to set page size: {page_size}")

    _layout_manager().addLayout(layout)
    return layout_summary(layout)


def layout_info(name: str) -> dict:
    """Return detailed information for a named layout."""
    return layout_summary(get_layout(name))


def remove_layout(name: str) -> dict:
    """Remove a print layout from the project."""
    layout = get_layout(name)
    removed = layout_summary(layout)
    _layout_manager().removeLayout(layout)
    return removed


def add_map_item(
    layout_name: str,
    x: float,
    y: float,
    width: float,
    height: float,
    extent: str | None = None,
) -> dict:
    """Add a map item to an existing layout."""
    ensure_qgis_app()
    from qgis.core import QgsLayoutItemMap, QgsLayoutPoint, QgsLayoutSize, QgsUnitTypes

    layout = get_layout(layout_name)
    map_item = QgsLayoutItemMap(layout)
    map_item.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
    map_item.attemptResize(QgsLayoutSize(width, height, QgsUnitTypes.LayoutMillimeters))
    map_item.setExtent(_parse_extent(extent) if extent else _combined_project_extent())
    layout.addLayoutItem(map_item)
    return layout_summary(layout)


def add_label_item(
    layout_name: str,
    text: str,
    x: float,
    y: float,
    width: float,
    height: float,
    font_size: float = 18.0,
) -> dict:
    """Add a label item to an existing layout."""
    ensure_qgis_app()
    from qgis.PyQt.QtGui import QFont
    from qgis.core import QgsLayoutItemLabel, QgsLayoutPoint, QgsLayoutSize, QgsUnitTypes

    layout = get_layout(layout_name)
    label = QgsLayoutItemLabel(layout)
    label.setText(text)
    font = QFont()
    font.setPointSizeF(font_size)
    label.setFont(font)
    label.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
    label.attemptResize(QgsLayoutSize(width, height, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(label)
    return layout_summary(layout)
