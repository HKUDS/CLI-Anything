r"""
Piggy bank management command group
"""

import click
from ..firefly_iii_cli import get_backend, output


@click.group()
def piggy_banks():
    """Manage piggy banks"""
    pass


@piggy_banks.command(name="list")
@click.option("--limit", default=50, help="Limit results")
@click.option("--page", default=1, help="Page number")
def piggy_banks_list(limit, page):
    """List all piggy banks"""
    backend = get_backend()
    params = {"limit": limit, "page": page}
    result = backend.get_piggy_banks(params)
    output(result)
