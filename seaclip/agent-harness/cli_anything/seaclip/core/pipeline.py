"""Pipeline commands for SeaClip CLI."""

import json as json_mod

import click

from ..utils.seaclip_backend import SeaClipBackend


@click.group("pipeline")
def pipeline_group():
    """Manage the agent pipeline."""


@pipeline_group.command("start")
@click.option("--issue", "issue_id", required=True, help="Issue UUID to start pipeline for")
@click.option("--mode", default="auto", type=click.Choice(["auto", "manual"]), help="Pipeline mode")
@click.pass_context
def pipeline_start(ctx, issue_id, mode):
    """Start the pipeline for an issue."""
    backend: SeaClipBackend = ctx.obj["backend"]
    skin = ctx.obj.get("skin")
    as_json = ctx.obj.get("json", False)

    try:
        result = backend.start_pipeline(issue_id, mode=mode)
    except Exception as e:
        if as_json:
            click.echo(json_mod.dumps({"error": str(e)}))
        elif skin:
            skin.error(f"Failed to start pipeline: {e}")
        raise SystemExit(1)

    if as_json:
        click.echo(json_mod.dumps(result, indent=2))
    elif skin:
        skin.success(f"Pipeline started for {issue_id[:8]} (mode: {mode})")


@pipeline_group.command("status")
@click.option("--issue", "issue_id", required=True, help="Issue UUID")
@click.pass_context
def pipeline_status(ctx, issue_id):
    """Get pipeline status for an issue."""
    backend: SeaClipBackend = ctx.obj["backend"]
    skin = ctx.obj.get("skin")
    as_json = ctx.obj.get("json", False)

    try:
        result = backend.pipeline_status(issue_id)
    except Exception as e:
        if as_json:
            click.echo(json_mod.dumps({"error": str(e)}))
        elif skin:
            skin.error(f"Failed to get pipeline status: {e}")
        raise SystemExit(1)

    if as_json:
        click.echo(json_mod.dumps(result, indent=2))
    elif skin:
        skin.status_block({
            "Issue": str(result.get("issue_id", issue_id))[:8],
            "Stage": str(result.get("current_stage", "unknown")),
            "Status": str(result.get("status", "unknown")),
            "Mode": str(result.get("mode", "unknown")),
        }, title="Pipeline Status")


@pipeline_group.command("resume")
@click.option("--issue", "issue_id", required=True, help="Issue UUID")
@click.pass_context
def pipeline_resume(ctx, issue_id):
    """Resume a paused pipeline."""
    backend: SeaClipBackend = ctx.obj["backend"]
    skin = ctx.obj.get("skin")
    as_json = ctx.obj.get("json", False)

    try:
        result = backend.resume_pipeline(issue_id)
    except Exception as e:
        if as_json:
            click.echo(json_mod.dumps({"error": str(e)}))
        elif skin:
            skin.error(f"Failed to resume pipeline: {e}")
        raise SystemExit(1)

    if as_json:
        click.echo(json_mod.dumps(result, indent=2))
    elif skin:
        skin.success(f"Pipeline resumed for {issue_id[:8]}")


@pipeline_group.command("stop")
@click.option("--issue", "issue_id", required=True, help="Issue UUID")
@click.pass_context
def pipeline_stop(ctx, issue_id):
    """Stop a running pipeline."""
    backend: SeaClipBackend = ctx.obj["backend"]
    skin = ctx.obj.get("skin")
    as_json = ctx.obj.get("json", False)

    try:
        result = backend.stop_pipeline(issue_id)
    except Exception as e:
        if as_json:
            click.echo(json_mod.dumps({"error": str(e)}))
        elif skin:
            skin.error(f"Failed to stop pipeline: {e}")
        raise SystemExit(1)

    if as_json:
        click.echo(json_mod.dumps(result, indent=2))
    elif skin:
        skin.success(f"Pipeline stopped for {issue_id[:8]}")
