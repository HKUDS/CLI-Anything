"""CLI-Anything-Uni-Mol-Tools - Main CLI Entry Point"""

import click
import functools
import json
import sys
import os
from pathlib import Path
from typing import Optional

from .core import project as project_mod
from .core import train as train_mod
from .core import predict as predict_mod
from .core import session as session_mod
from .utils.repl_skin import ReplSkin


def get_json_mode(ctx=None):
    """Get JSON mode from context"""
    if ctx is None:
        try:
            ctx = click.get_current_context()
        except RuntimeError:
            return False
    return ctx.obj.get("json_output", False) if ctx.obj else False


def output(data, ctx=None):
    """Unified output function"""
    use_json = get_json_mode(ctx)
    if use_json:
        click.echo(json.dumps(data, indent=2))
    else:
        # Human-readable output
        if "status" in data:
            status = data["status"]
            if status == "error":
                click.secho(f"Error: {data.get('message', 'Unknown error')}", fg="red", err=True)
            elif status in ["created", "loaded", "saved", "completed"]:
                click.secho(f"✓ {status.capitalize()}", fg="green")

        for key, value in data.items():
            if key not in ["status", "message"]:
                if isinstance(value, (dict, list)):
                    click.echo(f"{key}: {json.dumps(value, indent=2)}")
                else:
                    click.echo(f"{key}: {value}")


def handle_error(func):
    """Error handling decorator"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Get context from args
        ctx = None
        for arg in args:
            if isinstance(arg, click.Context):
                ctx = arg
                break

        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_data = {
                "status": "error",
                "error": str(e),
                "type": type(e).__name__
            }
            use_json = get_json_mode(ctx) if ctx else False
            repl_mode = ctx.obj.get("repl_mode", False) if ctx and ctx.obj else False

            if use_json:
                click.echo(json.dumps(error_data))
            else:
                click.secho(f"Error: {e}", fg="red", err=True)
            if not repl_mode:
                sys.exit(1)
    return wrapper


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output JSON format")
@click.option("--project", "-p", "project_path", type=click.Path(), help="Project file path")
@click.option("--weight-dir", "-w", "weight_dir", type=click.Path(),
              help="Custom weight directory path (or set UNIMOL_WEIGHT_DIR env var)")
@click.version_option(version="1.0.0")
@click.pass_context
def cli(ctx, use_json, project_path, weight_dir):
    """CLI-Anything-Uni-Mol-Tools - Molecular ML for AI Agents

    A powerful CLI for molecular property prediction using Uni-Mol models.
    Supports classification, regression, and representation learning tasks.

    Set weight directory:
      export UNIMOL_WEIGHT_DIR=/path/to/weights
    Or use --weight-dir flag.
    """
    # Initialize context object
    if ctx.obj is None:
        ctx.obj = {}

    ctx.obj["json_output"] = use_json
    ctx.obj["repl_mode"] = False

    # Set weight directory if provided
    if weight_dir:
        os.environ['UNIMOL_WEIGHT_DIR'] = str(Path(weight_dir).absolute())
        if not use_json:
            click.secho(f"✓ Using weight directory: {weight_dir}", fg="green")

    # Load project if specified
    if project_path:
        try:
            session = session_mod.UniMolSession(project_path)
            ctx.obj["session"] = session
            ctx.obj["project_path"] = project_path
        except Exception as e:
            if use_json:
                click.echo(json.dumps({"error": f"Failed to load project: {e}"}))
            else:
                click.secho(f"Error loading project: {e}", fg="red", err=True)
            sys.exit(1)
    else:
        ctx.obj["session"] = None
        ctx.obj["project_path"] = None

    # If no command specified, enter REPL mode
    if ctx.invoked_subcommand is None:
        ctx.obj["repl_mode"] = True
        repl_cmd(ctx)


# Project management commands
@cli.group()
def project():
    """Manage Uni-Mol projects"""
    pass


@project.command("new")
@click.option("-n", "--name", required=True, help="Project name")
@click.option("-t", "--task", required=True,
              type=click.Choice(["classification", "regression", "multiclass",
                                "multilabel_classification", "multilabel_regression", "repr"]),
              help="Task type")
@click.option("-o", "--output-dir", default=".", help="Output directory")
@click.option("--model-name", default="unimolv1", help="Model name (unimolv1, unimolv2)")
@click.option("--model-size", default=None, help="Model size for v2 (84m, 164m, 310m, 570m, 1.1B)")
@handle_error
def project_new(name, task, output_dir, model_name, model_size):
    """Create a new Uni-Mol project"""
    result = project_mod.create_project(
        name=name,
        task=task,
        output_dir=output_dir,
        model_name=model_name,
        model_size=model_size
    )
    output(result)


@project.command("info")
@click.pass_context
@handle_error
def project_info(ctx):
    """Show project information"""
    session = ctx.obj.get("session")
    if not session:
        output({"status": "error", "message": "No project loaded. Use --project or create new project"})
        return

    load_result = project_mod.load_project(session.project_path)
    proj = load_result["project"]
    result = project_mod.get_project_info(proj)
    output(result)


@project.command("set-dataset")
@click.argument("dataset_type", type=click.Choice(["train", "valid", "test"]))
@click.argument("data_path", type=click.Path(exists=True))
@click.pass_context
@handle_error
def project_set_dataset(ctx, dataset_type, data_path):
    """Set dataset path for project"""
    session = ctx.obj.get("session")
    if not session:
        output({"status": "error", "message": "No project loaded"})
        return

    # Load project, set dataset, save project
    load_result = project_mod.load_project(session.project_path)
    proj = load_result["project"]  # Extract actual project dict
    result = project_mod.set_dataset(proj, dataset_type, data_path)
    project_mod.save_project(session.project_path, proj)

    output(result)


# Training commands
@cli.group()
def train():
    """Train molecular property prediction models"""
    pass


@train.command("start")
@click.option("--epochs", default=None, type=int, help="Number of epochs")
@click.option("--batch-size", default=None, type=int, help="Batch size")
@click.option("--lr", default=None, type=float, help="Learning rate")
@click.option("--gpus", default=None, type=int, help="Number of GPUs")
@click.pass_context
@handle_error
def train_start(ctx, epochs, batch_size, lr, gpus):
    """Start training a model"""
    session = ctx.obj.get("session")
    if not session:
        output({"status": "error", "message": "No project loaded"})
        return

    # Load project
    load_result = project_mod.load_project(session.project_path)
    proj = load_result["project"]

    # Apply config overrides
    if epochs is not None:
        proj["config"]["epochs"] = epochs
    if batch_size is not None:
        proj["config"]["batch_size"] = batch_size
    if lr is not None:
        proj["config"]["learning_rate"] = lr
    if gpus is not None:
        proj["config"]["gpus"] = gpus

    # Run training
    result = train_mod.run_training(proj)

    # Save updated project
    project_mod.save_project(session.project_path, proj)

    output(result)


@train.command("list")
@click.pass_context
@handle_error
def train_list(ctx):
    """List all training runs"""
    session = ctx.obj.get("session")
    if not session:
        output({"status": "error", "message": "No project loaded"})
        return

    # Load project
    load_result = project_mod.load_project(session.project_path)
    proj = load_result["project"]

    result = train_mod.list_runs(proj)
    output(result)


@train.command("show")
@click.argument("run_id")
@click.pass_context
@handle_error
def train_show(ctx, run_id):
    """Show details of a training run"""
    session = ctx.obj.get("session")
    if not session:
        output({"status": "error", "message": "No project loaded"})
        return

    # Load project
    load_result = project_mod.load_project(session.project_path)
    proj = load_result["project"]

    result = train_mod.get_run_details(proj, run_id)
    output(result)


# Prediction commands
@cli.group()
def predict():
    """Run predictions on molecular data"""
    pass


@predict.command("run")
@click.argument("run_id", required=True)
@click.argument("data_path", type=click.Path(exists=True))
@click.option("--output", "-o", "output_path", default=None, help="Output path for predictions")
@click.pass_context
@handle_error
def predict_run(ctx, run_id, data_path, output_path):
    """Run prediction using trained model"""
    session = ctx.obj.get("session")
    if not session:
        output({"status": "error", "message": "No project loaded"})
        return

    # Load project
    load_result = project_mod.load_project(session.project_path)
    proj = load_result["project"]

    result = predict_mod.run_prediction(
        proj,
        run_id,
        data_path,
        output_path=output_path
    )

    # Save updated project
    project_mod.save_project(session.project_path, proj)

    output(result)


@predict.command("list")
@click.pass_context
@handle_error
def predict_list(ctx):
    """List all predictions"""
    session = ctx.obj.get("session")
    if not session:
        output({"status": "error", "message": "No project loaded"})
        return

    # Load project
    load_result = project_mod.load_project(session.project_path)
    proj = load_result["project"]

    result = predict_mod.list_predictions(proj)
    output(result)


# Storage and cleanup commands
@cli.command("storage")
@click.pass_context
@handle_error
def storage_analysis(ctx):
    """Analyze storage usage"""
    from .core import storage as storage_mod

    session = ctx.obj.get("session")
    if not session:
        output({"status": "error", "message": "No project loaded"})
        return

    # Load project
    load_result = project_mod.load_project(session.project_path)
    proj = load_result["project"]

    # Analyze storage
    analysis = storage_mod.analyze_project_storage(proj)

    # Display results
    if get_json_mode():
        output(analysis)
    else:
        click.echo()
        click.secho("💾 Storage Analysis", fg="cyan", bold=True)
        click.echo("━" * 50)
        click.echo()

        # Total usage
        total_mb = analysis["total_mb"]
        click.echo(f"Total Usage: {storage_mod.format_size(total_mb * 1024 ** 2)}")
        click.echo()

        # Breakdown
        breakdown = analysis["breakdown"]

        # Show models, conformers, predictions
        for component in ["models", "conformers", "predictions"]:
            size_mb = breakdown[component]
            pct = breakdown[f"{component}_pct"]
            size_str = storage_mod.format_size(size_mb * 1024 ** 2)

            # Progress bar
            bar_width = 30
            filled = int(bar_width * pct / 100)
            bar = "█" * filled + "░" * (bar_width - filled)

            click.echo(f"  {component.capitalize():<12} {size_str:>8} ({pct:>5.1f}%)  {bar}")

        # Recommendations
        if analysis["recommendations"]:
            click.echo()
            click.secho("⚠️  Recommendations:", fg="yellow", bold=True)
            for rec in analysis["recommendations"]:
                savings_mb = rec["potential_savings_mb"]
                savings = storage_mod.format_size(savings_mb * 1024 ** 2)
                click.echo(f"   • {rec['message']} (save {savings})")

        click.echo()


@cli.group("models")
def models():
    """Model management commands"""
    pass


@models.command("rank")
@click.pass_context
@handle_error
def models_rank(ctx):
    """Rank and compare all models"""
    from .core import models_manager as models_mod

    session = ctx.obj.get("session")
    if not session:
        output({"status": "error", "message": "No project loaded"})
        return

    # Load project
    load_result = project_mod.load_project(session.project_path)
    proj = load_result["project"]

    # Rank models
    ranked = models_mod.rank_models(proj)

    if get_json_mode():
        output({"models": ranked})
    else:
        if not ranked:
            click.echo("No models found")
            return

        click.echo()
        click.secho("🏆 Model Ranking", fg="cyan", bold=True)
        click.echo("━" * 70)
        click.echo()

        # Header
        click.echo(f"{'Rank':<6} {'Run ID':<12} {'Score':<8} {'AUC':<8} {'Time':<10} {'Status':<10}")
        click.echo("─" * 70)

        # Rows
        for model in ranked:
            rank = model["rank"]
            if rank == 1:
                rank_str = click.style("🥇 1", fg="yellow", bold=True)
            elif rank == 2:
                rank_str = click.style("🥈 2", fg="white", bold=True)
            elif rank == 3:
                rank_str = click.style("🥉 3", fg="yellow")
            else:
                rank_str = f"   {rank}"

            run_id = model["run_id"]
            score = f"{model['score']}/10"
            auc = f"{model['auc']:.3f}"
            if model['auc'] >= 0.85:
                auc = click.style(auc + " ⭐", fg="green")

            duration = f"{model['duration_sec']:.1f}s"
            if model['duration_sec'] < 16:
                duration = click.style(duration + " ⚡", fg="cyan")

            status = model["status"]
            if status == "Best":
                status = click.style(status, fg="green", bold=True)
            elif status == "Poor":
                status = click.style(status, fg="red")

            click.echo(f"{rank_str:<6} {run_id:<12} {score:<8} {auc:<20} {duration:<18} {status}")

        # Best model recommendation
        best = ranked[0]
        click.echo()
        click.secho(f"💡 Recommendation: Use {best['run_id']} for production", fg="green")
        click.echo(f"   - Highest score ({best['score']}/10)")
        click.echo(f"   - AUC: {best['auc']:.4f}")
        click.echo()


@models.command("history")
@click.pass_context
@handle_error
def models_history(ctx):
    """Show model performance history"""
    from .core import models_manager as models_mod

    session = ctx.obj.get("session")
    if not session:
        output({"status": "error", "message": "No project loaded"})
        return

    # Load project
    load_result = project_mod.load_project(session.project_path)
    proj = load_result["project"]

    # Get history
    history = models_mod.get_model_history(proj)

    if get_json_mode():
        output(history)
    else:
        if not history["timeline"]:
            click.echo("No training history found")
            return

        click.echo()
        click.secho("📊 Model Performance History", fg="cyan", bold=True)
        click.echo("━" * 70)
        click.echo()

        # Timeline
        timeline = history["timeline"]
        click.echo(f"Total runs: {history['total_runs']}")
        click.echo(f"Trend: {history['trend']}")
        click.echo()

        # Simple text chart
        if len(timeline) >= 2:
            click.echo("AUC Progress:")
            for i, entry in enumerate(timeline):
                auc = entry["auc"]
                bar_len = int(auc * 50)  # Scale to 50 chars
                bar = "█" * bar_len
                click.echo(f"  {entry['run_id']:<12} │{bar} {auc:.4f}")

        # Insights
        if history["insights"]:
            click.echo()
            click.secho("💡 Insights:", fg="yellow")
            for insight in history["insights"]:
                icon = "✓" if insight["type"] in ["best_model", "trend"] else "⚠️"
                click.echo(f"   {icon} {insight['message']}")

        click.echo()


@models.command("best")
@click.pass_context
@handle_error
def models_best(ctx):
    """Show the best performing model"""
    from .core import models_manager as models_mod

    session = ctx.obj.get("session")
    if not session:
        output({"status": "error", "message": "No project loaded"})
        return

    # Load project
    load_result = project_mod.load_project(session.project_path)
    proj = load_result["project"]

    # Get best model
    best = models_mod.get_best_model(proj)

    if get_json_mode():
        output(best if best else {"error": "No models found"})
    else:
        if not best:
            click.echo("No models found")
            return

        click.echo()
        click.secho("⭐ Best Model", fg="cyan", bold=True)
        click.echo("━" * 50)
        click.echo()

        click.echo(f"Run ID:   {best['run_id']}")
        click.echo(f"AUC:      {best['metrics'].get('auc', 'N/A')}")
        if 'duration_sec' in best:
            click.echo(f"Duration: {best['duration_sec']:.1f}s")
        if 'timestamp' in best:
            click.echo(f"Created:  {best['timestamp']}")
        click.echo()


@models.command("compare")
@click.argument("run_id_1")
@click.argument("run_id_2")
@click.pass_context
@handle_error
def models_compare(ctx, run_id_1, run_id_2):
    """Compare two models side by side"""
    from .core import models_manager as models_mod

    session = ctx.obj.get("session")
    if not session:
        output({"status": "error", "message": "No project loaded"})
        return

    # Load project
    load_result = project_mod.load_project(session.project_path)
    proj = load_result["project"]

    # Compare models
    comparison = models_mod.compare_models(proj, [run_id_1, run_id_2])

    if get_json_mode():
        output(comparison)
    else:
        click.echo()
        click.secho(f"⚖️  Model Comparison", fg="cyan", bold=True)
        click.echo("━" * 50)
        click.echo()

        click.echo(f"Comparing: {run_id_1} vs {run_id_2}")
        click.echo()

        # Show overall winner if available
        overall_winner = comparison.get("overall_winner")
        if overall_winner:
            click.secho(f"Overall winner: {overall_winner}", fg="green")
            click.echo()

        # Show metrics comparison
        comparisons = comparison.get("comparisons", {})
        if comparisons and len(comparisons) > 0:
            click.secho("Metrics:", fg="yellow")
            for metric, data in comparisons.items():
                values = data.get("values", {})
                v1 = values.get(run_id_1)
                v2 = values.get(run_id_2)

                if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                    if v1 > v2:
                        winner = f"{run_id_1} wins"
                        v1_str = click.style(f"{v1:.4f}", fg="green")
                        v2_str = f"{v2:.4f}"
                    elif v2 > v1:
                        winner = f"{run_id_2} wins"
                        v1_str = f"{v1:.4f}"
                        v2_str = click.style(f"{v2:.4f}", fg="green")
                    else:
                        winner = "tie"
                        v1_str = f"{v1:.4f}"
                        v2_str = f"{v2:.4f}"
                else:
                    winner = "n/a"
                    v1_str = str(v1) if v1 is not None else "N/A"
                    v2_str = str(v2) if v2 is not None else "N/A"

                click.echo(f"  {metric:12} {v1_str:12} vs {v2_str:12}  ({winner})")
        else:
            click.echo()
            click.secho("⚠️  No metrics available for comparison", fg="yellow")
            click.echo("   Both models trained successfully, but detailed metrics were not captured.")
            click.echo()

        click.echo()


@cli.command("cleanup")
@click.option("--auto", is_flag=True, help="Auto-cleanup with default settings")
@click.option("--keep-best", default=3, help="Number of best models to keep")
@click.option("--min-auc", default=0.75, help="Minimum AUC to keep")
@click.pass_context
@handle_error
def cleanup_models(ctx, auto, keep_best, min_auc):
    """Interactive model cleanup"""
    from .core import models_manager as models_mod
    from .core import cleanup as cleanup_mod
    from .core import storage as storage_mod

    session = ctx.obj.get("session")
    if not session:
        output({"status": "error", "message": "No project loaded"})
        return

    # Load project
    load_result = project_mod.load_project(session.project_path)
    proj = load_result["project"]

    # Get suggestions
    suggestions = models_mod.suggest_deletable_models(proj, keep_best_n=keep_best, min_auc=min_auc)

    if get_json_mode():
        output(suggestions)
        return

    click.echo()
    click.secho("🧹 Model Cleanup Assistant", fg="cyan", bold=True)
    click.echo("━" * 70)
    click.echo()

    # Summary
    total_models = len(proj.get("runs", []))
    delete_count = len(suggestions["delete"])
    archive_count = len(suggestions["archive"])
    keep_count = len(suggestions["keep"])

    click.echo(f"Found {total_models} models")
    click.echo()

    if delete_count == 0 and archive_count == 0:
        click.secho("✓ No cleanup needed - all models are optimal!", fg="green")
        return

    # Show suggestions
    if delete_count > 0:
        click.secho(f"🗑️  Suggested for deletion ({delete_count} models):", fg="red")
        for item in suggestions["delete"]:
            click.echo(f"   • {item['run_id']}: {item['reason']}")
        click.echo()

    if archive_count > 0:
        click.secho(f"📦 Suggested for archival ({archive_count} models):", fg="yellow")
        for item in suggestions["archive"]:
            click.echo(f"   • {item['run_id']}: {item['reason']}")
        click.echo()

    if keep_count > 0:
        click.secho(f"✅ Will keep ({keep_count} models):", fg="green")
        for item in suggestions["keep"][:5]:  # Show first 5
            click.echo(f"   • {item['run_id']}: {item['reason']}")
        if keep_count > 5:
            click.echo(f"   ... and {keep_count - 5} more")
        click.echo()

    # Auto mode
    if auto:
        delete_ids = [item["run_id"] for item in suggestions["delete"]]
        archive_ids = [item["run_id"] for item in suggestions["archive"]]

        result = cleanup_mod.batch_cleanup(proj, delete_ids, archive_ids, confirm=True)

        if result.get("status") != "cancelled":
            # Save updated project
            project_mod.save_project(session.project_path, proj)

            # Show results
            click.echo()
            click.secho("✓ Cleanup Complete!", fg="green", bold=True)
            click.echo(f"  Deleted: {len(result.get('deleted', []))} models")
            click.echo(f"  Archived: {len(result.get('archived', []))} models")
            click.echo(f"  Failed: {len(result.get('failed', []))}")
            space_freed_mb = result.get('space_freed_mb', 0)
            click.echo(f"  Space freed: {storage_mod.format_size(space_freed_mb * 1024 * 1024)}")

    else:
        # Interactive mode
        click.echo("Actions:")
        click.echo("  1. Auto-clean (delete suggested, archive rest)")
        click.echo("  2. Delete all suggested")
        click.echo("  3. Archive all suggested")
        click.echo("  4. Cancel")
        click.echo()

        choice = click.prompt("Select", type=int, default=4)

        if choice == 1:
            delete_ids = [item["run_id"] for item in suggestions["delete"]]
            archive_ids = [item["run_id"] for item in suggestions["archive"]]
        elif choice == 2:
            delete_ids = [item["run_id"] for item in suggestions["delete"]] + \
                        [item["run_id"] for item in suggestions["archive"]]
            archive_ids = []
        elif choice == 3:
            delete_ids = []
            archive_ids = [item["run_id"] for item in suggestions["delete"]] + \
                         [item["run_id"] for item in suggestions["archive"]]
        else:
            click.echo("Cancelled")
            return

        result = cleanup_mod.batch_cleanup(proj, delete_ids, archive_ids, confirm=True)

        if result.get("status") != "cancelled":
            # Save updated project
            project_mod.save_project(session.project_path, proj)

            # Show results
            click.echo()
            click.secho("✓ Cleanup Complete!", fg="green", bold=True)
            click.echo(f"  Deleted: {len(result.get('deleted', []))} models")
            click.echo(f"  Archived: {len(result.get('archived', []))} models")
            space_freed_mb = result.get('space_freed_mb', 0)
            click.echo(f"  Space freed: {storage_mod.format_size(space_freed_mb * 1024 * 1024)}")


@cli.command("archive")
@click.argument("action", type=click.Choice(["list", "restore"]))
@click.argument("run_id", required=False)
@click.pass_context
@handle_error
def archive_command(ctx, action, run_id):
    """Manage archived models"""
    from .core import cleanup as cleanup_mod
    from .core import storage as storage_mod

    if action == "list":
        archives = cleanup_mod.list_archives()

        if get_json_mode():
            output({"archives": archives})
        else:
            if not archives:
                click.echo("No archives found")
                return

            click.echo()
            click.secho("📦 Archived Models", fg="cyan", bold=True)
            click.echo("━" * 70)
            click.echo()

            for archive in archives:
                size = storage_mod.format_size(archive["size"])
                click.echo(f"{archive['project_name']}/{archive['run_id']}")
                click.echo(f"  Size: {size}")
                click.echo(f"  Date: {archive['date']}")
                click.echo(f"  Path: {archive['path']}")
                click.echo()

    elif action == "restore":
        if not run_id:
            click.echo("Error: run_id required for restore")
            return

        session = ctx.obj.get("session")
        if not session:
            output({"status": "error", "message": "No project loaded"})
            return

        # Load project
        load_result = project_mod.load_project(session.project_path)
        proj = load_result["project"]

        # Restore
        result = cleanup_mod.restore_model(proj, run_id)

        if result["status"] == "restored":
            # Save updated project
            project_mod.save_project(session.project_path, proj)

        output(result)


@cli.command("repl", hidden=True)
@click.pass_context
def repl_cmd(ctx):
    """Enter interactive REPL mode"""
    ctx.obj["repl_mode"] = True

    # Create REPL skin
    repl = ReplSkin(
        cli_group=cli,
        ctx=ctx,
        prompt_prefix="unimol-tools",
        intro_text="Welcome to Uni-Mol Tools CLI! Type 'help' for available commands.",
    )

    # Start REPL
    repl.run()


def main():
    """Main entry point"""
    try:
        cli(obj={})
    except KeyboardInterrupt:
        click.echo("\nInterrupted", err=True)
        sys.exit(130)


if __name__ == "__main__":
    main()
