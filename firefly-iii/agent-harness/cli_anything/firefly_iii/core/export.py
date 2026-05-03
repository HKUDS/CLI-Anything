r"""
Search command group
"""

import click
from ..firefly_iii_cli import get_backend, output


@click.group()
def export():
    """Export data"""
    pass


@export.command(name="accounts")
@click.option("--type", default="csv", type=click.Choice(['csv']), help="Export format")
def export_accounts(type):
    """Export accounts"""
    backend = get_backend()
    params = {"type": type}
    
    result = backend.export_data("accounts", params)
    output(result)


@export.command(name="transactions")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
@click.option("--accounts", help="Account IDs (comma-separated)")
@click.option("--type", default="csv", type=click.Choice(['csv']), help="Export format")
def export_transactions(start, end, accounts, type):
    """Export transactions"""
    backend = get_backend()
    params = {"start": start, "end": end, "type": type}
    
    if accounts:
        params["accounts"] = accounts
    
    result = backend.export_data("transactions", params)
    output(result)


@export.command(name="budgets")
@click.option("--type", default="csv", type=click.Choice(['csv']), help="Export format")
def export_budgets(type):
    """Export budgets"""
    backend = get_backend()
    params = {"type": type}
    
    result = backend.export_data("budgets", params)
    output(result)


@export.command(name="categories")
@click.option("--type", default="csv", type=click.Choice(['csv']), help="Export format")
def export_categories(type):
    """Export categories"""
    backend = get_backend()
    params = {"type": type}
    
    result = backend.export_data("categories", params)
    output(result)
