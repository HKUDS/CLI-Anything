"""cli-anything-cloudanalyzer — Command-line harness for CloudAnalyzer.

CloudAnalyzer is a QA platform for mapping, localization, and perception
point cloud outputs.  This CLI wraps CloudAnalyzer's Python API with a
structured, agent-friendly interface supporting both one-shot commands
and an interactive REPL.

Usage:
    cli-anything-cloudanalyzer                               # start REPL
    cli-anything-cloudanalyzer --json evaluate run s.pcd r.pcd
    cli-anything-cloudanalyzer check run cloudanalyzer.yaml
    cli-anything-cloudanalyzer --json baseline decision qa/s.json --history-dir qa/history/

Backend: CloudAnalyzer Python package (direct import, no subprocess)
"""

import json
import shlex
from pathlib import Path
from typing import Optional

import click

from cli_anything.cloudanalyzer.core.project import create_project
from cli_anything.cloudanalyzer.core.session import Session
from cli_anything.cloudanalyzer.utils import ca_backend
from cli_anything.cloudanalyzer.utils.repl_skin import ReplSkin

VERSION = "1.0.0"

# ── Output helpers ────────────────────────────────────────────────────────────

def _out(ctx: click.Context, data: dict | list) -> None:
    """Print data as JSON or human-readable."""
    if ctx.obj and ctx.obj.get("json"):
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        _pretty(data)


def _pretty(data, indent: int = 0) -> None:
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


# ── Root CLI ──────────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("-p", "--project", default=None, help="Path to project JSON file")
@click.option("--json", "json_mode", is_flag=True, help="Output as JSON")
@click.version_option(VERSION, prog_name="cli-anything-cloudanalyzer")
@click.pass_context
def cli(ctx: click.Context, project: Optional[str], json_mode: bool) -> None:
    """CloudAnalyzer — Agent-friendly QA platform for point cloud outputs."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_mode
    ctx.obj["project"] = project
    if ctx.invoked_subcommand is None:
        _start_repl(ctx)


# ── evaluate group ────────────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def evaluate(ctx: click.Context) -> None:
    """Point cloud evaluation commands."""


@evaluate.command("run")
@click.argument("source")
@click.argument("reference")
@click.option("--plot", default=None, help="Save F1 curve plot")
@click.option("--threshold", type=float, default=None)
@click.pass_context
def evaluate_run(ctx: click.Context, source: str, reference: str, plot: Optional[str], threshold: Optional[float]) -> None:
    """Evaluate a point cloud against a reference."""
    try:
        kwargs = {}
        if threshold is not None:
            kwargs["thresholds"] = [threshold]
        if plot:
            kwargs["plot"] = plot
        result = ca_backend.evaluate(source, reference, **kwargs)
        _out(ctx, result)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


@evaluate.command("compare")
@click.argument("source")
@click.argument("target")
@click.option("--register", default="gicp", help="Registration method")
@click.pass_context
def evaluate_compare(ctx: click.Context, source: str, target: str, register: str) -> None:
    """Compare two point clouds with optional registration."""
    try:
        result = ca_backend.compare(source, target, method=register)
        _out(ctx, result)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


@evaluate.command("diff")
@click.argument("source")
@click.argument("target")
@click.option("--threshold", type=float, default=None)
@click.pass_context
def evaluate_diff(ctx: click.Context, source: str, target: str, threshold: Optional[float]) -> None:
    """Quick distance statistics."""
    try:
        result = ca_backend.diff(source, target, threshold=threshold)
        _out(ctx, result)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


@evaluate.command("ground")
@click.argument("estimated_ground")
@click.argument("estimated_nonground")
@click.argument("reference_ground")
@click.argument("reference_nonground")
@click.option("--voxel-size", type=float, default=0.2)
@click.option("--min-precision", type=float, default=None)
@click.option("--min-recall", type=float, default=None)
@click.option("--min-f1", type=float, default=None)
@click.option("--min-iou", type=float, default=None)
@click.pass_context
def evaluate_ground(
    ctx: click.Context,
    estimated_ground: str, estimated_nonground: str,
    reference_ground: str, reference_nonground: str,
    voxel_size: float,
    min_precision: Optional[float], min_recall: Optional[float],
    min_f1: Optional[float], min_iou: Optional[float],
) -> None:
    """Evaluate ground segmentation quality."""
    try:
        result = ca_backend.evaluate_ground(
            estimated_ground, estimated_nonground,
            reference_ground, reference_nonground,
            voxel_size=voxel_size,
            min_precision=min_precision, min_recall=min_recall,
            min_f1=min_f1, min_iou=min_iou,
        )
        _out(ctx, result)
        if result.get("quality_gate") and not result["quality_gate"]["passed"]:
            ctx.exit(1)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


@evaluate.command("batch")
@click.argument("directory")
@click.argument("reference")
@click.option("--min-auc", type=float, default=None)
@click.option("--max-chamfer", type=float, default=None)
@click.pass_context
def evaluate_batch(ctx: click.Context, directory: str, reference: str, min_auc: Optional[float], max_chamfer: Optional[float]) -> None:
    """Batch evaluation of multiple point clouds."""
    try:
        result = ca_backend.batch_evaluate(
            directory, reference, min_auc=min_auc, max_chamfer=max_chamfer,
        )
        _out(ctx, result)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


@evaluate.command("pipeline")
@click.argument("input_path")
@click.argument("reference")
@click.option("-o", "--output", required=True)
@click.option("-v", "--voxel-size", type=float, default=0.05)
@click.pass_context
def evaluate_pipeline(
    ctx: click.Context,
    input_path: str,
    reference: str,
    output: str,
    voxel_size: float,
) -> None:
    """Filter, downsample, evaluate in one command."""
    try:
        result = ca_backend.run_pipeline(
            input_path, reference, output, voxel_size=voxel_size,
        )
        _out(ctx, result)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


# ── trajectory group ──────────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def trajectory(ctx: click.Context) -> None:
    """Trajectory evaluation commands."""


@trajectory.command("evaluate")
@click.argument("estimated")
@click.argument("reference")
@click.option("--max-ate", type=float, default=None)
@click.option("--max-rpe", type=float, default=None)
@click.option("--max-drift", type=float, default=None)
@click.option("--min-coverage", type=float, default=None)
@click.option("--max-lateral", type=float, default=None)
@click.option("--max-longitudinal", type=float, default=None)
@click.option("--align-origin", is_flag=True)
@click.option("--align-rigid", is_flag=True)
@click.pass_context
def trajectory_evaluate(
    ctx: click.Context,
    estimated: str,
    reference: str,
    max_ate: Optional[float],
    max_rpe: Optional[float],
    max_drift: Optional[float],
    min_coverage: Optional[float],
    max_lateral: Optional[float],
    max_longitudinal: Optional[float],
    align_origin: bool,
    align_rigid: bool,
) -> None:
    """Evaluate estimated vs reference trajectory."""
    try:
        result = ca_backend.evaluate_trajectory(
            estimated,
            reference,
            max_ate=max_ate,
            max_rpe=max_rpe,
            max_drift=max_drift,
            min_coverage=min_coverage,
            max_lateral=max_lateral,
            max_longitudinal=max_longitudinal,
            align_origin=align_origin,
            align_rigid=align_rigid,
        )
        _out(ctx, result)
        gate = result.get("quality_gate")
        if gate and not gate["passed"]:
            ctx.exit(1)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


@trajectory.command("batch")
@click.argument("directory")
@click.option("--reference-dir", required=True)
@click.option("--max-ate", type=float, default=None)
@click.option("--max-rpe", type=float, default=None)
@click.option("--max-drift", type=float, default=None)
@click.option("--min-coverage", type=float, default=None)
@click.pass_context
def trajectory_batch(
    ctx: click.Context,
    directory: str,
    reference_dir: str,
    max_ate: Optional[float],
    max_rpe: Optional[float],
    max_drift: Optional[float],
    min_coverage: Optional[float],
) -> None:
    """Batch trajectory evaluation."""
    try:
        result = ca_backend.trajectory_batch_evaluate(
            directory,
            reference_dir,
            max_ate=max_ate,
            max_rpe=max_rpe,
            max_drift=max_drift,
            min_coverage=min_coverage,
        )
        _out(ctx, result)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


@trajectory.command("run-evaluate")
@click.argument("map_path")
@click.argument("map_reference")
@click.argument("trajectory_path")
@click.argument("trajectory_reference")
@click.option("--min-auc", type=float, default=None)
@click.option("--max-ate", type=float, default=None)
@click.pass_context
def trajectory_run_evaluate(
    ctx: click.Context,
    map_path: str,
    map_reference: str,
    trajectory_path: str,
    trajectory_reference: str,
    min_auc: Optional[float],
    max_ate: Optional[float],
) -> None:
    """Integrated map + trajectory evaluation."""
    try:
        result = ca_backend.evaluate_run(
            map_path,
            map_reference,
            trajectory_path,
            trajectory_reference,
            min_auc=min_auc,
            max_ate=max_ate,
        )
        _out(ctx, result)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


# ── check group ───────────────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def check(ctx: click.Context) -> None:
    """Config-driven quality gate commands."""


@check.command("run")
@click.argument("config_path")
@click.option("--output-json", default=None, help="Dump summary JSON")
@click.pass_context
def check_run(ctx: click.Context, config_path: str, output_json: Optional[str]) -> None:
    """Run unified QA from a config file."""
    try:
        result = ca_backend.run_check_suite(config_path)
        if output_json:
            Path(output_json).parent.mkdir(parents=True, exist_ok=True)
            Path(output_json).write_text(json.dumps(result, indent=2), encoding="utf-8")
        _out(ctx, result)
        if not result.get("summary", {}).get("passed", True):
            ctx.exit(1)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


@check.command("init")
@click.argument("destination")
@click.option("--profile", default="integrated", help="Template profile")
@click.option("--force", is_flag=True, help="Overwrite existing file")
@click.pass_context
def check_init(ctx: click.Context, destination: str, profile: str, force: bool) -> None:
    """Generate a starter config file."""
    dest = Path(destination)
    if dest.exists() and not force:
        _error(f"File exists: {dest}. Use --force to overwrite.", ctx.obj.get("json", False))
        ctx.exit(1)
        return
    try:
        template = ca_backend.render_check_scaffold(profile=profile)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(template, encoding="utf-8")
        _out(ctx, {"created": str(dest), "profile": profile})
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


# ── baseline group ────────────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def baseline(ctx: click.Context) -> None:
    """Baseline evolution commands."""


@baseline.command("decision")
@click.argument("candidate_json")
@click.option("--history", "history_paths", multiple=True, help="History JSON files")
@click.option("--history-dir", default=None, help="Auto-discover history from directory")
@click.option("--output-json", default=None)
@click.pass_context
def baseline_decision(
    ctx: click.Context, candidate_json: str,
    history_paths: tuple[str, ...], history_dir: Optional[str], output_json: Optional[str],
) -> None:
    """Decide promote / keep / reject for a baseline."""
    try:
        paths = list(history_paths)
        if history_dir:
            paths.extend(ca_backend.baseline_discover(history_dir))
        if not paths:
            _error("Provide --history or --history-dir.", ctx.obj.get("json", False))
            ctx.exit(1)
            return
        result = ca_backend.baseline_decision(candidate_json, paths)
        if output_json:
            Path(output_json).parent.mkdir(parents=True, exist_ok=True)
            Path(output_json).write_text(json.dumps(result, indent=2), encoding="utf-8")
        _out(ctx, result)
        if result.get("decision") == "reject":
            ctx.exit(1)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


@baseline.command("save")
@click.argument("summary_json")
@click.option("--history-dir", default="qa/history", help="History directory")
@click.option("--label", default=None)
@click.option("--keep", type=int, default=None, help="Rotate to keep N baselines")
@click.pass_context
def baseline_save(
    ctx: click.Context, summary_json: str,
    history_dir: str, label: Optional[str], keep: Optional[int],
) -> None:
    """Save a QA summary to the history directory."""
    try:
        dest = ca_backend.baseline_save(summary_json, history_dir, label=label)
        data: dict = {"saved": dest}
        if keep is not None:
            removed = ca_backend.baseline_rotate(history_dir, keep=keep)
            data["rotated"] = len(removed)
        _out(ctx, data)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


@baseline.command("list")
@click.option("--history-dir", default="qa/history", help="History directory")
@click.pass_context
def baseline_list(ctx: click.Context, history_dir: str) -> None:
    """List saved baselines."""
    try:
        entries = ca_backend.baseline_list(history_dir)
        _out(ctx, entries)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


# ── process group ─────────────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def process(ctx: click.Context) -> None:
    """Point cloud processing commands."""


@process.command("downsample")
@click.argument("input_path")
@click.option("-o", "--output", required=True, help="Output file path")
@click.option("-v", "--voxel-size", type=float, required=True)
@click.pass_context
def process_downsample(ctx: click.Context, input_path: str, output: str, voxel_size: float) -> None:
    """Voxel grid downsampling."""
    try:
        result = ca_backend.downsample(input_path, output, voxel_size)
        _out(ctx, result)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


@process.command("split")
@click.argument("input_path")
@click.option("-o", "--output-dir", required=True)
@click.option("-g", "--grid-size", type=float, required=True)
@click.option("-a", "--axis", default="xy", help="Split axes (xy/xz/yz)")
@click.pass_context
def process_split(ctx: click.Context, input_path: str, output_dir: str, grid_size: float, axis: str) -> None:
    """Split point cloud into grid tiles."""
    try:
        result = ca_backend.split(input_path, output_dir, grid_size, axis=axis)
        _out(ctx, result)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


@process.command("sample")
@click.argument("input_path")
@click.option("-o", "--output", required=True)
@click.option("-n", "--num-points", type=int, required=True)
@click.pass_context
def process_sample(ctx: click.Context, input_path: str, output: str, num_points: int) -> None:
    """Random point sampling."""
    try:
        result = ca_backend.random_sample(input_path, output, num_points)
        _out(ctx, result)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


@process.command("filter")
@click.argument("input_path")
@click.option("-o", "--output", required=True)
@click.option("--nb-neighbors", type=int, default=20)
@click.option("--std-ratio", type=float, default=2.0)
@click.pass_context
def process_filter(ctx: click.Context, input_path: str, output: str, nb_neighbors: int, std_ratio: float) -> None:
    """Statistical outlier removal."""
    try:
        result = ca_backend.filter_outliers(
            input_path, output, nb_neighbors=nb_neighbors, std_ratio=std_ratio,
        )
        _out(ctx, result)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


@process.command("merge")
@click.argument("inputs", nargs=-1, required=True)
@click.option("-o", "--output", required=True)
@click.pass_context
def process_merge(ctx: click.Context, inputs: tuple[str, ...], output: str) -> None:
    """Merge multiple point clouds."""
    try:
        result = ca_backend.merge(list(inputs), output)
        _out(ctx, result)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


@process.command("convert")
@click.argument("input_path")
@click.option("-o", "--output", required=True)
@click.pass_context
def process_convert(ctx: click.Context, input_path: str, output: str) -> None:
    """Convert between point cloud formats."""
    try:
        result = ca_backend.convert(input_path, output)
        _out(ctx, result)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


# ── inspect group ─────────────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def inspect(ctx: click.Context) -> None:
    """Visualization and inspection commands."""


@inspect.command("view")
@click.argument("path")
@click.pass_context
def inspect_view(ctx: click.Context, path: str) -> None:
    """Open a point cloud viewer."""
    try:
        ca_backend.view_point_cloud(path)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


@inspect.command("web")
@click.argument("source")
@click.argument("reference", required=False, default=None)
@click.option("--heatmap", is_flag=True)
@click.option("--trajectory", default=None)
@click.option("--trajectory-reference", default=None)
@click.option("--port", type=int, default=8080)
@click.pass_context
def inspect_web(ctx: click.Context, source: str, reference: Optional[str], heatmap: bool, trajectory: Optional[str], trajectory_reference: Optional[str], port: int) -> None:
    """Interactive browser inspection."""
    try:
        ca_backend.web_serve(
            source,
            reference,
            port=port,
            heatmap=heatmap,
            trajectory=trajectory,
            trajectory_reference=trajectory_reference,
        )
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


@inspect.command("web-export")
@click.argument("source")
@click.argument("reference", required=False, default=None)
@click.option("-o", "--output", required=True)
@click.option("--heatmap", is_flag=True)
@click.option("--trajectory", default=None)
@click.option("--trajectory-reference", default=None)
@click.pass_context
def inspect_web_export(ctx: click.Context, source: str, reference: Optional[str], output: str, heatmap: bool, trajectory: Optional[str], trajectory_reference: Optional[str]) -> None:
    """Export a static HTML inspection bundle."""
    try:
        result = ca_backend.web_export_bundle(
            source, reference, output,
            heatmap=heatmap,
            trajectory=trajectory,
            trajectory_reference=trajectory_reference,
        )
        _out(ctx, result)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


# ── info group ────────────────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def info(ctx: click.Context) -> None:
    """Metadata commands."""


@info.command("show")
@click.argument("path")
@click.pass_context
def info_show(ctx: click.Context, path: str) -> None:
    """Show point cloud metadata."""
    try:
        result = ca_backend.info(path)
        _out(ctx, result)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


@info.command("version")
@click.pass_context
def info_version(ctx: click.Context) -> None:
    """Show CloudAnalyzer version."""
    try:
        ver = ca_backend.get_version()
        _out(ctx, {"cloudanalyzer_version": ver, "harness_version": VERSION})
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


# ── session group ─────────────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def session(ctx: click.Context) -> None:
    """Session management commands."""


@session.command("new")
@click.option("-o", "--output", required=True, help="Project file path")
@click.option("-n", "--name", default="untitled")
@click.pass_context
def session_new(ctx: click.Context, output: str, name: str) -> None:
    """Create a new project file."""
    try:
        create_project(output, name=name)
        _out(ctx, {"created": output, "name": name})
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


@session.command("history")
@click.option("-n", "--last", type=int, default=10)
@click.pass_context
def session_history(ctx: click.Context, last: int) -> None:
    """Show recent operation history."""
    project_path = ctx.obj.get("project")
    if not project_path:
        _error("No project specified. Use --project.", ctx.obj.get("json", False))
        ctx.exit(1)
        return
    try:
        sess = Session(project_path)
        history = sess.history[-last:]
        _out(ctx, history)
    except Exception as e:
        _error(str(e), ctx.obj.get("json", False))
        ctx.exit(1)


# ── REPL ──────────────────────────────────────────────────────────────────────

def _start_repl(ctx: click.Context) -> None:
    """Launch interactive REPL."""
    if not ca_backend.is_available():
        click.echo("Error: CloudAnalyzer is not installed. Run: pip install cloudanalyzer")
        ctx.exit(1)
        return

    skin = ReplSkin("cloudanalyzer", version=VERSION)
    skin.print_banner()

    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import FileHistory
        repl_session = PromptSession(history=FileHistory(".ca_repl_history"))
    except ImportError:
        repl_session = None

    while True:
        try:
            if repl_session:
                line = repl_session.prompt(skin.prompt())
            else:
                line = input(skin.prompt())
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

        line = line.strip()
        if not line:
            continue
        if line in ("exit", "quit", "q"):
            skin.print_goodbye()
            break

        try:
            args = shlex.split(line)
            cli.main(args, standalone_mode=False, obj=ctx.obj)
        except SystemExit:
            pass
        except ValueError as e:
            _error(f"Invalid input: {e}", ctx.obj.get("json", False))
        except Exception as e:
            _error(str(e), ctx.obj.get("json", False))


def main() -> None:
    cli(obj={})


if __name__ == "__main__":
    main()
