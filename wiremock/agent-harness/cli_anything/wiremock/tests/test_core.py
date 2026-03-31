"""Unit tests for cli_anything.wiremock core modules.

All tests use unittest.mock to intercept HTTP calls — no live server required.
"""
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(status_code: int = 200, json_data: dict = None):
    """Return a mock requests.Response with configurable status and JSON."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data or {}
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        from requests.exceptions import HTTPError
        mock.raise_for_status.side_effect = HTTPError(f"{status_code}")
    return mock


# ---------------------------------------------------------------------------
# WireMockClient tests
# ---------------------------------------------------------------------------


class TestWireMockClient(unittest.TestCase):
    def setUp(self):
        from cli_anything.wiremock.utils.client import WireMockClient
        self.client = WireMockClient(host="testhost", port=9090, scheme="https")

    def test_base_url_construction(self):
        self.assertEqual(self.client.base_url(), "https://testhost:9090/__admin")

    def test_base_url_defaults(self):
        from cli_anything.wiremock.utils.client import WireMockClient
        c = WireMockClient()
        self.assertEqual(c.base_url(), "http://localhost:8080/__admin")

    @patch("requests.get")
    def test_get_passes_auth_and_timeout(self, mock_get):
        mock_get.return_value = _mock_response(200, {})
        self.client.auth = ("user", "pass")
        self.client.get("/mappings")
        mock_get.assert_called_once_with(
            "https://testhost:9090/__admin/mappings",
            auth=("user", "pass"),
            timeout=30,
        )

    @patch("requests.post")
    def test_post_sends_json(self, mock_post):
        mock_post.return_value = _mock_response(200, {})
        self.client.post("/mappings", json={"key": "value"})
        mock_post.assert_called_once_with(
            "https://testhost:9090/__admin/mappings",
            json={"key": "value"},
            auth=None,
            timeout=30,
        )

    @patch("requests.put")
    def test_put_sends_json(self, mock_put):
        mock_put.return_value = _mock_response(200, {})
        self.client.put("/mappings/abc", json={"id": "abc"})
        mock_put.assert_called_once()

    @patch("requests.delete")
    def test_delete(self, mock_delete):
        mock_delete.return_value = _mock_response(200, {})
        self.client.delete("/mappings/abc")
        mock_delete.assert_called_once()

    @patch("requests.patch")
    def test_patch(self, mock_patch):
        mock_patch.return_value = _mock_response(200, {})
        self.client.patch("/mappings/abc", json={"name": "x"})
        mock_patch.assert_called_once()

    @patch("requests.get")
    def test_is_alive_true(self, mock_get):
        mock_get.return_value = _mock_response(200, {})
        self.assertTrue(self.client.is_alive())

    @patch("requests.get")
    def test_is_alive_false_on_non_200(self, mock_get):
        mock_get.return_value = _mock_response(503, {})
        self.assertFalse(self.client.is_alive())

    @patch("requests.get")
    def test_is_alive_false_on_exception(self, mock_get):
        mock_get.side_effect = ConnectionError("refused")
        self.assertFalse(self.client.is_alive())


# ---------------------------------------------------------------------------
# Session tests
# ---------------------------------------------------------------------------


class TestSession(unittest.TestCase):
    def test_from_env_defaults(self):
        from cli_anything.wiremock.core.session import Session
        env = {}
        with patch.dict(os.environ, env, clear=False):
            # Remove keys if they exist so defaults are used
            for k in ["WIREMOCK_HOST", "WIREMOCK_PORT", "WIREMOCK_SCHEME",
                       "WIREMOCK_USER", "WIREMOCK_PASSWORD"]:
                os.environ.pop(k, None)
            s = Session.from_env()
        self.assertEqual(s.host, "localhost")
        self.assertEqual(s.port, 8080)
        self.assertEqual(s.scheme, "http")
        self.assertIsNone(s.username)
        self.assertIsNone(s.password)

    def test_from_env_reads_env_vars(self):
        from cli_anything.wiremock.core.session import Session
        with patch.dict(os.environ, {
            "WIREMOCK_HOST": "myhost",
            "WIREMOCK_PORT": "9999",
            "WIREMOCK_SCHEME": "https",
            "WIREMOCK_USER": "admin",
            "WIREMOCK_PASSWORD": "secret",
        }):
            s = Session.from_env()
        self.assertEqual(s.host, "myhost")
        self.assertEqual(s.port, 9999)
        self.assertEqual(s.scheme, "https")
        self.assertEqual(s.username, "admin")
        self.assertEqual(s.password, "secret")

    def test_auth_returns_tuple_when_both_set(self):
        from cli_anything.wiremock.core.session import Session
        s = Session(username="u", password="p")
        self.assertEqual(s.auth(), ("u", "p"))

    def test_auth_returns_none_when_partial(self):
        from cli_anything.wiremock.core.session import Session
        s = Session(username="u")  # no password
        self.assertIsNone(s.auth())

    def test_auth_returns_none_when_empty(self):
        from cli_anything.wiremock.core.session import Session
        s = Session()
        self.assertIsNone(s.auth())


# ---------------------------------------------------------------------------
# StubsManager tests
# ---------------------------------------------------------------------------


class TestStubsManager(unittest.TestCase):
    def setUp(self):
        from cli_anything.wiremock.utils.client import WireMockClient
        from cli_anything.wiremock.core.stubs import StubsManager
        self.client = WireMockClient()
        self.mgr = StubsManager(self.client)

    @patch("requests.get")
    def test_list_no_params(self, mock_get):
        mock_get.return_value = _mock_response(200, {"mappings": [], "total": 0})
        result = self.mgr.list()
        self.assertEqual(result["total"], 0)
        call_kwargs = mock_get.call_args
        # params should not include limit/offset when not provided
        self.assertNotIn("limit", call_kwargs.kwargs.get("params", {}))

    @patch("requests.get")
    def test_list_with_limit_and_offset(self, mock_get):
        mock_get.return_value = _mock_response(200, {"mappings": [], "total": 0})
        self.mgr.list(limit=10, offset=5)
        params = mock_get.call_args.kwargs.get("params", {})
        self.assertEqual(params["limit"], 10)
        self.assertEqual(params["offset"], 5)

    @patch("requests.get")
    def test_get_stub(self, mock_get):
        stub_data = {"id": "abc-123", "request": {"method": "GET"}}
        mock_get.return_value = _mock_response(200, stub_data)
        result = self.mgr.get("abc-123")
        self.assertEqual(result["id"], "abc-123")
        mock_get.assert_called_once()
        assert "/mappings/abc-123" in mock_get.call_args.args[0]

    @patch("requests.post")
    def test_create_stub(self, mock_post):
        created = {"id": "new-id", "request": {"method": "GET", "url": "/foo"}}
        mock_post.return_value = _mock_response(201, created)
        mapping = {"request": {"method": "GET", "url": "/foo"}, "response": {"status": 200}}
        result = self.mgr.create(mapping)
        self.assertEqual(result["id"], "new-id")
        posted_json = mock_post.call_args.kwargs["json"]
        self.assertEqual(posted_json["request"]["url"], "/foo")

    @patch("requests.delete")
    def test_delete_stub(self, mock_delete):
        mock_delete.return_value = _mock_response(200, {})
        self.mgr.delete("abc-123")
        mock_delete.assert_called_once()
        assert "/mappings/abc-123" in mock_delete.call_args.args[0]

    @patch("requests.post")
    def test_reset(self, mock_post):
        mock_post.return_value = _mock_response(200, {})
        self.mgr.reset()
        assert "/mappings/reset" in mock_post.call_args.args[0]

    @patch("requests.post")
    def test_save(self, mock_post):
        mock_post.return_value = _mock_response(200, {})
        self.mgr.save()
        assert "/mappings/save" in mock_post.call_args.args[0]

    @patch("requests.post")
    def test_quick_stub_no_body(self, mock_post):
        mock_post.return_value = _mock_response(200, {"id": "q1"})
        self.mgr.quick_stub("GET", "/ping", 200)
        sent = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent["request"]["method"], "GET")
        self.assertEqual(sent["request"]["url"], "/ping")
        self.assertEqual(sent["response"]["status"], 200)
        self.assertNotIn("body", sent["response"])

    @patch("requests.post")
    def test_quick_stub_with_body(self, mock_post):
        mock_post.return_value = _mock_response(200, {"id": "q2"})
        self.mgr.quick_stub("POST", "/data", 201, body='{"ok":true}')
        sent = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent["response"]["body"], '{"ok":true}')
        self.assertIn("Content-Type", sent["response"]["headers"])

    @patch("requests.post")
    def test_quick_stub_method_uppercased(self, mock_post):
        mock_post.return_value = _mock_response(200, {"id": "q3"})
        self.mgr.quick_stub("get", "/health", 200)
        sent = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent["request"]["method"], "GET")

    @patch("requests.post")
    def test_import_stubs(self, mock_post):
        mock_post.return_value = _mock_response(200, {"mappings": []})
        result = self.mgr.import_stubs({"mappings": []})
        assert "/mappings/import" in mock_post.call_args.args[0]
        self.assertIn("mappings", result)

    @patch("requests.post")
    def test_find_by_metadata(self, mock_post):
        mock_post.return_value = _mock_response(200, {"mappings": []})
        pattern = {"matchesJsonPath": {"expression": "$.name", "equalTo": "x"}}
        self.mgr.find_by_metadata(pattern)
        assert "/mappings/find-by-metadata" in mock_post.call_args.args[0]


# ---------------------------------------------------------------------------
# RequestsLog tests
# ---------------------------------------------------------------------------


class TestRequestsLog(unittest.TestCase):
    def setUp(self):
        from cli_anything.wiremock.utils.client import WireMockClient
        from cli_anything.wiremock.core.requests_log import RequestsLog
        self.client = WireMockClient()
        self.log = RequestsLog(self.client)

    @patch("requests.get")
    def test_list(self, mock_get):
        mock_get.return_value = _mock_response(200, {"serveEvents": [], "total": 0})
        result = self.log.list()
        self.assertIn("serveEvents", result)

    @patch("requests.get")
    def test_list_with_limit(self, mock_get):
        mock_get.return_value = _mock_response(200, {"serveEvents": [], "total": 0})
        self.log.list(limit=5)
        params = mock_get.call_args.kwargs.get("params", {})
        self.assertEqual(params["limit"], 5)

    @patch("requests.post")
    def test_find(self, mock_post):
        mock_post.return_value = _mock_response(200, {"requests": []})
        pattern = {"method": "GET", "url": "/foo"}
        result = self.log.find(pattern)
        assert "/requests/find" in mock_post.call_args.args[0]
        self.assertIn("requests", result)

    @patch("requests.post")
    def test_count(self, mock_post):
        mock_post.return_value = _mock_response(200, {"count": 3})
        pattern = {"method": "POST"}
        result = self.log.count(pattern)
        self.assertEqual(result["count"], 3)
        assert "/requests/count" in mock_post.call_args.args[0]

    @patch("requests.get")
    def test_unmatched(self, mock_get):
        mock_get.return_value = _mock_response(200, {"requests": []})
        result = self.log.unmatched()
        assert "/requests/unmatched" in mock_get.call_args.args[0]

    @patch("requests.get")
    def test_near_misses_unmatched(self, mock_get):
        mock_get.return_value = _mock_response(200, {"nearMisses": []})
        result = self.log.near_misses_unmatched()
        assert "/requests/unmatched/near-misses" in mock_get.call_args.args[0]

    @patch("requests.delete")
    def test_reset(self, mock_delete):
        mock_delete.return_value = _mock_response(200, {})
        self.log.reset()
        assert "/requests" in mock_delete.call_args.args[0]


# ---------------------------------------------------------------------------
# ScenariosManager tests
# ---------------------------------------------------------------------------


class TestScenariosManager(unittest.TestCase):
    def setUp(self):
        from cli_anything.wiremock.utils.client import WireMockClient
        from cli_anything.wiremock.core.scenarios import ScenariosManager
        self.client = WireMockClient()
        self.mgr = ScenariosManager(self.client)

    @patch("requests.get")
    def test_list(self, mock_get):
        mock_get.return_value = _mock_response(200, {"scenarios": []})
        result = self.mgr.list()
        self.assertIn("scenarios", result)
        assert "/scenarios" in mock_get.call_args.args[0]

    @patch("requests.put")
    def test_set_state(self, mock_put):
        mock_put.return_value = _mock_response(200, {})
        self.mgr.set_state("login-flow", "logged-in")
        assert "/scenarios/login-flow/state" in mock_put.call_args.args[0]
        sent = mock_put.call_args.kwargs["json"]
        self.assertEqual(sent["state"], "logged-in")

    @patch("requests.post")
    def test_reset_all(self, mock_post):
        mock_post.return_value = _mock_response(200, {})
        self.mgr.reset_all()
        assert "/scenarios/reset" in mock_post.call_args.args[0]


# ---------------------------------------------------------------------------
# RecordingManager tests
# ---------------------------------------------------------------------------


class TestRecordingManager(unittest.TestCase):
    def setUp(self):
        from cli_anything.wiremock.utils.client import WireMockClient
        from cli_anything.wiremock.core.recording import RecordingManager
        self.client = WireMockClient()
        self.mgr = RecordingManager(self.client)

    @patch("requests.post")
    def test_start_no_headers(self, mock_post):
        mock_post.return_value = _mock_response(200, {"status": "Recording"})
        result = self.mgr.start("https://api.example.com")
        sent = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent["targetBaseUrl"], "https://api.example.com")
        self.assertNotIn("captureHeaders", sent)

    @patch("requests.post")
    def test_start_with_headers(self, mock_post):
        mock_post.return_value = _mock_response(200, {"status": "Recording"})
        self.mgr.start("https://api.example.com", headers_to_match=["Authorization", "X-Api-Key"])
        sent = mock_post.call_args.kwargs["json"]
        self.assertIn("captureHeaders", sent)
        self.assertIn("Authorization", sent["captureHeaders"])
        self.assertIn("X-Api-Key", sent["captureHeaders"])
        self.assertTrue(sent["captureHeaders"]["Authorization"]["caseInsensitive"])

    @patch("requests.post")
    def test_stop(self, mock_post):
        mock_post.return_value = _mock_response(200, {"mappings": [{"id": "x"}]})
        result = self.mgr.stop()
        assert "/recordings/stop" in mock_post.call_args.args[0]
        self.assertIn("mappings", result)

    @patch("requests.get")
    def test_status(self, mock_get):
        mock_get.return_value = _mock_response(200, {"status": "Recording"})
        result = self.mgr.status()
        assert "/recordings/status" in mock_get.call_args.args[0]
        self.assertEqual(result["status"], "Recording")

    @patch("requests.post")
    def test_snapshot(self, mock_post):
        mock_post.return_value = _mock_response(200, {"mappings": []})
        result = self.mgr.snapshot()
        assert "/recordings/snapshot" in mock_post.call_args.args[0]
        self.assertIn("mappings", result)

    @patch("requests.post")
    def test_snapshot_with_spec(self, mock_post):
        mock_post.return_value = _mock_response(200, {"mappings": []})
        self.mgr.snapshot(spec={"persist": False})
        sent = mock_post.call_args.kwargs["json"]
        self.assertFalse(sent["persist"])


# ---------------------------------------------------------------------------
# SettingsManager tests
# ---------------------------------------------------------------------------


class TestSettingsManager(unittest.TestCase):
    def setUp(self):
        from cli_anything.wiremock.utils.client import WireMockClient
        from cli_anything.wiremock.core.settings import SettingsManager
        self.client = WireMockClient()
        self.mgr = SettingsManager(self.client)

    @patch("requests.get")
    def test_get(self, mock_get):
        mock_get.return_value = _mock_response(200, {"fixedDelay": 0})
        result = self.mgr.get()
        assert "/settings" in mock_get.call_args.args[0]
        self.assertIn("fixedDelay", result)

    @patch("requests.put")
    def test_update(self, mock_put):
        mock_put.return_value = _mock_response(200, {"fixedDelay": 500})
        result = self.mgr.update({"fixedDelay": 500})
        sent = mock_put.call_args.kwargs["json"]
        self.assertEqual(sent["fixedDelay"], 500)

    @patch("requests.get")
    def test_get_version(self, mock_get):
        mock_get.return_value = _mock_response(200, {"version": "3.3.1"})
        result = self.mgr.get_version()
        assert "/version" in mock_get.call_args.args[0]
        self.assertEqual(result["version"], "3.3.1")


# ---------------------------------------------------------------------------
# Output utility tests
# ---------------------------------------------------------------------------


class TestOutputFunctions(unittest.TestCase):
    def test_print_json(self):
        from cli_anything.wiremock.utils.output import print_json
        import io
        with patch("builtins.print") as mock_print:
            print_json({"key": "value"})
            mock_print.assert_called_once()
            output = mock_print.call_args.args[0]
            parsed = json.loads(output)
            self.assertEqual(parsed["key"], "value")

    def test_success_json_mode(self):
        from cli_anything.wiremock.utils.output import success
        with patch("builtins.print") as mock_print:
            success("All good", data={"result": 1}, json_mode=True)
            mock_print.assert_called_once()
            output = mock_print.call_args.args[0]
            parsed = json.loads(output)
            self.assertEqual(parsed["status"], "ok")
            self.assertEqual(parsed["message"], "All good")
            self.assertEqual(parsed["data"]["result"], 1)

    def test_success_human_mode(self):
        from cli_anything.wiremock.utils.output import success
        with patch("builtins.print") as mock_print:
            success("Done", json_mode=False)
            first_call = mock_print.call_args_list[0].args[0]
            self.assertIn("Done", first_call)

    def test_error_json_mode(self):
        from cli_anything.wiremock.utils.output import error
        with patch("builtins.print") as mock_print:
            with self.assertRaises(SystemExit) as cm:
                error("Something broke", json_mode=True)
            self.assertEqual(cm.exception.code, 1)
            output = mock_print.call_args.args[0]
            parsed = json.loads(output)
            self.assertEqual(parsed["status"], "error")
            self.assertEqual(parsed["message"], "Something broke")

    def test_error_human_mode_exits_1(self):
        from cli_anything.wiremock.utils.output import error
        with self.assertRaises(SystemExit) as cm:
            error("Oops", json_mode=False)
        self.assertEqual(cm.exception.code, 1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
