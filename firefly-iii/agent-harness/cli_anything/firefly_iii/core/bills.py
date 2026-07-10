r"""
Bill management command group
"""

import click
from datetime import datetime
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


@bills.command(name="get")
@click.option("--id", required=True, type=int, help="Bill ID")
def bills_get(id):
    """Get bill details"""
    backend = get_backend()
    result = backend.get_bill(id)
    output(result)


@bills.command(name="create")
@click.option("--name", required=True, help="Bill name")
@click.option("--amount-min", required=True, help="Minimum amount")
@click.option("--amount-max", required=True, help="Maximum amount")
@click.option("--currency-code", default="USD", help="Currency code")
@click.option("--frequency",
              type=click.Choice(['weekly', 'monthly', 'quarterly', 'half-yearly', 'yearly']),
              default='monthly',
              help="Bill frequency")
@click.option("--start-date", help="Start date (YYYY-MM-DD)")
@click.option("--end-date", help="End date (YYYY-MM-DD)")
@click.option("--pay-date", help="Expected pay date (YYYY-MM-DD)")
@click.option("--payment-date", help="Payment date (YYYY-MM-DD)")
@click.option("--notes", help="Notes")
def bills_create(name, amount_min, amount_max, currency_code, frequency,
                 start_date, end_date, pay_date, payment_date, notes):
    """Create a new bill"""
    backend = get_backend()

    data = {
        "name": name,
        "amount_min": amount_min,
        "amount_max": amount_max,
        "currency_code": currency_code,
        "frequency": frequency,
    }

    if start_date:
        data["start_date"] = start_date
    if end_date:
        data["end_date"] = end_date
    if pay_date:
        data["pay_date"] = pay_date
    if payment_date:
        data["payment_date"] = payment_date
    if notes:
        data["notes"] = notes

    result = backend.create_bill(data)
    output(result)


@bills.command(name="update")
@click.option("--id", required=True, type=int, help="Bill ID")
@click.option("--name", help="Bill name")
@click.option("--amount-min", help="Minimum amount")
@click.option("--amount-max", help="Maximum amount")
@click.option("--currency-code", help="Currency code")
@click.option("--frequency",
              type=click.Choice(['weekly', 'monthly', 'quarterly', 'half-yearly', 'yearly']),
              help="Bill frequency")
@click.option("--start-date", help="Start date (YYYY-MM-DD)")
@click.option("--end-date", help="End date (YYYY-MM-DD)")
@click.option("--pay-date", help="Expected pay date (YYYY-MM-DD)")
@click.option("--payment-date", help="Payment date (YYYY-MM-DD)")
@click.option("--notes", help="Notes")
@click.option("--active", type=bool, help="Is active")
def bills_update(id, name, amount_min, amount_max, currency_code, frequency,
                 start_date, end_date, pay_date, payment_date, notes, active):
    """Update an existing bill"""
    backend = get_backend()

    data = {}
    if name:
        data["name"] = name
    if amount_min:
        data["amount_min"] = amount_min
    if amount_max:
        data["amount_max"] = amount_max
    if currency_code:
        data["currency_code"] = currency_code
    if frequency:
        data["frequency"] = frequency
    if start_date:
        data["start_date"] = start_date
    if end_date:
        data["end_date"] = end_date
    if pay_date:
        data["pay_date"] = pay_date
    if payment_date:
        data["payment_date"] = payment_date
    if notes:
        data["notes"] = notes
    if active is not None:
        data["active"] = active

    if not data:
        click.echo("Error: At least one update field is required", err=True)
        return

    result = backend.update_bill(id, data)
    output(result)


@bills.command(name="delete")
@click.option("--id", required=True, type=int, help="Bill ID")
@click.confirmation_option(prompt="Are you sure you want to delete this bill?")
def bills_delete(id):
    """Delete a bill"""
    backend = get_backend()
    result = backend.delete_bill(id)
    output(result)
