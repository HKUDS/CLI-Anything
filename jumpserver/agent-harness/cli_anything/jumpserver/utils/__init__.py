"""
Utilities for cli_anything.jumpserver.

Includes context management, error handling, and helper functions.
"""
import sys
import json
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

    def show(self, file=None, json_mode: bool | None = None) -> None:
        """Display the error message."""
        if file is None:
            file = sys.stderr
        if json_mode is None:
            json_mode = is_json_mode()

        if json_mode:
            payload = {"status": "error", "message": self.message}
            if self.detail:
                payload["detail"] = self.detail
            click.echo(json.dumps(payload, ensure_ascii=False), file=file)
            return

        click.echo(click.style(f"Error: {self.message}", fg="red"), err=True)
        if self.detail:
            click.echo(f"  {self.detail}", err=True)


SENSITIVE_KEYS = {
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "private_key",
    "ssh_key",
}
MASKED_VALUE = "********"


def _iter_context_chain(ctx: click.Context | None):
    """Yield the current Click context and its parents."""
    while ctx is not None:
        yield ctx
        ctx = ctx.parent


def is_json_mode() -> bool:
    """Return whether the active Click invocation requested JSON output."""
    ctx = click.get_current_context(silent=True)
    for current in _iter_context_chain(ctx):
        obj = current.obj or {}
        if obj.get("output_json"):
            return True
        if current.params.get("output") == "json":
            return True
    return False


def wants_json_output(args: list[str] | None = None) -> bool:
    """Best-effort JSON mode detection for top-level exception handling."""
    args = list(sys.argv[1:] if args is None else args)
    if "--json" in args or "--json-output" in args:
        return True

    for index, arg in enumerate(args):
        if arg in {"--output", "-o"}:
            if index + 1 < len(args) and args[index + 1] == "json":
                return True
        elif arg == "--output=json":
            return True

    return False


def resolve_output_format(fmt: str) -> str:
    """Apply global JSON mode to command-local output format defaults."""
    if fmt == "table" and is_json_mode():
        return "json"
    return fmt


def should_emit_human_text(fmt: str = "table") -> bool:
    """Return whether companion human text should be printed."""
    return resolve_output_format(fmt) != "json"


def mask_sensitive_data(value: Any) -> Any:
    """Recursively mask sensitive values before echoing dry-run payloads."""
    if isinstance(value, dict):
        masked = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS and item not in (None, ""):
                masked[key] = MASKED_VALUE
            else:
                masked[key] = mask_sensitive_data(item)
        return masked
    if isinstance(value, list):
        return [mask_sensitive_data(item) for item in value]
    return value


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
    fmt = resolve_output_format(fmt)
    columns_list = None
    if columns:
        columns_list = [c.strip() for c in columns.split(",")]

    # Handle paginated API responses
    if isinstance(data, dict) and "results" in data:
        format_output(data["results"], fmt=fmt, columns=columns_list)
        if fmt != "json" and "count" in data:
            click.echo(f"\nTotal: {data['count']}")
    else:
        format_output(data, fmt=fmt, columns=columns_list)
