r"""
Tag management command group
"""

import click
from ..firefly_iii_cli import get_backend, output


@click.group()
def tags():
    """Manage tags"""
    pass


@tags.command(name="list")
@click.option("--limit", default=50, help="Limit results")
@click.option("--page", default=1, help="Page number")
def tags_list(limit, page):
    """List all tags"""
    backend = get_backend()
    params = {"limit": limit, "page": page}
    result = backend.get_tags(params)
    output(result)
