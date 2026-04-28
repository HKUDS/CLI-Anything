r"""
System information command group
"""

import click
from ..firefly_iii_cli import get_backend, output


@click.group()
def info():
    """System information"""
    pass


@info.command(name="about")
def info_about():
    """Get Firefly III system information"""
    backend = get_backend()
    result = backend.get_about()
    output(result)


@info.command(name="status")
def info_status():
    """Check Firefly III connection status"""
    try:
        backend = get_backend()
        result = backend.get_about()
        click.echo("Firefly III connection is normal")
        if 'data' in result:
            attrs = result['data'].get('attributes', {})
            click.echo(f"  Version: {attrs.get('version', 'N/A')}")
            click.echo(f"  API Version: {attrs.get('api_version', 'N/A')}")
            click.echo(f"  Environment: {attrs.get('environment', 'N/A')}")
    except Exception as e:
        click.echo(f"Connection failed: {e}", err=True)
