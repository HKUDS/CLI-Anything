"""Agent-usable Click surface for the real fzf backend."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable

import click

from cli_anything.fzf import __version__
from cli_anything.fzf.core.capabilities import (
    compare_live_options,
    expanded_options,
    filtered_capabilities,
    load_capabilities,
    load_schemas,
    resolve_option,
)
from cli_anything.fzf.core.errors import BackendError, HarnessError, PolicyError, ValidationError
from cli_anything.fzf.core.input import DEFAULT_MAX_BYTES, DEFAULT_MAX_ITEMS, InputSource, prepare_input
from cli_anything.fzf.core.listener import (
    listener_action,
    listener_action_plan,
    listener_result,
    listener_status,
    remove_stale_state,
    start_listener,
    stop_listener,
)
from cli_anything.fzf.core.planner import (
    ExecutionPlan,
    annotate_plan,
    assert_executable,
    build_option_values,
    build_plan,
    prepare_environment,
    refresh_plan_id,
)
from cli_anything.fzf.core.profiles import compose_profiles, load_profile, profile_output_path, write_profile
from cli_anything.fzf.core.results import exit_semantics, parse_benchmark, parse_output
from cli_anything.fzf.core.validation import (
    Policy,
    ensure_contained,
    parse_option,
    validate_listen_address,
)
from cli_anything.fzf.utils.fzf_backend import (
    base_identity,
    get_backend_document,
    probe_backend,
    resolve_backend,
    run_captured,
    terminate_process_group,
)


def _json_default(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def _emit_json(payload: dict[str, Any]) -> None:
    click.echo(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=_json_default))


def _emit(ctx: click.Context, command: str, data: Any, human: Callable[[Any], None] | None = None) -> None:
    if ctx.obj["json_mode"]:
        _emit_json({"ok": True, "command": command, "data": data})
    elif human:
        human(data)
    elif isinstance(data, str):
        click.echo(data)
    else:
        click.echo(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False, default=_json_default))


def _policy(ctx: click.Context) -> Policy:
    return Policy(**ctx.obj["policy"])


def _has_option(options: Iterable, name: str) -> bool:
    enabled = False
    for option in options:
        if option.name == name:
            enabled = True
        elif option.name == f"no-{name}":
            enabled = False
    return enabled


def _ctx_settings() -> dict[str, Any]:
    return {"help_option_names": ["-h", "--help"], "max_content_width": 110}


@click.group(invoke_without_command=True, context_settings=_ctx_settings())
@click.option("--json", "json_mode", is_flag=True, help="Emit stable JSON envelopes.")
@click.option("--backend", type=click.Path(dir_okay=False), help="Explicit fzf executable path.")
@click.option("--allow-version-mismatch", is_flag=True, help="Allow a backend other than pinned fzf 0.74.5.")
@click.option("--timeout", type=float, default=30.0, show_default=True, help="Backend timeout in seconds.")
@click.option("--dry-run", is_flag=True, help="Build and show the plan without starting fzf.")
@click.option("--env-policy", type=click.Choice(["isolated", "inherit"]), default="isolated", show_default=True)
@click.option("--set-env", multiple=True, metavar="NAME=VALUE", help="Set an allowlisted backend environment value.")
@click.option("--allow-command-actions", is_flag=True, help="Authorize fzf features that invoke a shell command.")
@click.option("--allow-filesystem-write", is_flag=True, help="Authorize history/profile filesystem writes.")
@click.option("--allow-walker", is_flag=True, help="Authorize fzf directory traversal with explicit roots.")
@click.option("--allow-broad-walker", is_flag=True, help="Authorize root/home directory walker roots.")
@click.option("--allow-network-listener", is_flag=True, help="Authorize TCP listener binding.")
@click.option("--allow-unsafe-listener", is_flag=True, help="Authorize fzf --listen-unsafe with other required grants.")
@click.option("--allow-env-inherit", is_flag=True, help="Authorize inheriting the entire current environment.")
@click.option("--allow-default-opts-file", is_flag=True, help="Authorize and validate FZF_DEFAULT_OPTS_FILE.")
@click.option("--allow-unknown-options", is_flag=True, help="Authorize the restricted forward-compatibility escape hatch.")
@click.version_option(__version__, prog_name="cli-anything-fzf")
@click.pass_context
def cli(
    ctx: click.Context,
    json_mode: bool,
    backend: str | None,
    allow_version_mismatch: bool,
    timeout: float,
    dry_run: bool,
    env_policy: str,
    set_env: tuple[str, ...],
    **policy_flags: bool,
) -> None:
    """Structured planning, filtering, selection, and listener control for fzf."""

    ctx.ensure_object(dict)
    ctx.obj.update(
        {
            "json_mode": json_mode,
            "backend": backend,
            "allow_version_mismatch": allow_version_mismatch,
            "timeout": timeout,
            "dry_run": dry_run,
            "env_policy": env_policy,
            "set_env": set_env,
            "policy": policy_flags,
        }
    )
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.group("backend")
def backend_group() -> None:
    """Inspect and verify the exact backend executable."""


@backend_group.command("inspect")
@click.pass_context
def backend_inspect(ctx: click.Context) -> None:
    """Show path, realpath, digest, version, and compatibility."""

    path = resolve_backend(ctx.obj["backend"])
    data = (
        base_identity(path)
        if ctx.obj["dry_run"]
        else probe_backend(path.as_posix(), allow_version_mismatch=ctx.obj["allow_version_mismatch"])
    )
    data["dry_run"] = ctx.obj["dry_run"]
    _emit(ctx, "backend.inspect", data)


def _backend_document(ctx: click.Context, kind: str) -> None:
    if ctx.obj["dry_run"]:
        path = resolve_backend(ctx.obj["backend"])
        _emit(
            ctx,
            f"backend.{kind}",
            {"dry_run": True, "executed": False, "backend": base_identity(path), "argv": [str(path), f"--{kind}"]},
        )
        return
    identity, content = get_backend_document(
        kind,
        ctx.obj["backend"],
        allow_version_mismatch=ctx.obj["allow_version_mismatch"],
        timeout=ctx.obj["timeout"],
    )
    if ctx.obj["json_mode"]:
        _emit(
            ctx,
            f"backend.{kind}",
            {
                "backend": identity,
                "text": content.decode("utf-8", "replace"),
                "byte_count": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            },
        )
    else:
        sys.stdout.buffer.write(content)
        sys.stdout.buffer.flush()


@backend_group.command("help")
@click.pass_context
def backend_help(ctx: click.Context) -> None:
    """Retrieve help directly from the real backend."""

    _backend_document(ctx, "help")


@backend_group.command("man")
@click.pass_context
def backend_man(ctx: click.Context) -> None:
    """Retrieve the rendered man page directly from the real backend."""

    _backend_document(ctx, "man")


@backend_group.command("verify-spec")
@click.pass_context
def backend_verify_spec(ctx: click.Context) -> None:
    """Compare all live help/man option headings with capabilities.json."""

    if ctx.obj["dry_run"]:
        path = resolve_backend(ctx.obj["backend"])
        _emit(
            ctx,
            "backend.verify-spec",
            {
                "dry_run": True,
                "executed": False,
                "backend": base_identity(path),
                "argv": [[str(path), "--help"], [str(path), "--man"]],
            },
        )
        return
    identity, help_bytes = get_backend_document(
        "help", ctx.obj["backend"], allow_version_mismatch=ctx.obj["allow_version_mismatch"]
    )
    _, man_bytes = get_backend_document(
        "man", ctx.obj["backend"], allow_version_mismatch=ctx.obj["allow_version_mismatch"]
    )
    comparison = compare_live_options(
        help_bytes.decode("utf-8", "replace"), man_bytes.decode("utf-8", "replace")
    )
    comparison.update(
        {
            "backend": identity,
            "help_sha256": hashlib.sha256(help_bytes).hexdigest(),
            "man_sha256": hashlib.sha256(man_bytes).hexdigest(),
        }
    )
    if not comparison["complete"]:
        raise ValidationError(
            "capability_coverage_incomplete",
            "Live fzf options are missing from the capability ledger",
            details=comparison,
        )
    _emit(ctx, "backend.verify-spec", comparison)


@cli.group("capability")
def capability_group() -> None:
    """Query the machine-readable option/action/event coverage contract."""


@capability_group.command("list")
@click.option("--category")
@click.option("--effect", type=click.Choice(load_capabilities()["effect_classes"]))
@click.option("--coverage", type=click.Choice(["implemented", "interactive-only", "refused-with-rationale"]))
@click.pass_context
def capability_list(ctx: click.Context, category: str | None, effect: str | None, coverage: str | None) -> None:
    """List options, optionally filtered by category/effect/coverage."""

    options = filtered_capabilities(category=category, effect=effect, coverage=coverage)

    def human(rows: list[dict[str, Any]]) -> None:
        for row in rows:
            click.echo(
                f"--{row['name']:<25} {row['category']:<20} {row['coverage']:<16} "
                f"{','.join(row['effects'])}"
            )

    _emit(ctx, "capability.list", {"count": len(options), "options": options}, lambda data: human(data["options"]))


@capability_group.command("show")
@click.argument("name")
@click.pass_context
def capability_show(ctx: click.Context, name: str) -> None:
    """Show one canonical option or documented alias."""

    option = resolve_option(name)
    if option is None:
        raise ValidationError("option_unknown", f"Unknown fzf option: {name}")
    _emit(ctx, "capability.show", option)


@capability_group.command("actions")
@click.pass_context
def capability_actions(ctx: click.Context) -> None:
    """Show every documented key/event action and its safety class."""

    _emit(ctx, "capability.actions", load_capabilities()["actions"])


@capability_group.command("events")
@click.pass_context
def capability_events(ctx: click.Context) -> None:
    """Show documented binding events and key grammar."""

    spec = load_capabilities()
    _emit(ctx, "capability.events", {"events": spec["events"], "key_grammar": spec["key_grammar"]})


@capability_group.command("export")
@click.pass_context
def capability_export(ctx: click.Context) -> None:
    """Export the complete capability specification."""

    _emit(ctx, "capability.export", load_capabilities())


@capability_group.command("schemas")
@click.pass_context
def capability_schemas(ctx: click.Context) -> None:
    """Export JSON Schemas for envelopes, plans, profiles, and state."""

    _emit(ctx, "capability.schemas", load_schemas())


def _plan_options(function: Callable) -> Callable:
    decorators = [
        click.option("--option", "raw_options", multiple=True, metavar="NAME[=VALUE]", help="Validated fzf option; repeatable."),
        click.option("--bind", "bindings", multiple=True, metavar="KEY[,KEY...]:ACTION", help="Validated binding; repeatable."),
        click.option("--profile", "profile_paths", multiple=True, type=click.Path(dir_okay=False), help="Explicit JSON profile; repeatable."),
        click.option("--expert-option", "expert_options", multiple=True, metavar="--LONG[=VALUE]", help="Restricted unknown long option."),
        click.option("--item", "items", multiple=True, help="Candidate item; repeatable."),
        click.option("--input-file", type=click.Path(dir_okay=False), help="Explicit candidate byte stream."),
        click.option("--input-base64", help="Exact candidate bytes as canonical base64."),
        click.option("--stdin", "use_stdin", is_flag=True, help="Read bounded candidate bytes from stdin."),
        click.option("--max-input-bytes", type=int, default=DEFAULT_MAX_BYTES, show_default=True),
        click.option("--max-items", type=int, default=DEFAULT_MAX_ITEMS, show_default=True),
    ]
    for decorator in reversed(decorators):
        function = decorator(function)
    return function


def _prepare(
    ctx: click.Context,
    *,
    mode: str,
    raw_options: tuple[str, ...],
    bindings: tuple[str, ...],
    profile_paths: tuple[str, ...],
    expert_options: tuple[str, ...],
    items: tuple[str, ...],
    input_file: str | None,
    input_base64: str | None,
    use_stdin: bool,
    max_input_bytes: int,
    max_items: int,
    prefix_options: list[str] | None = None,
    extra_options: list[str] | None = None,
    surface: str = "declarative",
    expected_output: str = "selection-records",
) -> tuple[ExecutionPlan, list]:
    policy = _policy(ctx)
    options, profile_metadata = build_option_values(
        raw_options=[*(prefix_options or []), *raw_options, *(extra_options or [])],
        bindings=bindings,
        profile_paths=profile_paths,
        expert_options=expert_options,
        policy=policy,
    )
    prepared_environment = prepare_environment(
        env_policy=ctx.obj["env_policy"],
        set_env=ctx.obj["set_env"],
        policy=policy,
        interactive=mode in {"select", "listener"},
    )
    effective_options = [*prepared_environment[2], *options]
    read0 = _has_option(effective_options, "read0")
    input_source = prepare_input(
        items=items,
        input_file=input_file,
        input_base64=input_base64,
        use_stdin=use_stdin,
        read0=read0,
        dry_run=ctx.obj["dry_run"],
        allow_walker=policy.allow_walker,
        max_bytes=max_input_bytes,
        max_items=max_items,
    )
    plan = build_plan(
        backend_override=ctx.obj["backend"],
        mode=mode,
        options=options,
        input_source=input_source,
        policy=policy,
        dry_run=ctx.obj["dry_run"],
        timeout=ctx.obj["timeout"],
        env_policy=ctx.obj["env_policy"],
        set_env=ctx.obj["set_env"],
        expected_output=expected_output,
        surface=surface,
        profile_metadata=profile_metadata,
        prepared_environment=prepared_environment,
    )
    return plan, effective_options


@cli.group("plan")
def plan_group() -> None:
    """Construct exact validated argv/environment/input plans."""


@plan_group.command("build")
@click.option("--mode", type=click.Choice(["filter", "select"]), required=True)
@click.option("--query", default="", help="Filter query or initial interactive query.")
@_plan_options
@click.pass_context
def plan_build(ctx: click.Context, mode: str, query: str, **kwargs: Any) -> None:
    """Build a plan without starting fzf, regardless of root --dry-run."""

    original = ctx.obj["dry_run"]
    ctx.obj["dry_run"] = True
    try:
        prefix = [] if mode == "filter" else ["no-tty-default"]
        extra = [f"filter={query}", "sync"] if mode == "filter" else [f"query={query}"]
        plan, _ = _prepare(
            ctx,
            mode=mode,
            prefix_options=prefix,
            extra_options=extra,
            expected_output=(
                "filter-records" if mode == "filter" else "interactive-selection-records"
            ),
            **kwargs,
        )
    finally:
        ctx.obj["dry_run"] = original
    _emit(ctx, "plan.build", plan.as_dict())


@cli.group("filter")
def filter_group() -> None:
    """Deterministic, synchronous, noninteractive matching."""


@filter_group.command("run")
@click.option("--query", default="", help="fzf filter query.")
@_plan_options
@click.pass_context
def filter_run(ctx: click.Context, query: str, **kwargs: Any) -> None:
    """Filter candidates with the real backend and preserve exact bytes."""

    plan, options = _prepare(
        ctx,
        mode="filter",
        extra_options=[f"filter={query}", "sync"],
        expected_output="filter-records",
        **kwargs,
    )
    benchmark = _has_option(options, "bench")
    if benchmark:
        plan.public["expected_output"] = "benchmark-report"
        refresh_plan_id(plan.public)
    if ctx.obj["dry_run"]:
        _emit(ctx, "filter.run", {"plan": plan.as_dict(), "result": None})
        return
    assert_executable(plan)
    identity = probe_backend(
        ctx.obj["backend"], allow_version_mismatch=ctx.obj["allow_version_mismatch"]
    )
    result = run_captured(
        plan.public["argv"],
        input_bytes=plan.input_bytes or b"",
        env=plan.environment,
        timeout=ctx.obj["timeout"],
    )
    print0 = _has_option(options, "print0")
    parsed = (
        parse_benchmark(result["stdout"])
        if benchmark
        else parse_output(
            result["stdout"],
            print0=print0,
            print_query=_has_option(options, "print-query"),
            expect=_has_option(options, "expect"),
        )
    )
    evidence = {
        "plan": {**plan.as_dict(), "executed": True, "backend": identity},
        "result": {
            **exit_semantics(result["exit_code"]),
            **parsed,
            "duration_ms": result["duration_ms"],
            "stderr": result["stderr"].decode("utf-8", "replace"),
            "stderr_base64": base64.b64encode(result["stderr"]).decode("ascii"),
        },
    }
    if ctx.obj["json_mode"]:
        _emit(ctx, "filter.run", evidence)
    else:
        sys.stdout.buffer.write(result["stdout"])
        sys.stdout.buffer.flush()
        if result["stderr"]:
            sys.stderr.buffer.write(result["stderr"])
            sys.stderr.buffer.flush()
    if result["exit_code"] != 0:
        ctx.exit(result["exit_code"])


@cli.group("session")
def session_group() -> None:
    """Bounded interactive fzf selection."""


@session_group.command("select")
@click.option("--query", default=None, help="Initial interactive query.")
@_plan_options
@click.pass_context
def session_select(ctx: click.Context, query: str | None, **kwargs: Any) -> None:
    """Run one safe interactive selection on the current terminal."""

    extra: list[str] = []
    if query is not None:
        extra.append(f"query={query}")
    plan, options = _prepare(
        ctx,
        mode="select",
        prefix_options=["no-tty-default"],
        extra_options=extra,
        expected_output="interactive-selection-records",
        **kwargs,
    )
    if ctx.obj["dry_run"]:
        _emit(ctx, "session.select", {"plan": plan.as_dict(), "result": None})
        return
    assert_executable(plan)
    if not sys.stderr.isatty():
        raise PolicyError("tty_required", "Interactive selection requires a TTY on stderr")
    identity = probe_backend(
        ctx.obj["backend"], allow_version_mismatch=ctx.obj["allow_version_mismatch"]
    )
    started = time.monotonic()
    walker_input = plan.public["stdin"]["kind"] == "backend-walker"
    process = subprocess.Popen(
        plan.public["argv"],
        stdin=None if walker_input else subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,
        env=plan.environment,
        start_new_session=True,
    )
    try:
        stdout, _ = process.communicate(
            input=None if walker_input else plan.input_bytes or b"",
            timeout=ctx.obj["timeout"],
        )
    except subprocess.TimeoutExpired as exc:
        terminate_process_group(process)
        raise BackendError(
            "backend_timeout",
            f"Interactive fzf exceeded the {ctx.obj['timeout']:g}s timeout",
            exit_code=124,
        ) from exc
    except KeyboardInterrupt as exc:
        terminate_process_group(process)
        raise BackendError("backend_interrupted", "Interactive fzf was interrupted", exit_code=130) from exc
    parsed = parse_output(
        stdout,
        print0=_has_option(options, "print0"),
        print_query=_has_option(options, "print-query"),
        expect=_has_option(options, "expect"),
    )
    evidence = {
        "plan": {**plan.as_dict(), "executed": True, "backend": identity},
        "result": {
            **exit_semantics(process.returncode),
            **parsed,
            "duration_ms": round((time.monotonic() - started) * 1000, 3),
        },
    }
    if ctx.obj["json_mode"]:
        _emit(ctx, "session.select", evidence)
    else:
        sys.stdout.buffer.write(stdout)
        sys.stdout.buffer.flush()
    if process.returncode != 0:
        ctx.exit(process.returncode)


@cli.group("profile")
def profile_group() -> None:
    """Create, inspect, validate, and compose explicit profiles."""


@profile_group.command("create")
@click.argument("output", type=click.Path(dir_okay=False))
@click.option("--name", required=True)
@click.option("--description", default="")
@click.option("--option", "options", multiple=True, metavar="NAME[=VALUE]")
@click.option("--bind", "bindings", multiple=True, metavar="KEY:ACTION")
@click.option("--overwrite", is_flag=True)
@click.pass_context
def profile_create(
    ctx: click.Context,
    output: str,
    name: str,
    description: str,
    options: tuple[str, ...],
    bindings: tuple[str, ...],
    overwrite: bool,
) -> None:
    """Write a validated profile with mode 0600."""

    policy = _policy(ctx)
    if not policy.allow_filesystem_write:
        raise PolicyError("filesystem_write_denied", "Profile creation requires --allow-filesystem-write")
    if ctx.obj["dry_run"]:
        for option in options:
            parse_option(option)
        for binding in bindings:
            parse_option(f"bind={binding}")
        output_path = profile_output_path(output)
        _emit(
            ctx,
            "profile.create",
            {
                "dry_run": True,
                "executed": False,
                "path": str(output_path),
                "overwrite": overwrite,
                "profile": {"name": name, "description": description, "options": list(options), "bindings": list(bindings)},
            },
        )
        return
    result = write_profile(
        output,
        name=name,
        description=description,
        options=list(options),
        bindings=list(bindings),
        overwrite=overwrite,
    )
    _emit(ctx, "profile.create", result)


@profile_group.command("inspect")
@click.argument("path", type=click.Path(dir_okay=False))
@click.pass_context
def profile_inspect(ctx: click.Context, path: str) -> None:
    """Validate a profile and show resolved option metadata."""

    profile = load_profile(path)
    resolved = [
        {"token": item.argv_token(), "source": item.source, "spec": item.spec}
        for item in profile.pop("resolved_options")
    ]
    profile["resolved"] = resolved
    _emit(ctx, "profile.inspect", profile)


@profile_group.command("compose")
@click.argument("paths", nargs=-1, required=True, type=click.Path(dir_okay=False))
@click.pass_context
def profile_compose(ctx: click.Context, paths: tuple[str, ...]) -> None:
    """Compose profiles in order and show deterministic precedence."""

    result = compose_profiles(list(paths))
    result.pop("resolved_options")
    _emit(ctx, "profile.compose", result)


@cli.group("config")
def config_group() -> None:
    """Inspect ambient fzf configuration without applying it."""


@config_group.command("inspect")
@click.option("--opts-file", type=click.Path(dir_okay=False), help="Explicit options file to inspect.")
@click.option("--include-contents", is_flag=True, help="Include parsed option tokens from the explicit file.")
@click.pass_context
def config_inspect(ctx: click.Context, opts_file: str | None, include_contents: bool) -> None:
    """Show fzf-related environment presence with API keys redacted."""

    names = ["FZF_DEFAULT_COMMAND", "FZF_DEFAULT_OPTS", "FZF_DEFAULT_OPTS_FILE", "FZF_API_KEY", "NO_COLOR", "SHELL"]
    environment: dict[str, Any] = {}
    for name in names:
        if name not in os.environ:
            environment[name] = {"present": False}
        elif name == "FZF_API_KEY":
            environment[name] = {
                "present": True,
                "value": "<redacted>",
                "sha256_prefix": hashlib.sha256(os.environ[name].encode("utf-8")).hexdigest()[:12],
            }
        else:
            environment[name] = {"present": True, "value": os.environ[name]}
    file_info = None
    if opts_file:
        path = Path(opts_file).expanduser().resolve(strict=False)
        if not path.is_file():
            raise ValidationError("default_opts_file_invalid", f"Options file does not exist: {path}")
        file_info = {"path": str(path), "size": path.stat().st_size}
        if include_contents:
            if not _policy(ctx).allow_default_opts_file:
                raise PolicyError("default_opts_file_denied", "Reading contents requires --allow-default-opts-file")
            content = path.read_text(encoding="utf-8")
            tokens = shlex.split(content)
            resolved = [parse_option(token).argv_token() for token in tokens]
            file_info.update({"sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(), "options": resolved})
    _emit(
        ctx,
        "config.inspect",
        {
            "environment": environment,
            "execution_default": "isolated",
            "ambient_values_applied": False,
            "opts_file": file_info,
        },
    )


@cli.group("shell")
def shell_group() -> None:
    """Retrieve shell integration emitted by the real backend."""


@shell_group.command("integration")
@click.argument("shell_name", type=click.Choice(["bash", "zsh", "fish", "nushell"]))
@click.pass_context
def shell_integration(ctx: click.Context, shell_name: str) -> None:
    """Print an integration script; never evaluates or installs it."""

    path = resolve_backend(ctx.obj["backend"])
    argv = [str(path), f"--{shell_name}"]
    if ctx.obj["dry_run"]:
        _emit(
            ctx,
            "shell.integration",
            {
                "dry_run": True,
                "executed": False,
                "backend": base_identity(path),
                "argv": argv,
                "effect_classes": ["pure"],
                "expected_output": "shell-script",
            },
        )
        return
    identity = probe_backend(str(path), allow_version_mismatch=ctx.obj["allow_version_mismatch"])
    result = run_captured(argv, timeout=ctx.obj["timeout"])
    if result["exit_code"] != 0:
        raise BackendError("shell_integration_failed", f"fzf --{shell_name} failed")
    if ctx.obj["json_mode"]:
        _emit(
            ctx,
            "shell.integration",
            {
                "backend": identity,
                "shell": shell_name,
                "script": result["stdout"].decode("utf-8", "replace"),
                "byte_count": len(result["stdout"]),
                "sha256": hashlib.sha256(result["stdout"]).hexdigest(),
            },
        )
    else:
        sys.stdout.buffer.write(result["stdout"])
        sys.stdout.buffer.flush()


@cli.group("listener")
def listener_group() -> None:
    """Own the start/status/action/stop lifecycle of an fzf listener."""


@listener_group.command("start")
@click.option("--state-dir", required=True, type=click.Path(file_okay=False))
@click.option("--address", help="Absolute .sock path or [HOST:]PORT; defaults inside state-dir.")
@click.option("--unsafe", is_flag=True, help="Use fzf --listen-unsafe (strong grants required).")
@click.option("--api-key-file", type=click.Path(dir_okay=False))
@click.option("--startup-timeout", type=float, default=5.0, show_default=True)
@_plan_options
@click.pass_context
def listener_start(
    ctx: click.Context,
    state_dir: str,
    address: str | None,
    unsafe: bool,
    api_key_file: str | None,
    startup_timeout: float,
    **kwargs: Any,
) -> None:
    """Start a detached owned listener, preferring a contained Unix socket."""

    requested_state = Path(state_dir).expanduser()
    if requested_state.is_symlink():
        raise PolicyError("listener_state_unsafe", "Listener state directory cannot be a symlink")
    resolved_state = requested_state.resolve(strict=False)
    if resolved_state in {Path("/"), Path.home().resolve()}:
        raise PolicyError("listener_state_unsafe", "Listener state directory is too broad")
    address = address or str(resolved_state / "fzf.sock")
    parsed_address = validate_listen_address(address)
    if parsed_address["kind"] == "unix":
        socket_path = Path(parsed_address["path"])
        if socket_path.exists() or socket_path.is_symlink():
            raise PolicyError(
                "socket_collision", f"Listener socket path already exists: {socket_path}"
            )
        parsed_address["path"] = str(ensure_contained(socket_path, resolved_state))
    address_arg = (
        parsed_address["path"]
        if parsed_address["kind"] == "unix"
        else f"{parsed_address['host']}:{parsed_address['port']}"
    )
    option_name = "listen-unsafe" if unsafe else "listen"
    plan, options = _prepare(
        ctx,
        mode="listener",
        prefix_options=["no-tty-default"],
        extra_options=[f"{option_name}={address_arg}"],
        expected_output="managed-listener",
        surface="listener",
        **kwargs,
    )
    listener_refusals: list[dict[str, str]] = []
    listener_hazards: list[dict[str, str]] = []
    policy = _policy(ctx)
    managed_listener_options = [
        option for option in options if option.name in {"listen", "listen-unsafe"}
    ]
    if len(managed_listener_options) != 1 or (
        managed_listener_options[0].name != option_name
        or managed_listener_options[0].value != address_arg
    ):
        listener_refusals.append(
            {
                "listener": "option-source",
                "reason": "listener addresses and safety mode are owned exclusively by listener start",
            }
        )
    if parsed_address["kind"] == "tcp":
        listener_hazards.append({"listener": "tcp", "reason": "network listener"})
        if int(parsed_address["port"]) == 0:
            raise ValidationError(
                "listener_address_invalid",
                "Managed TCP listeners require an explicit non-zero port for deterministic ownership",
            )
        if not policy.allow_network_listener:
            listener_refusals.append(
                {"listener": "tcp", "reason": "requires allow-network-listener"}
            )
        if not parsed_address["loopback"] and not api_key_file:
            listener_refusals.append(
                {"listener": "non-loopback", "reason": "requires api-key-file"}
            )
    if unsafe:
        listener_hazards.append(
            {"listener": "listen-unsafe", "reason": "permits command-capable remote actions"}
        )
        if not policy.allow_command_actions:
            listener_refusals.append(
                {"listener": "listen-unsafe", "reason": "requires allow-command-actions"}
            )
        if not api_key_file:
            listener_refusals.append(
                {"listener": "listen-unsafe", "reason": "requires api-key-file"}
            )
    annotate_plan(
        plan,
        annotations={
            "listener": {
                "state_dir": str(resolved_state),
                "address": parsed_address,
                "unsafe": unsafe,
                "api_key": "<redacted from file>" if api_key_file else None,
                "output_format": {
                    "print0": _has_option(options, "print0"),
                    "print_query": _has_option(options, "print-query"),
                    "expect": _has_option(options, "expect"),
                },
            }
        },
        effects=("subprocess_capable",) if unsafe else (),
        hazards=listener_hazards,
        refusals=listener_refusals,
    )
    if ctx.obj["dry_run"]:
        _emit(ctx, "listener.start", {"plan": plan.as_dict(), "result": None})
        return
    probe_backend(ctx.obj["backend"], allow_version_mismatch=ctx.obj["allow_version_mismatch"])
    result = start_listener(
        plan,
        state_dir_value=state_dir,
        address_value=address,
        unsafe=unsafe,
        api_key_file=api_key_file,
        policy=policy,
        startup_timeout=startup_timeout,
    )
    _emit(ctx, "listener.start", {"plan": {**plan.as_dict(), "executed": True}, "result": result})


@listener_group.command("status")
@click.option("--state-dir", required=True, type=click.Path(file_okay=False))
@click.option("--api-key-file", type=click.Path(dir_okay=False))
@click.option("--no-probe", is_flag=True, help="Read ownership state without HTTP GET.")
@click.option("--limit", type=int, default=100, show_default=True)
@click.option("--offset", type=int, default=0, show_default=True)
@click.pass_context
def listener_status_command(
    ctx: click.Context,
    state_dir: str,
    api_key_file: str | None,
    no_probe: bool,
    limit: int,
    offset: int,
) -> None:
    """Re-probe owned process identity and backend GET state."""

    result = listener_status(
        state_dir,
        api_key_file=api_key_file,
        probe=not no_probe,
        limit=limit,
        offset=offset,
    )
    _emit(ctx, "listener.status", result)


@listener_group.command("result")
@click.option("--state-dir", required=True, type=click.Path(file_okay=False))
@click.pass_context
def listener_result_command(ctx: click.Context, state_dir: str) -> None:
    """Read a bounded exact selection snapshot from an owned listener."""

    _emit(
        ctx,
        "listener.result",
        listener_result(state_dir, dry_run=ctx.obj["dry_run"]),
    )


@listener_group.command("action")
@click.option("--state-dir", required=True, type=click.Path(file_okay=False))
@click.option("--action", "action_value", required=True, help="One fzf action or + composition.")
@click.option("--api-key-file", type=click.Path(dir_okay=False))
@click.pass_context
def listener_action_command(
    ctx: click.Context, state_dir: str, action_value: str, api_key_file: str | None
) -> None:
    """Send one validated action to the owned listener."""

    if ctx.obj["dry_run"]:
        _emit(
            ctx,
            "listener.action",
            listener_action_plan(
                state_dir,
                action_value,
                policy=_policy(ctx),
                api_key_file=api_key_file,
            ),
        )
        return
    result = listener_action(
        state_dir, action_value, policy=_policy(ctx), api_key_file=api_key_file
    )
    _emit(ctx, "listener.action", result)


@listener_group.command("stop")
@click.option("--state-dir", required=True, type=click.Path(file_okay=False))
@click.option("--stop-timeout", type=float, default=3.0, show_default=True)
@click.option("--remove-state", is_flag=True, help="Remove state.json after verified cleanup.")
@click.pass_context
def listener_stop_command(
    ctx: click.Context, state_dir: str, stop_timeout: float, remove_state: bool
) -> None:
    """Stop only the PIDs proven to belong to this listener."""

    if ctx.obj["dry_run"]:
        status = listener_status(state_dir, probe=False)
        _emit(
            ctx,
            "listener.stop",
            {
                "dry_run": True,
                "executed": False,
                "would_signal": [pid for pid in (status.get("worker_pid"), status.get("backend_pid")) if pid],
                "remove_state": remove_state,
                "status": status,
            },
        )
        return
    _emit(ctx, "listener.stop", stop_listener(state_dir, timeout=stop_timeout, remove_state=remove_state))


@listener_group.command("clean-stale")
@click.option("--state-dir", required=True, type=click.Path(file_okay=False))
@click.pass_context
def listener_clean_stale(ctx: click.Context, state_dir: str) -> None:
    """Remove state only after recorded process identities are proven dead."""

    if ctx.obj["dry_run"]:
        _emit(ctx, "listener.clean-stale", {"dry_run": True, "executed": False, "status": listener_status(state_dir, probe=False)})
        return
    _emit(ctx, "listener.clean-stale", remove_stale_state(state_dir))


@cli.command("repl")
@click.pass_context
def repl(ctx: click.Context) -> None:
    """Enter a lightweight REPL that dispatches the same Click commands."""

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise PolicyError("tty_required", "The REPL requires an interactive terminal")
    try:
        from cli_anything.fzf.utils.repl_skin import ReplSkin

        skin = ReplSkin("fzf", version=__version__)
        skin.print_banner()
        prompt_session = skin.create_prompt_session()
        while True:
            try:
                line = skin.get_input(prompt_session)
            except (EOFError, KeyboardInterrupt):
                break
            if not line.strip():
                continue
            if line.strip() in {"quit", "exit"}:
                break
            try:
                args = shlex.split(line)
                cli.main(args=args, prog_name="cli-anything-fzf", standalone_mode=False)
            except HarnessError as exc:
                skin.error(str(exc))
            except click.ClickException as exc:
                skin.error(exc.format_message())
        skin.print_goodbye()
    except ImportError:
        raise BackendError("repl_unavailable", "prompt-toolkit/ReplSkin is not installed")


def main() -> None:
    """Console entry with deterministic JSON errors for both harness and Click failures."""

    json_mode = "--json" in sys.argv[1:]
    try:
        result = cli.main(prog_name="cli-anything-fzf", standalone_mode=False)
        # Click returns the code carried by ctx.exit() in non-standalone mode.
        # Propagate real backend exits after the JSON evidence has been emitted.
        if isinstance(result, int) and result != 0:
            raise SystemExit(result)
    except HarnessError as exc:
        if json_mode:
            _emit_json({"ok": False, "error": exc.as_dict()})
        else:
            click.echo(f"Error [{exc.code}]: {exc.message}", err=True)
            if exc.details:
                click.echo(json.dumps(exc.details, indent=2, sort_keys=True, ensure_ascii=False), err=True)
        raise SystemExit(exc.exit_code) from exc
    except click.ClickException as exc:
        if json_mode:
            _emit_json(
                {
                    "ok": False,
                    "error": {"code": "usage_error", "message": exc.format_message()},
                }
            )
        else:
            exc.show()
        raise SystemExit(exc.exit_code) from exc
    except click.exceptions.Exit as exc:
        raise SystemExit(exc.exit_code) from exc
    except BrokenPipeError:
        raise SystemExit(0)


if __name__ == "__main__":
    main()
