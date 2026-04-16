#!/usr/bin/env python3
"""Novita CLI — OpenAI-compatible AI API client.

Usage:
    # One-shot commands
    cli-anything-novita chat --prompt "Hello" --model deepseek/deepseek-v3.2

    # Interactive REPL
    cli-anything-novita
"""

from __future__ import annotations

import sys
import os
import json
import click
from pathlib import Path

from cli_anything.novita.core.session import ChatSession
from cli_anything.novita.utils.novita_backend import (
    get_api_key,
    load_config,
    save_config,
    chat_completion,
    chat_completion_stream,
    run_full_workflow,
    API_BASE,
    ENV_API_KEY,
    list_models,
)

_session = None
_json_output = False
_repl_mode = False


def get_session():
    global _session
    if _session is None:
        sf = str(Path.home() / ".cli-anything-novita" / "session.json")
        _session = ChatSession(session_file=sf)
    return _session


def output(data, message: str = ""):
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        if isinstance(data, dict):
            _print_dict(data)
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
        except (RuntimeError, ValueError) as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": type(e).__name__}))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.option("--api-key", "api_key_opt", type=str, default=None, help="Novita API key")
@click.option(
    "--model",
    "model_opt",
    type=str,
    default=None,
    help="Model ID (default: deepseek/deepseek-v3.2)",
)
@click.pass_context
def cli(ctx, use_json, api_key_opt, model_opt):
    """Novita CLI — OpenAI-compatible AI API client."""
    global _json_output
    _json_output = use_json
    ctx.ensure_object(dict)
    ctx.obj["api_key"] = api_key_opt
    ctx.obj["model"] = model_opt

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.command()
@click.option("--prompt", "-p", required=True, help="User prompt")
@click.option(
    "--model",
    "model_opt",
    type=str,
    default=None,
    help="Model ID (default: deepseek/deepseek-v3.2)",
)
@click.option("--temperature", type=float, default=None, help="Temperature (0.0-1.0)")
@click.option("--max-tokens", type=int, default=None, help="Maximum tokens to generate")
@click.pass_context
@handle_error
def chat(ctx, prompt, model_opt=None, temperature=None, max_tokens=None):
    """Chat with the Novita API."""
    parent_key = ctx.obj.get("api_key") if ctx.obj else None
    api_key = get_api_key(parent_key)
    model = model_opt or (ctx.obj.get("model") if ctx.obj else None) or "deepseek/deepseek-v3.2"

    # Build messages
    messages = []

    # Check for existing session
    session = get_session()
    messages.extend(session.get_messages())
    messages.append({"role": "user", "content": prompt})

    result = chat_completion(
        api_key=api_key,
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # Extract content
    choices = result.get("choices", [])
    if choices:
        content = choices[0].get("message", {}).get("content", "")
    else:
        content = ""

    # Update session
    session.add_user_message(prompt)
    session.add_assistant_message(content)

    # Add usage info if available
    output_data = {"content": content}
    usage = result.get("usage", {})
    if usage:
        output_data["usage"] = usage

    output(output_data, f"✓ Response from {model}")


@cli.command()
@click.option("--prompt", "-p", required=True, help="User prompt")
@click.option(
    "--model",
    "model_opt",
    type=str,
    default=None,
    help="Model ID (default: deepseek/deepseek-v3.2)",
)
@click.option("--temperature", type=float, default=None, help="Temperature (0.0-1.0)")
@click.option("--max-tokens", type=int, default=None, help="Maximum tokens to generate")
@click.pass_context
@handle_error
def stream(ctx, prompt, model_opt=None, temperature=None, max_tokens=None):
    """Stream chat completion."""
    parent_key = ctx.obj.get("api_key") if ctx.obj else None
    api_key = get_api_key(parent_key)
    model = model_opt or (ctx.obj.get("model") if ctx.obj else None) or "deepseek/deepseek-v3.2"

    # Build messages
    messages = []
    session = get_session()
    messages.extend(session.get_messages())
    messages.append({"role": "user", "content": prompt})

    full_response = ""

    def on_chunk(chunk_content):
        if chunk_content:
            nonlocal full_response
            full_response += chunk_content
            if not _json_output:
                click.echo(chunk_content, nl=False)

    result = chat_completion_stream(
        api_key=api_key,
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        on_chunk=on_chunk,
    )

    if not _json_output:
        click.echo()  # Add newline after stream

    # Update session
    session.add_user_message(prompt)
    session.add_assistant_message(full_response)

    output({"content": full_response}, "✓ Stream completed")


@cli.group()
def session():
    """Session management commands."""
    pass


@session.command("status")
@handle_error
def session_status():
    """Show session status."""
    s = get_session()
    output(s.status(), "Session status")


@session.command("clear")
@handle_error
def session_clear():
    """Clear session history."""
    s = get_session()
    s.clear()
    output({"cleared": True}, "Session cleared")


@session.command("history")
@click.option("--limit", "-n", type=int, default=20, help="Maximum entries to show")
@handle_error
def session_history(limit):
    """Show command history."""
    s = get_session()
    history = s.history[-limit:]
    output(history, f"History ({len(history)} entries)")


@cli.group()
def config():
    """Configuration management."""
    pass


@config.command("set")
@click.argument("key", type=click.Choice(["api_key", "default_model"]))
@click.argument("value")
def config_set(key, value):
    """Set a configuration value."""
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)
    display = value[:10] + "..." if key == "api_key" and len(value) > 10 else value
    output({"key": key, "value": display}, f"✓ Set {key} = {display}")


@config.command("get")
@click.argument("key", required=False)
def config_get(key):
    """Get a configuration value (or show all)."""
    cfg = load_config()
    if key:
        val = cfg.get(key)
        if val:
            if key == "api_key" and len(val) > 10:
                val = val[:10] + "..."
            output({"key": key, "value": val}, f"{key} = {val}")
        else:
            output({"key": key, "value": None}, f"{key} is not set")
    else:
        if cfg:
            masked = {}
            for k, v in cfg.items():
                masked[k] = v[:10] + "..." if k == "api_key" and len(v) > 10 else v
            output(masked)
        else:
            output({}, "No configuration set")


@config.command("delete")
@click.argument("key")
def config_delete(key):
    """Delete a configuration value."""
    cfg = load_config()
    if key in cfg:
        del cfg[key]
        save_config(cfg)
        output({"deleted": key}, f"✓ Deleted {key}")
    else:
        output({"error": f"{key} not found"}, f"{key} not found in config")


@config.command("path")
def config_path():
    """Show the config file path."""
    from cli_anything.novita.utils.novita_backend import CONFIG_FILE

    output({"path": str(CONFIG_FILE)}, f"Config file: {CONFIG_FILE}")


@cli.command()
@click.option(
    "--model",
    "model_opt",
    type=str,
    default=None,
    help="Model ID to test (default: deepseek/deepseek-v3.2)",
)
@handle_error
def test(model_opt=None):
    """Test Novita API connectivity."""
    api_key = get_api_key()
    model = model_opt or "deepseek/deepseek-v3.2"

    result = chat_completion(
        api_key=api_key,
        model=model,
        messages=[{"role": "user", "content": "Say 'ok'"}],
        max_tokens=5,
    )

    choices = result.get("choices", [])
    content = ""
    if choices:
        content = choices[0].get("message", {}).get("content", "")

    output(
        {"status": "ok", "model": model, "response": content},
        "✓ Novita API test passed",
    )


@cli.command()
@handle_error
def models():
    """List available models."""
    api_key = get_api_key()
    models_list = list_models(api_key)

    for m in models_list:
        click.echo(m.get("id", m.get("name", "unknown")))


@cli.command("repl", hidden=True)
@handle_error
def repl():
    """Enter interactive REPL mode."""
    global _repl_mode
    _repl_mode = True

    from cli_anything.novita.utils.repl_skin import ReplSkin

    skin = ReplSkin("novita", version="1.0.0")
    skin.print_banner()

    pt_session = skin.create_prompt_session()

    commands = {
        "chat <prompt>": "Chat with the Novita API",
        "stream <prompt>": "Stream chat completion",
        "session status": "Show session status",
        "session clear": "Clear session history",
        "session history": "Show command history",
        "config set <key> <val>": "Set configuration",
        "config get [key]": "Show configuration",
        "test [model]": "Test API connectivity",
        "models": "List available models",
        "help": "Show this help",
        "quit / exit": "Exit REPL",
    }

    while True:
        try:
            line = skin.get_input(pt_session, context="novita")
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

        if not line:
            continue
        if line in ("quit", "exit", "q"):
            skin.print_goodbye()
            break
        if line == "help":
            skin.help(commands)
            continue

        parts = line.split()
        try:
            cli.main(parts, standalone_mode=False)
        except SystemExit:
            pass
        except click.exceptions.UsageError as e:
            skin.error(str(e))
        except Exception as e:
            skin.error(str(e))


def main():
    cli()


if __name__ == "__main__":
    main()
