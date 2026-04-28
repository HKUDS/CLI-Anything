r"""
Transaction management command group
"""

import click
from datetime import datetime
from ..firefly_iii_cli import get_backend, output


@click.group()
def transactions():
    """Manage transactions"""
    pass


@transactions.command(name="list")
@click.option("--limit", default=50, help="Limit results")
@click.option("--page", default=1, help="Page number")
@click.option("--start", help="Start date (YYYY-MM-DD)")
@click.option("--end", help="End date (YYYY-MM-DD)")
@click.option("--type",
              type=click.Choice(['withdrawal', 'deposit', 'transfer']),
              help="Transaction type")
@click.option("--source-account", help="Source account ID or name")
@click.option("--destination-account", help="Destination account ID or name")
def transactions_list(limit, page, start, end, type, source_account, destination_account):
    """List transactions"""
    backend = get_backend()
    params = {"limit": limit, "page": page}

    if start:
        params["start"] = start
    if end:
        params["end"] = end
    if type:
        params["type"] = type
    if source_account:
        params["source_id"] = source_account
    if destination_account:
        params["destination_id"] = destination_account

    result = backend.get_transactions(params)
    output(result)


@transactions.command(name="get")
@click.option("--id", required=True, type=int, help="Transaction ID")
def transactions_get(id):
    """Get transaction details"""
    backend = get_backend()
    result = backend.get_transaction(id)
    output(result)


@transactions.command(name="create")
@click.option("--description", required=True, help="Transaction description")
@click.option("--amount", required=True, help="Transaction amount")
@click.option("--source-account", required=True, help="Source account ID")
@click.option("--destination-account", help="Destination account ID (for transfers)")
@click.option("--type",
              type=click.Choice(['withdrawal', 'deposit', 'transfer']),
              default='withdrawal',
              help="Transaction type")
@click.option("--date", default=lambda: datetime.now().strftime('%Y-%m-%d'),
              help="Transaction date (YYYY-MM-DD)")
@click.option("--category", help="Category name")
@click.option("--tags", help="Tags (comma-separated)")
@click.option("--budget", help="Budget name")
@click.option("--notes", help="Notes")
def transactions_create(description, amount, source_account, destination_account,
                       type, date, category, tags, budget, notes):
    """Create a new transaction"""
    backend = get_backend()

    transaction_data = {
        "type": type,
        "date": date,
        "amount": amount,
        "description": description,
        "source_id": source_account,
    }

    if destination_account:
        transaction_data["destination_id"] = destination_account
    if category:
        transaction_data["category_name"] = category
    if tags:
        transaction_data["tags"] = [tag.strip() for tag in tags.split(",")]
    if budget:
        transaction_data["budget_name"] = budget
    if notes:
        transaction_data["notes"] = notes

    data = {
        "error_if_duplicate_hash": True,
        "error_if_duplicate_hash_v2": True,
        "apply_rules": True,
        "fire_webhooks": True,
        "group_title": description,
        "transactions": [transaction_data]
    }

    result = backend.create_transaction(data)
    output(result)


@transactions.command(name="update")
@click.option("--id", required=True, type=int, help="Transaction ID")
@click.option("--description", help="Transaction description")
@click.option("--amount", help="Transaction amount")
@click.option("--category", help="Category name")
@click.option("--tags", help="Tags (comma-separated)")
@click.option("--notes", help="Notes")
def transactions_update(id, description, amount, category, tags, notes):
    """Update an existing transaction"""
    backend = get_backend()

    transaction_data = {}
    if description:
        transaction_data["description"] = description
    if amount:
        transaction_data["amount"] = amount
    if category:
        transaction_data["category_name"] = category
    if tags:
        transaction_data["tags"] = [tag.strip() for tag in tags.split(",")]
    if notes:
        transaction_data["notes"] = notes

    if not transaction_data:
        click.echo("Error: At least one update field is required", err=True)
        return

    data = {
        "apply_rules": True,
        "fire_webhooks": True,
        "transactions": [transaction_data]
    }

    result = backend.update_transaction(id, data)
    output(result)


@transactions.command(name="delete")
@click.option("--id", required=True, type=int, help="Transaction ID")
@click.confirmation_option(prompt="Are you sure you want to delete this transaction?")
def transactions_delete(id):
    """Delete a transaction"""
    backend = get_backend()
    result = backend.delete_transaction(id)
    output(result)
