#!/usr/bin/env python3
"""Ollama CLI — A command-line interface for local LLM inference and model management.

This CLI provides full access to the Ollama REST API for managing models,
generating text, chatting, and creating embeddings.

Usage:
    # One-shot commands
    cli-anything-ollama model list
    cli-anything-ollama generate text --model llama3.2 --prompt "Hello"
    cli-anything-ollama --json server status

    # Interactive REPL
    cli-anything-ollama
"""

import sys
import os
import json
import shlex
import click
from typing import Optional

from cli_anything.ollama.utils.ollama_backend import DEFAULT_BASE_URL
from cli_anything.ollama.core import models as models_mod
from cli_anything.ollama.core import generate as gen_mod
from cli_anything.ollama.core import embeddings as embed_mod
from cli_anything.ollama.core import server as server_mod

# Global state
_json_output = False
_repl_mode = False
_host = DEFAULT_BASE_URL
_chat_history: list[dict] = []
_last_model: str = ""


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
@click.option("--host", type=str, default=None,
              help=f"Ollama server URL (default: {DEFAULT_BASE_URL})")
@click.pass_context
def cli(ctx, use_json, host):
    """Ollama CLI — Local LLM inference and model management.

    Run without a subcommand to enter interactive REPL mode.
    """
    global _json_output, _host
    _json_output = use_json
    if host:
        _host = host

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── Model Commands ───────────────────────────────────────────────
@cli.group()
def model():
    """Model management commands."""
    pass


@model.command("list")
@handle_error
def model_list():
    """List locally available models."""
    result = models_mod.list_models(_host)
    models = result.get("models", [])
    if _json_output:
        output(result)
    else:
        if not models:
            click.echo("No models installed. Pull one with: model pull <name>")
            return
        click.echo(f"{'NAME':<40} {'SIZE':<12} {'MODIFIED'}")
        click.echo("─" * 70)
        for m in models:
            name = m.get("name", "")
            size = m.get("size", 0)
            modified = m.get("modified_at", "")[:19]
            size_str = _format_size(size)
            click.echo(f"{name:<40} {size_str:<12} {modified}")


@model.command("show")
@click.argument("name")
@handle_error
def model_show(name):
    """Show model details (parameters, template, license)."""
    result = models_mod.show_model(_host, name)
    output(result, f"Model: {name}")


@model.command("pull")
@click.argument("name")
@click.option("--no-stream", is_flag=True, help="Wait for completion without progress")
@handle_error
def model_pull(name, no_stream):
    """Download a model from the Ollama library."""
    if no_stream or _json_output:
        result = models_mod.pull_model(_host, name, stream=False)
        output(result, f"Pulled: {name}")
    else:
        click.echo(f"Pulling {name}...")
        last_status = ""
        for chunk in models_mod.pull_model(_host, name, stream=True):
            if "error" in chunk:
                raise RuntimeError(chunk["error"])
            status = chunk.get("status", "")
            if status != last_status:
                click.echo(f"  {status}")
                last_status = status
            completed = chunk.get("completed", 0)
            total = chunk.get("total", 0)
            if total > 0:
                pct = int(completed / total * 100)
                bar_w = 30
                filled = int(bar_w * completed / total)
                bar = "█" * filled + "░" * (bar_w - filled)
                click.echo(f"\r  {bar} {pct:3d}% ({_format_size(completed)}/{_format_size(total)})", nl=False)
        click.echo(f"\nDone: {name}")


@model.command("rm")
@click.argument("name")
@handle_error
def model_rm(name):
    """Delete a model from local storage."""
    result = models_mod.delete_model(_host, name)
    output(result, f"Deleted: {name}")


@model.command("copy")
@click.argument("source")
@click.argument("destination")
@handle_error
def model_copy(source, destination):
    """Copy a model to a new name."""
    result = models_mod.copy_model(_host, source, destination)
    output(result, f"Copied {source} → {destination}")


@model.command("ps")
@handle_error
def model_ps():
    """List models currently loaded in memory."""
    result = models_mod.running_models(_host)
    models = result.get("models", [])
    if _json_output:
        output(result)
    else:
        if not models:
            click.echo("No models currently loaded.")
            return
        click.echo(f"{'NAME':<40} {'SIZE':<12} {'PROCESSOR':<15} {'UNTIL'}")
        click.echo("─" * 80)
        for m in models:
            name = m.get("name", "")
            size = m.get("size", 0)
            proc = m.get("size_vram", 0)
            until = m.get("expires_at", "")[:19]
            click.echo(f"{name:<40} {_format_size(size):<12} {_format_size(proc):<15} {until}")


# ── Generate Commands ────────────────────────────────────────────
@cli.group()
def generate():
    """Text generation and chat commands."""
    pass


@generate.command("text")
@click.option("--model", "-m", "model_name", required=True, help="Model name")
@click.option("--prompt", "-p", required=True, help="Input prompt")
@click.option("--system", "-s", default=None, help="System message")
@click.option("--no-stream", is_flag=True, help="Return complete response instead of streaming")
@click.option("--temperature", type=float, default=None, help="Sampling temperature")
@click.option("--top-p", type=float, default=None, help="Top-p sampling")
@click.option("--num-predict", type=int, default=None, help="Max tokens to generate")
@handle_error
def generate_text(model_name, prompt, system, no_stream, temperature, top_p, num_predict):
    """Generate text from a prompt."""
    global _last_model
    _last_model = model_name

    options = {}
    if temperature is not None:
        options["temperature"] = temperature
    if top_p is not None:
        options["top_p"] = top_p
    if num_predict is not None:
        options["num_predict"] = num_predict

    if no_stream or _json_output:
        result = gen_mod.generate(
            _host, model_name, prompt, system=system,
            options=options or None, stream=False,
        )
        output(result)
    else:
        chunks = gen_mod.generate(
            _host, model_name, prompt, system=system,
            options=options or None, stream=True,
        )
        final = gen_mod.stream_to_stdout(chunks)


@generate.command("chat")
@click.option("--model", "-m", "model_name", required=True, help="Model name")
@click.option("--message", "messages_input", multiple=True,
              help="Messages as role:content (repeatable)")
@click.option("--file", "messages_file", type=click.Path(exists=True), default=None,
              help="JSON file with messages array")
@click.option("--no-stream", is_flag=True, help="Return complete response instead of streaming")
@click.option("--temperature", type=float, default=None, help="Sampling temperature")
@click.option("--continue-chat", is_flag=True, help="Continue previous chat session")
@handle_error
def generate_chat(model_name, messages_input, messages_file, no_stream, temperature, continue_chat):
    """Send a chat completion request."""
    global _last_model, _chat_history
    _last_model = model_name

    options = {}
    if temperature is not None:
        options["temperature"] = temperature

    # Build messages list
    if messages_file:
        with open(messages_file, "r") as f:
            messages = json.load(f)
    elif messages_input:
        messages = []
        for msg in messages_input:
            if ":" not in msg:
                raise ValueError(f"Invalid message format: '{msg}'. Use role:content")
            role, content = msg.split(":", 1)
            messages.append({"role": role.strip(), "content": content.strip()})
    else:
        raise ValueError("Provide messages via --message or --file")

    if continue_chat:
        messages = _chat_history + messages

    if no_stream or _json_output:
        result = gen_mod.chat(
            _host, model_name, messages,
            options=options or None, stream=False,
        )
        if not _json_output and "message" in result:
            _chat_history = messages + [result["message"]]
        output(result)
    else:
        chunks = gen_mod.chat(
            _host, model_name, messages,
            options=options or None, stream=True,
        )
        # Collect streamed content for history
        collected = []
        for chunk in chunks:
            if "error" in chunk:
                raise RuntimeError(chunk["error"])
            if "message" in chunk and "content" in chunk["message"]:
                token = chunk["message"]["content"]
                collected.append(token)
                sys.stdout.write(token)
                sys.stdout.flush()
        sys.stdout.write("\n")
        sys.stdout.flush()
        full_response = "".join(collected)
        _chat_history = messages + [{"role": "assistant", "content": full_response}]


# ── Embed Commands ───────────────────────────────────────────────
@cli.group()
def embed():
    """Embedding generation commands."""
    pass


@embed.command("text")
@click.option("--model", "-m", "model_name", required=True, help="Model name")
@click.option(
    "--input", "-i", "input_texts",
    multiple=True, required=True,
    help="Text to embed. Repeat for batch embeddings.",
)
@handle_error
def embed_text(model_name, input_texts):
    """Generate embeddings for text."""
    payload = list(input_texts)
    result = embed_mod.embed(_host, model_name, payload[0] if len(payload) == 1 else payload)
    if _json_output:
        output(result)
    else:
        embeddings = result.get("embeddings", [])
        if embeddings:
            dims = len(embeddings[0]) if embeddings else 0
            click.echo(f"Model: {model_name}")
            click.echo(f"Dimensions: {dims}")
            click.echo(f"Vectors: {len(embeddings)}")
            # Show first few values
            if embeddings:
                preview = embeddings[0][:5]
                click.echo(f"Preview: [{', '.join(f'{v:.6f}' for v in preview)}, ...]")
        else:
            output(result)


# ── Server Commands ──────────────────────────────────────────────
@cli.group()
def server():
    """Server status and info commands."""
    pass


@server.command("status")
@handle_error
def server_status():
    """Check if Ollama server is running."""
    result = server_mod.server_status(_host)
    output(result, f"Ollama server at {_host}: running")


@server.command("version")
@handle_error
def server_version():
    """Show Ollama server version."""
    result = server_mod.version(_host)
    output(result)


# ── Session Commands ─────────────────────────────────────────────
@cli.group()
def session():
    """Session state commands."""
    pass


@session.command("status")
@handle_error
def session_status():
    """Show current session state."""
    data = {
        "host": _host,
        "last_model": _last_model or "(none)",
        "chat_history_length": len(_chat_history),
        "json_output": _json_output,
    }
    output(data, "Session Status")


@session.command("history")
@handle_error
def session_history():
    """Show chat history for current session."""
    if not _chat_history:
        output({"messages": []}, "No chat history.")
        return
    if _json_output:
        output({"messages": _chat_history})
    else:
        for msg in _chat_history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            # Truncate long messages for display
            if len(content) > 200:
                content = content[:200] + "..."
            click.echo(f"[{role}] {content}")


# ── REPL ─────────────────────────────────────────────────────────
@cli.command()
@handle_error
def repl():
    """Start interactive REPL session."""
    from cli_anything.ollama.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True

    skin = ReplSkin("ollama", version="1.0.1")
    skin.print_banner()

    pt_session = skin.create_prompt_session()

    _repl_commands = {
        "model":    "list|show|pull|rm|copy|ps",
        "generate": "text|chat",
        "embed":    "text",
        "server":   "status|version",
        "session":  "status|history",
        "help":     "Show this help",
        "quit":     "Exit REPL",
    }

    while True:
        try:
            context = _last_model if _last_model else ""
            line = skin.get_input(pt_session, project_name=context, modified=False)
            if not line:
                continue
            if line.lower() in ("quit", "exit", "q"):
                skin.print_goodbye()
                break
            if line.lower() == "help":
                skin.help(_repl_commands)
                continue

            # Parse and execute command (shlex handles quoted strings with spaces)
            try:
                args = shlex.split(line)
            except ValueError:
                args = line.split()
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


# ── Helpers ──────────────────────────────────────────────────────
def _format_size(size_bytes: int) -> str:
    """Format byte count as human-readable string."""
    if size_bytes == 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


# ── Entry Point ──────────────────────────────────────────────────
def main():
    cli()


if __name__ == "__main__":
    main()
