"""Click CLI for WaveTone 2.61."""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any

import click

from cli_anything.wavetone import __version__
from cli_anything.wavetone.core.audio import probe_audio
from cli_anything.wavetone.core.project import (
    DEFAULT_ANALYSIS_SETTINGS,
    add_label,
    create_project,
    load_project,
    project_summary,
    save_project,
    set_tempo,
    set_wfd_path,
    update_analysis,
)
from cli_anything.wavetone.core.session import append_event, load_events
from cli_anything.wavetone.utils import wavetone_backend
from cli_anything.wavetone.utils.repl_skin import ReplSkin


def emit(data: dict[str, Any], json_mode: bool) -> None:
    if json_mode:
        click.echo(json.dumps(data, indent=2, sort_keys=True))
        return
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            click.echo(f"{key}: {json.dumps(value, sort_keys=True)}")
        else:
            click.echo(f"{key}: {value}")


def ctx_json(ctx: click.Context) -> bool:
    return bool(ctx.obj and ctx.obj.get("json"))


def ctx_project(ctx: click.Context) -> Path | None:
    value = ctx.obj.get("project") if ctx.obj else None
    return Path(value).expanduser().resolve() if value else None


def load_ctx_project(ctx: click.Context, explicit_path: str | Path | None = None) -> tuple[dict[str, Any], Path]:
    path = Path(explicit_path).expanduser().resolve() if explicit_path else ctx_project(ctx)
    if not path:
        raise click.ClickException("Project path required. Use --project PATH or pass a project argument.")
    return load_project(path), path


def _strip_matching_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _split_repl_args(line: str) -> list[str]:
    return [_strip_matching_quotes(arg) for arg in shlex.split(line, posix=False)]


@click.group(invoke_without_command=True)
@click.option("--project", "project_path", type=click.Path(dir_okay=False), help="WaveTone project JSON path.")
@click.option("--json", "json_mode", is_flag=True, help="Emit machine-readable JSON.")
@click.version_option(version=__version__, prog_name="cli-anything-wavetone")
@click.pass_context
def cli(ctx: click.Context, project_path: str | None, json_mode: bool) -> None:
    """Agent-native CLI harness for WaveTone 2.61."""
    ctx.ensure_object(dict)
    if project_path is not None:
        ctx.obj["project"] = project_path
    else:
        ctx.obj.setdefault("project", None)
    if json_mode:
        ctx.obj["json"] = True
    else:
        ctx.obj.setdefault("json", False)
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.command()
@click.pass_context
def repl(ctx: click.Context) -> None:
    """Start an interactive command loop."""
    skin = ReplSkin("WaveTone", version=__version__)
    skin.print_banner()
    skin.info("Type 'help' for commands, 'exit' to quit.")
    prompt_session = skin.create_prompt_session()
    while True:
        try:
            line = skin.get_input(prompt_session, project_name="wavetone", modified=False)
        except (EOFError, KeyboardInterrupt):
            break
        line = line.strip()
        if not line:
            continue
        if line in {"exit", "quit"}:
            break
        if line == "help":
            click.echo(cli.get_help(ctx))
            continue
        try:
            args = _split_repl_args(line)
            cli.main(args=args, prog_name="cli-anything-wavetone", standalone_mode=False, obj=ctx.obj)
        except click.ClickException as exc:  # pragma: no cover
            skin.error(exc.format_message())
        except click.exceptions.Exit as exc:  # pragma: no cover
            if exc.exit_code not in (0, None):
                skin.error(f"Command exited with code {exc.exit_code}")
        except Exception as exc:  # pragma: no cover
            skin.error(f"Unexpected error: {exc}")
    skin.print_goodbye()


@cli.group(name="project")
def project_group() -> None:
    """Create and edit WaveTone project manifests."""


@project_group.command("new")
@click.argument("audio_path", type=click.Path(exists=True, dir_okay=False))
@click.option("-o", "--output", "output_path", type=click.Path(dir_okay=False), required=True)
@click.option("--name", help="Project name. Defaults to the audio file stem.")
@click.pass_context
def project_new(ctx: click.Context, audio_path: str, output_path: str, name: str | None) -> None:
    """Create a WaveTone project manifest for an audio file."""
    try:
        project = create_project(audio_path, name=name)
        path = save_project(project, output_path)
    except (OSError, RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    emit({"ok": True, "project_path": str(path), "project": project_summary(project)}, ctx_json(ctx))


@project_group.command("info")
@click.argument("project_path", required=False, type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def project_info(ctx: click.Context, project_path: str | None) -> None:
    """Inspect a WaveTone project manifest."""
    try:
        project, path = load_ctx_project(ctx, project_path)
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    emit({"ok": True, "project_path": str(path), "project": project_summary(project)}, ctx_json(ctx))


@project_group.command("add-label")
@click.argument("name")
@click.option("--time", "time_seconds", type=float, required=True, help="Label time in seconds.")
@click.option("--note", help="Optional label note.")
@click.argument("project_path", required=False, type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def project_add_label(ctx: click.Context, name: str, time_seconds: float, note: str | None, project_path: str | None) -> None:
    """Add a navigation label to the manifest."""
    try:
        project, path = load_ctx_project(ctx, project_path)
        add_label(project, name=name, time_seconds=time_seconds, note=note)
        save_project(project, path)
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    emit({"ok": True, "project_path": str(path), "labels": project.get("labels", [])}, ctx_json(ctx))


@project_group.command("set-tempo")
@click.option("--bpm", type=float, required=True)
@click.option("--first-bar", "first_bar_time_seconds", type=float, default=0.0, show_default=True)
@click.option("--meter", default="4/4", show_default=True)
@click.argument("project_path", required=False, type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def project_set_tempo(ctx: click.Context, bpm: float, first_bar_time_seconds: float, meter: str, project_path: str | None) -> None:
    """Set the tempo plan WaveTone should use before chord or note work."""
    try:
        project, path = load_ctx_project(ctx, project_path)
        set_tempo(project, bpm=bpm, first_bar_time_seconds=first_bar_time_seconds, meter=meter)
        save_project(project, path)
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    emit({"ok": True, "project_path": str(path), "tempo": project.get("tempo")}, ctx_json(ctx))


@project_group.command("analysis")
@click.option("--blocks-per-second", type=int)
@click.option("--blocks-per-semitone", type=int)
@click.option("--note-range")
@click.option("--reference-frequency-hz", type=float)
@click.option("--channel", type=click.Choice(["Stereo", "L-R", "L+R", "L", "R"]))
@click.option("--fundamental", "fundamental", flag_value=True, default=None)
@click.option("--no-fundamental", "fundamental", flag_value=False, default=None)
@click.option("--skip-dialog", "skip_dialog", flag_value=True, default=None)
@click.option("--show-dialog", "skip_dialog", flag_value=False, default=None)
@click.argument("project_path", required=False, type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def project_analysis(
    ctx: click.Context,
    blocks_per_second: int | None,
    blocks_per_semitone: int | None,
    note_range: str | None,
    reference_frequency_hz: float | None,
    channel: str | None,
    fundamental: bool | None,
    skip_dialog: bool | None,
    project_path: str | None,
) -> None:
    """Update intended WaveTone analysis settings."""
    try:
        project, path = load_ctx_project(ctx, project_path)
        update_analysis(
            project,
            blocks_per_second=blocks_per_second,
            blocks_per_semitone=blocks_per_semitone,
            note_range=note_range,
            reference_frequency_hz=reference_frequency_hz,
            channel=channel,
            analyze_fundamental_frequency=fundamental,
            skip_analysis_dialog=skip_dialog,
        )
        save_project(project, path)
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    emit({"ok": True, "project_path": str(path), "analysis": project.get("analysis")}, ctx_json(ctx))


@project_group.command("attach-wfd")
@click.argument("wfd_path", type=click.Path(exists=True, dir_okay=False))
@click.argument("project_path", required=False, type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def project_attach_wfd(ctx: click.Context, wfd_path: str, project_path: str | None) -> None:
    """Attach a WFD analysis file saved by WaveTone."""
    try:
        if Path(wfd_path).suffix.lower() != ".wfd":
            raise ValueError("WFD path must use the .wfd extension")
        project, path = load_ctx_project(ctx, project_path)
        set_wfd_path(project, wfd_path)
        save_project(project, path)
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    emit({"ok": True, "project_path": str(path), "wfd_path": project.get("wfd_path")}, ctx_json(ctx))


@cli.group(name="audio")
def audio_group() -> None:
    """Probe audio files before opening them in WaveTone."""


@audio_group.command("probe")
@click.argument("audio_path", required=False, type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def audio_probe(ctx: click.Context, audio_path: str | None) -> None:
    """Return duration, sample rate, channel, codec, and size metadata."""
    try:
        if audio_path:
            target = audio_path
        else:
            project, _ = load_ctx_project(ctx)
            target = project["audio"]["path"]
        data = probe_audio(target)
    except (OSError, ValueError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc
    emit({"ok": True, "audio": data}, ctx_json(ctx))


@cli.group(name="wavetone")
def wavetone_group() -> None:
    """Inspect and launch the real WaveTone executable."""


@wavetone_group.command("doctor")
@click.option("--exe", "executable", type=click.Path(dir_okay=False), help="Path to wavetone.exe.")
@click.pass_context
def wavetone_doctor(ctx: click.Context, executable: str | None) -> None:
    """Check whether WaveTone and its bundled decoder files are available."""
    data = wavetone_backend.doctor(executable)
    emit(data, ctx_json(ctx))
    if not data.get("ready"):
        raise click.exceptions.Exit(1)


@wavetone_group.command("formats")
@click.pass_context
def wavetone_formats(ctx: click.Context) -> None:
    """List audio formats documented by WaveTone 2.61."""
    emit({"ok": True, "formats": wavetone_backend.supported_formats()}, ctx_json(ctx))


@wavetone_group.command("launch")
@click.argument("audio_path", required=False, type=click.Path(exists=True, dir_okay=False))
@click.option("--exe", "executable", type=click.Path(dir_okay=False), help="Path to wavetone.exe.")
@click.option("--wait", "wait_seconds", type=float, default=0.0, show_default=True)
@click.option("--terminate", is_flag=True, help="Terminate after the wait period, useful for smoke tests.")
@click.pass_context
def wavetone_launch(ctx: click.Context, audio_path: str | None, executable: str | None, wait_seconds: float, terminate: bool) -> None:
    """Launch the real WaveTone GUI, optionally with an audio file."""
    try:
        target = audio_path
        if not target:
            project_path = ctx_project(ctx)
            if project_path:
                project = load_project(project_path)
                target = project["audio"]["path"]
        data = wavetone_backend.launch_wavetone(
            audio_path=target,
            executable=executable,
            wait_seconds=wait_seconds,
            terminate=terminate,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    failed_launch = (
        wait_seconds > 0
        and not data.get("running_after_wait")
        and not data.get("terminated")
        and data.get("exit_code") not in (None, 0)
    )
    emit({"ok": not failed_launch, "launch": data}, ctx_json(ctx))
    if failed_launch:
        raise click.exceptions.Exit(int(data.get("exit_code") or 1))


@cli.group(name="session")
def session_group() -> None:
    """Record lightweight CLI session events."""


@session_group.command("record")
@click.argument("session_path", type=click.Path(dir_okay=False))
@click.argument("event")
@click.option("--payload", default="{}", help="JSON object payload.")
@click.pass_context
def session_record(ctx: click.Context, session_path: str, event: str, payload: str) -> None:
    """Append an event to a session log."""
    try:
        payload_data = json.loads(payload)
        if not isinstance(payload_data, dict):
            raise ValueError("Payload must be a JSON object")
        record = append_event(session_path, event, payload_data)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise click.ClickException(str(exc)) from exc
    emit({"ok": True, "event": record}, ctx_json(ctx))


@session_group.command("events")
@click.argument("session_path", type=click.Path(dir_okay=False))
@click.pass_context
def session_events(ctx: click.Context, session_path: str) -> None:
    """List session events."""
    try:
        events = load_events(session_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise click.ClickException(str(exc)) from exc
    emit({"ok": True, "events": events}, ctx_json(ctx))


@cli.command("defaults")
@click.pass_context
def defaults(ctx: click.Context) -> None:
    """Show default WaveTone analysis settings used in new manifests."""
    emit({"ok": True, "analysis_defaults": DEFAULT_ANALYSIS_SETTINGS}, ctx_json(ctx))


def main() -> None:
    cli(obj={})


if __name__ == "__main__":
    main()
