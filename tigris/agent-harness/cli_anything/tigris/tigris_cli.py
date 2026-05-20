"""Tigris CLI-Anything harness -- Click CLI + REPL.

Tigris is a globally distributed, S3-compatible object storage service
with no egress fees. https://www.tigrisdata.com
"""

import shlex

import click

from .utils.tigris_backend import TigrisBackend, DEFAULT_ENDPOINT
from .utils.repl_skin import ReplSkin
from .core.bucket import bucket_group
from .core.object import object_group
from .core.presign import presign_group


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, default=False,
              help="Output in JSON format")
@click.option("--endpoint", default=DEFAULT_ENDPOINT,
              help=f"Tigris endpoint URL (default: {DEFAULT_ENDPOINT})")
@click.option("--access-key", default=None,
              help="Access key (else read from TIGRIS_STORAGE_ACCESS_KEY_ID / AWS_ACCESS_KEY_ID)")
@click.option("--secret-key", default=None,
              help="Secret key (else read from TIGRIS_STORAGE_SECRET_ACCESS_KEY / AWS_SECRET_ACCESS_KEY)")
@click.pass_context
def cli(ctx, use_json, endpoint, access_key, secret_key):
    """CLI-Anything harness for Tigris S3-compatible object storage."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = use_json
    ctx.obj["backend"] = TigrisBackend(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
    )
    ctx.obj["skin"] = ReplSkin("tigris", version="1.0.0")

    if ctx.invoked_subcommand is None:
        _run_repl(ctx)


cli.add_command(bucket_group)
cli.add_command(object_group)
cli.add_command(presign_group)


# ── REPL Commands Map (for help display) ─────────────────────────────

_REPL_COMMANDS = {
    "bucket list":                                  "List all buckets",
    "bucket create --name NAME":                    "Create a new bucket",
    "bucket delete --name NAME":                    "Delete an empty bucket",
    "bucket info NAME":                             "Get bucket info",
    "object list --bucket B [--prefix P]":          "List objects in a bucket",
    "object put --bucket B --key K --file F":       "Upload a file as an object",
    "object put --bucket B --key K --text T":       "Upload inline text as an object",
    "object get --bucket B --key K [--output F]":   "Download an object",
    "object delete --bucket B --key K":             "Delete an object",
    "object info --bucket B --key K":               "Get object metadata",
    "object cp SRC DST":                            "Copy (server-side or local↔tigris)",
    "presign get --bucket B --key K":               "Presigned URL for download",
    "presign put --bucket B --key K":               "Presigned URL for upload",
    "help":                                         "Show this help",
    "quit / exit":                                  "Exit the REPL",
}


def _run_repl(ctx):
    """Launch the interactive REPL."""
    skin: ReplSkin = ctx.obj["skin"]
    skin.print_banner()

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
