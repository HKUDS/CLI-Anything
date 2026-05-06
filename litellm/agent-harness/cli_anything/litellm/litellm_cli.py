#!/usr/bin/env python3
"""LiteLLM CLI for agentic app and workflow editing."""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path
from typing import Any

import click

from cli_anything.litellm import __version__
from cli_anything.litellm.core.execution import execute_flow, execute_task
from cli_anything.litellm.core.patches import export_patch, rollback_patch
from cli_anything.litellm.core.session import SessionStore, workspace_session_file
from cli_anything.litellm.core.taskdefs import load_flow, load_task, validate_definition
from cli_anything.litellm.utils.litellm_backend import (
    bootstrap_workspace,
    health as backend_health,
    list_models,
    load_config,
    load_workspace_config,
    resolve_api_key,
    resolve_host,
    resolve_model,
    save_config,
)
from cli_anything.litellm.utils.repl_skin import error, info, print_banner, success

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


def _session(workspace: str | None = None) -> SessionStore:
    if workspace:
        return SessionStore(workspace_session_file(workspace))
    return SessionStore()


def _output(data: Any, as_json: bool, message: str = "") -> None:
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    click.echo(f"{key}: {json.dumps(value, indent=2, default=str)}")
                else:
                    click.echo(f"{key}: {value}")
        elif isinstance(data, list):
            for item in data:
                click.echo(json.dumps(item, indent=2, default=str) if isinstance(item, dict) else str(item))
        else:
            click.echo(str(data))


def _handle_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (RuntimeError, ValueError) as exc:
            ctx = click.get_current_context(silent=True)
            as_json = bool(ctx and ctx.obj and ctx.obj.get("as_json"))
            if as_json:
                click.echo(json.dumps({"error": str(exc), "type": type(exc).__name__}))
            else:
                error(str(exc))
            raise SystemExit(1)
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON output")
@click.option("--host", default=None, help="LiteLLM proxy base URL")
@click.option("--api-key", default=None, help="LiteLLM proxy API key")
@click.option("--model", default=None, help="Default LiteLLM model alias")
@click.option("--workspace", default=".", help="Workspace root for task/flow execution")
@click.option("--max-iterations", default=None, type=int, help="Override max loop iterations")
@click.option("--timeout", default=60, type=int, help="Reserved for future network timeouts")
@click.version_option(version=__version__, prog_name="cli")
@click.pass_context
def cli(
    ctx: click.Context,
    as_json: bool,
    host: str | None,
    api_key: str | None,
    model: str | None,
    workspace: str,
    max_iterations: int | None,
    timeout: int,
) -> None:
    """LiteLLM CLI for agent execution tasks and flows."""
    resolved_workspace = str(Path(workspace).resolve())
    ctx.ensure_object(dict)
    ctx.obj.update(
        {
            "as_json": as_json,
            "host": resolve_host(host, workspace=resolved_workspace),
            "api_key": resolve_api_key(api_key, workspace=resolved_workspace),
            "model": resolve_model(model, workspace=resolved_workspace),
            "workspace": resolved_workspace,
            "max_iterations": max_iterations,
            "timeout": timeout,
        }
    )
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.command("repl", hidden=True)
@click.pass_context
def repl(ctx: click.Context) -> None:
    """Start a basic interactive REPL."""
    print_banner(ctx.obj["host"], ctx.obj.get("model"))
    while True:
        try:
            line = input("litellm> ").strip()
        except (EOFError, KeyboardInterrupt):
            click.echo()
            break
        if not line:
            continue
        if line in {"exit", "quit"}:
            break
        try:
            cli.main(args=shlex.split(line), standalone_mode=False, obj=ctx.obj)
        except SystemExit:
            pass


@cli.group()
def models() -> None:
    """Model discovery commands."""


@models.command("list")
@click.pass_context
@_handle_error
def models_list(ctx: click.Context) -> None:
    """List models exposed by the LiteLLM proxy."""
    result = list_models(ctx.obj["host"], api_key=ctx.obj["api_key"])
    _output(result, ctx.obj["as_json"], "Available LiteLLM models")


@cli.command("health")
@click.pass_context
@_handle_error
def health_cmd(ctx: click.Context) -> None:
    """Check LiteLLM proxy health."""
    result = backend_health(ctx.obj["host"], api_key=ctx.obj["api_key"])
    _output(result, ctx.obj["as_json"], "LiteLLM health")


@cli.group()
def config() -> None:
    """Local CLI config commands."""


@config.command("show")
@click.pass_context
def config_show(ctx: click.Context) -> None:
    """Show saved config with secrets masked."""
    cfg = load_config()
    workspace_cfg = load_workspace_config(ctx.obj["workspace"])
    if cfg.get("api_key"):
        cfg["api_key"] = "****configured****"
    if workspace_cfg.get("api_key"):
        workspace_cfg["api_key"] = "****configured****"
    cfg["effective_host"] = ctx.obj["host"]
    cfg["effective_model"] = ctx.obj["model"]
    cfg["workspace_config"] = workspace_cfg
    _output(cfg, ctx.obj["as_json"], "Config")


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
@_handle_error
def config_set(ctx: click.Context, key: str, value: str) -> None:
    """Set local CLI config values."""
    if key not in {"host", "api_key", "model"}:
        raise RuntimeError("Valid config keys: host, api_key, model")
    cfg = load_config()
    cfg[key] = value
    path = save_config(cfg)
    _output({"saved": key, "path": str(path)}, ctx.obj["as_json"], f"Saved {key}")


@config.command("bootstrap")
@click.option("--host", "host_opt", default=None, help="Repo-local default LiteLLM proxy URL")
@click.option("--model", "model_opt", default=None, help="Repo-local default model alias")
@click.pass_context
@_handle_error
def config_bootstrap(ctx: click.Context, host_opt: str | None, model_opt: str | None) -> None:
    """Create repo-local .litellm config and safe ignore files."""
    host_value = host_opt or ctx.obj["host"]
    model_value = model_opt or ctx.obj["model"]
    result = bootstrap_workspace(ctx.obj["workspace"], host=host_value, model=model_value)
    _output(result, ctx.obj["as_json"], "Workspace bootstrap complete")


@cli.group()
def task() -> None:
    """Task commands."""


@task.command("run")
@click.argument("task_file")
@click.pass_context
@_handle_error
def task_run(ctx: click.Context, task_file: str) -> None:
    """Run a repo-local YAML task."""
    model = ctx.obj.get("model")
    if not model:
        raise RuntimeError("No model configured. Use --model or `config set model <alias>`.")
    task_def = load_task(task_file)
    result = execute_task(
        task_def,
        workspace=ctx.obj["workspace"],
        host=ctx.obj["host"],
        api_key=ctx.obj["api_key"],
        model=model,
        max_iterations=ctx.obj["max_iterations"],
    )
    sess = _session(ctx.obj["workspace"])
    sess.record("task run", {"task_file": task_file, "workspace": ctx.obj["workspace"]}, result)
    if result.get("last_patch"):
        sess.set_last_patch(result["last_patch"])
    _output(result, ctx.obj["as_json"], f"Task {result['status']}")


@cli.group()
def flow() -> None:
    """Flow commands."""


@flow.command("validate")
@click.argument("flow_file")
@click.pass_context
@_handle_error
def flow_validate(ctx: click.Context, flow_file: str) -> None:
    """Validate a task or flow definition."""
    result = validate_definition(flow_file)
    _output(result, ctx.obj["as_json"], "Definition valid")


@flow.command("run")
@click.argument("flow_file")
@click.pass_context
@_handle_error
def flow_run(ctx: click.Context, flow_file: str) -> None:
    """Run a YAML flow."""
    model = ctx.obj.get("model")
    if not model:
        raise RuntimeError("No model configured. Use --model or `config set model <alias>`.")
    flow_def = load_flow(flow_file)
    result = execute_flow(
        flow_def,
        workspace=ctx.obj["workspace"],
        host=ctx.obj["host"],
        api_key=ctx.obj["api_key"],
        model=model,
    )
    sess = _session(ctx.obj["workspace"])
    sess.record("flow run", {"flow_file": flow_file, "workspace": ctx.obj["workspace"]}, result)
    results = result.get("results", [])
    if results and results[-1].get("last_patch"):
        sess.set_last_patch(results[-1]["last_patch"])
    _output(result, ctx.obj["as_json"], f"Flow {result['status']}")


@cli.group()
def patch() -> None:
    """Last patch inspection and rollback."""


@patch.command("show")
@click.pass_context
@_handle_error
def patch_show(ctx: click.Context) -> None:
    """Show the last generated patch diff."""
    patch_info = _session(ctx.obj["workspace"]).state.get("last_patch")
    if not patch_info:
        raise RuntimeError("No patch stored in session")
    if ctx.obj["as_json"]:
        _output(patch_info, True)
    else:
        click.echo(patch_info.get("diff", ""))


@patch.command("export")
@click.argument("outdir")
@click.pass_context
@_handle_error
def patch_export(ctx: click.Context, outdir: str) -> None:
    """Export the last patch as diff + action JSON."""
    patch_info = _session(ctx.obj["workspace"]).state.get("last_patch")
    if not patch_info:
        raise RuntimeError("No patch stored in session")
    result = export_patch(patch_info, outdir)
    _output(result, ctx.obj["as_json"], "Patch exported")


@patch.command("rollback")
@click.pass_context
@_handle_error
def patch_rollback(ctx: click.Context) -> None:
    """Roll back the last patch."""
    sess = _session(ctx.obj["workspace"])
    patch_info = sess.state.get("last_patch")
    if not patch_info:
        raise RuntimeError("No patch stored in session")
    restored = rollback_patch(patch_info, ctx.obj["workspace"])
    result = {"restored": restored}
    sess.record("patch rollback", {"workspace": ctx.obj["workspace"]}, result)
    _output(result, ctx.obj["as_json"], "Patch rolled back")


@cli.group()
def session() -> None:
    """Session commands."""


@session.command("status")
@click.pass_context
def session_status(ctx: click.Context) -> None:
    """Show session status."""
    result = _session(ctx.obj["workspace"]).status()
    result["workspace"] = ctx.obj["workspace"]
    result["host"] = ctx.obj["host"]
    result["model"] = ctx.obj["model"]
    _output(result, ctx.obj["as_json"], "Session")


@session.command("history")
@click.option("--limit", default=20, type=int)
@click.pass_context
def session_history(ctx: click.Context, limit: int) -> None:
    """Show recent run history."""
    _output(_session(ctx.obj["workspace"]).history(limit), ctx.obj["as_json"], "History")


@session.command("clear")
@click.pass_context
def session_clear(ctx: click.Context) -> None:
    """Clear session state."""
    _session(ctx.obj["workspace"]).clear()
    result = {"cleared": True}
    if ctx.obj["as_json"]:
        _output(result, True)
    else:
        success("Session cleared")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
