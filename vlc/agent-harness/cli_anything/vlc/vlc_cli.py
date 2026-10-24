#!/usr/bin/env python3
"""cli-anything-vlc — agent-native CLI for VLC.

Wraps the real VLC binary behind a structured, JSON-friendly interface. A "job" is a
JSON spec describing inputs + transcode options + output; the harness runs it through
VLC's ``--sout`` engine. Supports a stateful REPL with undo/redo and scripted
``--json`` usage for AI agents.
"""

from __future__ import annotations

import json
import math
import shlex
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import click

from . import __version__
from .core import project as proj
from .core.session import Session
from .core.transcode import build_transcode_sout, build_stream_sout
from .utils.vlc_backend import find_vlc, run_transcode, run_stream, run_snapshot, run_info
from .utils.repl_skin import ReplSkin


# ── Output helpers ──────────────────────────────────────────────────────

def _emit(data: Dict[str, Any], json_mode: bool) -> None:
    """Print a dict as JSON or as a readable key/value listing."""
    if json_mode:
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))
        return
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            click.echo(f"{key}:")
            click.echo(json.dumps(value, indent=2, ensure_ascii=False))
        else:
            click.echo(f"{key}: {value}")


def _fail(json_mode: bool, detail: str, exc: type = ValueError) -> None:
    """Emit a structured error and exit non-zero — the ``--json`` error contract."""
    _emit({"error": exc.__name__, "detail": detail}, json_mode)
    sys.exit(1)


def _ctx_state(ctx: click.Context):
    return ctx.obj.get("json", False), ctx.obj.get("project")


def _load_or_new(project: Optional[Path]) -> Dict[str, Any]:
    if project and Path(project).is_file():
        return proj.load_job(project)
    return proj.new_job()


def _apply(ctx: click.Context, label: str, mutator: Callable[[Dict[str, Any]], None]) -> None:
    """Load (or create) the job, apply a mutation, persist if --project given, emit.

    The whole load → mutate → save → summarise sequence sits inside the structured
    error guard. A schema-invalid project used to pass ``load_job`` and then raise
    inside the mutator, i.e. *outside* any guard, so ``--json`` callers got a
    traceback on stderr and an empty stdout.
    """
    json_mode, project = _ctx_state(ctx)
    try:
        job = _load_or_new(project)
        sess = Session(job, project)
        sess.mutate(label, mutator)
        saved = False
        if project:
            proj.save_job(sess.job, project)
            saved = True
        summary = proj.job_summary(sess.job)
        summary["saved"] = saved
        if project:
            summary["project"] = str(project)
    except Exception as e:  # noqa: BLE001 — load/mutate/save/summary -> structured error
        _emit({"error": type(e).__name__, "detail": str(e)}, json_mode)
        sys.exit(1)
    _emit(summary, json_mode)


def _run_job(ctx: click.Context) -> Dict[str, Any]:
    """Load the job referenced by --project (required for run commands)."""
    _, project = _ctx_state(ctx)
    if not project or not Path(project).is_file():
        raise click.ClickException(
            "a saved job is required: pass --project <job.json> (create one with "
            "'project new' then add-input / set-output / set-option)."
        )
    return proj.load_job(project)


def _guard(backend_fn: Callable[[], Dict[str, Any]], json_mode: bool) -> None:
    """Run a backend call, emitting structured errors on failure."""
    try:
        _emit(backend_fn(), json_mode)
    except Exception as e:  # noqa: BLE001 — surface as structured error
        _emit({"error": type(e).__name__, "detail": str(e)}, json_mode)
        sys.exit(1)


# ── Root group ──────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--json", "json_mode", is_flag=True, help="JSON output for agent consumption")
@click.option("--project", "project", type=click.Path(path_type=Path), default=None,
              help="Job spec JSON file to load/save")
@click.version_option(version=__version__, prog_name="cli-anything-vlc")
@click.pass_context
def cli(ctx: click.Context, json_mode: bool, project: Optional[Path]) -> None:
    """cli-anything-vlc — agent-native CLI for VLC.

    Define media jobs (transcode / stream / snapshot) as structured JSON and run them
    through the real VLC engine. Every command supports --json. Run with no subcommand
    to enter the interactive REPL.
    """
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_mode
    ctx.obj["project"] = project
    if ctx.invoked_subcommand is None:
        _repl(project)


# ── project group ───────────────────────────────────────────────────────

@cli.group()
def project() -> None:
    """Manage the job spec file."""


@project.command("new")
@click.option("-o", "--output", "output", type=click.Path(path_type=Path), required=True,
              help="Path of the new job spec JSON file")
@click.pass_context
def project_new(ctx: click.Context, output: Path) -> None:
    """Create a new empty job spec file."""
    json_mode, _ = _ctx_state(ctx)
    try:
        meta = proj.save_job(proj.new_job(), output)
        payload = {"created": str(output), "size_bytes": meta["size_bytes"]}
    except Exception as e:  # noqa: BLE001 — unwritable target -> structured error
        _fail(json_mode, str(e), type(e))
        return  # _fail exits; kept explicit so the happy path stays readable
    _emit(payload, json_mode)


@project.command("show")
@click.pass_context
def project_show(ctx: click.Context) -> None:
    """Print the current job spec (from --project)."""
    json_mode, project = _ctx_state(ctx)
    if not project or not Path(project).is_file():
        _fail(json_mode, "no --project file given or it does not exist", click.ClickException)
    try:
        loaded = proj.load_job(project)
    except Exception as e:  # noqa: BLE001 — malformed project -> structured error
        _emit({"error": type(e).__name__, "detail": str(e)}, json_mode)
        sys.exit(1)
    _emit(proj.job_summary(loaded), json_mode)


# ── mutation commands ───────────────────────────────────────────────────

# The transcode options `set-option` accepts, mirroring its --help text. An unknown key
# used to be persisted while `_transcode_block` ignored it, so a typo such as `vcdoec`
# reported success and the transcode quietly kept the old codec.
TRANSCODE_OPTION_KEYS = (
    "vcodec", "acodec", "vbitrate", "abitrate", "scale",
    "width", "height", "fps", "channels", "samplerate",
)
NUMERIC_OPTION_KEYS = frozenset(
    {"vbitrate", "abitrate", "width", "height", "fps", "channels", "samplerate", "scale"}
)


def _coerce_number(key: str, value: str) -> Optional[float]:
    """Parse a numeric transcode option, or return None when it is not finite.

    ``float()`` happily accepts ``nan`` / ``inf`` / ``1e309``. Those used to be
    persisted and echoed as the ``NaN`` / ``Infinity`` tokens, which are **not valid
    JSON**, so strict agent parsers could consume neither the ``--json`` response nor
    the saved project file.
    """
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return num if math.isfinite(num) else None


@cli.command("add-input")
@click.argument("file", type=click.Path(path_type=Path))
@click.pass_context
def add_input(ctx: click.Context, file: Path) -> None:
    """Append an input media file to the job."""
    # Validated here rather than by click.Path(exists=True, dir_okay=False): Click's
    # own checks exit 2 with human-only text, breaking the --json contract.
    json_mode, _ = _ctx_state(ctx)
    if not file.is_file():
        _fail(json_mode, f"media file not found: {file}")
    _apply(ctx, f"add-input {file.name}",
           lambda j: j.setdefault("inputs", []).append(str(file)))


@cli.command("set-output")
@click.argument("file", type=click.Path(path_type=Path))
@click.option("--format", "fmt", default=None, help="Output container (mp4/mkv/ts/webm/...)")
@click.pass_context
def set_output(ctx: click.Context, file: Path, fmt: Optional[str]) -> None:
    """Set the output file (and optional container format)."""
    json_mode, _ = _ctx_state(ctx)
    if file.is_dir():  # see add-input: keep the failure inside the structured contract
        _fail(json_mode, f"output path is a directory: {file}")
    _apply(ctx, f"set-output {file.name}",
           lambda j: (j.__setitem__("output", {"path": str(file),
                                                "format": fmt or j.get("output", {}).get("format", "mp4")})))


@cli.command("set-option")
@click.argument("key")
@click.argument("value")
@click.pass_context
def set_option(ctx: click.Context, key: str, value: str) -> None:
    """Set a transcode option (vcodec, acodec, vbitrate, abitrate, scale, width,
    height, fps, channels, samplerate). Numeric where appropriate."""
    json_mode, _ = _ctx_state(ctx)
    if key not in TRANSCODE_OPTION_KEYS:
        _fail(json_mode, f"unknown transcode option '{key}'. Known options: "
                         + ", ".join(TRANSCODE_OPTION_KEYS))
    coerced: Any = value
    if key in NUMERIC_OPTION_KEYS:
        num = _coerce_number(key, value)
        if num is None:
            _fail(json_mode, f"option '{key}' expects a finite number, got '{value}'")
        coerced = num

    def _mut(j: Dict[str, Any]) -> None:
        j.setdefault("transcode", {})[key] = coerced

    _apply(ctx, f"set-option {key}={value}", _mut)


@cli.command("set-stream")
@click.option("--protocol", default="rtp", help="rtp / udp / http")
@click.option("--dst", default="127.0.0.1", help="Destination host")
@click.option("--port", default=1234, type=int, help="Destination port")
@click.option("--mux", default="ts", help="Muxer (ts / ps / mpeg / mp4 / ...)")
@click.pass_context
def set_stream(ctx: click.Context, protocol: str, dst: str, port: int, mux: str) -> None:
    """Configure network streaming for the job."""
    _apply(ctx, f"set-stream {protocol}://{dst}:{port}",
           lambda j: j.__setitem__("stream",
                                    {"protocol": protocol, "dst": dst, "port": port, "mux": mux}))


@cli.command("set-snapshot")
@click.option("--path", "snap_dir", required=True, type=click.Path(path_type=Path),
              help="Output directory for the extracted frame")
@click.option("--time", default=1.0, type=float, help="Seek time in seconds")
@click.option("--ratio", default=1, type=int, help="Capture every Nth frame")
@click.pass_context
def set_snapshot(ctx: click.Context, snap_dir: Path, time: float, ratio: int) -> None:
    """Configure still-frame extraction for the job."""
    json_mode, _ = _ctx_state(ctx)
    # Click's type=float accepts nan/inf, which would persist the NaN/Infinity tokens —
    # not valid JSON, so neither the --json response nor the saved project could be
    # parsed by a strict caller.
    if not math.isfinite(time):
        _fail(json_mode, f"snapshot --time expects a finite number of seconds, got '{time}'")
    if ratio < 1:
        # Persisting 0 and substituting 1 at build time made the run disagree with the
        # saved spec, so reject it here rather than quietly capturing every frame.
        _fail(json_mode, f"snapshot --ratio must be >= 1, got {ratio}")
    _apply(ctx, f"set-snapshot {snap_dir}",
           lambda j: j.__setitem__("snapshot",
                                    {"path": str(snap_dir), "time": time, "ratio": ratio}))


@cli.command("clear")
@click.pass_context
def clear_job(ctx: click.Context) -> None:
    """Reset the job to defaults."""
    _apply(ctx, "clear", lambda j: j.clear() or j.update(proj.new_job()))


# ── run commands ────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def transcode(ctx: click.Context) -> None:
    """Transcode the job's first input to its output via the real VLC engine."""
    json_mode, _ = _ctx_state(ctx)
    # Load the job inside the guard so missing/malformed projects surface as
    # structured --json errors instead of a Click traceback.
    _guard(lambda: run_transcode(_run_job(ctx)), json_mode)


@cli.command()
@click.option("--run-time", "run_time", default=None, type=int,
              help="Seconds to stream before exiting; omit for a persistent stream")
@click.pass_context
def stream(ctx: click.Context, run_time: Optional[int]) -> None:
    """Stream the job's input over the network via the real VLC engine."""
    json_mode, _ = _ctx_state(ctx)
    _guard(lambda: run_stream(_run_job(ctx), run_time=run_time), json_mode)


@cli.command()
@click.pass_context
def snapshot(ctx: click.Context) -> None:
    """Extract a still frame from the job's input via the real VLC engine."""
    json_mode, _ = _ctx_state(ctx)
    _guard(lambda: run_snapshot(_run_job(ctx)), json_mode)


@cli.command()
@click.argument("file", type=click.Path(path_type=Path))
@click.pass_context
def info(ctx: click.Context, file: Path) -> None:
    """Probe a media file via VLC (best-effort metadata parse)."""
    json_mode, _ = _ctx_state(ctx)
    if not file.is_file():  # see add-input: structured error, not a Click usage error
        _fail(json_mode, f"media file not found: {file}")
    _guard(lambda: run_info(file), json_mode)


@cli.command()
@click.pass_context
def doctor(ctx: click.Context) -> None:
    """Verify the environment (VLC presence)."""
    json_mode, _ = _ctx_state(ctx)
    checks = []
    try:
        vlc = find_vlc()
        checks.append({"check": "vlc binary", "ok": True, "path": str(vlc)})
    except RuntimeError as e:
        checks.append({"check": "vlc binary", "ok": False, "detail": str(e)})
    all_ok = all(c.get("ok") for c in checks)
    _emit({"checks": checks, "ready": all_ok}, json_mode)
    if not all_ok:
        sys.exit(1)


# ── REPL ────────────────────────────────────────────────────────────────

_REPL_COMMANDS = {
    "new": "start a fresh in-memory job",
    "open <file>": "load a job spec into the session",
    "save [file]": "persist the session job (uses <file> or current --project)",
    "add-input <file>": "append an input",
    "set-output <file> [--format FMT]": "set output file",
    "set-option <key> <value>": "set a transcode option",
    "set-stream <proto> <dst> <port> [mux]": "configure streaming",
    "set-snapshot <dir> [time]": "configure snapshot",
    "clear": "reset the job",
    "show": "print the current job",
    "transcode": "run the job through VLC",
    "stream": "stream the job through VLC",
    "snapshot": "extract a frame through VLC",
    "info <file>": "probe a media file",
    "undo": "undo last mutation",
    "redo": "redo last undone mutation",
    "help": "show this help",
    "quit": "exit",
}


def _repl(project: Optional[Path] = None) -> None:
    skin = ReplSkin("vlc", version=__version__)
    skin.print_banner()
    session = Session()
    project_path: List[Optional[Path]] = [None]
    # Honour an explicit --project passed at launch: load it into the session so the
    # REPL starts from the saved job instead of a blank one.
    if project and Path(project).is_file():
        session = Session(proj.load_job(Path(project)), Path(project))
        project_path[0] = Path(project)
    elif project:
        # A --project that does not exist yet is the file to *create*: bind it so
        # mutations auto-save there and a bare `save` knows the destination (the
        # non-REPL mutation commands create a missing project the same way).
        session = Session(proj.new_job(), Path(project))
        project_path[0] = Path(project)
    pt = skin.create_prompt_session()

    def _persist() -> None:
        if project_path[0]:
            proj.save_job(session.job, project_path[0])

    while True:
        try:
            line = skin.get_input(pt, project_name=(str(project_path[0]) or "unsaved"),
                                  modified=session.can_undo())
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            return
        if not line:
            continue
        # Tokenise like a shell (quoted paths with spaces) while keeping Windows
        # backslash paths intact: non-POSIX lexing (backslashes stay literal),
        # then strip one pair of surrounding quotes from each token.
        try:
            lexer = shlex.shlex(line, posix=False)
            lexer.whitespace_split = True
            parts = [tok[1:-1] if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "\"'"
                     else tok for tok in lexer]
        except ValueError:
            parts = line.split()  # unbalanced quotes -> best effort
        cmd, args = parts[0].lower(), parts[1:]

        if cmd in ("quit", "exit"):
            skin.print_goodbye()
            return
        if cmd == "help":
            skin.help(_REPL_COMMANDS)
            continue

        try:
            if cmd == "new":
                session = Session()
                # Detach the opened project: `new` starts an in-memory job, so the
                # next mutation must not silently overwrite the file we opened.
                project_path[0] = None
                skin.success("new job (unsaved — 'save <file>' to persist)")
            elif cmd == "open":
                p = Path(args[0])
                session = Session(proj.load_job(p), p)
                project_path[0] = p
                skin.success(f"opened {p}")
            elif cmd == "save":
                if args:
                    project_path[0] = Path(args[0])
                if not project_path[0]:
                    skin.error("no --project path and no file argument")
                    continue
                meta = proj.save_job(session.job, project_path[0])
                skin.success(f"saved {meta['path']} ({meta['size_bytes']} bytes)")
            elif cmd == "add-input":
                candidate = Path(args[0])
                # The Click path validates existence; the REPL must not be the one
                # place a typo'd path is accepted and only fails later inside VLC.
                if not candidate.is_file():
                    skin.error(f"input file not found: {candidate}")
                    continue
                session.mutate(f"add-input {candidate.name}",
                               lambda j: j.setdefault("inputs", []).append(str(candidate)))
                _persist(); skin.success("input added")
            elif cmd == "set-output":
                fmt = None
                if "--format" in args:
                    i = args.index("--format"); fmt = args[i + 1]
                target = Path(args[0])
                if target.is_dir():
                    skin.error(f"output path is a directory: {target}")
                    continue
                session.mutate(f"set-output {target}",
                               lambda j: j.__setitem__("output",
                                    {"path": str(target),
                                     "format": fmt or j.get("output", {}).get("format", "mp4")}))
                _persist(); skin.success("output set")
            elif cmd == "set-option":
                key, val = args[0], args[1]
                if key not in TRANSCODE_OPTION_KEYS:
                    skin.error(f"unknown transcode option '{key}'. Known: "
                               + ", ".join(TRANSCODE_OPTION_KEYS))
                    continue
                coerced: Any = val
                if key in NUMERIC_OPTION_KEYS:
                    num = _coerce_number(key, val)
                    if num is None:
                        skin.error(f"option '{key}' expects a finite number, got '{val}'")
                        continue
                    coerced = num
                session.mutate(f"set-option {key}={val}",
                               lambda j: j.setdefault("transcode", {}).__setitem__(key, coerced))
                _persist(); skin.success(f"{key} = {val}")
            elif cmd == "set-stream":
                proto, dst, port = (args + ["rtp", "127.0.0.1", "1234"])[:3]
                mux = args[3] if len(args) > 3 else "ts"
                session.mutate(f"set-stream {proto}://{dst}:{port}",
                               lambda j: j.__setitem__("stream",
                                    {"protocol": proto, "dst": dst, "port": int(port), "mux": mux}))
                _persist(); skin.success("stream configured")
            elif cmd == "set-snapshot":
                seek = float(args[1]) if len(args) > 1 else 1.0
                if not math.isfinite(seek):
                    skin.error(f"set-snapshot: time expects a finite number, got '{seek}'")
                    continue
                session.mutate(f"set-snapshot {args[0]}",
                               lambda j: j.__setitem__("snapshot",
                                    {"path": str(Path(args[0])),
                                     "time": seek, "ratio": 1}))
                _persist(); skin.success("snapshot configured")
            elif cmd == "clear":
                session.mutate("clear", lambda j: j.clear() or j.update(proj.new_job()))
                _persist(); skin.success("job cleared")
            elif cmd == "show":
                skin.status_block({k: str(v) for k, v in proj.job_summary(session.job).items()})
            elif cmd == "transcode":
                res = run_transcode(session.job); _persist()
                skin.success(f"transcoded -> {res['output']} ({res['file_size']} bytes)")
            elif cmd == "stream":
                res = run_stream(session.job); skin.success(res["note"])
            elif cmd == "snapshot":
                res = run_snapshot(session.job); skin.success(f"snapshot -> {res['snapshot']}")
            elif cmd == "info":
                skin.status_block({k: str(v) for k, v in run_info(Path(args[0])).items() if v is not None})
            elif cmd == "undo":
                label = session.undo()
                _persist()
                skin.info(f"undid: {label}" if label else "nothing to undo")
            elif cmd == "redo":
                label = session.redo()
                _persist()
                skin.info(f"redid: {label}" if label else "nothing to redo")
            else:
                skin.error(f"unknown command: {cmd} (type 'help')")
        except Exception as e:  # noqa: BLE001
            skin.error(str(e))


if __name__ == "__main__":
    cli()
