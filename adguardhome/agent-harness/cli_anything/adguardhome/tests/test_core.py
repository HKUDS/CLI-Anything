"""Unit tests for cli-anything-adguardhome core modules.

No real AdGuardHome instance needed - all HTTP calls are mocked.
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from cli_anything.adguardhome.utils.adguardhome_backend import AdGuardHomeClient
from cli_anything.adguardhome.core import project, filtering, blocking, clients, rewrite


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def mock_response(data=None, status=200, text=""):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    if data is not None:
        resp.json.return_value = data
        resp.content = json.dumps(data).encode()
        resp.text = json.dumps(data)
    else:
        resp.json.side_effect = ValueError("no json")
        resp.content = text.encode() if text else b""
        resp.text = text
    resp.raise_for_status = MagicMock()
    return resp


def make_client(host="localhost", port=3000, username="admin", password="secret"):
    return AdGuardHomeClient(host=host, port=port, username=username, password=password)


# ---------------------------------------------------------------------------
# AdGuardHomeClient
# ---------------------------------------------------------------------------

class TestAdGuardHomeClient:
    def test_client_init_default(self):
        c = AdGuardHomeClient()
        assert c.base_url == "http://localhost:3000/control"
        assert c.host == "localhost"
        assert c.port == 3000

    def test_client_init_with_auth(self):
        c = AdGuardHomeClient(username="admin", password="pass")
        assert c.session.auth == ("admin", "pass")

    def test_client_init_no_auth(self):
        c = AdGuardHomeClient()
        assert c.session.auth is None

    def test_client_url_construction(self):
        c = AdGuardHomeClient(host="192.168.1.1", port=8080)
        assert c._url("/status") == "http://192.168.1.1:8080/control/status"
        assert c._url("status") == "http://192.168.1.1:8080/control/status"

    def test_get_success(self):
        c = make_client()
        resp = mock_response({"running": True})
        with patch.object(c.session, "get", return_value=resp) as mock_get:
            result = c.get("/status")
            assert result == {"running": True}
            mock_get.assert_called_once()

    def test_get_empty_response(self):
        c = make_client()
        resp = mock_response()
        with patch.object(c.session, "get", return_value=resp):
            result = c.get("/restart")
            assert result == {}

    def test_post_json(self):
        c = make_client()
        resp = mock_response({})
        with patch.object(c.session, "post", return_value=resp) as mock_post:
            c.post("/filtering/add_url", {"url": "http://example.com/list.txt", "name": "Test"})
            call_kwargs = mock_post.call_args
            assert call_kwargs.kwargs.get("json") == {"url": "http://example.com/list.txt", "name": "Test"}

    def test_post_empty(self):
        c = make_client()
        resp = mock_response()
        with patch.object(c.session, "post", return_value=resp) as mock_post:
            result = c.post("/restart")
            assert result == {}
            mock_post.assert_called_once()

    def test_connection_error_raises_runtime(self):
        c = make_client()
        with patch.object(c.session, "get", side_effect=requests.exceptions.ConnectionError("refused")):
            with pytest.raises(RuntimeError) as exc_info:
                c.get("/status")
            assert "Cannot connect to AdGuardHome" in str(exc_info.value)
            assert "docker run" in str(exc_info.value).lower() or "docker" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# project.py
# ---------------------------------------------------------------------------

class TestProject:
    def test_load_config_defaults(self, tmp_path):
        result = project.load_config(config_path=tmp_path / "nonexistent.json")
        assert result["host"] == "localhost"
        assert result["port"] == 3000
        assert result["username"] == ""
        assert result["password"] == ""

    def test_load_config_from_file(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({
            "host": "192.168.1.1", "port": 8080,
            "username": "admin", "password": "secret"
        }))
        result = project.load_config(config_path=cfg_file)
        assert result["host"] == "192.168.1.1"
        assert result["port"] == 8080
        assert result["username"] == "admin"

    def test_load_config_env_override(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({"host": "from-file", "port": 3000}))
        monkeypatch.setenv("AGH_HOST", "from-env")
        monkeypatch.setenv("AGH_PORT", "9000")
        result = project.load_config(config_path=cfg_file)
        assert result["host"] == "from-env"
        assert result["port"] == 9000

    def test_save_config(self, tmp_path):
        path = tmp_path / "config.json"
        saved = project.save_config("myhost", 4000, "user", "pass", config_path=path)
        assert saved == path
        data = json.loads(path.read_text())
        assert data["host"] == "myhost"
        assert data["port"] == 4000


# ---------------------------------------------------------------------------
# filtering.py
# ---------------------------------------------------------------------------

class TestFiltering:
    def test_get_status(self):
        c = make_client()
        resp = mock_response({"enabled": True, "filters": []})
        with patch.object(c.session, "get", return_value=resp):
            result = filtering.get_status(c)
            assert result["enabled"] is True

    def test_add_filter(self):
        c = make_client()
        resp = mock_response({})
        with patch.object(c.session, "post", return_value=resp) as mock_post:
            filtering.add_filter(c, url="http://example.com/list.txt", name="Test")
            body = mock_post.call_args.kwargs["json"]
            assert body["url"] == "http://example.com/list.txt"
            assert body["name"] == "Test"
            assert body["whitelist"] is False

    def test_remove_filter(self):
        c = make_client()
        resp = mock_response({})
        with patch.object(c.session, "post", return_value=resp) as mock_post:
            filtering.remove_filter(c, url="http://example.com/list.txt")
            body = mock_post.call_args.kwargs["json"]
            assert body["url"] == "http://example.com/list.txt"

    def test_set_enabled(self):
        c = make_client()
        status_resp = mock_response({"enabled": False, "interval": 48})
        post_resp = mock_response({})
        with patch.object(c.session, "get", return_value=status_resp):
            with patch.object(c.session, "post", return_value=post_resp) as mock_post:
                filtering.set_enabled(c, enabled=True)
                body = mock_post.call_args.kwargs["json"]
                assert body["enabled"] is True
                assert body["interval"] == 48


# ---------------------------------------------------------------------------
# blocking.py
# ---------------------------------------------------------------------------

class TestBlocking:
    def test_parental_status(self):
        c = make_client()
        resp = mock_response({"enabled": False})
        with patch.object(c.session, "get", return_value=resp):
            result = blocking.parental_status(c)
            assert result == {"enabled": False}

    def test_parental_enable(self):
        c = make_client()
        resp = mock_response()
        with patch.object(c.session, "post", return_value=resp) as mock_post:
            blocking.parental_enable(c)
            assert "/parental/enable" in mock_post.call_args.args[0]

    def test_safebrowsing_status(self):
        c = make_client()
        resp = mock_response({"enabled": True})
        with patch.object(c.session, "get", return_value=resp):
            result = blocking.safebrowsing_status(c)
            assert result["enabled"] is True


# ---------------------------------------------------------------------------
# clients.py
# ---------------------------------------------------------------------------

class TestClients:
    def test_list_clients(self):
        c = make_client()
        data = {"clients": [{"name": "PC", "ids": ["192.168.1.10"]}], "auto_clients": []}
        resp = mock_response(data)
        with patch.object(c.session, "get", return_value=resp):
            result = clients.list_clients(c)
            assert len(result["clients"]) == 1

    def test_add_client(self):
        c = make_client()
        resp = mock_response({})
        with patch.object(c.session, "post", return_value=resp) as mock_post:
            clients.add_client(c, name="MyPC", ids=["192.168.1.100"])
            body = mock_post.call_args.kwargs["json"]
            assert body["name"] == "MyPC"
            assert "192.168.1.100" in body["ids"]


# ---------------------------------------------------------------------------
# rewrite.py
# ---------------------------------------------------------------------------

class TestRewrite:
    def test_list_rewrites(self):
        c = make_client()
        data = [{"domain": "myserver.local", "answer": "192.168.1.50"}]
        resp = mock_response(data)
        with patch.object(c.session, "get", return_value=resp):
            result = rewrite.list_rewrites(c)
            assert len(result) == 1
            assert result[0]["domain"] == "myserver.local"

    def test_add_rewrite(self):
        c = make_client()
        resp = mock_response({})
        with patch.object(c.session, "post", return_value=resp) as mock_post:
            rewrite.add_rewrite(c, domain="myserver.local", answer="192.168.1.50")
            body = mock_post.call_args.kwargs["json"]
            assert body["domain"] == "myserver.local"
            assert body["answer"] == "192.168.1.50"
