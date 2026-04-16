"""cli-anything-cloudcompare — Command-line harness for CloudCompare.

CloudCompare is a 3D point cloud and mesh processing application.
This CLI wraps CloudCompare's native -SILENT command-line mode with a
structured, agent-friendly interface supporting both one-shot commands
and an interactive REPL.

Usage:
    cli-anything-cloudcompare                        # start REPL
    cli-anything-cloudcompare project new -o p.json  # create project
    cli-anything-cloudcompare --project p.json cloud subsample ...
    cli-anything-cloudcompare --json project info    # JSON output

Backend: CloudCompare -SILENT (Flatpak or native install required)
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

import click

from cli_anything.cloudcompare.core.export import (
    export_cloud,
    export_mesh,
    batch_export,
    list_presets,
    CLOUD_PRESETS,
    MESH_PRESETS,
)
from cli_anything.cloudcompare.core.project import (
    create_project,
    load_project,
    save_project,
    add_cloud,
    add_mesh,
    project_info,
    record_operation,
)
from cli_anything.cloudcompare.core.session import Session
from cli_anything.cloudcompare.utils.cc_backend import (
    apply_transform,
    compute_c2c_distances,
    compute_c2m_distances,
    compute_curvature,
    compute_density,
    compute_normals,
    compute_roughness,
    convert_format,
    coord_to_sf,
    coord_to_sf_and_filter,
    crop_cloud,
    csf_filter,
    delaunay_mesh,
    extract_connected_components,
    filter_sf_by_value,
    find_cloudcompare,
    get_version,
    invert_normals,
    noise_filter,
    is_available,
    merge_clouds,
    rgb_to_sf,
    run_icp,
    sample_mesh,
    sf_to_rgb,
    sor_filter,
    subsample,
)
from cli_anything.cloudcompare.utils.repl_skin import ReplSkin

VERSION = "1.0.0"

# ── Output helpers ────────────────────────────────────────────────────────────

def _out(ctx: click.Context, data: dict) -> None:
    """Print data as JSON or human-readable."""
    if ctx.obj and ctx.obj.get("json"):
        click.echo(json.dumps(data, indent=2))
    else:
        _pretty(data)


def _pretty(data, indent: int = 0) -> None:
    """Simple human-readable pretty printer for dicts/lists."""
    prefix = "  " * indent
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                click.echo(f"{prefix}{k}:")
                _pretty(v, indent + 1)
            else:
                click.echo(f"{prefix}{k}: {v}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, dict):
                click.echo(f"{prefix}[{i}]")
                _pretty(item, indent + 1)
            else:
                click.echo(f"{prefix}  {item}")
    else:
        click.echo(f"{prefix}{data}")


def _error(msg: str, json_mode: bool = False) -> None:
    if json_mode:
        click.echo(json.dumps({"error": msg}), err=True)
    else:
        click.echo(f"Error: {msg}", err=True)


def _require_project(ctx: click.Context) -> tuple[Session, str]:
    """Get project path from context, raise UsageError if missing."""
    project_path = ctx.obj.get("project") if ctx.obj else None
    if not project_path:
        raise click.UsageError(
            "No project file specified. Use --project or create one with:\n"
            "  cli-anything-cloudcompare project new -o myproject.json"
        )
    return Session(project_path), project_path


# ── Root CLI ─────────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--project", "-p", envvar="CC_PROJECT", default=None,
              help="Path to project JSON file.")
@click.option("--json", "json_output", is_flag=True, default=False,
              help="Output results as JSON (for agent consumption).")
@click.pass_context
def cli(ctx: click.Context, project: Optional[str], json_output: bool) -> None:
    """cli-anything-cloudcompare: Agent-friendly CLI for CloudCompare.

    Run without a subcommand to enter the interactive REPL.
    Use --json for machine-readable output.

    CloudCompare must be installed:
      flatpak install flathub org.cloudcompare.CloudCompare
    """
    ctx.ensure_object(dict)
    ctx.obj["project"] = project
    ctx.obj["json"] = json_output

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── REPL ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--project", "-p", default=None, help="Project file to open in REPL.")
@click.pass_context
def repl(ctx: click.Context, project: Optional[str]) -> None:
    """Start the interactive REPL session."""
    skin = ReplSkin("cloudcompare", version=VERSION)
    skin.print_banner()

    if not is_available():
        skin.warning("CloudCompare not found. Install it first.")
        skin.hint("  flatpak install flathub org.cloudcompare.CloudCompare")
        skin.print_goodbye()
        return

    # Override project from REPL flag
    project_path = project or (ctx.obj.get("project") if ctx.obj else None)
    session = Session(project_path) if project_path else None

    pt_session = skin.create_prompt_session()
    json_mode = ctx.obj.get("json", False) if ctx.obj else False

    # Build command reference
    commands = {
        "project new -o <file>":   "Create a new project",
        "project info":            "Show project status",
        "cloud add <file>":        "Add a cloud to the project",
        "cloud list":              "List loaded clouds",
        "cloud subsample <idx>":   "Subsample a cloud",
        "cloud roughness <idx>":   "Compute roughness SF",
        "cloud density <idx>":     "Compute density SF",
        "cloud normals <idx>":     "Compute normals",
        "cloud filter-sor <idx>":  "Statistical Outlier Removal",
        "cloud crop <idx>":        "Crop to bounding box",
        "cloud merge":             "Merge all clouds",
        "distance c2c":            "Cloud-to-cloud distance",
        "distance c2m":            "Cloud-to-mesh distance",
        "transform icp":           "ICP registration",
        "export cloud <idx>":      "Export a cloud",
        "export mesh <idx>":       "Export a mesh",
        "session save":            "Save the project",
        "session history":         "Show operation history",
        "help":                    "Show this help",
        "quit / exit":             "Exit the REPL",
    }

    while True:
        proj_name = session.name if session else ""
        modified = session.is_modified if session else False
        try:
            line = skin.get_input(pt_session, project_name=proj_name, modified=modified)
        except (EOFError, KeyboardInterrupt):
            break

        if not line:
            continue

        if line.lower() in ("quit", "exit", "q"):
            if session and session.is_modified:
                skin.warning("Unsaved changes in project. Save with: session save")
            break

        if line.lower() in ("help", "h", "?"):
            skin.help(commands)
            continue

        # Parse and invoke as Click command via subprocess-style invocation
        try:
            args = line.split()
            # Inject project context if available
            if session and "--project" not in args and "-p" not in args:
                args = ["--project", session.project_path] + args
            if json_mode:
                args = ["--json"] + args
            standalone_mode_result = cli.main(
                args=args,
                standalone_mode=False,
                obj={"project": session.project_path if session else None, "json": json_mode},
            )
            # Update session when project new or explicit -p/--project is used
            new_path: Optional[str] = None
            raw = line.split()
            if len(raw) >= 2 and raw[0] == "project" and raw[1] == "new":
                for i, tok in enumerate(raw):
                    if tok in ("-o", "--output") and i + 1 < len(raw):
                        new_path = raw[i + 1]
                        break
            elif "--project" in raw or "-p" in raw:
                for i, tok in enumerate(raw):
                    if tok in ("--project", "-p") and i + 1 < len(raw):
                        new_path = raw[i + 1]
                        break
            if new_path:
                session = Session(new_path)
        except SystemExit:
            pass
        except click.UsageError as e:
            skin.error(str(e))
        except Exception as e:
            skin.error(str(e))

    skin.print_goodbye()


# ── project group ─────────────────────────────────────────────────────────────

@cli.group()
def project() -> None:
    """Project management commands (create, open, inspect)."""


@project.command("new")
@click.option("--output", "-o", required=True, help="Output .json project file path.")
@click.option("--name", "-n", default=None, help="Project name.")
@click.pass_context
def project_new(ctx: click.Context, output: str, name: Optional[str]) -> None:
    """Create a new empty project file."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        proj = create_project(output, name)
        info = project_info(proj)
        info["project_path"] = os.path.abspath(output)
        _out(ctx, info)
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@project.command("info")
@click.pass_context
def project_info_cmd(ctx: click.Context) -> None:
    """Show project info and loaded entities."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        info = session.info()
        info["project_path"] = path
        _out(ctx, info)
    except click.UsageError as e:
        _error(str(e), json_mode)
        sys.exit(1)
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@project.command("status")
@click.pass_context
def project_status(ctx: click.Context) -> None:
    """Show quick project status."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        _out(ctx, session.status())
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


# ── cloud group ───────────────────────────────────────────────────────────────

@cli.group()
def cloud() -> None:
    """Point cloud operations (add, subsample, filter, analyze)."""


@cloud.command("add")
@click.argument("cloud_file")
@click.option("--label", "-l", default=None, help="Optional label for this cloud.")
@click.pass_context
def cloud_add(ctx: click.Context, cloud_file: str, label: Optional[str]) -> None:
    """Add a cloud file to the project."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        entry = session.add_cloud(cloud_file, label)
        session.save()
        _out(ctx, {"added": entry, "cloud_count": session.cloud_count})
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@cloud.command("list")
@click.pass_context
def cloud_list(ctx: click.Context) -> None:
    """List all clouds in the project."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        clouds = session.info()["clouds"]
        _out(ctx, {"clouds": clouds, "count": len(clouds)})
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@cloud.command("subsample")
@click.argument("cloud_index", type=int)
@click.option("--output", "-o", required=True, help="Output cloud file path.")
@click.option("--method", "-m", default="SPATIAL",
              type=click.Choice(["RANDOM", "SPATIAL", "OCTREE"], case_sensitive=False),
              help="Subsampling method.")
@click.option("--param", "-n", type=float, default=0.05,
              help="RANDOM: point count; SPATIAL: min distance; OCTREE: level.")
@click.option("--add-to-project", is_flag=True, default=False,
              help="Add output cloud back to the project.")
@click.pass_context
def cloud_subsample(
    ctx: click.Context,
    cloud_index: int,
    output: str,
    method: str,
    param: float,
    add_to_project: bool,
) -> None:
    """Subsample a cloud using RANDOM, SPATIAL, or OCTREE method."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        cloud_entry = session.get_cloud(cloud_index)
        result = subsample(cloud_entry["path"], output, method.upper(), param)
        if result["returncode"] != 0:
            raise RuntimeError(f"Subsample failed:\n{result['stderr'][:500]}")
        session.record("subsample", [cloud_entry["path"]], [output],
                       {"method": method, "param": param})
        if add_to_project and result.get("exists"):
            session.add_cloud(output, f"{cloud_entry['label']}_ss")
        session.save()
        _out(ctx, {
            "input": cloud_entry["path"],
            "output": result.get("output", output),
            "method": method,
            "param": param,
            "exists": result.get("exists", False),
            "file_size": result.get("file_size", 0),
        })
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@cloud.command("roughness")
@click.argument("cloud_index", type=int)
@click.option("--output", "-o", required=True, help="Output cloud file path.")
@click.option("--radius", "-r", type=float, default=0.1,
              help="Sphere radius for roughness computation.")
@click.option("--add-to-project", is_flag=True, default=False)
@click.pass_context
def cloud_roughness(
    ctx: click.Context,
    cloud_index: int,
    output: str,
    radius: float,
    add_to_project: bool,
) -> None:
    """Compute roughness scalar field for a cloud."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        cloud_entry = session.get_cloud(cloud_index)
        result = compute_roughness(cloud_entry["path"], output, radius)
        if result["returncode"] != 0:
            raise RuntimeError(f"Roughness failed:\n{result['stderr'][:500]}")
        session.record("roughness", [cloud_entry["path"]], [output], {"radius": radius})
        if add_to_project and result.get("exists"):
            session.add_cloud(output, f"{cloud_entry['label']}_rough")
        session.save()
        _out(ctx, {
            "input": cloud_entry["path"],
            "output": output,
            "radius": radius,
            "exists": result.get("exists", False),
            "file_size": result.get("file_size", 0),
        })
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@cloud.command("density")
@click.argument("cloud_index", type=int)
@click.option("--output", "-o", required=True, help="Output cloud file path.")
@click.option("--radius", "-r", type=float, default=0.1, help="Sphere radius.")
@click.option("--type", "density_type", default="KNN",
              type=click.Choice(["KNN", "SURFACE", "VOLUME"], case_sensitive=False),
              help="Density type.")
@click.option("--add-to-project", is_flag=True, default=False)
@click.pass_context
def cloud_density(
    ctx: click.Context,
    cloud_index: int,
    output: str,
    radius: float,
    density_type: str,
    add_to_project: bool,
) -> None:
    """Compute point density scalar field."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        cloud_entry = session.get_cloud(cloud_index)
        result = compute_density(cloud_entry["path"], output, radius, density_type)
        if result["returncode"] != 0:
            raise RuntimeError(f"Density failed:\n{result['stderr'][:500]}")
        session.record("density", [cloud_entry["path"]], [output],
                       {"radius": radius, "type": density_type})
        if add_to_project and result.get("exists"):
            session.add_cloud(output, f"{cloud_entry['label']}_density")
        session.save()
        _out(ctx, {
            "input": cloud_entry["path"],
            "output": output,
            "radius": radius,
            "type": density_type,
            "exists": result.get("exists", False),
            "file_size": result.get("file_size", 0),
        })
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@cloud.command("curvature")
@click.argument("cloud_index", type=int)
@click.option("--output", "-o", required=True, help="Output cloud file path.")
@click.option("--type", "curv_type", default="MEAN",
              type=click.Choice(["MEAN", "GAUSS"], case_sensitive=False))
@click.option("--radius", "-r", type=float, default=0.1)
@click.option("--add-to-project", is_flag=True, default=False)
@click.pass_context
def cloud_curvature(
    ctx: click.Context,
    cloud_index: int,
    output: str,
    curv_type: str,
    radius: float,
    add_to_project: bool,
) -> None:
    """Compute curvature scalar field (MEAN or GAUSS)."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        cloud_entry = session.get_cloud(cloud_index)
        result = compute_curvature(cloud_entry["path"], output, curv_type, radius)
        if result["returncode"] != 0:
            raise RuntimeError(f"Curvature failed:\n{result['stderr'][:500]}")
        session.record("curvature", [cloud_entry["path"]], [output],
                       {"type": curv_type, "radius": radius})
        if add_to_project and result.get("exists"):
            session.add_cloud(output, f"{cloud_entry['label']}_curv")
        session.save()
        _out(ctx, {
            "input": cloud_entry["path"],
            "output": output,
            "type": curv_type,
            "radius": radius,
            "exists": result.get("exists", False),
        })
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@cloud.command("normals")
@click.argument("cloud_index", type=int)
@click.option("--output", "-o", required=True, help="Output cloud file path.")
@click.option("--level", type=int, default=10, help="Octree level (1-10).")
@click.option("--orientation", default="PLUS_Z",
              type=click.Choice(["PLUS_X", "PLUS_Y", "PLUS_Z",
                                  "MINUS_X", "MINUS_Y", "MINUS_Z"], case_sensitive=False))
@click.option("--add-to-project", is_flag=True, default=False)
@click.pass_context
def cloud_normals(
    ctx: click.Context,
    cloud_index: int,
    output: str,
    level: int,
    orientation: str,
    add_to_project: bool,
) -> None:
    """Compute normals via octree method."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        cloud_entry = session.get_cloud(cloud_index)
        result = compute_normals(cloud_entry["path"], output, level, orientation)
        if result["returncode"] != 0:
            raise RuntimeError(f"Normals failed:\n{result['stderr'][:500]}")
        session.record("normals", [cloud_entry["path"]], [output],
                       {"level": level, "orientation": orientation})
        if add_to_project and result.get("exists"):
            session.add_cloud(output, f"{cloud_entry['label']}_normals")
        session.save()
        _out(ctx, {
            "input": cloud_entry["path"],
            "output": output,
            "level": level,
            "orientation": orientation,
            "exists": result.get("exists", False),
        })
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@cloud.command("filter-sor")
@click.argument("cloud_index", type=int)
@click.option("--output", "-o", required=True, help="Output cloud file path.")
@click.option("--nb-points", type=int, default=6, help="K nearest neighbors.")
@click.option("--std-ratio", type=float, default=1.0, help="Std deviation multiplier.")
@click.option("--add-to-project", is_flag=True, default=False)
@click.pass_context
def cloud_filter_sor(
    ctx: click.Context,
    cloud_index: int,
    output: str,
    nb_points: int,
    std_ratio: float,
    add_to_project: bool,
) -> None:
    """Statistical Outlier Removal (SOR) filter — removes noise points."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        cloud_entry = session.get_cloud(cloud_index)
        result = sor_filter(cloud_entry["path"], output, nb_points, std_ratio)
        if result["returncode"] != 0:
            raise RuntimeError(f"SOR filter failed:\n{result['stderr'][:500]}")
        session.record("sor_filter", [cloud_entry["path"]], [output],
                       {"nb_points": nb_points, "std_ratio": std_ratio})
        if add_to_project and result.get("exists"):
            session.add_cloud(output, f"{cloud_entry['label']}_sor")
        session.save()
        _out(ctx, {
            "input": cloud_entry["path"],
            "output": output,
            "nb_points": nb_points,
            "std_ratio": std_ratio,
            "exists": result.get("exists", False),
            "file_size": result.get("file_size", 0),
        })
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@cloud.command("crop")
@click.argument("cloud_index", type=int)
@click.option("--output", "-o", required=True, help="Output cloud file path.")
@click.option("--xmin", type=float, required=True)
@click.option("--ymin", type=float, required=True)
@click.option("--zmin", type=float, required=True)
@click.option("--xmax", type=float, required=True)
@click.option("--ymax", type=float, required=True)
@click.option("--zmax", type=float, required=True)
@click.option("--outside", is_flag=True, default=False, help="Keep points outside the box.")
@click.option("--add-to-project", is_flag=True, default=False)
@click.pass_context
def cloud_crop(
    ctx: click.Context,
    cloud_index: int,
    output: str,
    xmin: float,
    ymin: float,
    zmin: float,
    xmax: float,
    ymax: float,
    zmax: float,
    outside: bool,
    add_to_project: bool,
) -> None:
    """Crop a cloud to an axis-aligned bounding box."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        cloud_entry = session.get_cloud(cloud_index)
        result = crop_cloud(cloud_entry["path"], output,
                            xmin, ymin, zmin, xmax, ymax, zmax, outside)
        if result["returncode"] != 0:
            raise RuntimeError(f"Crop failed:\n{result['stderr'][:500]}")
        session.record("crop", [cloud_entry["path"]], [output], {
            "bbox": [xmin, ymin, zmin, xmax, ymax, zmax],
            "outside": outside,
        })
        if add_to_project and result.get("exists"):
            session.add_cloud(output, f"{cloud_entry['label']}_crop")
        session.save()
        _out(ctx, {
            "input": cloud_entry["path"],
            "output": output,
            "bbox": [xmin, ymin, zmin, xmax, ymax, zmax],
            "outside": outside,
            "exists": result.get("exists", False),
        })
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@cloud.command("filter-csf")
@click.argument("cloud_index", type=int)
@click.option("--ground", "-g", required=True, help="Output path for ground points.")
@click.option("--offground", "-u", default=None,
              help="Output path for off-ground points (optional).")
@click.option("--scene", default="RELIEF",
              type=click.Choice(["SLOPE", "RELIEF", "FLAT"], case_sensitive=False),
              help="Scene type: SLOPE (steep), RELIEF (general, default), FLAT (urban).")
@click.option("--cloth-resolution", type=float, default=2.0,
              help="Cloth grid resolution in metres. Smaller = finer detail. Default: 2.0.")
@click.option("--class-threshold", type=float, default=0.5,
              help="Max distance (m) from cloth to classify as ground. Default: 0.5.")
@click.option("--max-iteration", type=int, default=500,
              help="Maximum cloth simulation iterations. Default: 500.")
@click.option("--proc-slope", is_flag=True, default=False,
              help="Enable slope post-processing to smooth terrain artifacts.")
@click.option("--add-to-project", is_flag=True, default=False,
              help="Add ground (and off-ground if exported) back to the project.")
@click.pass_context
def cloud_filter_csf(
    ctx: click.Context,
    cloud_index: int,
    ground: str,
    offground: Optional[str],
    scene: str,
    cloth_resolution: float,
    class_threshold: float,
    max_iteration: int,
    proc_slope: bool,
    add_to_project: bool,
) -> None:
    """Ground filtering using the Cloth Simulation Filter (CSF) algorithm.

    Separates a LiDAR scan into ground points and off-ground points
    (buildings, vegetation, etc.) by simulating a cloth draped over the
    inverted point cloud.

    Scene presets:
      SLOPE  — steep terrain (rigidness=1, looser cloth)
      RELIEF — mixed terrain (rigidness=2, default)
      FLAT   — flat/urban terrain (rigidness=3, stiffer cloth)

    Examples:

      # Extract ground only (outdoor LiDAR, mixed terrain)
      cloud filter-csf 0 --ground ground.las --scene RELIEF

      # Split ground + off-ground (urban scene)
      cloud filter-csf 0 --ground ground.las --offground buildings.las \\
          --scene FLAT --cloth-resolution 0.5 --class-threshold 0.3

      # Steep forested slope with slope post-processing
      cloud filter-csf 0 --ground ground.las --scene SLOPE --proc-slope
    """
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        cloud_entry = session.get_cloud(cloud_index)
        result = csf_filter(
            cloud_entry["path"],
            ground_output=ground,
            offground_output=offground,
            scene=scene.upper(),
            cloth_resolution=cloth_resolution,
            class_threshold=class_threshold,
            max_iteration=max_iteration,
            proc_slope=proc_slope,
        )
        if result["returncode"] != 0:
            raise RuntimeError(f"CSF filter failed:\n{result['stderr'][:500]}")
        if not result.get("ground_exists"):
            raise RuntimeError(
                "CSF ran but ground output not found. "
                "Check that the CSF plugin is installed in CloudCompare."
            )
        params = {
            "scene": scene, "cloth_resolution": cloth_resolution,
            "class_threshold": class_threshold, "max_iteration": max_iteration,
            "proc_slope": proc_slope,
        }
        outputs = [ground]
        if offground:
            outputs.append(offground)
        session.record("csf_filter", [cloud_entry["path"]], outputs, params)
        if add_to_project:
            if result.get("ground_exists"):
                session.add_cloud(ground, f"{cloud_entry['label']}_ground")
            if offground and result.get("offground_exists"):
                session.add_cloud(offground, f"{cloud_entry['label']}_offground")
        session.save()
        out = {
            "input": cloud_entry["path"],
            "scene": scene,
            "cloth_resolution": cloth_resolution,
            "class_threshold": class_threshold,
            "ground": ground,
            "ground_exists": result.get("ground_exists", False),
            "ground_size": result.get("ground_size", 0),
        }
        if offground:
            out["offground"] = offground
            out["offground_exists"] = result.get("offground_exists", False)
            out["offground_size"] = result.get("offground_size", 0)
        _out(ctx, out)
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@cloud.command("sf-from-coord")
@click.argument("cloud_index", type=int)
@click.option("--output", "-o", required=True, help="Output cloud file path.")
@click.option("--dim", "dimension", default="Z",
              type=click.Choice(["X", "Y", "Z"], case_sensitive=False),
              help="Coordinate axis to convert to scalar field. Default: Z (height).")
@click.option("--sf-index", type=int, default=0,
              help="Index to set as active SF after creation.")
@click.option("--add-to-project", is_flag=True, default=False)
@click.pass_context
def cloud_sf_from_coord(
    ctx: click.Context,
    cloud_index: int,
    output: str,
    dimension: str,
    sf_index: int,
    add_to_project: bool,
) -> None:
    """Convert a coordinate axis (X/Y/Z) to a scalar field.

    Most commonly used to create a height (Z) scalar field for
    elevation-based analysis and visualization.

    Example:
        cloud sf-from-coord 0 -o with_z_sf.las --dim Z
    """
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        cloud_entry = session.get_cloud(cloud_index)
        result = coord_to_sf(cloud_entry["path"], output, dimension, sf_index)
        if result["returncode"] != 0:
            raise RuntimeError(f"coord_to_sf failed:\n{result['stderr'][:500]}")
        session.record("coord_to_sf", [cloud_entry["path"]], [output],
                       {"dimension": dimension, "sf_index": sf_index})
        if add_to_project and result.get("exists"):
            session.add_cloud(output, f"{cloud_entry['label']}_sf{dimension}")
        session.save()
        _out(ctx, {
            "input": cloud_entry["path"],
            "output": output,
            "dimension": dimension,
            "sf_index": sf_index,
            "exists": result.get("exists", False),
            "file_size": result.get("file_size", 0),
        })
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@cloud.command("filter-sf")
@click.argument("cloud_index", type=int)
@click.option("--output", "-o", required=True, help="Output cloud file path.")
@click.option("--min", "min_val", type=float, required=True,
              help="Minimum scalar field value to keep.")
@click.option("--max", "max_val", type=float, required=True,
              help="Maximum scalar field value to keep.")
@click.option("--sf-index", type=int, default=None,
              help="Set this SF index as active before filtering.")
@click.option("--add-to-project", is_flag=True, default=False)
@click.pass_context
def cloud_filter_sf(
    ctx: click.Context,
    cloud_index: int,
    output: str,
    min_val: float,
    max_val: float,
    sf_index: Optional[int],
    add_to_project: bool,
) -> None:
    """Filter a cloud by scalar field value range.

    Keeps only points whose active scalar field value is in [min, max].
    Typically used after sf-from-coord to filter by height range.

    Example — keep points between z=10m and z=20m:
        cloud sf-from-coord 0 -o with_z.las --dim Z --add-to-project
        cloud filter-sf 1 -o slice.las --min 10.0 --max 20.0
    """
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        cloud_entry = session.get_cloud(cloud_index)
        result = filter_sf_by_value(cloud_entry["path"], output, min_val, max_val, sf_index)
        if result["returncode"] != 0:
            raise RuntimeError(f"filter_sf failed:\n{result['stderr'][:500]}")
        session.record("filter_sf", [cloud_entry["path"]], [output],
                       {"min": min_val, "max": max_val, "sf_index": sf_index})
        if add_to_project and result.get("exists"):
            session.add_cloud(output, f"{cloud_entry['label']}_sffilter")
        session.save()
        _out(ctx, {
            "input": cloud_entry["path"],
            "output": output,
            "min": min_val,
            "max": max_val,
            "sf_index": sf_index,
            "exists": result.get("exists", False),
            "file_size": result.get("file_size", 0),
        })
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@cloud.command("sf-filter-z")
@click.argument("cloud_index", type=int)
@click.option("--output", "-o", required=True, help="Output cloud file path.")
@click.option("--min", "min_val", type=float, default=None,
              help="Minimum Z height to keep (omit for no lower bound).")
@click.option("--max", "max_val", type=float, default=None,
              help="Maximum Z height to keep (omit for no upper bound).")
@click.option("--add-to-project", is_flag=True, default=False)
@click.pass_context
def cloud_sf_filter_z(
    ctx: click.Context,
    cloud_index: int,
    output: str,
    min_val: Optional[float],
    max_val: Optional[float],
    add_to_project: bool,
) -> None:
    """Convert Z to scalar field and filter by height range in one step.

    Convenience command: combines sf-from-coord (Z) + filter-sf in a single
    CloudCompare call. Ideal for extracting a horizontal slice from a scan.

    Example — extract a 1-metre slice at z=5m to z=6m:
        cloud sf-filter-z 0 -o slice.las --min 5.0 --max 6.0
    """
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        cloud_entry = session.get_cloud(cloud_index)
        if min_val is None and max_val is None:
            raise click.UsageError("Provide at least one of --min or --max.")
        result = coord_to_sf_and_filter(
            cloud_entry["path"], output, dimension="Z",
            min_val=min_val, max_val=max_val,
        )
        if result["returncode"] != 0:
            raise RuntimeError(f"sf-filter-z failed:\n{result['stderr'][:500]}")
        session.record("sf_filter_z", [cloud_entry["path"]], [output],
                       {"min": min_val, "max": max_val})
        if add_to_project and result.get("exists"):
            session.add_cloud(output, f"{cloud_entry['label']}_zslice")
        session.save()
        _out(ctx, {
            "input": cloud_entry["path"],
            "output": output,
            "z_min": min_val,
            "z_max": max_val,
            "exists": result.get("exists", False),
            "file_size": result.get("file_size", 0),
        })
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@cloud.command("sf-to-rgb")
@click.argument("cloud_index", type=int)
@click.option("--output", "-o", required=True, help="Output cloud with RGB colours.")
@click.option("--add-to-project", is_flag=True, default=False)
@click.pass_context
def cloud_sf_to_rgb(ctx: click.Context, cloud_index: int, output: str, add_to_project: bool) -> None:
    """Convert the active scalar field to RGB colours."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        cloud_entry = session.get_cloud(cloud_index)
        result = sf_to_rgb(cloud_entry["path"], output)
        if result["returncode"] != 0:
            raise RuntimeError(f"SF→RGB failed:\n{result['stderr'][:500]}")
        session.record("sf_to_rgb", [cloud_entry["path"]], [output], {})
        if add_to_project and result.get("exists"):
            session.add_cloud(output, f"{cloud_entry['label']}_rgb")
        session.save()
        _out(ctx, {"input": cloud_entry["path"], "output": output,
                   "exists": result.get("exists", False), "file_size": result.get("file_size", 0)})
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@cloud.command("rgb-to-sf")
@click.argument("cloud_index", type=int)
@click.option("--output", "-o", required=True, help="Output cloud with SF from RGB.")
@click.option("--add-to-project", is_flag=True, default=False)
@click.pass_context
def cloud_rgb_to_sf(ctx: click.Context, cloud_index: int, output: str, add_to_project: bool) -> None:
    """Convert RGB colours to a scalar field (luminance)."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        cloud_entry = session.get_cloud(cloud_index)
        result = rgb_to_sf(cloud_entry["path"], output)
        if result["returncode"] != 0:
            raise RuntimeError(f"RGB→SF failed:\n{result['stderr'][:500]}")
        session.record("rgb_to_sf", [cloud_entry["path"]], [output], {})
        if add_to_project and result.get("exists"):
            session.add_cloud(output, f"{cloud_entry['label']}_sf")
        session.save()
        _out(ctx, {"input": cloud_entry["path"], "output": output,
                   "exists": result.get("exists", False), "file_size": result.get("file_size", 0)})
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@cloud.command("noise-filter")
@click.argument("cloud_index", type=int)
@click.option("--output", "-o", required=True, help="Output filtered cloud.")
@click.option("--knn", type=int, default=6, help="Number of nearest neighbours (default 6).")
@click.option("--noisiness", type=float, default=1.0, help="Noise threshold multiplier.")
@click.option("--radius", type=float, default=0.1, help="Search radius (when --use-radius).")
@click.option("--use-radius", is_flag=True, default=False, help="Use radius mode instead of KNN.")
@click.option("--absolute", is_flag=True, default=False, help="Use absolute noise threshold.")
@click.option("--add-to-project", is_flag=True, default=False)
@click.pass_context
def cloud_noise_filter(
    ctx: click.Context,
    cloud_index: int,
    output: str,
    knn: int,
    noisiness: float,
    radius: float,
    use_radius: bool,
    absolute: bool,
    add_to_project: bool,
) -> None:
    """Remove noisy points using the PCL noise filter (-NOISE KNN/RADIUS REL/ABS)."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        cloud_entry = session.get_cloud(cloud_index)
        result = noise_filter(cloud_entry["path"], output, knn=knn, noisiness=noisiness,
                              use_radius=use_radius, radius=radius, absolute=absolute)
        if result["returncode"] != 0:
            raise RuntimeError(f"Noise filter failed:\n{result['stderr'][:500]}")
        session.record("noise_filter", [cloud_entry["path"]], [output],
                       {"knn": knn, "noisiness": noisiness, "use_radius": use_radius})
        if add_to_project and result.get("exists"):
            session.add_cloud(output, f"{cloud_entry['label']}_denoised")
        session.save()
        _out(ctx, {"input": cloud_entry["path"], "output": output,
                   "knn": knn, "noisiness": noisiness,
                   "exists": result.get("exists", False), "file_size": result.get("file_size", 0)})
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@cloud.command("invert-normals")
@click.argument("cloud_index", type=int)
@click.option("--output", "-o", required=True, help="Output cloud with inverted normals.")
@click.option("--add-to-project", is_flag=True, default=False)
@click.pass_context
def cloud_invert_normals(ctx: click.Context, cloud_index: int, output: str, add_to_project: bool) -> None:
    """Invert (flip) all normals in the cloud."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        cloud_entry = session.get_cloud(cloud_index)
        result = invert_normals(cloud_entry["path"], output)
        if result["returncode"] != 0:
            raise RuntimeError(f"Invert normals failed:\n{result['stderr'][:500]}")
        session.record("invert_normals", [cloud_entry["path"]], [output], {})
        if add_to_project and result.get("exists"):
            session.add_cloud(output, f"{cloud_entry['label']}_inv")
        session.save()
        _out(ctx, {"input": cloud_entry["path"], "output": output,
                   "exists": result.get("exists", False), "file_size": result.get("file_size", 0)})
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@cloud.command("segment-cc")
@click.argument("cloud_index", type=int)
@click.option("--output-dir", "-o", required=True, help="Directory to save component clouds.")
@click.option("--octree-level", type=int, default=8, help="Octree level (1-10).")
@click.option("--min-points", type=int, default=100, help="Minimum points per component.")
@click.option("--fmt", default="xyz", help="Output format extension (xyz, las, ply, etc.).")
@click.pass_context
def cloud_segment_cc(
    ctx: click.Context,
    cloud_index: int,
    output_dir: str,
    octree_level: int,
    min_points: int,
    fmt: str,
) -> None:
    """Segment cloud into connected components (clusters).

    Each component is saved as a separate file in OUTPUT_DIR.
    """
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        cloud_entry = session.get_cloud(cloud_index)
        result = extract_connected_components(
            cloud_entry["path"], output_dir, octree_level, min_points, fmt
        )
        session.record("segment_cc", [cloud_entry["path"]], result["components"],
                       {"octree_level": octree_level, "min_points": min_points})
        session.save()
        _out(ctx, {
            "input": cloud_entry["path"],
            "output_dir": output_dir,
            "octree_level": octree_level,
            "min_points": min_points,
            "component_count": result["component_count"],
            "components": result["components"],
        })
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@cloud.command("mesh-delaunay")
@click.argument("cloud_index", type=int)
@click.option("--output", "-o", required=True, help="Output mesh file (.obj, .ply, .stl).")
@click.option("--best-fit", is_flag=True, default=False,
              help="Use best-fit plane instead of axis-aligned XY.")
@click.option("--max-edge-length", type=float, default=0.0,
              help="Remove triangles with edges longer than this (0=no limit).")
@click.option("--add-to-project", is_flag=True, default=False)
@click.pass_context
def cloud_mesh_delaunay(
    ctx: click.Context,
    cloud_index: int,
    output: str,
    best_fit: bool,
    max_edge_length: float,
    add_to_project: bool,
) -> None:
    """Build a 2.5-D Delaunay triangulation mesh from a cloud."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        cloud_entry = session.get_cloud(cloud_index)
        result = delaunay_mesh(
            cloud_entry["path"], output,
            axis_aligned=not best_fit,
            max_edge_length=max_edge_length,
        )
        if result["returncode"] != 0:
            raise RuntimeError(f"Delaunay failed:\n{result['stderr'][:500]}")
        session.record("delaunay_mesh", [cloud_entry["path"]], [output],
                       {"axis_aligned": not best_fit, "max_edge_length": max_edge_length})
        if add_to_project and result.get("exists"):
            session.add_mesh(output, f"{cloud_entry['label']}_mesh")
        session.save()
        _out(ctx, {"input": cloud_entry["path"], "output": output,
                   "exists": result.get("exists", False), "file_size": result.get("file_size", 0)})
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@cloud.command("merge")
@click.option("--output", "-o", required=True, help="Output merged cloud file.")
@click.option("--add-to-project", is_flag=True, default=False)
@click.pass_context
def cloud_merge(ctx: click.Context, output: str, add_to_project: bool) -> None:
    """Merge all clouds in the project into one."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        if session.cloud_count < 2:
            raise click.UsageError("Need at least 2 clouds to merge.")
        inputs = [session.get_cloud(i)["path"] for i in range(session.cloud_count)]
        result = merge_clouds(inputs, output)
        if result["returncode"] != 0:
            raise RuntimeError(f"Merge failed:\n{result['stderr'][:500]}")
        session.record("merge_clouds", inputs, [output], {})
        if add_to_project and result.get("exists"):
            session.add_cloud(output, "merged")
        session.save()
        _out(ctx, {
            "inputs": inputs,
            "output": output,
            "exists": result.get("exists", False),
            "file_size": result.get("file_size", 0),
        })
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@cloud.command("convert")
@click.argument("input_file")
@click.argument("output_file")
@click.pass_context
def cloud_convert(ctx: click.Context, input_file: str, output_file: str) -> None:
    """Convert a cloud from one format to another (format from extension)."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        result = convert_format(input_file, output_file)
        if result["returncode"] != 0:
            raise RuntimeError(f"Convert failed:\n{result['stderr'][:500]}")
        _out(ctx, {
            "input": input_file,
            "output": output_file,
            "exists": result.get("exists", False),
            "file_size": result.get("file_size", 0),
        })
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


# ── distance group ────────────────────────────────────────────────────────────

@cli.group()
def distance() -> None:
    """Distance computation between clouds and meshes."""


@distance.command("c2c")
@click.option("--compare", required=True, help="Index of cloud to compare (gets distance SF).")
@click.option("--reference", required=True, help="Index of reference cloud.")
@click.option("--output", "-o", required=True, help="Output cloud file path.")
@click.option("--split-xyz", is_flag=True, default=False, help="Split into X/Y/Z components.")
@click.option("--octree-level", type=int, default=10, help="Octree level for computation.")
@click.option("--add-to-project", is_flag=True, default=False)
@click.pass_context
def distance_c2c(
    ctx: click.Context,
    compare: str,
    reference: str,
    output: str,
    split_xyz: bool,
    octree_level: int,
    add_to_project: bool,
) -> None:
    """Compute cloud-to-cloud distances. Adds distance SF to compared cloud."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        compare_entry = session.get_cloud(int(compare))
        ref_entry = session.get_cloud(int(reference))
        result = compute_c2c_distances(
            compare_entry["path"], ref_entry["path"], output, split_xyz, octree_level
        )
        if result["returncode"] != 0:
            raise RuntimeError(f"C2C distance failed:\n{result['stderr'][:500]}")
        session.record("c2c_dist", [compare_entry["path"], ref_entry["path"]], [output], {
            "split_xyz": split_xyz, "octree_level": octree_level,
        })
        if add_to_project and result.get("exists"):
            session.add_cloud(output, f"{compare_entry['label']}_c2c")
        session.save()
        _out(ctx, {
            "compare": compare_entry["path"],
            "reference": ref_entry["path"],
            "output": output,
            "exists": result.get("exists", False),
            "file_size": result.get("file_size", 0),
        })
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@distance.command("c2m")
@click.option("--cloud", "cloud_idx", type=int, required=True, help="Cloud index.")
@click.option("--mesh", "mesh_idx", type=int, required=True, help="Mesh index.")
@click.option("--output", "-o", required=True, help="Output cloud file path.")
@click.option("--flip-normals", is_flag=True, default=False)
@click.option("--unsigned", is_flag=True, default=False)
@click.option("--add-to-project", is_flag=True, default=False)
@click.pass_context
def distance_c2m(
    ctx: click.Context,
    cloud_idx: int,
    mesh_idx: int,
    output: str,
    flip_normals: bool,
    unsigned: bool,
    add_to_project: bool,
) -> None:
    """Compute cloud-to-mesh distances. Adds distance SF to the cloud."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        cloud_entry = session.get_cloud(cloud_idx)
        mesh_entry = session.get_mesh(mesh_idx)
        result = compute_c2m_distances(
            cloud_entry["path"], mesh_entry["path"], output, flip_normals, unsigned
        )
        if result["returncode"] != 0:
            raise RuntimeError(f"C2M distance failed:\n{result['stderr'][:500]}")
        session.record("c2m_dist", [cloud_entry["path"], mesh_entry["path"]], [output], {
            "flip_normals": flip_normals, "unsigned": unsigned,
        })
        if add_to_project and result.get("exists"):
            session.add_cloud(output, f"{cloud_entry['label']}_c2m")
        session.save()
        _out(ctx, {
            "cloud": cloud_entry["path"],
            "mesh": mesh_entry["path"],
            "output": output,
            "exists": result.get("exists", False),
            "file_size": result.get("file_size", 0),
        })
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


# ── transform group ───────────────────────────────────────────────────────────

@cli.group()
def transform() -> None:
    """Transformations and registration (ICP, match-centers)."""


@transform.command("icp")
@click.option("--aligned", type=int, required=True, help="Index of cloud to align.")
@click.option("--reference", type=int, required=True, help="Index of reference cloud.")
@click.option("--output", "-o", required=True, help="Output aligned cloud path.")
@click.option("--max-iter", type=int, default=100, help="Maximum ICP iterations.")
@click.option("--min-error-diff", type=float, default=1e-6)
@click.option("--overlap", type=float, default=100.0, help="Overlap percentage (0-100).")
@click.option("--add-to-project", is_flag=True, default=False)
@click.pass_context
def transform_icp(
    ctx: click.Context,
    aligned: int,
    reference: int,
    output: str,
    max_iter: int,
    min_error_diff: float,
    overlap: float,
    add_to_project: bool,
) -> None:
    """Run ICP registration to align one cloud to another."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        aligned_entry = session.get_cloud(aligned)
        ref_entry = session.get_cloud(reference)
        result = run_icp(
            aligned_entry["path"], ref_entry["path"], output,
            max_iter, min_error_diff, overlap
        )
        if result["returncode"] != 0:
            raise RuntimeError(f"ICP failed:\n{result['stderr'][:500]}")
        session.record("icp", [aligned_entry["path"], ref_entry["path"]], [output], {
            "max_iter": max_iter, "overlap": overlap,
        })
        if add_to_project and result.get("exists"):
            session.add_cloud(output, f"{aligned_entry['label']}_icp")
        session.save()
        _out(ctx, {
            "aligned": aligned_entry["path"],
            "reference": ref_entry["path"],
            "output": output,
            "exists": result.get("exists", False),
            "file_size": result.get("file_size", 0),
        })
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@transform.command("apply")
@click.argument("cloud_index", type=int)
@click.option("--output", "-o", required=True, help="Output transformed cloud.")
@click.option("--matrix", "-m", required=True,
              help="Path to 4×4 transformation matrix text file.")
@click.option("--inverse", is_flag=True, default=False,
              help="Apply the inverse of the matrix.")
@click.option("--add-to-project", is_flag=True, default=False)
@click.pass_context
def transform_apply(
    ctx: click.Context,
    cloud_index: int,
    output: str,
    matrix: str,
    inverse: bool,
    add_to_project: bool,
) -> None:
    """Apply a 4×4 rigid-body transformation matrix to a cloud.

    The matrix file must contain 4 rows of 4 space-separated values.

    Example identity matrix file::

        1 0 0 0
        0 1 0 0
        0 0 1 0
        0 0 0 1
    """
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        cloud_entry = session.get_cloud(cloud_index)
        result = apply_transform(cloud_entry["path"], output, matrix, inverse)
        if result["returncode"] != 0:
            raise RuntimeError(f"Apply transform failed:\n{result['stderr'][:500]}")
        session.record("apply_transform", [cloud_entry["path"]], [output],
                       {"matrix": matrix, "inverse": inverse})
        if add_to_project and result.get("exists"):
            session.add_cloud(output, f"{cloud_entry['label']}_transformed")
        session.save()
        _out(ctx, {"input": cloud_entry["path"], "matrix": matrix, "inverse": inverse,
                   "output": output, "exists": result.get("exists", False),
                   "file_size": result.get("file_size", 0)})
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


# ── mesh group ────────────────────────────────────────────────────────────────

@cli.group()
def mesh() -> None:
    """Mesh operations (add, convert, export)."""


@mesh.command("add")
@click.argument("mesh_file")
@click.option("--label", "-l", default=None)
@click.pass_context
def mesh_add(ctx: click.Context, mesh_file: str, label: Optional[str]) -> None:
    """Add a mesh file to the project."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        entry = session.add_mesh(mesh_file, label)
        session.save()
        _out(ctx, {"added": entry, "mesh_count": session.mesh_count})
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@mesh.command("list")
@click.pass_context
def mesh_list(ctx: click.Context) -> None:
    """List all meshes in the project."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        meshes = session.info()["meshes"]
        _out(ctx, {"meshes": meshes, "count": len(meshes)})
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@mesh.command("sample")
@click.argument("mesh_index", type=int)
@click.option("--output", "-o", required=True, help="Output sampled point cloud.")
@click.option("--count", "-n", type=int, default=10000,
              help="Number of points to sample from the mesh surface.")
@click.option("--add-to-project", is_flag=True, default=False)
@click.pass_context
def mesh_sample(
    ctx: click.Context,
    mesh_index: int,
    output: str,
    count: int,
    add_to_project: bool,
) -> None:
    """Sample a point cloud from a mesh surface."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        mesh_entry = session.get_mesh(mesh_index)
        result = sample_mesh(mesh_entry["path"], output, count)
        if result["returncode"] != 0:
            raise RuntimeError(f"Sample mesh failed:\n{result['stderr'][:500]}")
        session.record("sample_mesh", [mesh_entry["path"]], [output], {"count": count})
        if add_to_project and result.get("exists"):
            session.add_cloud(output, f"{mesh_entry['label']}_sampled")
        session.save()
        _out(ctx, {"mesh": mesh_entry["path"], "output": output, "count": count,
                   "exists": result.get("exists", False), "file_size": result.get("file_size", 0)})
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


# ── export group ──────────────────────────────────────────────────────────────

@cli.group()
def export() -> None:
    """Export clouds and meshes to various formats."""


@export.command("cloud")
@click.argument("cloud_index", type=int)
@click.argument("output_path")
@click.option("--preset", "-f", default=None,
              help=f"Format preset: {', '.join(CLOUD_PRESETS)}.")
@click.option("--overwrite", is_flag=True, default=False)
@click.pass_context
def export_cloud_cmd(
    ctx: click.Context,
    cloud_index: int,
    output_path: str,
    preset: Optional[str],
    overwrite: bool,
) -> None:
    """Export a cloud to a target format using CloudCompare."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        cloud_entry = session.get_cloud(cloud_index)
        result = export_cloud(cloud_entry["path"], output_path, preset=preset, overwrite=overwrite)
        session.record("export_cloud", [cloud_entry["path"]], [result["output"]], {
            "format": result["format"],
        })
        session.save()
        _out(ctx, result)
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@export.command("mesh")
@click.argument("mesh_index", type=int)
@click.argument("output_path")
@click.option("--preset", "-f", default=None,
              help=f"Format preset: {', '.join(MESH_PRESETS)}.")
@click.option("--overwrite", is_flag=True, default=False)
@click.pass_context
def export_mesh_cmd(
    ctx: click.Context,
    mesh_index: int,
    output_path: str,
    preset: Optional[str],
    overwrite: bool,
) -> None:
    """Export a mesh to a target format using CloudCompare."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        mesh_entry = session.get_mesh(mesh_index)
        result = export_mesh(mesh_entry["path"], output_path, preset=preset, overwrite=overwrite)
        session.record("export_mesh", [mesh_entry["path"]], [result["output"]], {
            "format": result["format"],
        })
        session.save()
        _out(ctx, result)
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@export.command("batch")
@click.option("--output-dir", "-d", required=True, help="Output directory.")
@click.option("--preset", "-f", default="las", help="Format preset for all outputs.")
@click.option("--overwrite", is_flag=True, default=False)
@click.pass_context
def export_batch(ctx: click.Context, output_dir: str, preset: str, overwrite: bool) -> None:
    """Batch export all project clouds to a directory."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        inputs = [session.get_cloud(i)["path"] for i in range(session.cloud_count)]
        results = batch_export(inputs, output_dir, preset=preset, overwrite=overwrite)
        _out(ctx, {"results": results, "count": len(results)})
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@export.command("formats")
@click.pass_context
def export_formats(ctx: click.Context) -> None:
    """List all available export format presets."""
    _out(ctx, list_presets())


# ── session group ─────────────────────────────────────────────────────────────

@cli.group("session")
def session_group() -> None:
    """Session management (save, history, status)."""


@session_group.command("save")
@click.pass_context
def session_save(ctx: click.Context) -> None:
    """Save the current project to disk."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        session.save()
        _out(ctx, {"saved": path, "status": "ok"})
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@session_group.command("history")
@click.option("--last", "-n", type=int, default=10, help="Number of recent entries.")
@click.pass_context
def session_history(ctx: click.Context, last: int) -> None:
    """Show recent operation history."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        hist = session.history(last)
        _out(ctx, {"history": hist, "count": len(hist)})
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@session_group.command("undo")
@click.pass_context
def session_undo(ctx: click.Context) -> None:
    """Remove the last operation from history (soft undo)."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        removed = session.undo_last()
        session.save()
        if removed:
            _out(ctx, {"undone": removed})
        else:
            _out(ctx, {"status": "nothing_to_undo"})
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


@session_group.command("set-format")
@click.option("--cloud-fmt", default=None, help="Cloud export format (e.g. LAS, PLY).")
@click.option("--cloud-ext", default=None, help="Cloud file extension (e.g. las, ply).")
@click.option("--mesh-fmt", default=None, help="Mesh export format (e.g. OBJ, STL).")
@click.option("--mesh-ext", default=None, help="Mesh file extension.")
@click.pass_context
def session_set_format(
    ctx: click.Context,
    cloud_fmt: Optional[str],
    cloud_ext: Optional[str],
    mesh_fmt: Optional[str],
    mesh_ext: Optional[str],
) -> None:
    """Update default export format settings."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    try:
        session, path = _require_project(ctx)
        session.set_export_format(cloud_fmt, cloud_ext, mesh_fmt, mesh_ext)
        session.save()
        _out(ctx, {"settings": session.get_settings()})
    except Exception as e:
        _error(str(e), json_mode)
        sys.exit(1)


# ── info command ──────────────────────────────────────────────────────────────

@cli.command("info")
@click.pass_context
def info_cmd(ctx: click.Context) -> None:
    """Show CloudCompare installation info."""
    json_mode = ctx.obj.get("json", False) if ctx.obj else False
    available = is_available()
    try:
        cmd = find_cloudcompare() if available else []
    except RuntimeError:
        cmd = []
    version = get_version() if available else None
    _out(ctx, {
        "cloudcompare_available": available,
        "command": cmd,
        "version": version,
        "supported_cloud_formats": list(CLOUD_PRESETS.keys()),
        "supported_mesh_formats": list(MESH_PRESETS.keys()),
    })


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
