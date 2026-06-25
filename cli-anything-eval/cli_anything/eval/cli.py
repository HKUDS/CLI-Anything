"""`cli-anything-eval` console script and the per-harness eval command factory."""

from __future__ import annotations

import json

import click

from cli_anything.eval.runner import discover_tasks, run_eval
from cli_anything.eval.suite import run_suite


def build_eval_command(tasks_package: str, display_name: str = "") -> click.Group:
    @click.group("eval")
    def eval_group():
        """Run this harness's eval/benchmark tasks."""

    @eval_group.command("run")
    @click.option("-o", "--out-dir", default=None, help="Output directory for reports")
    @click.option("--baseline", "baseline_path", default=None, help="Baseline JSON to compare")
    @click.option("--update-baseline", is_flag=True, default=False, help="Write/update baseline")
    @click.option("--json", "as_json", is_flag=True, default=False, help="Print summary as JSON")
    @click.option("--fail-on-regression", is_flag=True, default=False,
                  help="Exit 1 if a regression is detected")
    def run_cmd(out_dir, baseline_path, update_baseline, as_json, fail_on_regression):
        result = run_eval(tasks_package, display_name=display_name, output_dir=out_dir,
                          baseline_path=baseline_path, update_baseline=update_baseline)
        summary = result["report"]["summary"]
        if as_json:
            click.echo(json.dumps(summary, indent=2))
        else:
            click.echo(f"{display_name or 'eval'}: {summary['passed']}/{summary['attempted']} "
                       f"passed ({summary['success_rate']:.2%}); skipped {summary['skipped']}")
            click.echo(f"Report: {result['paths']['report_md']}")
        comp = result.get("comparison")
        if fail_on_regression and comp and comp.get("regression"):
            raise SystemExit(1)

    @eval_group.command("list")
    def list_cmd():
        for t in discover_tasks(tasks_package):
            click.echo(f"{t.task_id}\t{t.name}")

    return eval_group


@click.group()
def main():
    """CLI-Anything evaluation / benchmark runner."""


@main.command("run")
@click.option("--harness", "tasks_package", required=True,
              help="Dotted tasks package, e.g. cli_anything.gimp.eval.tasks")
@click.option("--name", "display_name", default="", help="Display name for the report")
@click.option("-o", "--out-dir", default=None)
@click.option("--baseline", "baseline_path", default=None)
@click.option("--update-baseline", is_flag=True, default=False)
@click.option("--json", "as_json", is_flag=True, default=False)
def run_cmd(tasks_package, display_name, out_dir, baseline_path, update_baseline, as_json):
    result = run_eval(tasks_package, display_name=display_name, output_dir=out_dir,
                      baseline_path=baseline_path, update_baseline=update_baseline)
    summary = result["report"]["summary"]
    if as_json:
        click.echo(json.dumps(summary, indent=2))
    else:
        click.echo(f"{display_name or tasks_package}: {summary['passed']}/{summary['attempted']} "
                   f"passed ({summary['success_rate']:.2%}); skipped {summary['skipped']}")
        click.echo(f"Report: {result['paths']['report_md']}")


@main.command("suite")
@click.option("--harness", "harnesses", multiple=True,
              help="Limit to these harness names (repeatable)")
@click.option("-o", "--out-dir", default=None)
@click.option("--json", "as_json", is_flag=True, default=False)
def suite_cmd(harnesses, out_dir, as_json):
    result = run_suite(list(harnesses) or None, output_dir=out_dir)
    suite = result["suite"]
    if as_json:
        click.echo(json.dumps(suite, indent=2))
    else:
        for i, h in enumerate(suite["harnesses"], start=1):
            s = h["summary"]
            click.echo(f"{i}. {h['harness']}: {s['passed']}/{s['attempted']} "
                       f"({s['success_rate']:.2%})")
        click.echo(f"Leaderboard: {result['paths']['leaderboard_md']}")
