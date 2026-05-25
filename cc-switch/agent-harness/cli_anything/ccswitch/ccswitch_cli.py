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
import sys
import click

from .utils.db import connect_db, load_config, load_settings, VALID_APP_TYPES

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
    sensitive = ("token", "key", "secret", "password", "auth")
    if isinstance(value, str) and any(s in key.lower() for s in sensitive):
        if len(value) > 12:
            return value[:8] + "..." + value[-4:]
        return value[:4] + "***"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{k}: {_mask_sensitive(k, v)}" for k, v in value.items()) + "}"
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
            _json.dump(data, sys.stdout, indent=2, default=str)
            return

        click.echo(f"Provider: {data['name']}")
        click.echo(f"  ID: {data['id']}")
        click.echo(f"  App: {data['app_type']}")
        click.echo(f"  Category: {data.get('category', 'N/A')}")
        click.echo(f"  Current: {bool(data['is_current'])}")
        click.echo(f"  Settings:")
        for k, v in sorted(data["settings_config"].items()):
            click.echo(f"    {k}: {_mask_sensitive(k, v)}")
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
        db.commit()
        click.echo(f"Switched {app} to provider: {row['name']}")

        # Offer to write live config
        _write_live_config(app, db)
    finally:
        db.close()


def _write_live_config(app: str, db) -> None:
    """Write the current provider config to the live app config file."""
    import os as _os
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
        "gemini": home / ".gemini" / "settings.json",
        "opencode": home / ".opencode" / "config.toml",
        "openclaw": home / ".openclaw" / "openclaw.json",
        "hermes": home / ".hermes" / "config.yaml",
    }

    target = target_map.get(app)
    if not target or not target.parent.exists():
        click.echo(f"  (Note: {app} config directory not found, skipping live write)")
        return

    if app in ("claude",):
        # Claude Code uses env vars in settings.json
        existing = {}
        if target.exists():
            with open(target) as f:
                existing = _json.load(f)
        existing["env"] = existing.get("env", {})
        if "ANTHROPIC_AUTH_TOKEN" in config:
            existing["env"]["ANTHROPIC_AUTH_TOKEN"] = config["ANTHROPIC_AUTH_TOKEN"]
        if "ANTHROPIC_BASE_URL" in config:
            existing["env"]["ANTHROPIC_BASE_URL"] = config["ANTHROPIC_BASE_URL"]
        if "ANTHROPIC_MODEL" in config:
            existing["env"]["ANTHROPIC_MODEL"] = config["ANTHROPIC_MODEL"]
        with open(target, "w") as f:
            _json.dump(existing, f, indent=2)
        click.echo(f"  Written live config to: {target}")


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
        rows = db.execute(
            "SELECT id, name, description, enabled_claude, enabled_codex, "
            "enabled_gemini, enabled_opencode, enabled_hermes FROM mcp_servers ORDER BY name"
        ).fetchall()

        if ctx.obj.get("json_mode"):
            _json.dump([dict(r) for r in rows], sys.stdout, indent=2, default=str)
            return

        def apps_str(r: dict) -> str:
            apps = []
            for a in ("claude", "codex", "gemini", "opencode", "hermes"):
                if r[f"enabled_{a}"]:
                    apps.append(a[:2])
            return ",".join(apps) if apps else "-"

        click.echo(_table(["ID", "Name", "Apps", "Description"], [
            (r["id"][:30], r["name"], apps_str(r), (r["description"] or "")[:50])
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
        rows = db.execute(
            "SELECT id, name, description, repo_owner, repo_name, "
            "enabled_claude, enabled_codex, enabled_gemini, enabled_opencode, enabled_hermes "
            "FROM skills ORDER BY name"
        ).fetchall()

        if ctx.obj.get("json_mode"):
            _json.dump([dict(r) for r in rows], sys.stdout, indent=2, default=str)
            return

        def apps_str(r: dict) -> str:
            apps = []
            for a in ("claude", "codex", "gemini", "opencode", "hermes"):
                if r[f"enabled_{a}"]:
                    apps.append(a[:2])
            return ",".join(apps) if apps else "-"

        click.echo(_table(["Name", "Source", "Apps", "Description"], [
            (r["name"], f"{r['repo_owner']}/{r['repo_name']}" if r["repo_owner"] else "local",
             apps_str(r), (r["description"] or "")[:50])
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

        if ctx.obj.get("json_mode"):
            _json.dump([dict(r) for r in rows], sys.stdout, indent=2, default=str)
            return

        total_cost = sum(r["cost"] or 0 for r in rows)
        total_requests = sum(r["requests"] for r in rows)
        total_in = sum(r["input_tok"] or 0 for r in rows)
        total_out = sum(r["output_tok"] or 0 for r in rows)

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
            _json.dump({r["key"]: r["value"] for r in rows}, sys.stdout, indent=2)
            return
        click.echo(_table(["Key", "Value"], [
            (r["key"], r["value"][:80]) for r in rows
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
        click.echo(row["value"])
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
        click.echo(f"Set '{key}' = '{value}'")
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

        if not rows:
            click.echo("No session logs found. Enable usage tracking in CC Switch first.")
            return

        if ctx.obj.get("json_mode"):
            _json.dump([dict(r) for r in rows], sys.stdout, indent=2, default=str)
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
