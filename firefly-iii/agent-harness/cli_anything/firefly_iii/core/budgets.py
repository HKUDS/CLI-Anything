r"""
Budget management command group
"""

import click
from ..firefly_iii_cli import get_backend, output


@click.group()
def budgets():
    """Manage budgets"""
    pass


@budgets.command(name="list")
@click.option("--limit", default=50, help="Limit results")
@click.option("--page", default=1, help="Page number")
def budgets_list(limit, page):
    """List all budgets"""
    backend = get_backend()
    params = {"limit": limit, "page": page}
    result = backend.get_budgets(params)
    output(result)


@budgets.command(name="get")
@click.option("--id", required=True, type=int, help="Budget ID")
def budgets_get(id):
    """Get budget details"""
    backend = get_backend()
    result = backend.get_budget(id)
    output(result)
