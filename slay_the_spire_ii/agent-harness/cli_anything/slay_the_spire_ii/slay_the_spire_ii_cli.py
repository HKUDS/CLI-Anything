from __future__ import annotations

import json
import shlex
import sys
from collections.abc import Callable

import click

from . import __version__
from .core import action_adapter as actions
from .core.state_adapter import normalize_state
from .utils.repl_skin import ReplSkin
from .utils.sts2_backend import ApiError, Sts2RawClient


class CliRuntime:
    def __init__(self, base_url: str, timeout: float):
        self.base_url = base_url
        self.timeout = timeout
        self.client = Sts2RawClient(base_url=base_url, timeout=timeout)


@click.group(invoke_without_command=True)
@click.option("--base-url", default="http://localhost:15526", show_default=True, help="Local bridge API base URL")
@click.option("--timeout", type=float, default=10.0, show_default=True, help="HTTP timeout in seconds")
@click.pass_context
def cli(ctx: click.Context, base_url: str, timeout: float) -> None:
    """CLI adapter for controlling the real STS2 game via the local bridge plugin.

    Run without a subcommand to enter interactive REPL mode.
    """
    ctx.obj = CliRuntime(base_url=base_url, timeout=timeout)
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


def _get_runtime(ctx: click.Context) -> CliRuntime:
    runtime = ctx.obj
    if not isinstance(runtime, CliRuntime):
        raise RuntimeError("CLI runtime not initialized")
    return runtime


def _run_json(command: Callable[[], object]) -> None:
    try:
        _print_json(command())
    except (ApiError, RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc


def _run_post(client: Sts2RawClient, payload: dict[str, object]) -> None:
    action = str(payload.pop("action"))
    _run_json(lambda: client.post_action(action, **payload))


@cli.command("raw-state")
@click.pass_context
def raw_state(ctx: click.Context) -> None:
    """Print the raw bridge-plugin JSON state."""
    runtime = _get_runtime(ctx)
    _run_json(lambda: runtime.client.get_state(format="json"))


@cli.command("state")
@click.pass_context
def state(ctx: click.Context) -> None:
    """Print the normalized CLI-style state."""
    runtime = _get_runtime(ctx)
    _run_json(lambda: normalize_state(runtime.client.get_state(format="json")))


@cli.command("continue-game")
@click.pass_context
def continue_game(ctx: click.Context) -> None:
    """Continue a saved run from the main menu."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.continue_game())


@cli.command("abandon-game")
@click.pass_context
def abandon_game(ctx: click.Context) -> None:
    """Abandon the saved run from the main menu."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.abandon_game())


@cli.command("return-to-main-menu")
@click.pass_context
def return_to_main_menu(ctx: click.Context) -> None:
    """Return to the main menu from an active run."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.return_to_main_menu())


@cli.command("start-game")
@click.option("--character", default="IRONCLAD", show_default=True)
@click.option("--ascension", type=int, default=0, show_default=True)
@click.pass_context
def start_game(ctx: click.Context, character: str, ascension: int) -> None:
    """Start a new singleplayer run from the main menu."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.start_new_game(character, ascension))


@cli.command("action")
@click.argument("name")
@click.option("--kv", multiple=True, help="Extra payload in key=value form")
@click.pass_context
def action(ctx: click.Context, name: str, kv: tuple[str, ...]) -> None:
    """Send a raw action by name."""
    runtime = _get_runtime(ctx)
    _run_json(lambda: runtime.client.post_action(name, **_parse_kv_pairs(list(kv))))


@cli.command("play-card")
@click.argument("card_index", type=int)
@click.option("--target")
@click.pass_context
def play_card(ctx: click.Context, card_index: int, target: str | None) -> None:
    """Play a card by hand index."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.play_card(card_index, target=target))


@cli.command("use-potion")
@click.argument("slot", type=int)
@click.option("--target")
@click.pass_context
def use_potion(ctx: click.Context, slot: int, target: str | None) -> None:
    """Use a potion by slot index."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.use_potion(slot, target=target))


@cli.command("end-turn")
@click.pass_context
def end_turn(ctx: click.Context) -> None:
    """End turn."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.end_turn())


@cli.command("choose-map")
@click.argument("index", type=int)
@click.pass_context
def choose_map(ctx: click.Context, index: int) -> None:
    """Choose a map node by normalized index."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.choose_map_node(index))


@cli.command("claim-reward")
@click.argument("index", type=int)
@click.pass_context
def claim_reward(ctx: click.Context, index: int) -> None:
    """Claim a combat reward by index."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.claim_reward(index))


@cli.command("pick-card-reward")
@click.argument("index", type=int)
@click.pass_context
def pick_card_reward(ctx: click.Context, index: int) -> None:
    """Pick a card reward by index."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.select_card_reward(index))


@cli.command("skip-card-reward")
@click.pass_context
def skip_card_reward(ctx: click.Context) -> None:
    """Skip a card reward."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.skip_card_reward())


@cli.command("proceed")
@click.pass_context
def proceed(ctx: click.Context) -> None:
    """Proceed/leave current room when supported."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.proceed())


@cli.command("event")
@click.argument("index", type=int)
@click.pass_context
def event(ctx: click.Context, index: int) -> None:
    """Choose an event option by index."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.choose_event_option(index))


@cli.command("advance-dialogue")
@click.pass_context
def advance_dialogue(ctx: click.Context) -> None:
    """Advance ancient event dialogue."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.advance_dialogue())


@cli.command("rest")
@click.argument("index", type=int)
@click.pass_context
def rest(ctx: click.Context, index: int) -> None:
    """Choose a rest site option by index."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.choose_rest_option(index))


@cli.command("shop-buy")
@click.argument("index", type=int)
@click.pass_context
def shop_buy(ctx: click.Context, index: int) -> None:
    """Purchase a shop item by raw item index."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.shop_purchase(index))


@cli.command("select-card")
@click.argument("index", type=int)
@click.pass_context
def select_card(ctx: click.Context, index: int) -> None:
    """Select a card in an overlay by index."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.select_card(index))


@cli.command("confirm-selection")
@click.pass_context
def confirm_selection(ctx: click.Context) -> None:
    """Confirm the current card selection."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.confirm_selection())


@cli.command("cancel-selection")
@click.pass_context
def cancel_selection(ctx: click.Context) -> None:
    """Cancel/skip the current card selection."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.cancel_selection())


@cli.command("combat-select-card")
@click.argument("card_index", type=int)
@click.pass_context
def combat_select_card(ctx: click.Context, card_index: int) -> None:
    """Select a combat hand card during hand_select."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.combat_select_card(card_index))


@cli.command("combat-confirm-selection")
@click.pass_context
def combat_confirm_selection(ctx: click.Context) -> None:
    """Confirm an in-combat card selection."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.combat_confirm_selection())


@cli.command("select-relic")
@click.argument("index", type=int)
@click.pass_context
def select_relic(ctx: click.Context, index: int) -> None:
    """Select a relic by index."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.select_relic(index))


@cli.command("skip-relic-selection")
@click.pass_context
def skip_relic_selection(ctx: click.Context) -> None:
    """Skip relic selection."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.skip_relic_selection())


@cli.command("claim-treasure-relic")
@click.argument("index", type=int)
@click.pass_context
def claim_treasure_relic(ctx: click.Context, index: int) -> None:
    """Claim a treasure room relic by index."""
    runtime = _get_runtime(ctx)
    _run_post(runtime.client, actions.claim_treasure_relic(index))


@cli.command()
@click.pass_context
def repl(ctx: click.Context) -> None:
    """Start an interactive sts2 shell."""
    runtime = _get_runtime(ctx)
    skin = ReplSkin("slay_the_spire_ii", version=__version__)
    skin.print_banner()
    skin.hint("Type a command such as `state` or `play-card 0 --target NIBBIT_0`.")
    skin.hint("Type `help` to show shortcuts. Type `quit` or `exit` to leave.")
    print()

    pt_session = skin.create_prompt_session()

    while True:
        try:
            line = skin.get_input(pt_session, context=runtime.base_url)
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            return

        if not line:
            continue

        lowered = line.lower()
        if lowered in {"quit", "exit"}:
            skin.print_goodbye()
            return
        if lowered == "help":
            skin.help(_repl_commands())
            continue

        try:
            argv = shlex.split(line)
        except ValueError as exc:
            skin.warning(str(exc))
            continue

        if argv and argv[0] == "repl":
            skin.warning("Already in REPL. Run a command directly instead.")
            continue

        try:
            cli.main(
                args=["--base-url", runtime.base_url, "--timeout", str(runtime.timeout), *argv],
                prog_name="cli-anything-sts2",
                standalone_mode=False,
            )
        except click.ClickException as exc:
            skin.error(exc.format_message())
        except click.exceptions.Exit as exc:
            if exc.exit_code not in (None, 0):
                skin.error(f"Command exited with status {exc.exit_code}")
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
            if code not in (None, 0):
                skin.error(f"Command exited with status {code}")
        except Exception as exc:
            skin.error(str(exc))


def _repl_commands() -> dict[str, str]:
    commands = {name: cmd.short_help or "" for name, cmd in cli.commands.items() if name != "repl"}
    commands["help"] = "Show this help"
    commands["quit"] = "Exit REPL"
    return commands


def _parse_kv_pairs(entries: list[str]) -> dict[str, object]:
    result: dict[str, object] = {}
    for entry in entries:
        if "=" not in entry:
            raise ValueError(f"Expected key=value, got: {entry}")
        key, raw_value = entry.split("=", 1)
        result[key] = _coerce_value(raw_value)
    return result


def _coerce_value(raw: str) -> object:
    if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
        return int(raw)
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    return raw


def _print_json(value: object) -> None:
    json.dump(value, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    try:
        cli.main(args=argv, prog_name="cli-anything-sts2", standalone_mode=False)
        return 0
    except click.ClickException as exc:
        exc.show(file=sys.stderr)
        return exc.exit_code
    except click.exceptions.Exit as exc:
        return exc.exit_code
    except click.Abort:
        click.echo("Aborted!", err=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
