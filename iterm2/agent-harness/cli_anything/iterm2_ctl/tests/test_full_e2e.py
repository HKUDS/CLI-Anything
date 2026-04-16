"""E2E tests for cli-anything-iterm2.

These tests require iTerm2 to be running with the Python API enabled.

Prerequisites:
  1. iTerm2 is running
  2. iTerm2 → Preferences → General → Magic → Enable Python API ✓
  3. pip install iterm2 cli-anything-iterm2  (or pip install -e .)

Run with:
  python3 -m pytest cli_anything/iterm2_ctl/tests/test_full_e2e.py -v -s
  CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest ... -v -s
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

# ── resolve CLI helper ─────────────────────────────────────────────────

def _resolve_cli(name: str):
    """Resolve installed CLI command; falls back to python -m for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(
            f"{name} not found in PATH. Install with:\n"
            f"  cd /path/to/iTerm2-master/agent-harness && pip install -e ."
        )
    module = "cli_anything.iterm2_ctl.iterm2_ctl_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def iterm2_connection():
    """Provide a live iTerm2 connection. Skips if iTerm2 is not available."""
    try:
        import iterm2
    except ImportError:
        pytest.skip("iterm2 Python package not installed")

    # Quick connectivity check
    try:
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.window import list_windows
        run_iterm2(list_windows)
    except Exception as e:
        pytest.skip(f"iTerm2 not reachable: {e}")

    return True  # signal that connection is available


# ── App tests ──────────────────────────────────────────────────────────

class TestAppStatus:
    def test_app_status(self, iterm2_connection):
        """Get app status — should return window count."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        import iterm2

        async def _get_status(conn):
            app = await iterm2.async_get_app(conn)
            return {"window_count": len(app.windows)}

        result = run_iterm2(_get_status)
        assert "window_count" in result
        assert result["window_count"] >= 0
        print(f"\n  App status: {result['window_count']} window(s)")

    def test_get_current_context(self, iterm2_connection):
        """Get current focused window/tab/session."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.window import get_current_window

        result = run_iterm2(get_current_window)
        # May be None if no window focused, but should not raise
        print(f"\n  Current context: {result}")
        if result is not None:
            assert "window_id" in result


class TestWorkspaceSnapshot:
    def test_workspace_snapshot_structure(self, iterm2_connection):
        """snapshot returns session_count and sessions list with required keys."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.session import workspace_snapshot

        result = run_iterm2(workspace_snapshot)
        assert "session_count" in result
        assert "sessions" in result
        assert isinstance(result["sessions"], list)
        assert result["session_count"] == len(result["sessions"])
        print(f"\n  Snapshot: {result['session_count']} session(s)")
        for s in result["sessions"]:
            assert "session_id" in s
            assert "name" in s
            assert "window_id" in s
            assert "tab_id" in s
            assert "path" in s
            assert "pid" in s
            assert "process" in s
            assert "role" in s
            assert "last_line" in s
            print(f"    {s['session_id']}  name={s['name']}  "
                  f"process={s['process']}  path={s['path']}")

    def test_workspace_snapshot_process_populated(self, iterm2_connection):
        """process field should be a non-empty string for sessions with a running shell."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.session import workspace_snapshot

        result = run_iterm2(workspace_snapshot)
        if result["session_count"] > 0:
            # At least one session should have a process name
            processes = [s["process"] for s in result["sessions"] if s["process"]]
            assert len(processes) > 0, "Expected at least one session with a process name"
            print(f"\n  Processes found: {processes}")


# ── Window tests ───────────────────────────────────────────────────────

class TestWindowOperations:
    def test_list_windows(self, iterm2_connection):
        """List windows returns a list."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.window import list_windows

        result = run_iterm2(list_windows)
        assert isinstance(result, list)
        print(f"\n  Windows: {len(result)}")
        for w in result:
            print(f"    {w['window_id']}  tabs={w['tab_count']}")

    def test_create_and_close_window(self, iterm2_connection):
        """Create a window, verify it appears in the list, then close it."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.window import (
            list_windows, create_window, close_window
        )

        # Create
        created = run_iterm2(create_window)
        assert "window_id" in created
        wid = created["window_id"]
        print(f"\n  Created window: {wid}")

        # Verify it appears in list
        windows = run_iterm2(list_windows)
        ids = [w["window_id"] for w in windows]
        assert wid in ids, f"Window {wid} not in list: {ids}"

        # Close
        closed = run_iterm2(close_window, wid, force=True)
        assert closed["closed"] is True
        print(f"  Closed window: {wid}")

        # Verify removed
        time.sleep(0.3)
        windows_after = run_iterm2(list_windows)
        ids_after = [w["window_id"] for w in windows_after]
        assert wid not in ids_after

    def test_window_frame(self, iterm2_connection):
        """Get window frame returns numeric x/y/w/h."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.window import create_window, close_window, get_window_frame

        created = run_iterm2(create_window)
        wid = created["window_id"]
        try:
            frame = run_iterm2(get_window_frame, wid)
            assert "x" in frame
            assert "y" in frame
            assert "width" in frame
            assert "height" in frame
            assert frame["width"] > 0
            assert frame["height"] > 0
            print(f"\n  Frame: x={frame['x']} y={frame['y']} "
                  f"w={frame['width']} h={frame['height']}")
        finally:
            run_iterm2(close_window, wid, force=True)


# ── Tab tests ──────────────────────────────────────────────────────────

class TestTabOperations:
    def test_list_tabs(self, iterm2_connection):
        """List tabs returns a list."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.tab import list_tabs

        result = run_iterm2(list_tabs)
        assert isinstance(result, list)
        print(f"\n  Tabs: {len(result)}")

    def test_create_and_close_tab(self, iterm2_connection):
        """Create a tab in a new window, verify it, then close."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.window import create_window, close_window
        from cli_anything.iterm2_ctl.core.tab import create_tab, list_tabs

        # Create window for test
        w = run_iterm2(create_window)
        wid = w["window_id"]
        try:
            # Create extra tab
            tab = run_iterm2(create_tab, window_id=wid)
            assert "tab_id" in tab
            tid = tab["tab_id"]
            print(f"\n  Created tab: {tid} in window {wid}")

            # Verify it appears
            tabs = run_iterm2(list_tabs, window_id=wid)
            tab_ids = [t["tab_id"] for t in tabs]
            assert tid in tab_ids
        finally:
            run_iterm2(close_window, wid, force=True)


# ── Session tests ──────────────────────────────────────────────────────

class TestSessionOperations:
    def test_list_sessions(self, iterm2_connection):
        """List sessions returns a list."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.session import list_sessions

        result = run_iterm2(list_sessions)
        assert isinstance(result, list)
        assert len(result) >= 1
        print(f"\n  Sessions: {len(result)}")
        for s in result:
            print(f"    {s['session_id']}  name={s['name']}")

    def test_send_text_and_read_screen(self, iterm2_connection):
        """Send a command to a session and verify screen output."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.window import create_window, close_window
        from cli_anything.iterm2_ctl.core.session import (
            list_sessions, send_text, get_screen_contents
        )

        w = run_iterm2(create_window)
        wid = w["window_id"]
        sid = w["session_id"]
        try:
            # Send a distinctive command
            marker = "CLI_TEST_MARKER_12345"
            run_iterm2(send_text, sid, f"echo {marker}\n", suppress_broadcast=False)
            time.sleep(0.5)  # let the shell process it

            # Read screen
            screen = run_iterm2(get_screen_contents, sid)
            assert "lines" in screen
            assert screen["total_lines"] > 0
            all_text = "\n".join(screen["lines"])
            assert marker in all_text, f"Marker not found in screen:\n{all_text[:500]}"
            print(f"\n  Screen read OK — found marker '{marker}'")
            print(f"  Artifact: session {sid}, {screen['returned_lines']} lines")
        finally:
            run_iterm2(close_window, wid, force=True)

    def test_split_pane(self, iterm2_connection):
        """Split a pane horizontally and verify new session created."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.window import create_window, close_window
        from cli_anything.iterm2_ctl.core.session import split_pane, list_sessions

        w = run_iterm2(create_window)
        wid = w["window_id"]
        sid = w["session_id"]
        try:
            result = run_iterm2(split_pane, sid, vertical=False)
            assert "new_session_id" in result
            new_sid = result["new_session_id"]
            assert new_sid != sid
            print(f"\n  Split pane: original={sid}, new={new_sid}")

            # Verify both sessions exist
            sessions = run_iterm2(list_sessions, window_id=wid)
            session_ids = [s["session_id"] for s in sessions]
            assert sid in session_ids
            assert new_sid in session_ids
        finally:
            run_iterm2(close_window, wid, force=True)


# ── Profile tests ──────────────────────────────────────────────────────

class TestProfileOperations:
    def test_list_profiles(self, iterm2_connection):
        """List profiles returns ≥ 1 profile."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.profile import list_profiles

        result = run_iterm2(list_profiles)
        assert isinstance(result, list)
        assert len(result) >= 1
        print(f"\n  Profiles: {len(result)}")
        for p in result:
            print(f"    {p['name']}")

    def test_list_color_presets(self, iterm2_connection):
        """List color presets returns a list."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.profile import list_color_presets

        result = run_iterm2(list_color_presets)
        assert isinstance(result, list)
        print(f"\n  Color presets: {len(result)}")
        if result:
            print(f"  Sample: {result[:3]}")


# ── Arrangement tests ──────────────────────────────────────────────────

class TestArrangementOperations:
    def test_arrangement_save_list_restore(self, iterm2_connection):
        """Save, list, and restore an arrangement."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.arrangement import (
            save_arrangement, list_arrangements, restore_arrangement
        )

        name = "cli-test-arrangement-tmp"
        try:
            # Save current state
            saved = run_iterm2(save_arrangement, name)
            assert saved["saved"] is True
            print(f"\n  Saved arrangement: '{name}'")

            # Verify it appears in list
            arrangements = run_iterm2(list_arrangements)
            assert name in arrangements
            print(f"  Found in list: {arrangements}")

            # Restore it
            restored = run_iterm2(restore_arrangement, name)
            assert restored["restored"] is True
            print(f"  Restored arrangement: '{name}'")
        finally:
            # No cleanup API for arrangements — leave it (small footprint)
            pass


# ── Tmux tests ────────────────────────────────────────────────────────


@pytest.fixture
def tmux_connection(iterm2_connection):
    """Skip tests if no active tmux -CC connection is available."""
    from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
    from cli_anything.iterm2_ctl.core.tmux import list_connections

    connections = run_iterm2(list_connections)
    if not connections:
        pytest.skip(
            "No active tmux -CC connections. "
            "Start one with: tmux -CC  (or tmux -CC attach)"
        )
    return connections


class TestTmuxOperations:
    def test_list_connections_always_works(self, iterm2_connection):
        """list_connections returns a list (possibly empty) without error."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.tmux import list_connections

        result = run_iterm2(list_connections)
        assert isinstance(result, list)
        print(f"\n  Tmux connections: {len(result)}")
        for c in result:
            print(f"    {c['connection_id']}  gateway={c['owning_session_id']}")

    def test_list_tmux_tabs_always_works(self, iterm2_connection):
        """list_tmux_tabs returns a list (possibly empty) without error."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.tmux import list_tmux_tabs

        result = run_iterm2(list_tmux_tabs)
        assert isinstance(result, list)
        print(f"\n  Tmux-backed tabs: {len(result)}")
        for t in result:
            print(f"    tab={t['tab_id']} tmux-window={t['tmux_window_id']} "
                  f"connection={t['tmux_connection_id']}")

    def test_send_command_list_sessions(self, tmux_connection):
        """Send 'list-sessions' to an active tmux connection."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.tmux import send_command

        conn_id = tmux_connection[0]["connection_id"]
        result = run_iterm2(send_command, "list-sessions", connection_id=conn_id)
        assert "connection_id" in result
        assert "command" in result
        assert "output" in result
        assert result["command"] == "list-sessions"
        # Output must be non-empty (at least one session is active since we're in it)
        assert len(result["output"]) > 0
        print(f"\n  tmux list-sessions output:\n{result['output']}")

    def test_send_command_list_windows(self, tmux_connection):
        """Send 'list-windows' — verifies arbitrary tmux command dispatch."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.tmux import send_command

        result = run_iterm2(send_command, "list-windows")
        assert result["output"]
        print(f"\n  tmux list-windows:\n{result['output']}")

    def test_send_command_display_message(self, tmux_connection):
        """Send 'display-message' to get tmux server info."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.tmux import send_command

        result = run_iterm2(send_command, "display-message -p '#{session_name}'")
        assert "output" in result
        print(f"\n  tmux session name: {result['output'].strip()!r}")

    def test_create_and_verify_tmux_window(self, tmux_connection):
        """Create a tmux window and verify it appears as an iTerm2 tab."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.tmux import create_window, list_tmux_tabs
        from cli_anything.iterm2_ctl.core.window import close_window

        result = run_iterm2(create_window)
        assert "window_id" in result
        assert "tab_id" in result
        assert result["tab_id"] is not None
        print(f"\n  Created tmux window: window={result['window_id']} "
              f"tab={result['tab_id']} session={result['session_id']}")

        # Verify the new tab appears in the tmux-tabs list
        time.sleep(0.3)
        tabs = run_iterm2(list_tmux_tabs)
        tab_ids = [t["tab_id"] for t in tabs]
        assert result["tab_id"] in tab_ids, (
            f"New tab {result['tab_id']} not in tmux tabs: {tab_ids}"
        )
        print(f"  Confirmed new tab {result['tab_id']} in tmux tabs list")

        # Clean up
        run_iterm2(close_window, result["window_id"], force=True)

    def test_set_window_visible_roundtrip(self, tmux_connection):
        """Hide then show a tmux window and verify no errors."""
        from cli_anything.iterm2_ctl.utils.iterm2_backend import run_iterm2
        from cli_anything.iterm2_ctl.core.tmux import (
            create_window, list_tmux_tabs, set_window_visible
        )
        from cli_anything.iterm2_ctl.core.window import close_window

        # Create a tmux window to play with
        created = run_iterm2(create_window)
        wid = created["window_id"]
        tid = created["tab_id"]

        try:
            time.sleep(0.3)
            # Find its tmux_window_id
            tabs = run_iterm2(list_tmux_tabs)
            tmux_wid = next(
                (t["tmux_window_id"] for t in tabs if t["tab_id"] == tid), None
            )
            if tmux_wid is None:
                pytest.skip("Could not find tmux_window_id for new tab — may vary by iTerm2 version")

            # Hide
            r_hide = run_iterm2(set_window_visible, tmux_wid, False)
            assert r_hide["visible"] is False
            print(f"\n  Hidden tmux window {tmux_wid}")

            # Show
            r_show = run_iterm2(set_window_visible, tmux_wid, True)
            assert r_show["visible"] is True
            print(f"  Shown tmux window {tmux_wid}")
        finally:
            # Hiding a tmux window removes the corresponding iTerm2 window,
            # so close_window may raise ValueError if the window is already gone.
            try:
                run_iterm2(close_window, wid, force=True)
            except (ValueError, RuntimeError):
                pass  # Already removed — that's fine


# ── CLI subprocess tests ───────────────────────────────────────────────

class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-iterm2")

    def _run(self, args, check=True, timeout=15):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            check=check,
            timeout=timeout,
        )

    def test_help(self):
        """--help exits 0 and mentions commands."""
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "iterm2" in result.stdout.lower() or "window" in result.stdout.lower()
        print(f"\n  help output: {result.stdout[:200]}")

    def test_json_app_status(self):
        """--json app status returns parseable JSON."""
        try:
            result = self._run(["--json", "app", "status"])
            data = json.loads(result.stdout)
            assert "window_count" in data
            print(f"\n  JSON app status: {data}")
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            pytest.skip(f"iTerm2 not available for subprocess test: {e}")

    def test_json_window_list(self):
        """--json window list returns parseable JSON list."""
        try:
            result = self._run(["--json", "window", "list"])
            data = json.loads(result.stdout)
            assert "windows" in data
            assert isinstance(data["windows"], list)
            print(f"\n  JSON window list: {len(data['windows'])} window(s)")
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            pytest.skip(f"iTerm2 not available for subprocess test: {e}")

    def test_json_session_list(self):
        """--json session list returns parseable JSON."""
        try:
            result = self._run(["--json", "session", "list"])
            data = json.loads(result.stdout)
            assert "sessions" in data
            assert isinstance(data["sessions"], list)
            print(f"\n  JSON session list: {len(data['sessions'])} session(s)")
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            pytest.skip(f"iTerm2 not available for subprocess test: {e}")

    def test_json_profile_list(self):
        """--json profile list returns parseable JSON."""
        try:
            result = self._run(["--json", "profile", "list"])
            data = json.loads(result.stdout)
            assert "profiles" in data
            print(f"\n  JSON profiles: {len(data['profiles'])} profile(s)")
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            pytest.skip(f"iTerm2 not available for subprocess test: {e}")

    def test_json_tmux_list(self):
        """--json tmux list returns parseable JSON with a 'connections' key."""
        try:
            result = self._run(["--json", "tmux", "list"])
            data = json.loads(result.stdout)
            assert "connections" in data
            assert isinstance(data["connections"], list)
            print(f"\n  JSON tmux connections: {len(data['connections'])}")
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            pytest.skip(f"iTerm2 not available for subprocess test: {e}")

    def test_json_tmux_tabs(self):
        """--json tmux tabs returns parseable JSON with a 'tmux_tabs' key."""
        try:
            result = self._run(["--json", "tmux", "tabs"])
            data = json.loads(result.stdout)
            assert "tmux_tabs" in data
            assert isinstance(data["tmux_tabs"], list)
            print(f"\n  JSON tmux tabs: {len(data['tmux_tabs'])}")
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            pytest.skip(f"iTerm2 not available for subprocess test: {e}")

    def test_tmux_send_no_connections_error(self):
        """tmux send without any active connection exits non-zero with clear error."""
        # This test verifies the error path when no tmux -CC is running.
        # If tmux IS connected, the command succeeds — which is also fine.
        result = self._run(["tmux", "send", "list-sessions"], check=False)
        # Either success (tmux connected) or a clear error (not connected)
        if result.returncode != 0:
            assert "tmux" in result.stderr.lower() or "connection" in result.stderr.lower()
            print(f"\n  Expected error when no tmux: {result.stderr.strip()[:120]}")
        else:
            print(f"\n  tmux connected — command succeeded: {result.stdout[:80]}")

    def test_tmux_help(self):
        """tmux --help exits 0 and mentions subcommands."""
        result = self._run(["tmux", "--help"])
        assert result.returncode == 0
        assert "send" in result.stdout
        assert "list" in result.stdout


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "-s"])
