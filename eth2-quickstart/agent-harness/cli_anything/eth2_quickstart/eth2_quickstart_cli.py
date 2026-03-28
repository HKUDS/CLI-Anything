"""cli-anything-eth2-quickstart CLI."""

from __future__ import annotations

import json
import shlex
import sys

import click

from cli_anything.eth2_quickstart import __version__
from cli_anything.eth2_quickstart.core.install import install_clients, setup_node
from cli_anything.eth2_quickstart.core.rpc import start_rpc
from cli_anything.eth2_quickstart.core.status import health_check, status
from cli_anything.eth2_quickstart.core.validator import configure_validator
from cli_anything.eth2_quickstart.utils.eth2qs_backend import Eth2QuickStartBackend

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


def emit(data, as_json: bool) -> None:
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
        return

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                click.echo(f"{key}: {json.dumps(value, default=str)}")
            else:
                click.echo(f"{key}: {value}")
        return

    click.echo(str(data))


def backend_from_context(ctx: click.Context) -> Eth2QuickStartBackend:
    return Eth2QuickStartBackend(ctx.obj["repo_root"])


def fail(message: str, as_json: bool) -> None:
    if as_json:
        click.echo(json.dumps({"error": message}))
    else:
        click.echo(message)
    raise click.exceptions.Exit(1)


def require_confirm(ctx: click.Context, confirm: bool = False) -> None:
    if not (ctx.obj.get("confirm", False) or confirm):
        fail("This command requires --confirm", ctx.obj["as_json"])


def handle_backend_result(result: dict, as_json: bool) -> None:
    if result.get("ok"):
        emit(result, as_json)
        return

    payload = {
        "error": "Command failed",
        "result": result,
    }
    if as_json:
        click.echo(json.dumps(payload, indent=2))
    else:
        click.echo(f"ERROR {result.get('stderr') or result.get('stdout')}")
    raise click.exceptions.Exit(1)


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.option("--repo-root", default=None, help="Path to an eth2-quickstart checkout")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON")
@click.option("--confirm", is_flag=True, default=False, help="Confirm mutating operations")
@click.pass_context
def cli(ctx: click.Context, repo_root, as_json, confirm):
    """CLI harness for eth2-quickstart."""
    ctx.ensure_object(dict)
    ctx.obj["repo_root"] = repo_root
    ctx.obj["as_json"] = as_json
    ctx.obj["confirm"] = confirm

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


def main():
    cli(obj={})


@cli.command(hidden=True)
@click.pass_context
def repl(ctx: click.Context):
    """Interactive REPL mode."""
    from cli_anything.eth2_quickstart.utils.repl_skin import ReplSkin

    skin = ReplSkin("eth2-quickstart", version=__version__)
    skin.print_banner()
    pt_session = skin.create_prompt_session()

    while True:
        try:
            line = skin.get_input(pt_session, project_name="repo")
        except (EOFError, KeyboardInterrupt):
            break

        line = line.strip()
        if not line:
            continue
        if line in {"exit", "quit"}:
            break
        if line == "help":
            skin.help(
                {
                    "setup-node": "Run phase1, phase2, or ensure-driven orchestration",
                    "install-clients": "Install execution, consensus, and MEV clients",
                    "start-rpc": "Install and start nginx/caddy RPC exposure",
                    "configure-validator": "Update validator metadata and return import guidance",
                    "status": "Show aggregate status",
                    "health-check": "Run doctor --json",
                }
            )
            continue

        try:
            args = shlex.split(line)
            cli.main(args=args, obj=dict(ctx.obj), standalone_mode=False)
        except click.exceptions.Exit:
            pass
        except Exception as exc:  # pragma: no cover - REPL fallback
            skin.error(str(exc))

    skin.print_goodbye()


@cli.command("setup-node")
@click.option("--phase", type=click.Choice(["auto", "phase1", "phase2"]), default="auto")
@click.option("--network", type=click.Choice(["mainnet", "holesky"]), default=None)
@click.option("--execution-client", type=str, default=None)
@click.option("--consensus-client", type=str, default=None)
@click.option("--mev", type=click.Choice(["mev-boost", "commit-boost", "none"]), default=None)
@click.option("--ethgas", is_flag=True, default=False)
@click.option("--skip-deps", is_flag=True, default=False)
@click.option("--confirm", is_flag=True, default=False, help="Confirm mutating operations")
@click.pass_context
def setup_node_cmd(
    ctx,
    phase,
    network,
    execution_client,
    consensus_client,
    mev,
    ethgas,
    skip_deps,
    confirm,
):
    """Set up a node using phase1, phase2, or ensure-driven orchestration."""
    require_confirm(ctx, confirm)
    backend = backend_from_context(ctx)
    result = setup_node(
        backend,
        phase=phase,
        network=network,
        execution_client=execution_client,
        consensus_client=consensus_client,
        mev=mev,
        ethgas=ethgas,
        skip_deps=skip_deps,
    )
    handle_backend_result(result, ctx.obj["as_json"])


@cli.command("install-clients")
@click.option("--network", type=click.Choice(["mainnet", "holesky"]), default=None)
@click.option("--execution-client", required=True, type=str)
@click.option("--consensus-client", required=True, type=str)
@click.option("--mev", type=click.Choice(["mev-boost", "commit-boost", "none"]), default="mev-boost")
@click.option("--ethgas", is_flag=True, default=False)
@click.option("--skip-deps", is_flag=True, default=False)
@click.option("--confirm", is_flag=True, default=False, help="Confirm mutating operations")
@click.pass_context
def install_clients_cmd(
    ctx,
    network,
    execution_client,
    consensus_client,
    mev,
    ethgas,
    skip_deps,
    confirm,
):
    """Install execution, consensus, and MEV clients via phase2."""
    require_confirm(ctx, confirm)
    backend = backend_from_context(ctx)
    result = install_clients(
        backend,
        network=network,
        execution_client=execution_client,
        consensus_client=consensus_client,
        mev=mev,
        ethgas=ethgas,
        skip_deps=skip_deps,
    )
    handle_backend_result(result, ctx.obj["as_json"])


@cli.command("start-rpc")
@click.option("--web-stack", type=click.Choice(["nginx", "caddy"]), default="nginx")
@click.option("--server-name", default=None, help="Public hostname for RPC exposure")
@click.option("--ssl/--no-ssl", default=False)
@click.option("--confirm", is_flag=True, default=False, help="Confirm mutating operations")
@click.pass_context
def start_rpc_cmd(ctx, web_stack, server_name, ssl, confirm):
    """Install and start RPC exposure via nginx or caddy."""
    require_confirm(ctx, confirm)
    backend = backend_from_context(ctx)
    result = start_rpc(
        backend,
        web_stack=web_stack,
        server_name=server_name,
        ssl=ssl,
    )
    handle_backend_result(result, ctx.obj["as_json"])


@cli.command("configure-validator")
@click.option("--consensus-client", required=True, type=str)
@click.option("--fee-recipient", default=None)
@click.option("--graffiti", default=None)
@click.option("--keys-dir", default=None)
@click.option("--secrets-dir", default=None)
@click.option("--wallet-password-file", default=None)
@click.pass_context
def configure_validator_cmd(
    ctx,
    consensus_client,
    fee_recipient,
    graffiti,
    keys_dir,
    secrets_dir,
    wallet_password_file,
):
    """Update validator metadata and return client-specific import guidance."""
    backend = backend_from_context(ctx)
    result = configure_validator(
        backend,
        consensus_client=consensus_client,
        fee_recipient=fee_recipient,
        graffiti=graffiti,
        keys_dir=keys_dir,
        secrets_dir=secrets_dir,
        wallet_password_file=wallet_password_file,
    )
    emit(result, ctx.obj["as_json"])


@cli.command("status")
@click.pass_context
def status_cmd(ctx):
    """Show aggregate node status."""
    backend = backend_from_context(ctx)
    result = status(backend)
    emit(result, ctx.obj["as_json"])


@cli.command("health-check")
@click.pass_context
def health_check_cmd(ctx):
    """Run the canonical doctor --json health check."""
    backend = backend_from_context(ctx)
    result = health_check(backend)
    emit(result, ctx.obj["as_json"])
