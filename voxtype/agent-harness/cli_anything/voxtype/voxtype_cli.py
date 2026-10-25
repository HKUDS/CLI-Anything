#!/usr/bin/env python3
"""Voxtype CLI — agent-friendly control of the voxtype voice-to-text daemon.

Wraps the real `voxtype` binary: configuration (validated by voxtype itself,
with undo/redo), file transcription, meeting transcripts, daemon/recording
control, and install introspection.

Usage:
    # One-shot commands
    cli-anything-voxtype --json info engines
    cli-anything-voxtype transcribe file speech.wav
    cli-anything-voxtype --project ws.json config set text.spoken_punctuation true
    cli-anything-voxtype --project ws.json session undo

    # Interactive REPL
    cli-anything-voxtype
"""

import json
import os
import shlex
import sys

import click

from cli_anything.voxtype import __version__
from cli_anything.voxtype.core import config as config_mod
from cli_anything.voxtype.core import daemon as daemon_mod
from cli_anything.voxtype.core import meeting as meeting_mod
from cli_anything.voxtype.core import project as project_mod
from cli_anything.voxtype.core import system as system_mod
from cli_anything.voxtype.core import transcribe as transcribe_mod
from cli_anything.voxtype.core.session import Session
from cli_anything.voxtype.utils.voxtype_backend import VoxtypeError

# Global state
_json_output = False
_repl_mode = False
_dry_run = False
_session: Session | None = None


def get_session() -> Session:
    global _session
    if _session is None:
        _session = Session()
    return _session


def output(data, message: str = ""):
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        if isinstance(data, dict):
            _print_dict(data)
        elif isinstance(data, list):
            _print_list(data)
        elif data is not None:
            click.echo(str(data))


def _print_dict(d: dict, indent: int = 0):
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            click.echo(f"{prefix}{k}:")
            _print_dict(v, indent + 1)
        elif isinstance(v, list):
            click.echo(f"{prefix}{k}:")
            _print_list(v, indent + 1)
        else:
            click.echo(f"{prefix}{k}: {v}")


def _print_list(items: list, indent: int = 0):
    prefix = "  " * indent
    for i, item in enumerate(items):
        if isinstance(item, dict):
            click.echo(f"{prefix}[{i}]")
            _print_dict(item, indent + 1)
        else:
            click.echo(f"{prefix}- {item}")


def report(data, message: str):
    """JSON mode: the full record. Human mode: just the one-line message."""
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo(message)


def _fail(err: dict, code: int = 1):
    if _json_output:
        click.echo(json.dumps(err))
    else:
        click.echo(f"Error: {err['error']}", err=True)
    if not _repl_mode:
        sys.exit(code)


def handle_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except VoxtypeError as e:
            _fail({"error": str(e), "type": "voxtype_error", "returncode": e.returncode},
                  e.returncode if e.returncode in (1, 2) else 1)
        except (FileNotFoundError, FileExistsError) as e:
            _fail({"error": str(e), "type": type(e).__name__})
        except RuntimeError as e:
            _fail({"error": str(e), "type": "runtime_error"})
        except (ValueError, IndexError, KeyError) as e:
            _fail({"error": str(e), "type": type(e).__name__})
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def _require_workspace() -> Session:
    sess = get_session()
    if not sess.has_project():
        raise RuntimeError("This command needs a workspace. Pass --project FILE "
                           "(create one with 'project new -o FILE').")
    return sess


# ── Main CLI Group ──────────────────────────────────────────────
@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.option("--project", "project_path", type=str, default=None,
              help="Workspace file (config target, overrides, undo history)")
@click.option("--config", "config_path", type=str, default=None,
              help="voxtype config.toml to operate on (overrides the workspace's)")
@click.option("--dry-run", "dry_run", is_flag=True, default=False,
              help="Validate changes without writing the config or saving the workspace")
@click.version_option(__version__, prog_name="cli-anything-voxtype")
@click.pass_context
def cli(ctx, use_json, project_path, config_path, dry_run):
    """Voxtype CLI — voice-to-text configuration, transcription and daemon control.

    Run without a subcommand to enter interactive REPL mode.
    """
    global _json_output, _dry_run
    _json_output = use_json
    _dry_run = dry_run
    sess = get_session()
    if config_path:
        sess.config_override = os.path.abspath(config_path)
    if project_path and not (sess.has_project() and sess.project_path == os.path.abspath(project_path)):
        if os.path.exists(project_path):
            try:
                sess.open(project_path)
            except (ValueError, FileNotFoundError) as e:
                _fail({"error": str(e), "type": type(e).__name__})
        elif ctx.invoked_subcommand != "project":
            _fail({"error": f"Workspace not found: {project_path}. Create it with "
                            f"'project new -o {project_path}'", "type": "FileNotFoundError"})
        else:
            sess.project_path = os.path.abspath(project_path)

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.result_callback()
def auto_save_on_exit(result, use_json, project_path, config_path, dry_run, **kwargs):
    """Auto-save the workspace after one-shot commands if state was modified."""
    if _repl_mode or dry_run:
        return
    sess = get_session()
    if sess.has_project() and sess._modified and sess.project_path:
        try:
            sess.save_session()
        except Exception as e:  # noqa: BLE001
            click.echo(f"Warning: Auto-save failed: {e}", err=True)


# ── Project (workspace) ─────────────────────────────────────────
@cli.group()
def project():
    """Workspace management (config target, transcription overrides, history)."""


@project.command("new")
@click.option("-o", "--output", "out", required=True, help="Workspace file to create")
@click.option("-n", "--name", default=None, help="Workspace name")
@click.option("--config", "ws_config", default=None,
              help="voxtype config.toml this workspace manages (default: voxtype's own)")
@click.option("--overwrite", is_flag=True, help="Replace an existing workspace file")
@handle_error
def project_new(out, name, ws_config, overwrite):
    """Create a new workspace file."""
    if os.path.exists(out) and not overwrite:
        raise FileExistsError(f"{out} exists; pass --overwrite")
    sess = get_session()
    name = name or os.path.splitext(os.path.basename(out))[0]
    sess.new(out, name, ws_config or sess.config_override)
    if not _dry_run:
        sess.save_session(out)
    report(project_mod.workspace_info(sess.workspace, out), f"Created workspace: {out}")


@project.command("info")
@handle_error
def project_info():
    """Show the open workspace."""
    sess = _require_workspace()
    info = project_mod.workspace_info(sess.workspace, sess.project_path)
    info["resolved_config_path"] = config_mod.resolved_path(sess.config_path())
    output(info)


@project.command("set-config")
@click.argument("path", required=False)
@click.option("--default", "use_default", is_flag=True, help="Use voxtype's default config path")
@handle_error
def project_set_config(path, use_default):
    """Point the workspace at a voxtype config file."""
    sess = _require_workspace()
    if not path and not use_default:
        raise ValueError("Give a PATH or --default")
    sess.workspace["config_path"] = None if use_default else os.path.abspath(path)
    sess.mark_modified()
    output({"config_path": sess.workspace["config_path"]}, "Workspace config target updated")


@project.command("override")
@click.argument("key", required=False)
@click.argument("value", required=False)
@click.option("--remove", is_flag=True, help="Remove the override instead of setting it")
@handle_error
def project_override(key, value, remove):
    """Pin a transcription flag for this workspace (model, language, vad, ...).

    With no KEY, lists the available override keys and the current values.
    """
    sess = _require_workspace()
    if not key:
        output({"current": sess.overrides(),
                "available": {k: v[0] for k, v in project_mod.OVERRIDE_FLAGS.items()}})
        return
    if remove:
        result = project_mod.remove_override(sess.workspace, key)
    else:
        result = project_mod.set_override(sess.workspace, key, value)
    sess.mark_modified()
    output({"overrides": result}, f"Override {'removed' if remove else 'set'}: {key}")


@project.command("clear-overrides")
@handle_error
def project_clear_overrides():
    """Remove every transcription override."""
    sess = _require_workspace()
    sess.workspace["overrides"] = {}
    sess.mark_modified()
    output({"overrides": {}}, "Overrides cleared")


# ── Config ──────────────────────────────────────────────────────
@cli.group()
def config():
    """Read and change voxtype settings (validated by voxtype)."""


@config.command("path")
@handle_error
def config_path_cmd():
    """Show which config file is in use."""
    sess = get_session()
    path = config_mod.resolved_path(sess.config_path())
    output({"config_path": path, "exists": os.path.exists(path)})


@config.command("show")
@click.option("--changed", is_flag=True, help="Only keys present in the config file")
@click.option("--prefix", default=None, help="Only keys starting with this prefix (e.g. hotkey.)")
@handle_error
def config_show(changed, prefix):
    """Print the resolved configuration."""
    sess = get_session()
    if changed:
        data = config_mod.diff_against_defaults(sess.config_path())
        if prefix:
            data = [d for d in data if d["key"].startswith(prefix)]
        if _json_output:
            output(data)
        else:
            for d in data:
                click.echo(f"{d['key']} = {json.dumps(d['file_value'])}")
            if not data:
                click.echo("(no keys set in the config file; all defaults)")
        return
    data = config_mod.get_all(sess.config_path())
    if prefix:
        data = {k: v for k, v in data.items() if k.startswith(prefix)}
    if _json_output:
        output(data)
    else:
        for k, v in data.items():
            click.echo(f"{k} = {json.dumps(v)}")


@config.command("get")
@click.argument("key")
@handle_error
def config_get(key):
    """Print one key's effective value (and its literal file value)."""
    sess = get_session()
    data = config_mod.get_key(key, sess.config_path())
    if _json_output:
        output(data)
    else:
        click.echo(json.dumps(data["value"]))


@config.command("set")
@click.argument("key")
@click.argument("value")
@handle_error
def config_set(key, value):
    """Set KEY to VALUE (undoable inside a workspace)."""
    sess = get_session()
    entry = config_mod.set_key(key, value, sess.config_path(), dry_run=_dry_run)
    if not _dry_run:
        sess.record(entry)
    msg = f"{'[dry-run] would set' if _dry_run else 'Set'} {key} = {json.dumps(entry['new'])}"
    if entry["restart_required"] and not _dry_run:
        msg += "\nRestart the daemon to apply: cli-anything-voxtype daemon service restart"
    report(entry, msg)


@config.command("unset")
@click.argument("key")
@handle_error
def config_unset(key):
    """Remove KEY from the config file, restoring its default."""
    sess = get_session()
    entry = config_mod.unset_key(key, sess.config_path(), dry_run=_dry_run)
    if not _dry_run:
        sess.record(entry)
    report(entry, f"{'[dry-run] would unset' if _dry_run else 'Unset'} {key} "
                  f"(effective value now {json.dumps(entry['value'])})")


@config.command("schema")
@click.option("--section", default=None, help="Restrict to one section (Engine, Text, Audio, ...)")
@click.option("--search", default=None, help="Filter keys by substring in key/label/description")
@handle_error
def config_schema(section, search):
    """Describe settable keys: type, choices, ranges, current value."""
    sess = get_session()
    data = config_mod.schema(sess.config_path(), section, search)
    if _json_output:
        output(data)
        return
    for k in data["keys"]:
        extra = ""
        if k.get("choices"):
            extra = f"  [{'|'.join(map(str, k['choices']))}]"
        elif k.get("min") is not None or k.get("max") is not None:
            extra = f"  [{k.get('min')}..{k.get('max')}]"
        flag = "" if k.get("compiled", True) else "  (not compiled)"
        click.echo(f"{k['key']:<48} {k['type']:<13} = {json.dumps(k.get('value'))}{extra}{flag}")
    click.echo(f"\n{len(data['keys'])} keys")


@config.command("sections")
@handle_error
def config_sections():
    """List schema sections and key counts."""
    output(config_mod.sections(get_session().config_path()))


@config.group("replace")
def config_replace():
    """Word replacements applied to every transcript (text.replacements)."""


@config_replace.command("list")
@handle_error
def replace_list():
    """List spoken → written replacements."""
    data = config_mod.replacements(get_session().config_path())
    if _json_output:
        output(data)
    else:
        for k, v in data.items():
            click.echo(f"{k!r} -> {v!r}")
        if not data:
            click.echo("(no replacements)")


@config_replace.command("add")
@click.argument("spoken")
@click.argument("written")
@handle_error
def replace_add(spoken, written):
    """Replace SPOKEN with WRITTEN in transcripts."""
    sess = get_session()
    entry = config_mod.set_key(f"text.replacements.{spoken}", written, sess.config_path(), dry_run=_dry_run)
    if not _dry_run:
        sess.record(entry)
    report(entry, f"Replacement {spoken!r} -> {written!r}{' [dry-run]' if _dry_run else ''}")


@config_replace.command("remove")
@click.argument("spoken")
@handle_error
def replace_remove(spoken):
    """Remove a replacement."""
    sess = get_session()
    entry = config_mod.unset_key(f"text.replacements.{spoken}", sess.config_path(), dry_run=_dry_run)
    if not _dry_run:
        sess.record(entry)
    report(entry, f"Removed replacement {spoken!r}{' [dry-run]' if _dry_run else ''}")


# ── Transcribe ──────────────────────────────────────────────────
@cli.group()
def transcribe():
    """Transcribe audio files with voxtype's engine and text pipeline."""


def _overrides_with(**extra) -> dict:
    ov = get_session().overrides()
    for k, v in extra.items():
        if v is None or v is False:
            continue
        ov[k] = v
    return ov


_transcribe_options = [
    click.option("--engine", default=None, help="Engine override (whisper, parakeet, ...)"),
    click.option("--model", default=None, help="Model override (e.g. base.en, large-v3-turbo)"),
    click.option("--language", default=None, help="Language (en, fr, auto, en,fr,...)"),
    click.option("--translate", is_flag=True, default=None, help="Translate to English"),
    click.option("--initial-prompt", default=None, help="Context prompt (terminology, names)"),
    click.option("--threads", type=int, default=None, help="CPU threads"),
    click.option("--vad", is_flag=True, default=None, help="Enable voice activity detection"),
    click.option("--vad-backend", type=click.Choice(["auto", "energy", "whisper"]), default=None,
                 help="VAD backend (energy needs no model download)"),
    click.option("--spoken-punctuation", is_flag=True, default=None, help='Say "period" → "."'),
]


def _apply(options):
    def deco(f):
        for opt in reversed(options):
            f = opt(f)
        return f
    return deco


@transcribe.command("file")
@click.argument("path")
@_apply(_transcribe_options)
@click.option("-o", "--output", "out", default=None, help="Write the transcript to a file (.txt/.json/.md)")
@click.option("--overwrite", is_flag=True, help="Overwrite --output if it exists")
@handle_error
def transcribe_file(path, engine, model, language, translate, initial_prompt, threads, vad,
                    vad_backend, spoken_punctuation, out, overwrite):
    """Transcribe one audio file (any format ffmpeg reads)."""
    sess = get_session()
    ov = _overrides_with(model=model, language=language, translate=translate,
                         initial_prompt=initial_prompt, threads=threads, vad=vad, vad_backend=vad_backend,
                         spoken_punctuation=spoken_punctuation)
    result = transcribe_mod.transcribe_file(path, sess.config_path(), ov, engine)
    if out:
        result["export"] = transcribe_mod.export_results([result], out, overwrite=overwrite)
    if not _dry_run:
        sess.log_transcription(result)
    if _json_output:
        output(result)
    else:
        click.echo(result["text"] if result["text"] else "(no speech detected)")


@transcribe.command("batch")
@click.argument("inputs", nargs=-1, required=True)
@_apply(_transcribe_options)
@click.option("-r", "--recursive", is_flag=True, help="Recurse into directories")
@click.option("-o", "--output", "out", default=None, help="Write all results (.txt/.md/.json/.jsonl/.csv)")
@click.option("--overwrite", is_flag=True, help="Overwrite --output if it exists")
@click.option("--stop-on-error", is_flag=True, help="Abort on the first failure")
@handle_error
def transcribe_batch(inputs, engine, model, language, translate, initial_prompt, threads, vad,
                     vad_backend, spoken_punctuation, recursive, out, overwrite, stop_on_error):
    """Transcribe many files, directories or globs."""
    sess = get_session()
    ov = _overrides_with(model=model, language=language, translate=translate,
                         initial_prompt=initial_prompt, threads=threads, vad=vad, vad_backend=vad_backend,
                         spoken_punctuation=spoken_punctuation)

    def progress(i, n, name):
        if not _json_output:
            click.echo(f"[{i}/{n}] {name}", err=True)

    result = transcribe_mod.transcribe_batch(list(inputs), sess.config_path(), ov, engine,
                                             recursive, not stop_on_error, progress)
    if out and result["results"]:
        result["export"] = transcribe_mod.export_results(result["results"], out, overwrite=overwrite)
    if not _dry_run:
        for r in result["results"]:
            sess.log_transcription(r)
    if _json_output:
        output(result)
    else:
        for r in result["results"]:
            click.echo(f"{os.path.basename(r['file'])}: {r['text'] or '(no speech)'}")
        for e in result["errors"]:
            click.echo(f"{os.path.basename(e['file'])}: ERROR {e['error']}", err=True)
        click.echo(f"\n{result['succeeded']}/{result['count']} transcribed, "
                   f"{result['total_audio_secs']}s audio")
        if "export" in result:
            click.echo(f"Written: {result['export']['output']}")


@transcribe.command("history")
@click.option("-n", "--limit", type=int, default=20, help="Show the last N results")
@handle_error
def transcribe_history(limit):
    """Show transcriptions recorded in the workspace."""
    sess = _require_workspace()
    items = sess.workspace["transcriptions"][-limit:]
    if _json_output:
        output(items)
    else:
        for r in items:
            click.echo(f"{os.path.basename(r['file'])} ({r.get('duration_secs')}s): {r.get('text')}")
        if not items:
            click.echo("(no transcriptions yet)")


@transcribe.command("export")
@click.argument("out")
@click.option("-f", "--format", "fmt", type=click.Choice(transcribe_mod.EXPORT_FORMATS), default=None)
@click.option("--overwrite", is_flag=True)
@handle_error
def transcribe_export(out, fmt, overwrite):
    """Export the workspace's transcription history."""
    sess = _require_workspace()
    result = transcribe_mod.export_results(sess.workspace["transcriptions"], out, fmt, overwrite)
    output(result, f"Exported {result['entries']} transcriptions to {result['output']}")


@transcribe.command("clear")
@handle_error
def transcribe_clear():
    """Forget the workspace's transcription history."""
    sess = _require_workspace()
    n = len(sess.workspace["transcriptions"])
    sess.workspace["transcriptions"] = []
    sess.mark_modified()
    output({"cleared": n}, f"Cleared {n} transcriptions")


# ── Meeting ─────────────────────────────────────────────────────
@cli.group()
def meeting():
    """Meeting transcripts: list, export, label speakers, import audio."""


@meeting.command("list")
@click.option("-n", "--limit", type=int, default=20)
@click.option("--status", type=click.Choice(["active", "paused", "completed", "cancelled"]), default=None)
@handle_error
def meeting_list(limit, status):
    """List stored meetings (newest first)."""
    data = meeting_mod.list_meetings(get_session().config_path(), limit, status)
    if _json_output:
        output(data)
        return
    if not data["meetings"]:
        click.echo(f"No meetings in {data['storage_path']}")
        return
    click.echo(f"{'ID':<10} {'STARTED':<22} {'DUR':>6} {'STATUS':<10} TITLE")
    for m in data["meetings"]:
        click.echo(f"{m['id'][:8]:<10} {m['started_at'] or '':<22} {str(m['duration_secs'] or '-'):>6} "
                   f"{m['status']:<10} {m['title'] or ''}")


@meeting.command("show")
@click.argument("meeting_id", default="latest")
@handle_error
def meeting_show(meeting_id):
    """Show a meeting (ID, unique prefix, or 'latest')."""
    cfg = get_session().config_path()
    if _json_output:
        output(meeting_mod.get_meeting_json(meeting_id, cfg))
    else:
        click.echo(meeting_mod.show(meeting_id, cfg)["report"])


@meeting.command("export")
@click.argument("meeting_id", default="latest")
@click.option("-f", "--format", "fmt", default="markdown",
              help="text, markdown, json, srt, vtt")
@click.option("-o", "--output", "out", default=None, help="Output file (default: stdout)")
@click.option("--timestamps", is_flag=True)
@click.option("--speakers", is_flag=True)
@click.option("--metadata", is_flag=True)
@click.option("--overwrite", is_flag=True)
@handle_error
def meeting_export(meeting_id, fmt, out, timestamps, speakers, metadata, overwrite):
    """Export a meeting transcript via voxtype's exporters."""
    result = meeting_mod.export(meeting_id, out, fmt, timestamps, speakers, metadata,
                                get_session().config_path(), overwrite)
    if _json_output:
        output(result)
    elif out:
        click.echo(f"Exported {result['format']} to {result['output']} ({result['file_size']} bytes)")
    else:
        click.echo(result["content"], nl=False)


@meeting.command("label")
@click.argument("meeting_id")
@click.argument("speaker_id")
@click.argument("name")
@handle_error
def meeting_label(meeting_id, speaker_id, name):
    """Name a speaker (SPEAKER_00 or 0) in a meeting."""
    output(meeting_mod.label(meeting_id, speaker_id, name, get_session().config_path()),
           f"Labeled {speaker_id} as {name!r}")


@meeting.command("delete")
@click.argument("meeting_id")
@click.option("--yes", is_flag=True, help="Confirm deletion")
@handle_error
def meeting_delete(meeting_id, yes):
    """Delete a meeting and its files."""
    if not yes:
        raise ValueError("Refusing to delete without --yes")
    if _dry_run:
        mid = meeting_mod.resolve_id(meeting_id, get_session().config_path())
        output({"id": mid, "deleted": False, "dry_run": True}, f"[dry-run] would delete {mid}")
        return
    output(meeting_mod.delete(meeting_id, get_session().config_path()), "Meeting deleted")


@meeting.command("summarize")
@click.argument("meeting_id", default="latest")
@click.option("-f", "--format", "fmt", type=click.Choice(["text", "json", "markdown"]), default="markdown")
@click.option("-o", "--output", "out", default=None)
@handle_error
def meeting_summarize(meeting_id, fmt, out):
    """AI summary via voxtype (needs Ollama or a remote API configured)."""
    result = meeting_mod.summarize(meeting_id, fmt, out, get_session().config_path())
    if _json_output or out:
        output(result)
    else:
        click.echo(result["content"])


@meeting.command("import")
@click.argument("files", nargs=-1, required=True)
@click.option("-t", "--title", default=None)
@click.option("--speakers", default=None,
              help="Comma-separated speaker numbers per file, cycled (e.g. 0,1)")
@click.option("--gap-ms", type=int, default=0, help="Silence inserted between files on the timeline")
@click.option("--model", default=None)
@click.option("--language", default=None)
@handle_error
def meeting_import(files, title, speakers, gap_ms, model, language):
    """Create a meeting from pre-recorded audio files (transcribed by voxtype)."""
    sess = get_session()
    spk = [int(s) for s in speakers.split(",")] if speakers else None
    ov = _overrides_with(model=model, language=language)

    def progress(i, n, name):
        if not _json_output:
            click.echo(f"[{i}/{n}] transcribing {name}", err=True)

    if _dry_run:
        found = transcribe_mod.collect_inputs(list(files))
        output({"dry_run": True, "files": found}, f"[dry-run] would import {len(found)} files")
        return
    result = meeting_mod.import_meeting(list(files), title, spk, gap_ms, sess.config_path(), ov,
                                        progress=progress)
    output(result, f"Imported meeting {result['id']}")


def _meeting_control(action, **kw):
    return meeting_mod.control(action, get_session().config_path(), **kw)


@meeting.command("start")
@click.option("-t", "--title", default=None)
@click.option("--diarization", type=click.Choice(["simple", "ml"]), default=None)
@handle_error
def meeting_start(title, diarization):
    """Start live meeting transcription (daemon)."""
    output(_meeting_control("start", title=title, diarization=diarization))


@meeting.command("stop")
@handle_error
def meeting_stop():
    """Stop the live meeting."""
    output(_meeting_control("stop"))


@meeting.command("pause")
@handle_error
def meeting_pause():
    """Pause the live meeting."""
    output(_meeting_control("pause"))


@meeting.command("resume")
@handle_error
def meeting_resume():
    """Resume the live meeting."""
    output(_meeting_control("resume"))


@meeting.command("status")
@handle_error
def meeting_status():
    """Live meeting status."""
    output(_meeting_control("status"))


# ── Daemon ──────────────────────────────────────────────────────
@cli.group()
def daemon():
    """The running voxtype daemon: status, recording, service."""


@daemon.command("status")
@click.option("--icon-theme", default=None)
@handle_error
def daemon_status(icon_theme):
    """Daemon state (idle/recording/transcribing/stopped), model, device."""
    data = daemon_mod.status(get_session().config_path(), True, icon_theme)
    if _json_output:
        output(data)
    else:
        click.echo(f"state:   {data['state']}")
        for k in ("model", "device", "backend", "pid"):
            if data.get(k) is not None:
                click.echo(f"{k + ':':<8} {data[k]}")


@daemon.group("record")
def daemon_record():
    """Control recording (like the hotkey). start/toggle capture the mic!"""


def _record_opts(f):
    for opt in reversed([
        click.option("--output-mode", type=click.Choice(daemon_mod.OUTPUT_MODES), default=None,
                     help="Where the transcript goes for this recording"),
        click.option("--file", "file_path", default=None, help="Write the transcript to this file"),
        click.option("--model", default=None),
        click.option("--profile", default=None),
        click.option("--auto-submit/--no-auto-submit", default=None),
        click.option("--no-osd", is_flag=True),
    ]):
        f = opt(f)
    return f


@daemon_record.command("start")
@_record_opts
@handle_error
def record_start(output_mode, file_path, model, profile, auto_submit, no_osd):
    """Start recording."""
    output(daemon_mod.record("start", get_session().config_path(), output_mode=output_mode,
                             file_path=file_path, model=model, profile=profile,
                             auto_submit=auto_submit, no_osd=no_osd))


@daemon_record.command("toggle")
@_record_opts
@handle_error
def record_toggle(output_mode, file_path, model, profile, auto_submit, no_osd):
    """Toggle recording."""
    output(daemon_mod.record("toggle", get_session().config_path(), output_mode=output_mode,
                             file_path=file_path, model=model, profile=profile,
                             auto_submit=auto_submit, no_osd=no_osd))


@daemon_record.command("stop")
@handle_error
def record_stop():
    """Stop recording and transcribe."""
    output(daemon_mod.record("stop", get_session().config_path()))


@daemon_record.command("cancel")
@handle_error
def record_cancel():
    """Cancel recording/transcription without output."""
    output(daemon_mod.record("cancel", get_session().config_path()))


@daemon.command("service")
@click.argument("action", type=click.Choice(["status", "start", "stop", "restart"]), default="status")
@handle_error
def daemon_service(action):
    """systemd user service control."""
    if _dry_run and action != "status":
        output({"action": action, "dry_run": True}, f"[dry-run] would {action} voxtype.service")
        return
    output(daemon_mod.service(action))


@daemon.command("accel")
@handle_error
def daemon_accel():
    """Is the running daemon GPU-accelerated?"""
    output(daemon_mod.accel())


# ── Info ────────────────────────────────────────────────────────
@cli.group()
def info():
    """Install and runtime information."""


@info.command("version")
@handle_error
def info_version():
    """voxtype and harness versions."""
    data = system_mod.version_info()
    data["harness"] = __version__
    output(data)


@info.command("engines")
@handle_error
def info_engines():
    """Transcription engines and which are compiled in."""
    data = system_mod.info("engines", get_session().config_path())
    if _json_output:
        output(data)
    else:
        for e in data:
            mark = "*" if e.get("active") else " "
            click.echo(f"{mark} {e['name']:<12} {'compiled' if e.get('compiled') else 'not compiled'}")


@info.command("models")
@click.option("--engine", default=None)
@click.option("--installed", is_flag=True, help="Only installed models")
@click.option("--verify", is_flag=True, help="Hash-verify installed models (slow)")
@handle_error
def info_models(engine, installed, verify):
    """Downloadable and installed models."""
    cfg = get_session().config_path()
    if installed:
        data = system_mod.installed_models(cfg, engine)
        if _json_output:
            output(data)
        else:
            for m in data:
                click.echo(f"{m['engine']:<12} {m['name']}")
            if not data:
                click.echo("(no installed models)")
        return
    data = system_mod.info("models", cfg, engine=engine, verify=verify)
    if _json_output:
        output(data)
        return
    for eng, block in sorted(data.get("engines", {}).items()):
        click.echo(f"{eng} (default {block.get('default')}):")
        for m in block.get("models", []):
            click.echo(f"  {'✓' if m.get('installed') else ' '} {m['name']}")


@info.command("devices")
@handle_error
def info_devices():
    """Audio capture devices."""
    data = system_mod.info("devices", get_session().config_path())
    if _json_output:
        output(data)
    else:
        for d in data:
            click.echo(f"{'*' if d.get('default') else ' '} {d['name']}")


@info.command("variants")
@handle_error
def info_variants():
    """Installed binary variants."""
    output(system_mod.info("variants", get_session().config_path()))


@info.command("styles")
@handle_error
def info_styles():
    """Installed OSD styles."""
    output(system_mod.info("styles", get_session().config_path()))


# ── Setup ───────────────────────────────────────────────────────
@cli.group()
def setup():
    """Dependency checks and model downloads."""


@setup.command("check")
@handle_error
def setup_check():
    """Run voxtype's dependency check."""
    data = system_mod.check(get_session().config_path())
    if _json_output:
        output(data)
    else:
        click.echo(data["report"])


@setup.command("download")
@click.argument("model")
@click.option("--activate", is_flag=True, help="Also select the model in config")
@handle_error
def setup_download(model, activate):
    """Download a model (names from 'info models')."""
    if _dry_run:
        output({"model": model, "dry_run": True}, f"[dry-run] would download {model}")
        return
    output(system_mod.download_model(model, activate, get_session().config_path()),
           f"Downloaded {model}")


@setup.command("set-model")
@click.argument("model")
@click.option("--restart", is_flag=True, help="Restart the daemon afterwards")
@handle_error
def setup_set_model(model, restart):
    """Make an installed model the default."""
    output(system_mod.set_model(model, restart, get_session().config_path()))


@setup.command("vad")
@handle_error
def setup_vad():
    """Download the Silero VAD model."""
    output(system_mod.download_vad(get_session().config_path()))


# ── Session ─────────────────────────────────────────────────────
@cli.group()
def session():
    """Workspace session: status, history, undo/redo."""


@session.command("status")
@handle_error
def session_status():
    """Session state."""
    output(get_session().status())


@session.command("history")
@click.option("-n", "--limit", type=int, default=20)
@handle_error
def session_history(limit):
    """Config changes recorded in the workspace (most recent last)."""
    sess = _require_workspace()
    items = sess.workspace["history"][-limit:]
    if _json_output:
        output({"history": items, "redo": sess.workspace["redo"]})
    else:
        for i, e in enumerate(items):
            click.echo(f"{i:>3}. {e['op']:<5} {e['key']}: {json.dumps(e.get('old'))} -> {json.dumps(e.get('new'))}")
        if not items:
            click.echo("(no history)")


@session.command("undo")
@handle_error
def session_undo():
    """Revert the last config change."""
    sess = _require_workspace()
    entry = sess.pop_undo()
    if _dry_run:
        output({"would_undo": entry, "dry_run": True})
        return
    try:
        res = config_mod.undo_entry(entry, sess.config_path())
    except Exception:
        sess.workspace["redo"].pop()
        sess.workspace["history"].append(entry)
        raise
    report({"undone": entry, "now": res.get("new"), "key": entry["key"]},
           f"Undid {entry['op']} {entry['key']} (now {json.dumps(res.get('new'))})")


@session.command("redo")
@handle_error
def session_redo():
    """Re-apply the last undone change."""
    sess = _require_workspace()
    entry = sess.pop_redo()
    if _dry_run:
        output({"would_redo": entry, "dry_run": True})
        return
    try:
        res = config_mod.redo_entry(entry, sess.config_path())
    except Exception:
        sess.workspace["history"].pop()
        sess.workspace["redo"].append(entry)
        raise
    report({"redone": entry, "now": res.get("new"), "key": entry["key"]},
           f"Redid {entry['op']} {entry['key']} (now {json.dumps(res.get('new'))})")


@session.command("save")
@click.argument("path", required=False)
@handle_error
def session_save(path):
    """Save the workspace now (REPL mode does not auto-save)."""
    sess = _require_workspace()
    saved = sess.save_session(path)
    output({"saved": saved}, f"Saved {saved}")


# ── REPL ────────────────────────────────────────────────────────
@cli.command()
@click.argument("project_path", required=False)
def repl(project_path=None):
    """Start interactive REPL session."""
    from cli_anything.voxtype.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True

    sess = get_session()
    if project_path:
        try:
            sess.open(project_path)
        except Exception as e:  # noqa: BLE001
            click.echo(f"Could not open {project_path}: {e}", err=True)

    skin = ReplSkin("voxtype", version=__version__)
    skin.print_banner()
    pt_session = skin.create_prompt_session()

    _repl_commands = {
        "project":    "new|info|set-config|override|clear-overrides",
        "config":     "path|show|get|set|unset|schema|sections|replace",
        "transcribe": "file|batch|history|export|clear",
        "meeting":    "list|show|export|label|delete|summarize|import|start|stop|pause|resume|status",
        "daemon":     "status|record start/stop/toggle/cancel|service|accel",
        "info":       "version|engines|models|devices|variants|styles",
        "setup":      "check|download|set-model|vad",
        "session":    "status|history|undo|redo|save",
        "help":       "Show this help",
        "quit":       "Exit REPL (saves the workspace if modified)",
    }

    while True:
        try:
            name = sess.workspace.get("name") if sess.has_project() else ""
            line = skin.get_input(pt_session, project_name=name or "", modified=sess._modified)
            if not line:
                continue
            if line.lower() in ("quit", "exit", "q"):
                if sess.has_project() and sess._modified and sess.project_path:
                    sess.save_session()
                    skin.success(f"Saved {sess.project_path}")
                skin.print_goodbye()
                break
            if line.lower() == "help":
                skin.help(_repl_commands)
                continue
            try:
                args = shlex.split(line)
            except ValueError:
                args = line.split()
            try:
                cli.main(args, standalone_mode=False)
            except SystemExit:
                pass
            except click.exceptions.UsageError as e:
                skin.warning(f"Usage error: {e}")
            except Exception as e:  # noqa: BLE001
                skin.error(f"{e}")
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

    _repl_mode = False


def main():
    cli()


if __name__ == "__main__":
    main()
