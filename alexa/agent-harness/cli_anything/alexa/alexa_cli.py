#!/usr/bin/env python3
"""Alexa CLI — control Amazon Echo devices from the command line.

Wraps Amazon's Alexa web API through alexapy (the library behind Home
Assistant's Alexa Media Player). Make Echos speak, announce, run routines,
play music, set volume, and run any voice command as text.

Usage:
    cli-anything-alexa auth login --email you@example.com
    cli-anything-alexa device list
    cli-anything-alexa speak "Kitchen" "Dinner is ready"
    cli-anything-alexa command "Kitchen" "turn off the living room lights"
    cli-anything-alexa --json device list
    cli-anything-alexa               # interactive REPL
"""

from __future__ import annotations

import json
import shlex
import sys
from typing import Any

import click

from cli_anything.alexa import __version__
from cli_anything.alexa.core import actions as act
from cli_anything.alexa.core import devices as dev
from cli_anything.alexa.core import smarthome as sh
from cli_anything.alexa.utils import alexa_backend as backend

_json_output = False
_dry_run = False


# ── Output helpers ───────────────────────────────────────────────────

def _domain_warning() -> str | None:
    try:
        account = backend.load_account()
    except Exception:
        return None
    return backend.domain_warning(account) if account else None


def output(data: Any, message: str = "") -> None:
    warning = _domain_warning()
    if _json_output:
        if warning and isinstance(data, dict) and "warning" not in data:
            data = {**data, "warning": warning}
        elif warning:
            # Keep list-shaped JSON stable for agents; surface the warning on stderr.
            click.echo(f"Warning: {warning}", err=True)
        click.echo(json.dumps(data, indent=2, default=str))
        return
    if warning:
        click.echo(f"Warning: {warning}", err=True)
    if message:
        click.echo(message)
    if isinstance(data, list):
        for item in data:
            click.echo(_line(item) if isinstance(item, dict) else str(item))
    elif isinstance(data, dict):
        for k, v in data.items():
            click.echo(f"  {k}: {v}")
    elif data is not None:
        click.echo(str(data))


def _line(d: dict) -> str:
    if "serial" in d and "family" in d:
        state = "online " if d.get("online") else "offline"
        return f"  {state}  {d['name']:<28} {d['family']:<10} {d['serial']}"
    if "appliance_id" in d:
        return f"  {d['name']:<28} {','.join(d.get('types', [])):<20} {d.get('entity_id', '')}"
    return "  " + ", ".join(f"{k}={v}" for k, v in d.items())


def fail(message: str, code: str = "error") -> None:
    warning = _domain_warning()  # often the cause of the failure, so always surface it
    if _json_output:
        payload = {"ok": False, "error": code, "message": message}
        if warning:
            payload["warning"] = warning
        click.echo(json.dumps(payload, indent=2))
    else:
        if warning:
            click.echo(f"Warning: {warning}", err=True)
        click.echo(f"Error: {message}", err=True)
    raise SystemExit(1)


def _guard(fn):
    """Turn backend/validation exceptions into clean, agent-readable errors."""
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except backend.NotLoggedIn as exc:
            fail(str(exc), "not_logged_in")
        except dev.AmbiguousDevice as exc:
            fail(str(exc), "ambiguous_device")
        except dev.DeviceNotFound as exc:
            fail(str(exc), "device_not_found")
        except act.ActionError as exc:
            fail(str(exc), "invalid_input")
        except TimeoutError as exc:
            fail(str(exc), "timeout")
        except click.ClickException:
            raise
        except RuntimeError as exc:
            fail(str(exc), "runtime_error")
        except Exception as exc:  # alexapy / aiohttp transport and API errors
            fail(f"{type(exc).__name__}: {exc}", "backend_error")
    return wrapper


def _devices(refresh: bool = True) -> list[dict[str, Any]]:
    """Normalized devices: live from Amazon, or the cache in dry-run mode."""
    if _dry_run or not refresh:
        cached = backend.cached_devices()
        if cached is not None:  # an empty cached list is a valid answer
            return cached
        why = "Dry run" if _dry_run else "--cached"
        raise dev.DeviceNotFound(f"{why} needs a cached device list. Run `device list` once while logged in.")
    devices = [dev.normalize(d) for d in backend.fetch_devices()]
    backend.cache_devices(devices)
    return devices


def _resolve(name: str, allow_groups: bool = False) -> dict[str, Any]:
    """Resolve an action target.

    Speech and voice commands need a real speaker; multi-room speaker groups
    only accept media commands (music, playback, volume), so they are
    targetable only when ``allow_groups`` is set. Alexa apps are never targets.
    """
    candidates = [d for d in dev.filter_devices(_devices()) if allow_groups or d.get("is_speaker")]
    return dev.resolve(candidates, name)


def _send(action: dict[str, Any], message: str) -> None:
    summary = act.describe(action)
    if _dry_run:
        output({"ok": True, "dry_run": True, "action": summary}, f"[dry-run] {message}")
        return
    result = backend.execute(action)
    output({"ok": True, "action": summary, **result}, message)


# ── Root group ───────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON.")
@click.option("--dry-run", is_flag=True, help="Validate and show the action without contacting Amazon.")
@click.version_option(__version__, prog_name="cli-anything-alexa")
@click.pass_context
def cli(ctx, use_json, dry_run):
    """Alexa CLI — control Amazon Echo devices from the command line.

    Run without a subcommand to enter interactive REPL mode.
    """
    global _json_output, _dry_run
    _json_output = use_json
    _dry_run = dry_run
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── auth ─────────────────────────────────────────────────────────────

@cli.group()
def auth():
    """Amazon account login, status and logout."""


def _check_domain(ctx, param, value):
    value = (value or "").strip().lower()
    if not backend.valid_domain(value):
        raise click.BadParameter(f"'{value}' is not an Amazon domain (e.g. amazon.com, amazon.co.uk, amazon.de).")
    return value


@auth.command("login")
@click.option("--email", required=True, help="Amazon account email.")
@click.option("--domain", default="amazon.com", show_default=True, callback=_check_domain,
              help="Amazon domain of your account, e.g. amazon.co.uk, amazon.de, amazon.in.")
@click.option("--port", type=click.IntRange(1, 65535), default=None,
              help="Local port for the sign-in page (default: a free port).")
@click.option("--timeout", default=600, show_default=True, help="Seconds to wait for sign-in.")
@_guard
def auth_login(email, domain, port, timeout):
    """Sign in through a local proxy to Amazon's real login page.

    Opens http://127.0.0.1:PORT in your browser; complete Amazon sign-in there
    (captcha and 2FA work). Your password is never stored.
    """
    def show(url: str) -> None:
        click.echo(f"Open this URL in your browser and sign in to Amazon:\n\n  {url}\n", err=True)
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass
        click.echo("Waiting for sign-in to finish...", err=True)

    if _dry_run:
        output({"ok": True, "dry_run": True, "would": "start local sign-in page and store tokens",
                "email": email, "domain": domain, "port": port or "auto",
                "locale": backend.locale_for(domain)}, "[dry-run] Would start Amazon sign-in.")
        return
    result = backend.login(email, domain, port, timeout, on_url=show)
    output({"ok": True, **result}, f"Logged in as {email} ({domain}), speech language {result['locale']}.")


@auth.command("status")
@click.option("--verify", is_flag=True, help="Also check the session against Amazon.")
@_guard
def auth_status(verify):
    """Show the stored account (and optionally verify it)."""
    account = backend.load_account()
    if not account:
        output({"logged_in": False}, "Not logged in. Run: auth login --email you@example.com")
        return
    data = {"logged_in": True, "email": account["email"], "domain": account["domain"],
            "locale": account.get("locale"), "customer_id": account.get("customer_id"),
            "config_dir": str(backend.config_dir())}
    if verify and _dry_run:
        data["verify"] = "skipped (dry run does not contact Amazon)"
    elif verify:
        data.update(backend.verify())
    output(data)


@auth.command("logout")
@_guard
def auth_logout():
    """Delete stored tokens and cookies on this machine."""
    if _dry_run:
        output({"ok": True, "dry_run": True, "would_remove": backend.load_account() is not None},
               "[dry-run] Would delete stored tokens and cookies.")
        return
    removed = backend.delete_account()
    output({"ok": True, "removed": removed},
           "Logged out." if removed else "Nothing to remove.")


@auth.command("locale")
@click.argument("locale")
@_guard
def auth_locale(locale):
    """Set the language Alexa uses for speak/command, e.g. en-GB, de-DE."""
    account = backend.load_account()
    if not account:
        raise backend.NotLoggedIn("Not logged in. Run: auth login --email you@example.com")
    if _dry_run:
        output({"ok": True, "dry_run": True, "would_set_locale": locale}, f"[dry-run] Would set locale to {locale}.")
        return
    account["locale"] = locale
    backend.save_account(account)
    output({"ok": True, "locale": locale}, f"Locale set to {locale}.")


# ── device ───────────────────────────────────────────────────────────

@cli.group()
def device():
    """List and inspect Echo devices."""


@device.command("list")
@click.option("--all", "include_all", is_flag=True, help="Include non-speaker devices (apps, groups...).")
@click.option("--cached", is_flag=True, help="Use the last fetched list instead of asking Amazon.")
@_guard
def device_list(include_all, cached):
    """List devices on the account (speakers only by default)."""
    devices = dev.filter_devices(_devices(refresh=not cached), include_all)
    if _json_output:
        output([{k: v for k, v in d.items() if k != "capabilities"} for d in devices])
    else:
        output(devices, f"{len(devices)} device(s):")


@device.command("info")
@click.argument("name")
@_guard
def device_info(name):
    """Show one device, matched by name, partial name or serial."""
    output(dev.resolve(_devices(), name))


# ── voice actions ────────────────────────────────────────────────────

@cli.command("speak")
@click.argument("device_name")
@click.argument("text")
@_guard
def speak(device_name, text):
    """Make one Echo say TEXT out loud."""
    d = _resolve(device_name)
    _send(act.speak(d, text), f"{d['name']} will say: {text}")


@cli.command("announce")
@click.argument("text")
@click.option("-d", "--device", "names", multiple=True, help="Target device (repeatable). Default: all speakers.")
@click.option("--title", default="Announcement", show_default=True, help="Title shown on screen devices.")
@_guard
def announce(text, names, title):
    """Announce TEXT (with chime) on one, several or all Echos."""
    all_devices = _devices()
    speakers = [d for d in dev.filter_devices(all_devices) if d.get("is_speaker")]
    targets = [dev.resolve(speakers, n) for n in names] if names else \
        [d for d in dev.filter_devices(all_devices) if d.get("online") and d.get("is_speaker")]
    _send(act.announce(targets, text, title), f"Announcing on {len(targets)} device(s): {text}")


@cli.command("command")
@click.argument("device_name")
@click.argument("text")
@_guard
def command(device_name, text):
    """Run TEXT as if spoken to the device, e.g. "turn off the lights"."""
    d = _resolve(device_name)
    _send(act.command(d, text), f"Sent to {d['name']}: \"{text}\"")


@cli.command("sequence")
@click.argument("device_name")
@click.argument("name", type=click.Choice(sorted(act.SEQUENCES)))
@_guard
def sequence(device_name, name):
    """Play a built-in Alexa feature (weather, joke, flash-briefing...)."""
    d = _resolve(device_name)
    _send(act.sequence(d, name), f"{d['name']}: playing {name}")


# ── routines ─────────────────────────────────────────────────────────

@cli.group()
def routine():
    """List and run Alexa routines."""


@routine.command("list")
@_guard
def routine_list():
    """List routines with their trigger phrases."""
    if _dry_run:
        output({"ok": True, "dry_run": True, "would": "fetch routines from Amazon"}, "[dry-run] Would list routines.")
        return
    items = []
    for r in backend.fetch_routines():
        phrases = []
        for t in r.get("triggers") or []:
            utt = (t.get("payload") or {}).get("utterance")
            if utt:
                phrases.append(utt)
        items.append({"name": r.get("name") or "", "status": r.get("status") or "",
                      "utterances": phrases, "automation_id": r.get("automationId") or ""})
    output(items, f"{len(items)} routine(s):")


@routine.command("run")
@click.argument("device_name")
@click.argument("utterance")
@_guard
def routine_run(device_name, utterance):
    """Run the routine triggered by UTTERANCE on a device."""
    d = _resolve(device_name)
    _send(act.routine(d, utterance), f"{d['name']}: running routine '{utterance}'")


# ── media ────────────────────────────────────────────────────────────

@cli.group()
def music():
    """Play music and control playback."""


@music.command("play")
@click.argument("device_name")
@click.argument("query")
@click.option("--provider", default="amazon", show_default=True, type=click.Choice(sorted(act.MUSIC_PROVIDERS)))
@click.option("--timer", type=int, help="Stop after N seconds.")
@_guard
def music_play(device_name, query, provider, timer):
    """Search and play QUERY (song, artist, playlist, station)."""
    d = _resolve(device_name, allow_groups=True)
    _send(act.music(d, query, provider, timer), f"{d['name']}: playing '{query}' from {provider}")


_MEDIA_COMMANDS = {"resume": "play", "pause": "pause", "next": "next", "previous": "previous", "stop": "stop"}

for _name, _op in _MEDIA_COMMANDS.items():
    def _make(name, op):
        @_guard
        def _cmd(device_name):
            d = _resolve(device_name, allow_groups=True)
            _send(act.media(d, op), f"{d['name']}: {name}")
        _cmd.__doc__ = f"{name.capitalize()} playback on a device."
        return _cmd
    music.command(_name)(click.argument("device_name")(_make(_name, _op)))


@cli.command("volume")
@click.argument("device_name")
@click.argument("level", type=click.IntRange(0, 100))
@_guard
def volume(device_name, level):
    """Set volume 0-100."""
    d = _resolve(device_name, allow_groups=True)
    _send(act.volume(d, level), f"{d['name']}: volume {level}")


# ── smart home ───────────────────────────────────────────────────────

@cli.group()
def smarthome():
    """Smart-home appliances linked to Alexa."""


@smarthome.command("list")
@_guard
def smarthome_list():
    """List lights, plugs and other appliances Alexa controls."""
    if _dry_run:
        output({"ok": True, "dry_run": True, "would": "fetch smart-home appliances from Amazon"},
               "[dry-run] Would list smart-home appliances.")
        return
    items = sh.flatten_network(backend.fetch_network())
    output(items, f"{len(items)} appliance(s):")


@smarthome.command("light")
@click.argument("entity_id")
@click.option("--on/--off", "power", default=True, help="Turn on (default) or off.")
@click.option("--brightness", type=click.IntRange(0, 100))
@click.option("--color", help="Color name, e.g. red, warm_white.")
@_guard
def smarthome_light(entity_id, power, brightness, color):
    """Switch a light by ENTITY_ID (from `smarthome list`)."""
    _send(act.light(entity_id, power, brightness, color), f"Light {entity_id}: {'on' if power else 'off'}")


# ── REPL ─────────────────────────────────────────────────────────────

@cli.command("repl")
def repl():
    """Start the interactive REPL."""
    from cli_anything.alexa.utils.repl_skin import ReplSkin

    import contextlib
    repl_json, repl_dry = _json_output, _dry_run  # keep root flags for every REPL line

    def chrome():
        """Banner/status/help text: on stderr in --json mode so stdout stays JSON."""
        return contextlib.redirect_stdout(sys.stderr) if repl_json else contextlib.nullcontext()

    skin = ReplSkin("alexa", version=__version__)
    with chrome():
        skin.print_banner()
    session = skin.create_prompt_session()
    commands = {
        "auth": "login|status|logout|locale",
        "device": "list|info",
        "speak": "<device> <text>",
        "announce": "<text> [-d device]",
        "command": "<device> <text as if spoken>",
        "sequence": "<device> weather|joke|...",
        "routine": "list|run",
        "music": "play <device> <query>|pause|resume|next|previous|stop",
        "volume": "<device> <0-100>",
        "smarthome": "list|light",
        "help": "Show this help",
        "quit": "Exit REPL",
    }
    account = backend.load_account()
    if account:
        with chrome():
            skin.success(f"Logged in as {account['email']} ({account['domain']})")
    else:
        with chrome():
            skin.info("Not logged in. Run: auth login --email you@example.com")
    while True:
        try:
            line = skin.get_input(session, context=(account or {}).get("email", ""))
        except (EOFError, KeyboardInterrupt):
            with chrome():
                skin.print_goodbye()
            break
        if not line:
            continue
        if line.lower() in ("quit", "exit", "q"):
            with chrome():
                skin.print_goodbye()
            break
        if line.lower() == "help":
            with chrome():
                skin.help(commands)
            continue
        try:
            args = shlex.split(line)
        except ValueError:
            args = line.split()
        flags = (["--json"] if repl_json else []) + (["--dry-run"] if repl_dry else [])
        try:
            cli.main(flags + args, standalone_mode=False)
        except SystemExit:
            pass
        except click.ClickException as exc:
            if repl_json:  # agents driving the REPL in --json mode get JSON errors too
                click.echo(json.dumps({"ok": False, "error": "usage_error",
                                       "message": exc.format_message()}, indent=2))
            else:
                skin.error(exc.format_message())
        account = backend.load_account()


def main() -> None:
    """Entry point; reports Click usage errors as JSON when --json is given."""
    argv = sys.argv[1:]
    try:
        cli.main(args=argv, standalone_mode=False)
    except click.ClickException as exc:
        if "--json" in argv:
            click.echo(json.dumps({"ok": False, "error": "usage_error", "message": exc.format_message()}, indent=2))
        else:
            exc.show()
        raise SystemExit(exc.exit_code)
    except click.exceptions.Abort:
        click.echo("Aborted.", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
