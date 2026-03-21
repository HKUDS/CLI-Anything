#!/usr/bin/env python3
import sys, os, json, shlex, click
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cli_anything.git.core.session import Session

_session = None
_json_output = False
_repl_mode = False


def get_session():
    global _session
    if _session is None:
        _session = Session()
    return _session


def output(data, message=""):
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        if isinstance(data, dict):
            for k, v in data.items():
                click.echo(f"  {k}: {v}")
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    click.echo(f"  [{i}]")
                    for k, v in item.items():
                        click.echo(f"    {k}: {v}")
                else:
                    click.echo(f"  - {item}")
        else:
            click.echo(str(data))


def handle_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
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
@click.option("--json", "use_json", is_flag=True)
@click.pass_context
def cli(ctx, use_json):
    global _json_output
    _json_output = use_json
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


from cli_anything.git.core.repo import (
    status as _st,
    log as _log,
    diff as _diff,
    branches as _br,
    checkout as _co,
    add as _add,
    commit as _ci,
    push as _push,
    pull as _pull,
    stash_save as _ss,
    stash_list as _sl,
    stash_pop as _sp,
    remotes as _rem,
    tags as _tags,
)


@cli.command("status")
@handle_error
def status_cmd():
    output(_st())


@cli.command("log")
@click.option("--limit", "-n", type=int, default=10)
@handle_error
def log_cmd(limit):
    output(_log(limit))


@cli.command("diff")
@handle_error
def diff_cmd():
    output(_diff())


@cli.command("branches")
@handle_error
def branches_cmd():
    output(_br())


@cli.command("checkout")
@click.argument("branch")
@handle_error
def checkout_cmd(branch):
    output(_co(branch), "Checking out branch...")


@cli.command("add")
@click.argument("files", nargs=-1, required=True)
@handle_error
def add_cmd(files):
    output(_add(list(files)), "Adding files...")


@cli.command("commit")
@click.option("--message", "-m", required=True)
@handle_error
def commit_cmd(message):
    output(_ci(message), "Committing...")


@cli.command("push")
@handle_error
def push_cmd():
    output(_push(), "Pushing...")


@cli.command("pull")
@handle_error
def pull_cmd():
    output(_pull(), "Pulling...")


@cli.command("stash")
@click.argument("action", default="save")
@handle_error
def stash_cmd(action):
    if action == "save":
        output(_ss(), "Stashing...")
    elif action == "list":
        output(_sl())
    elif action == "pop":
        output(_sp(), "Popping stash...")
    else:
        click.echo(f"Unknown stash action: {action}")


@cli.command("remotes")
@handle_error
def remotes_cmd():
    output(_rem())


@cli.command("tags")
@handle_error
def tags_cmd():
    output(_tags())


@cli.command()
@handle_error
def repl():
    from cli_anything.git.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True
    skin = ReplSkin("git", version="1.0.0")
    skin.print_banner()
    pt_session = skin.create_prompt_session()
    while True:
        try:
            line = skin.get_input(pt_session)
            if not line:
                continue
            if line.lower() in ("quit", "exit", "q"):
                skin.print_goodbye()
                break
            if line.lower() == "help":
                skin.help({})
                continue
            try:
                args = shlex.split(line)
            except:
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


def main():
    cli()


if __name__ == "__main__":
    main()
