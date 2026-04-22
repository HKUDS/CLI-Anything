r"""
Currency management command group
"""

import click
from ..firefly_iii_cli import get_backend, output


@click.group()
def currencies():
    """Manage currencies"""
    pass


@currencies.command(name="list")
@click.option("--limit", default=50, help="Limit results")
@click.option("--page", default=1, help="Page number")
def currencies_list(limit, page):
    """List all currencies"""
    backend = get_backend()
    params = {"limit": limit, "page": page}
    result = backend.get_currencies(params)
    output(result)


@currencies.command(name="get")
@click.option("--id", required=True, type=int, help="Currency ID")
def currencies_get(id):
    """Get currency details"""
    backend = get_backend()
    result = backend.get_currency(id)
    output(result)


@currencies.command(name="create")
@click.option("--code", required=True, help="Currency code (ISO 4217, e.g., USD, EUR)")
@click.option("--name", required=True, help="Currency name")
@click.option("--symbol", required=True, help="Currency symbol (e.g., $)")
@click.option("--decimal-places", default=2, type=int, help="Number of decimal places")
@click.option("--enabled", default=True, type=bool, help="Is enabled")
def currencies_create(code, name, symbol, decimal_places, enabled):
    """Create a new currency"""
    backend = get_backend()

    data = {
        "code": code,
        "name": name,
        "symbol": symbol,
        "decimal_places": decimal_places,
        "enabled": enabled,
    }

    result = backend.create_currency(data)
    output(result)


@currencies.command(name="update")
@click.option("--id", required=True, type=int, help="Currency ID")
@click.option("--name", help="Currency name")
@click.option("--symbol", help="Currency symbol")
@click.option("--decimal-places", type=int, help="Number of decimal places")
@click.option("--enabled", type=bool, help="Is enabled")
def currencies_update(id, name, symbol, decimal_places, enabled):
    """Update an existing currency"""
    backend = get_backend()

    data = {}
    if name:
        data["name"] = name
    if symbol:
        data["symbol"] = symbol
    if decimal_places is not None:
        data["decimal_places"] = decimal_places
    if enabled is not None:
        data["enabled"] = enabled

    if not data:
        click.echo("Error: At least one update field is required", err=True)
        return

    result = backend.update_currency(id, data)
    output(result)


@currencies.command(name="delete")
@click.option("--id", required=True, type=int, help="Currency ID")
@click.confirmation_option(prompt="Are you sure you want to delete this currency?")
def currencies_delete(id):
    """Delete a currency"""
    backend = get_backend()
    result = backend.delete_currency(id)
    output(result)


@currencies.command(name="exchange-rates")
@click.option("--from", "from_code", help="Source currency code")
@click.option("--to", "to_code", help="Target currency code")
def currencies_exchange_rates(from_code, to_code):
    """Get currency exchange rates"""
    backend = get_backend()
    params = {}

    if from_code:
        params["from"] = from_code
    if to_code:
        params["to"] = to_code

    result = backend.get_currency_exchange_rates(params)
    output(result)
