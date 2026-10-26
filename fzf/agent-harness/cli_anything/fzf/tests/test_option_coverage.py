"""Live 0.74.5 option/capability coverage gates."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from importlib.resources import files

from jsonschema import Draft202012Validator

from cli_anything.fzf.core.capabilities import (
    all_options,
    compare_live_options,
    expanded_options,
    implicit_negative_options,
    load_capabilities,
)
from cli_anything.fzf.core.validation import parse_option
from cli_anything.fzf.utils.fzf_backend import get_backend_document, probe_backend


def test_real_backend_compatibility_tuple_and_digest(backend):
    identity = probe_backend(str(backend))
    assert identity["version"] == "0.74.5"
    assert identity["revision"] == "c0a193e0"
    assert identity["compatible"] is True
    assert identity["sha256"] == "c8d3ac08594f271a108528beb15338c42be113d392816b10bf5955cd139293e8"


def test_live_help_and_man_hashes_match_pinned_sources(backend):
    _, help_bytes = get_backend_document("help", str(backend))
    _, man_bytes = get_backend_document("man", str(backend))
    spec = load_capabilities()["backend"]
    assert hashlib.sha256(help_bytes).hexdigest() == spec["help_sha256"]
    assert hashlib.sha256(man_bytes).hexdigest() == spec["man_sha256"]


def test_every_live_help_and_man_heading_is_covered(backend):
    _, help_bytes = get_backend_document("help", str(backend))
    _, man_bytes = get_backend_document("man", str(backend))
    result = compare_live_options(help_bytes.decode(), man_bytes.decode())
    assert result == {
        "complete": True,
        "help_option_count": 113,
        "man_option_count": 125,
        "observed_option_count": 127,
        "ledger_option_count": 131,
        "implicit_negation_count": 49,
        "available_option_count": 180,
        "missing_from_ledger": [],
        "ledger_only": [
            "--no-expect",
            "--no-header-lines-border",
            "--no-list-border",
            "--tty-default",
            "--wrap-word",
        ],
    }


def test_ledger_only_options_are_documented_in_man_prose(backend):
    _, man_bytes = get_backend_document("man", str(backend))
    man = man_bytes.decode()
    result = compare_live_options("", man)
    for name in result["ledger_only"]:
        assert name in man


def test_capability_json_is_packaged_and_schema_stable():
    resource = files("cli_anything.fzf").joinpath("capabilities.json")
    raw = resource.read_bytes()
    document = json.loads(raw)
    assert document["schema_version"] == "cli-anything-fzf-capabilities/v1"
    assert len(document["options"]) == len(expanded_options()) == 131
    assert len(document["implicit_negations"]) == 59
    assert document["implicit_negation_rule"]["evidence"].startswith("live-probed")
    assert len(implicit_negative_options()) == 49
    assert len(all_options()) == 180


def test_packaged_json_schema_bundle_is_valid_draft_2020_12():
    document = json.loads(files("cli_anything.fzf").joinpath("schemas.json").read_bytes())
    assert document["schema_version"] == "cli-anything-fzf-schemas/v1"
    Draft202012Validator.check_schema(document)
    assert {
        "success_envelope", "error_envelope", "backend_identity", "plan",
        "profile", "byte_record", "selection_result", "benchmark_result", "listener_state",
    } == set(document["$defs"])


def test_every_implicit_negation_is_structured_and_backend_accepted(backend):
    for base_name in load_capabilities()["implicit_negations"]:
        parsed = parse_option(f"no-{base_name}")
        assert parsed.argv_token() == f"--no-{base_name}"
        result = subprocess.run(
            [str(backend), parsed.argv_token(), "--filter=", "--sync"],
            input=b"x\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=2,
        )
        assert result.returncode == 0, (parsed.argv_token(), result.stderr)


def test_every_option_has_source_effect_policy_surface_and_coverage():
    allowed_sources = {"help", "man"}
    allowed_coverage = {"implemented", "interactive-only", "refused-with-rationale"}
    allowed_surfaces = {"declarative", "listener", "shell", "backend"}
    effects = set(load_capabilities()["effect_classes"])
    for option in expanded_options():
        assert option["sources"] and set(option["sources"]) <= allowed_sources
        assert option["effects"] and set(option["effects"]) <= effects
        assert option["coverage"] in allowed_coverage
        assert option["surface"] in allowed_surfaces
        assert option["arity"] in {"none", "required", "optional"}


def test_option_and_alias_tokens_are_globally_unique():
    tokens: list[str] = []
    for option in expanded_options():
        tokens.extend([option["name"], f"--{option['name']}", *option.get("aliases", [])])
    assert len(tokens) == len(set(tokens))

    available = [item["name"] for item in all_options()]
    assert len(available) == len(set(available))


def test_action_lists_are_unique_disjoint_and_cover_man_table(backend):
    spec = load_capabilities()["actions"]
    pure = spec["pure"]
    hazardous = spec["subprocess_capable"]
    assert len(pure) == len(set(pure))
    assert len(hazardous) == len(set(hazardous))
    assert set(pure).isdisjoint(hazardous)
    _, man_bytes = get_backend_document("man", str(backend))
    man = man_bytes.decode()
    section = man.split("AVAILABLE ACTIONS:", 1)[1].split("ACTION COMPOSITION", 1)[0]
    table_actions = set(re.findall(r"^           ([a-z][a-z0-9+/-]*)(?:\(\.\.\.\))?\s", section, re.MULTILINE))
    assert table_actions - set(pure) - set(hazardous) == set()


def test_all_documented_effect_classes_are_used():
    actual = set()
    for option in expanded_options():
        actual.update(option["effects"])
    assert actual == set(load_capabilities()["effect_classes"])


def test_environment_inputs_are_classified_and_api_key_is_secret():
    inputs = {item["name"]: item for item in load_capabilities()["environment"]["inputs"]}
    assert set(inputs) == {
        "FZF_DEFAULT_COMMAND", "FZF_DEFAULT_OPTS", "FZF_DEFAULT_OPTS_FILE",
        "FZF_API_KEY", "NO_COLOR", "SHELL",
    }
    assert inputs["FZF_API_KEY"]["secret"] is True
    assert inputs["FZF_DEFAULT_COMMAND"]["policy"] == "allow-command-actions"
    assert inputs["FZF_DEFAULT_OPTS_FILE"]["policy"] == "allow-default-opts-file"
