r"""
Category management command group
"""

import click
from ..firefly_iii_cli import get_backend, output


@click.group()
def categories():
    """Manage categories"""
    pass


@categories.command(name="list")
@click.option("--limit", default=50, help="Limit results")
@click.option("--page", default=1, help="Page number")
def categories_list(limit, page):
    """List all categories"""
    backend = get_backend()
    params = {"limit": limit, "page": page}
    result = backend.get_categories(params)
    output(result)


@categories.command(name="get")
@click.option("--id", required=True, type=int, help="Category ID")
def categories_get(id):
    """Get category details"""
    backend = get_backend()
    result = backend.get_category(id)
    output(result)


@categories.command(name="create")
@click.option("--name", required=True, help="Category name")
@click.option("--notes", help="Notes")
def categories_create(name, notes):
    """Create a new category"""
    backend = get_backend()

    data = {"name": name}
    if notes:
        data["notes"] = notes

    result = backend.create_category(data)
    output(result)


@categories.command(name="update")
@click.option("--id", required=True, type=int, help="Category ID")
@click.option("--name", help="Category name")
@click.option("--notes", help="Notes")
def categories_update(id, name, notes):
    """Update an existing category"""
    backend = get_backend()

    data = {}
    if name:
        data["name"] = name
    if notes:
        data["notes"] = notes

    if not data:
        click.echo("Error: At least one update field is required", err=True)
        return

    result = backend.update_category(id, data)
    output(result)


@categories.command(name="delete")
@click.option("--id", required=True, type=int, help="Category ID")
@click.confirmation_option(prompt="Are you sure you want to delete this category?")
def categories_delete(id):
    """Delete a category"""
    backend = get_backend()
    result = backend.delete_category(id)
    output(result)
