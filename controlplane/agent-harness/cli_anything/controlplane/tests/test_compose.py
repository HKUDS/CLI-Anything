"""Unit tests for the compose parser."""

import textwrap

import pytest

from cli_anything.controlplane.core.compose import (
    ComposeError,
    find_compose_file,
    list_stacks,
    load_stack,
    merged_services,
    read_yaml,
    repo_root,
    validate,
)


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
          - adguard-home/docker-compose.yml
        networks:
          vps_infra:
            external: true
        """)
    write(tmp_path / "caddy" / "docker-compose.yml", """\
        services:
          caddy:
            image: caddy:2.8
            container_name: caddy
            restart: unless-stopped
            ports:
              - "80:80/tcp"
              - "443:443/tcp"
            volumes:
              - ./Caddyfile:/etc/caddy/Caddyfile:ro
        """)
    write(tmp_path / "adguard-home" / "docker-compose.yml", """\
        services:
          adguard:
            image: adguard/adguardhome:latest
            container_name: adguard
            ports:
              - "127.0.0.1:3000:3000"
            depends_on:
              - caddy
        """)
    return tmp_path


class TestDiscovery:
    def test_find_compose_file_prefers_yml(self, tmp_path):
        write(tmp_path / "docker-compose.yml", "services: {}\n")
        assert find_compose_file(tmp_path).name == "docker-compose.yml"

    def test_find_compose_file_returns_none_when_absent(self, tmp_path):
        assert find_compose_file(tmp_path) is None

    def test_repo_root_walks_up_to_include_file(self, repo):
        nested = repo / "caddy" / "deep" / "dir"
        nested.mkdir(parents=True)
        assert repo_root(nested) == repo.resolve()

    def test_list_stacks_skips_dot_directories(self, repo):
        (repo / ".hidden").mkdir()
        write(repo / ".hidden" / "docker-compose.yml", "services: {}\n")
        names = [s.path.name for s in list_stacks(repo)]
        assert ".hidden" not in names
        assert {"caddy", "adguard-home"} <= set(names)


class TestParsing:
    def test_ports_string_forms(self, repo):
        stack = load_stack(repo / "caddy")
        ports = {p.host: p.container for p in stack.services[0].ports}
        assert ports == {"80": "80", "443": "443"}

    def test_ports_with_bind_address(self, repo):
        stack = load_stack(repo / "adguard-home")
        port = stack.services[0].ports[0]
        assert port.host == "3000"
        assert port.container == "3000"

    def test_depends_on_list(self, repo):
        stack = load_stack(repo / "adguard-home")
        assert stack.services[0].depends_on == ["caddy"]

    def test_depends_on_mapping(self, tmp_path):
        write(tmp_path / "docker-compose.yml", """\
            services:
              app:
                image: nginx
                depends_on:
                  db:
                    condition: service_started
            """)
        assert load_stack(tmp_path).services[0].depends_on == ["db"]

    def test_environment_keys_only(self, tmp_path):
        write(tmp_path / "docker-compose.yml", """\
            services:
              app:
                image: nginx
                environment:
                  TOKEN: secret
                  DEBUG: "1"
            """)
        stack = load_stack(tmp_path)
        assert stack.services[0].environment == ["TOKEN", "DEBUG"]

    def test_invalid_yaml_raises(self, tmp_path):
        write(tmp_path / "docker-compose.yml", "services: [unclosed\n")
        with pytest.raises(ComposeError):
            read_yaml(tmp_path / "docker-compose.yml")

    def test_services_not_mapping_raises(self, tmp_path):
        write(tmp_path / "docker-compose.yml", "- just\n- a list\n")
        with pytest.raises(ComposeError):
            load_stack(tmp_path)

    def test_merged_services_expands_includes(self, repo):
        services = merged_services(repo)
        assert set(services) == {"caddy", "adguard"}


class TestValidate:
    def test_clean_repo_has_no_errors(self, repo):
        issues = validate(repo)
        assert [i for i in issues if i["level"] == "error"] == []

    def test_missing_include_target(self, repo):
        write(repo / "docker-compose.yml", """\
            include:
              - nope/docker-compose.yml
            """)
        issues = validate(repo)
        assert any("include target missing" in i["message"] for i in issues)

    def test_duplicate_container_name(self, repo):
        write(repo / "portainer" / "docker-compose.yml", """\
            services:
              portainer:
                image: portainer/portainer-ce
                container_name: caddy
            """)
        issues = validate(repo)
        assert any("container_name 'caddy'" in i["message"] for i in issues)

    def test_host_port_conflict_is_warning(self, repo):
        write(repo / "other" / "docker-compose.yml", """\
            services:
              clash:
                image: nginx
                ports:
                  - "443:8443"
            """)
        issues = validate(repo)
        conflicts = [i for i in issues if "host port 443" in i["message"]]
        assert conflicts and conflicts[0]["level"] == "warn"

    def test_service_without_image_or_build(self, repo):
        write(repo / "broken" / "docker-compose.yml", """\
            services:
              nothing:
                restart: always
            """)
        issues = validate(repo)
        assert any("needs 'image' or 'build'" in i["message"] for i in issues)

    def test_empty_repo_reports_error(self, tmp_path):
        issues = validate(tmp_path)
        assert issues[0]["level"] == "error"
        assert "no stacks found" in issues[0]["message"]
