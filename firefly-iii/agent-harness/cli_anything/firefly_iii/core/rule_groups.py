r"""
Rule group management command group
"""

import click
from ..firefly_iii_cli import get_backend, output


@click.group()
def rule_groups():
    """Manage rule groups"""
    pass


@rule_groups.command(name="list")
@click.option("--limit", default=50, help="Limit results")
@click.option("--page", default=1, help="Page number")
def rule_groups_list(limit, page):
    """List all rule groups"""
    backend = get_backend()
    params = {"limit": limit, "page": page}
    result = backend.get_rule_groups(params)
    output(result)


@rule_groups.command(name="get")
@click.option("--id", required=True, type=int, help="Rule group ID")
def rule_groups_get(id):
    """Get rule group details"""
    backend = get_backend()
    result = backend.get_rule_group(id)
    output(result)


@rule_groups.command(name="create")
@click.option("--title", required=True, help="Rule group title")
@click.option("--description", help="Description")
@click.option("--priority", default=0, type=int, help="Priority")
def rule_groups_create(title, description, priority):
    """Create a new rule group"""
    backend = get_backend()

    data = {
        "title": title,
        "priority": priority,
    }
    if description:
        data["description"] = description

    result = backend.create_rule_group(data)
    output(result)


@rule_groups.command(name="update")
@click.option("--id", required=True, type=int, help="Rule group ID")
@click.option("--title", help="Rule group title")
@click.option("--description", help="Description")
@click.option("--priority", type=int, help="Priority")
@click.option("--active", type=bool, help="Is active")
def rule_groups_update(id, title, description, priority, active):
    """Update an existing rule group"""
    backend = get_backend()

    data = {}
    if title:
        data["title"] = title
    if description:
        data["description"] = description
    if priority is not None:
        data["priority"] = priority
    if active is not None:
        data["active"] = active

    if not data:
        click.echo("Error: At least one update field is required", err=True)
        return

    result = backend.update_rule_group(id, data)
    output(result)


@rule_groups.command(name="delete")
@click.option("--id", required=True, type=int, help="Rule group ID")
@click.confirmation_option(prompt="Are you sure you want to delete this rule group?")
def rule_groups_delete(id):
    """Delete a rule group"""
    backend = get_backend()
    result = backend.delete_rule_group(id)
    output(result)


@rule_groups.command(name="execute")
@click.option("--id", required=True, type=int, help="Rule group ID")
def rule_groups_execute(id):
    """Execute all rules in a rule group"""
    backend = get_backend()
    result = backend.execute_rule_group(id)
    output(result)
