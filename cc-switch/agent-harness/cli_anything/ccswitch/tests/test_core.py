"""Unit tests for CC Switch CLI core modules — synthetic data, no external deps."""

import os
import sys
import json
import sqlite3
import tempfile
from pathlib import Path
from contextlib import contextmanager

import pytest
import tomlkit

from cli_anything.ccswitch.utils.db import (
    get_cc_switch_dir, get_db_path, get_config_path,
    get_settings_path, connect_db,
    load_config, save_config, load_settings,
    VALID_APP_TYPES,
)
from cli_anything.ccswitch.ccswitch_cli import (
    _resolve_app, _table, _mask_sensitive, _mask_value, _write_live_config,
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


def test_mask_hotkey_is_not_treated_as_secret():
    assert _mask_sensitive("hotkey", "ctrl+k") == "ctrl+k"


def test_mask_short_value():
    result = _mask_sensitive("secret", "abc")
    assert result == "***"


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

def test_mask_value_nested_json():
    result = _mask_value({
        "env": {
            "ANTHROPIC_AUTH_TOKEN": "sk-test1234567890",
            "ANTHROPIC_MODEL": "deepseek-v4-pro",
        },
        "headers": [
            {"authorization": "Bearer abcdef1234567890"},
        ],
    })

    assert result["env"]["ANTHROPIC_AUTH_TOKEN"] != "sk-test1234567890"
    assert result["env"]["ANTHROPIC_MODEL"] == "deepseek-v4-pro"
    assert result["headers"][0]["authorization"] != "Bearer abcdef1234567890"


def test_mask_sensitive_nested_list():
    result = _mask_sensitive("headers", [
        {"authorization": "Bearer abcdef1234567890"},
    ])

    assert "Bearer abcdef1234567890" not in result
    assert "headers" not in result


from click.testing import CliRunner
from cli_anything.ccswitch.ccswitch_cli import cli


@pytest.fixture
def runner():
    return CliRunner()


def _init_cli_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE providers (
            id TEXT,
            app_type TEXT,
            name TEXT,
            category TEXT,
            is_current INTEGER,
            sort_index INTEGER,
            settings_config TEXT
        );
        CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE skills (
            id TEXT,
            name TEXT DEFAULT '',
            description TEXT,
            repo_owner TEXT,
            repo_name TEXT,
            enabled_claude INTEGER DEFAULT 0,
            enabled_codex INTEGER DEFAULT 0,
            enabled_gemini INTEGER DEFAULT 0,
            enabled_opencode INTEGER DEFAULT 0,
            enabled_openclaw INTEGER DEFAULT 0,
            enabled_hermes INTEGER DEFAULT 0
        );
        CREATE TABLE mcp_servers (
            id TEXT,
            name TEXT DEFAULT '',
            description TEXT,
            enabled_claude INTEGER DEFAULT 0,
            enabled_codex INTEGER DEFAULT 0,
            enabled_gemini INTEGER DEFAULT 0,
            enabled_opencode INTEGER DEFAULT 0,
            enabled_openclaw INTEGER DEFAULT 0,
            enabled_hermes INTEGER DEFAULT 0
        );
        CREATE TABLE proxy_request_logs (
            app_type TEXT,
            model TEXT,
            status_code INTEGER,
            input_tokens INTEGER,
            output_tokens INTEGER,
            total_cost_usd TEXT,
            latency_ms INTEGER,
            created_at INTEGER
        );
        CREATE TABLE session_log_sync (
            file_path TEXT,
            last_modified INTEGER,
            last_synced_at INTEGER
        );
    """)
    return conn


def test_providers_get_json_masks_settings_config(runner, tmp_path):
    db_path = tmp_path / "cc-switch.db"
    conn = _init_cli_db(db_path)
    conn.execute(
        "INSERT INTO providers VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "deepseek",
            "claude",
            "DeepSeek",
            "default",
            1,
            0,
            json.dumps({
                "env": {
                    "ANTHROPIC_AUTH_TOKEN": "sk-test1234567890",
                    "ANTHROPIC_MODEL": "deepseek-v4-pro",
                },
                "headers": [{"authorization": "Bearer abcdef1234567890"}],
            }),
        ),
    )
    conn.commit()
    conn.close()

    result = runner.invoke(cli, [
        "--json", "--db", str(db_path),
        "providers", "get", "deepseek", "--app", "claude",
    ])

    assert result.exit_code == 0
    data = json.loads(result.output)
    output = json.dumps(data)
    assert "sk-test1234567890" not in output
    assert "Bearer abcdef1234567890" not in output
    assert data["settings_config"]["env"]["ANTHROPIC_MODEL"] == "deepseek-v4-pro"


def test_providers_get_plain_masks_nested_list(runner, tmp_path):
    db_path = tmp_path / "cc-switch.db"
    conn = _init_cli_db(db_path)
    conn.execute(
        "INSERT INTO providers VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "deepseek",
            "claude",
            "DeepSeek",
            "default",
            1,
            0,
            json.dumps({
                "headers": [{"authorization": "Bearer abcdef1234567890"}],
                "model": "deepseek-v4-pro",
            }),
        ),
    )
    conn.commit()
    conn.close()

    result = runner.invoke(cli, [
        "--db", str(db_path),
        "providers", "get", "deepseek", "--app", "claude",
    ])

    assert result.exit_code == 0
    assert "Bearer abcdef1234567890" not in result.output
    assert "deepseek-v4-pro" in result.output


def test_status_command_json(runner, tmp_path):
    db_path = tmp_path / "cc-switch.db"
    conn = _init_cli_db(db_path)
    conn.execute(
        "INSERT INTO providers VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("deepseek", "claude", "DeepSeek", "default", 1, 0, "{}"),
    )
    conn.execute("INSERT INTO skills (id) VALUES (?)", ("skill-1",))
    conn.execute("INSERT INTO mcp_servers (id) VALUES (?)", ("mcp-1",))
    conn.commit()
    conn.close()

    result = runner.invoke(cli, ["--json", "--db", str(db_path), "status"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {
        "providers": 1,
        "current": {"claude": "DeepSeek"},
        "skills": 1,
        "mcp_servers": 1,
    }


def test_sessions_list_json_empty_outputs_array(runner, tmp_path):
    db_path = tmp_path / "cc-switch.db"
    conn = _init_cli_db(db_path)
    conn.commit()
    conn.close()

    result = runner.invoke(cli, ["--json", "--db", str(db_path), "sessions", "list"])

    assert result.exit_code == 0
    assert json.loads(result.output) == []


def test_settings_get_json_outputs_object(runner, tmp_path):
    db_path = tmp_path / "cc-switch.db"
    conn = _init_cli_db(db_path)
    conn.execute("INSERT INTO settings VALUES (?, ?)", ("theme", "dark"))
    conn.commit()
    conn.close()

    result = runner.invoke(cli, [
        "--json", "--db", str(db_path), "settings", "get", "theme",
    ])

    assert result.exit_code == 0
    assert json.loads(result.output) == {"theme": "dark"}


def test_settings_outputs_mask_sensitive_values(runner, tmp_path):
    db_path = tmp_path / "cc-switch.db"
    conn = _init_cli_db(db_path)
    conn.execute("INSERT INTO settings VALUES (?, ?)", ("OPENAI_API_KEY", "sk-secret1234567890"))
    conn.commit()
    conn.close()

    get_result = runner.invoke(cli, [
        "--json", "--db", str(db_path), "settings", "get", "OPENAI_API_KEY",
    ])
    list_result = runner.invoke(cli, [
        "--json", "--db", str(db_path), "settings", "list",
    ])
    set_result = runner.invoke(cli, [
        "--db", str(db_path), "settings", "set", "OPENAI_API_KEY", "sk-newsecret1234567890",
    ])

    assert get_result.exit_code == 0
    assert list_result.exit_code == 0
    assert set_result.exit_code == 0
    combined = get_result.output + list_result.output + set_result.output
    assert "sk-secret1234567890" not in combined
    assert "sk-newsecret1234567890" not in combined
    assert json.loads(get_result.output)["OPENAI_API_KEY"] != "sk-secret1234567890"

    conn = sqlite3.connect(db_path)
    assert conn.execute(
        "SELECT value FROM settings WHERE key=?", ("OPENAI_API_KEY",)
    ).fetchone()[0] == "sk-newsecret1234567890"
    conn.close()


def test_mcp_and_skills_list_include_openclaw(runner, tmp_path):
    db_path = tmp_path / "cc-switch.db"
    conn = _init_cli_db(db_path)
    conn.execute(
        """
        INSERT INTO mcp_servers (
            id, name, description, enabled_claude, enabled_codex, enabled_gemini,
            enabled_opencode, enabled_openclaw, enabled_hermes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("mcp-1", "OpenClaw MCP", "desc", 0, 0, 0, 0, 1, 0),
    )
    conn.execute(
        """
        INSERT INTO skills (
            id, name, description, repo_owner, repo_name, enabled_claude,
            enabled_codex, enabled_gemini, enabled_opencode, enabled_openclaw,
            enabled_hermes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("skill-1", "OpenClaw Skill", "desc", "owner", "repo", 0, 0, 0, 0, 1, 0),
    )
    conn.commit()
    conn.close()

    mcp_json = runner.invoke(cli, ["--json", "--db", str(db_path), "mcp", "list"])
    skills_json = runner.invoke(cli, ["--json", "--db", str(db_path), "skills", "list"])
    mcp_text = runner.invoke(cli, ["--db", str(db_path), "mcp", "list"])
    skills_text = runner.invoke(cli, ["--db", str(db_path), "skills", "list"])

    assert mcp_json.exit_code == 0
    assert skills_json.exit_code == 0
    assert mcp_text.exit_code == 0
    assert skills_text.exit_code == 0
    assert json.loads(mcp_json.output)[0]["enabled_openclaw"] == 1
    assert json.loads(skills_json.output)[0]["enabled_openclaw"] == 1
    assert "openclaw" in mcp_text.output
    assert "openclaw" in skills_text.output


def test_usage_stats_normalises_nullable_aggregates(runner, tmp_path):
    db_path = tmp_path / "cc-switch.db"
    conn = _init_cli_db(db_path)
    conn.execute(
        """
        INSERT INTO proxy_request_logs (
            app_type, model, status_code, input_tokens, output_tokens,
            total_cost_usd, latency_ms, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, CAST(strftime('%s', 'now') AS INTEGER))
        """,
        ("claude", "deepseek-v4-pro", 200, None, None, None, 100),
    )
    conn.commit()
    conn.close()

    text_result = runner.invoke(cli, ["--db", str(db_path), "usage", "stats", "--days", "30"])
    json_result = runner.invoke(cli, [
        "--json", "--db", str(db_path), "usage", "stats", "--days", "30",
    ])

    assert text_result.exit_code == 0
    assert "deepseek-v4-pro" in text_result.output
    assert "$0.0000" in text_result.output
    assert json_result.exit_code == 0
    data = json.loads(json_result.output)
    assert data[0]["input_tok"] == 0
    assert data[0]["output_tok"] == 0
    assert data[0]["cost"] == 0


def test_write_live_config_codex_writes_config_and_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    config_path = tmp_path / ".codex" / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        'approval_policy = "on-request"\n'
        'sandbox_mode = "workspace-write"\n'
        'model = "old-model"\n'
        'model_provider = "old-provider"\n'
        '\n'
        '[model_providers.old-provider]\n'
        'name = "Old Provider"\n'
        'base_url = "https://old.example.test"\n'
        '\n'
        '[model_providers.keep]\n'
        'name = "Keep Provider"\n'
        'base_url = "https://keep.example.test"\n'
        '\n'
        '# mcp should stay with filesystem\n'
        '[mcp_servers.filesystem]\n'
        'command = "npx"\n'
        'args = ["-y", "@modelcontextprotocol/server-filesystem"]\n'
        '\n'
        '[profiles.work]\n'
        'model = "profile-model"\n',
        encoding="utf-8",
    )
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE providers (
            app_type TEXT,
            is_current INTEGER,
            settings_config TEXT
        )
    """)
    db.execute(
        "INSERT INTO providers VALUES (?, ?, ?)",
        (
            "codex",
            1,
            json.dumps({
                "config": (
                    'model = "deepseek-v4-pro"\n'
                    'model_provider = "deepseek"\n'
                    '\n'
                    '[model_providers.deepseek]\n'
                    'name = "DeepSeek"\n'
                    'base_url = "https://api.deepseek.com/v1"\n'
                ),
                "auth": {"OPENAI_API_KEY": "sk-codex1234567890"},
            }),
        ),
    )

    _write_live_config("codex", db)

    merged = config_path.read_text(encoding="utf-8")
    assert 'model = "deepseek-v4-pro"' in merged
    assert 'model_provider = "deepseek"' in merged
    assert '[model_providers.deepseek]' in merged
    assert 'base_url = "https://api.deepseek.com/v1"' in merged
    assert '[model_providers.keep]' in merged
    assert 'approval_policy = "on-request"' in merged
    assert 'sandbox_mode = "workspace-write"' in merged
    assert '[mcp_servers.filesystem]' in merged
    assert '[profiles.work]' in merged
    parsed = tomlkit.parse(merged)
    assert parsed["mcp_servers"]["filesystem"]["command"] == "npx"
    assert parsed["profiles"]["work"]["model"] == "profile-model"
    auth = json.loads((tmp_path / ".codex" / "auth.json").read_text(encoding="utf-8"))
    assert auth == {"OPENAI_API_KEY": "sk-codex1234567890"}
    assert not list((tmp_path / ".codex").glob(".config.toml.*"))
    assert not list((tmp_path / ".codex").glob(".auth.json.*"))


def test_write_live_config_codex_handles_multiline_strings(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    config_path = tmp_path / ".codex" / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        'model = "old-model"\n'
        'model_provider = "deepseek"\n'
        '\n'
        '[model_providers.deepseek]\n'
        'name = "Old DeepSeek"\n'
        'notes = """\n'
        'line one\n'
        '[mcp_servers.fake]\n'
        'line three\n'
        '"""\n'
        'base_url = "https://old.example.test"\n'
        '\n'
        '[mcp_servers.real]\n'
        'command = "npx"\n',
        encoding="utf-8",
    )
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE providers (
            app_type TEXT,
            is_current INTEGER,
            settings_config TEXT
        )
    """)
    db.execute(
        "INSERT INTO providers VALUES (?, ?, ?)",
        (
            "codex",
            1,
            json.dumps({
                "config": (
                    'model = "deepseek-v4-pro"\n'
                    'model_provider = "deepseek"\n'
                    '\n'
                    '[model_providers.deepseek]\n'
                    'name = "DeepSeek"\n'
                    'base_url = "https://api.deepseek.com/v1"\n'
                ),
            }),
        ),
    )

    _write_live_config("codex", db)

    parsed = tomlkit.parse(config_path.read_text(encoding="utf-8"))
    assert parsed["model"] == "deepseek-v4-pro"
    assert parsed["model_provider"] == "deepseek"
    assert parsed["model_providers"]["deepseek"]["base_url"] == "https://api.deepseek.com/v1"
    assert parsed["mcp_servers"]["real"]["command"] == "npx"
    assert "fake" not in parsed["mcp_servers"]


def test_write_live_config_claude_merges_nested_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(json.dumps({"env": {"EXISTING": "1"}}), encoding="utf-8")
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE providers (
            app_type TEXT,
            is_current INTEGER,
            settings_config TEXT
        )
    """)
    db.execute(
        "INSERT INTO providers VALUES (?, ?, ?)",
        (
            "claude",
            1,
            json.dumps({"env": {"ANTHROPIC_AUTH_TOKEN": "sk-test1234567890"}}),
        ),
    )

    _write_live_config("claude", db)

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["env"]["EXISTING"] == "1"
    assert data["env"]["ANTHROPIC_AUTH_TOKEN"] == "sk-test1234567890"


def test_write_live_config_gemini_writes_env_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    env_path = tmp_path / ".gemini" / ".env"
    env_path.parent.mkdir(parents=True)
    env_path.write_text("EXISTING=1\n", encoding="utf-8")
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE providers (
            app_type TEXT,
            is_current INTEGER,
            settings_config TEXT
        )
    """)
    db.execute(
        "INSERT INTO providers VALUES (?, ?, ?)",
        (
            "gemini",
            1,
            json.dumps({
                "env": {
                    "GEMINI_API_KEY": "sk-gemini1234567890",
                    "GOOGLE_GEMINI_BASE_URL": "https://api.example.test",
                    "GEMINI_MODEL": "gemini-3.1-pro",
                    "MULTILINE": "one\nTWO=2",
                    "BAD-KEY": "ignored",
                },
            }),
        ),
    )

    _write_live_config("gemini", db)

    content = env_path.read_text(encoding="utf-8")
    assert "EXISTING=1" in content
    assert "GEMINI_API_KEY=sk-gemini1234567890" in content
    assert "GOOGLE_GEMINI_BASE_URL=https://api.example.test" in content
    assert "GEMINI_MODEL=gemini-3.1-pro" in content
    assert "MULTILINE=one\\nTWO=2" in content
    assert "\nTWO=2" not in content
    assert "BAD-KEY=ignored" not in content
    assert not (tmp_path / ".gemini" / "settings.json").exists()


def test_write_live_config_opencode_merges_provider_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    config_path = tmp_path / ".config" / "opencode" / "opencode.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps({
        "$schema": "https://opencode.ai/config.json",
        "provider": {"old": {"npm": "@ai-sdk/openai"}},
    }), encoding="utf-8")
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE providers (
            id TEXT,
            app_type TEXT,
            is_current INTEGER,
            settings_config TEXT
        )
    """)
    db.execute(
        "INSERT INTO providers VALUES (?, ?, ?, ?)",
        (
            "deepseek",
            "opencode",
            1,
            json.dumps({
                "settingsConfig": {
                    "npm": "@ai-sdk/openai-compatible",
                    "options": {
                        "baseURL": "https://api.deepseek.com/v1",
                        "apiKey": "sk-opencode1234567890",
                    },
                    "models": {
                        "deepseek-v4-pro": {"name": "DeepSeek V4 Pro"},
                    },
                },
            }),
        ),
    )

    _write_live_config("opencode", db)

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert "old" in data["provider"]
    assert data["provider"]["deepseek"]["options"]["apiKey"] == "sk-opencode1234567890"
    assert data["provider"]["deepseek"]["models"]["deepseek-v4-pro"]["name"] == "DeepSeek V4 Pro"


def test_providers_set_current_codex_writes_live_config(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    config_path = tmp_path / ".codex" / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        'approval_policy = "on-request"\n'
        '\n'
        '[mcp_servers.filesystem]\n'
        'command = "npx"\n'
        '\n'
        '[profiles.work]\n'
        'model = "profile-model"\n',
        encoding="utf-8",
    )
    db_path = tmp_path / "cc-switch.db"
    conn = _init_cli_db(db_path)
    conn.execute(
        "INSERT INTO providers VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "old",
            "codex",
            "Old",
            "default",
            1,
            0,
            json.dumps({"config": 'model = "old"'}),
        ),
    )
    conn.execute(
        "INSERT INTO providers VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "deepseek",
            "codex",
            "DeepSeek",
            "default",
            0,
            1,
            json.dumps({
                "config": (
                    'model = "deepseek-v4-pro"\n'
                    'model_provider = "deepseek"\n'
                    '\n'
                    '[model_providers.deepseek]\n'
                    'name = "DeepSeek"\n'
                    'base_url = "https://api.deepseek.com/v1"\n'
                ),
                "auth": {"OPENAI_API_KEY": "sk-codex1234567890"},
            }),
        ),
    )
    conn.commit()
    conn.close()

    result = runner.invoke(cli, [
        "--db", str(db_path), "providers", "set-current", "deepseek", "--app", "codex",
    ])

    assert result.exit_code == 0
    assert "sk-codex1234567890" not in result.output
    merged = config_path.read_text(encoding="utf-8")
    assert 'model = "deepseek-v4-pro"' in merged
    assert 'model_provider = "deepseek"' in merged
    assert '[model_providers.deepseek]' in merged
    assert 'approval_policy = "on-request"' in merged
    assert '[mcp_servers.filesystem]' in merged
    assert '[profiles.work]' in merged
    auth = json.loads((tmp_path / ".codex" / "auth.json").read_text(encoding="utf-8"))
    assert auth["OPENAI_API_KEY"] == "sk-codex1234567890"

    conn = sqlite3.connect(db_path)
    current = conn.execute(
        "SELECT id FROM providers WHERE app_type=? AND is_current=1", ("codex",)
    ).fetchone()[0]
    conn.close()
    assert current == "deepseek"


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
