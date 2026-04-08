#!/usr/bin/env python3
"""VideoCaptioner CLI — AI-powered video captioning from the command line.

Transcribe speech, optimize and translate subtitles, then burn them into
video with beautiful customizable styles (ASS outline or rounded background).

Usage:
    cli-anything-videocaptioner transcribe video.mp4 --asr bijian
    cli-anything-videocaptioner subtitle input.srt --translator bing --target-language en
    cli-anything-videocaptioner synthesize video.mp4 -s sub.srt --subtitle-mode hard --style anime
    cli-anything-videocaptioner process video.mp4 --asr bijian --translator bing --target-language ja
    cli-anything-videocaptioner --json transcribe video.mp4 --asr bijian
"""

import sys
import json
import shlex
import click
from typing import Optional

from cli_anything.videocaptioner.utils import vc_backend
from cli_anything.videocaptioner.core import transcribe as transcribe_mod
from cli_anything.videocaptioner.core import subtitle as subtitle_mod
from cli_anything.videocaptioner.core import synthesize as synthesize_mod
from cli_anything.videocaptioner.core import pipeline as pipeline_mod

_json_output = False
_repl_mode = False


def output(data, message: str = ""):
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        if isinstance(data, dict):
            for k, v in data.items():
                click.echo(f"  {k}: {v}")
        elif isinstance(data, str):
            click.echo(data)


def handle_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RuntimeError as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": "runtime_error"}))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


# ── Main CLI Group ──────────────────────────────────────────────
@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.pass_context
def cli(ctx, use_json):
    """VideoCaptioner CLI — AI-powered video captioning.

    Transcribe speech, optimize/translate subtitles, burn into video with
    beautiful styles. Free ASR (bijian) and translation (Bing/Google) included.

    Run without a subcommand to enter interactive REPL mode.
    """
    global _json_output
    _json_output = use_json
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── Transcribe ──────────────────────────────────────────────────
@cli.command()
@click.argument("input_path")
@click.option("--asr", type=click.Choice(["bijian", "jianying", "whisper-api", "whisper-cpp"]),
              default="bijian", help="ASR engine (bijian/jianying: free, Chinese & English only)")
@click.option("--language", default="auto", help="Source language ISO 639-1 code, or 'auto'")
@click.option("--format", "fmt", type=click.Choice(["srt", "ass", "txt", "json"]),
              default="srt", help="Output format")
@click.option("-o", "--output", "output_path", default=None, help="Output file or directory path")
@click.option("--word-timestamps", is_flag=True, help="Include word-level timestamps")
@click.option("--whisper-api-key", default=None, help="Whisper API key")
@click.option("--whisper-api-base", default=None, help="Whisper API base URL")
@click.option("--whisper-model", default=None, help="Whisper model name")
@handle_error
def transcribe(input_path, asr, language, fmt, output_path, word_timestamps,
               whisper_api_key, whisper_api_base, whisper_model):
    """Transcribe audio/video to subtitles."""
    result_path = transcribe_mod.transcribe(
        input_path, output_path=output_path, asr=asr, language=language,
        format=fmt, word_timestamps=word_timestamps,
        whisper_api_key=whisper_api_key, whisper_api_base=whisper_api_base,
        whisper_model=whisper_model,
    )
    output({"output_path": result_path}, f"✓ Transcription complete → {result_path}")


# ── Subtitle ────────────────────────────────────────────────────
@cli.command()
@click.argument("input_path")
@click.option("--translator", type=click.Choice(["llm", "bing", "google"]),
              default=None, help="Translation service (bing/google: free)")
@click.option("--target-language", default=None, help="Target language BCP 47 code (e.g. en, ja, ko)")
@click.option("--format", "fmt", type=click.Choice(["srt", "ass", "txt", "json"]),
              default="srt", help="Output format")
@click.option("-o", "--output", "output_path", default=None, help="Output file or directory path")
@click.option("--layout", type=click.Choice(["target-above", "source-above", "target-only", "source-only"]),
              default=None, help="Bilingual subtitle layout")
@click.option("--no-optimize", is_flag=True, help="Skip LLM optimization")
@click.option("--no-translate", is_flag=True, help="Skip translation")
@click.option("--no-split", is_flag=True, help="Skip re-segmentation")
@click.option("--reflect", is_flag=True, help="Reflective translation (LLM only, higher quality)")
@click.option("--prompt", default=None, help="Custom LLM prompt")
@click.option("--api-key", default=None, help="LLM API key")
@click.option("--api-base", default=None, help="LLM API base URL")
@click.option("--model", default=None, help="LLM model name")
@handle_error
def subtitle(input_path, translator, target_language, fmt, output_path, layout,
             no_optimize, no_translate, no_split, reflect, prompt, api_key, api_base, model):
    """Optimize and/or translate subtitle files.

    Three processing steps (all enabled by default except translation):
      1. Split — re-segment by semantic boundaries (LLM)
      2. Optimize — fix ASR errors, punctuation (LLM)
      3. Translate — to another language (LLM/Bing/Google)

    Use --translator or --target-language to enable translation.
    """
    result_path = subtitle_mod.process_subtitle(
        input_path, output_path=output_path, translator=translator,
        target_language=target_language, format=fmt, layout=layout,
        no_optimize=no_optimize, no_translate=no_translate, no_split=no_split,
        reflect=reflect, prompt=prompt, api_key=api_key, api_base=api_base, model=model,
    )
    output({"output_path": result_path}, f"✓ Subtitle processing complete → {result_path}")


# ── Synthesize ──────────────────────────────────────────────────
@cli.command()
@click.argument("video_path")
@click.option("-s", "--subtitle", "subtitle_path", required=True, help="Subtitle file path")
@click.option("--subtitle-mode", type=click.Choice(["soft", "hard"]),
              default="soft", help="soft: embedded track, hard: burned into frames")
@click.option("--quality", type=click.Choice(["ultra", "high", "medium", "low"]),
              default="medium", help="Video quality (ultra=CRF18, high=CRF23, medium=CRF28, low=CRF32)")
@click.option("-o", "--output", "output_path", default=None, help="Output video file path")
@click.option("--layout", type=click.Choice(["target-above", "source-above", "target-only", "source-only"]),
              default=None, help="Bilingual subtitle layout")
@click.option("--render-mode", type=click.Choice(["ass", "rounded"]),
              default=None, help="ass: outline/shadow, rounded: background boxes")
@click.option("--style", default=None, help="Style preset (default, anime, vertical, rounded)")
@click.option("--style-override", default=None, help='Inline JSON, e.g. \'{"outline_color": "#ff0000"}\'')
@click.option("--font-file", default=None, help="Custom font file (.ttf/.otf)")
@handle_error
def synthesize(video_path, subtitle_path, subtitle_mode, quality, output_path,
               layout, render_mode, style, style_override, font_file):
    """Burn subtitles into video with customizable styles.

    Two rendering modes for beautiful subtitles:
      ASS — traditional outline/shadow (presets: default, anime, vertical)
      Rounded — modern rounded background boxes

    Use 'cli-anything-videocaptioner styles' to see all presets.
    """
    result_path = synthesize_mod.synthesize(
        video_path, subtitle_path, output_path=output_path,
        subtitle_mode=subtitle_mode, quality=quality, layout=layout,
        render_mode=render_mode, style=style, style_override=style_override,
        font_file=font_file,
    )
    output({"output_path": result_path}, f"✓ Video synthesis complete → {result_path}")


# ── Process (full pipeline) ─────────────────────────────────────
@cli.command()
@click.argument("input_path")
@click.option("--asr", type=click.Choice(["bijian", "jianying", "whisper-api", "whisper-cpp"]),
              default="bijian", help="ASR engine")
@click.option("--language", default="auto", help="Source language")
@click.option("--translator", type=click.Choice(["llm", "bing", "google"]),
              default=None, help="Translation service (bing/google: free)")
@click.option("--target-language", default=None, help="Target language BCP 47 code")
@click.option("--subtitle-mode", type=click.Choice(["soft", "hard"]), default="soft")
@click.option("--quality", type=click.Choice(["ultra", "high", "medium", "low"]), default="medium")
@click.option("-o", "--output", "output_path", default=None, help="Output file or directory path")
@click.option("--layout", type=click.Choice(["target-above", "source-above", "target-only", "source-only"]), default=None)
@click.option("--style", default=None, help="Style preset name")
@click.option("--style-override", default=None, help="Inline JSON style override")
@click.option("--render-mode", type=click.Choice(["ass", "rounded"]), default=None)
@click.option("--no-optimize", is_flag=True, help="Skip optimization")
@click.option("--no-translate", is_flag=True, help="Skip translation")
@click.option("--no-split", is_flag=True, help="Skip re-segmentation")
@click.option("--no-synthesize", is_flag=True, help="Skip video synthesis")
@click.option("--reflect", is_flag=True, help="Reflective translation (LLM only)")
@click.option("--prompt", default=None, help="Custom LLM prompt")
@click.option("--api-key", default=None, help="LLM API key")
@click.option("--api-base", default=None, help="LLM API base URL")
@click.option("--model", default=None, help="LLM model name")
@handle_error
def process(input_path, asr, language, translator, target_language, subtitle_mode,
            quality, output_path, layout, style, style_override, render_mode,
            no_optimize, no_translate, no_split, no_synthesize, reflect,
            prompt, api_key, api_base, model):
    """Full pipeline: transcribe → optimize → translate → synthesize.

    One command to go from video to captioned video with translated subtitles.
    Audio files automatically skip video synthesis.
    """
    result_path = pipeline_mod.process(
        input_path, output_path=output_path, asr=asr, language=language,
        translator=translator, target_language=target_language,
        subtitle_mode=subtitle_mode, quality=quality, layout=layout,
        style=style, style_override=style_override, render_mode=render_mode,
        no_optimize=no_optimize, no_translate=no_translate, no_split=no_split,
        no_synthesize=no_synthesize, reflect=reflect, prompt=prompt,
        api_key=api_key, api_base=api_base, model=model,
    )
    output({"output_path": result_path}, f"✓ Pipeline complete → {result_path}")


# ── Styles ──────────────────────────────────────────────────────
@cli.command()
@handle_error
def styles():
    """List available subtitle style presets."""
    result = vc_backend.get_styles()
    if _json_output:
        click.echo(json.dumps({"styles": result}))
    else:
        click.echo(result)


# ── Config ──────────────────────────────────────────────────────
@cli.group()
def config():
    """View and manage configuration."""
    pass


@config.command("show")
@handle_error
def config_show():
    """Display current configuration."""
    result = vc_backend.get_config()
    if _json_output:
        click.echo(json.dumps({"config": result}))
    else:
        click.echo(result)


@config.command("set")
@click.argument("key")
@click.argument("value")
@handle_error
def config_set(key, value):
    """Set a configuration value."""
    result = vc_backend.run(["config", "set", key, value])
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"] or result["stdout"])
    output({"key": key, "value": value}, f"✓ {key} = {value}")


# ── Download ────────────────────────────────────────────────────
@cli.command()
@click.argument("url")
@click.option("-o", "--output", "output_dir", default=".", help="Output directory")
@handle_error
def download(url, output_dir):
    """Download online video (YouTube, Bilibili, etc.)."""
    result_path = vc_backend.run_quiet(["download", url, "-o", output_dir])
    output({"output_path": result_path}, f"✓ Downloaded → {result_path}")


# ── Session ─────────────────────────────────────────────────────
@cli.group()
def session():
    """Session state commands."""
    pass


@session.command("status")
@handle_error
def session_status():
    """Show VideoCaptioner version and configuration."""
    version = vc_backend.get_version()
    data = {"version": version, "json_output": _json_output}
    output(data, f"VideoCaptioner {version}")


# ── REPL ────────────────────────────────────────────────────────
@cli.command()
@handle_error
def repl():
    """Start interactive REPL session."""
    from cli_anything.videocaptioner.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True

    skin = ReplSkin("videocaptioner", version="1.0.0")
    skin.print_banner()

    pt_session = skin.create_prompt_session()

    _repl_commands = {
        "transcribe": "Transcribe audio/video to subtitles",
        "subtitle":   "Optimize and/or translate subtitles",
        "synthesize": "Burn subtitles into video",
        "process":    "Full pipeline (transcribe → translate → synthesize)",
        "styles":     "List subtitle style presets",
        "config":     "show|set <key> <value>",
        "download":   "Download online video",
        "session":    "status",
        "help":       "Show this help",
        "quit":       "Exit REPL",
    }

    while True:
        try:
            line = skin.get_input(pt_session, project_name="", modified=False)
            if not line:
                continue
            if line.lower() in ("quit", "exit", "q"):
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
            except Exception as e:
                skin.error(f"{e}")

        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

    _repl_mode = False


# ── Entry Point ─────────────────────────────────────────────────
def main():
    cli()


if __name__ == "__main__":
    main()
