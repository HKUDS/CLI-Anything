"""Unit tests — all HTTP calls mocked."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cli_anything.opencti.core import (
    cases,
    entities,
    indicators,
    observables,
    relationships,
    reports,
    system,
)
from cli_anything.opencti.utils import opencti_backend


# ─── Helpers ────────────────────────────────────────────────────────────────

def mock_response(status_code: int = 200, body: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body or {}
    resp.content = json.dumps(body or {}).encode()
    resp.text = json.dumps(body or {})
    resp.headers = {}
    resp.raise_for_status = MagicMock()
    return resp


def gql_response(data: dict) -> MagicMock:
    return mock_response(200, {"data": data})


BASE = "https://opencti.example.com"
KEY = "test-token-1234"

GQL = {
    "observables": "cli_anything.opencti.core.observables.graphql_request",
    "indicators": "cli_anything.opencti.core.indicators.graphql_request",
    "reports": "cli_anything.opencti.core.reports.graphql_request",
    "cases": "cli_anything.opencti.core.cases.graphql_request",
    "entities": "cli_anything.opencti.core.entities.graphql_request",
    "relationships": "cli_anything.opencti.core.relationships.graphql_request",
    "system": "cli_anything.opencti.core.system.graphql_request",
}


# ─── Backend ────────────────────────────────────────────────────────────────

class TestResolveConnection:
    def test_args_win(self):
        conn = opencti_backend.resolve_connection(BASE, KEY)
        assert conn == {"base_url": BASE, "api_key": KEY}

    @patch.dict("os.environ", {"OPENCTI_BASE_URL": BASE, "OPENCTI_API_KEY": KEY}, clear=False)
    def test_env_fallback(self):
        with patch.object(opencti_backend, "_load_config_file", return_value={}):
            conn = opencti_backend.resolve_connection(None, None)
        assert conn["base_url"] == BASE

    @patch.dict("os.environ", {}, clear=True)
    def test_file_fallback(self):
        cfg = {"base_url": "https://file.example.com", "api_key": "filekey"}
        with patch.object(opencti_backend, "_load_config_file", return_value=cfg):
            conn = opencti_backend.resolve_connection(None, None)
        assert conn["base_url"] == "https://file.example.com"

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_url_raises(self):
        with patch.object(opencti_backend, "_load_config_file", return_value={}):
            with pytest.raises(opencti_backend.OpenCTIError, match="base URL not configured"):
                opencti_backend.resolve_connection(None, None)

    def test_trailing_slash_stripped(self):
        conn = opencti_backend.resolve_connection(BASE + "/", KEY)
        assert conn["base_url"] == BASE


class TestGraphqlRequest:
    @patch("cli_anything.opencti.utils.opencti_backend.requests.post")
    def test_post_and_auth_header(self, mock_post):
        mock_post.return_value = gql_response({"about": {"version": "7.0"}})
        data = opencti_backend.graphql_request("query { about { version } }",
                                               base_url=BASE, api_key=KEY)
        assert data == {"about": {"version": "7.0"}}
        args, kwargs = mock_post.call_args
        assert args[0] == f"{BASE}/graphql"
        assert kwargs["headers"]["Authorization"] == f"Bearer {KEY}"

    @patch("cli_anything.opencti.utils.opencti_backend._sleep_backoff")
    @patch("cli_anything.opencti.utils.opencti_backend.requests.post")
    def test_retry_on_503_then_success(self, mock_post, _backoff):
        mock_post.side_effect = [mock_response(503), gql_response({"me": {"name": "a"}})]
        data = opencti_backend.graphql_request("query { me { name } }",
                                               base_url=BASE, api_key=KEY)
        assert data["me"]["name"] == "a"
        assert mock_post.call_count == 2

    @patch("cli_anything.opencti.utils.opencti_backend._sleep_backoff")
    @patch("cli_anything.opencti.utils.opencti_backend.requests.post")
    def test_graphql_errors_raise_valueerror(self, mock_post, _backoff):
        mock_post.return_value = mock_response(200, {
            "errors": [{"message": "Unauthorized"}], "data": None,
        })
        with pytest.raises(ValueError, match="Unauthorized"):
            opencti_backend.graphql_request("query { me { name } }",
                                            base_url=BASE, api_key="bad")

    @patch("cli_anything.opencti.utils.opencti_backend.requests.post")
    def test_http_401_raises_opencti_error(self, mock_post):
        mock_post.return_value = mock_response(401, {})
        with pytest.raises(opencti_backend.OpenCTIError, match="HTTP 401"):
            opencti_backend.graphql_request("query { me { name } }",
                                            base_url=BASE, api_key=KEY)

    @patch("cli_anything.opencti.utils.opencti_backend._sleep_backoff")
    @patch("cli_anything.opencti.utils.opencti_backend.requests.post")
    def test_final_retry_5xx_raises_opencti_error(self, mock_post, _backoff):
        mock_post.side_effect = [mock_response(503) for _ in range(4)]
        with pytest.raises(opencti_backend.OpenCTIError, match="HTTP 503"):
            opencti_backend.graphql_request("query { me { name } }",
                                            base_url=BASE, api_key=KEY)
        assert mock_post.call_count == 4


class TestPaginated:
    def test_single_page(self):
        page = {"edges": [{"node": {"id": "1"}}, {"node": {"id": "2"}}],
                "pageInfo": {"endCursor": "c1", "hasNextPage": False}}
        items = opencti_backend.paginated(lambda after: page)
        assert [i["id"] for i in items] == ["1", "2"]

    def test_multi_page(self):
        pages = [
            {"edges": [{"node": {"id": "1"}}],
             "pageInfo": {"endCursor": "c1", "hasNextPage": True}},
            {"edges": [{"node": {"id": "2"}}],
             "pageInfo": {"endCursor": "c2", "hasNextPage": False}},
        ]
        calls = []

        def fetch(after):
            calls.append(after)
            return pages[len(calls) - 1]

        items = opencti_backend.paginated(fetch)
        assert [i["id"] for i in items] == ["1", "2"]
        assert calls == [None, "c1"]

    def test_cursor_loop_guard(self):
        """A server repeating its endCursor must terminate, not spin forever."""
        page = {"edges": [{"node": {"id": "1"}}],
                "pageInfo": {"endCursor": "same", "hasNextPage": True}}
        calls = []
        items = opencti_backend.paginated(
            lambda after: (calls.append(after), dict(page))[1])
        assert len(calls) <= 3  # terminates well below max_pages
        assert len(items) == len(calls)


# ─── System ─────────────────────────────────────────────────────────────────

class TestSystem:
    @patch("cli_anything.opencti.core.system.health_check", return_value=True)
    @patch(GQL["system"])
    def test_status(self, mock_gql, _health):
        mock_gql.side_effect = [
            {"about": {"version": "7.260824.0"}},
            {"me": {"user_email": "admin@opencti.io"}},
        ]
        result = system.status(base_url=BASE, api_key=KEY)
        assert result["reachable"] is True
        assert result["version"] == "7.260824.0"
        assert result["authenticated_as"] == "admin@opencti.io"


# ─── Observables ────────────────────────────────────────────────────────────

class TestObservables:
    @patch(GQL["observables"])
    def test_list(self, mock_gql):
        page = {"edges": [{"node": {"id": "obs-1", "observable_value": "1.2.3.4",
                                    "entity_type": "IPv4-Addr"}}],
                "pageInfo": {"endCursor": "c1", "hasNextPage": False}}
        mock_gql.return_value = {"stixCyberObservables": page}
        items = observables.list_observables(search="1.2.3", base_url=BASE, api_key=KEY)
        assert items[0]["observable_value"] == "1.2.3.4"
        q, variables = mock_gql.call_args[0]
        assert variables["search"] == "1.2.3"

    @patch(GQL["observables"])
    def test_get(self, mock_gql):
        mock_gql.return_value = {"stixCyberObservable": {"id": "obs-1"}}
        obs = observables.get_observable("obs-1", base_url=BASE, api_key=KEY)
        assert obs["id"] == "obs-1"


# ─── Indicators ─────────────────────────────────────────────────────────────

class TestIndicators:
    @patch(GQL["indicators"])
    def test_search_by_pattern_filters(self, mock_gql):
        mock_gql.return_value = {"indicators": {"edges": [], "pageInfo": {}}}
        indicators.search_by_pattern("[ipv4-addr:value", first=5,
                                     base_url=BASE, api_key=KEY)
        _, variables = mock_gql.call_args[0]
        filt = variables["filters"]
        assert filt["filters"][0]["key"] == "pattern"
        assert filt["filters"][0]["operator"] == "starts_with"

    @patch(GQL["indicators"])
    def test_list(self, mock_gql):
        page = {"edges": [{"node": {"id": "ind-1",
                                    "pattern": "[domain-name:value = 'x.com']"}}],
                "pageInfo": {"endCursor": None, "hasNextPage": False}}
        mock_gql.return_value = {"indicators": page}
        items = indicators.list_indicators(base_url=BASE, api_key=KEY)
        assert items[0]["id"] == "ind-1"


# ─── Reports / Cases ────────────────────────────────────────────────────────

class TestReportsAndCases:
    @patch(GQL["reports"])
    def test_report_get(self, mock_gql):
        mock_gql.return_value = {"report": {"id": "r-1", "name": "R"}}
        rep = reports.get_report("r-1", base_url=BASE, api_key=KEY)
        assert rep["name"] == "R"

    @patch(GQL["cases"])
    def test_case_dispatch_rfi(self, mock_gql):
        mock_gql.return_value = {"caseRfis": {"edges": [{"node": {"id": "rfi-1"}}],
                                              "pageInfo": {}}}
        items = cases.list_cases("rfi", base_url=BASE, api_key=KEY)
        assert items[0]["id"] == "rfi-1"
        q, _ = mock_gql.call_args[0]
        assert "caseRfis" in q

    def test_invalid_case_type(self):
        with pytest.raises(KeyError):
            cases.list_cases("bogus", base_url=BASE, api_key=KEY)


# ─── Entities ───────────────────────────────────────────────────────────────

class TestEntities:
    @patch(GQL["entities"])
    def test_threat_actor_get_includes_stix(self, mock_gql):
        mock_gql.return_value = {"threatActor": {"id": "ta-1", "toStix": "{}"}}
        ta = entities.get_entity("threat-actor", "ta-1", base_url=BASE, api_key=KEY)
        assert ta["id"] == "ta-1"
        q, variables = mock_gql.call_args[0]
        assert "threatActor(id: $id)" in q
        assert variables == {"id": "ta-1"}

    @patch(GQL["entities"])
    def test_global_search_types(self, mock_gql):
        mock_gql.return_value = {"stixCoreObjects": {"edges": [], "pageInfo": {}}}
        entities.global_search("apt", types=["Threat-Actor"], base_url=BASE, api_key=KEY)
        _, variables = mock_gql.call_args[0]
        assert variables["types"] == ["Threat-Actor"]

    def test_unknown_entity_type(self):
        with pytest.raises(KeyError):
            entities.list_entities("unicorn", base_url=BASE, api_key=KEY)


# ─── Writes ─────────────────────────────────────────────────────────────────

class TestObservableWrites:
    @patch(GQL["observables"])
    def test_add_ipv4(self, mock_gql):
        mock_gql.return_value = {"stixCyberObservableAdd": {"id": "new-1"}}
        result = observables.add_observable("ipv4-addr", "10.0.0.1",
                                            base_url=BASE, api_key=KEY)
        assert result["id"] == "new-1"
        q, variables = mock_gql.call_args[0]
        assert 'type: "IPv4-Addr"' in q
        assert "IPv4AddrAddInput" in q
        assert variables["inp"] == {"value": "10.0.0.1"}

    @patch(GQL["observables"])
    def test_add_file_sha256(self, mock_gql):
        mock_gql.return_value = {"stixCyberObservableAdd": {"id": "f-1"}}
        observables.add_observable("file-sha256", "abc123", base_url=BASE,
                                   api_key=KEY)
        _, variables = mock_gql.call_args[0]
        assert variables["inp"] == {
            "hashes": [{"algorithm": "SHA-256", "hash": "abc123"}]
        }

    def test_unsupported_type(self):
        with pytest.raises(ValueError, match="unsupported observable type"):
            observables.add_observable("bitcoin-wallet", "xyz")

    @patch(GQL["observables"])
    def test_labels_and_indicator_flag(self, mock_gql):
        mock_gql.return_value = {"stixCyberObservableAdd": {"id": "x"}}
        observables.add_observable("domain-name", "evil.example", labels=["c2"],
                                   create_indicator=True, base_url=BASE,
                                   api_key=KEY)
        _, variables = mock_gql.call_args[0]
        assert variables["labels"] == ["c2"]
        assert variables["ci"] is True


class TestIndicatorWrites:
    @patch(GQL["indicators"])
    def test_add(self, mock_gql):
        mock_gql.return_value = {"indicatorAdd": {"id": "ind-new"}}
        indicators.add_indicator("C2 domain", "[domain-name:value = 'x.example']",
                                 score=90, base_url=BASE, api_key=KEY)
        _, variables = mock_gql.call_args[0]
        inp = variables["input"]
        assert inp["pattern_type"] == "stix"
        assert inp["x_opencti_score"] == 90

    @patch(GQL["indicators"])
    def test_delete(self, mock_gql):
        mock_gql.return_value = {"indicatorDelete": "ind-9"}
        assert indicators.delete_indicator("ind-9", base_url=BASE,
                                           api_key=KEY) == "ind-9"


class TestEntityAndCaseWrites:
    @patch(GQL["entities"])
    def test_add_threat_actor(self, mock_gql):
        mock_gql.return_value = {"threatActorGroupAdd": {"id": "ta-new"}}
        entities.add_entity("threat-actor", "APT-X", aliases=["APT-X Prime"],
                            base_url=BASE, api_key=KEY)
        q, variables = mock_gql.call_args[0]
        assert "threatActorGroupAdd" in q
        assert variables["input"]["aliases"] == ["APT-X Prime"]

    @patch(GQL["entities"])
    def test_delete_object_guard_shape(self, mock_gql):
        mock_gql.return_value = {"stixCoreObjectEdit": {"delete": True}}
        assert entities.delete_object("obj-1", base_url=BASE, api_key=KEY) is True
        _, variables = mock_gql.call_args[0]
        assert variables == {"id": "obj-1"}

    @patch(GQL["cases"])
    def test_add_rft(self, mock_gql):
        mock_gql.return_value = {"caseRftAdd": {"id": "rft-new"}}
        cases.add_case("rft", "Takedown example.com", severity="high",
                       base_url=BASE, api_key=KEY)
        q, variables = mock_gql.call_args[0]
        assert "caseRftAdd" in q
        assert variables["input"]["severity"] == "high"

    @patch(GQL["reports"])
    def test_add_report(self, mock_gql):
        mock_gql.return_value = {"reportAdd": {"id": "rep-new"}}
        reports.add_report("Q3 APT report", published="2026-08-24T00:00:00Z",
                           base_url=BASE, api_key=KEY)
        _, variables = mock_gql.call_args[0]
        assert variables["input"]["published"] == "2026-08-24T00:00:00Z"

    @patch(GQL["relationships"])
    def test_add_relationship(self, mock_gql):
        mock_gql.return_value = {"stixCoreRelationshipAdd": {"id": "rel-new"}}
        relationships.add_relationship("src-1", "dst-1", "related-to",
                                       base_url=BASE, api_key=KEY)
        _, variables = mock_gql.call_args[0]
        inp = variables["input"]
        assert inp["fromId"] == "src-1"
        assert inp["relationship_type"] == "related-to"


# ─── CLI wiring (review fixes) ──────────────────────────────────────────────

class TestCliOffline:
    """config subcommands must work on an unconfigured machine (PR review)."""

    def test_config_set_without_connection(self, tmp_path):
        from cli_anything.opencti import opencti_cli

        cfg = tmp_path / "config.json"
        runner = CliRunner()
        with patch.dict("os.environ", {}, clear=True), \
             patch.object(opencti_backend, "CONFIG_DIR", tmp_path), \
             patch.object(opencti_backend, "CONFIG_FILE", cfg):
            result = runner.invoke(opencti_cli.cli,
                                   ["config", "set", "--url", BASE])
        assert result.exit_code == 0, result.output
        assert json.loads(cfg.read_text())["base_url"] == BASE

    def test_config_test_without_connection_reports_error(self):
        from cli_anything.opencti import opencti_cli

        runner = CliRunner()
        with patch.dict("os.environ", {}, clear=True), \
             patch.object(opencti_backend, "_load_config_file",
                          return_value={}):
            result = runner.invoke(
                opencti_cli.cli, ["config", "test", "--url", BASE])
        # reaches the command (fails on connect, not on missing config)
        assert "Usage:" not in result.output

    @patch(GQL["observables"])
    def test_observable_search_maps_type_tokens(self, mock_gql):
        from cli_anything.opencti import opencti_cli

        mock_gql.return_value = {"stixCyberObservables": {
            "edges": [], "pageInfo": {"endCursor": None, "hasNextPage": False}}}
        runner = CliRunner()
        result = runner.invoke(
            opencti_cli.cli,
            ["--url", BASE, "--token", KEY,
             "observable", "search", "evil", "--type", "ipv4-addr,domain-name"])
        assert result.exit_code == 0, result.output
        _, variables = mock_gql.call_args[0]
        assert variables["types"] == ["IPv4-Addr", "Domain-Name"]
