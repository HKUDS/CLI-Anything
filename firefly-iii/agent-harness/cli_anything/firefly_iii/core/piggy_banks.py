r"""
Piggy bank management command group
"""

import click
from datetime import datetime
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


@piggy_banks.command(name="get")
@click.option("--id", required=True, type=int, help="Piggy bank ID")
def piggy_banks_get(id):
    """Get piggy bank details"""
    backend = get_backend()
    result = backend.get_piggy_bank(id)
    output(result)


@piggy_banks.command(name="create")
@click.option("--name", required=True, help="Piggy bank name")
@click.option("--account-id", required=True, type=int, help="Account ID")
@click.option("--target-amount", help="Target amount")
@click.option("--start-date", help="Start date (YYYY-MM-DD)")
@click.option("--notes", help="Notes")
def piggy_banks_create(name, account_id, target_amount, start_date, notes):
    """Create a new piggy bank"""
    backend = get_backend()

    data = {
        "name": name,
        "account_id": account_id,
    }

    if target_amount:
        data["target_amount"] = target_amount
    if start_date:
        data["start_date"] = start_date
    if notes:
        data["notes"] = notes

    result = backend.create_piggy_bank(data)
    output(result)


@piggy_banks.command(name="update")
@click.option("--id", required=True, type=int, help="Piggy bank ID")
@click.option("--name", help="Piggy bank name")
@click.option("--target-amount", help="Target amount")
@click.option("--start-date", help="Start date (YYYY-MM-DD)")
@click.option("--end-date", help="End date (YYYY-MM-DD)")
@click.option("--notes", help="Notes")
@click.option("--active", type=bool, help="Is active")
def piggy_banks_update(id, name, target_amount, start_date, end_date, notes, active):
    """Update an existing piggy bank"""
    backend = get_backend()

    data = {}
    if name:
        data["name"] = name
    if target_amount:
        data["target_amount"] = target_amount
    if start_date:
        data["start_date"] = start_date
    if end_date:
        data["end_date"] = end_date
    if notes:
        data["notes"] = notes
    if active is not None:
        data["active"] = active

    if not data:
        click.echo("Error: At least one update field is required", err=True)
        return

    result = backend.update_piggy_bank(id, data)
    output(result)


@piggy_banks.command(name="delete")
@click.option("--id", required=True, type=int, help="Piggy bank ID")
@click.confirmation_option(prompt="Are you sure you want to delete this piggy bank?")
def piggy_banks_delete(id):
    """Delete a piggy bank"""
    backend = get_backend()
    result = backend.delete_piggy_bank(id)
    output(result)


@piggy_banks.command(name="events")
@click.option("--id", required=True, type=int, help="Piggy bank ID")
def piggy_banks_events(id):
    """List piggy bank events"""
    backend = get_backend()
    result = backend.get_piggy_bank_events(id)
    output(result)


@piggy_banks.command(name="add-money")
@click.option("--id", required=True, type=int, help="Piggy bank ID")
@click.option("--amount", required=True, help="Amount to add")
@click.option("--date", default=lambda: datetime.now().strftime('%Y-%m-%d'),
              help="Date (YYYY-MM-DD)")
@click.option("--note", help="Note")
def piggy_banks_add_money(id, amount, date, note):
    """Add money to piggy bank"""
    backend = get_backend()

    data = {
        "amount": amount,
        "date": date,
    }
    if note:
        data["note"] = note

    result = backend.create_piggy_bank_event(id, data)
    output(result)
