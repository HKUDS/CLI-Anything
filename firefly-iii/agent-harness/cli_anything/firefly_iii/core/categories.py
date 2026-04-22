r"""
Category management command group
"""

import click
from ..firefly_iii_cli import get_backend, output


@click.group()
def categories():
    """Manage categories"""
    pass


@categories.command(name="list")
@click.option("--limit", default=50, help="Limit results")
@click.option("--page", default=1, help="Page number")
def categories_list(limit, page):
    """List all categories"""
    backend = get_backend()
    params = {"limit": limit, "page": page}
    result = backend.get_categories(params)
    output(result)
