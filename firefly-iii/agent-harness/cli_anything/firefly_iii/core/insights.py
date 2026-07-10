r"""
Insight and report command group
"""

import click
from ..firefly_iii_cli import get_backend, output


@click.group()
def insights():
    """View financial insights and reports"""
    pass


@insights.command(name="expense")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
@click.option("--group-by", 
              type=click.Choice(['expense', 'asset', 'bill', 'budget', 'category', 'tag']),
              default='category',
              help="Group expenses by")
@click.option("--accounts", help="Account IDs (comma-separated)")
def insights_expense(start, end, group_by, accounts):
    """View expense insights"""
    backend = get_backend()
    params = {"start": start, "end": end}
    
    if accounts:
        params["accounts[]"] = accounts.split(",")
    
    endpoint_map = {
        'expense': '/insight/expense/expense',
        'asset': '/insight/expense/asset',
        'bill': '/insight/expense/bill',
        'budget': '/insight/expense/budget',
        'category': '/insight/expense/category',
        'tag': '/insight/expense/tag',
    }
    
    result = backend.get(endpoint_map[group_by], params=params)
    output(result)


@insights.command(name="income")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
@click.option("--group-by",
              type=click.Choice(['revenue', 'asset', 'category']),
              default='category',
              help="Group income by")
@click.option("--accounts", help="Account IDs (comma-separated)")
def insights_income(start, end, group_by, accounts):
    """View income insights"""
    backend = get_backend()
    params = {"start": start, "end": end}
    
    if accounts:
        params["accounts[]"] = accounts.split(",")
    
    endpoint_map = {
        'revenue': '/insight/income/revenue',
        'asset': '/insight/income/asset',
        'category': '/insight/income/category',
    }
    
    result = backend.get(endpoint_map[group_by], params=params)
    output(result)


@insights.command(name="transfer")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
@click.option("--accounts", help="Account IDs (comma-separated)")
def insights_transfer(start, end, accounts):
    """View transfer insights"""
    backend = get_backend()
    params = {"start": start, "end": end}
    
    if accounts:
        params["accounts[]"] = accounts.split(",")
    
    result = backend.get("/insight/transfer/asset", params=params)
    output(result)


@insights.command(name="overview")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
def insights_overview(start, end):
    """View account overview chart data"""
    backend = get_backend()
    params = {"start": start, "end": end}
    
    result = backend.get("/chart/account/overview", params=params)
    output(result)
