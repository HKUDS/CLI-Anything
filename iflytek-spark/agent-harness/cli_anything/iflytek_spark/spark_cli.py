#!/usr/bin/env python3
"""iFlytek Spark-X2.5 CLI — chat with Spark-X2.5 on any OpenAI-compatible server.

Usage:
    # One-shot commands
    cli-anything-iflytek-spark chat "Where is the capital of Anhui?"
    cli-anything-iflytek-spark --backend ollama --json chat --show-reasoning "1+1=?"

    # Interactive REPL
    cli-anything-iflytek-spark
"""

from __future__ import annotations

import functools
import json
import shlex
import sys

import click

from cli_anything.iflytek_spark import __version__
from cli_anything.iflytek_spark.core.session import ChatSession
from cli_anything.iflytek_spark.utils.spark_backend import (
    BACKENDS,
    CONFIG_KEYS,
    chat_completion,
    chat_completion_stream,
    get_config_file,
    get_home_dir,
    list_models,
    load_config,
    mask_secret,
    resolve_model,
    resolve_settings,
    save_config,
)

_json_output = False
_repl_mode = False


def output(data, message: str = ""):
    if _json_output:
        click.echo(json.dumps(data, indent=2, ensure_ascii=False, default=str))
        return
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
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (RuntimeError, ValueError) as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": type(e).__name__}, ensure_ascii=False))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)

    return wrapper


def _settings(ctx) -> dict:
    obj = ctx.find_root().obj or {}
    return resolve_settings(
        backend=obj.get("backend"),
        base_url=obj.get("base_url"),
        api_key=obj.get("api_key"),
        model=obj.get("model"),
    )


def _session() -> ChatSession:
    return ChatSession(str(get_home_dir() / "session.json"))


def _read_prompt(words: tuple, prompt_opt: str | None) -> str:
    prompt = prompt_opt or " ".join(words)
    if not prompt and not sys.stdin.isatty():
        prompt = sys.stdin.read()
    prompt = prompt.strip()
    if not prompt:
        raise ValueError("Empty prompt. Pass it as an argument, with -p, or on stdin.")
    return prompt


def _build_messages(prompt: str, system: str | None, use_session: bool) -> list:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if use_session:
        messages.extend(_session().get_messages())
    messages.append({"role": "user", "content": prompt})
    return messages


def chat_options(func):
    options = [
        click.argument("words", nargs=-1),
        click.option("--prompt", "-p", "prompt_opt", default=None, help="User prompt (alternative to positional text)"),
        click.option("--system", "-s", default=None, help="System prompt"),
        click.option("--model", "model_opt", default=None, help="Model id (overrides the backend default)"),
        click.option("--temperature", type=float, default=None, help="Sampling temperature (Spark-X2.5 recommends 1.0)"),
        click.option("--top-p", type=float, default=None, help="Nucleus sampling (Spark-X2.5 recommends 0.95)"),
        click.option("--max-tokens", type=int, default=None, help="Maximum tokens to generate"),
        click.option("--no-think", is_flag=True, help="Disable thinking (chat_template_kwargs.enable_thinking=false)"),
        click.option("--show-reasoning", is_flag=True, help="Include the model's reasoning in the output"),
        click.option("--no-session", is_flag=True, help="Do not read or write the multi-turn session"),
    ]
    for option in reversed(options):
        func = option(func)
    return func


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.option("--backend", type=click.Choice(list(BACKENDS)), default=None, help="Server preset (default: sglang)")
@click.option("--base-url", default=None, help="OpenAI-compatible base URL, e.g. http://localhost:30000/v1")
@click.option("--api-key", default=None, help="Bearer API key (needed for MaaS)")
@click.option("--model", default=None, help="Model id (default: backend preset)")
@click.version_option(__version__, prog_name="cli-anything-iflytek-spark")
@click.pass_context
def cli(ctx, use_json, backend, base_url, api_key, model):
    """iFlytek Spark-X2.5 CLI — chat with Spark-X2.5 through SGLang, vLLM,
    Ollama, llama.cpp or iFlytek Astron MaaS."""
    global _json_output
    _json_output = use_json
    ctx.ensure_object(dict)
    ctx.obj.update(backend=backend, base_url=base_url, api_key=api_key, model=model)
    if ctx.invoked_subcommand is None and not _repl_mode:
        ctx.invoke(repl)


@cli.command()
@chat_options
@click.pass_context
@handle_error
def chat(ctx, words, prompt_opt, system, model_opt, temperature, top_p, max_tokens,
         no_think, show_reasoning, no_session):
    """Send a prompt and print the answer."""
    settings = _settings(ctx)
    if model_opt:
        settings["model"] = model_opt
    prompt = _read_prompt(words, prompt_opt)
    messages = _build_messages(prompt, system, not no_session)
    result = chat_completion(
        settings,
        messages,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        thinking=not no_think,
    )
    if not no_session:
        _session().add_exchange(prompt, result["content"], result["model"])

    data = {"backend": settings["backend"], "model": result["model"], "content": result["content"]}
    if show_reasoning:
        data["reasoning"] = result["reasoning"]
    if result.get("finish_reason"):
        data["finish_reason"] = result["finish_reason"]
    if result.get("usage"):
        data["usage"] = result["usage"]

    if _json_output:
        output(data)
        return
    if show_reasoning and result["reasoning"]:
        click.secho("[reasoning]", fg="bright_black")
        click.secho(result["reasoning"], fg="bright_black")
        click.secho("[answer]", fg="bright_black")
    click.echo(result["content"])


@cli.command()
@chat_options
@click.pass_context
@handle_error
def stream(ctx, words, prompt_opt, system, model_opt, temperature, top_p, max_tokens,
           no_think, show_reasoning, no_session):
    """Stream the answer as it is generated."""
    settings = _settings(ctx)
    if model_opt:
        settings["model"] = model_opt
    prompt = _read_prompt(words, prompt_opt)
    messages = _build_messages(prompt, system, not no_session)
    state = {"in_reasoning": False}

    def on_reasoning(text):
        if _json_output or not show_reasoning:
            return
        if not state["in_reasoning"]:
            click.secho("[reasoning]", fg="bright_black")
            state["in_reasoning"] = True
        click.secho(text, fg="bright_black", nl=False)

    def on_content(text):
        if _json_output:
            return
        if state["in_reasoning"]:
            click.echo()
            click.secho("[answer]", fg="bright_black")
            state["in_reasoning"] = False
        click.echo(text, nl=False)

    result = chat_completion_stream(
        settings,
        messages,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        thinking=not no_think,
        on_content=on_content,
        on_reasoning=on_reasoning,
    )
    if not no_session:
        _session().add_exchange(prompt, result["content"], result["model"])

    if _json_output:
        data = {"backend": settings["backend"], "model": result["model"], "content": result["content"]}
        if show_reasoning:
            data["reasoning"] = result["reasoning"]
        output(data)
    else:
        click.echo()


@cli.command()
@click.pass_context
@handle_error
def models(ctx):
    """List the models served by the configured backend."""
    settings = _settings(ctx)
    items = list_models(settings["base_url"], settings.get("api_key"))
    ids = [m.get("id", "unknown") for m in items]
    if _json_output:
        output({"backend": settings["backend"], "base_url": settings["base_url"], "models": ids})
    else:
        for model_id in ids:
            click.echo(model_id)


@cli.command()
@click.pass_context
@handle_error
def backends(ctx):
    """Show the built-in server presets."""
    rows = [
        {"name": name, "base_url": p["base_url"], "model": p["model"], "description": p["description"]}
        for name, p in BACKENDS.items()
    ]
    output(rows, "Backends")


@cli.command()
@click.option("--model", "model_opt", default=None, help="Model id to test")
@click.pass_context
@handle_error
def test(ctx, model_opt):
    """Check that the server answers a short, non-thinking request."""
    settings = _settings(ctx)
    if model_opt:
        settings["model"] = model_opt
    settings["model"] = resolve_model(settings)
    result = chat_completion(
        settings,
        [{"role": "user", "content": "Reply with the single word: ok"}],
        max_tokens=16,
        thinking=False,
    )
    output(
        {"status": "ok", "backend": settings["backend"], "base_url": settings["base_url"],
         "model": result["model"], "response": result["content"]},
        "Spark-X2.5 server reachable",
    )


@cli.group()
def session():
    """Multi-turn session management."""


@session.command("status")
@handle_error
def session_status():
    """Show session status."""
    output(_session().status(), "Session status")


@session.command("clear")
@handle_error
def session_clear():
    """Forget the conversation."""
    _session().clear()
    output({"cleared": True}, "Session cleared")


@session.command("history")
@click.option("--limit", "-n", type=int, default=20, help="Maximum entries to show")
@handle_error
def session_history(limit):
    """Show recent prompts."""
    history = _session().history[-limit:]
    output(history, f"History ({len(history)} entries)")


@cli.group()
def config():
    """Persistent configuration (backend, base_url, api_key, default_model)."""


@config.command("set")
@click.argument("key", type=click.Choice(CONFIG_KEYS))
@click.argument("value")
@handle_error
def config_set(key, value):
    """Set a configuration value."""
    if key == "backend" and value not in BACKENDS:
        raise ValueError(f"Unknown backend '{value}'. Choose one of: {', '.join(BACKENDS)}")
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)
    shown = mask_secret(value) if key == "api_key" else value
    output({"key": key, "value": shown}, f"Set {key} = {shown}")


@config.command("get")
@click.argument("key", required=False)
@handle_error
def config_get(key):
    """Show one value, or the whole configuration."""
    cfg = load_config()
    if "api_key" in cfg:
        cfg["api_key"] = mask_secret(cfg["api_key"])
    if key:
        output({"key": key, "value": cfg.get(key)}, f"{key} = {cfg.get(key)}")
    else:
        output(cfg, "" if cfg else "No configuration set")


@config.command("delete")
@click.argument("key", type=click.Choice(CONFIG_KEYS))
@handle_error
def config_delete(key):
    """Delete a configuration value."""
    cfg = load_config()
    removed = cfg.pop(key, None) is not None
    save_config(cfg)
    output({"key": key, "deleted": removed}, f"Deleted {key}" if removed else f"{key} was not set")


@config.command("path")
def config_path():
    """Show the config file path."""
    path = str(get_config_file())
    output({"path": path}, f"Config file: {path}")


@cli.command("repl", hidden=True)
@click.pass_context
@handle_error
def repl(ctx):
    """Enter interactive REPL mode."""
    global _repl_mode
    _repl_mode = True

    from cli_anything.iflytek_spark.utils.repl_skin import ReplSkin

    skin = ReplSkin("iflytek_spark", version=__version__)
    skin.print_banner()
    pt_session = skin.create_prompt_session()

    commands = {
        "chat <prompt>": "Ask Spark-X2.5 (keeps multi-turn context)",
        "stream <prompt>": "Stream the answer",
        "chat --show-reasoning <prompt>": "Also print the reasoning",
        "chat --no-think <prompt>": "Answer without thinking",
        "models": "List served models",
        "backends": "Show server presets",
        "test": "Check server connectivity",
        "session status|clear|history": "Manage the conversation",
        "config set|get|delete|path": "Manage configuration",
        "help": "Show this help",
        "quit / exit": "Exit REPL",
    }

    root_args = []
    for flag, key in (("--backend", "backend"), ("--base-url", "base_url"),
                      ("--api-key", "api_key"), ("--model", "model")):
        if ctx.obj and ctx.obj.get(key):
            root_args += [flag, ctx.obj[key]]
    if _json_output:
        root_args.insert(0, "--json")

    while True:
        try:
            line = skin.get_input(pt_session, context="spark")
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

        try:
            parts = shlex.split(line)
        except ValueError as e:
            skin.error(str(e))
            continue
        try:
            cli.main(root_args + parts, standalone_mode=False)
        except SystemExit:
            pass
        except click.exceptions.UsageError as e:
            skin.error(str(e))
        except Exception as e:
            skin.error(str(e))


def main():
    for stream_ in (sys.stdout, sys.stderr):
        try:
            stream_.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    cli()


if __name__ == "__main__":
    main()
