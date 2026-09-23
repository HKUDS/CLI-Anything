#!/usr/bin/env python3
"""OrcaRouter CLI — first-class OrcaRouter provider for CLI-Anything.

OrcaRouter is an OpenAI-compatible AI gateway that routes many providers behind
one endpoint. This harness exposes two explicit ways to authenticate:

    cli-anything-orcarouter auth api-key --api-key sk-orca-...   # OrcaRouter - API
    cli-anything-orcarouter auth login                           # OrcaRouter - Auth (PKCE)

Both produce the same durable OrcaRouter API key. Inference and model discovery
go to https://api.orcarouter.ai/v1; authorization goes to
https://www.orcarouter.ai.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

import click

from cli_anything.orcarouter.core import catalog as catalog_mod
from cli_anything.orcarouter.core import credentials, login_manager, pkce, provider
from cli_anything.orcarouter.core import server as server_mod

_json_output = False
_repl_mode = False


def output(data: Any, message: str = "") -> None:
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
        return
    if message:
        click.echo(message)
    if isinstance(data, dict):
        _print_dict(data)
    elif isinstance(data, list):
        _print_list(data)
    elif data is not None:
        click.echo(str(data))


def _print_dict(data: dict, indent: int = 0) -> None:
    prefix = "  " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            click.echo(f"{prefix}{key}:")
            _print_dict(value, indent + 1)
        elif isinstance(value, list):
            click.echo(f"{prefix}{key}:")
            _print_list(value, indent + 1)
        else:
            click.echo(f"{prefix}{key}: {value}")


def _print_list(items: list, indent: int = 0) -> None:
    prefix = "  " * indent
    for item in items:
        if isinstance(item, dict):
            click.echo(f"{prefix}- {item.get('id', item)}")
            for key, value in item.items():
                if key != "id":
                    click.echo(f"{prefix}    {key}: {value}")
        else:
            click.echo(f"{prefix}- {item}")


def handle_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (
            credentials.AuthRequiredError,
            provider.ProviderError,
            catalog_mod.CatalogError,
            login_manager.LoginError,
            pkce.PkceError,
            ValueError,
        ) as exc:
            if _json_output:
                click.echo(json.dumps({"error": str(exc), "type": type(exc).__name__}))
            else:
                click.echo(f"Error: {exc}", err=True)
            if not _repl_mode:
                sys.exit(1)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def _credential(cli_key: Optional[str] = None) -> credentials.Credential:
    return credentials.require_credential(cli_key)


# ── main group ────────────────────────────────────────────────────────────────


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.option("--api-key", "api_key_opt", default=None, envvar=credentials.ENV_API_KEY,
              help="OrcaRouter API key (overrides the stored credential for this call).")
@click.pass_context
def cli(ctx, use_json, api_key_opt):
    """OrcaRouter — OpenAI-compatible AI gateway."""
    global _json_output
    _json_output = use_json
    ctx.ensure_object(dict)
    ctx.obj["api_key"] = api_key_opt
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── auth ──────────────────────────────────────────────────────────────────────


@cli.group()
def auth():
    """Authentication: API key or OrcaRouter account sign-in."""


@auth.command("api-key")
@click.option("--api-key", "api_key_opt", default=None, prompt=False,
              help="The sk-orca-… key to store. Prompted for when omitted.")
@click.pass_context
@handle_error
def auth_api_key(ctx, api_key_opt):
    """Store an existing OrcaRouter API key (choice: OrcaRouter - API)."""
    key = api_key_opt
    if not key:
        key = click.prompt("OrcaRouter API key", hide_input=True)
    credentials.validate_api_key_format(key)
    stored = credentials.store_credential(
        credentials.Credential(
            api_key=key.strip(),
            method=credentials.METHOD_API_KEY,
            source=credentials.SOURCE_STORED,
        )
    )
    output(
        {
            "status": "stored",
            "method": stored.method,
            "masked_key": credentials.mask_secret(stored.api_key),
            "generation": stored.generation,
            "config_path": str(credentials.CONFIG_FILE),
        },
        f"✓ Stored OrcaRouter API key {credentials.mask_secret(stored.api_key)} "
        f"({credentials.CONFIG_FILE})",
    )


@auth.command("login")
@click.option("--oob", "use_oob", is_flag=True,
              help="Out-of-band code instead of a loopback redirect (headless/SSH/containers).")
@click.option("--scope", type=click.Choice([pkce.SCOPE_API, pkce.SCOPE_CONNECTOR]),
              default=pkce.SCOPE_API, show_default=True, help="Requested authorization scope.")
@click.option("--timeout", type=float, default=login_manager.DEFAULT_TIMEOUT, show_default=True,
              help="Seconds to wait for the browser callback.")
@click.option("--no-browser", is_flag=True, help="Print the URL instead of opening a browser.")
@handle_error
def auth_login(use_oob, scope, timeout, no_browser):
    """Connect with OrcaRouter (choice: OrcaRouter - Auth, OAuth 2.0 + PKCE)."""
    flow = pkce.FLOW_OOB if use_oob else pkce.FLOW_LOOPBACK
    manager = login_manager.LoginManager()

    def on_prompt(url: str) -> None:
        if _json_output:
            return
        click.echo("Opening your browser to authorize OrcaRouter…")
        click.echo(url)

    def code_provider(url: str) -> str:
        click.echo("Approve the request in your browser, then paste the code shown there.")
        return click.prompt("Code", hide_input=False)

    result = login_manager.run_login(
        manager,
        flow=flow,
        scope=scope,
        timeout=timeout,
        open_browser=not no_browser,
        on_prompt=on_prompt,
        code_provider=code_provider if use_oob else None,
    )

    warning = result.scope_warning()
    if warning and not _json_output:
        click.echo(f"Warning: {warning}", err=True)
    if not result.scope_allows_api():
        raise ValueError(
            f'Granted scope "{result.granted_scope}" does not permit inference. '
            "Ask a workspace owner for the api scope, or store an API key instead."
        )

    stored = credentials.store_credential(result.to_credential())
    output(
        {
            "status": "connected",
            "method": stored.method,
            "flow": flow,
            "account_id": stored.account_id,
            "granted_scope": stored.scope,
            "masked_key": credentials.mask_secret(stored.api_key),
            "generation": stored.generation,
        },
        f"✓ Connected. Stored key {credentials.mask_secret(stored.api_key)} "
        f"(scope {stored.scope or 'api'}) in {credentials.CONFIG_FILE}",
    )


@auth.command("status")
@handle_error
def auth_status():
    """Show the credential in use and where it came from."""
    credential = credentials.resolve_credential()
    payload = {
        "authenticated": credential is not None,
        "auth_origin": credentials.auth_base_url(),
        "api_origin": credentials.api_base_url(),
        "config_path": str(credentials.CONFIG_FILE),
    }
    if credential is not None:
        payload.update(credential.public_dict())
        payload["masked_key"] = credentials.mask_secret(credential.api_key)
    output(payload, "Authenticated" if credential else "Not authenticated")


@auth.command("logout")
@handle_error
def auth_logout():
    """Remove the stored credential (does not revoke it upstream)."""
    removed = credentials.clear_credential()
    output(
        {"removed": removed},
        "✓ Removed the stored credential." if removed else "No stored credential.",
    )


@auth.command("set-key", hidden=True)
@click.argument("api_key")
@handle_error
def auth_set_key(api_key):
    """Alias for `auth api-key`."""
    credentials.validate_api_key_format(api_key)
    stored = credentials.store_credential(
        credentials.Credential(
            api_key=api_key.strip(),
            method=credentials.METHOD_API_KEY,
            source=credentials.SOURCE_STORED,
        )
    )
    output({"status": "stored", "masked_key": credentials.mask_secret(stored.api_key)},
           f"✓ Stored {credentials.mask_secret(stored.api_key)}")


@auth.command("clear", hidden=True)
@handle_error
def auth_clear():
    """Alias for `auth logout`."""
    removed = credentials.clear_credential()
    output({"removed": removed}, "✓ Cleared." if removed else "Nothing to clear.")


# ── models ────────────────────────────────────────────────────────────────────


@cli.command("models")
@click.option("--capability", type=click.Choice([
    catalog_mod.CAPABILITY_CHAT, catalog_mod.CAPABILITY_EMBEDDING,
    catalog_mod.CAPABILITY_IMAGE, catalog_mod.CAPABILITY_VIDEO,
    catalog_mod.CAPABILITY_RERANK,
]), default=catalog_mod.CAPABILITY_CHAT, show_default=True,
    help="Which entry point the list is for.")
@click.option("--modalities", default="",
              help="Comma-separated non-text input modalities the entry point uploads (e.g. image).")
@click.option("--refresh", is_flag=True, help="Ignore nothing; always re-fetch (live is the default).")
@click.pass_context
@handle_error
def models(ctx, capability, modalities, refresh):
    """List OrcaRouter models, filtered for one capability."""
    required = tuple(m for m in modalities.split(",") if m)
    credential = credentials.resolve_credential(ctx.obj.get("api_key"))
    source = catalog_mod.load_catalog(credential, capability=capability)
    selectable = catalog_mod.selectable_models(
        source, capability, required_modalities=required
    )
    payload = {
        "capability": capability,
        "required_modalities": list(required),
        "catalog_source": source.source,
        "degraded": source.degraded,
        "detail": source.detail,
        "count": len(selectable),
        "models": [m.to_public_dict() for m in selectable],
    }
    if _json_output:
        click.echo(json.dumps(payload, indent=2))
        return
    if source.degraded:
        click.echo(f"[degraded] live catalog unavailable ({source.detail}); "
                   "showing the verified fallback list.", err=True)
    if not selectable:
        click.echo(f"No OrcaRouter model declares the {capability} capability.")
        return
    for model in selectable:
        click.echo(f"{model.id}  ({', '.join(model.input_modalities) or 'unknown input'})")


@cli.command("catalog")
@click.option("--capability", default=catalog_mod.CAPABILITY_CHAT, show_default=True)
@handle_error
def catalog_cmd(capability):
    """Show catalog provenance (live vs verified fallback)."""
    credential = credentials.resolve_credential()
    source = catalog_mod.load_catalog(credential, capability=capability)
    output(
        {
            "source": source.source,
            "degraded": source.degraded,
            "detail": source.detail,
            "count": len(source.models),
            "catalog_url": f"{credentials.api_base_url()}/models",
            "reasoning_efforts": {
                m.id: list(m.reasoning_efforts)
                for m in source.models
                if m.reasoning_efforts
            },
        },
        f"catalog: {source.source} ({len(source.models)} models)",
    )


# ── chat ──────────────────────────────────────────────────────────────────────


@cli.command("chat")
@click.option("--prompt", "-p", required=True, help="User prompt.")
@click.option("--model", "model_opt", default=None, help="Model ID (default: orcarouter/auto).")
@click.option("--system", default=None, help="System instruction.")
@click.option("--image", "images", multiple=True, type=click.Path(exists=True, dir_okay=False),
              help="Attach an image (repeatable). The model must declare image input.")
@click.option("--temperature", type=float, default=None)
@click.option("--max-tokens", type=int, default=None)
@click.pass_context
@handle_error
def chat(ctx, prompt, model_opt, system, images, temperature, max_tokens):
    """Send one chat completion through the OrcaRouter relay."""
    credential = _credential(ctx.obj.get("api_key"))
    messages, required = provider.build_messages(
        prompt=prompt, system=system, image_paths=list(images) or None
    )
    model = model_opt or _default_model(credential, required)
    _guard(credential, model, required)

    result = provider.chat_completion(
        credential, model=model, messages=messages,
        temperature=temperature, max_tokens=max_tokens,
    )
    output(
        {
            "model": result.model,
            "content": result.content,
            "usage": result.usage,
            "response_id": result.response_id,
        },
        result.content,
    )


@cli.command("stream")
@click.option("--prompt", "-p", required=True, help="User prompt.")
@click.option("--model", "model_opt", default=None, help="Model ID (default: orcarouter/auto).")
@click.option("--system", default=None, help="System instruction.")
@click.pass_context
@handle_error
def stream(ctx, prompt, model_opt, system):
    """Stream a chat completion from the OrcaRouter relay."""
    credential = _credential(ctx.obj.get("api_key"))
    messages, required = provider.build_messages(prompt=prompt, system=system)
    model = model_opt or _default_model(credential, required)
    _guard(credential, model, required)

    chunks: list[str] = []
    for chunk in provider.chat_completion_stream(credential, model=model, messages=messages):
        chunks.append(chunk)
        if not _json_output:
            click.echo(chunk, nl=False)
    if not _json_output:
        click.echo()
    else:
        click.echo(json.dumps({"model": model, "content": "".join(chunks)}, indent=2))


def _default_model(credential: credentials.Credential, required: tuple[str, ...]) -> str:
    catalog = provider.discover_selectable(credential, required_modalities=required)
    if not catalog.models:
        raise ValueError(
            "No OrcaRouter model is available for this request. Run `models` to inspect the catalog."
        )
    return catalog.models[0].id


def _guard(credential: credentials.Credential, model: str, required: tuple[str, ...]) -> None:
    provider.guard_for_entry_point(credential, model, required)


@cli.command("test")
@click.option("--model", "model_opt", default=None, help="Model ID to test.")
@click.pass_context
@handle_error
def test(ctx, model_opt):
    """Make one real request through the OrcaRouter provider path."""
    credential = _credential(ctx.obj.get("api_key"))
    model = model_opt or _default_model(credential, ())
    result = provider.chat_completion(
        credential,
        model=model,
        messages=[{"role": "user", "content": "Reply with the single word: ok"}],
        max_tokens=16,
    )
    output(
        {
            "status": "ok",
            "api_origin": credentials.api_base_url(),
            "model": result.model,
            "response": result.content.strip(),
            "usage": result.usage,
        },
        f"✓ OrcaRouter request succeeded via {credentials.api_base_url()} ({result.model})",
    )


# ── config ────────────────────────────────────────────────────────────────────


@cli.group("config")
def config():
    """Configuration paths and raw values."""


@config.command("path")
def config_path():
    """Show the config file path."""
    output({"path": str(credentials.CONFIG_FILE)}, f"Config file: {credentials.CONFIG_FILE}")


@config.command("show")
@handle_error
def config_show():
    """Show stored configuration with the key masked."""
    config_data = credentials.load_config()
    entry = config_data.get("credential")
    if isinstance(entry, dict) and entry.get("api_key"):
        entry = dict(entry)
        entry["api_key"] = credentials.mask_secret(str(entry["api_key"]))
        config_data = dict(config_data)
        config_data["credential"] = entry
    output(config_data or {}, "No configuration stored." if not config_data else "")


# ── ui ────────────────────────────────────────────────────────────────────────


@cli.command("ui")
@click.option("--port", type=int, default=0, show_default=True,
              help="Loopback port (0 picks a free one).")
@click.option("--no-browser", is_flag=True, help="Do not open a browser.")
@handle_error
def ui(port, no_browser):
    """Serve the OrcaRouter settings page on loopback."""
    def on_ready(url: str) -> None:
        click.echo(f"OrcaRouter settings UI: {url}")
        click.echo("Press Ctrl-C to stop.")

    server_mod.serve_forever(port=port, open_browser=not no_browser, on_ready=on_ready)


# ── REPL ──────────────────────────────────────────────────────────────────────


@cli.command("repl", hidden=True)
@handle_error
def repl():
    """Enter interactive REPL mode."""
    global _repl_mode
    _repl_mode = True

    from cli_anything.orcarouter.utils.repl_skin import ReplSkin

    skin = ReplSkin("orcarouter", version="1.0.0")
    skin.print_banner()
    pt_session = skin.create_prompt_session()
    commands = {
        "auth status": "Show the credential in use",
        "auth api-key --api-key sk-orca-…": "Store an API key",
        "auth login": "Connect with OrcaRouter (OAuth 2.0 + PKCE)",
        "models": "List models for the chat capability",
        "catalog": "Show catalog provenance",
        "chat <prompt>": "Chat through OrcaRouter",
        "ui": "Serve the settings page",
        "quit": "Exit",
    }
    skin.help(commands)
    while True:
        try:
            line = skin.get_input(pt_session, project_name="orcarouter")
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line.strip().lower() in {"quit", "exit", "q"}:
            break
        try:
            cli.main(
                args=line.split(),
                prog_name="cli-anything-orcarouter",
                standalone_mode=False,
            )
        except SystemExit:
            pass
        except Exception as exc:  # pragma: no cover - interactive
            click.echo(f"Error: {exc}", err=True)
    skin.print_goodbye()


def main() -> None:
    cli(obj={})


if __name__ == "__main__":
    main()
