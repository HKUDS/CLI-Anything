"""cli-anything harness for the Mailchimp Marketing API v3.0."""

from __future__ import annotations

import click

import cli_anything.mailchimp.utils.output as _output_mod
from cli_anything.mailchimp.commands import ALL_GROUPS


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, default=False, help="Output as JSON.")
@click.version_option("0.1.0", prog_name="cli-anything-mailchimp")
@click.pass_context
def cli(ctx: click.Context, use_json: bool) -> None:
    """cli-anything harness for the Mailchimp Marketing API v3.0.

    Set MAILCHIMP_API_KEY before use:

        export MAILCHIMP_API_KEY=<your-key>-<dc>

    Run without arguments to enter the interactive REPL.
    """
    ctx.ensure_object(dict)
    _output_mod.USE_JSON = use_json
    if ctx.invoked_subcommand is None:
        _start_repl()


# Register all generated resource groups
for _group in ALL_GROUPS:
    cli.add_command(_group)


def main() -> None:
    """Entry point for the Click CLI."""
    cli()


def _start_repl() -> None:
    """Interactive REPL using prompt_toolkit."""
    from cli_anything.mailchimp.utils.repl_skin import ReplSkin
    import shlex

    skin = ReplSkin("mailchimp", version="0.1.0")
    skin.print_banner()

    pt_session = skin.create_prompt_session()

    while True:
        try:
            raw = skin.get_input(pt_session)
        except (KeyboardInterrupt, EOFError):
            skin.print_goodbye()
            break

        line = raw.strip()
        if not line:
            continue
        if line in ("quit", "exit", "q"):
            skin.print_goodbye()
            break
        if line in ("help", "?"):
            _print_repl_help(skin)
            continue

        try:
            args = shlex.split(line)
        except ValueError as e:
            skin.error(f"Parse error: {e}")
            continue

        try:
            cli.main(args=args, standalone_mode=False)
        except SystemExit:
            pass
        except click.UsageError as e:
            skin.error(str(e))
        except Exception as e:
            skin.error(str(e))


def _print_repl_help(skin: object) -> None:
    from cli_anything.mailchimp.commands import ALL_GROUPS

    commands = {g.name: (g.help or "").split("\n")[0] for g in ALL_GROUPS}
    commands["--help"] = "Show help for any command"
    commands["quit"] = "Exit the REPL"
    skin.help(commands)  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()
