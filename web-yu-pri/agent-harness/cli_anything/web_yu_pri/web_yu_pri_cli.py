#!/usr/bin/env python3
"""CLI harness for Japan Post Web Yu-pri."""

from __future__ import annotations

import json
import shlex
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import click

from cli_anything.web_yu_pri import __version__
from cli_anything.web_yu_pri.core.browser import (
    CONTENTS_URL,
    LOGIN_URL,
    build_dry_run,
    capture_snapshot,
    doctor as browser_doctor,
    fill_contents,
    inspect_url,
    open_login,
    selector_report,
)
from cli_anything.web_yu_pri.core.items import build_contents_plan, load_items

_json_output = False
_profile_dir: str | None = None


def emit(data: Any, message: str | None = None) -> None:
    if _json_output:
        click.echo(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        if isinstance(data, dict):
            _print_dict(data)
        elif isinstance(data, list):
            _print_list(data)
        elif data is not None:
            click.echo(str(data))


def fail(message: str, error_type: str = "runtime_error") -> None:
    if _json_output:
        click.echo(json.dumps({"error": message, "type": error_type}, ensure_ascii=False))
    else:
        click.echo(f"Error: {message}", err=True)
    raise SystemExit(1)


def _print_dict(data: dict[str, Any], indent: int = 0) -> None:
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


def _print_list(values: list[Any], indent: int = 0) -> None:
    prefix = "  " * indent
    for index, value in enumerate(values):
        if isinstance(value, dict):
            click.echo(f"{prefix}[{index}]")
            _print_dict(value, indent + 1)
        else:
            click.echo(f"{prefix}- {value}")


def _load_plan(
    items_file: str,
    default_country: str | None,
    total_value: int | None,
    value_mode: str,
) -> tuple[list[Any], dict[str, Any]]:
    path = Path(items_file).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"items file not found: {items_file}")
    items = load_items(path, default_country=default_country)
    plan = build_contents_plan(items, total_value=total_value, value_mode=value_mode)
    return items, plan


@click.group(invoke_without_command=True)
@click.option("--json", "json_output", is_flag=True, help="Output machine-readable JSON.")
@click.option(
    "--profile-dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=str),
    default=None,
    help="Persistent browser profile directory. Defaults to ~/.cli-anything-web-yu-pri/profile.",
)
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx: click.Context, json_output: bool, profile_dir: str | None) -> None:
    """Japan Post Web Yu-pri browser automation harness.

    Run with --json for agent-safe output. Commands that touch the real site use a
    persistent local browser profile and never store account passwords.
    """

    global _json_output, _profile_dir
    _json_output = json_output
    _profile_dir = profile_dir
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command("doctor")
def doctor_cmd() -> None:
    """Check local runtime and profile paths."""

    try:
        emit(browser_doctor(profile_dir=_profile_dir))
    except Exception as exc:
        fail(str(exc))


@cli.command("selectors")
def selectors_cmd() -> None:
    """Print the currently known Web Yu-pri selector map."""

    emit(selector_report())


@cli.command("plan")
@click.argument("items_file", type=str)
@click.option("--country-default", default=None, help="Default ISO country code for rows without one.")
@click.option("--total-value", type=int, default=None, help="Override the declared total value in yen.")
@click.option(
    "--value-mode",
    type=click.Choice(["line", "unit"]),
    default="line",
    show_default=True,
    help="Treat item value as a line total or a unit value.",
)
def plan_cmd(items_file: str, country_default: str | None, total_value: int | None, value_mode: str) -> None:
    """Validate an items JSON/CSV/TSV file and print the fill plan."""

    try:
        _items, plan = _load_plan(items_file, country_default, total_value, value_mode)
        emit(plan)
    except Exception as exc:
        fail(str(exc), error_type=type(exc).__name__)


@cli.command("open-login")
@click.option("--url", default=LOGIN_URL, show_default=True, help="Login/start URL to open.")
@click.option("--headless", is_flag=True, help="Run browser headless.")
@click.option("--browser-channel", default=None, help="Playwright channel, for example msedge or chrome.")
@click.option(
    "--wait/--no-wait",
    default=None,
    help="Keep the browser open until Enter is pressed. Defaults to on for human output and off for --json.",
)
def open_login_cmd(url: str, headless: bool, browser_channel: str | None, wait: bool | None) -> None:
    """Open the Web Yu-pri login/start page in the persistent profile."""

    try:
        should_wait = (not _json_output) if wait is None else wait
        if should_wait:
            with _interactive_session(url, headless=headless, browser_channel=browser_channel) as info:
                emit(info, "Opened Web Yu-pri login page.")
                if not _json_output:
                    click.echo("Log in or inspect the page, then press Enter here to close the browser.")
                input()
        else:
            info = open_login(url=url, profile_dir=_profile_dir, headless=headless, browser_channel=browser_channel)
            emit(info, "Opened Web Yu-pri login page.")
    except KeyboardInterrupt:
        return
    except Exception as exc:
        fail(str(exc), error_type=type(exc).__name__)


@cli.command("status")
@click.option("--url", default=LOGIN_URL, show_default=True, help="URL to inspect.")
@click.option("--headless", is_flag=True, help="Run browser headless.")
@click.option("--browser-channel", default=None, help="Playwright channel, for example msedge or chrome.")
def status_cmd(url: str, headless: bool, browser_channel: str | None) -> None:
    """Open a URL and report title, current URL, and selector presence."""

    try:
        emit(inspect_url(url=url, profile_dir=_profile_dir, headless=headless, browser_channel=browser_channel))
    except Exception as exc:
        fail(str(exc), error_type=type(exc).__name__)


@cli.command("snapshot")
@click.option("--url", default=LOGIN_URL, show_default=True, help="URL to capture.")
@click.option(
    "-o",
    "--output",
    required=True,
    type=click.Path(dir_okay=False, path_type=str),
    help="PNG screenshot output path.",
)
@click.option(
    "--html-output",
    type=click.Path(dir_okay=False, path_type=str),
    default=None,
    help="Optional HTML dump output path.",
)
@click.option("--headless", is_flag=True, help="Run browser headless.")
@click.option("--browser-channel", default=None, help="Playwright channel, for example msedge or chrome.")
def snapshot_cmd(
    url: str,
    output: str,
    html_output: str | None,
    headless: bool,
    browser_channel: str | None,
) -> None:
    """Capture a screenshot, and optionally HTML, for the current form state."""

    try:
        result = capture_snapshot(
            url=url,
            output=output,
            html_output=html_output,
            profile_dir=_profile_dir,
            headless=headless,
            browser_channel=browser_channel,
        )
        emit(result, "Snapshot captured.")
    except Exception as exc:
        fail(str(exc), error_type=type(exc).__name__)


@cli.group()
def contents() -> None:
    """Commands for the shipment contents form."""


@contents.command("fill")
@click.argument("items_file", type=str)
@click.option("--url", default=CONTENTS_URL, show_default=True, help="Contents form URL.")
@click.option("--country-default", default=None, help="Default ISO country code for rows without one.")
@click.option("--total-value", type=int, default=None, help="Override the declared total value in yen.")
@click.option(
    "--value-mode",
    type=click.Choice(["line", "unit"]),
    default="line",
    show_default=True,
    help="Treat item value as a line total or a unit value.",
)
@click.option("--package-type", default=None, help="Optional package type/select value.")
@click.option("--danger/--no-danger", default=None, help="Set the dangerous-goods flag when present.")
@click.option("--dry-run", is_flag=True, help="Validate and print the plan without opening a browser.")
@click.option("--headless", is_flag=True, help="Run browser headless.")
@click.option("--browser-channel", default=None, help="Playwright channel, for example msedge or chrome.")
@click.option("--delay-ms", type=int, default=500, show_default=True, help="Delay after adding each item.")
def contents_fill_cmd(
    items_file: str,
    url: str,
    country_default: str | None,
    total_value: int | None,
    value_mode: str,
    package_type: str | None,
    danger: bool | None,
    dry_run: bool,
    headless: bool,
    browser_channel: str | None,
    delay_ms: int,
) -> None:
    """Fill item lines on the Web Yu-pri contents page.

    This command stops after filling contents and the declared total. It does not
    click the final shipment confirmation/submit button.
    """

    try:
        items, _plan = _load_plan(items_file, country_default, total_value, value_mode)
        if dry_run:
            emit(
                build_dry_run(
                    items,
                    total_value=total_value,
                    value_mode=value_mode,
                    package_type=package_type,
                    danger=danger,
                )
            )
            return
        result = fill_contents(
            items,
            total_value=total_value,
            value_mode=value_mode,
            url=url,
            profile_dir=_profile_dir,
            package_type=package_type,
            danger=danger,
            headless=headless,
            browser_channel=browser_channel,
            delay_ms=delay_ms,
        )
        emit(result, "Contents filled.")
    except Exception as exc:
        fail(str(exc), error_type=type(exc).__name__)


@cli.command("repl")
def repl_cmd() -> None:
    """Start a small command REPL."""

    click.echo("cli-anything-web-yu-pri REPL. Type help or exit.")
    while True:
        try:
            line = input("web-yu-pri> ").strip()
        except (EOFError, KeyboardInterrupt):
            click.echo()
            return
        if not line:
            continue
        if line in {"exit", "quit"}:
            return
        if line == "help":
            click.echo("Try: doctor, selectors, plan <items.json>, contents fill <items.json> --dry-run")
            continue
        try:
            cli.main(args=shlex.split(line), prog_name="cli-anything-web-yu-pri", standalone_mode=False)
        except SystemExit:
            pass
        except Exception as exc:
            click.echo(f"Error: {exc}", err=True)


@contextmanager
def _interactive_session(url: str, headless: bool, browser_channel: str | None):
    from cli_anything.web_yu_pri.core.browser import browser_session, inspect_page

    with browser_session(profile_dir=_profile_dir, headless=headless, browser_channel=browser_channel) as (
        page,
        _context,
    ):
        page.goto(url, wait_until="domcontentloaded")
        yield inspect_page(page)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
