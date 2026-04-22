r"""
Budget management command group
"""

import click
from datetime import datetime
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


@budgets.command(name="create")
@click.option("--name", required=True, help="Budget name")
@click.option("--notes", help="Notes")
def budgets_create(name, notes):
    """Create a new budget"""
    backend = get_backend()

    data = {"name": name}
    if notes:
        data["notes"] = notes

    result = backend.create_budget(data)
    output(result)


@budgets.command(name="update")
@click.option("--id", required=True, type=int, help="Budget ID")
@click.option("--name", help="Budget name")
@click.option("--notes", help="Notes")
def budgets_update(id, name, notes):
    """Update an existing budget"""
    backend = get_backend()

    data = {}
    if name:
        data["name"] = name
    if notes:
        data["notes"] = notes

    if not data:
        click.echo("Error: At least one update field is required", err=True)
        return

    result = backend.update_budget(id, data)
    output(result)


@budgets.command(name="delete")
@click.option("--id", required=True, type=int, help="Budget ID")
@click.confirmation_option(prompt="Are you sure you want to delete this budget?")
def budgets_delete(id):
    """Delete a budget"""
    backend = get_backend()
    result = backend.delete_budget(id)
    output(result)


# ========== Budget Limits ==========

@budgets.command(name="limits")
@click.option("--budget-id", required=True, type=int, help="Budget ID")
@click.option("--start", help="Start date (YYYY-MM-DD)")
@click.option("--end", help="End date (YYYY-MM-DD)")
def budgets_limits(budget_id, start, end):
    """List budget limits for a budget"""
    backend = get_backend()
    params = {}
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    result = backend.get_budget_limits(budget_id, params)
    output(result)


@budgets.command(name="limit-create")
@click.option("--budget-id", required=True, type=int, help="Budget ID")
@click.option("--amount", required=True, help="Amount")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
@click.option("--currency-code", default="USD", help="Currency code")
def budgets_limit_create(budget_id, amount, start, end, currency_code):
    """Create a budget limit"""
    backend = get_backend()

    data = {
        "amount": amount,
        "start": start,
        "end": end,
        "currency_id": currency_code,
    }

    result = backend.create_budget_limit(budget_id, data)
    output(result)


@budgets.command(name="limit-update")
@click.option("--id", required=True, type=int, help="Budget limit ID")
@click.option("--amount", help="Amount")
def budgets_limit_update(id, amount):
    """Update a budget limit"""
    backend = get_backend()

    data = {}
    if amount:
        data["amount"] = amount

    if not data:
        click.echo("Error: Amount is required", err=True)
        return

    result = backend.update_budget_limit(id, data)
    output(result)


@budgets.command(name="limit-delete")
@click.option("--id", required=True, type=int, help="Budget limit ID")
@click.confirmation_option(prompt="Are you sure you want to delete this budget limit?")
def budgets_limit_delete(id):
    """Delete a budget limit"""
    backend = get_backend()
    result = backend.delete_budget_limit(id)
    output(result)
