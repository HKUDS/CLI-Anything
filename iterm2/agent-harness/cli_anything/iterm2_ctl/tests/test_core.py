"""Unit tests for cli-anything-iterm2 core modules.

These tests use synthetic data and do NOT require iTerm2 to be running.
All tests are deterministic and have no external dependencies.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure the package is importable from the agent-harness directory
_HARNESS = Path(__file__).resolve().parents[4]
if str(_HARNESS) not in sys.path:
    sys.path.insert(0, str(_HARNESS))

from cli_anything.iterm2_ctl.core.session_state import (
    SessionState,
    clear_state,
    load_state,
    save_state,
)


# ── SessionState tests ─────────────────────────────────────────────────

class TestSessionStateDefaults(unittest.TestCase):
    def test_defaults(self):
        s = SessionState()
        self.assertIsNone(s.window_id)
        self.assertIsNone(s.tab_id)
        self.assertIsNone(s.session_id)
        self.assertEqual(s.notes, "")

    def test_summary_empty(self):
        s = SessionState()
        self.assertEqual(s.summary(), "no context set")

    def test_summary_partial_window_only(self):
        s = SessionState(window_id="w1")
        self.assertIn("window=w1", s.summary())

    def test_summary_partial_tab_only(self):
        s = SessionState(tab_id="t1")
        self.assertIn("tab=t1", s.summary())

    def test_summary_full(self):
        s = SessionState(window_id="w1", tab_id="t1", session_id="s1")
        summary = s.summary()
        self.assertIn("window=w1", summary)
        self.assertIn("tab=t1", summary)
        self.assertIn("session=s1", summary)

    def test_to_dict(self):
        s = SessionState(window_id="w1", tab_id="t1", session_id="s1", notes="test")
        d = s.to_dict()
        self.assertEqual(d["window_id"], "w1")
        self.assertEqual(d["tab_id"], "t1")
        self.assertEqual(d["session_id"], "s1")
        self.assertEqual(d["notes"], "test")

    def test_from_dict(self):
        d = {"window_id": "w2", "tab_id": "t2", "session_id": "s2", "notes": "hi"}
        s = SessionState.from_dict(d)
        self.assertEqual(s.window_id, "w2")
        self.assertEqual(s.tab_id, "t2")
        self.assertEqual(s.session_id, "s2")
        self.assertEqual(s.notes, "hi")

    def test_from_dict_missing_keys(self):
        s = SessionState.from_dict({})
        self.assertIsNone(s.window_id)
        self.assertIsNone(s.tab_id)
        self.assertIsNone(s.session_id)
        self.assertEqual(s.notes, "")

    def test_clear(self):
        s = SessionState(window_id="w1", tab_id="t1", session_id="s1")
        s.clear()
        self.assertIsNone(s.window_id)
        self.assertIsNone(s.tab_id)
        self.assertIsNone(s.session_id)


# ── File persistence tests ─────────────────────────────────────────────

class TestSessionStatePersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "session.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_and_load_roundtrip(self):
        s = SessionState(window_id="w1", tab_id="t1", session_id="s1")
        save_state(s, self.path)
        loaded = load_state(self.path)
        self.assertEqual(loaded.window_id, "w1")
        self.assertEqual(loaded.tab_id, "t1")
        self.assertEqual(loaded.session_id, "s1")

    def test_save_creates_parent_dir(self):
        nested = os.path.join(self.tmp.name, "deep", "nested", "session.json")
        s = SessionState(window_id="w99")
        save_state(s, nested)
        self.assertTrue(os.path.exists(nested))

    def test_load_missing_file_returns_empty(self):
        missing = os.path.join(self.tmp.name, "nonexistent.json")
        s = load_state(missing)
        self.assertIsNone(s.window_id)

    def test_load_invalid_json_returns_empty(self):
        bad_path = os.path.join(self.tmp.name, "bad.json")
        with open(bad_path, "w") as f:
            f.write("NOT JSON {{{{")
        s = load_state(bad_path)
        self.assertIsNone(s.window_id)

    def test_clear_state(self):
        s = SessionState(window_id="w1")
        save_state(s, self.path)
        clear_state(self.path)
        loaded = load_state(self.path)
        self.assertIsNone(loaded.window_id)

    def test_overwrite_existing_state(self):
        s1 = SessionState(window_id="w1")
        save_state(s1, self.path)
        s2 = SessionState(window_id="w2", session_id="s2")
        save_state(s2, self.path)
        loaded = load_state(self.path)
        self.assertEqual(loaded.window_id, "w2")
        self.assertEqual(loaded.session_id, "s2")

    def test_saved_file_is_valid_json(self):
        s = SessionState(window_id="w1", tab_id="t1")
        save_state(s, self.path)
        with open(self.path) as f:
            data = json.load(f)
        self.assertEqual(data["window_id"], "w1")


# ── Backend utility tests ──────────────────────────────────────────────

class TestIterm2Backend(unittest.TestCase):
    def test_find_iterm2_app_absent(self):
        from cli_anything.iterm2_ctl.utils.iterm2_backend import find_iterm2_app
        with patch("os.path.isdir", return_value=False):
            with self.assertRaises(RuntimeError) as ctx:
                find_iterm2_app()
            self.assertIn("iTerm2", str(ctx.exception))
            self.assertIn("iterm2.com", str(ctx.exception))

    def test_find_iterm2_app_present(self):
        from cli_anything.iterm2_ctl.utils.iterm2_backend import find_iterm2_app
        with patch("os.path.isdir", return_value=True):
            path = find_iterm2_app()
            self.assertIn("iTerm", path)

    def test_require_iterm2_running_import_error(self):
        from cli_anything.iterm2_ctl.utils.iterm2_backend import require_iterm2_running
        with patch("builtins.__import__", side_effect=ImportError("no module")):
            with self.assertRaises((RuntimeError, ImportError)):
                require_iterm2_running()

    def test_connection_error_help_content(self):
        from cli_anything.iterm2_ctl.utils.iterm2_backend import connection_error_help
        help_text = connection_error_help()
        self.assertIn("iTerm2", help_text)
        self.assertIn("Python API", help_text)


# ── CLI help / structural tests ────────────────────────────────────────

class TestCLIHelp(unittest.TestCase):
    """Verify CLI structure without requiring iTerm2 connection."""

    def _invoke(self, args):
        from click.testing import CliRunner
        from cli_anything.iterm2_ctl.iterm2_ctl_cli import cli
        runner = CliRunner()
        return runner.invoke(cli, args)

    def test_main_help(self):
        result = self._invoke(["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("iterm2", result.output.lower())

    def test_app_help(self):
        result = self._invoke(["app", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("status", result.output)

    def test_window_help(self):
        result = self._invoke(["window", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("create", result.output)
        self.assertIn("list", result.output)

    def test_tab_help(self):
        result = self._invoke(["tab", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("create", result.output)

    def test_session_help(self):
        result = self._invoke(["session", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("send", result.output)
        self.assertIn("screen", result.output)

    def test_profile_help(self):
        result = self._invoke(["profile", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)

    def test_arrangement_help(self):
        result = self._invoke(["arrangement", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("save", result.output)
        self.assertIn("restore", result.output)

    def test_json_flag_in_help(self):
        result = self._invoke(["--help"])
        self.assertIn("json", result.output.lower())

    def test_session_send_help(self):
        result = self._invoke(["session", "send", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("text", result.output.lower())

    def test_session_split_help(self):
        result = self._invoke(["session", "split", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("vertical", result.output.lower())

    def test_tmux_help(self):
        result = self._invoke(["tmux", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("send", result.output)

    def test_tmux_list_help(self):
        result = self._invoke(["tmux", "list", "--help"])
        self.assertEqual(result.exit_code, 0)

    def test_tmux_send_help(self):
        result = self._invoke(["tmux", "send", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("command", result.output.lower())

    def test_tmux_create_window_help(self):
        result = self._invoke(["tmux", "create-window", "--help"])
        self.assertEqual(result.exit_code, 0)

    def test_tmux_set_visible_help(self):
        result = self._invoke(["tmux", "set-visible", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("on", result.output)
        self.assertIn("off", result.output)

    def test_tmux_tabs_help(self):
        result = self._invoke(["tmux", "tabs", "--help"])
        self.assertEqual(result.exit_code, 0)

    def test_session_run_tmux_cmd_help(self):
        result = self._invoke(["session", "run-tmux-cmd", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("command", result.output.lower())

    def test_session_get_prompt_help(self):
        result = self._invoke(["session", "get-prompt", "--help"])
        self.assertEqual(result.exit_code, 0)

    def test_session_wait_prompt_help(self):
        result = self._invoke(["session", "wait-prompt", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("timeout", result.output.lower())

    def test_session_wait_command_end_help(self):
        result = self._invoke(["session", "wait-command-end", "--help"])
        self.assertEqual(result.exit_code, 0)

    def test_app_get_var_help(self):
        result = self._invoke(["app", "get-var", "--help"])
        self.assertEqual(result.exit_code, 0)

    def test_app_set_var_help(self):
        result = self._invoke(["app", "set-var", "--help"])
        self.assertEqual(result.exit_code, 0)

    def test_broadcast_help(self):
        result = self._invoke(["broadcast", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("clear", result.output)

    def test_broadcast_list_help(self):
        result = self._invoke(["broadcast", "list", "--help"])
        self.assertEqual(result.exit_code, 0)

    def test_broadcast_set_help(self):
        result = self._invoke(["broadcast", "set", "--help"])
        self.assertEqual(result.exit_code, 0)

    def test_broadcast_add_help(self):
        result = self._invoke(["broadcast", "add", "--help"])
        self.assertEqual(result.exit_code, 0)

    def test_broadcast_all_panes_help(self):
        result = self._invoke(["broadcast", "all-panes", "--help"])
        self.assertEqual(result.exit_code, 0)

    def test_menu_help(self):
        result = self._invoke(["menu", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("select", result.output)
        self.assertIn("list-common", result.output)

    def test_menu_select_help(self):
        result = self._invoke(["menu", "select", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("identifier", result.output.lower())

    def test_menu_list_common_help(self):
        result = self._invoke(["menu", "list-common", "--help"])
        self.assertEqual(result.exit_code, 0)

    def test_pref_help(self):
        result = self._invoke(["pref", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("get", result.output)
        self.assertIn("set", result.output)
        self.assertIn("tmux-get", result.output)

    def test_pref_get_help(self):
        result = self._invoke(["pref", "get", "--help"])
        self.assertEqual(result.exit_code, 0)

    def test_pref_tmux_get_help(self):
        result = self._invoke(["pref", "tmux-get", "--help"])
        self.assertEqual(result.exit_code, 0)

    def test_pref_tmux_set_help(self):
        result = self._invoke(["pref", "tmux-set", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("open_in", result.output)

    def test_pref_theme_help(self):
        result = self._invoke(["pref", "theme", "--help"])
        self.assertEqual(result.exit_code, 0)

    def test_tmux_bootstrap_help(self):
        result = self._invoke(["tmux", "bootstrap", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("attach", result.output.lower())


# ── Tmux core logic tests ──────────────────────────────────────────────

class TestTmuxCore(unittest.TestCase):
    """Unit tests for core/tmux.py logic that doesn't need a live connection."""

    def test_resolve_connection_empty_raises(self):
        """_resolve_connection raises RuntimeError when no connections exist."""
        import asyncio
        from unittest.mock import AsyncMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.tmux import _resolve_connection

            mock_conn = MagicMock()

            with patch(
                "cli_anything.iterm2_ctl.core.tmux._ensure_app_and_connections",
                new=AsyncMock(return_value=[]),
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    await _resolve_connection(mock_conn, None)
                self.assertIn("tmux -CC", str(ctx.exception))

        asyncio.run(_run())

    def test_resolve_connection_by_id_not_found(self):
        """_resolve_connection raises ValueError for unknown connection ID."""
        import asyncio
        from unittest.mock import AsyncMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.tmux import _resolve_connection

            mock_conn_obj = MagicMock()
            mock_conn_obj.connection_id = "real-id"

            with patch(
                "cli_anything.iterm2_ctl.core.tmux._ensure_app_and_connections",
                new=AsyncMock(return_value=[mock_conn_obj]),
            ):
                with self.assertRaises(ValueError) as ctx:
                    await _resolve_connection(MagicMock(), "wrong-id")
                self.assertIn("real-id", str(ctx.exception))

        asyncio.run(_run())

    def test_resolve_connection_returns_first_when_no_id(self):
        """_resolve_connection returns the first connection when ID is None."""
        import asyncio
        from unittest.mock import AsyncMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.tmux import _resolve_connection

            c1 = MagicMock()
            c1.connection_id = "conn-1"
            c2 = MagicMock()
            c2.connection_id = "conn-2"

            with patch(
                "cli_anything.iterm2_ctl.core.tmux._ensure_app_and_connections",
                new=AsyncMock(return_value=[c1, c2]),
            ):
                result = await _resolve_connection(MagicMock(), None)
                self.assertEqual(result.connection_id, "conn-1")

        asyncio.run(_run())

    def test_list_connections_empty(self):
        """list_connections returns empty list when no tmux connections."""
        import asyncio
        from unittest.mock import AsyncMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.tmux import list_connections

            with patch(
                "cli_anything.iterm2_ctl.core.tmux._ensure_app_and_connections",
                new=AsyncMock(return_value=[]),
            ):
                result = await list_connections(MagicMock())
                self.assertEqual(result, [])

        asyncio.run(_run())

    def test_list_connections_formats_result(self):
        """list_connections returns dicts with expected keys."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.tmux import list_connections

            mock_session = MagicMock()
            mock_session.session_id = "sess-1"
            mock_session.name = "bash"

            mock_conn = MagicMock()
            mock_conn.connection_id = "user@host"
            mock_conn.owning_session = mock_session

            with patch(
                "cli_anything.iterm2_ctl.core.tmux._ensure_app_and_connections",
                new=AsyncMock(return_value=[mock_conn]),
            ):
                result = await list_connections(MagicMock())
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["connection_id"], "user@host")
                self.assertEqual(result[0]["owning_session_id"], "sess-1")
                self.assertEqual(result[0]["owning_session_name"], "bash")

        asyncio.run(_run())

    def test_send_command_returns_output(self):
        """send_command returns connection_id, command, and output."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.tmux import send_command

            mock_tc = MagicMock()
            mock_tc.connection_id = "user@host"
            mock_tc.async_send_command = AsyncMock(return_value="session1\nsession2\n")

            with patch(
                "cli_anything.iterm2_ctl.core.tmux._resolve_connection",
                new=AsyncMock(return_value=mock_tc),
            ):
                result = await send_command(MagicMock(), "list-sessions")
                self.assertEqual(result["command"], "list-sessions")
                self.assertEqual(result["output"], "session1\nsession2\n")
                self.assertEqual(result["connection_id"], "user@host")

        asyncio.run(_run())

    def test_set_window_visible_on(self):
        """set_window_visible calls async_set_tmux_window_visible with correct args."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.tmux import set_window_visible

            mock_tc = MagicMock()
            mock_tc.connection_id = "user@host"
            mock_tc.async_set_tmux_window_visible = AsyncMock()

            with patch(
                "cli_anything.iterm2_ctl.core.tmux._resolve_connection",
                new=AsyncMock(return_value=mock_tc),
            ):
                result = await set_window_visible(MagicMock(), "@1", True)
                mock_tc.async_set_tmux_window_visible.assert_awaited_once_with("@1", True)
                self.assertEqual(result["tmux_window_id"], "@1")
                self.assertTrue(result["visible"])

        asyncio.run(_run())


# ── Broadcast core logic tests ────────────────────────────────────────

class TestBroadcastCore(unittest.TestCase):
    """Unit tests for core/broadcast.py."""

    def test_get_broadcast_domains_empty(self):
        """get_broadcast_domains returns empty list when no domains active."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.broadcast import get_broadcast_domains

            mock_app = MagicMock()
            mock_app.async_refresh_broadcast_domains = AsyncMock()
            mock_app.broadcast_domains = []

            with patch(
                "iterm2.async_get_app",
                new=AsyncMock(return_value=mock_app),
            ):
                result = await get_broadcast_domains(MagicMock())
                self.assertEqual(result, [])

        asyncio.run(_run())

    def test_clear_broadcast_calls_set(self):
        """clear_broadcast calls async_set_broadcast_domains with empty list."""
        import asyncio
        from unittest.mock import AsyncMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.broadcast import clear_broadcast

            with patch(
                "iterm2.async_set_broadcast_domains",
                new=AsyncMock(),
            ) as mock_set:
                result = await clear_broadcast(MagicMock())
                mock_set.assert_awaited_once()
                self.assertEqual(result["domains"], [])
                self.assertTrue(result["cleared"])

        asyncio.run(_run())


# ── Menu core logic tests ──────────────────────────────────────────────

class TestMenuCore(unittest.TestCase):
    """Unit tests for core/menu.py."""

    def test_list_common_menu_items_structure(self):
        """list_common_menu_items returns list of dicts with identifier+description."""
        import asyncio

        async def _run():
            from cli_anything.iterm2_ctl.core.menu import list_common_menu_items
            result = await list_common_menu_items(MagicMock())
            self.assertIsInstance(result, list)
            self.assertGreater(len(result), 0)
            for item in result:
                self.assertIn("identifier", item)
                self.assertIn("description", item)

        asyncio.run(_run())

    def test_select_menu_item_calls_api(self):
        """select_menu_item calls MainMenu.async_select_menu_item."""
        import asyncio
        from unittest.mock import AsyncMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.menu import select_menu_item

            with patch(
                "iterm2.MainMenu.async_select_menu_item",
                new=AsyncMock(),
            ) as mock_select:
                result = await select_menu_item(MagicMock(), "Shell/New Window")
                mock_select.assert_awaited_once()
                self.assertTrue(result["invoked"])
                self.assertEqual(result["identifier"], "Shell/New Window")

        asyncio.run(_run())


# ── Pref core logic tests ──────────────────────────────────────────────

class TestPrefCore(unittest.TestCase):
    """Unit tests for core/pref.py."""

    def test_parse_value_bool_true(self):
        from cli_anything.iterm2_ctl.core.pref import _parse_value
        self.assertTrue(_parse_value("true"))
        self.assertTrue(_parse_value("True"))
        self.assertTrue(_parse_value("TRUE"))

    def test_parse_value_bool_false(self):
        from cli_anything.iterm2_ctl.core.pref import _parse_value
        self.assertFalse(_parse_value("false"))

    def test_parse_value_int(self):
        from cli_anything.iterm2_ctl.core.pref import _parse_value
        self.assertEqual(_parse_value("42"), 42)
        self.assertIsInstance(_parse_value("42"), int)

    def test_parse_value_float(self):
        from cli_anything.iterm2_ctl.core.pref import _parse_value
        self.assertAlmostEqual(_parse_value("3.14"), 3.14)

    def test_parse_value_string(self):
        from cli_anything.iterm2_ctl.core.pref import _parse_value
        self.assertEqual(_parse_value("hello"), "hello")

    def test_parse_value_passthrough_non_string(self):
        from cli_anything.iterm2_ctl.core.pref import _parse_value
        self.assertEqual(_parse_value(42), 42)

    def test_set_tmux_preference_unknown_setting(self):
        """set_tmux_preference raises ValueError for unknown setting name."""
        import asyncio

        async def _run():
            from cli_anything.iterm2_ctl.core.pref import set_tmux_preference
            with self.assertRaises(ValueError) as ctx:
                await set_tmux_preference(MagicMock(), "nonexistent_setting", "1")
            self.assertIn("nonexistent_setting", str(ctx.exception))

        asyncio.run(_run())


# ── Prompt core logic tests ────────────────────────────────────────────

class TestPromptCore(unittest.TestCase):
    """Unit tests for core/prompt.py."""

    def test_prompt_to_dict_none(self):
        """_prompt_to_dict handles None (Shell Integration absent)."""
        from cli_anything.iterm2_ctl.core.prompt import _prompt_to_dict
        result = _prompt_to_dict(None)
        self.assertFalse(result["available"])

    def test_prompt_to_dict_with_mock(self):
        """_prompt_to_dict converts a mock prompt object to dict."""
        from cli_anything.iterm2_ctl.core.prompt import _prompt_to_dict
        mock_prompt = MagicMock()
        mock_prompt.unique_id = "uid-1"
        mock_prompt.command = "ls -la"
        mock_prompt.working_directory = "/home/user"
        mock_prompt.state = MagicMock()
        mock_prompt.state.name = "RUNNING"
        mock_prompt.prompt_range = None
        mock_prompt.command_range = MagicMock()
        mock_prompt.output_range = None
        result = _prompt_to_dict(mock_prompt)
        self.assertTrue(result["available"])
        self.assertEqual(result["command"], "ls -la")
        self.assertEqual(result["working_directory"], "/home/user")
        self.assertEqual(result["state"], "RUNNING")
        self.assertFalse(result["has_prompt_range"])
        self.assertTrue(result["has_command_range"])

    def test_get_last_prompt_returns_unavailable_for_none(self):
        """get_last_prompt returns available=False when API returns None."""
        import asyncio
        from unittest.mock import AsyncMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.prompt import get_last_prompt

            with patch(
                "iterm2.async_get_last_prompt",
                new=AsyncMock(return_value=None),
            ):
                result = await get_last_prompt(MagicMock(), "sess-1")
                self.assertFalse(result["available"])

        asyncio.run(_run())

    def test_list_prompts_empty(self):
        """list_prompts returns empty list when no prompts recorded."""
        import asyncio
        from unittest.mock import AsyncMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.prompt import list_prompts

            with patch(
                "iterm2.async_list_prompts",
                new=AsyncMock(return_value=[]),
            ):
                result = await list_prompts(MagicMock(), "sess-1")
                self.assertEqual(result["prompt_ids"], [])
                self.assertEqual(result["count"], 0)
                self.assertEqual(result["session_id"], "sess-1")

        asyncio.run(_run())


# ── Tmux bootstrap logic tests ─────────────────────────────────────────

class TestTmuxBootstrap(unittest.TestCase):
    """Unit tests for core/tmux.bootstrap()."""

    def test_bootstrap_timeout_raises(self):
        """bootstrap raises RuntimeError when no connection appears in time."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.tmux import bootstrap

            mock_session = MagicMock()
            mock_session.async_send_text = AsyncMock()

            mock_tab = MagicMock()
            mock_tab.current_session = mock_session

            mock_window = MagicMock()
            mock_window.current_tab = mock_tab

            mock_app = MagicMock()
            mock_app.windows = [mock_window]

            with patch("iterm2.async_get_app", new=AsyncMock(return_value=mock_app)), \
                 patch("iterm2.async_get_tmux_connections", new=AsyncMock(return_value=[])):
                with self.assertRaises(RuntimeError) as ctx:
                    await bootstrap(MagicMock(), timeout=0.1)
                self.assertIn("Timed out", str(ctx.exception))

        asyncio.run(_run())

    def test_bootstrap_no_windows_raises(self):
        """bootstrap raises RuntimeError when no windows exist."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.tmux import bootstrap

            mock_app = MagicMock()
            mock_app.windows = []

            with patch("iterm2.async_get_app", new=AsyncMock(return_value=mock_app)), \
                 patch("iterm2.async_get_tmux_connections", new=AsyncMock(return_value=[])):
                with self.assertRaises(RuntimeError) as ctx:
                    await bootstrap(MagicMock(), timeout=0.1)
                self.assertIn("No iTerm2 windows", str(ctx.exception))

        asyncio.run(_run())


# ── CLI help tests for new commands ────────────────────────────────────

class TestNewCommandHelp(unittest.TestCase):
    """Smoke-test --help for every new command added in the refine pass."""

    def _help(self, *args):
        from click.testing import CliRunner
        from cli_anything.iterm2_ctl.iterm2_ctl_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, list(args) + ["--help"])
        self.assertEqual(result.exit_code, 0, result.output)
        return result.output

    def test_app_alert_help(self):
        out = self._help("app", "alert")
        self.assertIn("modal alert", out.lower())

    def test_app_text_input_help(self):
        out = self._help("app", "text-input")
        self.assertIn("text input", out.lower())

    def test_app_file_panel_help(self):
        out = self._help("app", "file-panel")
        self.assertIn("open file panel", out.lower())

    def test_app_save_panel_help(self):
        out = self._help("app", "save-panel")
        self.assertIn("save file panel", out.lower())

    def test_session_inject_help(self):
        out = self._help("session", "inject")
        self.assertIn("inject", out.lower())
        self.assertIn("hex", out.lower())

    def test_tab_select_pane_help(self):
        out = self._help("tab", "select-pane")
        self.assertIn("direction", out.lower())

    def test_profile_get_help(self):
        out = self._help("profile", "get")
        self.assertIn("guid", out.lower())

    def test_pref_list_keys_help(self):
        out = self._help("pref", "list-keys")
        self.assertIn("preference", out.lower())


# ── Dialogs core tests ──────────────────────────────────────────────────

class TestDialogsCore(unittest.TestCase):
    def test_show_alert_calls_api(self):
        """show_alert constructs an Alert and returns button info."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.dialogs import show_alert

            mock_alert_instance = MagicMock()
            mock_alert_instance.async_run = AsyncMock(return_value=1000)

            with patch("iterm2.Alert", return_value=mock_alert_instance):
                result = await show_alert(MagicMock(), "Title", "Sub")
            self.assertEqual(result["button_index"], 1000)
            self.assertEqual(result["button_label"], "OK")

        asyncio.run(_run())

    def test_show_alert_with_buttons(self):
        """show_alert maps button index back to label."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.dialogs import show_alert

            mock_alert_instance = MagicMock()
            mock_alert_instance.async_run = AsyncMock(return_value=1001)

            with patch("iterm2.Alert", return_value=mock_alert_instance):
                result = await show_alert(MagicMock(), "T", "S",
                                          buttons=["Yes", "No"])
            self.assertEqual(result["button_index"], 1001)
            self.assertEqual(result["button_label"], "No")

        asyncio.run(_run())

    def test_show_text_input_cancelled(self):
        """show_text_input returns cancelled=True when result is None."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.dialogs import show_text_input

            mock_alert = MagicMock()
            mock_alert.async_run = AsyncMock(return_value=None)

            with patch("iterm2.TextInputAlert", return_value=mock_alert):
                result = await show_text_input(MagicMock(), "T", "S")
            self.assertTrue(result["cancelled"])
            self.assertIsNone(result["text"])

        asyncio.run(_run())

    def test_show_text_input_value(self):
        """show_text_input returns entered text."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.dialogs import show_text_input

            mock_alert = MagicMock()
            mock_alert.async_run = AsyncMock(return_value="hello")

            with patch("iterm2.TextInputAlert", return_value=mock_alert):
                result = await show_text_input(MagicMock(), "T", "S")
            self.assertFalse(result["cancelled"])
            self.assertEqual(result["text"], "hello")

        asyncio.run(_run())

    def test_show_open_panel_cancelled(self):
        """show_open_panel returns cancelled=True when panel is dismissed."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.dialogs import show_open_panel

            mock_panel = MagicMock()
            mock_panel.async_run = AsyncMock(return_value=None)

            with patch("iterm2.OpenPanel", return_value=mock_panel):
                result = await show_open_panel(MagicMock(), "Open")
            self.assertTrue(result["cancelled"])
            self.assertEqual(result["files"], [])

        asyncio.run(_run())

    def test_show_open_panel_files(self):
        """show_open_panel returns chosen files."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.dialogs import show_open_panel

            mock_result = MagicMock()
            mock_result.files = ["/Users/alex/foo.py"]

            mock_panel = MagicMock()
            mock_panel.async_run = AsyncMock(return_value=mock_result)
            mock_panel.options = []

            with patch("iterm2.OpenPanel", return_value=mock_panel):
                result = await show_open_panel(MagicMock(), "Open")
            self.assertFalse(result["cancelled"])
            self.assertEqual(result["files"], ["/Users/alex/foo.py"])

        asyncio.run(_run())


# ── Tab select-pane tests ───────────────────────────────────────────────

class TestTabSelectPane(unittest.TestCase):
    def test_invalid_direction_raises(self):
        """select_pane_in_direction raises ValueError for unknown direction."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.tab import select_pane_in_direction

            with self.assertRaises(ValueError) as ctx:
                await select_pane_in_direction(MagicMock(), "t1", "diagonal")
            self.assertIn("diagonal", str(ctx.exception))

        asyncio.run(_run())

    def test_valid_direction_calls_api(self):
        """select_pane_in_direction calls async_select_pane_in_direction."""
        import asyncio
        import iterm2
        from unittest.mock import AsyncMock, MagicMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.tab import select_pane_in_direction

            mock_tab = MagicMock()
            mock_tab.tab_id = "t1"
            mock_tab.async_select_pane_in_direction = AsyncMock(return_value="s_new")

            with patch("cli_anything.iterm2_ctl.utils.iterm2_backend.async_find_tab",
                       new=AsyncMock(return_value=mock_tab)):
                result = await select_pane_in_direction(MagicMock(), "t1", "right")

            self.assertEqual(result["new_session_id"], "s_new")
            self.assertTrue(result["moved"])

        asyncio.run(_run())

    def test_no_pane_in_direction(self):
        """Returns moved=False when API returns None."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        async def _run():
            from cli_anything.iterm2_ctl.core.tab import select_pane_in_direction

            mock_tab = MagicMock()
            mock_tab.tab_id = "t1"
            mock_tab.async_select_pane_in_direction = AsyncMock(return_value=None)

            with patch("cli_anything.iterm2_ctl.utils.iterm2_backend.async_find_tab",
                       new=AsyncMock(return_value=mock_tab)):
                result = await select_pane_in_direction(MagicMock(), "t1", "left")

            self.assertFalse(result["moved"])

        asyncio.run(_run())


# ── Session inject tests ────────────────────────────────────────────────

class TestSessionInjectCLI(unittest.TestCase):
    def test_inject_help(self):
        from click.testing import CliRunner
        from cli_anything.iterm2_ctl.iterm2_ctl_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["session", "inject", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("--hex", result.output)

    def test_inject_hex_invalid(self):
        """--hex with invalid hex string exits with error."""
        from click.testing import CliRunner
        from cli_anything.iterm2_ctl.iterm2_ctl_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["session", "inject", "ZZZZ", "--hex"])
        self.assertNotEqual(result.exit_code, 0)


# ── pref list-keys tests ────────────────────────────────────────────────

class TestPrefListKeys(unittest.TestCase):
    def test_list_keys_returns_keys(self):
        from click.testing import CliRunner
        from cli_anything.iterm2_ctl.iterm2_ctl_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["pref", "list-keys"])
        self.assertEqual(result.exit_code, 0)
        # Should list something
        self.assertIn("preference key(s)", result.output)

    def test_list_keys_filter(self):
        from click.testing import CliRunner
        from cli_anything.iterm2_ctl.iterm2_ctl_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["pref", "list-keys", "--filter", "TMUX"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("TMUX", result.output)


# ── _get_process_name tests ────────────────────────────────────────────

class TestGetProcessName(unittest.TestCase):
    def test_returns_none_for_none_pid(self):
        from cli_anything.iterm2_ctl.core.session import _get_process_name
        self.assertIsNone(_get_process_name(None))

    def test_returns_process_name_for_real_pid(self):
        """Should return a non-empty string for the current process PID."""
        import os
        from cli_anything.iterm2_ctl.core.session import _get_process_name
        name = _get_process_name(os.getpid())
        self.assertIsNotNone(name)
        self.assertIsInstance(name, str)
        self.assertGreater(len(name), 0)

    def test_returns_none_for_invalid_pid(self):
        from cli_anything.iterm2_ctl.core.session import _get_process_name
        # PID 999999999 almost certainly doesn't exist
        result = _get_process_name(999999999)
        self.assertIsNone(result)

    def test_strips_path_prefix(self):
        """Should return only the basename, not a full path like /usr/bin/python3."""
        from cli_anything.iterm2_ctl.core.session import _get_process_name
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="/usr/bin/python3\n", returncode=0)
            result = _get_process_name(12345)
        self.assertEqual(result, "python3")

    def test_returns_none_on_subprocess_exception(self):
        from cli_anything.iterm2_ctl.core.session import _get_process_name
        with patch("subprocess.run", side_effect=OSError("no ps")):
            result = _get_process_name(12345)
        self.assertIsNone(result)

    def test_handles_string_pid(self):
        """PIDs from iTerm2 variables arrive as strings."""
        from cli_anything.iterm2_ctl.core.session import _get_process_name
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="zsh\n", returncode=0)
            result = _get_process_name("12345")
        self.assertEqual(result, "zsh")


if __name__ == "__main__":
    unittest.main(verbosity=2)
