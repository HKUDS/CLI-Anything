"""Project lifecycle helpers for cli-anything-qgis."""

from __future__ import annotations

from pathlib import Path

from cli_anything.qgis.utils.qgis_backend import QgisBackendError, ensure_qgis_app


def normalize_project_path(path: str) -> str:
    """Normalize project paths and default to .qgz when no extension is given."""
    target = Path(path).expanduser()
    if target.suffix.lower() not in {".qgs", ".qgz"}:
        target = target.with_suffix(".qgz")
    return str(target.resolve())


def current_project():
    """Return the singleton QgsProject instance."""
    ensure_qgis_app()
    from qgis.core import QgsProject

    return QgsProject.instance()


def current_project_path() -> str:
    """Return the current project file path, if any."""
    return current_project().fileName() or ""


def require_saved_project_path() -> str:
    """Return the active project path or raise if the project is unsaved."""
    project_path = current_project_path()
    if not project_path:
        raise QgisBackendError(
            "No saved project is loaded. Create or open a project first, or pass --project."
        )
    return project_path


def default_datastore_path(project_path: str | None = None) -> str:
    """Return the default GeoPackage path for a saved project."""
    path = Path(project_path or require_saved_project_path())
    return str(path.with_name(f"{path.stem}_data.gpkg"))


def _layout_names(project) -> list[str]:
    manager = project.layoutManager()
    if hasattr(manager, "printLayouts"):
        return sorted(layout.name() for layout in manager.printLayouts())
    if hasattr(manager, "layouts"):
        return sorted(layout.name() for layout in manager.layouts())
    return []


def project_info() -> dict:
    """Return a summary of the active project."""
    project = current_project()
    project_path = project.fileName() or ""
    layer_names = sorted(layer.name() for layer in project.mapLayers().values())
    layout_names = _layout_names(project)

    return {
        "path": project_path or None,
        "title": project.title() or None,
        "crs": project.crs().authid() if project.crs().isValid() else None,
        "modified": bool(project.isDirty()),
        "layer_count": len(layer_names),
        "layout_count": len(layout_names),
        "layer_names": layer_names,
        "layout_names": layout_names,
        "datastore_path": default_datastore_path(project_path) if project_path else None,
    }


def create_project(output_path: str, title: str | None = None, crs: str = "EPSG:4326") -> dict:
    """Create a new QGIS project and save it immediately."""
    ensure_qgis_app()
    from qgis.core import QgsCoordinateReferenceSystem

    project = current_project()
    normalized = normalize_project_path(output_path)
    target = Path(normalized)
    target.parent.mkdir(parents=True, exist_ok=True)

    project.clear()
    project.setFileName(normalized)
    project.setTitle(title or target.stem)

    crs_value = QgsCoordinateReferenceSystem(crs)
    if not crs_value.isValid():
        raise QgisBackendError(f"Invalid CRS: {crs}")
    project.setCrs(crs_value)

    if not project.write():
        raise QgisBackendError(f"Failed to create project at {normalized}")

    return project_info()


def open_project(project_path: str) -> dict:
    """Load an existing QGIS project."""
    project = current_project()
    normalized = normalize_project_path(project_path)
    target = Path(normalized)
    if not target.exists():
        raise QgisBackendError(f"Project does not exist: {normalized}")

    project.clear()
    if not project.read(normalized):
        raise QgisBackendError(f"Failed to open project: {normalized}")

    return project_info()


def save_project(output_path: str | None = None) -> dict:
    """Save the active QGIS project."""
    project = current_project()
    target_path = normalize_project_path(output_path) if output_path else current_project_path()
    if not target_path:
        raise QgisBackendError("No project file path is set. Use project save PATH.")

    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    project.setFileName(target_path)

    if not project.write():
        raise QgisBackendError(f"Failed to save project: {target_path}")

    return project_info()


def save_if_dirty() -> dict:
    """Save the active project when it is dirty or missing on disk."""
    project = current_project()
    target_path = require_saved_project_path()
    if project.isDirty() or not Path(target_path).exists():
        return save_project(target_path)
    return project_info()


def set_project_crs(crs: str) -> dict:
    """Set the active project CRS."""
    ensure_qgis_app()
    from qgis.core import QgsCoordinateReferenceSystem

    project = current_project()
    crs_value = QgsCoordinateReferenceSystem(crs)
    if not crs_value.isValid():
        raise QgisBackendError(f"Invalid CRS: {crs}")

    project.setCrs(crs_value)
    return project_info()
