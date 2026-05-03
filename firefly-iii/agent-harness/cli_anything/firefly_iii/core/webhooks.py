r"""
Webhook management command group
"""

import click
from ..firefly_iii_cli import get_backend, output


@click.group()
def webhooks():
    """Manage webhooks"""
    pass


@webhooks.command(name="list")
@click.option("--limit", default=50, help="Limit results")
@click.option("--page", default=1, help="Page number")
def webhooks_list(limit, page):
    """List all webhooks"""
    backend = get_backend()
    params = {"limit": limit, "page": page}
    result = backend.get_webhooks(params)
    output(result)


@webhooks.command(name="get")
@click.option("--id", required=True, type=int, help="Webhook ID")
def webhooks_get(id):
    """Get webhook details"""
    backend = get_backend()
    result = backend.get_webhook(id)
    output(result)


@webhooks.command(name="create")
@click.option("--title", required=True, help="Webhook title")
@click.option("--trigger",
              type=click.Choice(['create', 'update', 'delete']),
              required=True,
              help="Trigger event type")
@click.option("--url", required=True, help="Webhook URL")
@click.option("--secret", help="Webhook secret")
@click.option("--active", default=True, type=bool, help="Is active")
@click.option("--events",
              type=click.Choice(['ANY', 'TRANSACTION_STORE', 'TRANSACTION_UPDATE', 'TRANSACTION_DESTROY',
                                 'JOURNAL_CREATE', 'JOURNAL_UPDATE', 'JOURNAL_DESTROY']),
              multiple=True,
              help="Events to trigger on")
def webhooks_create(title, trigger, url, secret, active, events):
    """Create a new webhook"""
    backend = get_backend()

    data = {
        "title": title,
        "trigger": trigger,
        "url": url,
        "active": active,
    }

    if secret:
        data["secret"] = secret
    if events:
        data["events"] = list(events)

    result = backend.create_webhook(data)
    output(result)


@webhooks.command(name="update")
@click.option("--id", required=True, type=int, help="Webhook ID")
@click.option("--title", help="Webhook title")
@click.option("--trigger",
              type=click.Choice(['create', 'update', 'delete']),
              help="Trigger event type")
@click.option("--url", help="Webhook URL")
@click.option("--secret", help="Webhook secret")
@click.option("--active", type=bool, help="Is active")
@click.option("--events",
              type=click.Choice(['ANY', 'TRANSACTION_STORE', 'TRANSACTION_UPDATE', 'TRANSACTION_DESTROY',
                                 'JOURNAL_CREATE', 'JOURNAL_UPDATE', 'JOURNAL_DESTROY']),
              multiple=True,
              help="Events to trigger on")
def webhooks_update(id, title, trigger, url, secret, active, events):
    """Update an existing webhook"""
    backend = get_backend()

    data = {}
    if title:
        data["title"] = title
    if trigger:
        data["trigger"] = trigger
    if url:
        data["url"] = url
    if secret:
        data["secret"] = secret
    if active is not None:
        data["active"] = active
    if events:
        data["events"] = list(events)

    if not data:
        click.echo("Error: At least one update field is required", err=True)
        return

    result = backend.update_webhook(id, data)
    output(result)


@webhooks.command(name="delete")
@click.option("--id", required=True, type=int, help="Webhook ID")
@click.confirmation_option(prompt="Are you sure you want to delete this webhook?")
def webhooks_delete(id):
    """Delete a webhook"""
    backend = get_backend()
    result = backend.delete_webhook(id)
    output(result)


@webhooks.command(name="trigger")
@click.option("--id", required=True, type=int, help="Webhook ID")
def webhooks_trigger(id):
    """Trigger a webhook manually"""
    backend = get_backend()
    result = backend.trigger_webhook(id)
    output(result)
