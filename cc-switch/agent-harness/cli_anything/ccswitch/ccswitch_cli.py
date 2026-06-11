"""CC Switch CLI — command-line interface for CC Switch configuration manager.

Usage:
    ccswitch providers list [--app claude] [--json]
    ccswitch providers set-current <provider-id> --app claude
    ccswitch proxy status [--app claude] [--json]
    ccswitch proxy config get [--app claude]
    ccswitch mcp list [--json]
    ccswitch skills list [--json]
    ccswitch usage stats [--days 30] [--json]
    ccswitch settings get <key>
"""

import json as _json
import os as _os
import sys
import tempfile as _tempfile
from collections.abc import Mapping
from copy import deepcopy as _deepcopy
import click
import tomlkit

from .utils.db import connect_db, load_config, load_settings, VALID_APP_TYPES

_MANAGED_APPS = VALID_APP_TYPES

# ──────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────


def _resolve_app(app: str | None) -> str | None:
    if app is not None:
        app = app.lower()
        if app not in VALID_APP_TYPES:
            raise click.BadParameter(f"Invalid app: {app}. Valid: {', '.join(VALID_APP_TYPES)}")
    return app


def _mask_sensitive(key: str, value) -> str:
    """Mask sensitive values like API tokens and keys."""
    if isinstance(value, str) and _is_sensitive_key(key):
        if len(value) > 12:
            return value[:8] + "..." + value[-4:]
        return "***"
    if isinstance(value, Mapping | list | tuple):
        return _format_masked_value(_mask_value(value, key))
    return str(value)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    normalized = "".join(ch if ch.isalnum() else "_" for ch in lowered).strip("_")
    parts = {p for p in normalized.split("_") if p}
    if not normalized:
        return False
    if normalized in {"key", "apikey", "api_key"}:
        return True
    if normalized.endswith("_key") or normalized.startswith("key_"):
        return True
    sensitive_words = {
        "token", "secret", "password", "auth", "credential",
        "bearer", "cookie", "private",
    }
    if parts & sensitive_words:
        return True
    return any(word in normalized for word in (
        "apikey", "api_key", "authtoken", "accesskey", "secretkey",
        "secretaccesskey", "authorization",
    ))


def _mask_value(value, key: str = ""):
    """Return a JSON-safe copy with sensitive nested values masked."""
    if _is_sensitive_key(key):
        if isinstance(value, str):
            return _mask_sensitive(key, value)
        return "***"
    if isinstance(value, Mapping):
        return {k: _mask_value(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask_value(item, key) for item in value]
    if isinstance(value, tuple):
        return [_mask_value(item, key) for item in value]
    return value


def _format_masked_value(value) -> str:
    if isinstance(value, Mapping):
        return "{" + ", ".join(
            f"{k}: {_format_masked_value(v)}" for k, v in value.items()
        ) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_format_masked_value(item) for item in value) + "]"
    return str(value)


def _table(headers: list[str], rows: list[tuple]) -> str:
    """Format data as a simple aligned table."""
    if not rows:
        return "(empty)"
    all_rows = [headers] + [list(map(str, r)) for r in rows]
    col_widths = [max(len(r[i]) for r in all_rows) for i in range(len(headers))]
    lines = []
    header = "  ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    lines.append(header)
    lines.append("-" * len(header))
    for row in all_rows[1:]:
        lines.append("  ".join(v.ljust(col_widths[i]) for i, v in enumerate(row)))
    return "\n".join(lines)


def _enabled_apps_str(row: Mapping) -> str:
    apps = [app for app in _MANAGED_APPS if row[f"enabled_{app}"]]
    return ",".join(apps) if apps else "-"


def _normalise_usage_rows(rows) -> list[dict]:
    normalised = []
    for row in rows:
        data = dict(row)
        data["input_tok"] = data["input_tok"] or 0
        data["output_tok"] = data["output_tok"] or 0
        data["cost"] = data["cost"] or 0
        normalised.append(data)
    return normalised


def _enabled_app_columns(db, table: str) -> str:
    columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
    parts = []
    for app in _MANAGED_APPS:
        column = f"enabled_{app}"
        parts.append(column if column in columns else f"0 AS {column}")
    return ", ".join(parts)


_CODEX_PROVIDER_CONFIG_KEYS = ("model", "model_provider", "base_url")


def _merge_codex_provider_toml(target, provider_config: str) -> None:
    """Merge provider-owned Codex TOML fields without deleting user settings."""
    try:
        existing_text = target.read_text(encoding="utf-8") if target.exists() else ""
        existing_doc = (
            tomlkit.parse(existing_text) if existing_text.strip() else tomlkit.document()
        )
        provider_doc = (
            tomlkit.parse(provider_config) if provider_config.strip() else tomlkit.document()
        )
    except Exception as exc:
        raise click.ClickException(f"Invalid Codex config.toml: {exc}") from exc

    for key in _CODEX_PROVIDER_CONFIG_KEYS:
        if key in provider_doc:
            existing_doc[key] = _deepcopy(provider_doc[key])

    if "model_providers" in provider_doc:
        provider_table = provider_doc["model_providers"]
        if not hasattr(provider_table, "items"):
            existing_doc["model_providers"] = _deepcopy(provider_table)
        else:
            existing_table = existing_doc.get("model_providers")
            if not hasattr(existing_table, "items"):
                existing_doc["model_providers"] = tomlkit.table()
                existing_table = existing_doc["model_providers"]
            for provider_id, provider_settings in provider_table.items():
                existing_table[provider_id] = _deepcopy(provider_settings)

    _write_text_config(target, tomlkit.dumps(existing_doc))


# ──────────────────────────────────────────────
# Main CLI
# ──────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--json", "json_mode", is_flag=True, help="Output in JSON format")
@click.option("--db", "db_path", type=click.Path(), help="Override database path")
@click.pass_context
def cli(ctx: click.Context, json_mode: bool, db_path: str | None) -> None:
    """CC Switch CLI — Manage AI coding tool configurations from the terminal."""
    ctx.ensure_object(dict)
    ctx.obj["json_mode"] = json_mode
    ctx.obj["db_path"] = db_path
    if ctx.invoked_subcommand is None:
        # Show status overview
        _show_status(ctx)


@cli.command("status")
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show a quick database overview."""
    _show_status(ctx)


def _show_status(ctx: click.Context) -> None:
    """Show a quick status overview."""
    db = connect_db(ctx.obj.get("db_path"))
    try:
        # Count providers
        prov_count = db.execute("SELECT COUNT(*) FROM providers").fetchone()[0]
        # Current provider per app
        cur = db.execute(
            "SELECT app_type, name FROM providers WHERE is_current=1 ORDER BY app_type"
        ).fetchall()
        # Skill count
        skill_count = db.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
        # MCP count
        mcp_count = db.execute("SELECT COUNT(*) FROM mcp_servers").fetchone()[0]

        if ctx.obj.get("json_mode"):
            _json.dump({
                "providers": prov_count,
                "current": {r["app_type"]: r["name"] for r in cur},
                "skills": skill_count,
                "mcp_servers": mcp_count,
            }, sys.stdout, indent=2)
            return

        click.echo("CC Switch Status")
        click.echo("-" * 40)
        click.echo(f"  Providers: {prov_count}")
        click.echo(f"  Skills: {skill_count}")
        click.echo(f"  MCP Servers: {mcp_count}")
        click.echo()
        click.echo("  Current providers:")
        for r in cur:
            click.echo(f"    {r['app_type']:>10s}: {r['name']}")
    finally:
        db.close()


# ──────────────────────────────────────────────
# Providers
# ──────────────────────────────────────────────

@cli.group()
def providers() -> None:
    """Manage AI provider configurations."""
    pass


@providers.command("list")
@click.option("--app", "-a", help="Filter by app type")
@click.pass_context
def providers_list(ctx: click.Context, app: str | None) -> None:
    """List all configured providers."""
    app = _resolve_app(app)
    db = connect_db(ctx.obj.get("db_path"))
    try:
        if app:
            rows = db.execute(
                "SELECT id, name, category, is_current, sort_index FROM providers "
                "WHERE app_type=? ORDER BY sort_index",
                (app,),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT app_type, id, name, category, is_current, sort_index "
                "FROM providers ORDER BY app_type, sort_index"
            ).fetchall()

        if ctx.obj.get("json_mode"):
            _json.dump([dict(r) for r in rows], sys.stdout, indent=2, default=str)
            return

        if app:
            click.echo(_table(["ID", "Name", "Category", "Current", "Sort"], [
                (r["id"], r["name"], r["category"] or "", "*" if r["is_current"] else "", r["sort_index"])
                for r in rows
            ]))
        else:
            click.echo(_table(["App", "ID", "Name", "Category", "Current", "Sort"], [
                (r["app_type"], r["id"], r["name"], r["category"] or "", "*" if r["is_current"] else "", r["sort_index"])
                for r in rows
            ]))
    finally:
        db.close()


@providers.command("get")
@click.argument("provider_id")
@click.option("--app", "-a", required=True, help="App type (claude/codex/gemini/...)")
@click.pass_context
def providers_get(ctx: click.Context, provider_id: str, app: str) -> None:
    """Get detailed configuration for a provider."""
    app = _resolve_app(app)
    db = connect_db(ctx.obj.get("db_path"))
    try:
        row = db.execute(
            "SELECT * FROM providers WHERE id=? AND app_type=?", (provider_id, app)
        ).fetchone()
        if not row:
            click.echo(f"Provider '{provider_id}' not found for app '{app}'", err=True)
            raise SystemExit(1)

        data = dict(row)
        # Parse settings_config JSON
        data["settings_config"] = _json.loads(data["settings_config"])

        if ctx.obj.get("json_mode"):
            data["settings_config"] = _mask_value(data["settings_config"])
            _json.dump(data, sys.stdout, indent=2, default=str)
            return

        click.echo(f"Provider: {data['name']}")
        click.echo(f"  ID: {data['id']}")
        click.echo(f"  App: {data['app_type']}")
        click.echo(f"  Category: {data.get('category', 'N/A')}")
        click.echo(f"  Current: {bool(data['is_current'])}")
        click.echo(f"  Settings:")
        for k, v in sorted(data["settings_config"].items()):
            click.echo(f"    {k}: {_format_masked_value(_mask_value(v, k))}")
    finally:
        db.close()


@providers.command("set-current")
@click.argument("provider_id")
@click.option("--app", "-a", required=True, help="App type")
@click.pass_context
def providers_set_current(ctx: click.Context, provider_id: str, app: str) -> None:
    """Set the current/active provider for an app."""
    app = _resolve_app(app)
    db = connect_db(ctx.obj.get("db_path"))
    try:
        # Verify provider exists
        row = db.execute(
            "SELECT id, name FROM providers WHERE id=? AND app_type=?", (provider_id, app)
        ).fetchone()
        if not row:
            click.echo(f"Provider '{provider_id}' not found for '{app}'", err=True)
            raise SystemExit(1)

        # Unset all, then set current
        db.execute("UPDATE providers SET is_current=0 WHERE app_type=?", (app,))
        db.execute(
            "UPDATE providers SET is_current=1 WHERE id=? AND app_type=?", (provider_id, app)
        )

        _write_live_config(app, db)
        db.commit()
        click.echo(f"Switched {app} to provider: {row['name']}")
    finally:
        db.close()


def _write_live_config(app: str, db) -> None:
    """Write the current provider config to the live app config file."""
    from pathlib import Path

    home = Path(_os.path.expanduser("~"))
    row = db.execute(
        "SELECT * FROM providers WHERE app_type=? AND is_current=1", (app,)
    ).fetchone()
    if not row:
        return

    config = _json.loads(row["settings_config"])

    target_map = {
        "claude": home / ".claude" / "settings.json",
        "codex": home / ".codex" / "config.toml",
        "gemini": home / ".gemini" / ".env",
        "opencode": home / ".config" / "opencode" / "opencode.json",
        "openclaw": home / ".openclaw" / "openclaw.json",
        "hermes": home / ".hermes" / "config.yaml",
    }

    target = target_map.get(app)
    if not target:
        return

    if app == "claude":
        _write_json_env_config(target, _env_config(config))
        click.echo(f"  Written live config to: {target}")
    elif app == "codex":
        wrote = False
        if "config" in config:
            _merge_codex_provider_toml(target, str(config["config"]))
            wrote = True
        if isinstance(config.get("auth"), dict):
            _write_json_config(home / ".codex" / "auth.json", config["auth"])
            wrote = True
        if wrote:
            click.echo(f"  Written live config to: {target}")
        else:
            click.echo(f"  (Note: no supported {app} live config payload found)")
    elif app == "gemini":
        written_targets = []
        env = _gemini_env_config(config)
        if env:
            _write_env_config(target, env)
            written_targets.append(target)
        if "config" in config:
            settings_target = home / ".gemini" / "settings.json"
            if isinstance(config["config"], dict):
                _write_json_config(settings_target, config["config"])
            else:
                _write_text_config(settings_target, str(config["config"]))
            written_targets.append(settings_target)
        if written_targets:
            click.echo(
                "  Written live config to: "
                + ", ".join(str(path) for path in written_targets)
            )
        else:
            click.echo(f"  (Note: no supported {app} live config payload found)")
    elif app == "opencode":
        if "config" in config:
            _write_text_config(target, str(config["config"]))
        elif "settingsConfig" in config:
            _write_opencode_provider_config(target, str(row["id"]), config["settingsConfig"])
        else:
            click.echo(f"  (Note: no supported {app} live config payload found)")
            return
        click.echo(f"  Written live config to: {target}")
    elif app == "openclaw":
        _write_json_config(target, config)
        click.echo(f"  Written live config to: {target}")
    elif app == "hermes":
        if "config" in config:
            _write_text_config(target, str(config["config"]))
        else:
            click.echo(f"  (Note: no supported {app} live config payload found)")
            return
        click.echo(f"  Written live config to: {target}")


def _env_config(config: dict) -> dict:
    env = config.get("env")
    if isinstance(env, dict):
        return env
    return config


def _gemini_env_config(config: dict) -> dict:
    env = config.get("env")
    if isinstance(env, dict):
        return env
    if "config" in config or "auth" in config or "settingsConfig" in config:
        return {}
    return config


def _write_json_env_config(target, env: dict) -> None:
    existing = {}
    if target.exists():
        with open(target, encoding="utf-8") as f:
            existing = _json.load(f)
    if not isinstance(existing, dict):
        existing = {}
    existing_env = existing.get("env")
    if not isinstance(existing_env, dict):
        existing_env = {}
    existing_env.update(env)
    existing["env"] = existing_env
    _write_json_config(target, existing)


def _write_env_config(target, env: dict) -> None:
    existing = {}
    if target.exists():
        existing = _parse_env_file(target.read_text(encoding="utf-8"))
    existing.update(_coerce_env_config(env))
    lines = [f"{key}={existing[key]}" for key in sorted(existing)]
    _write_text_config(target, "\n".join(lines))


def _parse_env_file(content: str) -> dict[str, str]:
    parsed = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if _is_valid_env_key(key):
            parsed[key] = value
    return parsed


def _coerce_env_config(env: dict) -> dict[str, str]:
    result = {}
    for key, value in env.items():
        key = str(key)
        if not _is_valid_env_key(key):
            continue
        result[key] = _env_value(value)
    return result


def _is_valid_env_key(key: str) -> bool:
    return bool(key) and all(
        ch == "_" or "A" <= ch <= "Z" or "a" <= ch <= "z" or "0" <= ch <= "9"
        for ch in key
    )


def _env_value(value) -> str:
    text = "" if value is None else str(value)
    return text.replace("\r", "\\r").replace("\n", "\\n")


def _write_json_config(target, config: dict) -> None:
    _write_text_config(target, _json.dumps(config, indent=2, ensure_ascii=False) + "\n")


def _write_opencode_provider_config(target, provider_id: str, provider_config: dict) -> None:
    existing = {
        "$schema": "https://opencode.ai/config.json",
    }
    if target.exists():
        with open(target, encoding="utf-8") as f:
            existing = _json.load(f)
    if not isinstance(existing, dict):
        existing = {}
    providers = existing.get("provider")
    if not isinstance(providers, dict):
        providers = {}
    providers[provider_id] = provider_config
    existing["provider"] = providers
    _write_json_config(target, existing)


def _write_text_config(target, content: str) -> None:
    if content and not content.endswith("\n"):
        content += "\n"
    _write_secure_file(target, content)


def _write_secure_file(target, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = _tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with _os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        try:
            _os.chmod(tmp_name, 0o600)
        except OSError:
            pass
        _os.replace(tmp_name, target)
    except Exception:
        try:
            _os.unlink(tmp_name)
        except OSError:
            pass
        raise


# ──────────────────────────────────────────────
# Proxy
# ──────────────────────────────────────────────

@cli.group()
def proxy() -> None:
    """Manage the local HTTP proxy server."""
    pass


@proxy.command("status")
@click.option("--app", "-a", default="claude", help="App type")
@click.pass_context
def proxy_status(ctx: click.Context, app: str) -> None:
    """Show proxy server status."""
    app = _resolve_app(app)
    db = connect_db(ctx.obj.get("db_path"))
    try:
        row = db.execute(
            "SELECT * FROM proxy_config WHERE app_type=?", (app,)
        ).fetchone()
        if not row:
            click.echo(f"No proxy config for {app}")
            return

        data = dict(row)
        if ctx.obj.get("json_mode"):
            _json.dump(data, sys.stdout, indent=2, default=str)
            return

        click.echo(f"Proxy Status ({app}):")
        click.echo(f"  Enabled: {bool(data['enabled'])}")
        click.echo(f"  Listen: {data['listen_address']}:{data['listen_port']}")
        click.echo(f"  Proxy Enabled: {bool(data['proxy_enabled'])}")
        click.echo(f"  Auto Failover: {bool(data['auto_failover_enabled'])}")
        click.echo(f"  Max Retries: {data['max_retries']}")
        click.echo(f"  Circuit Breaker: {bool(data.get('live_takeover_active', 0))}")
    finally:
        db.close()


@proxy.command("config")
@click.option("--app", "-a", default="claude", help="App type")
@click.option("--set-port", type=int, help="Set listen port")
@click.option("--enable/--disable", default=None, help="Enable/disable proxy")
@click.option("--failover/--no-failover", default=None, help="Enable/disable auto failover")
@click.pass_context
def proxy_config(
    ctx: click.Context, app: str, set_port: int | None,
    enable: bool | None, failover: bool | None
) -> None:
    """Get or set proxy configuration."""
    app = _resolve_app(app)
    db = connect_db(ctx.obj.get("db_path"))
    try:
        if set_port is not None:
            db.execute("UPDATE proxy_config SET listen_port=? WHERE app_type=?", (set_port, app))
        if enable is True:
            db.execute("UPDATE proxy_config SET proxy_enabled=1 WHERE app_type=?", (app,))
        elif enable is False:
            db.execute("UPDATE proxy_config SET proxy_enabled=0 WHERE app_type=?", (app,))
        if failover is True:
            db.execute("UPDATE proxy_config SET auto_failover_enabled=1 WHERE app_type=?", (app,))
        elif failover is False:
            db.execute("UPDATE proxy_config SET auto_failover_enabled=0 WHERE app_type=?", (app,))
        db.commit()

        # Show updated config
        row = db.execute(
            "SELECT * FROM proxy_config WHERE app_type=?", (app,)
        ).fetchone()
        if row:
            data = dict(row)
            click.echo(_json.dumps({
                "app": app,
                "listen": f"{data['listen_address']}:{data['listen_port']}",
                "enabled": bool(data["enabled"]),
                "proxy_enabled": bool(data["proxy_enabled"]),
                "auto_failover": bool(data["auto_failover_enabled"]),
                "max_retries": data["max_retries"],
            }, indent=2))
    finally:
        db.close()


# ──────────────────────────────────────────────
# MCP
# ──────────────────────────────────────────────

@cli.group()
def mcp() -> None:
    """Manage MCP (Model Context Protocol) servers."""
    pass


@mcp.command("list")
@click.pass_context
def mcp_list(ctx: click.Context) -> None:
    """List all MCP servers."""
    db = connect_db(ctx.obj.get("db_path"))
    try:
        enabled_columns = _enabled_app_columns(db, "mcp_servers")
        rows = db.execute(
            f"SELECT id, name, description, {enabled_columns} "
            "FROM mcp_servers ORDER BY name"
        ).fetchall()

        if ctx.obj.get("json_mode"):
            _json.dump([dict(r) for r in rows], sys.stdout, indent=2, default=str)
            return

        click.echo(_table(["ID", "Name", "Apps", "Description"], [
            (r["id"][:30], r["name"], _enabled_apps_str(r), (r["description"] or "")[:50])
            for r in rows
        ]))
    finally:
        db.close()


@mcp.command("enable")
@click.argument("server_id")
@click.option("--app", "-a", required=True, help="App type")
@click.option("--on/--off", default=True, help="Enable or disable")
@click.pass_context
def mcp_enable(ctx: click.Context, server_id: str, app: str, on: bool) -> None:
    """Enable or disable an MCP server for an app."""
    app = _resolve_app(app)
    db = connect_db(ctx.obj.get("db_path"))
    try:
        col = f"enabled_{app}"
        db.execute(f"UPDATE mcp_servers SET {col}=? WHERE id=?", (int(on), server_id))
        if db.total_changes == 0:
            click.echo(f"MCP server '{server_id}' not found", err=True)
            raise SystemExit(1)
        db.commit()
        click.echo(f"MCP '{server_id}' {'enabled' if on else 'disabled'} for {app}")
    finally:
        db.close()


# ──────────────────────────────────────────────
# Skills
# ──────────────────────────────────────────────

@cli.group()
def skills() -> None:
    """Manage installed skills."""
    pass


@skills.command("list")
@click.pass_context
def skills_list(ctx: click.Context) -> None:
    """List all installed skills."""
    db = connect_db(ctx.obj.get("db_path"))
    try:
        enabled_columns = _enabled_app_columns(db, "skills")
        rows = db.execute(
            "SELECT id, name, description, repo_owner, repo_name, "
            f"{enabled_columns} "
            "FROM skills ORDER BY name"
        ).fetchall()

        if ctx.obj.get("json_mode"):
            _json.dump([dict(r) for r in rows], sys.stdout, indent=2, default=str)
            return

        click.echo(_table(["Name", "Source", "Apps", "Description"], [
            (r["name"], f"{r['repo_owner']}/{r['repo_name']}" if r["repo_owner"] else "local",
             _enabled_apps_str(r), (r["description"] or "")[:50])
            for r in rows
        ]))
    finally:
        db.close()


@skills.command("repos")
@click.pass_context
def skills_repos(ctx: click.Context) -> None:
    """List registered skill repositories."""
    db = connect_db(ctx.obj.get("db_path"))
    try:
        rows = db.execute(
            "SELECT owner, name, branch, enabled FROM skill_repos ORDER BY owner, name"
        ).fetchall()

        if ctx.obj.get("json_mode"):
            _json.dump([dict(r) for r in rows], sys.stdout, indent=2, default=str)
            return

        click.echo(_table(["Owner", "Name", "Branch", "Enabled"], [
            (r["owner"], r["name"], r["branch"], "yes" if r["enabled"] else "no")
            for r in rows
        ]))
    finally:
        db.close()


# ──────────────────────────────────────────────
# Usage
# ──────────────────────────────────────────────

@cli.group()
def usage() -> None:
    """View API usage and cost statistics."""
    pass


@usage.command("stats")
@click.option("--days", "-d", default=30, type=int, help="Number of days to show")
@click.option("--app", "-a", help="Filter by app type")
@click.pass_context
def usage_stats(ctx: click.Context, days: int, app: str | None) -> None:
    """Show usage statistics."""
    app = _resolve_app(app)
    db = connect_db(ctx.obj.get("db_path"))
    try:
        if app:
            rows = db.execute(
                "SELECT model, COUNT(*) as requests, SUM(input_tokens) as input_tok, "
                "SUM(output_tokens) as output_tok, "
                "SUM(CAST(total_cost_usd AS REAL)) as cost "
                "FROM proxy_request_logs "
                "WHERE app_type=? AND created_at > unixepoch('now', ? || ' days') "
                "GROUP BY model ORDER BY cost DESC",
                (app, f"-{days}"),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT app_type, model, COUNT(*) as requests, SUM(input_tokens) as input_tok, "
                "SUM(output_tokens) as output_tok, "
                "SUM(CAST(total_cost_usd AS REAL)) as cost "
                "FROM proxy_request_logs "
                "WHERE created_at > unixepoch('now', ? || ' days') "
                "GROUP BY app_type, model ORDER BY cost DESC",
                (f"-{days}",),
            ).fetchall()

        rows = _normalise_usage_rows(rows)

        if ctx.obj.get("json_mode"):
            _json.dump(rows, sys.stdout, indent=2, default=str)
            return

        total_cost = sum(r["cost"] for r in rows)
        total_requests = sum(r["requests"] for r in rows)
        total_in = sum(r["input_tok"] for r in rows)
        total_out = sum(r["output_tok"] for r in rows)

        if app:
            click.echo(_table(["Model", "Requests", "Input Tokens", "Output Tokens", "Cost (USD)"], [
                (r["model"], r["requests"], f'{r["input_tok"]:,}', f'{r["output_tok"]:,}', f'${r["cost"]:.4f}')
                for r in rows
            ]))
        else:
            click.echo(_table(["App", "Model", "Requests", "Input Tokens", "Output Tokens", "Cost (USD)"], [
                (r["app_type"], r["model"], r["requests"],
                 f'{r["input_tok"]:,}', f'{r["output_tok"]:,}', f'${r["cost"]:.4f}')
                for r in rows
            ]))

        click.echo()
        click.echo(f"  Total ({days} days): {total_requests:,} requests | "
                    f"{total_in + total_out:,} tokens | ${total_cost:.4f}")
    finally:
        db.close()


@usage.command("logs")
@click.option("--limit", "-n", default=20, type=int, help="Number of recent logs to show")
@click.option("--app", "-a", help="Filter by app type")
@click.pass_context
def usage_logs(ctx: click.Context, limit: int, app: str | None) -> None:
    """Show recent API request logs."""
    app = _resolve_app(app)
    db = connect_db(ctx.obj.get("db_path"))
    try:
        if app:
            rows = db.execute(
                "SELECT app_type, model, status_code, input_tokens, output_tokens, "
                "total_cost_usd, latency_ms, datetime(created_at, 'unixepoch') as ts "
                "FROM proxy_request_logs WHERE app_type=? "
                "ORDER BY created_at DESC LIMIT ?",
                (app, limit),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT app_type, model, status_code, input_tokens, output_tokens, "
                "total_cost_usd, latency_ms, datetime(created_at, 'unixepoch') as ts "
                "FROM proxy_request_logs "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

        if ctx.obj.get("json_mode"):
            _json.dump([dict(r) for r in rows], sys.stdout, indent=2, default=str)
            return

        click.echo(_table(["App", "Model", "Status", "Tokens (in/out)", "Cost", "Latency", "Time"], [
            (r["app_type"], r["model"][:25], r["status_code"],
             f'{r["input_tokens"]}/{r["output_tokens"]}',
             f'${float(r["total_cost_usd"] or 0):.4f}',
             f'{r["latency_ms"]}ms', r["ts"])
            for r in rows
        ]))
    finally:
        db.close()


# ──────────────────────────────────────────────
# Settings
# ──────────────────────────────────────────────

@cli.group()
def settings() -> None:
    """View and manage CC Switch settings."""
    pass


@settings.command("list")
@click.pass_context
def settings_list(ctx: click.Context) -> None:
    """List all settings key-value pairs."""
    db = connect_db(ctx.obj.get("db_path"))
    try:
        rows = db.execute("SELECT key, value FROM settings ORDER BY key").fetchall()
        if ctx.obj.get("json_mode"):
            _json.dump({
                r["key"]: _mask_value(r["value"], r["key"]) for r in rows
            }, sys.stdout, indent=2)
            return
        click.echo(_table(["Key", "Value"], [
            (r["key"], _mask_sensitive(r["key"], r["value"])[:80]) for r in rows
        ]))
    finally:
        db.close()


@settings.command("get")
@click.argument("key")
@click.pass_context
def settings_get(ctx: click.Context, key: str) -> None:
    """Get a specific setting value."""
    db = connect_db(ctx.obj.get("db_path"))
    try:
        row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if not row:
            click.echo(f"Setting '{key}' not found", err=True)
            raise SystemExit(1)
        if ctx.obj.get("json_mode"):
            _json.dump({key: _mask_value(row["value"], key)}, sys.stdout, indent=2)
            return
        click.echo(_mask_sensitive(key, row["value"]))
    finally:
        db.close()


@settings.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def settings_set(ctx: click.Context, key: str, value: str) -> None:
    """Set a setting value."""
    db = connect_db(ctx.obj.get("db_path"))
    try:
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
        db.commit()
        click.echo(f"Set '{key}' = '{_mask_sensitive(key, value)}'")
    finally:
        db.close()


# ──────────────────────────────────────────────
# Sessions
# ──────────────────────────────────────────────

@cli.group()
def sessions() -> None:
    """Browse and search AI conversation sessions."""
    pass


@sessions.command("list")
@click.option("--app", "-a", help="Filter by app type")
@click.option("--limit", "-n", default=20, type=int)
@click.pass_context
def sessions_list(ctx: click.Context, app: str | None, limit: int) -> None:
    """List recent conversation sessions."""
    app = _resolve_app(app)
    db = connect_db(ctx.obj.get("db_path"))
    try:
        if app:
            rows = db.execute(
                "SELECT file_path, last_modified, last_synced_at "
                "FROM session_log_sync WHERE file_path LIKE ? "
                "ORDER BY last_modified DESC LIMIT ?",
                (f"%{app}%", limit),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT file_path, last_modified, last_synced_at "
                "FROM session_log_sync ORDER BY last_modified DESC LIMIT ?",
                (limit,),
            ).fetchall()

        if ctx.obj.get("json_mode"):
            _json.dump([dict(r) for r in rows], sys.stdout, indent=2, default=str)
            return

        if not rows:
            click.echo("No session logs found. Enable usage tracking in CC Switch first.")
            return

        click.echo(_table(["Path", "Last Modified", "Last Synced"], [
            (r["file_path"][:60],
             r["last_modified"],
             r["last_synced_at"])
            for r in rows
        ]))
    finally:
        db.close()


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

def main() -> None:
    """Main entry point for CC Switch CLI."""
    cli(prog_name="ccswitch")


if __name__ == "__main__":
    main()
