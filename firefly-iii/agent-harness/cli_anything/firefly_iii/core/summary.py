r"""
Summary command group

Provides various summary reports and statistics.
"""

import click
from ..firefly_iii_cli import get_backend, output


@click.group()
def summary():
    """Financial summaries and reports"""
    pass


@summary.command(name="default-set")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
def summary_default_set(start, end):
    """Get default summary set"""
    backend = get_backend()
    params = {"start": start, "end": end}
    result = backend.get_summary("default-set", params)
    output(result)


@summary.command(name="account-summary")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
@click.option("--accounts", help="Account IDs (comma-separated)")
def summary_account_summary(start, end, accounts):
    """Get account summary"""
    backend = get_backend()
    params = {"start": start, "end": end}
    if accounts:
        params["accounts"] = accounts
    result = backend.get_summary("account-summary", params)
    output(result)


@summary.command(name="available-budget")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
def summary_available_budget(start, end):
    """Get available budget summary"""
    backend = get_backend()
    params = {"start": start, "end": end}
    result = backend.get_summary("available-budget", params)
    output(result)


@summary.command(name="bill-summary")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
def summary_bill_summary(start, end):
    """Get bill summary"""
    backend = get_backend()
    params = {"start": start, "end": end}
    result = backend.get_summary("bill-summary", params)
    output(result)


@summary.command(name="budget-summary")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
def summary_budget_summary(start, end):
    """Get budget summary"""
    backend = get_backend()
    params = {"start": start, "end": end}
    result = backend.get_summary("budget-summary", params)
    output(result)


@summary.command(name="category-summary")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
def summary_category_summary(start, end):
    """Get category summary"""
    backend = get_backend()
    params = {"start": start, "end": end}
    result = backend.get_summary("category-summary", params)
    output(result)


@summary.command(name="tag-summary")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
def summary_tag_summary(start, end):
    """Get tag summary"""
    backend = get_backend()
    params = {"start": start, "end": end}
    result = backend.get_summary("tag-summary", params)
    output(result)


@summary.command(name="transfer-summary")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
def summary_transfer_summary(start, end):
    """Get transfer summary"""
    backend = get_backend()
    params = {"start": start, "end": end}
    result = backend.get_summary("transfer-summary", params)
    output(result)
