#!/usr/bin/env python3
"""quietshrink agent-native CLI — wraps the bash CLI with structured output."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import click

from . import __version__

# Find the bash CLI: prefer $PATH (installed), fall back to bundled (dev mode)
PACKAGE_DIR = Path(__file__).parent
# Walk up to project root (cli_anything/quietshrink → cli_anything → agent-harness → project_root)
BUNDLED_BIN = PACKAGE_DIR.parent.parent.parent / "bin" / "quietshrink"


def find_bash_cli() -> Path:
    """Locate the quietshrink bash binary."""
    in_path = shutil.which("quietshrink")
    if in_path:
        return Path(in_path)
    if BUNDLED_BIN.exists():
        return BUNDLED_BIN
    raise click.ClickException(
        "quietshrink bash CLI not found. Install via:\n"
        "  curl -fsSL https://raw.githubusercontent.com/achiya-automation/quietshrink/main/install.sh | bash"
    )


def emit(data: dict, json_mode: bool) -> None:
    """Emit data as JSON or pretty-printed."""
    if json_mode:
        click.echo(json.dumps(data, indent=2))
    else:
        for k, v in data.items():
            click.echo(f"{k}: {v}")


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="cli-anything-quietshrink")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Agent-native CLI for quietshrink — Apple Silicon screen recording compressor.

    Designed for AI agents (Claude Code, OpenClaw, Cursor) — every command supports
    --json for machine-readable output and exits with proper error codes.
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@click.argument("input_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("output_path", type=click.Path(dir_okay=False, path_type=Path), required=False)
@click.option(
    "--quality", "-q",
    type=click.Choice(["tiny", "balanced", "transparent", "pristine"]),
    default="transparent",
    help="Quality preset",
)
@click.option("--gop", "-g", type=int, default=600, help="GOP size")
@click.option("--audio", "-a", default="96k", help="Audio bitrate")
@click.option("--replace", is_flag=True, help="Replace input file with compressed version")
@click.option("--json", "json_mode", is_flag=True, help="JSON output")
def compress(
    input_path: Path,
    output_path: Optional[Path],
    quality: str,
    gop: int,
    audio: str,
    replace: bool,
    json_mode: bool,
) -> None:
    """Compress a video file. Returns size statistics."""
    bash_cli = find_bash_cli()
    args = [
        str(bash_cli),
        "--quality", quality,
        "--gop", str(gop),
        "--audio", audio,
        "--json",
    ]
    if replace:
        args.append("--replace")
    args.append(str(input_path))
    if output_path:
        args.append(str(output_path))

    try:
        result = subprocess.run(args, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        emit({"error": "compression_failed", "stderr": e.stderr.strip()}, json_mode)
        sys.exit(1)

    try:
        data = json.loads(result.stdout)
        emit(data, json_mode)
    except json.JSONDecodeError as e:
        emit({"error": "invalid_output", "raw": result.stdout, "detail": str(e)}, json_mode)
        sys.exit(1)


@cli.command()
@click.argument("input_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--json", "json_mode", is_flag=True, help="JSON output")
def probe(input_path: Path, json_mode: bool) -> None:
    """Inspect a video file before compression. Returns codec, resolution, duration, size."""
    if not shutil.which("ffprobe"):
        emit({"error": "ffprobe not found", "hint": "brew install ffmpeg"}, json_mode)
        sys.exit(2)

    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_name,width,height,r_frame_rate",
        "-show_entries", "format=duration,bit_rate,size",
        "-of", "json",
        str(input_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        probe_data = json.loads(result.stdout)
        size = input_path.stat().st_size
        video_stream = next((s for s in probe_data.get("streams", []) if s.get("codec_name") not in ("aac", "mp3")), {})
        duration = float(probe_data.get("format", {}).get("duration", 0))

        info = {
            "path": str(input_path),
            "size_bytes": size,
            "size_mb": round(size / 1024 / 1024, 2),
            "codec": video_stream.get("codec_name"),
            "width": video_stream.get("width"),
            "height": video_stream.get("height"),
            "framerate": video_stream.get("r_frame_rate"),
            "duration_seconds": round(duration, 2),
        }
        emit(info, json_mode)
    except subprocess.CalledProcessError as e:
        emit({"error": "probe_failed", "stderr": e.stderr.strip()}, json_mode)
        sys.exit(1)


@cli.command()
@click.option("--json", "json_mode", is_flag=True, help="JSON output")
def presets(json_mode: bool) -> None:
    """List available quality presets with their characteristics."""
    presets_data = [
        {"name": "tiny",        "q_value": 50, "typical_reduction": "~90%", "ssim": "~0.95",  "use_case": "chat / email"},
        {"name": "balanced",    "q_value": 55, "typical_reduction": "~88%", "ssim": "~0.99",  "use_case": "docs / sharing"},
        {"name": "transparent", "q_value": 60, "typical_reduction": "~87%", "ssim": "~0.99+", "use_case": "default — visually lossless"},
        {"name": "pristine",    "q_value": 70, "typical_reduction": "~84%", "ssim": "~0.997", "use_case": "archival / editing"},
    ]
    if json_mode:
        click.echo(json.dumps({"presets": presets_data}, indent=2))
    else:
        for p in presets_data:
            click.echo(f"  {p['name']:<13} q={p['q_value']:<3} {p['typical_reduction']:<6} ssim={p['ssim']:<8} — {p['use_case']}")


@cli.command()
@click.option("--json", "json_mode", is_flag=True, help="JSON output")
def doctor(json_mode: bool) -> None:
    """Verify environment is set up correctly."""
    checks = []

    # Check ffmpeg
    ffmpeg = shutil.which("ffmpeg")
    checks.append({"check": "ffmpeg installed", "ok": bool(ffmpeg), "path": ffmpeg or "not found"})

    # Check hevc_videotoolbox
    if ffmpeg:
        try:
            result = subprocess.run(
                [ffmpeg, "-hide_banner", "-encoders"],
                capture_output=True, text=True, check=True,
            )
            has_vt = "hevc_videotoolbox" in result.stdout
            checks.append({"check": "hevc_videotoolbox available", "ok": has_vt})
        except subprocess.CalledProcessError:
            checks.append({"check": "hevc_videotoolbox available", "ok": False})

    # Check bash CLI
    try:
        find_bash_cli()
        checks.append({"check": "quietshrink bash CLI", "ok": True})
    except click.ClickException:
        checks.append({"check": "quietshrink bash CLI", "ok": False})

    # Platform check
    import platform
    is_arm_mac = platform.system() == "Darwin" and platform.machine() == "arm64"
    checks.append({"check": "Apple Silicon Mac", "ok": is_arm_mac})

    all_ok = all(c["ok"] for c in checks)

    if json_mode:
        click.echo(json.dumps({"checks": checks, "ready": all_ok}, indent=2))
    else:
        for c in checks:
            mark = "✓" if c["ok"] else "✗"
            click.echo(f"  {mark} {c['check']}")
        click.echo()
        click.echo("Ready" if all_ok else "Setup incomplete")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    cli()
