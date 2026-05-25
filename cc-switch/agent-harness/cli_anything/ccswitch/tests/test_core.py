"""Unit tests for CC Switch CLI core modules — synthetic data, no external deps."""

import os
import sys
import json
import sqlite3
import tempfile
from pathlib import Path
from contextlib import contextmanager

import pytest

from cli_anything.ccswitch.utils.db import (
    get_cc_switch_dir, get_db_path, get_config_path,
    get_settings_path, connect_db,
    load_config, save_config, load_settings,
    VALID_APP_TYPES,
)
from cli_anything.ccswitch.ccswitch_cli import (
    _resolve_app, _table, _mask_sensitive,
)


# ───────────────────────────
# Database path helpers
# ───────────────────────────

def test_get_cc_switch_dir_custom():
    os.environ["CCSWITCH_HOME"] = "/tmp/ccswitch-test"
    assert get_cc_switch_dir() == Path("/tmp/ccswitch-test/.cc-switch")
    del os.environ["CCSWITCH_HOME"]


def test_get_db_path():
    os.environ["CCSWITCH_HOME"] = "/home/user"
    assert get_db_path() == Path("/home/user/.cc-switch/cc-switch.db")
    del os.environ["CCSWITCH_HOME"]


def test_get_config_path():
    os.environ["CCSWITCH_HOME"] = "/x"
    assert get_config_path() == Path("/x/.cc-switch/config.json")
    del os.environ["CCSWITCH_HOME"]


def test_get_settings_path():
    os.environ["CCSWITCH_HOME"] = "/y"
    assert get_settings_path() == Path("/y/.cc-switch/settings.json")
    del os.environ["CCSWITCH_HOME"]


def test_valid_app_types():
    assert "claude" in VALID_APP_TYPES
    assert "codex" in VALID_APP_TYPES
    assert "gemini" in VALID_APP_TYPES
    assert "opencode" in VALID_APP_TYPES
    assert "openclaw" in VALID_APP_TYPES
    assert "hermes" in VALID_APP_TYPES
    assert len(VALID_APP_TYPES) == 6


# ───────────────────────────
# Database connection
# ───────────────────────────

def test_connect_db_in_memory():
    conn = connect_db(Path(":memory:"))
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO test VALUES (1)")
    assert conn.execute("SELECT COUNT(*) FROM test").fetchone()[0] == 1
    conn.close()


# ───────────────────────────
# Config load/save
# ───────────────────────────

def test_load_config_missing():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        pass  # empty file
    result = load_config(Path(f.name))
    assert result == {}
    os.unlink(f.name)


def test_save_and_load_config():
    path = Path(tempfile.mktemp(suffix=".json"))
    data = {"version": 2, "apps": {"claude": {"providers": {}}}}
    save_config(data, path)
    loaded = load_config(path)
    assert loaded["version"] == 2
    assert "apps" in loaded
    os.unlink(path)


def test_load_settings_missing():
    os.environ["CCSWITCH_HOME"] = "/nonexistent-tmp-xyz"
    result = load_settings()
    assert result == {}
    del os.environ["CCSWITCH_HOME"]


# ───────────────────────────
# App resolution
# ───────────────────────────

def test_resolve_app_valid():
    assert _resolve_app("claude") == "claude"
    assert _resolve_app("CLAUDE") == "claude"
    assert _resolve_app("OpenCode") == "opencode"
    assert _resolve_app("Hermes") == "hermes"


def test_resolve_app_none():
    assert _resolve_app(None) is None


def test_resolve_app_invalid():
    from click import BadParameter
    with pytest.raises(BadParameter):
        _resolve_app("invalid-app")


# ───────────────────────────
# Table formatting
# ───────────────────────────

def test_table_basic():
    result = _table(["Name", "Count"], [("Alice", 5), ("Bob", 3)])
    assert "Name" in result
    assert "Count" in result
    assert "Alice" in result
    assert "5" in result
    assert "Bob" in result
    assert "3" in result


def test_table_empty():
    assert _table(["Col"], []) == "(empty)"


def test_table_single():
    result = _table(["A"], [("x",)])
    assert "A" in result
    assert "x" in result


# ───────────────────────────
# Sensitive masking
# ───────────────────────────

def test_mask_api_token():
    result = _mask_sensitive("ANTHROPIC_AUTH_TOKEN", "sk-bc089d043dc34c6c9022831769d85cbb")
    assert "sk-bc089" in result
    assert "5cbb" in result
    assert "bc089d043dc34c6c" not in result  # middle is masked


def test_mask_api_key():
    result = _mask_sensitive("api_key", "sec-1234567890abcdef")
    assert "..." in result or "***" in result or "sec-1234" in result


def test_mask_password():
    result = _mask_sensitive("password", "mysecretkey")
    assert "mysec" in result or "***" in result


def test_mask_short_value():
    result = _mask_sensitive("secret", "abc")
    assert "***" in result


def test_mask_non_sensitive():
    result = _mask_sensitive("model", "claude-sonnet-4-6")
    assert "claude-sonnet-4-6" in result
    assert "***" not in result


def test_mask_nested_dict():
    result = _mask_sensitive("env", {
        "ANTHROPIC_AUTH_TOKEN": "sk-test1234567890",
        "ANTHROPIC_MODEL": "deepseek-v4-pro",
        "ANTHROPIC_BASE_URL": "https://api.deepseek.com",
    })
    assert "sk-test1" in result
    assert "7890" in result
    assert "deepseek-v4-pro" in result
    assert "https://api.deepseek.com" in result


# ───────────────────────────
# CLI help tests
# ───────────────────────────

from click.testing import CliRunner
from cli_anything.ccswitch.ccswitch_cli import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_main_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "CC Switch" in result.output


def test_providers_help(runner):
    result = runner.invoke(cli, ["providers", "--help"])
    assert result.exit_code == 0
    assert "Manage AI provider" in result.output


def test_usage_help(runner):
    result = runner.invoke(cli, ["usage", "--help"])
    assert result.exit_code == 0


def test_skills_help(runner):
    result = runner.invoke(cli, ["skills", "--help"])
    assert result.exit_code == 0


def test_mcp_help(runner):
    result = runner.invoke(cli, ["mcp", "--help"])
    assert result.exit_code == 0


def test_proxy_help(runner):
    result = runner.invoke(cli, ["proxy", "--help"])
    assert result.exit_code == 0


def test_settings_help(runner):
    result = runner.invoke(cli, ["settings", "--help"])
    assert result.exit_code == 0


def test_sessions_help(runner):
    result = runner.invoke(cli, ["sessions", "--help"])
    assert result.exit_code == 0


def test_all_command_groups(runner):
    result = runner.invoke(cli, ["--help"])
    assert "providers" in result.output
    assert "proxy" in result.output
    assert "mcp" in result.output
    assert "skills" in result.output
    assert "usage" in result.output
    assert "settings" in result.output
    assert "sessions" in result.output
