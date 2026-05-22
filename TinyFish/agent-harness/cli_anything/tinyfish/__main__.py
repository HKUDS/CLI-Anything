"""CLI harness wrapper for TinyFish - provides structured JSON output for AI agents."""

import click
from typing import List, Optional
import json


@click.group()
def cli():
    """TinyFish CLI Harness - Structured web automation commands with JSON output."""
    pass


@cli.command("search")
@click.argument("query")
@click.option("--location", default=None, help="Search location (country code)")
@click.option("--language", default="en", help="Language code for search results")
def search(query: str, location: Optional[str], language: str):
    """Execute web search query and return structured JSON results."""
    from cli_anything.tinyfish.core.search import search_query
    result = search_query(
        query=query,
        location=location,
        language=language
    )
    click.echo(json.dumps(result, indent=2))


@cli.command("fetch")
@click.argument("urls", nargs=-1)
@click.option("--include-images", is_flag=True, help="Include image URLs in output")
@click.option("--metadata", is_flag=True, help="Extract page metadata headers")
def fetch(urls: List[str], include_images: bool, metadata: bool):
    """Fetch content from URLs and return structured JSON results."""
    if not urls:
        click.echo(json.dumps({
            "status": "error", 
            "message": "No URLs provided"
        }))
        return
    
    from cli_anything.tinyfish.core.fetch import content_get
    result = content_get(
        urls=list(urls),
        include_images=include_images,
        include_metadata=metadata
    )
    click.echo(json.dumps(result, indent=2))


@cli.command("browser")
@click.argument("action")
@click.option("--url", default=None, help="Target URL for navigation actions")
def browser(action: str, url: Optional[str]):
    """Manage browser sessions via TinyFish - start/stop/navigate/screenshot."""
    from cli_anything.tinyfish.core.browser import session_manage
    
    if action not in ["start", "stop", "navigate", "screenshot"]:
        click.echo(json.dumps({
            "status": "error", 
            "message": f"Invalid action: {action}. Use start/stop/navigate/screenshot."
        }))
        return
        
    result = session_manage(action=action, url=url)
    click.echo(json.dumps(result, indent=2))


if __name__ == "__main__":
    cli()
