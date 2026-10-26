"""Deterministic fzf plan construction and environment policy."""

from __future__ import annotations

import hashlib
import json
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from cli_anything.fzf.core.capabilities import load_capabilities
from cli_anything.fzf.core.errors import PolicyError, ValidationError
from cli_anything.fzf.core.input import InputSource
from cli_anything.fzf.core.profiles import compose_profiles
from cli_anything.fzf.core.validation import (
    OptionValue,
    Policy,
    parse_expert_option,
    parse_option,
    validate_option_set,
)
from cli_anything.fzf.utils.fzf_backend import base_identity, minimal_environment, resolve_backend


_SECRET_NAME = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
_ENV_INPUTS = {item["name"]: item for item in load_capabilities()["environment"]["inputs"]}
_SAFE_ENV = {"TERM", "LANG", "LC_ALL", "NO_COLOR"}


@dataclass
class ExecutionPlan:
    """Serializable evidence plus runtime-only environment and bytes."""

    public: dict[str, Any]
    environment: dict[str, str]
    input_bytes: bytes | None

    def as_dict(self) -> dict[str, Any]:
        return self.public


EnvironmentPreparation = tuple[
    dict[str, str], dict[str, Any], list[OptionValue], list[dict[str, str]], set[str]
]


def _redact(name: str, value: str) -> str:
    if name == "FZF_API_KEY" or any(marker in name.upper() for marker in _SECRET_NAME):
        fingerprint = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
        return f"<redacted sha256:{fingerprint}>"
    return value


def _parse_env_pair(raw: str) -> tuple[str, str]:
    name, separator, value = raw.partition("=")
    if not separator or not name:
        raise ValidationError("environment_invalid", "Environment entries must be NAME=VALUE")
    if not (name.replace("_", "A").isalnum() and not name[0].isdigit()):
        raise ValidationError("environment_invalid", f"Invalid environment name: {name!r}")
    if "\x00" in value:
        raise ValidationError("environment_invalid", "Environment values cannot contain NUL bytes")
    return name, value


def _options_from_default_string(value: str, source: str) -> list[OptionValue]:
    try:
        tokens = shlex.split(value, posix=True)
    except ValueError as exc:
        raise ValidationError("default_opts_invalid", f"Could not parse {source}: {exc}") from exc
    options: list[OptionValue] = []
    for token in tokens:
        if not token.startswith("--"):
            raise ValidationError(
                "default_opts_invalid",
                f"{source} must use one --long-option or --long-option=value token per option",
                details={"token": token},
            )
        options.append(parse_option(token, source=source))
    return options


def build_option_values(
    *,
    raw_options: Iterable[str] = (),
    bindings: Iterable[str] = (),
    profile_paths: Iterable[str] = (),
    expert_options: Iterable[str] = (),
    policy: Policy,
) -> tuple[list[OptionValue], dict[str, Any]]:
    """Compose profiles and direct declarative values in stable order."""

    paths = list(profile_paths)
    composition = compose_profiles(paths) if paths else {"profiles": [], "resolved_options": []}
    options = list(composition["resolved_options"])
    options.extend(parse_option(raw) for raw in raw_options)
    options.extend(parse_option(f"bind={binding}") for binding in bindings)
    options.extend(parse_expert_option(raw, policy) for raw in expert_options)
    return options, {"profiles": composition["profiles"]}


def prepare_environment(
    *,
    env_policy: str,
    set_env: Iterable[str],
    policy: Policy,
    interactive: bool,
) -> EnvironmentPreparation:
    if env_policy not in {"isolated", "inherit"}:
        raise ValidationError("environment_policy_invalid", f"Unknown environment policy: {env_policy}")
    refusals: list[dict[str, str]] = []
    effects: set[str] = set()
    if env_policy == "inherit":
        if not policy.allow_env_inherit:
            refusals.append({"environment": "inherit", "reason": "requires allow-env-inherit"})
            env = minimal_environment(interactive=interactive)
            inherited_names: list[str] = []
        else:
            env = dict(os.environ)
            inherited_names = sorted(env)
    else:
        env = minimal_environment(interactive=interactive)
        inherited_names = []

    pairs = [_parse_env_pair(raw) for raw in set_env]
    names = [name for name, _ in pairs]
    for name in names:
        if names.count(name) > 1:
            raise ValidationError(
                "environment_duplicate", f"Environment variable {name} was supplied more than once"
            )
    if {"FZF_DEFAULT_OPTS", "FZF_DEFAULT_OPTS_FILE"} <= set(names):
        raise ValidationError(
            "environment_conflict",
            "FZF_DEFAULT_OPTS and FZF_DEFAULT_OPTS_FILE cannot be composed together",
        )

    env_options: list[OptionValue] = []
    explicit: dict[str, str] = {}
    for name, value in pairs:
        if name == "FZF_API_KEY":
            raise PolicyError(
                "api_key_argv_denied",
                "FZF_API_KEY cannot be supplied as command text; listener commands require --api-key-file",
            )
        if name not in _ENV_INPUTS and name not in _SAFE_ENV:
            raise PolicyError(
                "environment_variable_denied",
                f"Environment variable {name} is not on the explicit fzf allowlist",
            )
        if name == "FZF_DEFAULT_COMMAND":
            effects.add("subprocess_capable")
            if not policy.allow_command_actions:
                refusals.append({"environment": name, "reason": "requires allow-command-actions"})
        elif name == "FZF_DEFAULT_OPTS":
            parsed = _options_from_default_string(value, name)
            env_options.extend(parsed)
        elif name == "FZF_DEFAULT_OPTS_FILE":
            effects.update({"filesystem_reading", "subprocess_capable"})
            if not policy.allow_default_opts_file:
                refusals.append({"environment": name, "reason": "requires allow-default-opts-file"})
            else:
                path = Path(value).expanduser().resolve(strict=False)
                if not path.is_file():
                    raise ValidationError("default_opts_file_invalid", f"Options file does not exist: {path}")
                try:
                    content = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as exc:
                    raise ValidationError("default_opts_file_invalid", str(exc)) from exc
                env_options.extend(_options_from_default_string(content, str(path)))
                value = str(path)
        elif name == "SHELL":
            effects.add("subprocess_capable")
            if not policy.allow_command_actions:
                refusals.append({"environment": name, "reason": "requires allow-command-actions"})
        explicit[name] = value
        env[name] = value

    removed = sorted(
        name
        for name in os.environ
        if name.startswith("FZF_") and name not in explicit
    )
    # An inherited environment can contain arbitrary credentials. Its names
    # are useful audit evidence, but its values must never enter a plan or JSON
    # result. Only isolated mode's small constructed environment is safe to
    # enumerate as name/value pairs.
    constructed = (
        {name: _redact(name, value) for name, value in sorted(env.items()) if name not in explicit}
        if env_policy == "isolated" or not policy.allow_env_inherit
        else {}
    )
    delta = {
        "policy": env_policy,
        "set": {name: _redact(name, value) for name, value in sorted(explicit.items())},
        "constructed": constructed,
        "removed_ambient": removed if env_policy == "isolated" else [],
        "inherited_names": inherited_names,
    }
    return env, delta, env_options, refusals, effects


def build_plan(
    *,
    backend_override: str | None,
    mode: str,
    options: list[OptionValue],
    input_source: InputSource,
    policy: Policy,
    dry_run: bool,
    timeout: float,
    env_policy: str = "isolated",
    set_env: Iterable[str] = (),
    expected_output: str = "selection-records",
    surface: str = "declarative",
    profile_metadata: dict[str, Any] | None = None,
    prepared_environment: EnvironmentPreparation | None = None,
) -> ExecutionPlan:
    """Build a complete, non-executing plan for one bounded operation."""

    if not 0.05 <= timeout <= 3600:
        raise ValidationError("timeout_invalid", "Timeout must be between 0.05 and 3600 seconds")
    path = resolve_backend(backend_override)
    runtime_env, env_delta, env_options, env_refusals, env_effects = (
        prepared_environment
        if prepared_environment is not None
        else prepare_environment(
            env_policy=env_policy,
            set_env=set_env,
            policy=policy,
            interactive=mode in {"select", "listener"},
        )
    )
    all_options = [*env_options, *options]
    analysis = validate_option_set(all_options, policy, surface=surface)
    analysis["refusals"].extend(env_refusals)
    effects = set(analysis["effects"]) | env_effects
    if input_source.kind == "file":
        effects.add("filesystem_reading")
    if input_source.kind == "walker":
        effects.add("filesystem_reading")
        roots = [item.value for item in all_options if item.name == "walker-root" and item.value]
        if not roots:
            analysis["refusals"].append(
                {"input": "backend-walker", "reason": "an explicit --option walker-root=DIR is required"}
            )
        home = Path.home().resolve()
        resolved_roots = [Path(root).expanduser().resolve(strict=False) for root in roots]
        broad = any(root == Path("/").resolve() or home.is_relative_to(root) for root in resolved_roots)
        if broad and not policy.allow_broad_walker:
            analysis["refusals"].append(
                {"input": "backend-walker", "reason": "root or home traversal requires allow-broad-walker"}
            )
    argv = [str(path), *(option.argv_token() for option in options)]
    public: dict[str, Any] = {
        "schema_version": "cli-anything-fzf-plan/v1",
        "mode": mode,
        "dry_run": dry_run,
        "executed": False,
        "backend": base_identity(path),
        "argv": argv,
        "stdin": input_source.description,
        "environment_delta": env_delta,
        "effect_classes": sorted(effects),
        "hazards": analysis["hazards"],
        "policy_grants": policy.grants(),
        "refused": bool(analysis["refusals"]),
        "refusal_reasons": analysis["refusals"],
        "expected_output": expected_output,
        "timeout_seconds": timeout,
        "profiles": (profile_metadata or {}).get("profiles", []),
        "option_sources": [
            {"option": item.argv_token(), "source": item.source} for item in all_options
        ],
    }
    refresh_plan_id(public)
    return ExecutionPlan(public=public, environment=runtime_env, input_bytes=input_source.data)


def refresh_plan_id(public: dict[str, Any]) -> None:
    """Seal the current public plan after command-specific annotations."""

    public.pop("plan_id", None)
    canonical = json.dumps(public, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    public["plan_id"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def annotate_plan(
    plan: ExecutionPlan,
    *,
    annotations: dict[str, Any] | None = None,
    effects: Iterable[str] = (),
    hazards: Iterable[dict[str, str]] = (),
    refusals: Iterable[dict[str, str]] = (),
) -> None:
    """Add command-surface evidence and reseal a plan deterministically."""

    plan.public.update(annotations or {})
    plan.public["effect_classes"] = sorted(set(plan.public["effect_classes"]) | set(effects))
    plan.public["hazards"].extend(hazards)
    plan.public["refusal_reasons"].extend(refusals)
    plan.public["refused"] = bool(plan.public["refusal_reasons"])
    refresh_plan_id(plan.public)


def assert_executable(plan: ExecutionPlan) -> None:
    """Refuse execution while preserving refusal reasons in dry-run output."""

    if plan.public["refused"]:
        raise PolicyError(
            "plan_refused",
            "The requested fzf plan violates default-deny policy",
            details={
                "plan_id": plan.public["plan_id"],
                "refusals": plan.public["refusal_reasons"],
            },
        )
