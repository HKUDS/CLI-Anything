#!/usr/bin/env python3
"""QGIS CLI — stateful project, layer, layout, export, and processing commands.

Usage:
    # One-shot commands
    cli-anything-qgis project new -o demo.qgz --title "Demo"
    cli-anything-qgis --project demo.qgz layer create-vector --name places --geometry point --field name:string
    cli-anything-qgis --project demo.qgz feature add --layer places --wkt "POINT(1 2)" --attr name=HQ
    cli-anything-qgis --project demo.qgz layout create --name Main
    cli-anything-qgis --project demo.qgz export pdf out.pdf --layout Main --overwrite
    cli-anything-qgis --json process help native:printlayouttopdf

    # Interactive REPL
    cli-anything-qgis
"""

from __future__ import annotations

import functools
import json
import shlex
import sys
from pathlib import Path
from typing import Optional

import click

from cli_anything.qgis import __version__
from cli_anything.qgis.core import export as export_mod
from cli_anything.qgis.core import features as features_mod
from cli_anything.qgis.core import layers as layers_mod
from cli_anything.qgis.core import layouts as layouts_mod
from cli_anything.qgis.core import processing as processing_mod
from cli_anything.qgis.core import project as project_mod
from cli_anything.qgis.core.session import Session
from cli_anything.qgis.utils.qgis_backend import QgisBackendError, QgisProcessError

_session: Optional[Session] = None
_json_output = False
_repl_mode = False


def get_session() -> Session:
    """Return the process-local session object."""
    global _session
    if _session is None:
        session_dir = Path.home() / ".cli-anything-qgis"
        session_dir.mkdir(parents=True, exist_ok=True)
        _session = Session(str(session_dir / "session.json"))
    return _session


def _print_dict(data: dict, indent: int = 0) -> None:
    prefix = "  " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            click.echo(f"{prefix}{key}:")
            _print_dict(value, indent + 1)
        elif isinstance(value, list):
            click.echo(f"{prefix}{key}:")
            _print_list(value, indent + 1)
        else:
            click.echo(f"{prefix}{key}: {value}")


def _print_list(items: list, indent: int = 0) -> None:
    prefix = "  " * indent
    for index, item in enumerate(items):
        if isinstance(item, dict):
            click.echo(f"{prefix}[{index}]")
            _print_dict(item, indent + 1)
        else:
            click.echo(f"{prefix}- {item}")


def output(data, message: str = "") -> None:
    """Emit data in either JSON or human-readable form."""
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
        return

    if message:
        click.echo(message)
    if isinstance(data, dict):
        _print_dict(data)
    elif isinstance(data, list):
        _print_list(data)
    else:
        click.echo(str(data))


def _error_payload(exc: Exception) -> dict:
    payload = {
        "error": str(exc),
        "type": exc.__class__.__name__,
    }
    if isinstance(exc, QgisProcessError):
        payload["returncode"] = exc.returncode
        if exc.stderr:
            payload["stderr"] = exc.stderr
        if exc.stdout:
            payload["stdout"] = exc.stdout
        if exc.payload:
            payload["payload"] = exc.payload
    return payload


def handle_error(func):
    """Normalize domain/backend errors for CLI and REPL use."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (QgisBackendError, QgisProcessError, ValueError) as exc:
            payload = _error_payload(exc)
            if _json_output:
                click.echo(json.dumps(payload, indent=2, default=str))
            else:
                click.echo(f"Error: {exc}", err=True)
            if not _repl_mode:
                raise SystemExit(1)
            return None

    return wrapper


def _requested_project_path() -> str | None:
    ctx = click.get_current_context(silent=True)
    if ctx is None:
        return None
    root = ctx.find_root()
    obj = root.obj or {}
    return obj.get("project_path")


def _sync_session_project_path() -> None:
    session = get_session()
    current_path = project_mod.current_project_path()
    if current_path:
        session.set_project_path(current_path)
    else:
        session.clear_project()


def _current_project_modified() -> bool:
    try:
        return bool(project_mod.current_project().isDirty())
    except Exception:
        return False


def _load_requested_project(required: bool = False) -> str | None:
    requested = _requested_project_path()
    if requested:
        normalized = project_mod.normalize_project_path(requested)
        if project_mod.current_project_path() != normalized:
            project_mod.open_project(normalized)
            _sync_session_project_path()
        return normalized

    if required and not project_mod.current_project_path():
        raise QgisBackendError(
            "No project is loaded. Open one with project open or pass --project."
        )

    return project_mod.current_project_path() or None


def _active_project_path(required: bool = False) -> str | None:
    requested = _requested_project_path()
    if requested:
        return project_mod.normalize_project_path(requested)

    current = project_mod.current_project_path()
    if current:
        return current

    if required:
        raise QgisBackendError(
            "No project is loaded. Open one with project open or pass --project."
        )
    return None


def _auto_save_if_one_shot() -> None:
    if _repl_mode:
        return
    if project_mod.current_project_path():
        project_mod.save_project()
        _sync_session_project_path()


def _record(command: str, args: dict, result=None) -> None:
    summary = None
    if isinstance(result, dict):
        summary_keys = {
            "path",
            "output",
            "format",
            "title",
            "layer_count",
            "layout_count",
            "feature_count",
            "count",
            "name",
        }
        summary = {key: value for key, value in result.items() if key in summary_keys}
        if not summary and "layer" in result and isinstance(result["layer"], dict):
            summary = {"layer": result["layer"].get("name")}
    get_session().record(command, args, summary)


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.option(
    "--project",
    "project_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Open this project for the current command.",
)
@click.pass_context
def cli(ctx, use_json, project_path):
    """QGIS CLI for project authoring, layout export, and processing."""
    global _json_output
    _json_output = use_json
    get_session()
    ctx.obj = {"project_path": str(project_path) if project_path else None}

    if ctx.invoked_subcommand is None and "--help" not in sys.argv and "-h" not in sys.argv:
        ctx.invoke(repl)


@cli.group()
def project():
    """Project management commands."""


@project.command("new")
@click.option("-o", "--output", "output_path", required=True, type=click.Path(path_type=Path))
@click.option("--title", default=None, help="Project title")
@click.option("--crs", default="EPSG:4326", help="Project CRS, e.g. EPSG:4326")
@handle_error
def project_new(output_path: Path, title: str | None, crs: str):
    """Create a new saved QGIS project."""
    data = project_mod.create_project(str(output_path), title=title, crs=crs)
    _sync_session_project_path()
    _record("project new", {"output": str(output_path), "title": title, "crs": crs}, data)
    output(data, f"Created project: {data['path']}")


@project.command("open")
@click.argument("project_path", type=click.Path(path_type=Path))
@handle_error
def project_open(project_path: Path):
    """Open an existing QGIS project."""
    data = project_mod.open_project(str(project_path))
    _sync_session_project_path()
    _record("project open", {"project_path": str(project_path)}, data)
    output(data, f"Opened project: {data['path']}")


@project.command("save")
@click.argument("output_path", required=False, type=click.Path(path_type=Path))
@handle_error
def project_save(output_path: Path | None):
    """Save the current QGIS project."""
    if output_path is None:
        _load_requested_project(required=bool(_requested_project_path()))
    data = project_mod.save_project(str(output_path) if output_path else None)
    _sync_session_project_path()
    _record("project save", {"output": str(output_path) if output_path else None}, data)
    output(data, f"Saved project: {data['path']}")


@project.command("info")
@handle_error
def project_info():
    """Show information about the current QGIS project."""
    if _requested_project_path():
        _load_requested_project(required=True)
    data = project_mod.project_info()
    _record("project info", {}, data)
    output(data)


@project.command("set-crs")
@click.argument("crs")
@handle_error
def project_set_crs(crs: str):
    """Set the active project's CRS."""
    _load_requested_project(required=True)
    data = project_mod.set_project_crs(crs)
    _auto_save_if_one_shot()
    _record("project set-crs", {"crs": crs}, data)
    output(data, f"Updated project CRS to {crs}")


@cli.group()
def layer():
    """Layer management commands."""


@layer.command("create-vector")
@click.option("--name", required=True, help="Layer name")
@click.option(
    "--geometry",
    required=True,
    type=click.Choice(["point", "linestring", "polygon"], case_sensitive=False),
    help="Geometry type",
)
@click.option("--crs", default=None, help="Layer CRS, e.g. EPSG:4326")
@click.option("--field", "field_specs", multiple=True, help="Field spec as name:type")
@handle_error
def layer_create_vector(name: str, geometry: str, crs: str | None, field_specs: tuple[str, ...]):
    """Create a GeoPackage-backed vector layer in the current project."""
    _load_requested_project(required=True)
    effective_crs = crs or project_mod.project_info().get("crs") or "EPSG:4326"
    data = layers_mod.create_vector_layer(name, geometry, effective_crs, field_specs)
    _auto_save_if_one_shot()
    _record(
        "layer create-vector",
        {
            "name": name,
            "geometry": geometry,
            "crs": effective_crs,
            "fields": list(field_specs),
        },
        data,
    )
    output(data, f"Created layer: {data['name']}")


@layer.command("list")
@handle_error
def layer_list():
    """List layers in the current project."""
    _load_requested_project(required=True)
    data = layers_mod.list_layers()
    _record("layer list", {}, data)
    output(data)


@layer.command("info")
@click.argument("identifier")
@handle_error
def layer_info(identifier: str):
    """Show detailed information for a layer."""
    _load_requested_project(required=True)
    data = layers_mod.layer_info(identifier)
    _record("layer info", {"identifier": identifier}, data)
    output(data)


@layer.command("remove")
@click.argument("identifier")
@handle_error
def layer_remove(identifier: str):
    """Remove a layer from the current project."""
    _load_requested_project(required=True)
    data = layers_mod.remove_layer(identifier)
    _auto_save_if_one_shot()
    _record("layer remove", {"identifier": identifier}, data)
    output(data, f"Removed layer: {data['name']}")


@cli.group()
def feature():
    """Feature editing commands."""


@feature.command("add")
@click.option("--layer", "layer_identifier", required=True, help="Target layer id or name")
@click.option("--wkt", required=True, help="Geometry in WKT format")
@click.option("--attr", "attr_specs", multiple=True, help="Feature attribute as key=value")
@handle_error
def feature_add(layer_identifier: str, wkt: str, attr_specs: tuple[str, ...]):
    """Add a feature to a vector layer using WKT geometry."""
    _load_requested_project(required=True)
    data = features_mod.add_feature(layer_identifier, wkt, list(attr_specs))
    _auto_save_if_one_shot()
    _record(
        "feature add",
        {"layer": layer_identifier, "wkt": wkt, "attrs": list(attr_specs)},
        data,
    )
    output(data, f"Added feature to {data['layer']['name']}")


@feature.command("list")
@click.option("--layer", "layer_identifier", required=True, help="Target layer id or name")
@click.option("--limit", default=20, show_default=True, type=int, help="Maximum features to show")
@handle_error
def feature_list(layer_identifier: str, limit: int):
    """List features from a vector layer."""
    _load_requested_project(required=True)
    data = features_mod.list_features(layer_identifier, limit=limit)
    _record("feature list", {"layer": layer_identifier, "limit": limit}, data)
    output(data)


@cli.group()
def layout():
    """Print layout authoring commands."""


@layout.command("create")
@click.option("--name", required=True, help="Layout name")
@click.option("--page-size", default="A4", show_default=True, help="Page size")
@click.option(
    "--orientation",
    default="portrait",
    show_default=True,
    type=click.Choice(["portrait", "landscape"], case_sensitive=False),
    help="Page orientation",
)
@handle_error
def layout_create(name: str, page_size: str, orientation: str):
    """Create a print layout."""
    _load_requested_project(required=True)
    data = layouts_mod.create_layout(name, page_size=page_size, orientation=orientation)
    _auto_save_if_one_shot()
    _record(
        "layout create",
        {"name": name, "page_size": page_size, "orientation": orientation},
        data,
    )
    output(data, f"Created layout: {name}")


@layout.command("list")
@handle_error
def layout_list():
    """List print layouts in the current project."""
    _load_requested_project(required=True)
    data = layouts_mod.list_layouts()
    _record("layout list", {}, data)
    output(data)


@layout.command("info")
@click.argument("name")
@handle_error
def layout_info(name: str):
    """Show detailed information for a print layout."""
    _load_requested_project(required=True)
    data = layouts_mod.layout_info(name)
    _record("layout info", {"name": name}, data)
    output(data)


@layout.command("remove")
@click.argument("name")
@handle_error
def layout_remove(name: str):
    """Remove a print layout from the project."""
    _load_requested_project(required=True)
    data = layouts_mod.remove_layout(name)
    _auto_save_if_one_shot()
    _record("layout remove", {"name": name}, data)
    output(data, f"Removed layout: {name}")


@layout.command("add-map")
@click.option("--layout", "layout_name", required=True, help="Layout name")
@click.option("--x", type=float, required=True, help="Left position in millimeters")
@click.option("--y", type=float, required=True, help="Top position in millimeters")
@click.option("--width", type=float, required=True, help="Item width in millimeters")
@click.option("--height", type=float, required=True, help="Item height in millimeters")
@click.option("--extent", default=None, help="Map extent as xmin,ymin,xmax,ymax")
@handle_error
def layout_add_map(layout_name: str, x: float, y: float, width: float, height: float, extent: str | None):
    """Add a map item to a print layout."""
    _load_requested_project(required=True)
    data = layouts_mod.add_map_item(layout_name, x, y, width, height, extent=extent)
    _auto_save_if_one_shot()
    _record(
        "layout add-map",
        {
            "layout": layout_name,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "extent": extent,
        },
        data,
    )
    output(data, f"Added map item to layout: {layout_name}")


@layout.command("add-label")
@click.option("--layout", "layout_name", required=True, help="Layout name")
@click.option("--text", required=True, help="Label text")
@click.option("--x", type=float, required=True, help="Left position in millimeters")
@click.option("--y", type=float, required=True, help="Top position in millimeters")
@click.option("--width", type=float, required=True, help="Item width in millimeters")
@click.option("--height", type=float, required=True, help="Item height in millimeters")
@click.option("--font-size", default=18.0, show_default=True, type=float, help="Font size")
@handle_error
def layout_add_label(
    layout_name: str,
    text: str,
    x: float,
    y: float,
    width: float,
    height: float,
    font_size: float,
):
    """Add a label item to a print layout."""
    _load_requested_project(required=True)
    data = layouts_mod.add_label_item(layout_name, text, x, y, width, height, font_size=font_size)
    _auto_save_if_one_shot()
    _record(
        "layout add-label",
        {
            "layout": layout_name,
            "text": text,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "font_size": font_size,
        },
        data,
    )
    output(data, f"Added label item to layout: {layout_name}")


@cli.group()
def export():
    """Layout export commands."""


@export.command("presets")
@handle_error
def export_presets():
    """List supported export formats and their backend algorithms."""
    data = export_mod.export_presets()
    _record("export presets", {}, data)
    output(data)


@export.command("pdf")
@click.argument("output_path", type=click.Path(path_type=Path))
@click.option("--layout", "layout_name", required=True, help="Layout name")
@click.option("--dpi", default=None, type=float, help="Override layout DPI")
@click.option("--force-vector", is_flag=True, help="Always export vector output")
@click.option("--force-raster", is_flag=True, help="Always rasterize the PDF")
@click.option("--georeference/--no-georeference", default=True, help="Append georeference metadata")
@click.option("--overwrite", is_flag=True, help="Overwrite existing output")
@handle_error
def export_pdf(
    output_path: Path,
    layout_name: str,
    dpi: float | None,
    force_vector: bool,
    force_raster: bool,
    georeference: bool,
    overwrite: bool,
):
    """Export a named print layout as PDF."""
    _load_requested_project(required=True)
    data = export_mod.export_layout_pdf(
        str(output_path),
        layout_name=layout_name,
        dpi=dpi,
        force_vector=force_vector,
        force_raster=force_raster,
        georeference=georeference,
        overwrite=overwrite,
    )
    _record(
        "export pdf",
        {
            "output": str(output_path),
            "layout": layout_name,
            "dpi": dpi,
            "force_vector": force_vector,
            "force_raster": force_raster,
            "georeference": georeference,
            "overwrite": overwrite,
        },
        data,
    )
    output(data, f"Exported PDF: {data['output']}")


@export.command("image")
@click.argument("output_path", type=click.Path(path_type=Path))
@click.option("--layout", "layout_name", required=True, help="Layout name")
@click.option("--dpi", default=None, type=float, help="Override layout DPI")
@click.option("--overwrite", is_flag=True, help="Overwrite existing output")
@handle_error
def export_image(output_path: Path, layout_name: str, dpi: float | None, overwrite: bool):
    """Export a named print layout as an image file."""
    _load_requested_project(required=True)
    data = export_mod.export_layout_image(
        str(output_path),
        layout_name=layout_name,
        dpi=dpi,
        overwrite=overwrite,
    )
    _record(
        "export image",
        {
            "output": str(output_path),
            "layout": layout_name,
            "dpi": dpi,
            "overwrite": overwrite,
        },
        data,
    )
    output(data, f"Exported image: {data['output']}")


@cli.group()
def process():
    """Generic qgis_process discovery and execution commands."""


@process.command("list")
@handle_error
def process_list():
    """List installed QGIS processing algorithms."""
    data = processing_mod.list_algorithms()
    _record("process list", {}, {"count": data.get("algorithm_count")})
    output(data)


@process.command("help")
@click.argument("algorithm_id")
@handle_error
def process_help(algorithm_id: str):
    """Show parameter and output details for a processing algorithm."""
    data = processing_mod.help_algorithm(algorithm_id)
    _record("process help", {"algorithm_id": algorithm_id}, data)
    output(data)


@process.command("run")
@click.argument("algorithm_id")
@click.option("--param", "param_specs", multiple=True, help="Algorithm parameter as KEY=VALUE")
@handle_error
def process_run(algorithm_id: str, param_specs: tuple[str, ...]):
    """Run a QGIS processing algorithm through qgis_process."""
    data = processing_mod.run_algorithm(
        algorithm_id,
        param_specs=list(param_specs),
        project_path=_active_project_path(required=False),
    )
    _record("process run", {"algorithm_id": algorithm_id, "params": list(param_specs)}, data)
    output(data)


@cli.group()
def session():
    """Session state and history commands."""


@session.command("status")
@handle_error
def session_status():
    """Show the current session status."""
    _sync_session_project_path()
    data = get_session().status(modified=_current_project_modified())
    _record("session status", {}, data)
    output(data)


@session.command("history")
@click.option("--limit", default=20, show_default=True, type=int, help="Maximum history entries to show")
@handle_error
def session_history(limit: int):
    """Show recent command history."""
    data = {"history": get_session().history(limit=limit)}
    _record("session history", {"limit": limit}, {"count": len(data['history'])})
    output(data)


@cli.command()
@handle_error
def repl():
    """Start the interactive REPL."""
    from cli_anything.qgis.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True

    skin = ReplSkin("qgis", version=__version__)
    skin.print_banner()
    prompt_session = skin.create_prompt_session()

    command_help = {
        "project": "new|open|save|info|set-crs",
        "layer": "create-vector|list|info|remove",
        "feature": "add|list",
        "layout": "create|list|info|remove|add-map|add-label",
        "export": "presets|pdf|image",
        "process": "list|help|run",
        "session": "status|history",
        "help": "Show this help",
        "quit": "Exit REPL",
    }

    try:
        while True:
            _sync_session_project_path()
            session_state = get_session()
            line = skin.get_input(
                prompt_session,
                project_name=session_state.active_project_name,
                modified=_current_project_modified(),
            )
            if not line:
                continue
            lowered = line.lower()
            if lowered in {"quit", "exit", "q"}:
                skin.print_goodbye()
                break
            if lowered == "help":
                skin.help(command_help)
                continue

            try:
                args = shlex.split(line)
            except ValueError as exc:
                skin.error(str(exc))
                continue

            try:
                cli.main(args=args, standalone_mode=False)
            except SystemExit:
                pass
            except click.ClickException as exc:
                skin.error(str(exc))
            except Exception as exc:  # pragma: no cover - last-resort REPL guard
                skin.error(str(exc))
    finally:
        _repl_mode = False


def main() -> None:
    """CLI entry point for setuptools."""
    cli()


if __name__ == "__main__":
    main()
