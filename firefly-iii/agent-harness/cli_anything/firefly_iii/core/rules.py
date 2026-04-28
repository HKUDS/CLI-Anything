r"""
Rule management command group
"""

import click
from datetime import datetime
from ..firefly_iii_cli import get_backend, output


@click.group()
def rules():
    """Manage transaction rules"""
    pass


@rules.command(name="list")
@click.option("--limit", default=50, help="Limit results")
@click.option("--page", default=1, help="Page number")
def rules_list(limit, page):
    """List all rules"""
    backend = get_backend()
    params = {"limit": limit, "page": page}
    result = backend.get_rules(params)
    output(result)


@rules.command(name="get")
@click.option("--id", required=True, type=int, help="Rule ID")
def rules_get(id):
    """Get rule details"""
    backend = get_backend()
    result = backend.get_rule(id)
    output(result)


@rules.command(name="create")
@click.option("--title", required=True, help="Rule title")
@click.option("--trigger", required=True, help="Trigger type (e.g., from_account_is, to_account_is, description_contains)")
@click.option("--value", required=True, help="Trigger value")
@click.option("--action", required=True,
              type=click.Choice(['set_category', 'add_tag', 'remove_tag', 'set_description', 'set_source_account', 'set_destination_account']),
              help="Action to take")
@click.option("--action-value", help="Action value (e.g., category name)")
@click.option("--rule-group-id", type=int, help="Rule group ID")
@click.option("--priority", default=0, type=int, help="Priority (lower = higher priority)")
@click.option("--notes", help="Notes")
def rules_create(title, trigger, value, action, action_value, rule_group_id, priority, notes):
    """Create a new rule"""
    backend = get_backend()

    data = {
        "title": title,
        "triggers": [{"type": trigger, "value": value}],
        "actions": [{"type": action, "value": action_value or ""}],
        "priority": priority,
    }

    if rule_group_id:
        data["rule_group_id"] = rule_group_id
    if notes:
        data["notes"] = notes

    result = backend.create_rule(data)
    output(result)


@rules.command(name="update")
@click.option("--id", required=True, type=int, help="Rule ID")
@click.option("--title", help="Rule title")
@click.option("--trigger", help="Trigger type")
@click.option("--value", help="Trigger value")
@click.option("--action",
              type=click.Choice(['set_category', 'add_tag', 'remove_tag', 'set_description', 'set_source_account', 'set_destination_account']),
              help="Action type")
@click.option("--action-value", help="Action value")
@click.option("--rule-group-id", type=int, help="Rule group ID")
@click.option("--priority", type=int, help="Priority")
@click.option("--notes", help="Notes")
@click.option("--active", type=bool, help="Is active")
def rules_update(id, title, trigger, value, action, action_value, rule_group_id, priority, notes, active):
    """Update an existing rule"""
    backend = get_backend()

    data = {}
    if title:
        data["title"] = title
    if trigger and value:
        data["triggers"] = [{"type": trigger, "value": value}]
    if action:
        data["actions"] = [{"type": action, "value": action_value or ""}]
    if rule_group_id:
        data["rule_group_id"] = rule_group_id
    if priority is not None:
        data["priority"] = priority
    if notes:
        data["notes"] = notes
    if active is not None:
        data["active"] = active

    if not data:
        click.echo("Error: At least one update field is required", err=True)
        return

    result = backend.update_rule(id, data)
    output(result)


@rules.command(name="delete")
@click.option("--id", required=True, type=int, help="Rule ID")
@click.confirmation_option(prompt="Are you sure you want to delete this rule?")
def rules_delete(id):
    """Delete a rule"""
    backend = get_backend()
    result = backend.delete_rule(id)
    output(result)


@rules.command(name="test")
@click.option("--id", required=True, type=int, help="Rule ID")
@click.option("--data", help="JSON data for test")
def rules_test(id, data):
    """Test a rule against sample data"""
    backend = get_backend()
    test_data = data or {}
    result = backend.test_rule(id, test_data)
    output(result)


@rules.command(name="execute")
@click.option("--id", required=True, type=int, help="Rule ID")
def rules_execute(id):
    """Execute a rule against existing transactions"""
    backend = get_backend()
    result = backend.execute_rule(id)
    output(result)
