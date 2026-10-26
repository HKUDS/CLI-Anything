"""Release-style tests against the installed CLI and real fzf 0.74.5."""

from __future__ import annotations

import json
import os
import pty
import base64
import signal
import socket
import subprocess
import termios
import threading
import time
from importlib.resources import files
from pathlib import Path

import fcntl
import pytest
from jsonschema import Draft202012Validator

from cli_anything.fzf.core.validation import pid_matches


SCHEMA_BUNDLE = json.loads(files("cli_anything.fzf").joinpath("schemas.json").read_bytes())


def assert_schema(instance: object, definition: str) -> None:
    schema = {
        "$schema": SCHEMA_BUNDLE["$schema"],
        "$ref": f"#/$defs/{definition}",
        "$defs": SCHEMA_BUNDLE["$defs"],
    }
    Draft202012Validator(schema).validate(instance)


def run_cli(
    cli: Path,
    backend: Path,
    args: list[str],
    *,
    input_bytes: bytes = b"",
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: float = 15,
) -> tuple[subprocess.CompletedProcess[bytes], dict]:
    command = [str(cli), "--json", "--backend", str(backend), *args]
    environment = dict(os.environ)
    if env:
        environment.update(env)
    result = subprocess.run(
        command,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=environment,
        timeout=timeout,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"CLI did not return JSON\nargv={command!r}\nstdout={result.stdout!r}\nstderr={result.stderr!r}"
        ) from exc
    return result, payload


def assert_error(result, payload, code: str, exit_code: int = 2):
    assert result.returncode == exit_code
    assert payload["ok"] is False
    assert payload["error"]["code"] == code


def selection_texts(payload: dict) -> list[str | None]:
    return [item["text"] for item in payload["data"]["result"]["selections"]]


def _drain(fd: int, output: bytearray) -> None:
    while True:
        try:
            chunk = os.read(fd, 65_536)
        except OSError:
            break
        if not chunk:
            break
        output.extend(chunk)


def run_interactive(
    cli: Path,
    backend: Path,
    args: list[str],
    *,
    timeout: float = 10,
    interrupt_after: float | None = None,
) -> tuple[subprocess.CompletedProcess[bytes], dict, bytes]:
    master_fd, slave_fd = pty.openpty()

    def controlling_tty() -> None:
        os.setsid()
        fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)

    command = [str(cli), "--json", "--backend", str(backend), *args]
    process = subprocess.Popen(
        command,
        stdin=slave_fd,
        stdout=subprocess.PIPE,
        stderr=slave_fd,
        env=dict(os.environ),
        preexec_fn=controlling_tty,
    )
    os.close(slave_fd)
    terminal = bytearray()
    drainer = threading.Thread(target=_drain, args=(master_fd, terminal), daemon=True)
    drainer.start()
    if interrupt_after is not None:
        time.sleep(interrupt_after)
        os.kill(process.pid, signal.SIGINT)
    stdout, _ = process.communicate(timeout=timeout)
    drainer.join(timeout=2)
    os.close(master_fd)
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"interactive CLI did not return JSON\nargv={command!r}\n"
            f"returncode={process.returncode}\nstdout={stdout!r}\nterminal={bytes(terminal)!r}"
        ) from exc
    completed = subprocess.CompletedProcess(command, process.returncode, stdout, bytes(terminal))
    return completed, payload, bytes(terminal)


def stop_listener_best_effort(cli: Path, backend: Path, state_dir: Path) -> None:
    if (state_dir / "state.json").is_file():
        run_cli(
            cli,
            backend,
            ["listener", "stop", "--state-dir", str(state_dir), "--remove-state", "--stop-timeout", "0.5"],
            timeout=5,
        )


def test_installed_console_script_works_outside_checkout(installed_cli, backend, tmp_path):
    result, payload = run_cli(installed_cli, backend, ["backend", "inspect"], cwd=tmp_path)
    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["data"]["version"] == "0.74.5"
    assert payload["data"]["revision"] == "c0a193e0"
    assert_schema(payload, "success_envelope")
    assert_schema(payload["data"], "backend_identity")


def test_module_and_console_version_agree(installed_cli):
    result = subprocess.run([str(installed_cli), "--version"], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "cli-anything-fzf, version 1.0.0"
    imported = subprocess.run(
        [str(installed_cli.parent / "python"), "-c", "import cli_anything.fzf as f; print(f.__version__)"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert imported.stdout.strip() == "1.0.0"


@pytest.mark.parametrize("document", ["help", "man"])
def test_backend_document_retrieval(installed_cli, backend, document):
    result, payload = run_cli(installed_cli, backend, ["backend", document])
    assert result.returncode == 0
    assert payload["data"]["byte_count"] > 10_000
    assert "fzf" in payload["data"]["text"]


def test_backend_verify_spec_cli(installed_cli, backend):
    result, payload = run_cli(installed_cli, backend, ["backend", "verify-spec"])
    assert result.returncode == 0
    assert payload["data"]["complete"] is True
    assert payload["data"]["observed_option_count"] == 127
    assert payload["data"]["ledger_option_count"] == 131
    assert payload["data"]["implicit_negation_count"] == 49
    assert payload["data"]["available_option_count"] == 180


def test_capability_export_json_schema(installed_cli, backend):
    result, payload = run_cli(installed_cli, backend, ["capability", "export"])
    assert result.returncode == 0
    assert payload["command"] == "capability.export"
    assert payload["data"]["schema_version"] == "cli-anything-fzf-capabilities/v1"
    assert len(payload["data"]["options"]) == 131
    assert len(payload["data"]["implicit_negations"]) == 59


def test_json_schema_bundle_is_agent_retrievable(installed_cli, backend):
    result, payload = run_cli(installed_cli, backend, ["capability", "schemas"])
    assert result.returncode == 0
    assert payload["data"]["schema_version"] == "cli-anything-fzf-schemas/v1"
    assert payload["data"]["$defs"] == SCHEMA_BUNDLE["$defs"]
    assert_schema(payload, "success_envelope")


def test_capability_list_includes_implicit_negations(installed_cli, backend):
    result, payload = run_cli(installed_cli, backend, ["capability", "list"])
    assert result.returncode == 0
    assert payload["data"]["count"] == 180
    options = {item["name"]: item for item in payload["data"]["options"]}
    assert options["no-preview"]["implicit_negation_of"] == "preview"
    assert options["no-listen-unsafe"]["effects"] == ["interactive_tty"]


@pytest.mark.parametrize(
    ("query", "options", "expected"),
    [
        ("alp", [], ["alpha", "alphabet"]),
        ("B", ["smart-case"], ["Beta"]),
        ("srcmod", ["scheme=path"], ["src/module.py"]),
        ("alp", ["algo=v1"], ["alpha", "alphabet"]),
        ("alp", ["algo=v2", "no-sort"], ["alpha", "alphabet"]),
        ("", ["tac"], ["Beta", "src/module.py", "alphabet", "alpha"]),
    ],
)
def test_real_filter_search_modes(installed_cli, backend, query, options, expected):
    args = ["filter", "run", "--query", query]
    for option in options:
        args.extend(["--option", option])
    for item in ["alpha", "alphabet", "src/module.py", "Beta"]:
        args.extend(["--item", item])
    result, payload = run_cli(installed_cli, backend, args)
    assert result.returncode == 0
    assert selection_texts(payload) == expected
    assert payload["data"]["result"]["semantic_success"] is True


def test_benchmark_mode_is_reported_as_benchmark_not_selection(installed_cli, backend):
    dry, dry_payload = run_cli(
        installed_cli,
        backend,
        [
            "--dry-run", "filter", "run", "--query", "", "--option", "bench=10ms",
            "--item", "alpha", "--item", "beta",
        ],
    )
    assert dry.returncode == 0
    assert dry_payload["data"]["plan"]["expected_output"] == "benchmark-report"
    result, payload = run_cli(
        installed_cli,
        backend,
        [
            "filter", "run", "--query", "", "--option", "bench=10ms",
            "--item", "alpha", "--item", "beta",
        ],
    )
    assert result.returncode == 0
    benchmark = payload["data"]["result"]["benchmark"]
    assert "items: 2" in benchmark["text"]
    assert "selections" not in payload["data"]["result"]
    assert_schema(payload["data"]["result"], "benchmark_result")


def test_composed_fields_delimiter_and_accept_transform(installed_cli, backend):
    args = [
        "filter", "run", "--query", "ready",
        "--option", "delimiter=:", "--option", "nth=2..3", "--option", "accept-nth={1}:{2}",
        "--item", "1:alpha:ready", "--item", "2:beta:waiting",
    ]
    result, payload = run_cli(installed_cli, backend, args)
    assert result.returncode == 0
    assert selection_texts(payload) == ["1:alpha"]


def test_nul_unicode_ansi_newline_and_invalid_utf8_backend_semantics(installed_cli, backend):
    raw = "first line\ncontinued\0snowman ☃\0\x1b[31mred\x1b[0m\0".encode() + b"bad\xffbytes\0"
    args = [
        "filter", "run", "--query", "", "--stdin", "--option", "read0",
        "--option", "print0", "--option", "ansi", "--option", "no-sort",
    ]
    result, payload = run_cli(installed_cli, backend, args, input_bytes=raw)
    assert result.returncode == 0
    records = payload["data"]["result"]["selections"]
    assert records[0]["text"] == "first line\ncontinued"
    assert records[1]["text"] == "snowman ☃"
    assert records[2]["text"] == "red"
    # fzf itself normalizes malformed UTF-8 to U+FFFD. The harness truthfully
    # reports those exact backend bytes instead of claiming input round-trip.
    assert records[3]["text"] == "bad�bytes"
    assert records[3]["base64"] == "YmFk77+9Ynl0ZXM="


def test_base64_input_is_agent_safe_and_byte_exact(installed_cli, backend):
    raw = b"first\nline\0snowman \xe2\x98\x83\0"
    result, payload = run_cli(
        installed_cli,
        backend,
        [
            "filter", "run", "--query", "", "--input-base64", base64.b64encode(raw).decode(),
            "--option", "read0", "--option", "print0", "--option", "no-sort",
        ],
    )
    assert result.returncode == 0
    assert selection_texts(payload) == ["first\nline", "snowman ☃"]
    assert payload["data"]["plan"]["stdin"]["kind"] == "base64"
    assert_schema(payload["data"]["plan"], "plan")
    assert_schema(payload["data"]["result"], "selection_result")


def test_negated_framing_options_use_last_option_semantics(installed_cli, backend):
    result, payload = run_cli(
        installed_cli,
        backend,
        [
            "filter", "run", "--query", "", "--input-base64",
            base64.b64encode(b"alpha\nbeta\n").decode(),
            "--option", "read0", "--option", "no-read0",
            "--option", "print0", "--option", "no-print0", "--option", "no-sort",
        ],
    )
    assert result.returncode == 0
    assert selection_texts(payload) == ["alpha", "beta"]
    assert payload["data"]["plan"]["stdin"]["record_separator"] == "newline"
    assert payload["data"]["result"]["record_separator"] == "newline"


def test_print_query_prefix_is_separate(installed_cli, backend):
    result, payload = run_cli(
        installed_cli,
        backend,
        ["filter", "run", "--query", "alp", "--option", "print-query", "--item", "alpha"],
    )
    assert result.returncode == 0
    assert payload["data"]["result"]["query"]["text"] == "alp"
    assert selection_texts(payload) == ["alpha"]


@pytest.mark.parametrize(("items", "query"), [([], "x"), (["alpha"], "zzz")])
def test_empty_and_no_match_are_semantic_not_transport_success(installed_cli, backend, items, query):
    args = ["filter", "run", "--query", query]
    if items:
        for item in items:
            args.extend(["--item", item])
    else:
        args.append("--stdin")
    result, payload = run_cli(installed_cli, backend, args)
    assert result.returncode == 1
    semantics = payload["data"]["result"]
    assert semantics["process_exit_code"] == 1
    assert semantics["backend_completed"] is True
    assert semantics["semantic_success"] is False
    assert semantics["no_match"] is True


def test_huge_but_bounded_input_and_limit_refusal(installed_cli, backend):
    raw = b"".join(f"item-{index:05d}\n".encode() for index in range(20_000))
    result, payload = run_cli(
        installed_cli, backend, ["filter", "run", "--query", "item-19999", "--stdin"], input_bytes=raw
    )
    assert result.returncode == 0
    assert selection_texts(payload) == ["item-19999"]
    refused, error = run_cli(
        installed_cli,
        backend,
        ["filter", "run", "--query", "", "--stdin", "--max-input-bytes", "1024"],
        input_bytes=raw,
    )
    assert_error(refused, error, "input_too_large")


def test_shell_metacharacters_are_data_not_python_shell(installed_cli, backend, tmp_path):
    marker = tmp_path / "must-not-exist"
    item = f"$(touch {marker}) ; `touch {marker}` | &"
    result, payload = run_cli(
        installed_cli, backend, ["filter", "run", "--query", "touch", "--item", item]
    )
    assert result.returncode == 0
    assert selection_texts(payload) == [item]
    assert not marker.exists()


@pytest.mark.parametrize(
    "args",
    [
        ["--dry-run", "plan", "build", "--mode", "select", "--item", "x", "--option", "preview=cat {}"],
        ["--dry-run", "plan", "build", "--mode", "select", "--item", "x", "--option", "with-shell=sh -c"],
        ["--dry-run", "plan", "build", "--mode", "select", "--item", "x", "--bind", "enter:execute(echo {})"],
        ["--dry-run", "plan", "build", "--mode", "select", "--item", "x", "--option", "history=/tmp/history"],
    ],
)
def test_hazardous_plans_show_refusal_reasons(installed_cli, backend, args):
    result, payload = run_cli(installed_cli, backend, args)
    assert result.returncode == 0
    plan = payload["data"]
    assert plan["dry_run"] is True
    assert plan["executed"] is False
    assert plan["refused"] is True
    assert plan["refusal_reasons"]


def test_granted_preview_plan_remains_exact_argv(installed_cli, backend):
    command = "printf 'preview %s' {}"
    args = [
        "--dry-run", "--allow-command-actions", "plan", "build", "--mode", "select",
        "--item", "x", "--option", f"preview={command}",
    ]
    result, payload = run_cli(installed_cli, backend, args)
    assert result.returncode == 0
    plan = payload["data"]
    assert plan["refused"] is False
    assert f"--preview={command}" in plan["argv"]
    assert "subprocess_capable" in plan["effect_classes"]


@pytest.mark.parametrize(
    ("mode", "expected"),
    [("filter", "filter-records"), ("select", "interactive-selection-records")],
)
def test_plan_build_reports_truthful_output_mode(installed_cli, backend, mode, expected):
    result, payload = run_cli(
        installed_cli,
        backend,
        ["--dry-run", "plan", "build", "--mode", mode, "--item", "x"],
    )
    assert result.returncode == 0
    assert payload["data"]["expected_output"] == expected
    assert_schema(payload["data"], "plan")


def test_user_tty_default_can_override_safe_session_default(installed_cli, backend):
    result, payload = run_cli(
        installed_cli,
        backend,
        [
            "--dry-run", "plan", "build", "--mode", "select",
            "--option", "tty-default=/dev/tty", "--item", "x",
        ],
    )
    assert result.returncode == 0
    argv = payload["data"]["argv"]
    assert argv.index("--no-tty-default") < argv.index("--tty-default=/dev/tty")


def test_unknown_expert_option_requires_grant_and_is_one_token(installed_cli, backend):
    args = ["--dry-run", "plan", "build", "--mode", "filter", "--item", "x", "--expert-option", "--future=value with spaces"]
    denied, error = run_cli(installed_cli, backend, args)
    assert_error(denied, error, "unknown_options_denied")
    allowed, payload = run_cli(installed_cli, backend, ["--allow-unknown-options", *args])
    assert allowed.returncode == 0
    assert "--future=value with spaces" in payload["data"]["argv"]
    assert payload["data"]["refused"] is False
    assert payload["data"]["refusal_reasons"] == []


def test_granted_expert_option_reaches_real_backend(installed_cli, backend):
    args = ["filter", "run", "--item", "apple", "--query", "a", "--expert-option", "--future=1"]
    denied, error = run_cli(installed_cli, backend, args)
    assert_error(denied, error, "unknown_options_denied")
    executed, payload = run_cli(installed_cli, backend, ["--allow-unknown-options", *args])
    plan = payload["data"]["plan"]
    result = payload["data"]["result"]
    assert plan["refused"] is False
    assert plan["executed"] is True
    assert plan["argv"][-1] == "--future=1"
    assert "subprocess_capable" in plan["effect_classes"]
    assert result["process_exit_code"] == 2
    assert result["stderr"] == "unknown option: --future\n"
    assert executed.returncode == 2


def test_inherited_secret_value_never_appears_in_plan(installed_cli, backend):
    secret = "literal-secret-that-must-not-be-emitted"
    result, payload = run_cli(
        installed_cli,
        backend,
        ["--dry-run", "--env-policy", "inherit", "--allow-env-inherit", "plan", "build", "--mode", "filter", "--item", "x"],
        env={"CLI_ANYTHING_E2E_CREDENTIAL": secret},
    )
    assert result.returncode == 0
    assert secret not in result.stdout.decode()
    delta = payload["data"]["environment_delta"]
    assert delta["constructed"] == {}
    assert "CLI_ANYTHING_E2E_CREDENTIAL" in delta["inherited_names"]


def test_ambient_fzf_defaults_are_not_applied(installed_cli, backend):
    result, payload = run_cli(
        installed_cli,
        backend,
        ["filter", "run", "--query", "alp", "--item", "alpha"],
        env={"FZF_DEFAULT_OPTS": "--filter=will-not-match", "FZF_DEFAULT_COMMAND": "exit 99"},
    )
    assert result.returncode == 0
    assert selection_texts(payload) == ["alpha"]
    removed = payload["data"]["plan"]["environment_delta"]["removed_ambient"]
    assert {"FZF_DEFAULT_OPTS", "FZF_DEFAULT_COMMAND"} <= set(removed)


def test_explicit_default_opts_are_validated_and_refused_if_hazardous(installed_cli, backend):
    result, payload = run_cli(
        installed_cli,
        backend,
        ["--dry-run", "--set-env", "FZF_DEFAULT_OPTS=--preview='cat {}'", "plan", "build", "--mode", "filter", "--item", "x"],
    )
    assert result.returncode == 0
    assert payload["data"]["refused"] is True
    assert payload["data"]["refusal_reasons"] == [
        {"option": "--preview", "reason": "requires allow-command-actions"}
    ]


def test_default_opts_control_input_and_output_framing_truthfully(installed_cli, backend):
    raw = b"line one\ncontinued\0second\0"
    result, payload = run_cli(
        installed_cli,
        backend,
        [
            "--set-env", "FZF_DEFAULT_OPTS=--read0 --print0 --no-sort",
            "filter", "run", "--query", "", "--input-base64", base64.b64encode(raw).decode(),
        ],
    )
    assert result.returncode == 0
    assert selection_texts(payload) == ["line one\ncontinued", "second"]
    assert payload["data"]["plan"]["stdin"]["record_separator"] == "nul"
    assert payload["data"]["result"]["record_separator"] == "nul"
    assert {item["source"] for item in payload["data"]["plan"]["option_sources"]} >= {
        "FZF_DEFAULT_OPTS", "command-line"
    }


def test_direct_option_overrides_default_output_framing(installed_cli, backend):
    result, payload = run_cli(
        installed_cli,
        backend,
        [
            "--set-env", "FZF_DEFAULT_OPTS=--print0",
            "filter", "run", "--query", "", "--item", "alpha", "--option", "no-print0",
        ],
    )
    assert result.returncode == 0
    assert selection_texts(payload) == ["alpha"]
    assert payload["data"]["result"]["record_separator"] == "newline"


@pytest.mark.parametrize(
    "environment_args",
    [
        ["--set-env", "FZF_DEFAULT_OPTS=--exact", "--set-env", "FZF_DEFAULT_OPTS=--no-sort"],
        [
            "--set-env", "FZF_DEFAULT_OPTS=--exact",
            "--set-env", "FZF_DEFAULT_OPTS_FILE=/tmp/not-read-because-conflict",
        ],
    ],
)
def test_environment_option_conflicts_are_deterministic(
    installed_cli, backend, environment_args
):
    result, payload = run_cli(
        installed_cli,
        backend,
        [*environment_args, "--dry-run", "plan", "build", "--mode", "filter", "--item", "x"],
    )
    assert result.returncode == 2
    assert payload["error"]["code"] in {"environment_duplicate", "environment_conflict"}


def test_default_opts_file_grant_does_not_bypass_command_policy(installed_cli, backend, tmp_path):
    opts = tmp_path / "hazardous.opts"
    opts.write_text("--preview='cat {}'\n", encoding="utf-8")
    result, payload = run_cli(
        installed_cli,
        backend,
        [
            "--dry-run", "--allow-default-opts-file",
            "--set-env", f"FZF_DEFAULT_OPTS_FILE={opts}",
            "plan", "build", "--mode", "filter", "--item", "x",
        ],
    )
    assert result.returncode == 0
    assert payload["data"]["refused"] is True
    assert {item.get("option") for item in payload["data"]["refusal_reasons"]} == {"--preview"}
    assert {"filesystem_reading", "subprocess_capable"} <= set(payload["data"]["effect_classes"])


@pytest.mark.parametrize(
    "environment",
    ["FZF_DEFAULT_COMMAND=printf unsafe", "SHELL=/bin/sh"],
)
def test_command_capable_environment_values_require_grant(installed_cli, backend, environment):
    result, payload = run_cli(
        installed_cli,
        backend,
        [
            "--dry-run", "--set-env", environment,
            "plan", "build", "--mode", "filter", "--item", "x",
        ],
    )
    assert result.returncode == 0
    assert payload["data"]["refused"] is True
    assert payload["data"]["refusal_reasons"][0]["reason"] == "requires allow-command-actions"


def test_environment_inheritance_without_grant_is_refused_and_value_free(installed_cli, backend):
    secret = "inheritance-secret"
    result, payload = run_cli(
        installed_cli,
        backend,
        [
            "--dry-run", "--env-policy", "inherit",
            "plan", "build", "--mode", "filter", "--item", "x",
        ],
        env={"CLI_ANYTHING_E2E_CREDENTIAL": secret},
    )
    assert result.returncode == 0
    assert payload["data"]["refused"] is True
    assert secret not in result.stdout.decode()
    assert payload["data"]["environment_delta"]["inherited_names"] == []


def test_config_redacts_api_key_verbatim(installed_cli, backend):
    secret = "super-secret-api-key"
    result, payload = run_cli(
        installed_cli, backend, ["config", "inspect"], env={"FZF_API_KEY": secret}
    )
    assert result.returncode == 0
    assert secret not in result.stdout.decode()
    key = payload["data"]["environment"]["FZF_API_KEY"]
    assert key["value"] == "<redacted>"
    assert len(key["sha256_prefix"]) == 12


def test_profile_create_inspect_compose_and_execute(installed_cli, backend, tmp_path):
    base = tmp_path / "base.json"
    override = tmp_path / "override.json"
    created, _ = run_cli(
        installed_cli,
        backend,
        ["--allow-filesystem-write", "profile", "create", str(base), "--name", "base", "--option", "scheme=path", "--option", "layout=default"],
    )
    assert created.returncode == 0
    run_cli(
        installed_cli,
        backend,
        ["--allow-filesystem-write", "profile", "create", str(override), "--name", "override", "--option", "layout=reverse"],
    )
    assert (base.stat().st_mode & 0o777) == 0o600
    assert_schema(json.loads(base.read_text(encoding="utf-8")), "profile")
    inspected, inspect_payload = run_cli(installed_cli, backend, ["profile", "inspect", str(base)])
    assert inspected.returncode == 0
    assert inspect_payload["data"]["resolved"][0]["token"] == "--scheme=path"
    composed, compose_payload = run_cli(installed_cli, backend, ["profile", "compose", str(base), str(override)])
    assert composed.returncode == 0
    assert compose_payload["data"]["option_tokens"] == ["--scheme=path", "--layout=reverse"]
    filtered, payload = run_cli(
        installed_cli,
        backend,
        ["filter", "run", "--query", "srcmod", "--profile", str(base), "--profile", str(override), "--item", "src/module.py"],
    )
    assert filtered.returncode == 0
    assert selection_texts(payload) == ["src/module.py"]


def test_opts_file_requires_grant_and_is_composed(installed_cli, backend, tmp_path):
    opts = tmp_path / "fzf.opts"
    opts.write_text("--layout=reverse --scheme=path\n", encoding="utf-8")
    denied, error = run_cli(
        installed_cli,
        backend,
        ["config", "inspect", "--opts-file", str(opts), "--include-contents"],
    )
    assert_error(denied, error, "default_opts_file_denied")
    allowed, payload = run_cli(
        installed_cli,
        backend,
        ["--allow-default-opts-file", "config", "inspect", "--opts-file", str(opts), "--include-contents"],
    )
    assert allowed.returncode == 0
    assert payload["data"]["opts_file"]["options"] == ["--layout=reverse", "--scheme=path"]


@pytest.mark.parametrize("shell_name", ["bash", "zsh", "fish", "nushell"])
def test_shell_integration_is_retrieved_not_evaluated(installed_cli, backend, shell_name):
    result, payload = run_cli(installed_cli, backend, ["shell", "integration", shell_name])
    assert result.returncode == 0
    assert payload["data"]["shell"] == shell_name
    assert payload["data"]["byte_count"] > 100
    assert len(payload["data"]["sha256"]) == 64


def test_missing_and_wrong_version_backends_have_typed_errors(installed_cli, backend, tmp_path):
    missing = tmp_path / "missing-fzf"
    result, payload = run_cli(installed_cli, missing, ["backend", "inspect"])
    assert_error(result, payload, "backend_not_found", 127)
    wrong = tmp_path / "wrong-fzf"
    wrong.write_text("#!/bin/sh\nprintf '%s\\n' '99.0.0 (wrong)'\n", encoding="utf-8")
    wrong.chmod(0o700)
    mismatch, error = run_cli(installed_cli, wrong, ["backend", "inspect"])
    assert_error(mismatch, error, "backend_version_mismatch")
    allowed, accepted = run_cli(
        installed_cli, wrong, ["--allow-version-mismatch", "backend", "inspect"]
    )
    assert allowed.returncode == 0
    assert accepted["data"]["compatible"] is False


def test_backend_timeout_kills_process_group(installed_cli, tmp_path):
    fake = tmp_path / "slow-fzf"
    fake.write_text(
        "#!/usr/bin/python3\nimport sys,time\n"
        "if '--version' in sys.argv: print('0.74.5 (c0a193e0)')\n"
        "else: time.sleep(10)\n",
        encoding="utf-8",
    )
    fake.chmod(0o700)
    result, payload = run_cli(
        installed_cli,
        fake,
        ["--timeout", "0.1", "filter", "run", "--query", "x", "--item", "x"],
        timeout=4,
    )
    assert_error(result, payload, "backend_timeout", 124)


def test_interactive_pty_single_selection_and_expect_prefix(installed_cli, backend):
    result, payload, terminal = run_interactive(
        installed_cli,
        backend,
        [
            "session", "select", "--query", "beta", "--option", "expect=ctrl-x",
            "--bind", "load:accept", "--item", "alpha", "--item", "beta", "--item", "gamma",
        ],
    )
    assert result.returncode == 0
    assert selection_texts(payload) == ["beta"]
    assert payload["data"]["result"]["expect_key"]["text"] == ""
    assert terminal


def test_interactive_pty_multi_selection(installed_cli, backend):
    result, payload, _ = run_interactive(
        installed_cli,
        backend,
        [
            "session", "select", "--option", "multi", "--bind", "load:select-all+accept",
            "--item", "one", "--item", "two", "--item", "three",
        ],
    )
    assert result.returncode == 0
    assert selection_texts(payload) == ["one", "two", "three"]


def test_real_directory_walker_is_explicit_bounded_and_selectable(installed_cli, backend, tmp_path):
    root = tmp_path / "walker-root"
    root.mkdir()
    (root / "alpha.txt").write_text("alpha", encoding="utf-8")
    (root / "snowman-☃.txt").write_text("unicode", encoding="utf-8")
    ignored_dir = root / "nested"
    ignored_dir.mkdir()
    (ignored_dir / "nested.txt").write_text("nested", encoding="utf-8")
    result, payload, _ = run_interactive(
        installed_cli,
        backend,
        [
            "--allow-walker", "session", "select",
            "--option", "walker=file", "--option", f"walker-root={root}",
            "--option", "multi", "--option", "no-sort",
            "--bind", "load:select-all+accept",
        ],
    )
    assert result.returncode == 0
    selected = {Path(value).name for value in selection_texts(payload) if value is not None}
    assert selected == {"alpha.txt", "snowman-☃.txt", "nested.txt"}
    assert payload["data"]["plan"]["stdin"]["kind"] == "backend-walker"
    assert "filesystem_reading" in payload["data"]["plan"]["effect_classes"]


def test_history_file_is_written_only_with_grant(installed_cli, backend, tmp_path):
    history = tmp_path / "fzf-history"
    result, payload, _ = run_interactive(
        installed_cli,
        backend,
        [
            "--allow-filesystem-write", "session", "select",
            "--option", f"history={history}",
            "--bind", "load:change-query(needle)+accept", "--item", "needle",
        ],
    )
    assert result.returncode == 0
    assert selection_texts(payload) == ["needle"]
    assert history.is_file()
    assert "needle" in history.read_text(encoding="utf-8")
    assert "filesystem_writing" in payload["data"]["plan"]["effect_classes"]


def test_interactive_timeout_is_bounded(installed_cli, backend):
    result, payload, _ = run_interactive(
        installed_cli,
        backend,
        ["--timeout", "0.2", "session", "select", "--item", "one", "--item", "two"],
        timeout=4,
    )
    assert_error(result, payload, "backend_timeout", 124)


def test_timeout_kills_command_action_descendant(installed_cli, backend, tmp_path):
    pid_file = tmp_path / "descendant.pid"
    command = tmp_path / "long-command"
    command.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$$\" > \"$1\"\nexec sleep 30\n",
        encoding="utf-8",
    )
    command.chmod(0o700)
    result, payload, _ = run_interactive(
        installed_cli,
        backend,
        [
            "--timeout", "1.5", "--allow-command-actions", "session", "select",
            "--bind", f"load:execute-silent({command} {pid_file})", "--item", "one",
        ],
        timeout=5,
    )
    assert_error(result, payload, "backend_timeout", 124)
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and (
        not pid_file.is_file() or Path(f"/proc/{pid_file.read_text().strip()}").exists()
    ):
        time.sleep(0.05)
    assert pid_file.is_file()
    assert not Path(f"/proc/{pid_file.read_text().strip()}").exists()


def test_interactive_interrupt_is_bounded(installed_cli, backend):
    result, payload, _ = run_interactive(
        installed_cli,
        backend,
        ["session", "select", "--item", "one", "--item", "two"],
        timeout=4,
        interrupt_after=0.2,
    )
    assert_error(result, payload, "backend_interrupted", 130)


def test_broken_preview_is_explicitly_authorized_and_bounded(installed_cli, backend):
    result, payload, _ = run_interactive(
        installed_cli,
        backend,
        [
            "--allow-command-actions", "session", "select", "--option", "preview=exit 7",
            "--bind", "load:accept", "--item", "one",
        ],
    )
    assert result.returncode == 0
    assert selection_texts(payload) == ["one"]
    assert "subprocess_capable" in payload["data"]["plan"]["effect_classes"]


def test_unix_listener_lifecycle_actions_and_cleanup(installed_cli, backend, tmp_path):
    state_dir = tmp_path / "listener"
    try:
        started, payload = run_cli(
            installed_cli,
            backend,
            ["listener", "start", "--state-dir", str(state_dir), "--item", "alpha", "--item", "beta", "--item", "gamma"],
        )
        assert started.returncode == 0
        state = payload["data"]["result"]
        worker = (state["worker_pid"], state["worker_start_time"])
        child = (state["backend_pid"], state["backend_start_time"])
        assert state["http_status"] == 200
        assert state["backend_state"]["totalCount"] == 3
        assert_schema(state, "listener_state")
        action, action_payload = run_cli(
            installed_cli, backend, ["listener", "action", "--state-dir", str(state_dir), "--action", "change-query(be)"]
        )
        assert action.returncode == 0
        assert action_payload["data"]["hazardous"] is False
        status, status_payload = run_cli(installed_cli, backend, ["listener", "status", "--state-dir", str(state_dir)])
        assert status.returncode == 0
        assert status_payload["data"]["backend_state"]["query"] == "be"
        assert status_payload["data"]["backend_state"]["matchCount"] == 1
        denied, error = run_cli(
            installed_cli,
            backend,
            ["listener", "action", "--state-dir", str(state_dir), "--action", "execute(echo unsafe)"],
        )
        assert_error(denied, error, "command_actions_denied")
        granted, granted_error = run_cli(
            installed_cli,
            backend,
            [
                "--allow-command-actions", "listener", "action", "--state-dir", str(state_dir),
                "--action", "execute(echo still-unsafe)",
            ],
        )
        assert_error(granted, granted_error, "unsafe_listener_required")
        dry, dry_payload = run_cli(
            installed_cli,
            backend,
            [
                "--dry-run", "--allow-command-actions", "listener", "action",
                "--state-dir", str(state_dir), "--action", "execute(echo still-unsafe)",
            ],
        )
        assert dry.returncode == 0
        assert dry_payload["data"]["executed"] is False
        assert [item["code"] for item in dry_payload["data"]["refusal_reasons"]] == [
            "unsafe_listener_required"
        ]
        stopped, stopped_payload = run_cli(
            installed_cli,
            backend,
            ["listener", "stop", "--state-dir", str(state_dir), "--remove-state", "--stop-timeout", "0.5"],
            timeout=5,
        )
        assert stopped.returncode == 0
        assert stopped_payload["data"]["cleanup_verified"] is True
        assert not pid_matches(*worker)
        assert not pid_matches(*child)
        for name in ["state.json", "fzf.sock", "worker.json", "input.bin", "selection.bin"]:
            assert not (state_dir / name).exists()
    finally:
        stop_listener_best_effort(installed_cli, backend, state_dir)


def test_listener_accept_result_preserves_prefix_nul_and_cleanup(installed_cli, backend, tmp_path):
    state_dir = tmp_path / "listener-result"
    try:
        started, payload = run_cli(
            installed_cli,
            backend,
            [
                "listener", "start", "--state-dir", str(state_dir),
                "--option", "query=beta", "--option", "print-query", "--option", "print0",
                "--item", "alpha", "--item", "beta",
            ],
        )
        assert started.returncode == 0
        assert payload["data"]["plan"]["listener"]["output_format"] == {
            "expect": False, "print0": True, "print_query": True
        }
        dry, dry_payload = run_cli(
            installed_cli,
            backend,
            ["--dry-run", "listener", "result", "--state-dir", str(state_dir)],
        )
        assert dry.returncode == 0
        assert dry_payload["data"]["content_read"] is False
        assert dry_payload["data"]["result"] is None
        accepted, _ = run_cli(
            installed_cli,
            backend,
            ["listener", "action", "--state-dir", str(state_dir), "--action", "accept"],
        )
        assert accepted.returncode == 0
        deadline = time.monotonic() + 3
        while True:
            _, status = run_cli(
                installed_cli,
                backend,
                ["listener", "status", "--state-dir", str(state_dir), "--no-probe"],
            )
            if not status["data"]["owned"] or time.monotonic() >= deadline:
                break
            time.sleep(0.05)
        assert status["data"]["owned"] is False
        result, result_payload = run_cli(
            installed_cli,
            backend,
            ["listener", "result", "--state-dir", str(state_dir)],
        )
        assert result.returncode == 0
        data = result_payload["data"]
        assert data["completion_observed"] is True
        assert data["result"]["query"]["text"] == "beta"
        assert [item["text"] for item in data["result"]["selections"]] == ["beta"]
        assert data["result"]["record_separator"] == "nul"
        assert_schema(data["result"], "selection_result")
        cleaned, clean_payload = run_cli(
            installed_cli,
            backend,
            ["listener", "clean-stale", "--state-dir", str(state_dir)],
        )
        assert cleaned.returncode == 0
        assert str(state_dir / "selection.bin") in clean_payload["data"]["removed"]
    finally:
        stop_listener_best_effort(installed_cli, backend, state_dir)


def test_listener_collision_preserves_foreign_file(installed_cli, backend, tmp_path):
    state_dir = tmp_path / "collision"
    state_dir.mkdir()
    collision = state_dir / "fzf.sock"
    collision.write_text("foreign", encoding="utf-8")
    result, payload = run_cli(
        installed_cli, backend, ["listener", "start", "--state-dir", str(state_dir), "--item", "x"]
    )
    assert_error(result, payload, "socket_collision")
    assert collision.read_text(encoding="utf-8") == "foreign"


def test_listener_symlink_collision_is_preserved(installed_cli, backend, tmp_path):
    state_dir = tmp_path / "symlink-collision"
    state_dir.mkdir()
    target = state_dir / "foreign-target"
    target.write_text("foreign", encoding="utf-8")
    collision = state_dir / "fzf.sock"
    collision.symlink_to(target)
    result, payload = run_cli(
        installed_cli, backend, ["listener", "start", "--state-dir", str(state_dir), "--item", "x"]
    )
    assert_error(result, payload, "socket_collision")
    assert collision.is_symlink()
    assert target.read_text(encoding="utf-8") == "foreign"


def test_listener_dangling_symlink_collision_is_preserved(installed_cli, backend, tmp_path):
    state_dir = tmp_path / "dangling-collision"
    state_dir.mkdir()
    collision = state_dir / "fzf.sock"
    collision.symlink_to(state_dir / "missing-target")
    result, payload = run_cli(
        installed_cli, backend, ["listener", "start", "--state-dir", str(state_dir), "--item", "x"]
    )
    assert_error(result, payload, "socket_collision")
    assert collision.is_symlink()


def test_listener_rejects_socket_outside_state_boundary(installed_cli, backend, tmp_path):
    state_dir = tmp_path / "contained"
    outside = tmp_path / "outside.sock"
    result, payload = run_cli(
        installed_cli,
        backend,
        [
            "--dry-run", "listener", "start", "--state-dir", str(state_dir),
            "--address", str(outside), "--item", "x",
        ],
    )
    assert_error(result, payload, "path_outside_boundary")
    assert not state_dir.exists()
    assert not outside.exists()


def test_listener_startup_failure_leaves_evidence_without_orphans(installed_cli, tmp_path):
    backend = tmp_path / "failing-fzf"
    backend.write_text(
        "#!/usr/bin/python3\nimport signal,sys,time\n"
        "if '--version' in sys.argv:\n print('0.74.5 (c0a193e0)')\n raise SystemExit(0)\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\ntime.sleep(30)\n",
        encoding="utf-8",
    )
    backend.chmod(0o700)
    state_dir = tmp_path / "failed-listener"
    result, payload = run_cli(
        installed_cli,
        backend,
        [
            "listener", "start", "--state-dir", str(state_dir),
            "--startup-timeout", "0.2", "--item", "x",
        ],
        timeout=5,
    )
    assert_error(result, payload, "listener_start_failed")
    state = json.loads((state_dir / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "failed"
    assert state["worker_pid"] is None
    assert state["backend_pid"] is None
    assert not pid_matches(state["last_worker_pid"], state["worker_start_time"])
    assert not pid_matches(state["last_backend_pid"], state["backend_start_time"])
    for name in ["worker.json", "input.bin", "selection.bin", "fzf.sock"]:
        assert not (state_dir / name).exists()


def test_listener_dry_run_does_not_create_missing_state(installed_cli, backend, tmp_path):
    state_dir = tmp_path / "missing-state"
    result, payload = run_cli(
        installed_cli,
        backend,
        ["--dry-run", "listener", "action", "--state-dir", str(state_dir), "--action", "abort"],
    )
    assert_error(result, payload, "listener_not_found")
    assert not state_dir.exists()


def test_authenticated_unix_listener_never_echoes_key(installed_cli, backend, tmp_path):
    state_dir = tmp_path / "authenticated"
    key_file = tmp_path / "api.key"
    secret = "listener-secret-value"
    key_file.write_text(secret + "\n", encoding="utf-8")
    key_file.chmod(0o600)
    wrong_key_file = tmp_path / "wrong-api.key"
    wrong_key_file.write_text("wrong-secret\n", encoding="utf-8")
    wrong_key_file.chmod(0o600)
    try:
        started, payload = run_cli(
            installed_cli,
            backend,
            ["listener", "start", "--state-dir", str(state_dir), "--api-key-file", str(key_file), "--item", "x"],
        )
        assert started.returncode == 0
        assert secret not in started.stdout.decode()
        assert payload["data"]["result"]["authenticated"] is True
        denied, error = run_cli(installed_cli, backend, ["listener", "status", "--state-dir", str(state_dir)])
        assert_error(denied, error, "listener_auth_required")
        wrong, wrong_error = run_cli(
            installed_cli,
            backend,
            ["listener", "status", "--state-dir", str(state_dir), "--api-key-file", str(wrong_key_file)],
        )
        assert_error(wrong, wrong_error, "listener_auth_required")
        allowed, status = run_cli(
            installed_cli,
            backend,
            ["listener", "status", "--state-dir", str(state_dir), "--api-key-file", str(key_file)],
        )
        assert allowed.returncode == 0
        assert status["data"]["http_status"] == 200
    finally:
        stop_listener_best_effort(installed_cli, backend, state_dir)


def test_unsafe_listener_dry_run_lists_every_refusal(installed_cli, backend, tmp_path):
    state_dir = tmp_path / "unsafe"
    result, payload = run_cli(
        installed_cli,
        backend,
        ["--dry-run", "listener", "start", "--state-dir", str(state_dir), "--unsafe", "--item", "x"],
    )
    assert result.returncode == 0
    plan = payload["data"]["plan"]
    assert plan["refused"] is True
    reasons = {item["reason"] for item in plan["refusal_reasons"]}
    assert "requires allow-unsafe-listener" in reasons
    assert "requires allow-command-actions" in reasons
    assert "requires api-key-file" in reasons
    assert not state_dir.exists()


@pytest.mark.parametrize(
    ("global_injection", "listener_injection"),
    [
        (["--set-env", "FZF_DEFAULT_OPTS=--listen-unsafe=/tmp/unowned-fzf.sock"], []),
        ([], ["--option", "listen-unsafe=/tmp/unowned-fzf.sock"]),
    ],
)
def test_listener_mode_cannot_be_injected_through_declarative_options(
    installed_cli, backend, tmp_path, global_injection, listener_injection
):
    state_dir = tmp_path / "managed-only"
    result, payload = run_cli(
        installed_cli,
        backend,
        [
            "--dry-run", "--allow-unsafe-listener", *global_injection,
            "listener", "start", "--state-dir", str(state_dir),
            *listener_injection, "--item", "x",
        ],
    )
    assert result.returncode == 0
    reasons = {item["reason"] for item in payload["data"]["plan"]["refusal_reasons"]}
    assert "listener addresses and safety mode are owned exclusively by listener start" in reasons
    assert not state_dir.exists()


def test_authenticated_unsafe_listener_executes_only_with_all_grants(installed_cli, backend, tmp_path):
    state_dir = tmp_path / "unsafe-live"
    key_file = tmp_path / "unsafe-api.key"
    marker = tmp_path / "unsafe-action-ran"
    secret = "unsafe-listener-secret"
    key_file.write_text(secret + "\n", encoding="utf-8")
    key_file.chmod(0o600)
    try:
        started, payload = run_cli(
            installed_cli,
            backend,
            [
                "--allow-unsafe-listener", "--allow-command-actions",
                "listener", "start", "--state-dir", str(state_dir), "--unsafe",
                "--api-key-file", str(key_file), "--item", "x",
            ],
        )
        assert started.returncode == 0
        assert payload["data"]["result"]["unsafe"] is True
        assert payload["data"]["result"]["authenticated"] is True
        assert secret not in started.stdout.decode()
        action, action_payload = run_cli(
            installed_cli,
            backend,
            [
                "--allow-command-actions", "listener", "action", "--state-dir", str(state_dir),
                "--api-key-file", str(key_file),
                "--action", f"execute-silent(printf unsafe > {marker})",
            ],
        )
        assert action.returncode == 0
        assert action_payload["data"]["hazardous"] is True
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not marker.is_file():
            time.sleep(0.05)
        assert marker.read_text(encoding="utf-8") == "unsafe"
    finally:
        stop_listener_best_effort(installed_cli, backend, state_dir)


def test_loopback_tcp_listener_requires_grant_then_cleans_up(installed_cli, backend, tmp_path):
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    state_dir = tmp_path / "tcp"
    address = f"127.0.0.1:{port}"
    denied, payload = run_cli(
        installed_cli,
        backend,
        ["--dry-run", "listener", "start", "--state-dir", str(state_dir), "--address", address, "--item", "x"],
    )
    assert denied.returncode == 0
    assert payload["data"]["plan"]["refused"] is True
    try:
        started, result = run_cli(
            installed_cli,
            backend,
            ["--allow-network-listener", "listener", "start", "--state-dir", str(state_dir), "--address", address, "--item", "x"],
        )
        assert started.returncode == 0
        assert result["data"]["result"]["address"]["kind"] == "tcp"
        assert result["data"]["result"]["http_status"] == 200
    finally:
        stop_listener_best_effort(installed_cli, backend, state_dir)


def test_non_loopback_listener_requires_authentication_even_with_network_grant(
    installed_cli, backend, tmp_path
):
    state_dir = tmp_path / "non-loopback"
    result, payload = run_cli(
        installed_cli,
        backend,
        [
            "--dry-run", "--allow-network-listener", "listener", "start",
            "--state-dir", str(state_dir), "--address", "0.0.0.0:12345", "--item", "x",
        ],
    )
    assert result.returncode == 0
    assert payload["data"]["plan"]["refused"] is True
    assert {item["reason"] for item in payload["data"]["plan"]["refusal_reasons"]} == {
        "requires api-key-file"
    }
    assert not state_dir.exists()


def test_listener_abort_then_stale_cleanup(installed_cli, backend, tmp_path):
    state_dir = tmp_path / "stale"
    try:
        started, _ = run_cli(
            installed_cli, backend, ["listener", "start", "--state-dir", str(state_dir), "--item", "x"]
        )
        assert started.returncode == 0
        action, _ = run_cli(
            installed_cli, backend, ["listener", "action", "--state-dir", str(state_dir), "--action", "abort"]
        )
        assert action.returncode == 0
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            _, status = run_cli(
                installed_cli, backend, ["listener", "status", "--state-dir", str(state_dir), "--no-probe"]
            )
            if not status["data"]["owned"]:
                break
            time.sleep(0.05)
        assert status["data"]["owned"] is False
        cleaned, payload = run_cli(
            installed_cli, backend, ["listener", "clean-stale", "--state-dir", str(state_dir)]
        )
        assert cleaned.returncode == 0
        assert str(state_dir / "state.json") in payload["data"]["removed"]
        assert not (state_dir / "state.json").exists()
    finally:
        stop_listener_best_effort(installed_cli, backend, state_dir)


def test_json_usage_error_envelope_is_deterministic(installed_cli, backend):
    args = ["filter", "run", "--query", "x", "--option", "not-a-real-option", "--item", "x"]
    first, payload_one = run_cli(installed_cli, backend, args)
    second, payload_two = run_cli(installed_cli, backend, args)
    assert first.returncode == second.returncode == 2
    assert payload_one == payload_two == {
        "error": {"code": "option_unknown", "message": "Unknown fzf option: 'not-a-real-option'"},
        "ok": False,
    }
    assert_schema(payload_one, "error_envelope")
