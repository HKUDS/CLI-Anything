"""
Utilities for cli_anything.jumpserver.

Includes context management, error handling, and helper functions.
"""
import sys
from contextlib import contextmanager
from typing import Any

import click

from cli_anything.jumpserver.core.session import Session, JumpServerClient
from cli_anything.jumpserver.core.output import format_output
from cli_anything.jumpserver.core.state import get_state


class CLIError(click.ClickException):
    """CLI-specific error with formatted message."""

    def __init__(self, message: str, detail: str | None = None):
        super().__init__(message)
        self.detail = detail

    def show(self, file=None) -> None:
        """Display the error message."""
        click.echo(click.style(f"Error: {self.message}", fg="red"), err=True)
        if self.detail:
            click.echo(f"  {self.detail}", err=True)


def require_auth(session: Session) -> JumpServerClient:
    """Ensure the session is authenticated, raise error if not."""
    if not session.is_authenticated():
        raise CLIError(
            "Not authenticated. Please login first.",
            "Use: jumpserver login --url <URL> --username <USER>",
        )
    return session.get_client()


def handle_api_error(response, action: str = "request") -> None:
    """Handle API error responses uniformly."""
    if response.status_code >= 400:
        try:
            detail = response.json()
        except Exception:
            detail = response.text

        if isinstance(detail, dict):
            msg = detail.get("detail", detail.get("error", str(detail)))
        else:
            msg = str(detail)

        raise CLIError(
            f"{msg}",
            f"API {action} failed (HTTP {response.status_code}): {str(msg)[:200]}",
        )


def parse_ids(value: str | None) -> list[str] | None:
    """Parse comma-separated IDs from a string."""
    if value is None:
        return None
    if not value.strip():
        return None
    return [v.strip() for v in value.split(",") if v.strip()]


def validate_output_format(fmt: str) -> str:
    """Validate and normalize output format."""
    valid = {"json", "table", "yaml", "csv"}
    fmt = fmt.lower()
    if fmt not in valid:
        raise CLIError(
            f"Invalid output format: {fmt}",
            f"Valid formats: {', '.join(sorted(valid))}",
        )
    return fmt


def with_output_options(f):
    """Decorator to add common output options to Click commands."""
    f = click.option(
        "--output", "-o",
        type=click.Choice(["table", "json", "yaml"]),
        default="table",
        help="Output format",
    )(f)
    f = click.option(
        "--columns", "-c",
        default=None,
        help="Comma-separated column names to display",
    )(f)
    return f


def print_result(
    data: Any,
    fmt: str = "table",
    columns: list[str] | None = None,
) -> None:
    """Print API response data in the requested format."""
    columns_list = None
    if columns:
        columns_list = [c.strip() for c in columns.split(",")]

    # Handle paginated API responses
    if isinstance(data, dict) and "results" in data:
        format_output(data["results"], fmt=fmt, columns=columns_list)
        if "count" in data:
            click.echo(f"\nTotal: {data['count']}")
    else:
        format_output(data, fmt=fmt, columns=columns_list)
