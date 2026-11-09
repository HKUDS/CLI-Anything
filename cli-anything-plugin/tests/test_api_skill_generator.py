"""Backend-aware skill generation, static command discovery, and rendered usage."""

import json
import shlex
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skill_generator import (
    extract_cli_metadata,
    extract_commands_from_cli,
    generate_skill_file,
    generate_skill_md,
    generate_skill_md_simple,
)


@pytest.fixture
def harness(tmp_path):
    root = tmp_path / "cloud-service" / "agent-harness"
    package = root / "cli_anything" / "cloud_service"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (root / "README.md").write_text(
        '# Cloud Service\n\nManage "remote" jobs: create, inspect, and export.\n',
        encoding="utf-8",
    )
    (root / "setup.py").write_text(textwrap.dedent('''\
        from setuptools import setup
        raise RuntimeError("setup must never run during extraction")
        setup(version="2.0.0", entry_points={"console_scripts": [
            "cli-anything-cloud-service=cli_anything.cloud_service.commands:cli"
        ]})
    '''), encoding="utf-8")
    (package / "commands.py").write_text(textwrap.dedent('''\
        import click
        from .jobs import job_group as imported_jobs

        @click.group()
        @click.option("--json", is_flag=True)
        def cli(json):
            """Cloud service operations."""
            pass

        @cli.command(name="health")
        def check_health():
            """Check service health."""
            pass

        cli.add_command(imported_jobs, name="jobs")
    '''), encoding="utf-8")
    (package / "jobs.py").write_text(textwrap.dedent('''\
        import click

        @click.group("internal-name")
        def job_group():
            """Manage remote jobs."""
            pass

        @job_group.command("list")
        def list_jobs():
            """List jobs | include pending jobs.

            Return the current job collection.
            """
            pass

        @job_group.group("artifacts")
        def artifact_group():
            """Inspect artifacts."""
            pass

        @artifact_group.command(name="download")
        @click.argument("job_id")
        @click.option("--output", required=True)
        def download(job_id, output):
            """Download an artifact."""
            pass

        @job_group.command("delete", hidden=True)
        def delete_job():
            pass
    '''), encoding="utf-8")
    return root


def metadata_file(root, backend):
    (root / "harness.json").write_text(
        json.dumps({"schema_version": 1, "backend": backend}), encoding="utf-8")


def command_paths(metadata):
    return [command.path for group in metadata.command_groups for command in group.commands]


def test_extracts_api_backend_from_declaration_without_reading_credentials(harness, monkeypatch):
    monkeypatch.setenv("CLOUD_TOKEN", "SECRET_VALUE_DO_NOT_COPY")
    metadata_file(harness, {
        "type": "api", "base_url_env": "CLOUD_BASE_URL", "auth_env": ["CLOUD_TOKEN"],
        "requirements": ["Access to the Cloud Service public API"],
    })
    metadata = extract_cli_metadata(str(harness))
    assert metadata.entry_point == "cli-anything-cloud-service"
    assert metadata.version == "2.0.0"
    assert metadata.backend.type == "api"
    assert "remote" in metadata.skill_intro  # Root-level README fallback.
    assert metadata.backend.auth_env == ["CLOUD_TOKEN"]
    assert command_paths(metadata) == [("health",), ("jobs", "list"), ("jobs", "artifacts", "download")]
    for render in (generate_skill_md_simple, generate_skill_md):
        content = render(metadata)
        assert "CLOUD_TOKEN" in content and "CLOUD_BASE_URL" in content
        assert "SECRET_VALUE_DO_NOT_COPY" not in content
        assert "no local application binary is required" in content
        assert "must be installed on your system" not in content
        assert "project new" not in content and "project info" not in content
        assert "50 levels" not in content and "REPL Session" not in content
        assert "jobs artifacts download" in content
        assert "jobs delete" not in content
        assert "List jobs \\| include pending jobs." in content
        assert "poll remote jobs" in content


@pytest.mark.parametrize("backend,expected", [
    ({"type": "local"}, "must be installed on your system"),
    ({"type": "mcp"}, "configured, reachable MCP server"),
    ({"type": "api"}, "no local application binary is required"),
])
def test_renderer_backend_parity(harness, backend, expected):
    metadata_file(harness, backend)
    metadata = extract_cli_metadata(str(harness))
    for render in (generate_skill_md_simple, generate_skill_md):
        assert expected in render(metadata)


def test_unknown_backend_does_not_invent_local_dependency(harness):
    metadata = extract_cli_metadata(str(harness))
    assert metadata.backend.type == "unknown"
    for render in (generate_skill_md_simple, generate_skill_md):
        assert "backend requirements documented in the package README" in render(metadata)
        assert "must be installed on your system" not in render(metadata)


def test_known_local_dependency_is_preserved_but_api_declaration_wins(harness):
    (harness / "README.md").write_text("# App\n\nInstall `brew install tool`.\n")
    assert extract_cli_metadata(str(harness)).backend.type == "local"
    assert "brew install tool" in generate_skill_md_simple(extract_cli_metadata(str(harness)))
    metadata_file(harness, {"type": "api"})
    content = generate_skill_md_simple(extract_cli_metadata(str(harness)))
    prerequisites = content.split("**Prerequisites:**", 1)[1].split("## Usage", 1)[0]
    assert "brew install tool" not in prerequisites


@pytest.mark.parametrize("data", [
    [], {}, {"schema_version": True, "backend": {"type": "api"}},
    {"schema_version": 2, "backend": {"type": "api"}},
    {"schema_version": 1, "backend": []},
    *[{"schema_version": 1, "backend": backend} for backend in [
        {}, {"type": "cloud"}, {"type": "api", "token": "secret"},
        {"type": "api", "base_url_env": "https://example.com"},
        {"type": "api", "base_url_env": None}, {"type": "api", "auth_env": "TOKEN"},
        {"type": "api", "auth_env": ["TOKEN=value"]},
        {"type": "api", "auth_env": ["TOKEN\nOTHER"]},
        {"type": "api", "requirements": [""]}, {"type": "api", "requirements": [1]},
        {"type": "api", "requirements": "service access"},
    ]],
])
def test_rejects_invalid_metadata_before_writing_skills(harness, data):
    (harness / "harness.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="harness.json"):
        generate_skill_file(str(harness))
    assert not (harness.parent.parent / "skills").exists()


def test_malformed_metadata_is_not_silently_ignored(harness):
    (harness / "harness.json").write_text('{"backend":', encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid harness.json"):
        extract_cli_metadata(str(harness))


def test_analysis_never_imports_target_modules(harness):
    package = harness / "cli_anything" / "cloud_service"
    marker = harness / "executed.txt"
    with (package / "jobs.py").open("a", encoding="utf-8") as target:
        target.write(f"\nfrom pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n")
    metadata = extract_cli_metadata(str(harness))
    assert ("jobs", "artifacts", "download") in command_paths(metadata)
    assert not marker.exists()


def test_generated_examples_resolve_against_real_click_tree(harness, monkeypatch):
    pytest.importorskip("click")
    monkeypatch.syspath_prepend(str(harness))
    from click.testing import CliRunner
    from cli_anything.cloud_service.commands import cli
    try:
        metadata = extract_cli_metadata(str(harness))
        for example in metadata.examples:
            for line in example.code.splitlines():
                args = shlex.split(line)
                assert args.pop(0) == metadata.entry_point
                assert args[-1] == "--help"
                result = CliRunner().invoke(cli, args)
                assert result.exit_code == 0, result.output
    finally:
        for name in list(sys.modules):
            if name == "cli_anything" or name.startswith("cli_anything.cloud_service"):
                sys.modules.pop(name)


def test_canonical_and_compatibility_outputs_match_and_have_valid_yaml(harness):
    yaml = pytest.importorskip("yaml")
    pytest.importorskip("jinja2")
    metadata_file(harness, {"type": "api", "auth_env": ["CLOUD_TOKEN"]})
    output = Path(generate_skill_file(str(harness)))
    compatibility = harness / "cli_anything/cloud_service/skills/SKILL.md"
    assert output.read_bytes() == compatibility.read_bytes()
    metadata = extract_cli_metadata(str(harness))
    for content in (output.read_text(), generate_skill_md_simple(metadata)):
        frontmatter = yaml.safe_load(content.split("---", 2)[1])
        assert frontmatter["name"] == "cli-anything-cloud-service"
        assert frontmatter["description"] == metadata.skill_description


def test_standalone_generator_subprocess(harness):
    metadata_file(harness, {"type": "api"})
    script = Path(__file__).resolve().parents[1] / "skill_generator.py"
    output = harness / "generated.md"
    result = subprocess.run([sys.executable, str(script), str(harness), "-o", str(output)],
                            text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "Generated:" in result.stdout
    assert "jobs artifacts download" in output.read_text()


def test_registration_aliases_cycles_and_hidden_groups(tmp_path):
    path = tmp_path / "cli.py"
    path.write_text(textwrap.dedent('''\
        import click
        @click.group()
        def cli(): pass
        @click.group()
        def remote(): pass
        @remote.command("show")
        def show(): pass
        @remote.group(hidden=True)
        def hidden_group(): pass
        @hidden_group.command()
        def secret(): pass
        remote.add_command(remote, "cycle")
        cli.add_command(remote, "first")
        cli.add_command(remote, name="second")
        @click.group()
        def unattached(): pass
        @unattached.command()
        def absent(): pass
    '''))
    groups = extract_commands_from_cli(path)
    paths = [command.path for group in groups for command in group.commands]
    assert paths == [("first", "show"), ("second", "show")]


@pytest.mark.parametrize("import_line,reference", [
    ("from . import jobs", "jobs.job_group"),
    ("from cli_anything.cloud_service import jobs", "jobs.job_group"),
    ("import cli_anything.cloud_service.jobs as jobs", "jobs.job_group"),
    ("import cli_anything.cloud_service.jobs", "cli_anything.cloud_service.jobs.job_group"),
    ("from .exports import exported_jobs", "exported_jobs"),
])
def test_module_import_and_reexport_registration(harness, import_line, reference):
    package = harness / "cli_anything/cloud_service"
    (package / "exports.py").write_text("from .jobs import job_group as exported_jobs\n")
    (package / "commands.py").write_text(
        f"import click\n{import_line}\n@click.group()\ndef cli(): pass\n"
        f"cli.add_command({reference}, 'remote')\n")
    assert command_paths(extract_cli_metadata(str(harness))) == [
        ("remote", "list"), ("remote", "artifacts", "download")]


def test_cyclic_import_aliases_terminate(harness):
    package = harness / "cli_anything/cloud_service"
    (package / "a.py").write_text("from .b import cycle\n")
    (package / "b.py").write_text("from .a import cycle\n")
    (package / "commands.py").write_text(
        "import click\nfrom .a import cycle\n@click.group()\ndef cli(): pass\n"
        "cli.add_command(cycle)\n")
    assert command_paths(extract_cli_metadata(str(harness))) == []


def test_last_explicit_registration_uses_click_alias_semantics(harness):
    path = harness / "cli_anything/cloud_service/commands.py"
    path.write_text(textwrap.dedent('''\
        import click
        @click.group()
        def cli(): pass
        @cli.command("show")
        def first():
            """Old implementation."""
        @click.command()
        def replacement():
            """New implementation."""
        cli.add_command(replacement, "show")
    '''))
    metadata = extract_cli_metadata(str(harness))
    assert command_paths(metadata) == [("show",)]
    assert metadata.command_groups[0].commands[0].description == "New implementation."


def test_later_decorator_can_replace_an_explicit_registration(harness):
    path = harness / "cli_anything/cloud_service/commands.py"
    path.write_text(textwrap.dedent('''\
        import click
        @click.group()
        def cli(): pass
        @click.command()
        def old():
            """Old implementation."""
        cli.add_command(old, "show")
        @cli.command("show")
        def new():
            """New implementation."""
    '''))
    metadata = extract_cli_metadata(str(harness))
    assert command_paths(metadata) == [("show",)]
    assert metadata.command_groups[0].commands[0].description == "New implementation."


def test_dynamic_command_names_are_not_guessed(harness):
    path = harness / "cli_anything/cloud_service/commands.py"
    path.write_text(textwrap.dedent('''\
        import click
        @click.group()
        def cli(): pass
        @cli.command(compute_name())
        def unknown(): pass
        @cli.command(name=compute_name())
        def also_unknown(): pass
    '''))
    assert command_paths(extract_cli_metadata(str(harness))) == []


def test_console_script_selects_a_nonstandard_root_function(harness):
    path = harness / "cli_anything/cloud_service/commands.py"
    path.write_text(textwrap.dedent('''\
        import click
        @click.group()
        def service_root(): pass
        @service_root.command()
        def ping(): pass
        @click.group()
        def cli(): pass
        @cli.command()
        def unrelated(): pass
    '''))
    setup = harness / "setup.py"
    setup.write_text(setup.read_text().replace("commands:cli", "commands:service_root"))
    assert command_paths(extract_cli_metadata(str(harness))) == [("ping",)]


def test_rejects_ambiguous_packages_and_console_scripts(harness):
    setup = harness / "setup.py"
    setup.write_text('entry_points={"console_scripts": ['
                     '"first=cli_anything.cloud_service.commands:cli",'
                     '"second=cli_anything.cloud_service.commands:cli"]}')
    # Use the supported setup keyword form.
    setup.write_text("setup(" + setup.read_text() + ")")
    with pytest.raises(ValueError, match="Multiple console scripts"):
        extract_cli_metadata(str(harness))
    other = harness / "cli_anything/other"
    other.mkdir()
    (other / "__init__.py").write_text("")
    with pytest.raises(ValueError, match="Multiple CLI packages"):
        extract_cli_metadata(str(harness))


def test_root_command_examples_do_not_invent_a_subcommand(harness):
    path = harness / "cli_anything/cloud_service/commands.py"
    path.write_text("import click\n@click.command()\ndef cli(): pass\n")
    metadata = extract_cli_metadata(str(harness))
    assert command_paths(metadata) == [()]
    assert all(" cli " not in example.code for example in metadata.examples)
    assert "| `cli` |" not in generate_skill_md_simple(metadata)
    assert "| `cli-anything-cloud-service` |" in generate_skill_md_simple(metadata)


def test_console_script_package_reexport(harness):
    package = harness / "cli_anything/cloud_service"
    (package / "__init__.py").write_text("from .commands import cli as main\n")
    setup = harness / "setup.py"
    setup.write_text(setup.read_text().replace("cloud_service.commands:cli", "cloud_service:main"))
    metadata = extract_cli_metadata(str(harness))
    assert ("jobs", "list") in command_paths(metadata)


def test_empty_harness_reports_discovery_gap(harness):
    path = harness / "cli_anything/cloud_service/commands.py"
    path.write_text("# Dynamically registered elsewhere\n")
    metadata = extract_cli_metadata(str(harness))
    for render in (generate_skill_md_simple, generate_skill_md):
        content = render(metadata)
        assert "No statically discoverable commands" in content
        assert "| Command |" not in content
        assert "project new" not in content


def test_fallback_renderer_without_jinja2(harness, monkeypatch):
    monkeypatch.setitem(sys.modules, "jinja2", None)
    metadata_file(harness, {"type": "api", "auth_env": ["TOKEN"]})
    metadata = extract_cli_metadata(str(harness))
    assert generate_skill_md(metadata) == generate_skill_md_simple(metadata)


def test_existing_api_harnesses_have_real_command_examples():
    repo = Path(__file__).resolve().parents[2]
    for name, expected in [("anygen", ("task", "create")), ("adguardhome", ("server", "status"))]:
        metadata = extract_cli_metadata(str(repo / name / "agent-harness"))
        assert expected in command_paths(metadata)
        assert "project new" not in "\n".join(example.code for example in metadata.examples)
