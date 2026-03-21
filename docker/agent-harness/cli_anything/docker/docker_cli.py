#!/usr/bin/env python3
import sys, os, json, shlex, click
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cli_anything.docker.core.session import Session

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


from cli_anything.docker.core.container import (
    ps as _ps,
    run_image as _run,
    stop as _stop,
    logs as _logs,
    exec_cmd as _exec,
    images as _imgs,
    pull as _pull,
    build as _build,
    rm as _rm,
    volumes as _vols,
    networks as _nets,
    info as _info,
)


@cli.command("ps")
@handle_error
def ps_cmd():
    output(_ps())


@cli.command("run")
@click.argument("image")
@click.option("--name", default=None)
@handle_error
def run_cmd(image, name):
    output(_run(image, name=name), "Running container...")


@cli.command("stop")
@click.argument("container_id")
@handle_error
def stop_cmd(container_id):
    output(_stop(container_id), "Stopping...")


@cli.command("logs")
@click.argument("container_id")
@click.option("--tail", "-n", type=int, default=50)
@handle_error
def logs_cmd(container_id, tail):
    output(_logs(container_id, tail=tail))


@cli.command("exec")
@click.argument("container_id")
@click.option("--cmd", "-c", required=True)
@handle_error
def exec_cmd(container_id, cmd):
    output(_exec(container_id, cmd))


@cli.command("images")
@handle_error
def images_cmd():
    output(_imgs())


@cli.command("pull")
@click.argument("name")
@handle_error
def pull_cmd(name):
    output(_pull(name), "Pulling image...")


@cli.command("build")
@click.option("--path", "-p", required=True)
@click.option("--tag", "-t", required=True)
@handle_error
def build_cmd(path, tag):
    output(_build(path, tag), "Building image...")


@cli.command("rm")
@click.argument("container_id")
@handle_error
def rm_cmd(container_id):
    output(_rm(container_id), "Removing...")


@cli.command("volumes")
@handle_error
def volumes_cmd():
    output(_vols())


@cli.command("networks")
@handle_error
def networks_cmd():
    output(_nets())


@cli.command("info")
@handle_error
def info_cmd():
    output(_info())


@cli.command()
@handle_error
def repl():
    from cli_anything.docker.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True
    skin = ReplSkin("docker", version="1.0.0")
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
