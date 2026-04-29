#!/usr/bin/env python3
"""Browser CLI — A command-line interface for browser automation via DOMShell MCP.

This CLI provides filesystem-first browser automation using Chrome's Accessibility Tree.
Navigate web pages using familiar shell commands: ls, cd, cat, grep, click.

Usage:
    # One-shot commands
    cli-anything-browser page open https://example.com
    cli-anything-browser fs ls /
    cli-anything-browser act click /main/button[0]
    cli-anything-browser --json fs cat /main/title

    # Interactive REPL
    cli-anything-browser
"""

import sys
import json
import shlex
import click
from typing import Optional

from cli_anything.browser.core.session import Session
from cli_anything.browser.core import page as page_mod
from cli_anything.browser.core import fs as fs_mod
from cli_anything.browser.utils import domshell_backend as backend

# Global state
_session: Optional[Session] = None
_json_output = False
_repl_mode = False
_availability_cached: Optional[tuple[bool, str]] = None  # Cache for REPL mode


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
        else:
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
        except (ValueError, IndexError) as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": type(e).__name__}))
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
@click.option("--daemon", "use_daemon", is_flag=True,
              help="Use persistent daemon mode (faster for interactive use)")
@click.pass_context
def cli(ctx, use_json, use_daemon):
    """Browser CLI — Filesystem-first browser automation via DOMShell.

    Run without a subcommand to enter interactive REPL mode.
    """
    global _json_output, _session, _availability_cached
    _json_output = use_json

    # Check DOMShell availability (skip for help/version to allow viewing docs without DOMShell)
    # Cache the result for REPL mode to avoid repeated npx subprocess spawns
    if '--help' not in sys.argv and '--version' not in sys.argv:
        if _availability_cached is None:
            _availability_cached = backend.is_available()
        available, msg = _availability_cached
        if not available:
            if _json_output:
                click.echo(json.dumps({"error": msg, "type": "dependency_error"}))
            else:
                click.echo(f"Error: {msg}", err=True)
                click.echo(
                    "\nInstall DOMShell Chrome extension:\n"
                    "  https://chromewebstore.google.com/detail/domshell"
                )
            sys.exit(1)

    # Initialize session with daemon mode
    _session = get_session()
    if use_daemon:
        try:
            backend.start_daemon()
            _session.enable_daemon()
            if not _json_output:
                click.echo("Daemon mode: persistent MCP connection active")
        except RuntimeError as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": "daemon_error"}))
            else:
                click.echo(f"Daemon start failed: {e}", err=True)
                click.echo("Falling back to per-command mode", err=True)

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── Page Commands ───────────────────────────────────────────────
@cli.group()
def page():
    """Page navigation commands."""
    pass


@page.command("open")
@click.argument("url")
@handle_error
def page_open(url):
    """Open a URL in Chrome."""
    sess = get_session()
    result = page_mod.open_page(sess, url)
    output(result, f"Opened: {url}")


@page.command("reload")
@handle_error
def page_reload():
    """Reload the current page."""
    sess = get_session()
    result = page_mod.reload_page(sess)
    output(result, "Page reloaded")


@page.command("back")
@handle_error
def page_back():
    """Navigate back in history."""
    sess = get_session()
    result = page_mod.go_back(sess)
    if "error" in result:
        output(result, result["error"])
    else:
        output(result, "Navigated back")


@page.command("forward")
@handle_error
def page_forward():
    """Navigate forward in history."""
    sess = get_session()
    result = page_mod.go_forward(sess)
    if "error" in result:
        output(result, result["error"])
    else:
        output(result, "Navigated forward")


@page.command("info")
@handle_error
def page_info():
    """Show current page information."""
    sess = get_session()
    result = page_mod.get_page_info(sess)
    output(result)


# ── Filesystem Commands ──────────────────────────────────────────
@cli.group()
def fs():
    """Filesystem navigation commands (Accessibility Tree)."""
    pass


@fs.command("ls")
@click.argument("path", default="", required=False)
@handle_error
def fs_ls(path):
    """List elements at a path in the accessibility tree."""
    sess = get_session()
    result = fs_mod.list_elements(sess, path)
    if _json_output:
        output(result)
    else:
        entries = result.get("entries", [])
        if not entries:
            click.echo(f"No elements at {path or sess.working_dir}")
            return
        click.echo(f"{'NAME':<40} {'ROLE':<20} {'PATH'}")
        click.echo("─" * 80)
        for entry in entries:
            name = entry.get("name", "")
            role = entry.get("role", "")
            entry_path = entry.get("path", "")
            click.echo(f"{name:<40} {role:<20} {entry_path}")


@fs.command("cd")
@click.argument("path")
@handle_error
def fs_cd(path):
    """Change directory in the accessibility tree."""
    sess = get_session()
    result = fs_mod.change_directory(sess, path)
    if "error" in result:
        output(result, result["error"])
    else:
        output(result, f"Changed to: {sess.working_dir}")


@fs.command("cat")
@click.argument("path", default="", required=False)
@handle_error
def fs_cat(path):
    """Read element content from the accessibility tree."""
    sess = get_session()
    result = fs_mod.read_element(sess, path)
    output(result)


@fs.command("grep")
@click.argument("pattern")
@click.argument("path", default="", required=False)
@handle_error
def fs_grep(pattern, path):
    """Search for pattern in the accessibility tree."""
    sess = get_session()
    result = fs_mod.grep_elements(sess, pattern, path)
    if _json_output:
        output(result)
    else:
        matches = result.get("matches", [])
        if not matches:
            click.echo(f"No matches for '{pattern}'")
            return
        click.echo(f"Matches for '{pattern}':")
        for match in matches:
            click.echo(f"  {match}")


@fs.command("pwd")
@handle_error
def fs_pwd():
    """Print current working directory in accessibility tree."""
    sess = get_session()
    click.echo(sess.working_dir)


# ── Action Commands ──────────────────────────────────────────────
@cli.group()
def act():
    """Action commands on elements."""
    pass


@act.command("click")
@click.argument("path")
@handle_error
def act_click(path):
    """Click an element at the given path."""
    sess = get_session()
    use_daemon = sess.daemon_mode
    result = backend.click(path, use_daemon=use_daemon)
    output(result, f"Clicked: {path}")


@act.command("type")
@click.argument("path")
@click.argument("text")
@handle_error
def act_type(path, text):
    """Type text into an input element."""
    sess = get_session()
    use_daemon = sess.daemon_mode
    result = backend.type_text(path, text, use_daemon=use_daemon)
    output(result, f"Typed into: {path}")


# ── Session Commands ─────────────────────────────────────────────
@cli.group()
def session():
    """Session management commands."""
    pass


@session.command("status")
@handle_error
def session_status():
    """Show current session status."""
    sess = get_session()
    status = sess.status()
    output(status)


@session.command("daemon-start")
@handle_error
def session_daemon_start():
    """Start persistent daemon mode."""
    try:
        backend.start_daemon()
        get_session().enable_daemon()
        output({"daemon": "started"}, "Daemon mode started")
    except RuntimeError as e:
        output({"error": str(e)}, str(e))


@session.command("daemon-stop")
@handle_error
def session_daemon_stop():
    """Stop persistent daemon mode."""
    backend.stop_daemon()
    get_session().disable_daemon()
    output({"daemon": "stopped"}, "Daemon mode stopped")


# ── REPL ─────────────────────────────────────────────────────────
@cli.command()
@handle_error
def repl():
    """Start interactive REPL session."""
    from cli_anything.browser.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True

    skin = ReplSkin("browser", version="1.0.0")
    skin.print_banner()

    pt_session = skin.create_prompt_session()

    _repl_commands = {
        "page":     "open|reload|back|forward|info",
        "fs":       "ls|cd|cat|grep|pwd",
        "act":      "click|type",
        "session":  "status|daemon-start|daemon-stop",
        "help":     "Show this help",
        "quit":     "Exit REPL",
    }

    while True:
        try:
            sess = get_session()
            # Show URL and working dir in prompt
            context = sess.working_dir if sess.working_dir != "/" else "/"
            if sess.current_url:
                # Truncate long URLs for prompt
                url_display = sess.current_url[:40] + "..." if len(sess.current_url) > 40 else sess.current_url
                context = f"{url_display} {context}"

            line = skin.get_input(pt_session, context=context)
            if not line:
                continue
            if line.lower() in ("quit", "exit", "q"):
                skin.print_goodbye()
                break
            if line.lower() == "help":
                skin.help(_repl_commands)
                continue

            # Parse and execute command (preserve quoted arguments)
            try:
                args = shlex.split(line)
            except ValueError:
                args = line.split()  # Fallback for unbalanced quotes
            # Propagate --json from top-level to subcommands in REPL
            if _json_output and '--json' not in args and not any(a.startswith('--json') for a in args):
                args = ['--json'] + args
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


# ── Entry Point ──────────────────────────────────────────────────
def main():
    cli()


if __name__ == "__main__":
    main()
