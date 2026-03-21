#!/usr/bin/env python3
import sys, os, json, shlex, click
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cli_anything.sox.core.session import Session
from cli_anything.sox.core import effects as sox_effects

_session = None
_json_output = False
_repl_mode = False


def get_session():
    global _session
    if _session is None:
        _session = Session()
    return _session


def output(data, message=""):
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        if isinstance(data, dict):
            for k, v in data.items():
                click.echo(f"  {k}: {v}")
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    click.echo(f"  [{i}]")
                    for k, v in item.items():
                        click.echo(f"    {k}: {v}")
                else:
                    click.echo(f"  - {item}")
        else:
            click.echo(str(data))


def handle_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": type(e).__name__}))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True)
@click.pass_context
def cli(ctx, use_json):
    global _json_output
    _json_output = use_json
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.command()
@click.argument("file_path")
@handle_error
def info(file_path):
    """Get audio file info."""
    result = sox_effects.info(file_path)
    output(result)


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option("--sample-rate", type=int, default=None)
@click.option("--channels", type=int, default=None)
@click.option("--bits", type=int, default=None)
@click.option("--encoding", default=None)
@handle_error
def convert(input_path, output_path, sample_rate, channels, bits, encoding):
    """Convert audio format."""
    result = sox_effects.convert(
        input_path,
        output_path,
        sample_rate=sample_rate,
        channels=channels,
        bits=bits,
        encoding=encoding,
    )
    output(result)


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option("--start", type=float, default=None)
@click.option("--duration", type=float, default=None)
@handle_error
def trim(input_path, output_path, start, duration):
    """Trim audio segment."""
    result = sox_effects.trim(input_path, output_path, start=start, duration=duration)
    output(result)


@cli.command()
@click.argument("inputs", nargs=-1, required=True)
@click.option("--output", "output_path", required=True)
@handle_error
def concat(inputs, output_path):
    """Concatenate audio files."""
    result = sox_effects.concat(list(inputs), output_path)
    output(result)


@cli.command()
@click.argument("inputs", nargs=-1, required=True)
@click.option("--output", "output_path", required=True)
@click.option("--mix-type", default="mix")
@handle_error
def mix(inputs, output_path, mix_type):
    """Mix audio files together."""
    result = sox_effects.mix(list(inputs), output_path, mix_type=mix_type)
    output(result)


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option("--factor", type=float, required=True)
@handle_error
def speed(input_path, output_path, factor):
    """Change playback speed."""
    result = sox_effects.speed(input_path, output_path, factor=factor)
    output(result)


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option("--semitones", type=float, required=True)
@handle_error
def pitch(input_path, output_path, semitones):
    """Change pitch in semitones."""
    result = sox_effects.pitch(input_path, output_path, semitones=semitones)
    output(result)


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option("--factor", type=float, required=True)
@handle_error
def tempo(input_path, output_path, factor):
    """Change tempo without pitch."""
    result = sox_effects.tempo(input_path, output_path, factor=factor)
    output(result)


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option("--gain", type=float, required=True)
@handle_error
def volume(input_path, output_path, gain):
    """Adjust volume (dB)."""
    result = sox_effects.volume(input_path, output_path, gain=gain)
    output(result)


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@handle_error
def normalize(input_path, output_path):
    """Normalize audio levels."""
    result = sox_effects.normalize(input_path, output_path)
    output(result)


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@handle_error
def reverse(input_path, output_path):
    """Reverse audio."""
    result = sox_effects.reverse(input_path, output_path)
    output(result)


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option("--type", "fade_type", default="t")
@click.option("--fade-in", type=float, default=0)
@click.option("--fade-out", type=float, default=0)
@handle_error
def fade(input_path, output_path, fade_type, fade_in, fade_out):
    """Apply fade in/out."""
    result = sox_effects.fade(
        input_path, output_path, fade_type=fade_type, fade_in=fade_in, fade_out=fade_out
    )
    output(result)


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option("--threshold", type=float, default=1)
@click.option("--duration", type=float, default=0.1)
@handle_error
def silence(input_path, output_path, threshold, duration):
    """Remove silence from audio."""
    result = sox_effects.silence(
        input_path, output_path, threshold=threshold, duration=duration
    )
    output(result)


@cli.command()
@click.argument("file_path")
@handle_error
def stat(file_path):
    """Detailed audio statistics."""
    result = sox_effects.stat(file_path)
    output(result)


@cli.command()
@click.argument("input_path")
@click.argument("output_path")
@click.option("--width", type=int, default=800)
@click.option("--height", type=int, default=400)
@handle_error
def spectrogram(input_path, output_path, width, height):
    """Generate spectrogram image."""
    result = sox_effects.spectrogram(
        input_path, output_path, width=width, height=height
    )
    output(result)


@cli.command()
@click.argument("output_path")
@click.option("--type", "synth_type", default="sine")
@click.option("--frequency", type=float, default=440)
@click.option("--duration", type=float, default=3)
@handle_error
def synth(output_path, synth_type, frequency, duration):
    """Generate test tone."""
    result = sox_effects.synth(
        output_path, synth_type=synth_type, frequency=frequency, duration=duration
    )
    output(result)


@cli.group()
def effects():
    """SoX effects commands."""
    pass


@effects.command("list")
@handle_error
def effects_list():
    """List available SoX effects."""
    result = sox_effects.effects_list()
    output(result)


@cli.command()
@handle_error
def repl():
    """Start interactive REPL."""
    from cli_anything.sox.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True
    skin = ReplSkin("sox", version="1.0.0")
    skin.print_banner()
    pt_session = skin.create_prompt_session()
    commands = {
        "info": "Audio file metadata",
        "convert": "Convert audio format",
        "trim": "Trim audio segment",
        "concat": "Concatenate audio files",
        "mix": "Mix audio files",
        "speed": "Change playback speed",
        "pitch": "Change pitch (semitones)",
        "tempo": "Change tempo without pitch",
        "volume": "Adjust volume (dB)",
        "normalize": "Normalize levels",
        "reverse": "Reverse audio",
        "fade": "Apply fade in/out",
        "silence": "Remove silence",
        "stat": "Detailed statistics",
        "spectrogram": "Generate spectrogram",
        "synth": "Generate test tone",
        "effects list": "List available effects",
        "help": "Show this help",
        "quit": "Exit REPL",
    }
    while True:
        try:
            line = skin.get_input(pt_session)
            if not line:
                continue
            if line.lower() in ("quit", "exit", "q"):
                skin.print_goodbye()
                break
            if line.lower() == "help":
                skin.help(commands)
                continue
            try:
                args = shlex.split(line)
            except:
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


def main():
    cli()


if __name__ == "__main__":
    main()
