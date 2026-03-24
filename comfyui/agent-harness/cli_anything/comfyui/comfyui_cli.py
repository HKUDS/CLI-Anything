#!/usr/bin/env python3
"""ComfyUI CLI — Manage AI image generation from the command line.

This CLI wraps the ComfyUI REST API. It covers the full generation lifecycle:
workflow management, queue operations, model discovery, and image retrieval.

Usage:
    # Check server status
    cli-anything-comfyui system stats

    # List available checkpoints
    cli-anything-comfyui models checkpoints

    # Queue a workflow
    cli-anything-comfyui queue prompt --workflow my_workflow.json

    # Check queue
    cli-anything-comfyui queue status

    # Download images
    cli-anything-comfyui images download --filename ComfyUI_00001_.png --output ./out.png

    # Interactive REPL
    cli-anything-comfyui repl
"""

import sys
import os
import json
import shlex
import click
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli_anything.comfyui.core import workflows as workflow_mod
from cli_anything.comfyui.core import queue as queue_mod
from cli_anything.comfyui.core import models as models_mod
from cli_anything.comfyui.core import images as images_mod
from cli_anything.comfyui.utils.comfyui_backend import api_get, DEFAULT_BASE_URL
from cli_anything.comfyui.core.session import Session

# ── Global State ────────────────────────────────────────────────
_json_output = False
_base_url = DEFAULT_BASE_URL
_session: Optional[Session] = None


def get_session(project_path: Optional[str] = None) -> Session:
    global _session
    if _session is None:
        _session = Session(project_path)
    return _session


def output(data, message: str = ""):
    """Print output in JSON or human-readable format."""
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        if isinstance(data, dict):
            _print_dict(data)
        elif isinstance(data, list):
            _print_list(data)
        else:
            click.echo(str(data))


def _print_dict(d: dict, indent: int = 0):
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            click.echo(f"{prefix}{k}:")
            _print_dict(v, indent + 1)
        elif isinstance(v, list):
            click.echo(f"{prefix}{k}:")
            _print_list(v, indent + 1)
        else:
            click.echo(f"{prefix}{k}: {v}")


def _print_list(items: list, indent: int = 0):
    prefix = "  " * indent
    for i, item in enumerate(items):
        if isinstance(item, dict):
            click.echo(f"{prefix}[{i}]")
            _print_dict(item, indent + 1)
        else:
            click.echo(f"{prefix}- {item}")


def handle_error(func):
    """Decorator for consistent error handling."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if _json_output:
                click.echo(json.dumps({
                    "error": str(e),
                    "type": type(e).__name__,
                }))
            else:
                click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


# ── Main CLI Group ──────────────────────────────────────────────
@click.group(invoke_without_command=True)
@click.option("--project", "-p", type=click.Path(), help="Path to the JSON project file")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.option("--url", default=DEFAULT_BASE_URL, show_default=True,
              help="ComfyUI server URL")
@click.pass_context
def cli(ctx, project, use_json, url):
    """ComfyUI CLI — AI image generation from the command line.

    Run without a subcommand to enter interactive REPL mode.
    """
    global _json_output, _base_url
    _json_output = use_json
    _base_url = url
    
    # Load session if project path is provided
    get_session(project)

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── Workflow Commands ───────────────────────────────────────────
@cli.group()
def workflow():
    """Workflow file management."""
    pass


@workflow.command("list")
@click.argument("directory", default=".", type=click.Path())
@handle_error
def workflow_list(directory):
    """List workflow JSON files in a directory."""
    result = workflow_mod.list_workflows(directory)
    output(result, f"Workflows in {directory}:")


@workflow.command("load")
@click.argument("path", type=click.Path(exists=True))
@handle_error
def workflow_load(path):
    """Load and display a workflow JSON file."""
    result = workflow_mod.load_workflow(path)
    output(result, f"Workflow: {path}")


@workflow.command("validate")
@click.argument("path", type=click.Path(exists=True))
@handle_error
def workflow_validate(path):
    """Validate the structure of a workflow JSON file."""
    wf = workflow_mod.load_workflow(path)
    result = workflow_mod.validate_workflow(wf)
    output(result, f"Validation: {path}")
    if result["valid"]:
        click.echo("  Workflow is valid.")
    else:
        click.echo(f"  {len(result['errors'])} error(s) found.", err=True)


# ── Queue Commands ──────────────────────────────────────────────
@cli.group()
def queue():
    """Prompt queue management."""
    pass


@queue.command("prompt")
@click.option("--workflow", "-w", required=True, type=click.Path(exists=True),
              help="Path to workflow JSON file (API format)")
@click.option("--client-id", default=None, help="Client ID for tracking")
@handle_error
def queue_prompt(workflow, client_id):
    """Queue a workflow for generation."""
    wf = workflow_mod.load_workflow(workflow)
    result = queue_mod.queue_prompt(_base_url, wf, client_id=client_id)
    output(result, f"Queued prompt: {result.get('prompt_id', '')}")


@queue.command("status")
@handle_error
def queue_status():
    """Show current queue status (running and pending items)."""
    result = queue_mod.get_queue_status(_base_url)
    output(result, "Queue status:")


@queue.command("clear")
@click.option("--confirm", is_flag=True, help="Skip confirmation")
@handle_error
def queue_clear(confirm):
    """Clear all pending items from the queue."""
    if not confirm:
        click.confirm("Clear the queue?", abort=True)
    result = queue_mod.clear_queue(_base_url)
    output(result, "Queue cleared.")


@queue.command("history")
@click.option("--max-items", type=int, default=None, help="Maximum entries to show")
@handle_error
def queue_history(max_items):
    """Show completed prompt history."""
    result = queue_mod.get_history(_base_url, max_items=max_items)
    output(result, f"History ({result.get('total', 0)} entries):")


@queue.command("interrupt")
@handle_error
def queue_interrupt():
    """Stop the currently running generation."""
    result = queue_mod.interrupt(_base_url)
    output(result, "Generation interrupted.")


# ── Models Commands ─────────────────────────────────────────────
@cli.group()
def models():
    """Model discovery commands."""
    pass


@models.command("checkpoints")
@handle_error
def models_checkpoints():
    """List available checkpoint models."""
    result = models_mod.list_checkpoints(_base_url)
    output(result, f"Checkpoints ({len(result)}):")


@models.command("loras")
@handle_error
def models_loras():
    """List available LoRA models."""
    result = models_mod.list_loras(_base_url)
    output(result, f"LoRAs ({len(result)}):")


@models.command("vaes")
@handle_error
def models_vaes():
    """List available VAE models."""
    result = models_mod.list_vaes(_base_url)
    output(result, f"VAEs ({len(result)}):")


@models.command("controlnets")
@handle_error
def models_controlnets():
    """List available ControlNet models."""
    result = models_mod.list_controlnets(_base_url)
    output(result, f"ControlNets ({len(result)}):")


@models.command("node-info")
@click.argument("node_class")
@handle_error
def models_node_info(node_class):
    """Get input/output schema for a node class (e.g., KSampler)."""
    result = models_mod.get_node_info(_base_url, node_class)
    output(result)


@models.command("list-nodes")
@handle_error
def models_list_nodes():
    """List all available node class names."""
    result = models_mod.list_all_node_classes(_base_url)
    output(result, f"Node classes ({len(result)}):")


# ── Images Commands ─────────────────────────────────────────────
@cli.group()
def images():
    """Image output management."""
    pass


@images.command("list")
@click.option("--prompt-id", required=True, help="Prompt ID to list images for")
@handle_error
def images_list(prompt_id):
    """List output images for a completed prompt."""
    result = images_mod.list_output_images(_base_url, prompt_id)
    output(result, f"Output images for {prompt_id}:")


@images.command("download")
@click.option("--filename", required=True, help="Image filename (e.g., ComfyUI_00001_.png)")
@click.option("--output", "output_path", required=True,
              type=click.Path(), help="Local path to save the image")
@click.option("--subfolder", default="", help="Subfolder in ComfyUI output dir")
@click.option("--type", "image_type", default="output",
              type=click.Choice(["output", "input", "temp"]),
              help="Image type")
@click.option("--overwrite", is_flag=True, help="Overwrite existing file")
@handle_error
def images_download(filename, output_path, subfolder, image_type, overwrite):
    """Download a single output image from ComfyUI."""
    result = images_mod.download_image(
        base_url=_base_url,
        filename=filename,
        output_path=output_path,
        subfolder=subfolder,
        image_type=image_type,
        overwrite=overwrite,
    )
    output(result, f"Downloaded: {output_path}")


@images.command("download-all")
@click.option("--prompt-id", required=True, help="Prompt ID to download images for")
@click.option("--output-dir", required=True,
              type=click.Path(), help="Directory to save images into")
@click.option("--overwrite", is_flag=True, help="Overwrite existing files")
@handle_error
def images_download_all(prompt_id, output_dir, overwrite):
    """Download all output images for a prompt to a directory."""
    result = images_mod.download_prompt_images(
        base_url=_base_url,
        prompt_id=prompt_id,
        output_dir=output_dir,
        overwrite=overwrite,
    )
    output(result, f"Downloaded {len(result)} image(s) to {output_dir}")


# ── System Commands ─────────────────────────────────────────────
@cli.group()
def system():
    """System information commands."""
    pass


@system.command("stats")
@handle_error
def system_stats():
    """Show GPU/memory system stats."""
    result = api_get(_base_url, "/system_stats")
    output(result, "System stats:")


@system.command("info")
@handle_error
def system_info():
    """Show ComfyUI server information."""
    result = api_get(_base_url, "/")
    output(result, "Server info:")


# ── REPL ─────────────────────────────────────────────────────────
@cli.command()
@handle_error
def repl():
    """Start interactive REPL session."""
    click.echo("ComfyUI CLI REPL — type 'help' for commands, 'quit' to exit")
    click.echo(f"Server: {_base_url}")

    try:
        api_get(_base_url, "/system_stats")
        click.echo("Connected to ComfyUI server.")
    except Exception as e:
        click.echo(f"Warning: Could not connect to ComfyUI: {e}", err=True)

    repl_commands = {
        "workflow":  "list|load|validate",
        "queue":     "prompt|status|clear|history|interrupt",
        "models":    "checkpoints|loras|vaes|controlnets|node-info|list-nodes",
        "images":    "list|download|download-all",
        "system":    "stats|info",
        "help":      "Show this help",
        "quit":      "Exit REPL",
    }

    while True:
        try:
            line = click.prompt("comfyui", prompt_suffix="> ", default="", show_default=False)
            line = line.strip()
            if not line:
                continue
            if line.lower() in ("quit", "exit", "q"):
                click.echo("Goodbye.")
                break
            if line.lower() == "help":
                for cmd, subs in repl_commands.items():
                    click.echo(f"  {cmd:<12} {subs}")
                continue

            try:
                args = shlex.split(line)
            except ValueError:
                args = line.split()
            try:
                cli.main(args, standalone_mode=False)
            except SystemExit:
                pass
            except click.exceptions.UsageError as e:
                click.echo(f"Usage error: {e}", err=True)
            except Exception as e:
                click.echo(f"Error: {e}", err=True)

        except (EOFError, KeyboardInterrupt):
            click.echo("\nGoodbye.")
            break


# ── Entry Point ──────────────────────────────────────────────────
def main():
    cli()


if __name__ == "__main__":
    main()
