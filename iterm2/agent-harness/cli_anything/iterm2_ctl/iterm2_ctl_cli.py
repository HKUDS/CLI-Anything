#!/usr/bin/env python3
"""cli-anything-iterm2 — Stateful CLI harness for iTerm2.

Controls a running iTerm2 instance programmatically via the iTerm2 Python API.
Supports one-shot commands and an interactive REPL.

Usage:
    # One-shot commands
    cli-anything-iterm2 app status
    cli-anything-iterm2 window list
    cli-anything-iterm2 window create --profile "Default"
    cli-anything-iterm2 session send --session-id <id> "echo hello\\n"

    # Interactive REPL (default when invoked with no subcommand)
    cli-anything-iterm2
"""

import json
import os
import sys
from typing import Optional

import click

from cli_anything.iterm2_ctl.core import (
    arrangement as arr_mod,
    broadcast as bcast_mod,
    dialogs as dlg_mod,
    menu as menu_mod,
    pref as pref_mod,
    profile as profile_mod,
    prompt as prompt_mod,
    session as sess_mod,
    session_state,
    tab as tab_mod,
    tmux as tmux_mod,
    window as win_mod,
)
from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2

# ── Global state ───────────────────────────────────────────────────────
_json_output = False
_state: Optional[session_state.SessionState] = None


def get_state() -> session_state.SessionState:
    global _state
    if _state is None:
        _state = session_state.load_state()
    return _state


def save_state_now():
    global _state
    if _state is not None:
        session_state.save_state(_state)


def output(data, message: str = ""):
    """Print result as JSON (--json) or human-readable."""
    if _json_output:
        print(json.dumps(data, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        if data and not message:
            _print_data(data)


def _print_data(data, indent: int = 0):
    prefix = "  " * indent
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                click.echo(f"{prefix}{k}:")
                _print_data(v, indent + 1)
            else:
                click.echo(f"{prefix}{k}: {v}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                _print_data(item, indent)
                click.echo(f"{prefix}---")
            else:
                click.echo(f"{prefix}- {item}")
    else:
        click.echo(f"{prefix}{data}")


def handle_iterm2_error(func):
    """Decorator to format iTerm2 errors nicely."""
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RuntimeError as e:
            if _json_output:
                print(json.dumps({"error": str(e)}, indent=2))
            else:
                click.echo(f"Error: {e}", err=True)
            sys.exit(1)
        except ValueError as e:
            if _json_output:
                print(json.dumps({"error": str(e)}, indent=2))
            else:
                click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    return wrapper


# ── Root CLI ───────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, default=False,
              help="Output results as JSON (for agent use).")
@click.pass_context
def cli(ctx, use_json):
    """cli-anything-iterm2 — Control iTerm2 from the command line.

    Connects to a running iTerm2 instance via the iTerm2 Python API.
    Run without a subcommand to enter the interactive REPL.

    Prerequisites:
      1. iTerm2 must be running
      2. Python API enabled: Preferences → General → Magic → Enable Python API
    """
    global _json_output
    _json_output = use_json
    ctx.ensure_object(dict)
    ctx.obj["json"] = use_json

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


def main():
    cli()


# ── App group ──────────────────────────────────────────────────────────

@cli.group()
def app():
    """Application-level information and status."""


@app.command("status")
@handle_iterm2_error
def app_status():
    """Show current iTerm2 app status (windows, tabs, sessions)."""
    def _get_status(connection):
        import asyncio

        async def _inner(conn):
            import iterm2
            a = await iterm2.async_get_app(conn)
            windows = []
            for w in a.windows:
                tabs = []
                for t in w.tabs:
                    sessions = [{"session_id": s.session_id, "name": s.name}
                                for s in t.sessions]
                    tabs.append({"tab_id": t.tab_id, "sessions": sessions})
                windows.append({"window_id": w.window_id, "tabs": tabs})
            return {
                "window_count": len(a.windows),
                "windows": windows,
            }
        return _inner(connection)

    result = run_iterm2(_get_status)
    output(result, f"iTerm2: {result['window_count']} window(s)")


@app.command("current")
@handle_iterm2_error
def app_current():
    """Show the currently focused window/tab/session."""
    result = run_iterm2(win_mod.get_current_window)
    if result is None:
        output({"current": None}, "No window is currently focused.")
    else:
        state = get_state()
        state.window_id = result.get("window_id")
        state.tab_id = result.get("tab_id")
        state.session_id = result.get("session_id")
        save_state_now()
        output(result, f"Current: window={result.get('window_id')} "
               f"tab={result.get('tab_id')} session={result.get('session_id')}")


@app.command("context")
def app_context():
    """Show the saved session context (current window/tab/session IDs)."""
    state = get_state()
    data = state.to_dict()
    output(data, f"Context: {state.summary()}")


@app.command("set-context")
@click.option("--window-id", default=None, help="Window ID to set as current.")
@click.option("--tab-id", default=None, help="Tab ID to set as current.")
@click.option("--session-id", default=None, help="Session ID to set as current.")
def app_set_context(window_id, tab_id, session_id):
    """Manually set the session context (window/tab/session IDs)."""
    state = get_state()
    if window_id:
        state.window_id = window_id
    if tab_id:
        state.tab_id = tab_id
    if session_id:
        state.session_id = session_id
    save_state_now()
    output(state.to_dict(), f"Context updated: {state.summary()}")


@app.command("clear-context")
def app_clear_context():
    """Clear the saved session context."""
    state = get_state()
    state.clear()
    save_state_now()
    output({}, "Context cleared.")


@app.command("get-var")
@click.argument("variable_name")
@handle_iterm2_error
def app_get_var(variable_name):
    """Get an app-level iTerm2 variable."""
    def _get(conn):
        async def _inner(c):
            import iterm2
            a = await iterm2.async_get_app(c)
            value = await a.async_get_variable(variable_name)
            return {"variable": variable_name, "value": value}
        return _inner(conn)
    result = run_iterm2(_get)
    output(result, f"{variable_name} = {result['value']}")


@app.command("set-var")
@click.argument("variable_name")
@click.argument("value")
@handle_iterm2_error
def app_set_var(variable_name, value):
    """Set an app-level iTerm2 variable (user.* namespace)."""
    def _set(conn):
        async def _inner(c):
            import iterm2
            a = await iterm2.async_get_app(c)
            await a.async_set_variable(variable_name, value)
            return {"variable": variable_name, "value": value, "set": True}
        return _inner(conn)
    result = run_iterm2(_set)
    output(result, f"Set {variable_name} = {value}")


@app.command("alert")
@click.argument("title")
@click.argument("subtitle")
@click.option("--button", "buttons", multiple=True,
              help="Add a button label. Repeat for multiple buttons.")
@click.option("--window-id", default=None, help="Attach to a specific window.")
@handle_iterm2_error
def app_alert(title, subtitle, buttons, window_id):
    """Show a modal alert dialog with optional custom buttons.

    Returns the label of the button the user clicked.

    \b
      cli-anything-iterm2 app alert "Deploy?" "Push to production?"
      cli-anything-iterm2 app alert "Choose" "Pick one" --button Yes --button No
    """
    wid = window_id or get_state().window_id
    result = run_iterm2(dlg_mod.show_alert, title, subtitle,
                        buttons=list(buttons) or None, window_id=wid)
    output(result, f"Clicked: {result['button_label']}")


@app.command("text-input")
@click.argument("title")
@click.argument("subtitle")
@click.option("--placeholder", default="", help="Gray placeholder text.")
@click.option("--default", "default_value", default="", help="Pre-filled text.")
@click.option("--window-id", default=None)
@handle_iterm2_error
def app_text_input(title, subtitle, placeholder, default_value, window_id):
    """Show a modal alert with a text input field.

    Returns the text the user typed, or indicates cancellation.

    \b
      cli-anything-iterm2 app text-input "Rename" "Enter new name:" --default "myapp"
    """
    wid = window_id or get_state().window_id
    result = run_iterm2(dlg_mod.show_text_input, title, subtitle,
                        placeholder=placeholder, default_value=default_value,
                        window_id=wid)
    if result["cancelled"]:
        output(result, "Cancelled.")
    else:
        output(result, f"Input: {result['text']}")


@app.command("file-panel")
@click.option("--title", default="Open", help="Panel message text.")
@click.option("--path", default=None, help="Initial directory.")
@click.option("--ext", "extensions", multiple=True,
              help="Allowed extensions, e.g. --ext py --ext txt")
@click.option("--dirs", is_flag=True, default=False,
              help="Allow choosing directories.")
@click.option("--multi", is_flag=True, default=False,
              help="Allow multiple file selection.")
@handle_iterm2_error
def app_file_panel(title, path, extensions, dirs, multi):
    """Show a macOS Open File panel and return the chosen path(s).

    \b
      cli-anything-iterm2 app file-panel
      cli-anything-iterm2 app file-panel --path ~/Documents --ext py --ext txt
      cli-anything-iterm2 app file-panel --dirs --multi
    """
    result = run_iterm2(dlg_mod.show_open_panel, title, path=path,
                        extensions=list(extensions) or None,
                        can_choose_directories=dirs,
                        allows_multiple=multi)
    if result["cancelled"]:
        output(result, "Cancelled.")
    else:
        output(result, f"Selected: {', '.join(result['files'])}")


@app.command("save-panel")
@click.option("--title", default="Save", help="Panel message text.")
@click.option("--path", default=None, help="Initial directory.")
@click.option("--filename", default=None, help="Pre-filled filename.")
@handle_iterm2_error
def app_save_panel(title, path, filename):
    """Show a macOS Save File panel and return the chosen path.

    \b
      cli-anything-iterm2 app save-panel
      cli-anything-iterm2 app save-panel --path ~/Desktop --filename output.txt
    """
    result = run_iterm2(dlg_mod.show_save_panel, title, path=path, filename=filename)
    if result["cancelled"]:
        output(result, "Cancelled.")
    else:
        output(result, f"Save to: {result['file']}")


@app.command("snapshot")
@handle_iterm2_error
def app_snapshot():
    """Rich workspace snapshot: every session with path, process, role, and last output line.

    \b
    Use this to orient in an existing workspace without reading full screen contents
    for every pane. Returns name, current directory, foreground process, user.role
    label, and the last non-empty visible line for each session.

      cli-anything-iterm2 --json app snapshot
    """
    result = run_iterm2(sess_mod.workspace_snapshot)
    output(result, f"Workspace: {result['session_count']} session(s)")
    if not _json_output:
        for s in result["sessions"]:
            role_tag = f" [{s['role']}]" if s.get("role") else ""
            process_tag = f" ({s['process']})" if s.get("process") else ""
            path_tag = f"  {s['path']}" if s.get("path") else ""
            click.echo(f"  {s['session_id']}  {s['name']}{role_tag}{process_tag}{path_tag}")
            if s.get("last_line"):
                click.echo(f"    > {s['last_line']}")


# ── Window group ───────────────────────────────────────────────────────

@cli.group()
def window():
    """Manage iTerm2 windows."""


@window.command("list")
@handle_iterm2_error
def window_list():
    """List all open windows."""
    result = run_iterm2(win_mod.list_windows)
    output({"windows": result},
           f"{len(result)} window(s)" if result else "No windows open.")
    if not _json_output and result:
        for w in result:
            current_mark = " *" if w.get("is_current") else ""
            click.echo(f"  {w['window_id']}{current_mark}  "
                       f"tabs={w['tab_count']} sessions={w['session_count']}")


@window.command("create")
@click.option("--profile", "-p", default=None, help="Profile name.")
@click.option("--command", "-c", default=None, help="Command to run.")
@click.option("--use-as-context", is_flag=True, default=False,
              help="Save new window/tab/session as the current context.")
@handle_iterm2_error
def window_create(profile, command, use_as_context):
    """Create a new iTerm2 window."""
    result = run_iterm2(win_mod.create_window, profile=profile, command=command)
    if use_as_context:
        state = get_state()
        state.window_id = result.get("window_id")
        state.tab_id = result.get("tab_id")
        state.session_id = result.get("session_id")
        save_state_now()
    output(result, f"Created window {result['window_id']}")


@window.command("close")
@click.argument("window_id", required=False)
@click.option("--force", is_flag=True, default=False, help="Force close without confirmation.")
@handle_iterm2_error
def window_close(window_id, force):
    """Close a window. Uses context window if WINDOW_ID is omitted."""
    wid = window_id or get_state().window_id
    if not wid:
        raise click.UsageError("No window ID specified and no context window set. "
                               "Use 'app current' or 'app set-context' first.")
    result = run_iterm2(win_mod.close_window, wid, force=force)
    output(result, f"Closed window {wid}")


@window.command("activate")
@click.argument("window_id", required=False)
@handle_iterm2_error
def window_activate(window_id):
    """Bring a window to the foreground."""
    wid = window_id or get_state().window_id
    if not wid:
        raise click.UsageError("No window ID specified.")
    result = run_iterm2(win_mod.activate_window, wid)
    output(result, f"Activated window {wid}")


@window.command("set-title")
@click.argument("title")
@click.option("--window-id", default=None)
@handle_iterm2_error
def window_set_title(title, window_id):
    """Set the title of a window."""
    wid = window_id or get_state().window_id
    if not wid:
        raise click.UsageError("No window ID specified.")
    result = run_iterm2(win_mod.set_window_title, wid, title)
    output(result, f"Set title of {wid} to '{title}'")


@window.command("frame")
@click.option("--window-id", default=None)
@handle_iterm2_error
def window_frame(window_id):
    """Get the position and size of a window."""
    wid = window_id or get_state().window_id
    if not wid:
        raise click.UsageError("No window ID specified.")
    result = run_iterm2(win_mod.get_window_frame, wid)
    output(result, f"Window {wid}: x={result['x']} y={result['y']} "
           f"w={result['width']} h={result['height']}")


@window.command("set-frame")
@click.option("--window-id", default=None)
@click.option("--x", type=float, required=True)
@click.option("--y", type=float, required=True)
@click.option("--width", type=float, required=True)
@click.option("--height", type=float, required=True)
@handle_iterm2_error
def window_set_frame(window_id, x, y, width, height):
    """Set the position and size of a window."""
    wid = window_id or get_state().window_id
    if not wid:
        raise click.UsageError("No window ID specified.")
    result = run_iterm2(win_mod.set_window_frame, wid, x, y, width, height)
    output(result, f"Moved window {wid} to ({x},{y}) size {width}x{height}")


@window.command("fullscreen")
@click.argument("mode", type=click.Choice(["on", "off", "toggle", "status"]))
@click.option("--window-id", default=None)
@handle_iterm2_error
def window_fullscreen(mode, window_id):
    """Control fullscreen mode for a window."""
    wid = window_id or get_state().window_id
    if not wid:
        raise click.UsageError("No window ID specified.")
    if mode == "status":
        result = run_iterm2(win_mod.get_window_fullscreen, wid)
        output(result, f"Window {wid} fullscreen: {result['fullscreen']}")
    else:
        if mode == "toggle":
            status = run_iterm2(win_mod.get_window_fullscreen, wid)
            target = not status["fullscreen"]
        else:
            target = mode == "on"
        result = run_iterm2(win_mod.set_window_fullscreen, wid, target)
        output(result, f"Window {wid} fullscreen: {target}")


# ── Tab group ──────────────────────────────────────────────────────────

@cli.group()
def tab():
    """Manage tabs within iTerm2 windows."""


@tab.command("list")
@click.option("--window-id", default=None, help="Filter to specific window.")
@handle_iterm2_error
def tab_list(window_id):
    """List all tabs."""
    wid = window_id or get_state().window_id
    result = run_iterm2(tab_mod.list_tabs, window_id=wid)
    output({"tabs": result}, f"{len(result)} tab(s)")
    if not _json_output and result:
        for t in result:
            current_mark = " *" if t.get("is_current") else ""
            click.echo(f"  {t['tab_id']}{current_mark}  "
                       f"window={t['window_id']} sessions={t['session_count']}")


@tab.command("create")
@click.option("--window-id", default=None)
@click.option("--profile", "-p", default=None)
@click.option("--command", "-c", default=None)
@click.option("--use-as-context", is_flag=True, default=False)
@handle_iterm2_error
def tab_create(window_id, profile, command, use_as_context):
    """Create a new tab."""
    wid = window_id or get_state().window_id
    result = run_iterm2(tab_mod.create_tab, window_id=wid, profile=profile, command=command)
    if use_as_context:
        state = get_state()
        state.window_id = result.get("window_id")
        state.tab_id = result.get("tab_id")
        state.session_id = result.get("session_id")
        save_state_now()
    output(result, f"Created tab {result['tab_id']} in window {result['window_id']}")


@tab.command("close")
@click.argument("tab_id", required=False)
@click.option("--force", is_flag=True, default=False)
@handle_iterm2_error
def tab_close(tab_id, force):
    """Close a tab."""
    tid = tab_id or get_state().tab_id
    if not tid:
        raise click.UsageError("No tab ID specified.")
    result = run_iterm2(tab_mod.close_tab, tid, force=force)
    output(result, f"Closed tab {tid}")


@tab.command("activate")
@click.argument("tab_id", required=False)
@handle_iterm2_error
def tab_activate(tab_id):
    """Focus a tab."""
    tid = tab_id or get_state().tab_id
    if not tid:
        raise click.UsageError("No tab ID specified.")
    result = run_iterm2(tab_mod.activate_tab, tid)
    output(result, f"Activated tab {tid}")


@tab.command("info")
@click.argument("tab_id", required=False)
@handle_iterm2_error
def tab_info(tab_id):
    """Get details about a tab."""
    tid = tab_id or get_state().tab_id
    if not tid:
        raise click.UsageError("No tab ID specified.")
    result = run_iterm2(tab_mod.get_tab_info, tid)
    output(result)


@tab.command("select-pane")
@click.argument("direction", type=click.Choice(["left", "right", "above", "below"]))
@click.option("--tab-id", default=None)
@handle_iterm2_error
def tab_select_pane(direction, tab_id):
    """Move focus to the adjacent split pane in a direction.

    DIRECTION: left | right | above | below

    \b
      cli-anything-iterm2 tab select-pane right
      cli-anything-iterm2 tab select-pane below --tab-id <id>
    """
    tid = tab_id or get_state().tab_id
    if not tid:
        raise click.UsageError("No tab ID specified.")
    result = run_iterm2(tab_mod.select_pane_in_direction, tid, direction)
    if result["moved"]:
        output(result, f"Moved focus {direction} → session {result['new_session_id']}")
    else:
        output(result, f"No pane {direction} of current selection.")


# ── Session group ──────────────────────────────────────────────────────

@cli.group()
def session():
    """Manage terminal sessions (panes) within iTerm2 tabs."""


@session.command("list")
@click.option("--window-id", default=None)
@click.option("--tab-id", default=None)
@handle_iterm2_error
def session_list(window_id, tab_id):
    """List all sessions."""
    wid = window_id or get_state().window_id
    tid = tab_id or get_state().tab_id
    result = run_iterm2(sess_mod.list_sessions, window_id=wid, tab_id=tid)
    output({"sessions": result}, f"{len(result)} session(s)")
    if not _json_output and result:
        for s in result:
            current_mark = " *" if s.get("is_current") else ""
            click.echo(f"  {s['session_id']}{current_mark}  "
                       f"name={s['name'] or '(unnamed)'}  "
                       f"tab={s['tab_id']}")


@session.command("send")
@click.argument("text")
@click.option("--session-id", default=None)
@click.option("--no-newline", is_flag=True, default=False,
              help="Do not append a newline.")
@click.option("--suppress-broadcast", is_flag=True, default=False,
              help="Suppress sending to broadcast domains.")
@handle_iterm2_error
def session_send(text, session_id, no_newline, suppress_broadcast):
    """Send text to a session.

    TEXT: The text to send. Use \\n for newlines. A newline is appended
    unless --no-newline is given.

    Example:
        cli-anything-iterm2 session send "ls -la"
        cli-anything-iterm2 session send "pwd" --session-id w0t0p0
    """
    sid = session_id or get_state().session_id
    if not sid:
        raise click.UsageError("No session ID specified. Use --session-id or set context "
                               "with 'app current' or 'app set-context'.")
    payload = text if no_newline else (text + "\n")
    result = run_iterm2(sess_mod.send_text, sid, payload, suppress_broadcast=suppress_broadcast)
    output(result, f"Sent {result['text_length']} chars to session {sid}")


@session.command("screen")
@click.option("--session-id", default=None)
@click.option("--lines", "-n", type=int, default=None, help="Max lines to return.")
@handle_iterm2_error
def session_screen(session_id, lines):
    """Get the visible screen contents of a session."""
    sid = session_id or get_state().session_id
    if not sid:
        raise click.UsageError("No session ID specified.")
    result = run_iterm2(sess_mod.get_screen_contents, sid, lines=lines)
    output(result)
    if not _json_output:
        click.echo(f"  Session {sid}  ({result['returned_lines']}/{result['total_lines']} lines)")
        click.echo("  " + "─" * 60)
        for line in result["lines"]:
            click.echo(f"  {line}")


@session.command("scrollback")
@click.option("--session-id", default=None)
@click.option("--lines", "-n", type=int, default=None,
              help="Max lines to return (default: all).")
@click.option("--tail", "-t", type=int, default=None,
              help="Return only the last N lines (most recent). Overrides --lines.")
@click.option("--strip", is_flag=True, default=False,
              help="Strip null bytes and non-printable control characters.")
@handle_iterm2_error
def session_scrollback(session_id, lines, tail, strip):
    """Get the full scrollback buffer including history beyond the visible screen.

    Unlike 'screen' which only shows the visible terminal area, this reads
    the entire history buffer — everything since the session started (up to
    the scrollback limit).

    \b
      cli-anything-iterm2 session scrollback                  # all history
      cli-anything-iterm2 session scrollback --tail 100       # last 100 lines
      cli-anything-iterm2 session scrollback --lines 500      # first 500 lines
    """
    sid = session_id or get_state().session_id
    if not sid:
        raise click.UsageError("No session ID specified.")
    result = run_iterm2(sess_mod.get_scrollback, sid, lines=lines, tail=tail)
    if strip:
        import re
        result["lines"] = [
            re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", ln)
            for ln in result["lines"]
        ]
    output(result)
    if not _json_output:
        click.echo(f"  Session {sid}  ({result['returned_lines']} lines, "
                   f"scrollback={result['scrollback_lines']} screen={result['screen_lines']} "
                   f"overflow={result['overflow']})")
        click.echo("  " + "─" * 60)
        for line in result["lines"]:
            click.echo(f"  {line}")


@session.command("split")
@click.option("--session-id", default=None)
@click.option("--vertical", "-v", is_flag=True, default=False,
              help="Split vertically (side by side). Default: horizontal.")
@click.option("--before", is_flag=True, default=False,
              help="Insert new pane before the split point.")
@click.option("--profile", "-p", default=None)
@click.option("--command", "-c", default=None)
@click.option("--use-as-context", is_flag=True, default=False)
@handle_iterm2_error
def session_split(session_id, vertical, before, profile, command, use_as_context):
    """Split a session into two panes."""
    sid = session_id or get_state().session_id
    if not sid:
        raise click.UsageError("No session ID specified.")
    result = run_iterm2(sess_mod.split_pane, sid,
                        vertical=vertical, before=before,
                        profile=profile, command=command)
    if use_as_context:
        state = get_state()
        state.session_id = result.get("new_session_id")
        save_state_now()
    direction = "vertically" if vertical else "horizontally"
    output(result, f"Split {direction}: new session {result['new_session_id']}")


@session.command("close")
@click.argument("session_id", required=False)
@click.option("--force", is_flag=True, default=False)
@handle_iterm2_error
def session_close(session_id, force):
    """Close a session."""
    sid = session_id or get_state().session_id
    if not sid:
        raise click.UsageError("No session ID specified.")
    result = run_iterm2(sess_mod.close_session, sid, force=force)
    output(result, f"Closed session {sid}")


@session.command("activate")
@click.argument("session_id", required=False)
@handle_iterm2_error
def session_activate(session_id):
    """Focus a session."""
    sid = session_id or get_state().session_id
    if not sid:
        raise click.UsageError("No session ID specified.")
    result = run_iterm2(sess_mod.activate_session, sid)
    output(result, f"Activated session {sid}")


@session.command("set-name")
@click.argument("name")
@click.option("--session-id", default=None)
@handle_iterm2_error
def session_set_name(name, session_id):
    """Set the display name of a session."""
    sid = session_id or get_state().session_id
    if not sid:
        raise click.UsageError("No session ID specified.")
    result = run_iterm2(sess_mod.set_session_name, sid, name)
    output(result, f"Named session {sid} '{name}'")


@session.command("restart")
@click.option("--session-id", default=None)
@click.option("--only-if-exited", is_flag=True, default=False)
@handle_iterm2_error
def session_restart(session_id, only_if_exited):
    """Restart a session."""
    sid = session_id or get_state().session_id
    if not sid:
        raise click.UsageError("No session ID specified.")
    result = run_iterm2(sess_mod.restart_session, sid, only_if_exited=only_if_exited)
    output(result, f"Restarted session {sid}")


@session.command("get-var")
@click.argument("variable_name")
@click.option("--session-id", default=None)
@handle_iterm2_error
def session_get_var(variable_name, session_id):
    """Get a session variable value."""
    sid = session_id or get_state().session_id
    if not sid:
        raise click.UsageError("No session ID specified.")
    result = run_iterm2(sess_mod.get_session_variable, sid, variable_name)
    output(result, f"{variable_name} = {result['value']}")


@session.command("set-var")
@click.argument("variable_name")
@click.argument("value")
@click.option("--session-id", default=None)
@handle_iterm2_error
def session_set_var(variable_name, value, session_id):
    """Set a session variable."""
    sid = session_id or get_state().session_id
    if not sid:
        raise click.UsageError("No session ID specified.")
    result = run_iterm2(sess_mod.set_session_variable, sid, variable_name, value)
    output(result, f"Set {variable_name} = {value}")


@session.command("resize")
@click.option("--session-id", default=None)
@click.option("--columns", "-c", type=int, required=True)
@click.option("--rows", "-r", type=int, required=True)
@handle_iterm2_error
def session_resize(session_id, columns, rows):
    """Resize a session terminal grid."""
    sid = session_id or get_state().session_id
    if not sid:
        raise click.UsageError("No session ID specified.")
    result = run_iterm2(sess_mod.set_grid_size, sid, columns, rows)
    output(result, f"Resized session {sid} to {columns}x{rows}")


@session.command("run-tmux-cmd")
@click.argument("command")
@click.option("--session-id", default=None)
@handle_iterm2_error
def session_run_tmux_cmd(command, session_id):
    """Run a tmux command from within a tmux-integrated session.

    The session must be one where `tmux -CC` was started (the "gateway"
    session). Raises if the session is not a tmux integration session.

    Example:
        cli-anything-iterm2 session run-tmux-cmd "rename-window mywork"
        cli-anything-iterm2 session run-tmux-cmd "list-sessions"
    """
    sid = session_id or get_state().session_id
    if not sid:
        raise click.UsageError("No session ID specified.")
    result = run_iterm2(tmux_mod.run_session_tmux_command, sid, command)
    output(result, f"tmux [{sid}]: {result.get('output', '').strip()}")


@session.command("selection")
@click.option("--session-id", default=None)
@handle_iterm2_error
def session_selection(session_id):
    """Get the selected text in a session."""
    sid = session_id or get_state().session_id
    if not sid:
        raise click.UsageError("No session ID specified.")
    result = run_iterm2(sess_mod.get_selection, sid)
    output(result)
    if not _json_output:
        if result["has_selection"]:
            click.echo(result["selected_text"])
        else:
            click.echo("(no selection)")


@session.command("inject")
@click.argument("data")
@click.option("--session-id", default=None)
@click.option("--hex", "use_hex", is_flag=True, default=False,
              help="Interpret DATA as a hex string (e.g. '1b5b41' for ESC[A).")
@handle_iterm2_error
def session_inject(data, session_id, use_hex):
    """Inject raw bytes into a session as if received from the shell.

    Useful for sending escape sequences, OSC codes, or other terminal control
    bytes that would normally come from a running program.

    \b
      cli-anything-iterm2 session inject $'\\x1b[2J'      # clear screen (ESC[2J)
      cli-anything-iterm2 session inject "1b5b324a" --hex  # same in hex
      cli-anything-iterm2 session inject $'\\x07'          # bell
    """
    sid = session_id or get_state().session_id
    if not sid:
        raise click.UsageError("No session ID specified.")
    if use_hex:
        try:
            raw = bytes.fromhex(data)
        except ValueError as e:
            raise click.UsageError(f"Invalid hex string: {e}")
    else:
        raw = data.encode("utf-8", errors="surrogateescape")
    result = run_iterm2(sess_mod.inject_bytes, sid, raw)
    output(result, f"Injected {result['injected_bytes']} byte(s) into session {sid}")


@session.command("get-prompt")
@click.option("--session-id", default=None)
@handle_iterm2_error
def session_get_prompt(session_id):
    """Get the last shell prompt info (requires Shell Integration)."""
    sid = session_id or get_state().session_id
    if not sid:
        raise click.UsageError("No session ID specified.")
    result = run_iterm2(prompt_mod.get_last_prompt, sid)
    output(result)
    if not _json_output:
        if result.get("available"):
            click.echo(f"  command: {result.get('command')}")
            click.echo(f"  cwd:     {result.get('working_directory')}")
            click.echo(f"  state:   {result.get('state')}")
        else:
            click.echo("  Shell Integration not available in this session.")


@session.command("wait-prompt")
@click.option("--session-id", default=None)
@click.option("--timeout", "-t", type=float, default=30.0,
              help="Seconds to wait (default 30).")
@handle_iterm2_error
def session_wait_prompt(session_id, timeout):
    """Wait for the next shell prompt (requires Shell Integration).

    Blocks until the shell in the session displays its next prompt, meaning
    the previously running command has completed.
    """
    sid = session_id or get_state().session_id
    if not sid:
        raise click.UsageError("No session ID specified.")
    result = run_iterm2(prompt_mod.wait_for_prompt, sid, timeout=timeout)
    if result.get("timed_out"):
        output(result, f"Timed out after {timeout}s waiting for prompt.")
    else:
        output(result, f"Prompt received in session {sid}")


@session.command("wait-command-end")
@click.option("--session-id", default=None)
@click.option("--timeout", "-t", type=float, default=30.0,
              help="Seconds to wait (default 30).")
@handle_iterm2_error
def session_wait_command_end(session_id, timeout):
    """Wait for the current command to finish (requires Shell Integration).

    Returns the exit status of the completed command.
    """
    sid = session_id or get_state().session_id
    if not sid:
        raise click.UsageError("No session ID specified.")
    result = run_iterm2(prompt_mod.wait_for_command_end, sid, timeout=timeout)
    if result.get("timed_out"):
        output(result, f"Timed out after {timeout}s.")
    else:
        output(result, f"Command ended, exit_status={result.get('exit_status')}")


# ── Profile group ──────────────────────────────────────────────────────

@cli.group()
def profile():
    """Manage iTerm2 profiles."""


@profile.command("list")
@click.option("--filter", "name_filter", default=None,
              help="Filter by name substring.")
@handle_iterm2_error
def profile_list(name_filter):
    """List all available profiles."""
    result = run_iterm2(profile_mod.list_profiles, name_filter=name_filter)
    output({"profiles": result}, f"{len(result)} profile(s)")
    if not _json_output and result:
        for p in result:
            click.echo(f"  {p['name']}  ({p['guid']})")


@profile.command("get")
@click.argument("guid")
@handle_iterm2_error
def profile_get(guid):
    """Get detailed settings for a profile by GUID.

    GUID: The profile GUID from `profile list`.

    \b
      cli-anything-iterm2 profile list          # find the GUID
      cli-anything-iterm2 profile get <guid>    # get details
    """
    result = run_iterm2(profile_mod.get_profile_detail, guid)
    output(result)
    if not _json_output:
        click.echo(f"  name:       {result['name']}")
        click.echo(f"  guid:       {result['guid']}")
        click.echo(f"  badge_text: {result.get('badge_text') or '(none)'}")


@profile.command("color-presets")
@handle_iterm2_error
def profile_color_presets():
    """List all available color presets."""
    result = run_iterm2(profile_mod.list_color_presets)
    output({"color_presets": result}, f"{len(result)} color preset(s)")
    if not _json_output and result:
        for p in result:
            click.echo(f"  {p}")


@profile.command("apply-preset")
@click.argument("preset_name")
@click.option("--session-id", default=None)
@handle_iterm2_error
def profile_apply_preset(preset_name, session_id):
    """Apply a color preset to a session."""
    sid = session_id or get_state().session_id
    if not sid:
        raise click.UsageError("No session ID specified.")
    result = run_iterm2(profile_mod.apply_color_preset, sid, preset_name)
    output(result, f"Applied preset '{preset_name}' to session {sid}")


# ── Arrangement group ──────────────────────────────────────────────────

@cli.group()
def arrangement():
    """Save and restore window arrangements."""


@arrangement.command("list")
@handle_iterm2_error
def arrangement_list():
    """List all saved arrangements."""
    result = run_iterm2(arr_mod.list_arrangements)
    output({"arrangements": result}, f"{len(result)} arrangement(s)")
    if not _json_output and result:
        for a in result:
            click.echo(f"  {a}")


@arrangement.command("save")
@click.argument("name")
@handle_iterm2_error
def arrangement_save(name):
    """Save all current windows as a named arrangement."""
    result = run_iterm2(arr_mod.save_arrangement, name)
    output(result, f"Saved arrangement '{name}'")


@arrangement.command("restore")
@click.argument("name")
@click.option("--window-id", default=None,
              help="Restore into an existing window (default: open new windows).")
@handle_iterm2_error
def arrangement_restore(name, window_id):
    """Restore a saved arrangement."""
    wid = window_id or None
    result = run_iterm2(arr_mod.restore_arrangement, name, window_id=wid)
    output(result, f"Restored arrangement '{name}'")


@arrangement.command("save-window")
@click.argument("name")
@click.option("--window-id", default=None)
@handle_iterm2_error
def arrangement_save_window(name, window_id):
    """Save a single window as a named arrangement."""
    wid = window_id or get_state().window_id
    if not wid:
        raise click.UsageError("No window ID specified.")
    result = run_iterm2(arr_mod.save_window_arrangement, wid, name)
    output(result, f"Saved window {wid} as arrangement '{name}'")


# ── Tmux group ────────────────────────────────────────────────────────

@cli.group()
def tmux():
    """Manage iTerm2 tmux integration connections.

    Requires at least one active `tmux -CC` session running inside iTerm2.
    Start one with:  tmux -CC          (new session)
                     tmux -CC attach   (attach to existing)
    """


@tmux.command("list")
@handle_iterm2_error
def tmux_list():
    """List all active tmux integration connections."""
    result = run_iterm2(tmux_mod.list_connections)
    output({"connections": result},
           f"{len(result)} tmux connection(s)" if result else "No active tmux connections.")
    if not _json_output and result:
        for c in result:
            click.echo(f"  {c['connection_id']}  "
                       f"gateway-session={c['owning_session_id']}")


@tmux.command("send")
@click.argument("command")
@click.option("--connection-id", default=None,
              help="Tmux connection ID (default: first available).")
@handle_iterm2_error
def tmux_send(command, connection_id):
    """Send a tmux command to an active connection.

    COMMAND is any valid tmux command, e.g.:

    \b
      cli-anything-iterm2 tmux send "list-sessions"
      cli-anything-iterm2 tmux send "new-window -n work"
      cli-anything-iterm2 tmux send "rename-session dev"
      cli-anything-iterm2 tmux send "split-window -h"
    """
    result = run_iterm2(tmux_mod.send_command, command, connection_id=connection_id)
    output(result, result.get("output", "").strip() or "(no output)")


@tmux.command("create-window")
@click.option("--connection-id", default=None,
              help="Tmux connection ID (default: first available).")
@click.option("--use-as-context", is_flag=True, default=False,
              help="Save new window/session as the current context.")
@handle_iterm2_error
def tmux_create_window(connection_id, use_as_context):
    """Create a new tmux window (surfaces as an iTerm2 tab)."""
    result = run_iterm2(tmux_mod.create_window, connection_id=connection_id)
    if use_as_context:
        state = get_state()
        state.window_id = result.get("window_id")
        state.tab_id = result.get("tab_id")
        state.session_id = result.get("session_id")
        save_state_now()
    output(result, f"Created tmux window: tab={result.get('tab_id')} "
           f"session={result.get('session_id')}")


@tmux.command("set-visible")
@click.argument("tmux_window_id")
@click.argument("mode", type=click.Choice(["on", "off"]))
@click.option("--connection-id", default=None)
@handle_iterm2_error
def tmux_set_visible(tmux_window_id, mode, connection_id):
    """Show or hide a tmux window tab.

    TMUX_WINDOW_ID is the tmux window ID (e.g. @1). Get it from `tmux tabs`.

    \b
      cli-anything-iterm2 tmux set-visible @1 off   # hide
      cli-anything-iterm2 tmux set-visible @1 on    # show
    """
    visible = mode == "on"
    result = run_iterm2(tmux_mod.set_window_visible, tmux_window_id, visible,
                        connection_id=connection_id)
    state_str = "visible" if visible else "hidden"
    output(result, f"Tmux window {tmux_window_id} is now {state_str}")


@tmux.command("tabs")
@handle_iterm2_error
def tmux_tabs():
    """List all iTerm2 tabs backed by a tmux integration window."""
    result = run_iterm2(tmux_mod.list_tmux_tabs)
    output({"tmux_tabs": result},
           f"{len(result)} tmux tab(s)" if result else "No tmux-backed tabs found.")
    if not _json_output and result:
        for t in result:
            click.echo(f"  tab={t['tab_id']}  tmux-window={t['tmux_window_id']}  "
                       f"connection={t['tmux_connection_id']}")


@tmux.command("bootstrap")
@click.option("--attach", is_flag=True, default=False,
              help="Run `tmux -CC attach` instead of `tmux -CC`.")
@click.option("--session-id", default=None,
              help="Session to send the command to (default: first session).")
@click.option("--timeout", "-t", type=float, default=15.0,
              help="Seconds to wait for connection to appear (default 15).")
@handle_iterm2_error
def tmux_bootstrap(attach, session_id, timeout):
    """Start a tmux -CC session and wait for the integration to connect.

    Sends `tmux -CC` (or `tmux -CC attach` with --attach) to a terminal
    session, then polls until the iTerm2 tmux integration connection appears.

    \b
      cli-anything-iterm2 tmux bootstrap                # start new session
      cli-anything-iterm2 tmux bootstrap --attach       # attach to existing
      cli-anything-iterm2 tmux bootstrap --session-id w0t0p0
    """
    sid = session_id or get_state().session_id
    result = run_iterm2(tmux_mod.bootstrap, attach=attach,
                        session_id=sid, timeout=timeout)
    output(result, f"tmux -CC connected: {result['connection_id']} "
           f"({result['elapsed_seconds']}s)")


# ── Broadcast group ────────────────────────────────────────────────────

@cli.group()
def broadcast():
    """Control broadcast domains (sync keystrokes across panes)."""


@broadcast.command("list")
@handle_iterm2_error
def broadcast_list():
    """List current broadcast domains."""
    result = run_iterm2(bcast_mod.get_broadcast_domains)
    output({"domains": result},
           f"{len(result)} broadcast domain(s)" if result else "No active broadcast domains.")
    if not _json_output and result:
        for i, d in enumerate(result, 1):
            click.echo(f"  domain {i}: {', '.join(d['sessions'])}")


@broadcast.command("set")
@click.argument("groups", nargs=-1, required=True)
@handle_iterm2_error
def broadcast_set(groups):
    """Set broadcast domains from session ID groups.

    Each argument is a comma-separated list of session IDs forming one domain.

    \b
      cli-anything-iterm2 broadcast set "s1,s2" "s3,s4"
    """
    domain_groups = [g.split(",") for g in groups]
    result = run_iterm2(bcast_mod.set_broadcast_domains, domain_groups)
    output(result, f"Set {result['domain_count']} broadcast domain(s)")


@broadcast.command("add")
@click.argument("session_ids", nargs=-1, required=True)
@handle_iterm2_error
def broadcast_add(session_ids):
    """Add sessions to a new broadcast domain.

    SESSION_IDS: One or more session IDs to group into one domain.
    Existing domains are preserved.

    \b
      cli-anything-iterm2 broadcast add s1 s2
    """
    result = run_iterm2(bcast_mod.add_to_broadcast, list(session_ids))
    output(result, f"Added {len(session_ids)} session(s) to new broadcast domain")


@broadcast.command("clear")
@handle_iterm2_error
def broadcast_clear():
    """Clear all broadcast domains, stopping all input sync."""
    result = run_iterm2(bcast_mod.clear_broadcast)
    output(result, "All broadcast domains cleared.")


@broadcast.command("all-panes")
@click.option("--window-id", default=None,
              help="Scope to a specific window (default: all windows).")
@handle_iterm2_error
def broadcast_all_panes(window_id):
    """Sync keystrokes across all panes in all windows (or one window)."""
    wid = window_id or get_state().window_id
    result = run_iterm2(bcast_mod.broadcast_all_panes, window_id=wid)
    output(result, f"Broadcasting to {result['session_count']} session(s)")


# ── Menu group ─────────────────────────────────────────────────────────

@cli.group()
def menu():
    """Invoke iTerm2 menu items programmatically."""


@menu.command("select")
@click.argument("identifier")
@handle_iterm2_error
def menu_select(identifier):
    """Invoke a menu item by its identifier string.

    IDENTIFIER: e.g. "Shell/Split Vertically with Current Profile"

    Run `menu list-common` to see available identifiers.
    """
    result = run_iterm2(menu_mod.select_menu_item, identifier)
    output(result, f"Invoked: {identifier}")


@menu.command("state")
@click.argument("identifier")
@handle_iterm2_error
def menu_state(identifier):
    """Get the checked/enabled state of a menu item."""
    result = run_iterm2(menu_mod.get_menu_item_state, identifier)
    output(result, f"{identifier}: checked={result['checked']} enabled={result['enabled']}")


@menu.command("list-common")
@handle_iterm2_error
def menu_list_common():
    """List commonly useful menu item identifiers."""
    result = run_iterm2(menu_mod.list_common_menu_items)
    output({"menu_items": result},
           f"{len(result)} common menu item(s)")
    if not _json_output and result:
        for item in result:
            click.echo(f"  {item['identifier']}")
            click.echo(f"    {item['description']}")


# ── Pref group ─────────────────────────────────────────────────────────

@cli.group()
def pref():
    """Read and write iTerm2 global preferences."""


@pref.command("get")
@click.argument("key")
@handle_iterm2_error
def pref_get(key):
    """Get a preference by key name (PreferenceKey enum name or raw string)."""
    result = run_iterm2(pref_mod.get_preference, key)
    output(result, f"{result['key']} = {result['value']}")


@pref.command("set")
@click.argument("key")
@click.argument("value")
@handle_iterm2_error
def pref_set(key, value):
    """Set a preference by key name."""
    result = run_iterm2(pref_mod.set_preference, key, value)
    output(result, f"Set {result['key']} = {result['value']}")


@pref.command("tmux-get")
@handle_iterm2_error
def pref_tmux_get():
    """Show all tmux-related preferences."""
    result = run_iterm2(pref_mod.get_tmux_preferences)
    output(result)
    if not _json_output:
        click.echo(f"  open_in:    {result['open_tmux_windows_in']} "
                   f"({result['open_tmux_windows_in_label']})")
        click.echo(f"  dash_limit: {result['tmux_dashboard_limit']}")
        click.echo(f"  auto_hide:  {result['auto_hide_tmux_client_session']}")
        click.echo(f"  use_profile:{result['use_tmux_profile']}")


@pref.command("tmux-set")
@click.argument("setting", type=click.Choice(
    ["open_in", "dashboard_limit", "auto_hide_client", "use_profile"]))
@click.argument("value")
@handle_iterm2_error
def pref_tmux_set(setting, value):
    """Set a tmux preference by name.

    \b
      open_in: 0=native_windows  1=new_window  2=tabs_in_existing
      dashboard_limit: integer
      auto_hide_client: true/false
      use_profile: true/false
    """
    result = run_iterm2(pref_mod.set_tmux_preference, setting, value)
    output(result, f"Set tmux.{setting} = {result['value']}")


@pref.command("list-keys")
@click.option("--filter", "name_filter", default=None,
              help="Filter key names by substring (case-insensitive).")
def pref_list_keys(name_filter):
    """List all valid preference key names for use with `pref get/set`.

    \b
      cli-anything-iterm2 pref list-keys
      cli-anything-iterm2 pref list-keys --filter tmux
      cli-anything-iterm2 pref list-keys --filter font
    """
    from iterm2.preferences import PreferenceKey
    keys = sorted(k.name for k in PreferenceKey)
    if name_filter:
        keys = [k for k in keys if name_filter.lower() in k.lower()]
    data = {"keys": keys, "count": len(keys)}
    output(data, f"{len(keys)} preference key(s)")
    if not _json_output:
        for k in keys:
            click.echo(f"  {k}")


@pref.command("theme")
@handle_iterm2_error
def pref_theme():
    """Get the current iTerm2 theme tags."""
    result = run_iterm2(pref_mod.get_theme)
    output(result, f"Theme: {', '.join(result['tags'])}  dark={result['is_dark']}")


# ── REPL ───────────────────────────────────────────────────────────────

@cli.command("repl")
@click.pass_context
def repl(ctx):
    """Start the interactive REPL (default when no subcommand given)."""
    from cli_anything.iterm2_ctl.utils.repl_skin import ReplSkin

    skin = ReplSkin("iterm2_ctl", version="1.0.0")
    skin.print_banner()

    state = get_state()
    if state.summary() != "no context set":
        skin.info(f"Context: {state.summary()}")
        click.echo()

    skin.info("Type 'help' for commands, 'quit' to exit.")
    click.echo()

    pt_session = skin.create_prompt_session()

    _COMMANDS = {
        "app status": "Show iTerm2 status",
        "app current": "Get current window/tab/session",
        "app context": "Show saved context",
        "app set-context": "Set context IDs",
        "app clear-context": "Clear saved context",
        "app get-var <var>": "Get app-level variable",
        "app set-var <var> <val>": "Set app-level variable",
        "app alert <title> <subtitle>": "Show modal alert dialog",
        "app text-input <title> <subtitle>": "Show text input dialog",
        "app file-panel": "Show macOS open file picker",
        "app save-panel": "Show macOS save file picker",
        "window list": "List open windows",
        "window create": "Create a new window",
        "window close [id]": "Close a window",
        "window activate [id]": "Focus a window",
        "window set-title <title>": "Set window title",
        "window frame [id]": "Get window geometry",
        "window fullscreen <on|off|toggle|status>": "Control fullscreen",
        "tab list": "List tabs",
        "tab create": "Create a new tab",
        "tab close [id]": "Close a tab",
        "tab activate [id]": "Focus a tab",
        "tab select-pane <dir>": "Move focus to adjacent pane (left/right/above/below)",
        "session list": "List sessions",
        "session send <text>": "Send text to session",
        "session screen": "Read terminal screen",
        "session split": "Split pane",
        "session close [id]": "Close a session",
        "session set-name <name>": "Name a session",
        "session resize -c <cols> -r <rows>": "Resize terminal",
        "session inject <data>": "Inject raw bytes into session (use --hex for hex string)",
        "session get-prompt": "Get last shell prompt info (Shell Integration)",
        "session wait-prompt": "Wait for next shell prompt",
        "session wait-command-end": "Wait for command to finish",
        "session run-tmux-cmd <command>": "Run tmux cmd from gateway session",
        "profile list": "List profiles",
        "profile get <guid>": "Get profile details by GUID",
        "profile color-presets": "List color presets",
        "arrangement list": "List arrangements",
        "arrangement save <name>": "Save arrangement",
        "arrangement restore <name>": "Restore arrangement",
        "tmux list": "List active tmux -CC connections",
        "tmux bootstrap": "Start tmux -CC and wait for connection",
        "tmux send <command>": "Send tmux command (e.g. 'list-sessions')",
        "tmux create-window": "Create tmux window as iTerm2 tab",
        "tmux set-visible <id> on|off": "Show/hide a tmux window tab",
        "tmux tabs": "List tmux-backed tabs",
        "broadcast list": "List broadcast domains",
        "broadcast set <g1> [g2...]": "Set broadcast domains (comma-sep session IDs)",
        "broadcast add <s1> [s2...]": "Add sessions to a new broadcast domain",
        "broadcast clear": "Clear all broadcast domains",
        "broadcast all-panes": "Broadcast to all panes",
        "menu select <identifier>": "Invoke a menu item",
        "menu state <identifier>": "Get menu item state",
        "menu list-common": "List common menu identifiers",
        "pref list-keys": "List all valid preference key names",
        "pref get <key>": "Get a preference value",
        "pref set <key> <val>": "Set a preference value",
        "pref tmux-get": "Show all tmux preferences",
        "pref tmux-set <setting> <val>": "Set a tmux preference",
        "pref theme": "Show current theme tags",
        "help": "Show this help",
        "quit": "Exit REPL",
    }

    while True:
        try:
            state = get_state()
            ctx_str = ""
            if state.session_id:
                ctx_str = state.session_id[:12]
            elif state.window_id:
                ctx_str = state.window_id[:12]

            line = skin.get_input(pt_session, context=ctx_str)
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

        if not line:
            continue

        cmd = line.strip()

        if cmd in ("quit", "exit", "q"):
            skin.print_goodbye()
            break
        elif cmd == "help":
            skin.help(_COMMANDS)
            continue

        # Run the line through the Click CLI
        try:
            args = cmd.split()
            standalone = cli.main(args=args, standalone_mode=False,
                                  obj={"json": _json_output})
        except SystemExit:
            pass
        except click.UsageError as e:
            skin.error(str(e))
        except Exception as e:
            skin.error(str(e))


if __name__ == "__main__":
    main()
