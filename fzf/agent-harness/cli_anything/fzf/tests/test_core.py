"""Unit and policy tests for structured fzf planning."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from cli_anything.fzf.core.capabilities import (
    all_options,
    all_action_names,
    compare_live_options,
    expanded_options,
    implicit_negative_options,
    load_capabilities,
    resolve_option,
)
from cli_anything.fzf.core.errors import PolicyError, ValidationError
from cli_anything.fzf.core.input import InputSource, prepare_input
from cli_anything.fzf.core.planner import annotate_plan, build_option_values, build_plan
from cli_anything.fzf.core.profiles import PROFILE_SCHEMA, compose_profiles, load_profile, write_profile
from cli_anything.fzf.core.results import exit_semantics, parse_output, split_records
from cli_anything.fzf.core.validation import (
    Policy,
    binding_actions,
    binding_is_hazardous,
    ensure_contained,
    parse_expert_option,
    parse_option,
    pid_matches,
    process_start_time,
    validate_listen_address,
    validate_option_set,
    validate_value,
)


VALUE_SAMPLES = {
    "positive-integer": "1",
    "nonnegative-integer": "0",
    "field-expression-list": "1,-2,3..",
    "field-template": "{1}:{2..}",
    "regex": "[:|]",
    "tiebreak": "length,index",
    "height": "~50%",
    "min-height": "10+",
    "box-dimensions": "1,2%,3,4%",
    "border-style": "rounded",
    "border-style-inline": "inline",
    "border-style-no-line": "sharp",
    "label-position": "-2:bottom",
    "style": "full:rounded",
    "color": "dark,fg:#aabbcc,hl:red:bold",
    "info-style": "inline-right:matches ",
    "popup": "center,80%,60%",
    "preview-window": "right,50%,wrap,border-left",
    "duration": "100ms",
    "walker": "file,dir,hidden,follow",
    "key-list": "enter,ctrl-x,alt-/",
    "bindings": "enter:accept",
    "name-list": ".git,node_modules",
    "characters": "abc",
    "path": "/tmp",
    "text": "value with spaces",
    "command": "printf '%s' {}",
    "listen-address": "/tmp/fzf-test.sock",
}


def _sample_for(option: dict) -> str:
    validator = option["validator"]
    if validator.startswith("enum:"):
        return validator.removeprefix("enum:").split(",")[0]
    return VALUE_SAMPLES[validator]


def test_capability_document_is_complete_and_classified():
    spec = load_capabilities()
    options = expanded_options()
    assert spec["backend"] == {
        "name": "fzf",
        "version": "0.74.5",
        "revision": "c0a193e0",
        "help_sha256": "944def5bbeff3f7450b69aec8519cf762091704ad52d49ee735fe4cd168867d0",
        "man_sha256": "d246636f6baf06684abbc468a0cf60fcd9679144bae148ecabdc4a7b54e2a46b",
    }
    assert len(options) == 131
    assert len(implicit_negative_options()) == 49
    assert len(all_options()) == 180
    assert {item["coverage"] for item in options} == {
        "implemented",
        "interactive-only",
    }
    assert set().union(*(set(item["effects"]) for item in options)) == set(spec["effect_classes"])
    assert {item["category"] for item in options} >= {
        "search", "fields", "input-output", "style", "layout", "list",
        "input-section", "preview", "header", "footer", "scripting",
        "bindings", "advanced", "directory-traversal", "history",
        "shell-integration", "introspection",
    }


def test_every_ledger_option_can_be_constructed():
    for option in all_options():
        if option["arity"] == "none":
            parsed = parse_option(option["name"])
            assert parsed.argv_token() == f"--{option['name']}"
        else:
            sample = _sample_for(option)
            parsed = parse_option(f"{option['name']}={sample}")
            assert parsed.value == sample
            if option["arity"] == "optional":
                assert parse_option(option["name"]).value is None


@pytest.mark.parametrize(
    ("alias", "canonical", "value"),
    [
        ("-e", "exact", None),
        ("+x", "no-extended", None),
        ("--tmux=bottom,50%", "popup", "bottom,50%"),
        ("-m=3", "multi", "3"),
        ("--wrap-word", "wrap-word", None),
        ("--no-expect", "no-expect", None),
        ("--no-header-lines-border", "no-header-lines-border", None),
    ],
)
def test_documented_alias_and_compatibility_semantics(alias, canonical, value):
    parsed = parse_option(alias)
    assert (parsed.name, parsed.value) == (canonical, value)


def test_actions_events_keys_and_environment_inventory_has_new_074_surface():
    spec = load_capabilities()
    actions = all_action_names()
    assert {"change-footer", "change-footer-label", "transform-footer", "transform-footer-label"} <= actions
    assert {"result-final", "click-footer", "every(N)"} <= set(spec["events"])
    assert {"return", "ctrl-m", "btab", "pgup", "ctrl-_"} <= set(spec["key_grammar"]["named"])
    exports = set(spec["environment"]["exported_to_children"])
    assert {"FZF_INFO", "FZF_CLICK_HEADER_NTH", "FZF_CLICK_FOOTER_WORD"} <= exports


def test_live_comparison_reports_missing_and_ledger_only():
    result = compare_live_options("    --exact\n", "       --threads=N\n")
    assert result["complete"]
    assert result["help_option_count"] == 1
    assert result["man_option_count"] == 1
    assert result["implicit_negation_count"] == 49
    assert result["available_option_count"] == 180
    assert "--wrap-word" in result["ledger_only"]


@pytest.mark.parametrize(
    ("validator", "bad"),
    [
        ("positive-integer", "0"),
        ("nonnegative-integer", "-1"),
        ("field-expression-list", "0,1"),
        ("field-expression-list", "1...2"),
        ("tiebreak", "index,length"),
        ("height", "fifty"),
        ("box-dimensions", "1,2,3,4,5"),
        ("border-style", "curly"),
        ("label-position", "left"),
        ("style", "maximum"),
        ("color", "fg:not a color"),
        ("popup", "diagonal"),
        ("preview-window", "right,(broken"),
        ("duration", "forever"),
        ("walker", "file,device"),
        ("key-list", "ctrl-999"),
        ("name-list", "../escape"),
        ("characters", "aab"),
    ],
)
def test_malformed_values_are_rejected(validator, bad):
    with pytest.raises(ValidationError):
        validate_value(validator, bad)


@pytest.mark.parametrize(
    ("binding", "actions", "hazardous"),
    [
        ("enter:accept", ["accept"], False),
        ("start,ctrl-r:reload:printf '%s' x", ["reload"], True),
        ("ctrl-x:execute(echo a+b)+accept", ["execute", "accept"], True),
        ("alt-@:change-footer(done)+transform-footer(echo ok)", ["change-footer", "transform-footer"], True),
        ("ctrl-a:+select-all+accept", ["select-all", "accept"], False),
        ("enter:execute~printf + accept~+accept", ["execute", "accept"], True),
        ("every(0.25):bg-transform-query(echo query)", ["bg-transform-query"], True),
        ("tab:toggle+down", ["toggle", "down"], False),
    ],
)
def test_binding_grammar_and_hazard_classification(binding, actions, hazardous):
    assert binding_actions(binding) == actions
    assert binding_is_hazardous(binding) is hazardous


@pytest.mark.parametrize(
    "binding",
    [
        "unknown:accept",
        "enter:no-such-action",
        "enter:execute(unclosed",
        "enter:accept+",
        "enter:accept garbage",
        "every(0.001):accept",
    ],
)
def test_malformed_bindings_are_rejected(binding):
    with pytest.raises(ValidationError):
        binding_actions(binding)


def test_option_set_default_denies_hazardous_features():
    options = [
        parse_option("preview=cat {}"),
        parse_option("history=/tmp/history"),
        parse_option("walker-root=/tmp"),
        parse_option("bind=enter:execute(echo {})"),
    ]
    analysis = validate_option_set(options, Policy(), surface="declarative")
    refused = {item["option"] for item in analysis["refusals"]}
    assert refused == {"--preview", "--history", "--walker-root", "--bind"}
    assert {"subprocess_capable", "filesystem_reading", "filesystem_writing"} <= set(analysis["effects"])


def test_option_set_accepts_each_explicit_grant():
    options = [
        parse_option("preview=cat {}"),
        parse_option("history=/tmp/history"),
        parse_option("walker-root=/tmp"),
        parse_option("bind=enter:execute(echo {})"),
    ]
    policy = Policy(allow_command_actions=True, allow_filesystem_write=True, allow_walker=True)
    assert validate_option_set(options, policy, surface="declarative")["refusals"] == []


def test_duplicate_direct_option_is_rejected_but_argv_can_override_environment_default():
    with pytest.raises(ValidationError, match="cannot be repeated"):
        validate_option_set(
            [parse_option("layout=default"), parse_option("layout=reverse")],
            Policy(),
            surface="declarative",
        )
    analysis = validate_option_set(
        [
            parse_option("layout=default", source="FZF_DEFAULT_OPTS"),
            parse_option("layout=reverse"),
        ],
        Policy(),
        surface="declarative",
    )
    assert analysis["refusals"] == []


@pytest.mark.parametrize(
    "raw",
    ["x", "-x", "--known value", "--bad\nvalue", "--listen=/tmp/x.sock", "--exact"],
)
def test_expert_escape_hatch_rejects_unsafe_or_known_forms(raw):
    with pytest.raises((PolicyError, ValidationError)):
        parse_expert_option(raw, Policy(allow_unknown_options=True))


def test_expert_escape_hatch_is_one_argv_token_and_visible():
    item = parse_expert_option("--future-mode=value with spaces", Policy(allow_unknown_options=True))
    assert item.argv_token() == "--future-mode=value with spaces"
    analysis = validate_option_set([item], Policy(allow_unknown_options=True), surface="declarative")
    assert analysis["effects"] == ["subprocess_capable"]


@pytest.mark.parametrize("surface", ["declarative", "listener"])
def test_expert_option_is_accepted_on_execution_surfaces_only_with_grant(surface):
    item = parse_expert_option("--future-mode", Policy(allow_unknown_options=True))
    granted = validate_option_set([item], Policy(allow_unknown_options=True), surface=surface)
    assert granted["refusals"] == []
    assert granted["effects"] == ["subprocess_capable"]
    denied = validate_option_set([item], Policy(), surface=surface)
    assert denied["refusals"] == [
        {"option": "--future-mode", "reason": "requires allow-unknown-options"}
    ]


@pytest.mark.parametrize(
    ("value", "kind", "loopback"),
    [
        ("/tmp/fzf.sock", "unix", True),
        ("12345", "tcp", True),
        ("localhost:12345", "tcp", True),
        ("0.0.0.0:12345", "tcp", False),
        ("[::1]:12345", "tcp", True),
    ],
)
def test_listener_address_validation(value, kind, loopback):
    result = validate_listen_address(value)
    assert result["kind"] == kind
    assert result["loopback"] is loopback


@pytest.mark.parametrize("value", ["relative.sock", "host:notaport", "99999", "[::1"])
def test_bad_listener_addresses(value):
    with pytest.raises(ValidationError):
        validate_listen_address(value)


def test_containment_accepts_child_and_rejects_escape(tmp_path):
    assert ensure_contained(tmp_path / "child.sock", tmp_path) == tmp_path / "child.sock"
    with pytest.raises(PolicyError):
        ensure_contained(tmp_path.parent / "foreign.sock", tmp_path)


def test_process_identity_matches_current_process():
    started = process_start_time(os.getpid())
    assert started is not None
    assert pid_matches(os.getpid(), started)
    assert not pid_matches(os.getpid(), started + 1)
    assert not pid_matches(0, None)


def test_items_preserve_unicode_ansi_and_newlines_in_read0():
    source = prepare_input(items=["snowman ☃", "line\n\x1b[31mred\x1b[0m"], read0=True)
    assert source.data == "snowman ☃\0line\n\x1b[31mred\x1b[0m\0".encode()
    assert source.description["record_separator"] == "nul"
    assert source.description["item_count"] == 2


def test_base64_input_preserves_exact_bytes_and_limits():
    source = prepare_input(input_base64="YWxwaGEAYmFk/2J5dGVzAA==", read0=True)
    assert source.kind == "base64"
    assert source.data == b"alpha\0bad\xffbytes\0"
    assert source.description["item_count"] == 2
    assert source.description["byte_count"] == len(source.data)


@pytest.mark.parametrize("value", ["not base64", "YQ", "YQ===", "YR=="])
def test_invalid_base64_input_is_rejected(value):
    with pytest.raises(ValidationError, match="canonical base64"):
        prepare_input(input_base64=value)


def test_item_newline_requires_nul_mode():
    with pytest.raises(ValidationError):
        prepare_input(items=["line\nbreak"])


def test_dry_run_stats_file_without_reading_content(tmp_path):
    path = tmp_path / "input"
    path.write_bytes(b"alpha\nbeta\n")
    source = prepare_input(input_file=str(path), dry_run=True)
    assert source.data is None
    assert source.description == {
        "kind": "file",
        "path": str(path),
        "record_separator": "newline",
        "byte_count": 11,
        "content_read": False,
    }


def test_input_bounds_bytes_and_records(tmp_path):
    path = tmp_path / "input"
    path.write_bytes(b"a\nb\nc\n")
    with pytest.raises(ValidationError, match="records"):
        prepare_input(input_file=str(path), max_items=2)
    with pytest.raises(ValidationError, match="bytes"):
        prepare_input(input_file=str(path), max_bytes=5)


def test_implicit_walker_is_refused(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    with pytest.raises(PolicyError, match="traversal"):
        prepare_input()


def test_walker_source_requires_explicit_permission(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    source = prepare_input(allow_walker=True)
    assert source.kind == "walker"
    assert source.data is None


def test_exact_output_parsing_preserves_binary_and_prefixes():
    raw = b"needle\0ctrl-x\0valid\0bad\xff\0"
    result = parse_output(raw, print0=True, print_query=True, expect=True)
    assert result["query"]["text"] == "needle"
    assert result["expect_key"]["text"] == "ctrl-x"
    assert result["selections"][0]["text"] == "valid"
    assert result["selections"][1]["text"] is None
    assert result["selections"][1]["base64"] == "YmFk/w=="
    assert result["output_byte_count"] == len(raw)


def test_empty_output_and_intentional_empty_record():
    assert split_records(b"", print0=False) == []
    assert split_records(b"\n", print0=False) == [b""]


@pytest.mark.parametrize(
    ("code", "meaning", "semantic", "completed"),
    [
        (0, "accepted-or-completed", True, True),
        (1, "no-match", False, True),
        (2, "backend-error", False, False),
        (126, "become-permission-denied", False, False),
        (127, "become-command-not-found", False, False),
        (130, "interrupted", False, False),
        (99, "unknown-backend-exit", False, False),
    ],
)
def test_exit_semantics(code, meaning, semantic, completed):
    result = exit_semantics(code)
    assert result["meaning"] == meaning
    assert result["semantic_success"] is semantic
    assert result["backend_completed"] is completed


def test_profile_write_mode_load_and_overwrite(tmp_path):
    path = tmp_path / "profile.json"
    result = write_profile(
        str(path), name="base", description="test", options=["scheme=path"], bindings=["ctrl-j:accept"]
    )
    assert result["mode"] == "0600"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert load_profile(str(path))["resolved_options"][0].argv_token() == "--scheme=path"
    with pytest.raises(ValidationError, match="already exists"):
        write_profile(str(path), name="base", description="", options=[], bindings=[])
    overwritten = write_profile(
        str(path),
        name="replacement",
        description="updated",
        options=["layout=reverse"],
        bindings=[],
        overwrite=True,
    )
    assert overwritten["mode"] == "0600"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert load_profile(str(path))["name"] == "replacement"


@pytest.mark.parametrize("dangling", [False, True], ids=["existing-target", "dangling-target"])
def test_profile_overwrite_refuses_final_component_symlink(tmp_path, dangling):
    target = tmp_path / "target.json"
    sentinel = b"existing target must remain unchanged\n"
    if not dangling:
        target.write_bytes(sentinel)
    output = tmp_path / "profile.json"
    output.symlink_to(target)

    with pytest.raises(ValidationError) as raised:
        write_profile(
            str(output),
            name="replacement",
            description="",
            options=[],
            bindings=[],
            overwrite=True,
        )

    assert raised.value.code == "profile_path_unsafe"
    assert output.is_symlink()
    if dangling:
        assert not target.exists()
    else:
        assert target.read_bytes() == sentinel


@pytest.mark.parametrize("dangling", [False, True], ids=["existing-target", "dangling-target"])
def test_profile_create_refuses_planted_lock_symlink(tmp_path, dangling):
    target = tmp_path / "lock-target"
    sentinel = b"lock target must remain unchanged\n"
    if not dangling:
        target.write_bytes(sentinel)
    output = tmp_path / "profile.json"
    lock = tmp_path / ".profile.json.lock"
    lock.symlink_to(target)

    with pytest.raises(ValidationError) as raised:
        write_profile(str(output), name="p", description="", options=[], bindings=[])

    assert raised.value.code == "profile_path_unsafe"
    assert lock.is_symlink()
    assert not output.exists()
    if dangling:
        assert not target.exists()
    else:
        assert target.read_bytes() == sentinel


def test_profile_composition_overrides_scalars_and_appends_bindings(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    write_profile(str(first), name="first", description="", options=["scheme=path", "layout=default"], bindings=["ctrl-a:accept"])
    write_profile(str(second), name="second", description="", options=["layout=reverse"], bindings=["ctrl-b:abort"])
    result = compose_profiles([str(first), str(second)])
    assert result["option_tokens"] == [
        "--scheme=path", "--layout=reverse", "--bind=ctrl-a:accept", "--bind=ctrl-b:abort"
    ]


@pytest.mark.parametrize(
    "document",
    [
        [],
        {"schema_version": "bad", "name": "x"},
        {"schema_version": PROFILE_SCHEMA, "name": "", "options": []},
        {"schema_version": PROFILE_SCHEMA, "name": "x", "unknown": True},
        {"schema_version": PROFILE_SCHEMA, "name": "x", "options": ["bad-option"]},
    ],
)
def test_invalid_profiles_are_rejected(tmp_path, document):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_profile(str(path))


def test_build_plan_is_exact_refusal_evidence_and_stable(backend):
    options, metadata = build_option_values(
        raw_options=["preview=printf x", "layout=reverse"], policy=Policy()
    )
    source = InputSource("items", {"kind": "items", "item_count": 1}, b"alpha\n")
    plan = build_plan(
        backend_override=str(backend),
        mode="select",
        options=options,
        input_source=source,
        policy=Policy(),
        dry_run=True,
        timeout=2,
        profile_metadata=metadata,
    )
    assert plan.public["argv"] == [str(backend), "--preview=printf x", "--layout=reverse"]
    assert plan.public["refused"]
    assert plan.public["refusal_reasons"] == [
        {"option": "--preview", "reason": "requires allow-command-actions"}
    ]
    original = plan.public["plan_id"]
    annotate_plan(plan, annotations={"surface_detail": "example"}, effects=["network_listener"])
    assert plan.public["plan_id"] != original
    assert plan.public["effect_classes"] == ["interactive_tty", "network_listener", "subprocess_capable"]


def test_inherit_plan_never_serializes_environment_values(monkeypatch, backend):
    secret = "value-that-must-not-appear"
    monkeypatch.setenv("CLI_ANYTHING_TEST_CREDENTIAL", secret)
    source = InputSource("items", {"kind": "items"}, b"x\n")
    plan = build_plan(
        backend_override=str(backend),
        mode="filter",
        options=[],
        input_source=source,
        policy=Policy(allow_env_inherit=True),
        dry_run=True,
        timeout=1,
        env_policy="inherit",
    )
    serialized = json.dumps(plan.public)
    assert secret not in serialized
    assert plan.public["environment_delta"]["constructed"] == {}
    assert "CLI_ANYTHING_TEST_CREDENTIAL" in plan.public["environment_delta"]["inherited_names"]


def test_api_key_cannot_be_supplied_as_environment_text(backend):
    source = InputSource("items", {"kind": "items"}, b"x\n")
    with pytest.raises(PolicyError, match="api-key-file"):
        build_plan(
            backend_override=str(backend),
            mode="filter",
            options=[],
            input_source=source,
            policy=Policy(),
            dry_run=True,
            timeout=1,
            set_env=["FZF_API_KEY=secret"],
        )


def _walker_plan(backend, root, policy):
    return build_plan(
        backend_override=str(backend),
        mode="filter",
        options=[parse_option(f"walker-root={root}")],
        input_source=InputSource("walker", {"kind": "backend-walker"}, None),
        policy=policy,
        dry_run=True,
        timeout=1,
    ).public


BROAD_WALKER_REFUSAL = {
    "input": "backend-walker",
    "reason": "root or home traversal requires allow-broad-walker",
}


@pytest.mark.parametrize("relative", ["var/home/user", "var/home", "var", "alias-home", "alias-parent"])
def test_walker_root_containing_home_requires_broad_grant(backend, tmp_path, monkeypatch, relative):
    home = tmp_path / "var" / "home" / "user"
    home.mkdir(parents=True)
    (tmp_path / "alias-home").symlink_to(home)
    (tmp_path / "alias-parent").symlink_to(home.parent)
    monkeypatch.setenv("HOME", str(home))
    root = tmp_path / relative
    refused = _walker_plan(backend, root, Policy(allow_walker=True))
    assert refused["refused"]
    assert BROAD_WALKER_REFUSAL in refused["refusal_reasons"]
    granted = _walker_plan(backend, root, Policy(allow_walker=True, allow_broad_walker=True))
    assert not granted["refused"]
    assert granted["argv"] == [str(backend), f"--walker-root={root}"]


def test_filesystem_root_walker_requires_broad_grant(backend):
    assert BROAD_WALKER_REFUSAL in _walker_plan(backend, "/", Policy(allow_walker=True))["refusal_reasons"]
    assert not _walker_plan(backend, "/", Policy(allow_walker=True, allow_broad_walker=True))["refused"]


@pytest.mark.parametrize("relative", ["var/home/user/project", "var/home/sibling", "elsewhere"])
def test_walker_root_not_containing_home_needs_only_walker_grant(backend, tmp_path, monkeypatch, relative):
    home = tmp_path / "var" / "home" / "user"
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    plan = _walker_plan(backend, tmp_path / relative, Policy(allow_walker=True))
    assert not plan["refused"]
    assert plan["refusal_reasons"] == []


def test_source_contains_no_shell_true():
    package = Path(__file__).parents[1]
    sources = "\n".join(path.read_text(encoding="utf-8") for path in package.rglob("*.py"))
    assert "shell" + "=True" not in sources
