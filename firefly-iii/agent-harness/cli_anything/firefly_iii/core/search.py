r"""
Search command group
"""

import click
from ..firefly_iii_cli import get_backend, output


@click.group()
def search():
    """Search transactions"""
    pass


@search.command(name="transactions")
@click.option("--query", required=True, help="Search query")
@click.option("--limit", default=50, help="Limit results")
@click.option("--page", default=1, help="Page number")
def search_transactions(query, limit, page):
    """Search transactions"""
    backend = get_backend()
    params = {"limit": limit, "page": page}
    
    result = backend.search(query, params)
    output(result)
