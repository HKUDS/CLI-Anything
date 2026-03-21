#!/usr/bin/env python3
"""GPG CLI — GnuPG encryption, signing, and key management."""

import sys
import os
import json
import shlex
import click
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cli_anything.gpg.core.session import Session
from cli_anything.gpg.core import keys as gpg_keys
from cli_anything.gpg.core import crypto as gpg_crypto

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


# ── Key group ─────────────────────────────────────────────────────────


@cli.group()
def key():
    """Key management commands."""
    pass


@key.command("list")
@click.option("--secret", is_flag=True, help="List secret keys")
@handle_error
def key_list(secret):
    """List keys."""
    result = gpg_keys.key_list(secret=secret)
    label = "Secret keys" if secret else "Public keys"
    output(result, f"{label}:")


@key.command("generate")
@click.argument("name")
@click.argument("email")
@click.option(
    "--type",
    "key_type",
    default="RSA",
    type=click.Choice(["RSA", "ED25519"]),
    help="Key type",
)
@click.option("--length", default=2048, help="Key length (RSA only)")
@click.option("--passphrase", default="", help="Passphrase (empty for none)")
@handle_error
def key_generate(name, email, key_type, length, passphrase):
    """Generate new key pair."""
    result = gpg_keys.key_generate(
        name, email, key_type=key_type, key_length=length, passphrase=passphrase
    )
    output(result, "Key generated:")


@key.command("export")
@click.argument("key_id")
@handle_error
def key_export(key_id):
    """Export public key."""
    result = gpg_keys.key_export(key_id)
    click.echo(result)


@key.command("export-secret")
@click.argument("key_id")
@handle_error
def key_export_secret(key_id):
    """Export secret key."""
    result = gpg_keys.key_export_secret(key_id)
    click.echo(result)


@key.command("import")
@click.argument("file")
@handle_error
def key_import(file):
    """Import a key from file."""
    result = gpg_keys.key_import(file)
    output(result, "Key imported:")


@key.command("delete")
@click.argument("key_id")
@click.option("--secret", is_flag=True, help="Also delete secret key")
@handle_error
def key_delete(key_id, secret):
    """Delete a key."""
    result = gpg_keys.key_delete(key_id, secret=secret)
    output(result)


@key.command("trust")
@click.argument("key_id")
@click.option(
    "--level",
    default=5,
    type=click.IntRange(1, 5),
    help="Trust level (1=unknown, 2=never, 3=marginal, 4=full, 5=ultimate)",
)
@handle_error
def key_trust(key_id, level):
    """Set trust level for a key."""
    result = gpg_keys.key_trust(key_id, level=level)
    output(result)


@key.command("fingerprint")
@click.argument("key_id")
@handle_error
def key_fingerprint(key_id):
    """Show key fingerprint."""
    result = gpg_keys.key_fingerprint(key_id)
    click.echo(result)


# ── Encrypt / Decrypt ─────────────────────────────────────────────────


@cli.command()
@click.argument("file")
@click.option("--recipient", "-r", required=True, help="Recipient key ID")
@click.option("--output", "-o", default=None, help="Output file")
@handle_error
def encrypt(file, recipient, output):
    """Encrypt a file."""
    result = gpg_crypto.encrypt(file, recipient, output=output)
    output(result, "Encrypted:")


@cli.command()
@click.argument("file")
@click.option("--output", "-o", default=None, help="Output file")
@handle_error
def decrypt(file, output):
    """Decrypt a file."""
    result = gpg_crypto.decrypt(file, output=output)
    output(result, "Decrypted:")


# ── Sign / Verify ─────────────────────────────────────────────────────


@cli.command()
@click.argument("file")
@click.option("--key", "-k", "key_id", default=None, help="Signing key ID")
@click.option("--output", "-o", default=None, help="Output file")
@handle_error
def sign(file, key_id, output):
    """Sign a file (detached)."""
    result = gpg_crypto.sign(file, key_id=key_id, output=output)
    output(result, "Signed:")


@cli.command()
@click.argument("file")
@click.option("--sig-file", default=None, help="Signature file (default: <file>.sig)")
@handle_error
def verify(file, sig_file):
    """Verify a signature."""
    result = gpg_crypto.verify(file, sig_file=sig_file)
    output(result)


@cli.command("clearsign")
@click.argument("file")
@click.option("--key", "-k", "key_id", default=None, help="Signing key ID")
@click.option("--output", "-o", default=None, help="Output file")
@handle_error
def clearsign(file, key_id, output):
    """Create cleartext signature."""
    result = gpg_crypto.clearsign(file, key_id=key_id, output=output)
    output(result, "Clearsigned:")


@cli.command("detach-sign")
@click.argument("file")
@click.option("--key", "-k", "key_id", default=None, help="Signing key ID")
@click.option("--output", "-o", default=None, help="Output file")
@handle_error
def detach_sign(file, key_id, output):
    """Create detached signature."""
    result = gpg_crypto.detach_sign(file, key_id=key_id, output=output)
    output(result, "Detached signature created:")


# ── Session commands ──────────────────────────────────────────────────


@cli.command()
@handle_error
def status():
    """Show session status."""
    s = get_session()
    output(s.status())


# ── REPL ──────────────────────────────────────────────────────────────


@cli.command()
@handle_error
def repl():
    """Start interactive REPL."""
    from cli_anything.gpg.utils.repl_skin import ReplSkin

    global _repl_mode
    _repl_mode = True
    skin = ReplSkin("gpg", version="1.0.0")
    skin.print_banner()

    commands = {
        "key list": "List public keys (--secret for secret keys)",
        "key generate <name> <email>": "Generate new key pair",
        "key export <key-id>": "Export public key",
        "key export-secret <key-id>": "Export secret key",
        "key import <file>": "Import a key",
        "key delete <key-id>": "Delete a key",
        "key trust <key-id>": "Set trust level",
        "key fingerprint <key-id>": "Show key fingerprint",
        "encrypt <file> -r <key-id>": "Encrypt a file",
        "decrypt <file>": "Decrypt a file",
        "sign <file> -k <key-id>": "Sign a file",
        "verify <file>": "Verify a signature",
        "clearsign <file>": "Create cleartext signature",
        "detach-sign <file>": "Create detached signature",
        "status": "Show session status",
        "help": "Show this help",
        "quit": "Exit the REPL",
    }

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
                skin.help(commands)
                continue
            try:
                args = shlex.split(line)
            except Exception:
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
