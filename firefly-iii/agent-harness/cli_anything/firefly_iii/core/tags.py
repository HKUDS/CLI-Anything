r"""
Tag management command group
"""

import click
from ..firefly_iii_cli import get_backend, output


@click.group()
def tags():
    """Manage tags"""
    pass


@tags.command(name="list")
@click.option("--limit", default=50, help="Limit results")
@click.option("--page", default=1, help="Page number")
def tags_list(limit, page):
    """List all tags"""
    backend = get_backend()
    params = {"limit": limit, "page": page}
    result = backend.get_tags(params)
    output(result)


@tags.command(name="get")
@click.option("--id", required=True, help="Tag ID (can be UUID or integer)")
def tags_get(id):
    """Get tag details"""
    backend = get_backend()
    result = backend.get_tag(id)
    output(result)


@tags.command(name="create")
@click.option("--tag", required=True, help="Tag value")
@click.option("--description", help="Description")
@click.option("--date", help="Date (YYYY-MM-DD)")
def tags_create(tag, description, date):
    """Create a new tag"""
    backend = get_backend()

    data = {"tag": tag}
    if description:
        data["description"] = description
    if date:
        data["date"] = date

    result = backend.create_tag(data)
    output(result)


@tags.command(name="update")
@click.option("--id", required=True, help="Tag ID")
@click.option("--tag", help="Tag value")
@click.option("--description", help="Description")
@click.option("--date", help="Date (YYYY-MM-DD)")
def tags_update(id, tag, description, date):
    """Update an existing tag"""
    backend = get_backend()

    data = {}
    if tag:
        data["tag"] = tag
    if description:
        data["description"] = description
    if date:
        data["date"] = date

    if not data:
        click.echo("Error: At least one update field is required", err=True)
        return

    result = backend.update_tag(id, data)
    output(result)


@tags.command(name="delete")
@click.option("--id", required=True, help="Tag ID")
@click.confirmation_option(prompt="Are you sure you want to delete this tag?")
def tags_delete(id):
    """Delete a tag"""
    backend = get_backend()
    result = backend.delete_tag(id)
    output(result)
