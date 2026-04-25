#!/usr/bin/env python3
"""OBS Studio CLI for JSON-backed scene collection workflows."""

from __future__ import annotations

import json
import sys

import click

from cli_anything.obs_studio.core import filters as filter_mod
from cli_anything.obs_studio.core import output as output_mod
from cli_anything.obs_studio.core import project as project_mod
from cli_anything.obs_studio.core import scenes as scene_mod
from cli_anything.obs_studio.core import sources as source_mod
from cli_anything.obs_studio.core.session import Session

_json_output = False
_repl_mode = False


def _emit(data, message: str | None = None) -> None:
    if _json_output:
        click.echo(json.dumps(data, indent=2))
        return
    if message:
        click.echo(message)
    if isinstance(data, dict):
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(str(data))


def _handle_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - exercised via CLI tests
            if _json_output:
                click.echo(json.dumps({"error": str(exc), "type": type(exc).__name__}))
            else:
                click.echo(f"Error: {exc}", err=True)
            if not _repl_mode:
                sys.exit(1)
        return None

    wrapper.__name__ = func.__name__
    return wrapper


def _require_project(project_path: str | None) -> Session:
    if not project_path:
        raise RuntimeError("Use --project PATH for this command")
    session = Session()
    session.open_project(project_path)
    return session


def _autosave(session: Session, project_path: str | None) -> None:
    if project_path:
        session.save_project(project_path)


@click.group(invoke_without_command=True)
@click.option("--project", type=click.Path(dir_okay=False, path_type=str), default=None)
@click.option("--json", "use_json", is_flag=True, help="Output JSON")
@click.pass_context
def cli(ctx: click.Context, project: str | None, use_json: bool) -> None:
    """OBS Studio CLI for scene collection management."""
    global _json_output
    _json_output = use_json
    ctx.ensure_object(dict)
    ctx.obj["project"] = project
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.group()
def project() -> None:
    """Project lifecycle commands."""


@project.command("new")
@click.option("--name", required=True, help="Project name")
@click.option("-o", "--output", required=True, type=click.Path(dir_okay=False, path_type=str))
@_handle_error
def project_new(name: str, output: str) -> None:
    session = Session()
    result = project_mod.new_project(session, name)
    session.save_project(output)
    result["path"] = output
    _emit(result, f"Created OBS project: {name}")


@project.command("info")
@click.pass_context
@_handle_error
def project_info(ctx: click.Context) -> None:
    session = _require_project(ctx.obj.get("project"))
    _emit(project_mod.project_info(session))


@project.command("save")
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=str), default=None)
@click.pass_context
@_handle_error
def project_save(ctx: click.Context, output: str | None) -> None:
    session = _require_project(ctx.obj.get("project"))
    _emit(project_mod.save_project(session, output or ctx.obj.get("project")))


@project.command("status")
@click.pass_context
@_handle_error
def project_status(ctx: click.Context) -> None:
    session = _require_project(ctx.obj.get("project"))
    _emit(session.status())


@cli.group()
def scene() -> None:
    """Scene management commands."""


@scene.command("add")
@click.option("--name", required=True, help="Scene name")
@click.pass_context
@_handle_error
def scene_add(ctx: click.Context, name: str) -> None:
    project_path = ctx.obj.get("project")
    session = _require_project(project_path)
    result = scene_mod.add_scene(session, name)
    _autosave(session, project_path)
    _emit(result, f"Added scene: {name}")


@scene.command("list")
@click.pass_context
@_handle_error
def scene_list(ctx: click.Context) -> None:
    session = _require_project(ctx.obj.get("project"))
    _emit(scene_mod.list_scenes(session))


@scene.command("select")
@click.option("--name", required=True, help="Scene name")
@click.pass_context
@_handle_error
def scene_select(ctx: click.Context, name: str) -> None:
    project_path = ctx.obj.get("project")
    session = _require_project(project_path)
    result = scene_mod.select_scene(session, name)
    _autosave(session, project_path)
    _emit(result, f"Selected scene: {name}")


@cli.group()
def source() -> None:
    """Source management commands."""


@source.command("add")
@click.argument("source_type")
@click.option("--name", required=True, help="Source name")
@click.option("--scene", "scene_name", default=None, help="Target scene name")
@click.option("-S", "--setting", "settings", multiple=True, help="Source setting key=value")
@click.option("--hidden", is_flag=True, help="Create source as hidden")
@click.pass_context
@_handle_error
def source_add(
    ctx: click.Context,
    source_type: str,
    name: str,
    scene_name: str | None,
    settings: tuple[str, ...],
    hidden: bool,
) -> None:
    project_path = ctx.obj.get("project")
    session = _require_project(project_path)
    result = source_mod.add_source(
        session,
        source_type=source_type,
        name=name,
        scene_name=scene_name,
        visible=not hidden,
        settings=settings,
    )
    _autosave(session, project_path)
    _emit(result, f"Added source: {name}")


@source.command("list")
@click.option("--scene", "scene_name", default=None, help="Scene name")
@click.pass_context
@_handle_error
def source_list(ctx: click.Context, scene_name: str | None) -> None:
    session = _require_project(ctx.obj.get("project"))
    _emit(source_mod.list_sources(session, scene_name=scene_name))


@cli.group()
def filter() -> None:
    """Filter management commands."""


@filter.command("add")
@click.argument("filter_type")
@click.option("-S", "--source", "source_name", required=True, help="Source name")
@click.option("--scene", "scene_name", default=None, help="Scene name")
@click.option("-p", "--param", "settings", multiple=True, help="Filter setting key=value")
@click.pass_context
@_handle_error
def filter_add(
    ctx: click.Context,
    filter_type: str,
    source_name: str,
    scene_name: str | None,
    settings: tuple[str, ...],
) -> None:
    project_path = ctx.obj.get("project")
    session = _require_project(project_path)
    result = filter_mod.add_filter(
        session,
        filter_type=filter_type,
        source_name=source_name,
        scene_name=scene_name,
        settings=settings,
    )
    _autosave(session, project_path)
    _emit(result, f"Added filter {filter_type} to {source_name}")


@filter.command("list")
@click.option("-S", "--source", "source_name", required=True, help="Source name")
@click.option("--scene", "scene_name", default=None, help="Scene name")
@click.pass_context
@_handle_error
def filter_list(ctx: click.Context, source_name: str, scene_name: str | None) -> None:
    session = _require_project(ctx.obj.get("project"))
    _emit(filter_mod.list_filters(session, source_name=source_name, scene_name=scene_name))


@cli.group()
def output() -> None:
    """Streaming and recording settings."""


@output.command("streaming")
@click.option("--service", required=True, help="Streaming service")
@click.option("--key", required=True, help="Stream key")
@click.option("--server", default="auto", help="Streaming server")
@click.pass_context
@_handle_error
def output_streaming(ctx: click.Context, service: str, key: str, server: str) -> None:
    project_path = ctx.obj.get("project")
    session = _require_project(project_path)
    result = output_mod.configure_streaming(session, service=service, key=key, server=server)
    _autosave(session, project_path)
    _emit(result)


@output.command("recording")
@click.option("--path", default=None, help="Recording directory")
@click.option("--format", "format_name", default="mkv", help="Recording format")
@click.option("--quality", default="high", help="Recording quality")
@click.pass_context
@_handle_error
def output_recording(
    ctx: click.Context, path: str | None, format_name: str, quality: str
) -> None:
    project_path = ctx.obj.get("project")
    session = _require_project(project_path)
    result = output_mod.configure_recording(
        session, path=path, format_name=format_name, quality=quality
    )
    _autosave(session, project_path)
    _emit(result)


@output.command("settings")
@click.option("--preset", default=None)
@click.option("--fps", type=int, default=None)
@click.option("--output-width", type=int, default=None)
@click.option("--output-height", type=int, default=None)
@click.option("--video-bitrate", type=int, default=None)
@click.option("--audio-bitrate", type=int, default=None)
@click.option("--encoder", default=None)
@click.pass_context
@_handle_error
def output_settings(
    ctx: click.Context,
    preset: str | None,
    fps: int | None,
    output_width: int | None,
    output_height: int | None,
    video_bitrate: int | None,
    audio_bitrate: int | None,
    encoder: str | None,
) -> None:
    project_path = ctx.obj.get("project")
    session = _require_project(project_path)
    result = output_mod.configure_output_settings(
        session,
        preset=preset,
        fps=fps,
        output_width=output_width,
        output_height=output_height,
        video_bitrate=video_bitrate,
        audio_bitrate=audio_bitrate,
        encoder=encoder,
    )
    _autosave(session, project_path)
    _emit(result)


@cli.command("export")
@click.option("-o", "--output", required=True, type=click.Path(dir_okay=False, path_type=str),
              help="Output path for OBS-native JSON")
@click.pass_context
@_handle_error
def export_obs_native(ctx: click.Context, output: str) -> None:
    """Export project to OBS Studio native scene collection format."""
    from cli_anything.obs_studio.core.export_obs import export_to_obs
    session = _require_project(ctx.obj.get("project"))
    result = export_to_obs(session.state, output)
    _emit({"action": "export", "path": result}, f"Exported OBS-native scene collection to: {result}")


@cli.command()
def repl() -> None:
    """Minimal interactive shell."""
    global _repl_mode
    _repl_mode = True
    click.echo("OBS Studio REPL is not fully interactive yet. Use subcommands with --help.")


def main() -> None:
    cli(obj={})

