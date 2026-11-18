"""CLI tests: argument handling, JSON output and exit codes."""

import json
import textwrap

import pytest
from click.testing import CliRunner

from cli_anything.controlplane.cli import cli


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


@pytest.fixture
def repo(tmp_path):
    write(tmp_path / "docker-compose.yml", """\
        name: ControlPlane
        include:
          - caddy/docker-compose.yml
          - app/docker-compose.yml
        """)
    write(tmp_path / "caddy" / "docker-compose.yml", """\
        services:
          caddy:
            image: caddy:2.8
            container_name: caddy
            ports:
              - "443:443"
        """)
    write(tmp_path / "app" / "docker-compose.yml", """\
        services:
          app:
            image: ghcr.io/example/app:1.2.3
            container_name: app
            ports:
              - "3000:3000"
        """)
    write(tmp_path / "caddy" / "Caddyfile", """\
        app.example.com {
            reverse_proxy app:3000
        }

        alpha.example.com, beta.example.com {
            redir https://example.com{uri} permanent
        }
        """)
    return tmp_path


@pytest.fixture
def runner():
    return CliRunner()


class TestStackCommands:
    def test_stack_list(self, runner, repo):
        result = runner.invoke(cli, ["--repo", str(repo), "stack", "list"])
        assert result.exit_code == 0
        assert "caddy" in result.output and "app" in result.output

    def test_stack_list_json(self, runner, repo):
        result = runner.invoke(cli, ["--repo", str(repo), "--json", "stack", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert {row["dir"] for row in data} == {"caddy", "app"}

    def test_stack_show_by_dir_name(self, runner, repo):
        result = runner.invoke(cli, ["--repo", str(repo), "stack", "show", "app"])
        assert result.exit_code == 0
        assert "ghcr.io/example/app:1.2.3" in result.output

    def test_stack_show_unknown_exits_nonzero(self, runner, repo):
        result = runner.invoke(cli, ["--repo", str(repo), "stack", "show", "nope"])
        assert result.exit_code != 0
        assert "unknown stack" in result.output

    def test_stack_validate_ok(self, runner, repo):
        result = runner.invoke(cli, ["--repo", str(repo), "stack", "validate"])
        assert result.exit_code == 0
        assert "no issues found" in result.output

    def test_stack_validate_fails_on_error(self, runner, repo):
        write(repo / "broken" / "docker-compose.yml", """\
            services:
              x:
                restart: always
            """)
        result = runner.invoke(cli, ["--repo", str(repo), "stack", "validate"])
        assert result.exit_code == 1
        assert "needs 'image' or 'build'" in result.output

    def test_service_list_json(self, runner, repo):
        result = runner.invoke(cli, ["--repo", str(repo), "--json", "service", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert {row["service"] for row in data} == {"caddy", "app"}


class TestCaddyCommands:
    def test_caddy_sites(self, runner, repo):
        result = runner.invoke(cli, ["--repo", str(repo), "caddy", "sites"])
        assert result.exit_code == 0
        assert "app.example.com" in result.output
        assert "app:3000" in result.output

    def test_caddy_sites_json_shape(self, runner, repo):
        result = runner.invoke(cli, ["--repo", str(repo), "--json", "caddy", "sites"])
        data = json.loads(result.output)
        assert data[0]["kind"] in {"reverse_proxy", "redirect"}
        assert any(site["upstreams"] == ["app:3000"] for site in data)

    def test_caddy_hosts(self, runner, repo):
        result = runner.invoke(cli, ["--repo", str(repo), "caddy", "hosts"])
        assert result.exit_code == 0
        hosts = result.output.split()
        assert {"alpha.example.com", "beta.example.com", "app.example.com"} <= set(hosts)

    def test_caddy_find(self, runner, repo):
        result = runner.invoke(cli, ["--repo", str(repo), "caddy", "find", "app.example.com"])
        assert result.exit_code == 0
        assert "app:3000" in result.output

    def test_caddy_find_unknown_exits_nonzero(self, runner, repo):
        result = runner.invoke(cli, ["--repo", str(repo), "caddy", "find", "nope.example.com"])
        assert result.exit_code != 0
        assert "no site block serves" in result.output

    def test_caddy_validate_missing_file(self, runner, tmp_path):
        result = runner.invoke(cli, ["--repo", str(tmp_path), "caddy", "validate"])
        assert result.exit_code != 0

    def test_custom_caddyfile_path(self, runner, repo, tmp_path):
        custom = write(tmp_path / "other" / "Caddyfile", """\
            only.example.com {
                reverse_proxy only:9000
            }
            """)
        result = runner.invoke(
            cli, ["--repo", str(repo), "--caddyfile", str(custom), "caddy", "hosts"]
        )
        assert result.exit_code == 0
        assert "only.example.com" in result.output


class TestDoctor:
    def test_doctor_reports_unproxied_service(self, runner, repo):
        result = runner.invoke(cli, ["--repo", str(repo), "--json", "doctor"])
        data = json.loads(result.output)
        # caddy publishes 443 but no site block proxies to it
        assert "caddy/caddy" in data["unproxied_services"] or "ControlPlane/caddy" in data["unproxied_services"]
        assert data["sites"] == 2

    def test_doctor_ok_on_fully_wired_repo(self, runner, repo):
        write(repo / "caddy" / "docker-compose.yml", """\
            services:
              caddy:
                image: caddy:2.8
                ports:
                  - "443:443"
            """)
        write(repo / "caddy" / "Caddyfile", """\
            app.example.com {
                reverse_proxy app:3000
            }
            proxy.example.com {
                reverse_proxy caddy:443
            }
            """)
        result = runner.invoke(cli, ["--repo", str(repo), "--json", "doctor"])
        data = json.loads(result.output)
        assert data["unproxied_services"] == []
        assert data["ok"] is True

    def test_doctor_fails_without_caddyfile(self, runner, tmp_path):
        write(tmp_path / "docker-compose.yml", "services: {}\n")
        result = runner.invoke(cli, ["--repo", str(tmp_path), "doctor"])
        assert result.exit_code != 0
        assert "Caddyfile" in result.output
