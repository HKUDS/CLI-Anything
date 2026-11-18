"""Unit tests for the Caddyfile parser."""

import textwrap

from cli_anything.controlplane.core import caddyfile as caddy_mod

SAMPLE = """\
{
    admin off
    log {
        output file /var/log/caddy/access.log
    }
}

:80 {
    redir https://{host}{uri} permanent
}

app.example.com {
    header {
        Strict-Transport-Security "max-age=31536000"
    }
    reverse_proxy app:3000
}

www.example.com, example.com {
    redir https://example.com{uri} permanent
}

*.internal.example.com {
    reverse_proxy {
        to backend-a:8080
        to backend-b:8080
    }
}

files.example.com {
    root * /srv
    file_server
}

(snippet_headers) {
    header X-Test "1"
}

legacy.example.com {
    reverse_proxy https://legacy-upstream:8443 {
        transport http {
            versions 1.1
        }
    }
}
"""


def parse():
    return caddy_mod.parse(SAMPLE)


class TestStructure:
    def test_global_options_detected(self):
        assert parse().has_global_options is True

    def test_snippets_collected(self):
        assert parse().snippets == ["snippet_headers"]

    def test_site_count_excludes_global_and_snippet(self):
        addresses = [a for site in parse().sites for a in site.addresses]
        assert ":80" in addresses
        assert "app.example.com" in addresses
        # the snippet's name must not become a site address
        assert "snippet_headers" not in addresses

    def test_multi_address_site(self):
        cf = parse()
        site = next(s for s in cf.sites if "www.example.com" in s.addresses)
        assert site.addresses == ["www.example.com", "example.com"]

    def test_line_numbers_monotonic(self):
        lines = [site.line for site in parse().sites]
        assert lines == sorted(lines)


class TestHandlers:
    def test_reverse_proxy_kind_and_upstream(self):
        cf = parse()
        site = next(s for s in cf.sites if s.primary == "app.example.com")
        assert site.kind() == "reverse_proxy"
        assert site.upstreams() == ["app:3000"]

    def test_upstreams_from_to_block(self):
        cf = parse()
        site = next(s for s in cf.sites if s.primary == "*.internal.example.com")
        assert site.upstreams() == ["backend-a:8080", "backend-b:8080"]

    def test_scheme_prefix_stripped(self):
        cf = parse()
        site = next(s for s in cf.sites if s.primary == "legacy.example.com")
        assert site.upstreams() == ["legacy-upstream:8443"]

    def test_nested_options_do_not_break_parsing(self):
        cf = parse()
        site = next(s for s in cf.sites if s.primary == "legacy.example.com")
        proxy = next(h for h in site.handlers if h.type == "reverse_proxy")
        assert any(child.type == "transport" for child in proxy.children)

    def test_redirect_kind(self):
        cf = parse()
        site = next(s for s in cf.sites if s.primary == "www.example.com")
        assert site.kind() == "redirect"
        assert site.upstreams() == []

    def test_static_kind(self):
        cf = parse()
        site = next(s for s in cf.sites if s.primary == "files.example.com")
        assert site.kind() == "static"

    def test_header_block_kept_verbatim(self):
        cf = parse()
        site = next(s for s in cf.sites if s.primary == "app.example.com")
        header = next(h for h in site.handlers if h.type == "header")
        assert header.children
        assert header.children[0].type == "Strict-Transport-Security"
        assert header.children[0].args[0] == "max-age=31536000"


class TestFind:
    def test_exact_match(self):
        assert [s.primary for s in parse().find("app.example.com")] == ["app.example.com"]

    def test_wildcard_matches_subdomain(self):
        matches = parse().find("db.internal.example.com")
        assert matches and matches[0].primary == "*.internal.example.com"

    def test_wildcard_does_not_match_other_domain(self):
        assert parse().find("db.example.com") == []

    def test_unknown_domain_returns_empty(self):
        assert parse().find("nope.example.net") == []

    def test_case_insensitive_and_trailing_dot(self):
        assert parse().find("APP.Example.COM.") != []


class TestComments:
    def test_comments_are_ignored(self):
        cf = caddy_mod.parse(textwrap.dedent("""\
            # top comment
            a.example.com {   # inline comment
                reverse_proxy a:80
            }
            """))
        assert len(cf.sites) == 1
        assert cf.sites[0].upstreams() == ["a:80"]

    def test_hash_inside_quotes_survives(self):
        cf = caddy_mod.parse(textwrap.dedent("""\
            a.example.com {
                header X-Color "#fff"
                reverse_proxy a:80
            }
            """))
        header = next(h for h in cf.sites[0].handlers if h.type == "header")
        assert header.args[1] == "#fff"


class TestValidate:
    def test_valid_file_has_no_errors(self):
        issues = caddy_mod.validate(parse())
        assert [i for i in issues if i["level"] == "error"] == []

    def test_empty_file_reports_no_sites(self):
        issues = caddy_mod.validate(caddy_mod.parse(""))
        assert issues and issues[0]["level"] == "error"

    def test_duplicate_address_warns(self):
        cf = caddy_mod.parse(textwrap.dedent("""\
            a.example.com {
                reverse_proxy a:80
            }
            a.example.com {
                reverse_proxy b:80
            }
            """))
        issues = caddy_mod.validate(cf)
        assert any("already declared" in i["message"] for i in issues)

    def test_reverse_proxy_without_upstream_errors(self):
        cf = caddy_mod.parse(textwrap.dedent("""\
            a.example.com {
                reverse_proxy
            }
            """))
        issues = caddy_mod.validate(cf)
        assert any("without an upstream" in i["message"] for i in issues)

    def test_upstream_without_port_warns(self):
        cf = caddy_mod.parse(textwrap.dedent("""\
            a.example.com {
                reverse_proxy backend
            }
            """))
        issues = caddy_mod.validate(cf)
        assert any("no port" in i["message"] for i in issues)
