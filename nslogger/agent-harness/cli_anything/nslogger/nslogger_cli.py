"""cli-anything-nslogger — CLI harness for NSLogger."""
from __future__ import annotations
import json
import sys
import os
from datetime import datetime, timezone
from typing import Optional

import click

from .core.parser import parse_file
from .core.filter import filter_messages
from .core.stats import compute_stats
from .core.exporter import export_messages
from .core.message import LEVEL_NAMES, MSG_TYPE_CLIENT_INFO


CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


def _level_option():
    return click.option(
        "--level", "-l",
        type=int, default=None,
        help="Maximum log level to show (0=error … 4=verbose)",
    )


def _json_option():
    return click.option("--json", "as_json", is_flag=True, help="Output as JSON")


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO-like datetime string to aware UTC datetime."""
    if value is None:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%H:%M:%S"):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.year == 1900:
                today = datetime.now(tz=timezone.utc).date()
                dt = dt.replace(year=today.year, month=today.month, day=today.day)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise click.BadParameter(f"Cannot parse datetime: {value!r}. Use HH:MM:SS or YYYY-MM-DDTHH:MM:SS")


def _time_range_options():
    def decorator(f):
        f = click.option("--after", default=None,
                         help="Show messages after this time (HH:MM:SS or YYYY-MM-DDTHH:MM:SS)")(f)
        f = click.option("--before", default=None,
                         help="Show messages before this time (HH:MM:SS or YYYY-MM-DDTHH:MM:SS)")(f)
        return f
    return decorator


def _listen_waiting_message(port: int, bonjour: bool) -> str:
    if bonjour:
        return f"[Bonjour] Waiting for an iOS client to connect on port {port}…"
    return f"Waiting for a client connection on port {port}…"


def _format_live_output_message(msg, fmt: str) -> str:
    if fmt == "jsonl":
        return json.dumps(msg.to_dict(), default=str)
    return msg.to_text_line()


def _open_live_output_file(path: str, append: bool):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    mode = "a" if append else "w"
    return open(path, mode, encoding="utf-8", buffering=1)


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(package_name="cli-anything-nslogger")
def cli():
    """NSLogger CLI — read, filter, export, and monitor NSLogger log files.

    \b
    Use COMMAND -h to see command-specific options, for example:
      cli-anything-nslogger listen -h

    \b
    Live logs can be mirrored to a file with:
      cli-anything-nslogger listen --bonjour --name bazinga --output app.log

    \b
    Live listen file output options:
      -o, --output FILE          Write live logs to FILE while printing stdout
      --output-format text|jsonl Write text lines or JSON Lines
      --append                   Append instead of replacing FILE on startup
    """


# ---------------------------------------------------------------------------
# read
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("file", type=click.Path(exists=True))
@_level_option()
@click.option("--tag", "-t", multiple=True, help="Filter by tag (repeatable)")
@click.option("--thread", help="Filter by thread ID")
@click.option("--search", "-s", help="Text search (case-insensitive)")
@click.option("--limit", "-n", type=int, default=None, help="Max messages to show")
@click.option("--after", default=None, help="Show messages after this time (HH:MM:SS or YYYY-MM-DDTHH:MM:SS)")
@click.option("--before", default=None, help="Show messages before this time (HH:MM:SS or YYYY-MM-DDTHH:MM:SS)")
@_json_option()
def read(file, level, tag, thread, search, limit, after, before, as_json):
    """Parse and display messages from a .rawnsloggerdata or .nsloggerdata file."""
    msgs = parse_file(file)
    msgs = filter_messages(
        msgs,
        max_level=level,
        tags=list(tag) if tag else None,
        thread_id=thread,
        text_search=search,
        limit=limit,
        after=_parse_dt(after),
        before=_parse_dt(before),
    )
    result = list(msgs)
    if as_json:
        click.echo(json.dumps([m.to_dict() for m in result], indent=2, default=str))
    else:
        for m in result:
            click.echo(m.to_text_line())


# ---------------------------------------------------------------------------
# filter
# ---------------------------------------------------------------------------

@cli.command(name="filter")
@click.argument("file", type=click.Path(exists=True))
@_level_option()
@click.option("--min-level", type=int, default=None, help="Minimum log level")
@click.option("--tag", "-t", multiple=True, help="Filter by tag")
@click.option("--thread", help="Filter by thread ID")
@click.option("--search", "-s", help="Substring search in message text")
@click.option("--regex", "-r", help="Regex search in message text")
@click.option("--type", "msg_type", multiple=True,
              type=click.Choice(["text", "image", "data", "client_info", "block_start", "block_end"]),
              help="Filter by message type")
@click.option("--limit", "-n", type=int, default=None, help="Max messages")
@click.option("--after", default=None, help="Show messages after this time (HH:MM:SS or YYYY-MM-DDTHH:MM:SS)")
@click.option("--before", default=None, help="Show messages before this time")
@click.option("--from-seq", type=int, default=None, help="Start from sequence number (inclusive)")
@click.option("--to-seq", type=int, default=None, help="End at sequence number (inclusive)")
@_json_option()
def filter_cmd(file, level, min_level, tag, thread, search, regex, msg_type, limit,
               after, before, from_seq, to_seq, as_json):
    """Filter messages from a file with advanced criteria."""
    msgs = parse_file(file)
    msgs = filter_messages(
        msgs,
        max_level=level,
        min_level=min_level,
        tags=list(tag) if tag else None,
        thread_id=thread,
        text_search=search,
        text_regex=regex,
        msg_types=list(msg_type) if msg_type else None,
        limit=limit,
        after=_parse_dt(after),
        before=_parse_dt(before),
        from_seq=from_seq,
        to_seq=to_seq,
    )
    result = list(msgs)
    if as_json:
        click.echo(json.dumps([m.to_dict() for m in result], indent=2, default=str))
    else:
        for m in result:
            click.echo(m.to_text_line())


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--format", "-f", "fmt",
              type=click.Choice(["text", "json", "csv"]), default="text",
              show_default=True, help="Output format")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Output file (default: stdout)")
@_level_option()
@click.option("--tag", "-t", multiple=True, help="Filter by tag before export")
@click.option("--search", "-s", help="Filter by text before export")
@click.option("--limit", "-n", type=int, default=None, help="Max messages")
def export(file, fmt, output, level, tag, search, limit):
    """Export messages to text, JSON, or CSV."""
    msgs = parse_file(file)
    msgs = filter_messages(
        msgs,
        max_level=level,
        tags=list(tag) if tag else None,
        text_search=search,
        limit=limit,
    )
    result_str = export_messages(msgs, fmt=fmt)
    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(result_str)
        click.echo(f"Exported to {output}", err=True)
    else:
        click.echo(result_str, nl=False)


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("file", type=click.Path(exists=True))
@_json_option()
def stats(file, as_json):
    """Show statistics for a NSLogger file."""
    msgs = parse_file(file)
    s = compute_stats(msgs)
    if as_json:
        click.echo(json.dumps(s, indent=2, default=str))
        return

    click.echo(f"Total messages : {s['total']}")
    if s.get("first_timestamp"):
        click.echo(f"First message  : {s['first_timestamp']}")
        click.echo(f"Last message   : {s['last_timestamp']}")
    if s.get("duration_seconds") is not None:
        click.echo(f"Duration       : {s['duration_seconds']:.1f}s")
    if s.get("clients"):
        click.echo(f"Clients        : {', '.join(s['clients'])}")
    click.echo("")
    click.echo("By level:")
    for name, count in s.get("by_level", {}).items():
        click.echo(f"  {name:<10} {count}")
    click.echo("")
    click.echo("By type:")
    for name, count in s.get("by_type", {}).items():
        click.echo(f"  {name:<15} {count}")
    if s.get("by_tag"):
        click.echo("")
        click.echo("Top tags:")
        for tag, count in list(s["by_tag"].items())[:10]:
            click.echo(f"  {tag:<20} {count}")
    if s.get("by_thread"):
        click.echo("")
        click.echo("Top threads:")
        for thread, count in list(s["by_thread"].items())[:5]:
            click.echo(f"  {thread:<25} {count}")


# ---------------------------------------------------------------------------
# listen
# ---------------------------------------------------------------------------

@cli.command(short_help="Listen for live logs; use --output FILE to mirror them to disk.")
@click.option("--port", "-p", type=int, default=50000, show_default=True,
              help="TCP port to listen on")
@click.option("--timeout", "-t", type=float, default=None,
              help="Stop after N seconds (default: run until Ctrl-C)")
@click.option("--level", "-l", type=int, default=None,
              help="Maximum level to display while listening")
@click.option("--bonjour", "-b", is_flag=True, default=False,
              help="Advertise via Bonjour/mDNS (iOS app auto-discovers, no IP config needed)")
@click.option("--name", "-n", default=None,
              help="Bonjour service name (default: system-selected name)")
@click.option("--ssl", "force_ssl", is_flag=True,
              help="Use SSL/TLS for direct TCP mode; Bonjour uses SSL by default")
@click.option("--no-ssl", is_flag=True, help="Advertise/use the legacy non-SSL NSLogger Bonjour service")
@click.option("--bonjour-mode", type=click.Choice(["auto", "ssl", "raw"]), default="ssl", show_default=True,
              help="Bonjour service mode: ssl matches NSLogger GUI default, auto publishes raw+SSL, raw publishes legacy raw only")
@click.option("--bonjour-publisher", type=click.Choice(["native", "dns-sd", "zeroconf"]), default="native", show_default=True,
              help="Bonjour publisher backend")
@click.option("--advertise-host", default=None,
              help="IP address to publish when using --bonjour-publisher zeroconf")
@click.option("--filter-clients/--no-filter-clients", default=None,
              help="Advertise filterClients=1; defaults to on when --name is non-empty, matching NSLogger GUI")
@click.option("--output", "-o", type=click.Path(dir_okay=False, path_type=str),
              help="Write received live logs to this file while still printing to stdout")
@click.option("--output-format", type=click.Choice(["text", "jsonl"]), default="text", show_default=True,
              help="Format used for --output")
@click.option("--append", is_flag=True,
              help="Append to --output instead of replacing it at listener startup")
@click.option("--debug", is_flag=True, help="Print live frame diagnostics to stderr")
@_json_option()
def listen(
    port, timeout, level, bonjour, name, force_ssl, no_ssl, bonjour_mode,
    bonjour_publisher, advertise_host, filter_clients, output, output_format,
    append, debug, as_json
):
    """Listen for live NSLogger connections.

    \b
    TCP mode (default):
      cli-anything-nslogger listen --port 50000

    Bonjour mode (iOS auto-discovers on same WiFi):
      cli-anything-nslogger listen --bonjour --name bazinga
    """
    from .core.listener import NSLoggerListener

    collected = []
    output_file = _open_live_output_file(output, append) if output else None

    def on_message(msg):
        if level is not None and msg.level > level:
            return
        collected.append(msg)
        if output_file:
            output_file.write(_format_live_output_message(msg, output_format) + "\n")
        if as_json:
            click.echo(json.dumps(msg.to_dict(), default=str))
        else:
            click.echo(msg.to_text_line())

    def on_connect(host, p):
        click.echo(f"[+] Client connected: {host}:{p}", err=True)

    def on_disconnect(host, p):
        click.echo(f"[-] Client disconnected: {host}:{p}", err=True)

    def on_bonjour_ready(svc_name, svc_port):
        click.echo(f"[Bonjour] Advertising as '{svc_name}' on port {svc_port}", err=True)
        click.echo(f"[Bonjour] iOS app will auto-discover — no IP config needed", err=True)

    def on_parse_error(host, p, raw, exc):
        if not debug:
            return
        head = raw[:32].hex(" ")
        click.echo(
            f"[debug] Dropped frame from {host}:{p}: len={len(raw)} head={head} error={exc}",
            err=True,
        )

    def on_debug(message):
        if debug:
            click.echo(f"[debug] {message}", err=True)

    if no_ssl:
        bonjour_mode = "raw"
    use_ssl = force_ssl
    if bonjour:
        use_ssl = False if bonjour_mode == "raw" else None
    allow_plaintext = bonjour_mode != "ssl"

    listener = NSLoggerListener(
        port=port,
        timeout=timeout,
        on_message=on_message,
        on_connect=on_connect,
        on_disconnect=on_disconnect,
        on_bonjour_ready=on_bonjour_ready,
        on_parse_error=on_parse_error,
        on_debug=on_debug,
        use_ssl=use_ssl,
        allow_plaintext=allow_plaintext,
        bonjour=bonjour,
        bonjour_name=name,
        filter_clients=filter_clients,
        bonjour_publisher=bonjour_publisher,
        advertise_host=advertise_host,
    )

    if bonjour:
        click.echo(f"Starting Bonjour listener on port {port}…  (Ctrl-C to stop)", err=True)
    else:
        click.echo(f"Listening on TCP port {port}…  (Ctrl-C to stop)", err=True)
    click.echo(_listen_waiting_message(port, bonjour), err=True)
    if output:
        action = "Appending" if append else "Writing"
        click.echo(f"[output] {action} live logs to {output} ({output_format})", err=True)

    try:
        listener.listen()
    except KeyboardInterrupt:
        pass
    finally:
        if output_file:
            output_file.close()
    click.echo(f"\nCaptured {len(collected)} messages.", err=True)


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("output", type=click.Path())
@click.option("--count", "-n", type=int, default=20, show_default=True,
              help="Number of log messages to generate")
def generate(output, count):
    """Generate a sample .rawnsloggerdata file for testing."""
    from .utils.generate import generate_sample_file
    generate_sample_file(output, count=count)
    click.echo(f"Generated {count} messages → {output}")


# ---------------------------------------------------------------------------
# tail
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--count", "-n", type=int, default=20, show_default=True,
              help="Number of messages from the end to show")
@_level_option()
@click.option("--tag", "-t", multiple=True, help="Filter by tag before tailing")
@_json_option()
def tail(file, count, level, tag, as_json):
    """Show the last N messages from a file (reverse of --limit in read)."""
    msgs = parse_file(file)
    msgs = filter_messages(
        msgs,
        max_level=level,
        tags=list(tag) if tag else None,
    )
    all_msgs = list(msgs)
    result = all_msgs[-count:]
    if as_json:
        click.echo(json.dumps([m.to_dict() for m in result], indent=2, default=str))
    else:
        for m in result:
            click.echo(m.to_text_line())


# ---------------------------------------------------------------------------
# clients
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("file", type=click.Path(exists=True))
@_json_option()
def clients(file, as_json):
    """List all client connections recorded in a NSLogger file."""
    from .core.blocks import extract_clients
    msgs = parse_file(file)
    client_list = extract_clients(msgs)
    if as_json:
        click.echo(json.dumps(client_list, indent=2, default=str))
    else:
        if not client_list:
            click.echo("No client_info messages found.")
            return
        for c in client_list:
            ts = c.get("timestamp") or "?"
            name = c.get("client_name") or "unknown"
            ver = c.get("client_version") or ""
            os_ = f"{c.get('os_name', '')} {c.get('os_version', '')}".strip()
            machine = c.get("machine") or ""
            click.echo(f"[{ts}] {name} {ver}  {os_}  {machine}".strip())


# ---------------------------------------------------------------------------
# blocks
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--indent", type=int, default=2, show_default=True,
              help="Spaces per indent level")
@_json_option()
def blocks(file, indent, as_json):
    """Show the block start/end structure from a NSLogger file as an indented tree."""
    from .core.blocks import iter_block_tree
    msgs = parse_file(file)
    entries = list(iter_block_tree(msgs))
    if as_json:
        result = [
            {"depth": depth, **m.to_dict()}
            for depth, m in entries
        ]
        click.echo(json.dumps(result, indent=2, default=str))
    else:
        for depth, m in entries:
            prefix = " " * (depth * indent)
            click.echo(f"{prefix}{m.to_text_line()}")


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Write merged output to file (default: stdout)")
@click.option("--format", "-f", "fmt",
              type=click.Choice(["text", "json", "csv"]), default="text",
              show_default=True)
@_level_option()
def merge(files, output, fmt, level):
    """Merge multiple NSLogger files, sorted by timestamp."""
    from .core.blocks import merge_files
    all_msgs = merge_files(list(files))
    if level is not None:
        all_msgs = [m for m in all_msgs if m.level <= level]
    from .core.exporter import export_messages
    result_str = export_messages(iter(all_msgs), fmt=fmt)
    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(result_str)
        click.echo(f"Merged {len(files)} files → {output}", err=True)
    else:
        click.echo(result_str, nl=False)


# ---------------------------------------------------------------------------
# repl (interactive shell)
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("file", type=click.Path(exists=True), required=False)
def repl(file):
    """Start an interactive REPL for exploring NSLogger files."""
    try:
        import code
        import readline  # noqa: F401
    except ImportError:
        pass

    context = {}
    if file:
        msgs = list(parse_file(file))
        context["messages"] = msgs
        context["file"] = file
        click.echo(f"Loaded {len(msgs)} messages from {file}")
        click.echo("Available: messages, filter_messages, compute_stats, export_messages")
    else:
        click.echo("NSLogger REPL — no file loaded. Use: messages = list(parse_file('x.rawnsloggerdata'))")

    context.update({
        "parse_file": parse_file,
        "filter_messages": filter_messages,
        "compute_stats": compute_stats,
        "export_messages": export_messages,
    })

    import code as _code
    _code.interact(local=context, banner="")


def main():
    cli()


if __name__ == "__main__":
    main()
