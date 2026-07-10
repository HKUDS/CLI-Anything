r"""
Account management command group
"""

import click
from ..firefly_iii_cli import get_backend, output


@click.group()
def accounts():
    """Manage accounts"""
    pass


@accounts.command(name="list")
@click.option("--type", 
              type=click.Choice(['asset', 'expense', 'revenue', 'liability', 'all']),
              default='all',
              help="Filter by account type")
@click.option("--limit", default=50, help="Limit results")
@click.option("--page", default=1, help="Page number")
def accounts_list(type, limit, page):
    """List all accounts"""
    backend = get_backend()
    params = {"limit": limit, "page": page}
    if type != 'all':
        params["type"] = type
    
    result = backend.get_accounts(params)
    output(result)


@accounts.command(name="get")
@click.option("--id", required=True, type=int, help="Account ID")
def accounts_get(id):
    """Get account details"""
    backend = get_backend()
    result = backend.get_account(id)
    output(result)


@accounts.command(name="create")
@click.option("--name", required=True, help="Account name")
@click.option("--type", 
              required=True,
              type=click.Choice(['asset', 'expense', 'revenue', 'liability']),
              help="Account type")
@click.option("--currency-code", default="USD", help="Currency code (ISO 4217)")
@click.option("--opening-balance", default="0", help="Opening balance")
@click.option("--account-role", help="Account role (for asset accounts)")
@click.option("--iban", help="IBAN")
@click.option("--bic", help="BIC")
@click.option("--account-number", help="Account number")
@click.option("--notes", help="Notes")
def accounts_create(name, type, currency_code, opening_balance, account_role, iban, bic, account_number, notes):
    """Create a new account"""
    backend = get_backend()
    
    data = {
        "name": name,
        "type": type,
        "currency_code": currency_code,
        "opening_balance": opening_balance,
    }
    
    if account_role:
        data["account_role"] = account_role
    if iban:
        data["iban"] = iban
    if bic:
        data["bic"] = bic
    if account_number:
        data["account_number"] = account_number
    if notes:
        data["notes"] = notes
    
    result = backend.create_account(data)
    output(result)


@accounts.command(name="update")
@click.option("--id", required=True, type=int, help="Account ID")
@click.option("--name", help="Account name")
@click.option("--opening-balance", help="Opening balance")
@click.option("--notes", help="Notes")
def accounts_update(id, name, opening_balance, notes):
    """Update an existing account"""
    backend = get_backend()
    
    data = {}
    if name:
        data["name"] = name
    if opening_balance:
        data["opening_balance"] = opening_balance
    if notes:
        data["notes"] = notes
    
    if not data:
        click.echo("Error: At least one update field is required", err=True)
        return
    
    result = backend.update_account(id, data)
    output(result)


@accounts.command(name="delete")
@click.option("--id", required=True, type=int, help="Account ID")
@click.confirmation_option(prompt="Are you sure you want to delete this account?")
def accounts_delete(id):
    """Delete an account"""
    backend = get_backend()
    result = backend.delete_account(id)
    output(result)
