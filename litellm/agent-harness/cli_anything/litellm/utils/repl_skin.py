from __future__ import annotations

"""Minimal output helpers for cli-anything-litellm."""

import click


def print_banner(host: str, model: str | None) -> None:
    click.echo("cli")
    click.echo(f"  host: {host}")
    click.echo(f"  model: {model or '(unset)'}")
    click.echo("  mode: agent execution")


def success(message: str) -> None:
    click.secho(message, fg="green")


def error(message: str) -> None:
    click.secho(message, fg="red", err=True)


def warn(message: str) -> None:
    click.secho(message, fg="yellow")


def info(message: str) -> None:
    click.secho(message, fg="cyan")
