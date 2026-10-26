"""Load and compare the pinned fzf capability specification."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib.resources import files
from typing import Any, Iterable

from cli_anything.fzf.core.errors import ValidationError


_HEADING = re.compile(r"^\s{4,8}(?:[-+][^\s].*)$")
_LONG_OPTION = re.compile(r"--[a-z][a-z0-9-]*")


@lru_cache(maxsize=1)
def load_capabilities() -> dict[str, Any]:
    """Return the validated, immutable capability document."""

    path = files("cli_anything.fzf").joinpath("capabilities.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "cli-anything-fzf-capabilities/v1":
        raise ValidationError(
            "capability_schema_invalid",
            "Unsupported fzf capability schema",
            details={"schema_version": data.get("schema_version")},
        )
    names: set[str] = set()
    aliases: set[str] = set()
    valid_effects = set(data["effect_classes"])
    defaults = data["option_defaults"]
    for raw in data.get("options", []):
        name = raw.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
            raise ValidationError("capability_schema_invalid", f"Invalid option name: {name!r}")
        if name in names:
            raise ValidationError("capability_schema_invalid", f"Duplicate option: {name}")
        names.add(name)
        effects = set(raw.get("effects", defaults["effects"]))
        if not effects or not effects <= valid_effects:
            raise ValidationError(
                "capability_schema_invalid",
                f"Invalid effect classification for --{name}",
                details={"effects": sorted(effects)},
            )
        for alias in raw.get("aliases", []):
            if alias in aliases:
                raise ValidationError("capability_schema_invalid", f"Duplicate alias: {alias}")
            aliases.add(alias)
    negations = data.get("implicit_negations", [])
    if not isinstance(negations, list) or len(negations) != len(set(negations)):
        raise ValidationError("capability_schema_invalid", "Implicit negations must be a unique list")
    unknown_bases = sorted(set(negations) - names)
    if unknown_bases:
        raise ValidationError(
            "capability_schema_invalid",
            "Implicit negation references unknown options",
            details={"options": unknown_bases},
        )
    return data


@lru_cache(maxsize=1)
def load_schemas() -> dict[str, Any]:
    """Return the packaged JSON Schema bundle for agent-visible artifacts."""

    path = files("cli_anything.fzf").joinpath("schemas.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "cli-anything-fzf-schemas/v1":
        raise ValidationError("schema_bundle_invalid", "Unsupported JSON Schema bundle")
    return data


def expanded_options() -> list[dict[str, Any]]:
    """Return options with all schema defaults materialized."""

    data = load_capabilities()
    defaults = data["option_defaults"]
    return [{**defaults, **option} for option in data["options"]]


@lru_cache(maxsize=1)
def implicit_negative_options() -> list[dict[str, Any]]:
    """Materialize backend-probed `--no-*` forms not separately documented."""

    explicit = {option["name"]: option for option in expanded_options()}
    generated: list[dict[str, Any]] = []
    for base_name in load_capabilities()["implicit_negations"]:
        name = f"no-{base_name}"
        if name in explicit:
            continue
        base = explicit[base_name]
        effects = [effect for effect in base["effects"] if effect == "interactive_tty"] or ["pure"]
        generated.append(
            {
                **base,
                "name": name,
                "aliases": [],
                "arity": "none",
                "validator": "flag",
                "repeatable": False,
                "effects": effects,
                "policy": "none",
                "coverage": "implemented" if effects == ["pure"] else "interactive-only",
                "surface": "declarative",
                "implicit_negation_of": base_name,
            }
        )
    return generated


def all_options() -> list[dict[str, Any]]:
    """Return explicit records followed by supported implicit negations."""

    return [*expanded_options(), *implicit_negative_options()]


@lru_cache(maxsize=1)
def option_index() -> dict[str, dict[str, Any]]:
    """Index canonical names and aliases to expanded option records."""

    index: dict[str, dict[str, Any]] = {}
    for option in all_options():
        tokens = [option["name"], f"--{option['name']}", *option.get("aliases", [])]
        for token in tokens:
            if token in index and index[token]["name"] != option["name"]:
                raise ValidationError("capability_schema_invalid", f"Ambiguous option alias: {token}")
            index[token] = option
    return index


def resolve_option(name: str) -> dict[str, Any] | None:
    """Resolve a declarative name or documented alias."""

    return option_index().get(name) or option_index().get(name.removeprefix("--"))


def all_action_names() -> set[str]:
    """Return every explicitly named action in the pinned man page."""

    actions = load_capabilities()["actions"]
    return set(actions["pure"]) | set(actions["subprocess_capable"])


def subprocess_actions() -> set[str]:
    """Return command-bearing or dynamically hazardous actions."""

    return set(load_capabilities()["actions"]["subprocess_capable"])


def extract_option_headings(text: str) -> set[str]:
    """Extract long option names from help/man option-heading lines.

    This intentionally ignores option names in prose and examples. It is used
    to prove that the pinned ledger covers the live executable surface.
    """

    observed: set[str] = set()
    for line in text.splitlines():
        if _HEADING.match(line):
            observed.update(_LONG_OPTION.findall(line))
    return observed


def covered_long_options() -> set[str]:
    """Return canonical and aliased long options represented by the ledger."""

    covered: set[str] = set()
    for option in expanded_options():
        covered.add(f"--{option['name']}")
        covered.update(alias for alias in option.get("aliases", []) if alias.startswith("--"))
    return covered


def compare_live_options(help_text: str, man_text: str) -> dict[str, Any]:
    """Compare live option headings with the pinned capability ledger."""

    help_options = extract_option_headings(help_text)
    man_options = extract_option_headings(man_text)
    observed = help_options | man_options
    covered = covered_long_options()
    missing = sorted(observed - covered)
    return {
        "complete": not missing,
        "help_option_count": len(help_options),
        "man_option_count": len(man_options),
        "observed_option_count": len(observed),
        "ledger_option_count": len(expanded_options()),
        "implicit_negation_count": len(implicit_negative_options()),
        "available_option_count": len(all_options()),
        "missing_from_ledger": missing,
        "ledger_only": sorted(covered - observed),
    }


def filtered_capabilities(
    *, category: str | None = None, effect: str | None = None, coverage: str | None = None
) -> list[dict[str, Any]]:
    """Filter expanded option records for agent-facing inspection."""

    options: Iterable[dict[str, Any]] = all_options()
    if category:
        options = (item for item in options if item["category"] == category)
    if effect:
        options = (item for item in options if effect in item["effects"])
    if coverage:
        options = (item for item in options if item["coverage"] == coverage)
    return list(options)
