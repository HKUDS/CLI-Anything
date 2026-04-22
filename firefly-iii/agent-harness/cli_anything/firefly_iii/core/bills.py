r"""
Bill management command group
"""

import click
from ..firefly_iii_cli import get_backend, output


@click.group()
def bills():
    """Manage bills"""
    pass


@bills.command(name="list")
@click.option("--limit", default=50, help="Limit results")
@click.option("--page", default=1, help="Page number")
def bills_list(limit, page):
    """List all bills"""
    backend = get_backend()
    params = {"limit": limit, "page": page}
    result = backend.get_bills(params)
    output(result)
