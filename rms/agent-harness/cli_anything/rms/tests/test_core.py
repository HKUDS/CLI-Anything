"""Unit tests for cli-anything-rms core modules."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest


# ── Backend tests ──────────────────────────────────────────────────────


class TestBackend:
    """Tests for rms_backend module."""

    def test_get_api_token_from_env(self):
        from cli_anything.rms.utils.rms_backend import get_api_token

        with patch.dict(os.environ, {"RMS_API_TOKEN": "test-token-123"}):
            assert get_api_token() == "test-token-123"

    def test_get_api_token_cli_override(self):
        from cli_anything.rms.utils.rms_backend import get_api_token

        with patch.dict(os.environ, {"RMS_API_TOKEN": "env-token"}):
            assert get_api_token("cli-token") == "cli-token"

    def test_get_api_token_from_config(self, tmp_path):
        from cli_anything.rms.utils import rms_backend

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"api_token": "config-token"}))

        with patch.object(rms_backend, "CONFIG_FILE", config_file):
            with patch.dict(os.environ, {}, clear=True):
                # Remove RMS_API_TOKEN if present
                os.environ.pop("RMS_API_TOKEN", None)
                assert rms_backend.get_api_token() == "config-token"

    def test_require_api_token_missing(self):
        from cli_anything.rms.utils.rms_backend import _require_api_token

        with pytest.raises(RuntimeError, match="RMS API token not found"):
            _require_api_token(None)

    def test_require_api_token_present(self):
        from cli_anything.rms.utils.rms_backend import _require_api_token

        assert _require_api_token("my-token") == "my-token"

    def test_make_auth_headers(self):
        from cli_anything.rms.utils.rms_backend import _make_auth_headers

        headers = _make_auth_headers("test-token")
        assert headers == {"Authorization": "Bearer test-token"}

    @patch("cli_anything.rms.utils.rms_backend.requests")
    def test_api_get_success(self, mock_requests):
        from cli_anything.rms.utils.rms_backend import api_get

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "success": True,
            "data": [{"id": 1, "name": "Router-1"}],
            "meta": {"total": 1},
        }
        mock_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_resp

        result = api_get("/devices", token="test-token")
        assert result["success"] is True
        assert len(result["data"]) == 1

    @patch("cli_anything.rms.utils.rms_backend.requests")
    def test_api_get_with_params(self, mock_requests):
        from cli_anything.rms.utils.rms_backend import api_get

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": True, "data": []}
        mock_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_resp

        api_get("/devices", params={"status": "online", "limit": 10}, token="test-token")
        mock_requests.get.assert_called_once()
        call_kwargs = mock_requests.get.call_args
        assert call_kwargs.kwargs["params"] == {"status": "online", "limit": 10}

    @patch("cli_anything.rms.utils.rms_backend.requests")
    def test_api_get_error(self, mock_requests):
        import requests as _requests
        from cli_anything.rms.utils.rms_backend import api_get

        # Preserve real exception classes so except clauses work
        mock_requests.RequestException = _requests.RequestException
        mock_requests.exceptions = _requests.exceptions

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = '{"success": false, "errors": [{"message": "Not found"}]}'
        mock_resp.json.return_value = {"success": False, "errors": [{"message": "Not found"}]}
        mock_resp.raise_for_status.side_effect = _requests.exceptions.HTTPError("404 Not Found")
        mock_requests.get.return_value = mock_resp

        with pytest.raises(RuntimeError, match="Not found"):
            api_get("/devices/999999", token="test-token")

    @patch("cli_anything.rms.utils.rms_backend.requests")
    def test_api_get_rate_limited(self, mock_requests):
        from cli_anything.rms.utils.rms_backend import api_get

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"Retry-After": "60"}
        mock_resp.text = "Rate limit exceeded"
        mock_resp.raise_for_status.side_effect = Exception("429 Too Many Requests")
        mock_requests.get.return_value = mock_resp

        with pytest.raises(RuntimeError, match="[Rr]ate limit"):
            api_get("/devices", token="test-token")

    @patch("cli_anything.rms.utils.rms_backend.requests")
    def test_api_post_success(self, mock_requests):
        from cli_anything.rms.utils.rms_backend import api_post

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "success": True,
            "data": {"id": 10, "name": "New Tag"},
        }
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        result = api_post("/tags", data={"name": "New Tag"}, token="test-token")
        assert result["success"] is True

    @patch("cli_anything.rms.utils.rms_backend.requests")
    def test_api_put_success(self, mock_requests):
        from cli_anything.rms.utils.rms_backend import api_put

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "success": True,
            "data": {"id": 10, "name": "Updated"},
        }
        mock_resp.raise_for_status = MagicMock()
        mock_requests.put.return_value = mock_resp

        result = api_put("/tags/10", data={"name": "Updated"}, token="test-token")
        assert result["success"] is True

    @patch("cli_anything.rms.utils.rms_backend.requests")
    def test_api_delete_success(self, mock_requests):
        from cli_anything.rms.utils.rms_backend import api_delete

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": True}
        mock_resp.raise_for_status = MagicMock()
        mock_requests.delete.return_value = mock_resp

        result = api_delete("/tags/10", token="test-token")
        assert result["success"] is True

    def test_config_save_load(self, tmp_path):
        from cli_anything.rms.utils import rms_backend

        config_file = tmp_path / "config.json"
        with patch.object(rms_backend, "CONFIG_FILE", config_file):
            with patch.object(rms_backend, "CONFIG_DIR", tmp_path):
                rms_backend.save_config({"api_token": "saved-token", "default_limit": 50})
                loaded = rms_backend.load_config()
                assert loaded["api_token"] == "saved-token"
                assert loaded["default_limit"] == 50


# ── Core module tests ──────────────────────────────────────────────────


class TestDevices:
    """Tests for devices core module."""

    @patch("cli_anything.rms.core.devices.api_get")
    def test_list_devices(self, mock_get):
        from cli_anything.rms.core.devices import list_devices

        mock_get.return_value = {
            "success": True,
            "data": [{"id": 1, "name": "Router-1"}],
            "meta": {"total": 1},
        }

        result = list_devices("token")
        mock_get.assert_called_once()
        assert result["data"][0]["name"] == "Router-1"

    @patch("cli_anything.rms.core.devices.api_get")
    def test_list_devices_with_filters(self, mock_get):
        from cli_anything.rms.core.devices import list_devices

        mock_get.return_value = {"success": True, "data": [], "meta": {"total": 0}}

        list_devices("token", status="online", tag=["office"], limit=10, offset=5)
        call_args = mock_get.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params", {})
        assert params.get("status") == "online"

    @patch("cli_anything.rms.core.devices.api_get")
    def test_get_device(self, mock_get):
        from cli_anything.rms.core.devices import get_device

        mock_get.return_value = {
            "success": True,
            "data": {"id": 42, "name": "Gateway-42", "status": "online"},
        }

        result = get_device("token", "42")
        assert result["data"]["id"] == 42


class TestCompanies:
    @patch("cli_anything.rms.core.companies.api_get")
    def test_list_companies(self, mock_get):
        from cli_anything.rms.core.companies import list_companies

        mock_get.return_value = {"success": True, "data": [{"id": 1}]}
        result = list_companies("token")
        assert result["success"] is True

    @patch("cli_anything.rms.core.companies.api_post")
    def test_create_company(self, mock_post):
        from cli_anything.rms.core.companies import create_company

        mock_post.return_value = {"success": True, "data": {"id": 2, "name": "Acme"}}
        result = create_company("token", {"name": "Acme"})
        assert result["data"]["name"] == "Acme"


class TestTags:
    @patch("cli_anything.rms.core.tags.api_get")
    def test_list_tags(self, mock_get):
        from cli_anything.rms.core.tags import list_tags

        mock_get.return_value = {"success": True, "data": [{"id": 1, "name": "office"}]}
        result = list_tags("token")
        assert len(result["data"]) == 1

    @patch("cli_anything.rms.core.tags.api_post")
    def test_create_tag(self, mock_post):
        from cli_anything.rms.core.tags import create_tag

        mock_post.return_value = {"success": True, "data": {"id": 3, "name": "new-tag"}}
        result = create_tag("token", {"name": "new-tag"})
        assert result["data"]["name"] == "new-tag"


class TestAlerts:
    @patch("cli_anything.rms.core.alerts.api_get")
    def test_list_alerts(self, mock_get):
        from cli_anything.rms.core.alerts import list_alerts

        mock_get.return_value = {"success": True, "data": []}
        result = list_alerts("token")
        assert result["success"] is True

    @patch("cli_anything.rms.core.alerts.api_get")
    def test_list_alerts_by_device(self, mock_get):
        from cli_anything.rms.core.alerts import list_alerts

        mock_get.return_value = {"success": True, "data": []}
        list_alerts("token", device_id="42")
        call_args = mock_get.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params", {})
        assert params.get("device_id") == "42"


class TestLocation:
    @patch("cli_anything.rms.core.location.api_get")
    def test_get_location(self, mock_get):
        from cli_anything.rms.core.location import get_location

        mock_get.return_value = {
            "success": True,
            "data": {"latitude": 54.6872, "longitude": 25.2797},
        }
        result = get_location("token", "42")
        assert "latitude" in result["data"]


class TestSession:
    def test_session_create(self, tmp_path):
        from cli_anything.rms.core.session import Session

        sf = str(tmp_path / "session.json")
        s = Session(session_file=sf)
        assert s.status()["history_count"] == 0

    def test_session_save_load(self, tmp_path):
        from cli_anything.rms.core.session import Session

        sf = str(tmp_path / "session.json")
        s = Session(session_file=sf)
        s.set_last_device("42")
        s.save_history("devices list", {"count": 5})

        s2 = Session(session_file=sf)
        assert s2.last_device_id == "42"
        assert len(s2.history) == 1

    def test_session_clear(self, tmp_path):
        from cli_anything.rms.core.session import Session

        sf = str(tmp_path / "session.json")
        s = Session(session_file=sf)
        s.set_last_device("42")
        s.save_history("test", {})
        s.clear()
        assert s.last_device_id is None
        assert len(s.history) == 0

    def test_session_history_limit(self, tmp_path):
        from cli_anything.rms.core.session import Session

        sf = str(tmp_path / "session.json")
        s = Session(session_file=sf)
        for i in range(60):
            s.save_history(f"cmd-{i}", {})
        assert len(s.history) == 50


# ── Phase 2: Tests for previously untested core modules ───────────────


class TestUsers:
    @patch("cli_anything.rms.core.users.api_get")
    def test_list_users(self, mock_get):
        from cli_anything.rms.core.users import list_users

        mock_get.return_value = {"success": True, "data": [{"id": 1, "email": "a@b.com"}]}
        result = list_users("token")
        mock_get.assert_called_once()
        assert result["data"][0]["email"] == "a@b.com"

    @patch("cli_anything.rms.core.users.api_get")
    def test_get_user(self, mock_get):
        from cli_anything.rms.core.users import get_user

        mock_get.return_value = {"success": True, "data": {"id": 5, "email": "u@b.com"}}
        result = get_user("token", "5")
        assert result["data"]["id"] == 5

    @patch("cli_anything.rms.core.users.api_post")
    def test_invite_user(self, mock_post):
        from cli_anything.rms.core.users import invite_user

        mock_post.return_value = {"success": True, "data": {"id": 6, "email": "new@b.com"}}
        result = invite_user("token", {"email": "new@b.com"})
        assert result["data"]["email"] == "new@b.com"

    @patch("cli_anything.rms.core.users.api_put")
    def test_update_user(self, mock_put):
        from cli_anything.rms.core.users import update_user

        mock_put.return_value = {"success": True, "data": {"id": 5, "name": "Updated"}}
        result = update_user("token", "5", {"name": "Updated"})
        assert result["data"]["name"] == "Updated"

    @patch("cli_anything.rms.core.users.api_delete")
    def test_delete_user(self, mock_delete):
        from cli_anything.rms.core.users import delete_user

        mock_delete.return_value = {"success": True}
        result = delete_user("token", "5")
        assert result["success"] is True


class TestConfigs:
    @patch("cli_anything.rms.core.configs.api_get")
    def test_list_configs(self, mock_get):
        from cli_anything.rms.core.configs import list_configs

        mock_get.return_value = {"success": True, "data": [{"id": 1}]}
        result = list_configs("token")
        mock_get.assert_called_once()
        assert result["success"] is True

    @patch("cli_anything.rms.core.configs.api_get")
    def test_list_configs_by_device(self, mock_get):
        from cli_anything.rms.core.configs import list_configs

        mock_get.return_value = {"success": True, "data": []}
        list_configs("token", device_id="42")
        call_args = mock_get.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params", {})
        assert params.get("device_id") == "42"

    @patch("cli_anything.rms.core.configs.api_get")
    def test_get_config(self, mock_get):
        from cli_anything.rms.core.configs import get_config

        mock_get.return_value = {"success": True, "data": {"id": 10, "name": "cfg1"}}
        result = get_config("token", "10")
        assert result["data"]["id"] == 10

    @patch("cli_anything.rms.core.configs.api_put")
    def test_update_config(self, mock_put):
        from cli_anything.rms.core.configs import update_config

        mock_put.return_value = {"success": True, "data": {"id": 10, "value": "new"}}
        result = update_config("token", "10", {"value": "new"})
        assert result["success"] is True


class TestRemoteAccess:
    @patch("cli_anything.rms.core.remote_access.api_get")
    def test_list_sessions(self, mock_get):
        from cli_anything.rms.core.remote_access import list_sessions

        mock_get.return_value = {"success": True, "data": [{"id": 1}]}
        result = list_sessions("token")
        mock_get.assert_called_once()
        assert result["success"] is True

    @patch("cli_anything.rms.core.remote_access.api_get")
    def test_list_sessions_by_device(self, mock_get):
        from cli_anything.rms.core.remote_access import list_sessions

        mock_get.return_value = {"success": True, "data": []}
        list_sessions("token", device_id="42")
        call_args = mock_get.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params", {})
        assert params.get("device_id") == "42"

    @patch("cli_anything.rms.core.remote_access.api_get")
    def test_get_session(self, mock_get):
        from cli_anything.rms.core.remote_access import get_session

        mock_get.return_value = {"success": True, "data": {"id": 3, "status": "active"}}
        result = get_session("token", "3")
        assert result["data"]["status"] == "active"

    @patch("cli_anything.rms.core.remote_access.api_post")
    def test_create_session(self, mock_post):
        from cli_anything.rms.core.remote_access import create_session

        mock_post.return_value = {"success": True, "data": {"id": 4, "device_id": "42"}}
        result = create_session("token", {"device_id": "42", "type": "ssh"})
        assert result["data"]["device_id"] == "42"

    @patch("cli_anything.rms.core.remote_access.api_delete")
    def test_delete_session(self, mock_delete):
        from cli_anything.rms.core.remote_access import delete_session

        mock_delete.return_value = {"success": True}
        result = delete_session("token", "3")
        assert result["success"] is True


class TestLogs:
    @patch("cli_anything.rms.core.logs.api_get")
    def test_list_logs(self, mock_get):
        from cli_anything.rms.core.logs import list_logs

        mock_get.return_value = {"success": True, "data": [{"id": 1}]}
        result = list_logs("token")
        mock_get.assert_called_once()
        assert result["success"] is True

    @patch("cli_anything.rms.core.logs.api_get")
    def test_list_logs_by_device(self, mock_get):
        from cli_anything.rms.core.logs import list_logs

        mock_get.return_value = {"success": True, "data": []}
        list_logs("token", device_id="42")
        call_args = mock_get.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params", {})
        assert params.get("device_id") == "42"

    @patch("cli_anything.rms.core.logs.api_get")
    def test_get_log(self, mock_get):
        from cli_anything.rms.core.logs import get_log

        mock_get.return_value = {"success": True, "data": {"id": 7, "message": "boot"}}
        result = get_log("token", "7")
        assert result["data"]["id"] == 7

    @patch("cli_anything.rms.core.logs.api_delete")
    def test_delete_log(self, mock_delete):
        from cli_anything.rms.core.logs import delete_log

        mock_delete.return_value = {"success": True}
        result = delete_log("token", "7")
        assert result["success"] is True


class TestCredits:
    @patch("cli_anything.rms.core.credits.api_get")
    def test_list_credits(self, mock_get):
        from cli_anything.rms.core.credits import list_credits

        mock_get.return_value = {"success": True, "data": [{"id": 1, "amount": 100}]}
        result = list_credits("token")
        mock_get.assert_called_once()
        assert result["data"][0]["amount"] == 100

    @patch("cli_anything.rms.core.credits.api_post")
    def test_transfer_credits(self, mock_post):
        from cli_anything.rms.core.credits import transfer_credits

        mock_post.return_value = {"success": True, "data": {"transferred": 50}}
        result = transfer_credits("token", {"amount": 50, "to_company": "2"})
        assert result["data"]["transferred"] == 50

    @patch("cli_anything.rms.core.credits.api_get")
    def test_list_transfer_codes(self, mock_get):
        from cli_anything.rms.core.credits import list_transfer_codes

        mock_get.return_value = {"success": True, "data": [{"code": "ABC123"}]}
        result = list_transfer_codes("token")
        assert result["data"][0]["code"] == "ABC123"


class TestFiles:
    @patch("cli_anything.rms.core.files.api_get")
    def test_list_files(self, mock_get):
        from cli_anything.rms.core.files import list_files

        mock_get.return_value = {"success": True, "data": [{"id": 1, "name": "fw.bin"}]}
        result = list_files("token")
        mock_get.assert_called_once()
        assert result["data"][0]["name"] == "fw.bin"

    @patch("cli_anything.rms.core.files.api_get")
    def test_get_file(self, mock_get):
        from cli_anything.rms.core.files import get_file

        mock_get.return_value = {"success": True, "data": {"id": 1, "name": "fw.bin", "size": 1024}}
        result = get_file("token", "1")
        assert result["data"]["size"] == 1024

    @patch("cli_anything.rms.core.files.api_delete")
    def test_delete_file(self, mock_delete):
        from cli_anything.rms.core.files import delete_file

        mock_delete.return_value = {"success": True}
        result = delete_file("token", "1")
        assert result["success"] is True


class TestReports:
    @patch("cli_anything.rms.core.reports.api_get")
    def test_list_reports(self, mock_get):
        from cli_anything.rms.core.reports import list_reports

        mock_get.return_value = {"success": True, "data": [{"id": 1}]}
        result = list_reports("token")
        mock_get.assert_called_once()
        assert result["success"] is True

    @patch("cli_anything.rms.core.reports.api_get")
    def test_get_report(self, mock_get):
        from cli_anything.rms.core.reports import get_report

        mock_get.return_value = {"success": True, "data": {"id": 1, "name": "Weekly"}}
        result = get_report("token", "1")
        assert result["data"]["name"] == "Weekly"

    @patch("cli_anything.rms.core.reports.api_post")
    def test_create_report(self, mock_post):
        from cli_anything.rms.core.reports import create_report

        mock_post.return_value = {"success": True, "data": {"id": 2, "name": "Daily"}}
        result = create_report("token", {"name": "Daily"})
        assert result["data"]["name"] == "Daily"

    @patch("cli_anything.rms.core.reports.api_delete")
    def test_delete_report(self, mock_delete):
        from cli_anything.rms.core.reports import delete_report

        mock_delete.return_value = {"success": True}
        result = delete_report("token", "1")
        assert result["success"] is True

    @patch("cli_anything.rms.core.reports.api_get")
    def test_list_templates(self, mock_get):
        from cli_anything.rms.core.reports import list_templates

        mock_get.return_value = {"success": True, "data": [{"id": 1, "name": "tmpl1"}]}
        result = list_templates("token")
        assert len(result["data"]) == 1

    @patch("cli_anything.rms.core.reports.api_post")
    def test_create_template(self, mock_post):
        from cli_anything.rms.core.reports import create_template

        mock_post.return_value = {"success": True, "data": {"id": 2, "name": "new-tmpl"}}
        result = create_template("token", {"name": "new-tmpl"})
        assert result["data"]["name"] == "new-tmpl"


class TestHotspots:
    @patch("cli_anything.rms.core.hotspots.api_get")
    def test_list_hotspots(self, mock_get):
        from cli_anything.rms.core.hotspots import list_hotspots

        mock_get.return_value = {"success": True, "data": [{"id": 1}]}
        result = list_hotspots("token")
        mock_get.assert_called_once()
        assert result["success"] is True

    @patch("cli_anything.rms.core.hotspots.api_get")
    def test_list_hotspots_by_device(self, mock_get):
        from cli_anything.rms.core.hotspots import list_hotspots

        mock_get.return_value = {"success": True, "data": []}
        list_hotspots("token", device_id="42")
        call_args = mock_get.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params", {})
        assert params.get("device_id") == "42"

    @patch("cli_anything.rms.core.hotspots.api_get")
    def test_get_hotspot(self, mock_get):
        from cli_anything.rms.core.hotspots import get_hotspot

        mock_get.return_value = {"success": True, "data": {"id": 1, "name": "Lobby"}}
        result = get_hotspot("token", "1")
        assert result["data"]["name"] == "Lobby"

    @patch("cli_anything.rms.core.hotspots.api_post")
    def test_create_hotspot(self, mock_post):
        from cli_anything.rms.core.hotspots import create_hotspot

        mock_post.return_value = {"success": True, "data": {"id": 2, "name": "Cafe"}}
        result = create_hotspot("token", {"name": "Cafe"})
        assert result["data"]["name"] == "Cafe"

    @patch("cli_anything.rms.core.hotspots.api_put")
    def test_update_hotspot(self, mock_put):
        from cli_anything.rms.core.hotspots import update_hotspot

        mock_put.return_value = {"success": True, "data": {"id": 1, "name": "Updated"}}
        result = update_hotspot("token", "1", {"name": "Updated"})
        assert result["data"]["name"] == "Updated"

    @patch("cli_anything.rms.core.hotspots.api_delete")
    def test_delete_hotspot(self, mock_delete):
        from cli_anything.rms.core.hotspots import delete_hotspot

        mock_delete.return_value = {"success": True}
        result = delete_hotspot("token", "1")
        assert result["success"] is True


class TestPasswords:
    @patch("cli_anything.rms.core.passwords.api_get")
    def test_get_password(self, mock_get):
        from cli_anything.rms.core.passwords import get_password

        mock_get.return_value = {"success": True, "data": {"device_id": "42", "password": "***"}}
        result = get_password("token", "42")
        assert result["data"]["device_id"] == "42"

    @patch("cli_anything.rms.core.passwords.api_put")
    def test_update_password(self, mock_put):
        from cli_anything.rms.core.passwords import update_password

        mock_put.return_value = {"success": True, "data": {"device_id": "42"}}
        result = update_password("token", "42", {"password": "newpass"})
        assert result["success"] is True


class TestSmtp:
    @patch("cli_anything.rms.core.smtp.api_get")
    def test_list_smtp_configs(self, mock_get):
        from cli_anything.rms.core.smtp import list_smtp_configs

        mock_get.return_value = {"success": True, "data": [{"id": 1, "host": "smtp.test"}]}
        result = list_smtp_configs("token")
        mock_get.assert_called_once()
        assert result["data"][0]["host"] == "smtp.test"

    @patch("cli_anything.rms.core.smtp.api_get")
    def test_get_smtp_config(self, mock_get):
        from cli_anything.rms.core.smtp import get_smtp_config

        mock_get.return_value = {"success": True, "data": {"id": 1, "host": "smtp.test"}}
        result = get_smtp_config("token", "1")
        assert result["data"]["id"] == 1

    @patch("cli_anything.rms.core.smtp.api_post")
    def test_create_smtp_config(self, mock_post):
        from cli_anything.rms.core.smtp import create_smtp_config

        mock_post.return_value = {"success": True, "data": {"id": 2, "host": "new.smtp"}}
        result = create_smtp_config("token", {"host": "new.smtp", "port": 587})
        assert result["data"]["host"] == "new.smtp"

    @patch("cli_anything.rms.core.smtp.api_put")
    def test_update_smtp_config(self, mock_put):
        from cli_anything.rms.core.smtp import update_smtp_config

        mock_put.return_value = {"success": True, "data": {"id": 1, "host": "updated.smtp"}}
        result = update_smtp_config("token", "1", {"host": "updated.smtp"})
        assert result["data"]["host"] == "updated.smtp"

    @patch("cli_anything.rms.core.smtp.api_delete")
    def test_delete_smtp_config(self, mock_delete):
        from cli_anything.rms.core.smtp import delete_smtp_config

        mock_delete.return_value = {"success": True}
        result = delete_smtp_config("token", "1")
        assert result["success"] is True


# ── Phase 3: _handle_response direct tests ────────────────────────────


class TestHandleResponse:
    """Direct tests for _handle_response edge cases."""

    def test_success_json(self):
        from cli_anything.rms.utils.rms_backend import _handle_response

        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"success": True, "data": [1, 2, 3]}
        result = _handle_response(resp)
        assert result == {"success": True, "data": [1, 2, 3]}

    def test_success_non_json(self):
        from cli_anything.rms.utils.rms_backend import _handle_response

        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.side_effect = ValueError("No JSON")
        resp.text = "plain text body"
        result = _handle_response(resp)
        assert result == {"success": True, "data": "plain text body"}

    def test_error_with_messages(self):
        import requests as _requests
        from cli_anything.rms.utils.rms_backend import _handle_response

        resp = MagicMock()
        resp.status_code = 400
        resp.raise_for_status.side_effect = _requests.exceptions.HTTPError("400")
        resp.json.return_value = {"errors": [{"message": "Invalid field"}, {"message": "Missing param"}]}
        with pytest.raises(RuntimeError, match="Invalid field"):
            _handle_response(resp)

    def test_error_plain_text(self):
        import requests as _requests
        from cli_anything.rms.utils.rms_backend import _handle_response

        resp = MagicMock()
        resp.status_code = 500
        resp.raise_for_status.side_effect = _requests.exceptions.HTTPError("500")
        resp.json.side_effect = ValueError("No JSON")
        resp.text = "Internal Server Error"
        with pytest.raises(RuntimeError, match="Internal Server Error"):
            _handle_response(resp)

    def test_rate_limit(self):
        from cli_anything.rms.utils.rms_backend import _handle_response

        resp = MagicMock()
        resp.status_code = 429
        resp.headers = {"Retry-After": "30"}
        with pytest.raises(RuntimeError, match="Rate limit"):
            _handle_response(resp)


# ── File upload tests ─────────────────────────────────────────────────


class TestFiles:
    """Tests for file operations."""

    @patch("cli_anything.rms.core.files.requests.post")
    def test_upload_file(self, mock_post):
        from cli_anything.rms.core.files import upload_file

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": True, "data": {"id": 99}}
        mock_post.return_value = mock_resp

        with patch("builtins.open", mock_open(read_data=b"file-content")):
            result = upload_file("test-token", "/tmp/test.bin")

        assert mock_post.called
        assert result["success"] is True


# ── Device ID zero tests ─────────────────────────────────────────────


class TestDeviceIdZero:
    """Verify device_id=0 is not falsy-skipped."""

    @patch("cli_anything.rms.core.alerts.api_get")
    def test_alerts_device_id_zero(self, mock_get):
        from cli_anything.rms.core.alerts import list_alerts

        mock_get.return_value = {"success": True, "data": []}
        list_alerts("token", device_id=0)
        params = mock_get.call_args.kwargs.get("params", {})
        assert "device_id" in params

    @patch("cli_anything.rms.core.configs.api_get")
    def test_configs_device_id_zero(self, mock_get):
        from cli_anything.rms.core.configs import list_configs

        mock_get.return_value = {"success": True, "data": []}
        list_configs("token", device_id=0)
        params = mock_get.call_args.kwargs.get("params", {})
        assert "device_id" in params

    @patch("cli_anything.rms.core.logs.api_get")
    def test_logs_device_id_zero(self, mock_get):
        from cli_anything.rms.core.logs import list_logs

        mock_get.return_value = {"success": True, "data": []}
        list_logs("token", device_id=0)
        params = mock_get.call_args.kwargs.get("params", {})
        assert "device_id" in params


# ── CLI Runner tests ──────────────────────────────────────────────────


class TestCLI:
    """Click CliRunner tests for CLI commands."""

    def setup_method(self):
        from click.testing import CliRunner

        self.runner = CliRunner()

    def test_root_help(self):
        from cli_anything.rms.rms_cli import cli

        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Teltonika RMS CLI" in result.output
        assert "devices" in result.output
        assert "alerts" in result.output

    def test_devices_help(self):
        from cli_anything.rms.rms_cli import cli

        result = self.runner.invoke(cli, ["devices", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "get" in result.output

    def test_auth_help(self):
        from cli_anything.rms.rms_cli import cli

        result = self.runner.invoke(cli, ["auth", "--help"])
        assert result.exit_code == 0
        assert "test" in result.output
        assert "status" in result.output

    def test_devices_list_json_no_token(self):
        from cli_anything.rms.rms_cli import cli

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RMS_API_TOKEN", None)
            result = self.runner.invoke(cli, ["--json", "devices", "list"])
        assert "error" in result.output.lower() or result.exit_code != 0

    @patch("cli_anything.rms.core.devices.api_get")
    def test_devices_list_json(self, mock_api):
        from cli_anything.rms.rms_cli import cli

        mock_api.return_value = {"success": True, "data": [{"id": 1, "name": "Router1", "serial": "ABC"}]}
        with patch.dict(os.environ, {"RMS_API_TOKEN": "test-token"}):
            result = self.runner.invoke(cli, ["--json", "devices", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True
        assert len(data["data"]) == 1
        assert data["data"][0]["name"] == "Router1"

    @patch("cli_anything.rms.core.devices.api_get")
    def test_devices_get(self, mock_api):
        from cli_anything.rms.rms_cli import cli

        mock_api.return_value = {"success": True, "data": {"id": 42, "name": "Gateway"}}
        with patch.dict(os.environ, {"RMS_API_TOKEN": "test-token"}):
            result = self.runner.invoke(cli, ["--json", "devices", "get", "42"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["data"]["id"] == 42
        assert data["data"]["name"] == "Gateway"

    @patch("cli_anything.rms.utils.rms_backend.api_get")
    def test_auth_test(self, mock_api):
        from cli_anything.rms.rms_cli import cli

        mock_api.return_value = {"success": True, "data": []}
        with patch.dict(os.environ, {"RMS_API_TOKEN": "test-token"}):
            result = self.runner.invoke(cli, ["auth", "test"])
        assert result.exit_code == 0
        assert "passed" in result.output.lower() or "ok" in result.output.lower()

    def test_passwords_update_no_password(self):
        from cli_anything.rms.rms_cli import cli

        with patch.dict(os.environ, {"RMS_API_TOKEN": "test-token"}):
            result = self.runner.invoke(cli, ["passwords", "update", "123"])
        assert result.exit_code != 0 or "error" in result.output.lower()
