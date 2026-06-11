"""Tigris CLI-Anything harness — Click CLI + REPL.

Wraps the official Tigris CLI (`tigris`) so all of its primitives —
including snapshots, IAM, scoped access keys, and OAuth — are reachable
through a single agent-friendly entry point with `--json` everywhere.

Tigris is a globally distributed, S3-compatible object storage service
with no egress fees. https://www.tigrisdata.com
"""

import shlex

import click

from .utils.tigris_backend import TigrisBackend, TigrisCliError
from .utils.repl_skin import ReplSkin
from .core.auth import auth_group
from .core.bucket import bucket_group
from .core.object import object_group
from .core.presign import presign_group
from .core.snapshot import snapshot_group
from .core.access_key import access_key_group
from .core.iam import iam_group


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, default=False,
              help="Output in JSON format")
@click.option("--cli-path", default="tigris",
              help="Path to the tigris CLI binary (default: 'tigris' on PATH)")
@click.option("--access-key", default=None,
              help="Optional access key ID (exported to env for child processes)")
@click.option("--secret-key", default=None,
              help="Optional secret key (exported to env for child processes)")
@click.pass_context
def cli(ctx, use_json, cli_path, access_key, secret_key):
    """CLI-Anything harness for Tigris (S3-compatible object storage).

    Wraps the official `tigris` CLI. Install it once with
    `npm install -g @tigrisdata/cli` or `brew install tigrisdata/tap/tigris`,
    run `tigris login`, then drive everything from here.
    """
    ctx.ensure_object(dict)
    ctx.obj["json"] = use_json
    try:
        ctx.obj["backend"] = TigrisBackend(
            cli_path=cli_path,
            access_key=access_key,
            secret_key=secret_key,
        )
    except TigrisCliError as e:
        # Defer the error so `--help` still works without the binary.
        ctx.obj["backend"] = None
        ctx.obj["backend_error"] = str(e)
    ctx.obj["skin"] = ReplSkin("tigris", version="1.0.0")

    if ctx.invoked_subcommand is None:
        _run_repl(ctx)


cli.add_command(auth_group)
cli.add_command(bucket_group)
cli.add_command(object_group)
cli.add_command(presign_group)
cli.add_command(snapshot_group)
cli.add_command(access_key_group)
cli.add_command(iam_group)


# ── REPL Commands Map (for help display) ─────────────────────────────

_REPL_COMMANDS = {
    "auth login":                                       "Browser OAuth login (`tigris login`)",
    "auth logout":                                      "Log out of current session",
    "auth whoami":                                      "Print current user / org",
    "bucket list":                                      "List buckets",
    "bucket create --name NAME":                        "Create a bucket",
    "bucket delete --name NAME --yes":                  "Delete an empty bucket",
    "bucket info NAME":                                 "Get bucket info",
    "object list --bucket B [--prefix P]":              "List objects",
    "object put --bucket B --key K --file F":           "Upload a file",
    "object put --bucket B --key K --text T":           "Upload inline text",
    "object get --bucket B --key K --output F":         "Download to file",
    "object delete --bucket B --key K":                 "Delete an object",
    "object info --bucket B --key K":                   "Object metadata (stat)",
    "object cp SRC DST [-r]":                           "Copy local↔t3 or t3↔t3",
    "presign get --bucket B --key K [--expires SEC]":   "Presigned GET URL",
    "presign put --bucket B --key K [--expires SEC]":   "Presigned PUT URL",
    "snapshot list BUCKET":                             "List bucket snapshots",
    "snapshot take BUCKET [--name N]":                  "Take a point-in-time snapshot",
    "access-key list":                                  "List access keys",
    "access-key create NAME":                           "Create an access key",
    "access-key get KEY_ID":                            "Get access key details",
    "access-key delete KEY_ID --yes":                   "Delete an access key",
    "access-key assign KEY_ID --bucket B --role R":     "Scope a key to a bucket/role",
    "access-key rotate KEY_ID --yes":                   "Rotate a key's secret",
    "iam policy list / create NAME --document F":       "Manage IAM policies",
    "iam user list / invite EMAIL [--role R]":          "Manage org users",
    "help":                                             "Show this help",
    "quit / exit":                                      "Exit the REPL",
}


def _run_repl(ctx):
    """Launch the interactive REPL."""
    skin: ReplSkin = ctx.obj["skin"]
    skin.print_banner()

    if ctx.obj.get("backend") is None:
        skin.error(ctx.obj.get("backend_error", "tigris CLI not available"))
        return

    session = skin.create_prompt_session()

    while True:
        try:
            user_input = skin.get_input(session, context="tigris")
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

        if not user_input:
            continue

        cmd = user_input.strip().lower()

        if cmd in ("quit", "exit", "q"):
            skin.print_goodbye()
            break

        if cmd in ("help", "h", "?"):
            skin.help(_REPL_COMMANDS)
            continue

        try:
            args = shlex.split(user_input)
        except ValueError as e:
            skin.error(f"Parse error: {e}")
            continue

        try:
            cli.main(args=args, obj=ctx.obj, standalone_mode=False)
        except SystemExit:
            pass
        except click.exceptions.UsageError as e:
            skin.error(str(e))
        except Exception as e:
            skin.error(f"Error: {e}")


def main():
    """Entry point."""
    cli(auto_envvar_prefix="TIGRIS_CLI")


if __name__ == "__main__":
    main()
