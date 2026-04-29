"""Layout export helpers for cli-anything-qgis."""

from __future__ import annotations

import os
from pathlib import Path

from cli_anything.qgis.core import project as project_mod
from cli_anything.qgis.core.layouts import get_layout
from cli_anything.qgis.utils import qgis_backend as backend
from cli_anything.qgis.utils.qgis_backend import QgisBackendError


def _normalize_output_path(path: str) -> str:
    return str(Path(path).expanduser().resolve())


def _bool_param(value: bool) -> str:
    return "true" if value else "false"


def _prepare_output(path: str, overwrite: bool) -> str:
    output_path = _normalize_output_path(path)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if not overwrite:
            raise QgisBackendError(
                f"Output already exists: {output_path}. Use --overwrite to replace it."
            )
        target.unlink()
    return output_path


def export_presets() -> dict:
    """Describe the supported layout export modes."""
    return {
        "formats": [
            {
                "name": "pdf",
                "algorithm": "native:printlayouttopdf",
                "description": "Export a named print layout as a PDF file.",
            },
            {
                "name": "image",
                "algorithm": "native:printlayouttoimage",
                "description": "Export a named print layout as an image file such as PNG.",
            },
        ]
    }


def export_layout_pdf(
    output_path: str,
    *,
    layout_name: str,
    dpi: float | None = None,
    force_vector: bool = False,
    force_raster: bool = False,
    georeference: bool = True,
    overwrite: bool = False,
) -> dict:
    """Export a print layout to PDF via qgis_process."""
    get_layout(layout_name)
    project_info = project_mod.save_if_dirty()
    project_path = project_mod.require_saved_project_path()
    output = _prepare_output(output_path, overwrite)

    parameters = [
        f"LAYOUT={layout_name}",
        f"OUTPUT={output}",
        f"FORCE_VECTOR={_bool_param(force_vector)}",
        f"FORCE_RASTER={_bool_param(force_raster)}",
        f"GEOREFERENCE={_bool_param(georeference)}",
    ]
    if dpi is not None:
        parameters.append(f"DPI={dpi}")

    payload = backend.run_algorithm(
        "native:printlayouttopdf",
        parameters=parameters,
        project_path=project_path,
    )

    if not os.path.exists(output):
        raise QgisBackendError(
            f"Export succeeded but output file was not created: {output}"
        )

    return {
        "format": "pdf",
        "layout": layout_name,
        "output": payload.get("results", {}).get("OUTPUT", output),
        "file_size": os.path.getsize(output),
        "project": project_info,
        "results": payload.get("results", {}),
        "log": payload.get("log", []),
    }


def export_layout_image(
    output_path: str,
    *,
    layout_name: str,
    dpi: float | None = None,
    overwrite: bool = False,
) -> dict:
    """Export a print layout to an image via qgis_process."""
    get_layout(layout_name)
    project_info = project_mod.save_if_dirty()
    project_path = project_mod.require_saved_project_path()
    output = _prepare_output(output_path, overwrite)

    parameters = [
        f"LAYOUT={layout_name}",
        f"OUTPUT={output}",
    ]
    if dpi is not None:
        parameters.append(f"DPI={dpi}")

    payload = backend.run_algorithm(
        "native:printlayouttoimage",
        parameters=parameters,
        project_path=project_path,
    )

    if not os.path.exists(output):
        raise QgisBackendError(
            f"Export succeeded but output file was not created: {output}"
        )

    return {
        "format": "image",
        "layout": layout_name,
        "output": payload.get("results", {}).get("OUTPUT", output),
        "file_size": os.path.getsize(output),
        "project": project_info,
        "results": payload.get("results", {}),
        "log": payload.get("log", []),
    }
