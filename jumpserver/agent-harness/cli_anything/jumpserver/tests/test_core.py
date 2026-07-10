"""
Unit tests for cli_anything.jumpserver core modules.

Uses synthetic data with no external dependencies.
Mock HTTP responses for client tests.
"""
import json
import io
import tempfile
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add agent-harness to path for local testing
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from cli_anything.jumpserver.core.session import Session, JumpServerClient, SESSION_FILE
from cli_anything.jumpserver.core.state import CLIState, get_state, reset_state, STATE_FILE
from cli_anything.jumpserver.core.output import format_output
from cli_anything.jumpserver.utils import (
    require_auth,
    handle_api_error,
    parse_ids,
    validate_output_format,
    mask_sensitive_data,
    CLIError,
)


# ─── Fixtures ────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clean_session_state():
    """Ensure session and state files don't persist between tests."""
    for f in (SESSION_FILE, STATE_FILE):
        if f.exists():
            f.unlink()
    reset_state()
    yield
    for f in (SESSION_FILE, STATE_FILE):
        if f.exists():
            f.unlink()
    reset_state()


@pytest.fixture
def empty_session():
    return Session()


@pytest.fixture
def auth_session():
    return Session(
        base_url="https://jumpserver.example.com",
        username="admin",
        token="abc123test",
        token_expiry=time.time() + 3600,
        org_id="00000000-0000-0000-0000-000000000002",
        org_name="Default",
    )


@pytest.fixture
def expired_session():
    return Session(
        base_url="https://jumpserver.example.com",
        username="admin",
        token="expired123",
        token_expiry=time.time() - 3600,
    )


# ─── Session Tests ───────────────────────────────────────────────


class TestSessionInit:
    """Session default initialization."""

    def test_defaults(self, empty_session):
        assert empty_session.base_url == ""
        assert empty_session.username == ""
        assert empty_session.token == ""
        assert empty_session.token_expiry == 0.0
        assert empty_session.verify_ssl is True
        assert empty_session.timeout == 60

    def test_custom_values(self, auth_session):
        assert auth_session.base_url == "https://jumpserver.example.com"
        assert auth_session.username == "admin"
        assert auth_session.token == "abc123test"
        assert auth_session.org_id == "00000000-0000-0000-0000-000000000002"


class TestSessionSaveLoad:
    """Session save/load round-trip."""

    def test_save_creates_file(self, auth_session):
        auth_session.save()
        assert SESSION_FILE.exists()

    def test_load_returns_session(self, auth_session):
        auth_session.save()
        loaded = Session.load()
        assert loaded.base_url == auth_session.base_url
        assert loaded.username == "admin"
        assert loaded.token == "abc123test"
        assert loaded.org_id == auth_session.org_id
        assert loaded.token_expiry == auth_session.token_expiry

    def test_load_nonexistent_returns_empty(self):
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()
        loaded = Session.load()
        assert loaded.token == ""
        assert loaded.base_url == ""

    def test_load_corrupted_file_returns_empty(self):
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        SESSION_FILE.write_text("{not valid json")
        loaded = Session.load()
        assert loaded.token == ""

    def test_clear_removes_file(self, auth_session):
        auth_session.save()
        assert SESSION_FILE.exists()
        auth_session.clear()
        assert not SESSION_FILE.exists()

    def test_clear_nonexistent_file(self, empty_session):
        empty_session.clear()  # should not raise


class TestSessionAuth:
    """Authentication state checks."""

    def test_no_token_not_authenticated(self, empty_session):
        assert not empty_session.is_authenticated()

    def test_valid_token_is_authenticated(self, auth_session):
        assert auth_session.is_authenticated()

    def test_expired_token_not_authenticated(self, expired_session):
        assert not expired_session.is_authenticated()

    def test_no_token_expiry(self):
        s = Session(token="test")
        # token_expiry defaults to 0.0, which means "no expiry set"
        # we consider a token without expiry as valid
        assert s.is_authenticated()


# ─── JumpServerClient Tests ──────────────────────────────────────


class TestClientURLConstruction:
    """URL construction from base URL + API path."""

    def test_basic_url(self, auth_session):
        client = auth_session.get_client()
        url = client._url("users/users/")
        assert url == "https://jumpserver.example.com/api/v1/users/users/"

    def test_strip_trailing_slash(self):
        s = Session(base_url="https://js.example.com/", token="x")
        client = s.get_client()
        url = client._url("assets/hosts/")
        assert url == "https://js.example.com/api/v1/assets/hosts/"

    def test_leading_slash_stripped(self, auth_session):
        client = auth_session.get_client()
        url = client._url("/users/profile/")
        assert url == "https://jumpserver.example.com/api/v1/users/profile/"


class TestClientHeaders:
    """HTTP header construction."""

    def test_basic_headers(self, auth_session):
        client = auth_session.get_client()
        headers = client.headers
        assert headers["Accept"] == "application/json"
        assert headers["Content-Type"] == "application/json"

    def test_auth_header(self, auth_session):
        client = auth_session.get_client()
        assert client.headers["Authorization"] == "Token abc123test"

    def test_org_header(self, auth_session):
        client = auth_session.get_client()
        assert client.headers["X-JMS-ORG"] == "00000000-0000-0000-0000-000000000002"

    def test_no_auth_header_without_token(self, empty_session):
        client = empty_session.get_client()
        assert "Authorization" not in client.headers

    def test_no_org_header_without_org(self):
        s = Session(base_url="https://js.example.com", token="x")
        client = s.get_client()
        assert "X-JMS-ORG" not in client.headers


class TestClientLogin:
    """Login flow with mocked responses."""

    @patch("requests.Session.request")
    def test_login_stores_token(self, mock_request, empty_session):
        mock_response = MagicMock()
        mock_response.json.return_value = {"token": "new-token-456"}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        client = empty_session.get_client()
        result = client.login("admin", "password123")

        assert result["token"] == "new-token-456"
        assert empty_session.token == "new-token-456"
        assert empty_session.username == "admin"
        assert empty_session.is_authenticated()

    @patch("requests.Session.request")
    def test_login_raises_on_failure(self, mock_request, empty_session):
        import requests
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
        mock_request.return_value = mock_response

        client = empty_session.get_client()
        with pytest.raises(requests.HTTPError):
            client.login("admin", "wrong-password")


class TestClientPagination:
    """Pagination helper."""

    @patch("requests.Session.request")
    def test_paginate_single_page(self, mock_request, auth_session):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [{"id": 1}, {"id": 2}]}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        client = auth_session.get_client()
        results = list(client.paginate("assets/hosts/"))

        assert len(results) == 2
        assert results[0]["id"] == 1

    @patch("requests.Session.request")
    def test_paginate_multiple_pages(self, mock_request, auth_session):
        page1 = MagicMock()
        page1.json.return_value = {"results": [{"id": i} for i in range(100)]}
        page1.raise_for_status.return_value = None

        page2 = MagicMock()
        page2.json.return_value = {"results": [{"id": i} for i in range(100, 150)]}
        page2.raise_for_status.return_value = None

        mock_request.side_effect = [page1, page2]

        client = auth_session.get_client()
        results = list(client.paginate("assets/hosts/", limit=100))

        assert len(results) == 150
        assert results[0]["id"] == 0
        assert results[-1]["id"] == 149

    @patch("requests.Session.request")
    def test_paginate_empty(self, mock_request, auth_session):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        client = auth_session.get_client()
        results = list(client.paginate("assets/hosts/"))
        assert len(results) == 0


# ─── CLIState Tests ──────────────────────────────────────────────


class TestCLIState:
    """CLI operational state tests."""

    def test_defaults(self):
        state = CLIState()
        assert state.current_org_id == ""
        assert state.selected_asset_ids == []
        assert state.pagination == {"limit": 20, "offset": 0}
        assert state.dry_run is False

    def test_save_load(self):
        state = CLIState(
            current_org_id="org-123",
            selected_asset_ids=["a1", "a2"],
            last_filters={"search": "web"},
        )
        state.save()
        assert STATE_FILE.exists()

        loaded = CLIState.load()
        assert loaded.current_org_id == "org-123"
        assert loaded.selected_asset_ids == ["a1", "a2"]
        assert loaded.last_filters == {"search": "web"}

    def test_clear_selection(self):
        state = CLIState(selected_asset_ids=["a1", "a2"], selected_node_ids=["n1"])
        state.clear_selection()
        assert state.selected_asset_ids == []
        assert state.selected_node_ids == []

    def test_set_filters(self):
        state = CLIState()
        state.set_filters(search="test", status="active")
        assert state.last_filters == {"search": "test", "status": "active"}

    def test_as_dict(self):
        state = CLIState(dry_run=True)
        d = state.as_dict()
        assert isinstance(d, dict)
        assert d["dry_run"] is True


class TestGlobalState:
    """get_state/reset_state functions."""

    def test_get_state_returns_instance(self, clean_session_state):
        state = get_state()
        assert isinstance(state, CLIState)

    def test_get_state_cached(self, clean_session_state):
        s1 = get_state()
        s2 = get_state()
        assert s1 is s2  # same instance

    def test_reset_state(self, clean_session_state):
        state = get_state()
        state.selected_asset_ids = ["test"]
        reset_state()
        new_state = get_state()
        assert new_state.selected_asset_ids == []
        assert new_state is not state


# ─── Output Formatting Tests ─────────────────────────────────────


class TestOutputFormatting:
    """format_output function tests."""

    def test_json_output(self):
        data = {"key": "value", "list": [1, 2, 3]}
        buf = io.StringIO()
        format_output(data, fmt="json", stream=buf)
        output = buf.getvalue()
        parsed = json.loads(output)
        assert parsed == data

    def test_json_output_is_parseable(self):
        data = [{"id": 1, "name": "test"}, {"id": 2, "name": "test2"}]
        buf = io.StringIO()
        format_output(data, fmt="json", stream=buf)
        output = buf.getvalue()
        parsed = json.loads(output)
        assert len(parsed) == 2

    def test_table_output_for_list(self):
        data = [{"name": "Alice", "role": "Admin"}, {"name": "Bob", "role": "User"}]
        buf = io.StringIO()
        format_output(data, fmt="table", columns=["name", "role"], stream=buf)
        output = buf.getvalue()
        assert "Alice" in output
        assert "Bob" in output
        assert "Admin" in output
        assert "2 result" in output

    def test_table_output_for_dict(self):
        data = {"name": "test-host", "address": "192.168.1.1"}
        buf = io.StringIO()
        format_output(data, fmt="table", stream=buf)
        output = buf.getvalue()
        assert "name" in output
        assert "test-host" in output

    def test_table_output_empty_list(self):
        buf = io.StringIO()
        format_output([], fmt="table", stream=buf)
        output = buf.getvalue()
        assert "no results" in output

    def test_yaml_output(self):
        data = {"key": "value", "list": [1, 2]}
        buf = io.StringIO()
        format_output(data, fmt="yaml", stream=buf)
        output = buf.getvalue()
        # Basic check that it contains expected keys
        assert "key" in output
        assert "value" in output


class TestPackagingMetadata:
    """Package metadata regressions."""

    def test_readme_paths_exist(self):
        harness_root = Path(__file__).resolve().parents[3]
        readme_path = harness_root / "cli_anything" / "jumpserver" / "README.md"
        assert readme_path.exists()
        assert 'readme = "cli_anything/jumpserver/README.md"' in (
            harness_root / "pyproject.toml"
        ).read_text()
        assert 'open("cli_anything/jumpserver/README.md", "r")' in (
            harness_root / "setup.py"
        ).read_text()


# ─── Utility Tests ───────────────────────────────────────────────


class TestRequireAuth:
    """require_auth function."""

    def test_raises_when_not_authenticated(self, empty_session):
        with pytest.raises(CLIError, match="Not authenticated"):
            require_auth(empty_session)

    def test_returns_client_when_authenticated(self, auth_session):
        client = require_auth(auth_session)
        assert isinstance(client, JumpServerClient)


class TestHandleAPIError:
    """handle_api_error function."""

    @patch("requests.Response")
    def test_400_raises_cli_error(self, mock_resp, auth_session):
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"detail": "Bad request"}
        with pytest.raises(CLIError, match="Bad request"):
            handle_api_error(mock_resp, "test action")

    @patch("requests.Response")
    def test_403_raises_cli_error(self, mock_resp, auth_session):
        mock_resp.status_code = 403
        mock_resp.json.return_value = {"detail": "Forbidden"}
        with pytest.raises(CLIError, match="Forbidden"):
            handle_api_error(mock_resp, "update")

    @patch("requests.Response")
    def test_404_raises_cli_error(self, mock_resp, auth_session):
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"detail": "Not found"}
        with pytest.raises(CLIError, match="Not found"):
            handle_api_error(mock_resp, "get")

    @patch("requests.Response")
    def test_500_with_text_body(self, mock_resp, auth_session):
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_resp.json.side_effect = ValueError("not json")
        with pytest.raises(CLIError, match="Internal Server Error"):
            handle_api_error(mock_resp, "request")

    @patch("requests.Response")
    def test_200_does_not_raise(self, mock_resp, auth_session):
        mock_resp.status_code = 200
        # should not raise
        handle_api_error(mock_resp, "get")


class TestParseIDs:
    """parse_ids helper."""

    def test_parses_comma_separated(self):
        result = parse_ids("a,b,c")
        assert result == ["a", "b", "c"]

    def test_parses_spaces(self):
        result = parse_ids("  a , b , c  ")
        assert result == ["a", "b", "c"]

    def test_single_id(self):
        result = parse_ids("only-one")
        assert result == ["only-one"]

    def test_none_returns_none(self):
        assert parse_ids(None) is None

    def test_empty_string_returns_none(self):
        assert parse_ids("") is None
        assert parse_ids("   ") is None

    def test_handles_uuid(self):
        ids = "0000-0000-0000,1111-1111-1111"
        result = parse_ids(ids)
        assert len(result) == 2


class TestSensitiveDataMasking:
    """Sensitive dry-run payload masking."""

    def test_masks_nested_sensitive_values(self):
        data = {
            "username": "root",
            "secret": "super-secret",
            "nested": {
                "password": "password123",
                "tokens": [{"token": "abc123"}],
            },
        }

        masked = mask_sensitive_data(data)

        assert masked["username"] == "root"
        assert masked["secret"] == "********"
        assert masked["nested"]["password"] == "********"
        assert masked["nested"]["tokens"][0]["token"] == "********"
        assert data["secret"] == "super-secret"


class TestValidateOutputFormat:
    """validate_output_format function."""

    def test_valid_formats(self):
        for fmt in ("json", "table", "yaml"):
            assert validate_output_format(fmt) == fmt

    def test_case_insensitive(self):
        assert validate_output_format("JSON") == "json"
        assert validate_output_format("Table") == "table"

    def test_invalid_format_raises(self):
        with pytest.raises(CLIError, match="Invalid output format"):
            validate_output_format("xml")

    def test_empty_string_raises(self):
        with pytest.raises(CLIError, match="Invalid output format"):
            validate_output_format("")


class TestCLIError:
    """CLIError exception."""

    def test_message_only(self):
        e = CLIError("Something went wrong")
        assert e.message == "Something went wrong"
        assert e.detail is None

    def test_message_with_detail(self):
        e = CLIError("Failed", "Connection refused")
        assert e.message == "Failed"
        assert e.detail == "Connection refused"


# ─── Long string truncation ──────────────────────────────────────


class TestTruncation:
    """Output truncation helper."""

    def test_truncate_value(self):
        from cli_anything.jumpserver.core.output import _truncate
        short = _truncate("hello", 10)
        assert short == "hello     "  # padded to width
        long_val = _truncate("this_is_a_very_long_string", 10)
        assert long_val.endswith("...")
        assert len(long_val) == 10
