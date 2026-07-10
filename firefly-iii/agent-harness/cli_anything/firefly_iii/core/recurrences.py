r"""
Recurring transaction management command group
"""

import click
from datetime import datetime
from ..firefly_iii_cli import get_backend, output


@click.group()
def recurrences():
    """Manage recurring transactions"""
    pass


@recurrences.command(name="list")
@click.option("--limit", default=50, help="Limit results")
@click.option("--page", default=1, help="Page number")
def recurrences_list(limit, page):
    """List all recurring transactions"""
    backend = get_backend()
    params = {"limit": limit, "page": page}
    result = backend.get_recurrences(params)
    output(result)


@recurrences.command(name="get")
@click.option("--id", required=True, type=int, help="Recurrence ID")
def recurrences_get(id):
    """Get recurring transaction details"""
    backend = get_backend()
    result = backend.get_recurrence(id)
    output(result)


@recurrences.command(name="create")
@click.option("--title", required=True, help="Recurrence title")
@click.option("--type",
              type=click.Choice(['withdrawal', 'deposit', 'transfer']),
              required=True,
              help="Transaction type")
@click.option("--amount", required=True, help="Amount")
@click.option("--currency-code", default="USD", help="Currency code")
@click.option("--source-account", required=True, help="Source account ID")
@click.option("--destination-account", help="Destination account ID")
@click.option("--frequency",
              type=click.Choice(['daily', 'weekly', 'monthly', 'quarterly', 'half-yearly', 'yearly']),
              required=True,
              help="Frequency")
@click.option("--start-date", help="Start date (YYYY-MM-DD)")
@click.option("--end-date", help="End date (YYYY-MM-DD)")
@click.option("--description", help="Description")
@click.option("--notes", help="Notes")
@click.option("--tags", help="Tags (comma-separated)")
def recurrences_create(title, type, amount, currency_code, source_account,
                       destination_account, frequency, start_date, end_date,
                       description, notes, tags):
    """Create a new recurring transaction"""
    backend = get_backend()

    data = {
        "title": title,
        "type": type,
        "amount": amount,
        "currency_code": currency_code,
        "source_id": source_account,
        "frequency": frequency,
    }

    if destination_account:
        data["destination_id"] = destination_account
    if start_date:
        data["start_date"] = start_date
    if end_date:
        data["end_date"] = end_date
    if description:
        data["description"] = description
    if notes:
        data["notes"] = notes
    if tags:
        data["tags"] = [t.strip() for t in tags.split(",")]

    result = backend.create_recurrence(data)
    output(result)


@recurrences.command(name="update")
@click.option("--id", required=True, type=int, help="Recurrence ID")
@click.option("--title", help="Recurrence title")
@click.option("--type",
              type=click.Choice(['withdrawal', 'deposit', 'transfer']),
              help="Transaction type")
@click.option("--amount", help="Amount")
@click.option("--currency-code", help="Currency code")
@click.option("--source-account", help="Source account ID")
@click.option("--destination-account", help="Destination account ID")
@click.option("--frequency",
              type=click.Choice(['daily', 'weekly', 'monthly', 'quarterly', 'half-yearly', 'yearly']),
              help="Frequency")
@click.option("--start-date", help="Start date (YYYY-MM-DD)")
@click.option("--end-date", help="End date (YYYY-MM-DD)")
@click.option("--description", help="Description")
@click.option("--notes", help="Notes")
@click.option("--tags", help="Tags (comma-separated)")
def recurrences_update(id, title, type, amount, currency_code, source_account,
                       destination_account, frequency, start_date, end_date,
                       description, notes, tags):
    """Update an existing recurring transaction"""
    backend = get_backend()

    data = {}
    if title:
        data["title"] = title
    if type:
        data["type"] = type
    if amount:
        data["amount"] = amount
    if currency_code:
        data["currency_code"] = currency_code
    if source_account:
        data["source_id"] = source_account
    if destination_account:
        data["destination_id"] = destination_account
    if frequency:
        data["frequency"] = frequency
    if start_date:
        data["start_date"] = start_date
    if end_date:
        data["end_date"] = end_date
    if description:
        data["description"] = description
    if notes:
        data["notes"] = notes
    if tags:
        data["tags"] = [t.strip() for t in tags.split(",")]

    if not data:
        click.echo("Error: At least one update field is required", err=True)
        return

    result = backend.update_recurrence(id, data)
    output(result)


@recurrences.command(name="delete")
@click.option("--id", required=True, type=int, help="Recurrence ID")
@click.confirmation_option(prompt="Are you sure you want to delete this recurring transaction?")
def recurrences_delete(id):
    """Delete a recurring transaction"""
    backend = get_backend()
    result = backend.delete_recurrence(id)
    output(result)
