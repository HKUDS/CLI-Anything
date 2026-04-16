"""E2E tests for cli-anything-rms — requires valid RMS_API_TOKEN."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

# Skip all tests if no token is available
pytestmark = pytest.mark.skipif(
    not os.environ.get("RMS_API_TOKEN"),
    reason="RMS_API_TOKEN not set — skipping E2E tests",
)


class TestAPIConnectivity:
    def test_api_connectivity(self):
        from cli_anything.rms.utils.rms_backend import api_get, get_api_token

        token = get_api_token()
        result = api_get("/devices", params={"limit": 1}, token=token)
        assert result["success"] is True

    def test_auth_headers(self):
        from cli_anything.rms.utils.rms_backend import _make_auth_headers

        token = os.environ["RMS_API_TOKEN"]
        headers = _make_auth_headers(token)
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")


class TestDevicesE2E:
    def test_list_devices(self):
        from cli_anything.rms.core.devices import list_devices
        from cli_anything.rms.utils.rms_backend import get_api_token

        token = get_api_token()
        result = list_devices(token, limit=5)
        assert result["success"] is True
        assert "data" in result
        assert isinstance(result["data"], list)

    def test_get_device(self):
        from cli_anything.rms.core.devices import list_devices, get_device
        from cli_anything.rms.utils.rms_backend import get_api_token

        token = get_api_token()
        devices = list_devices(token, limit=1)
        if not devices["data"]:
            pytest.skip("No devices available")

        device_id = str(devices["data"][0]["id"])
        result = get_device(token, device_id)
        assert result["success"] is True
        assert result["data"]["id"] == devices["data"][0]["id"]


class TestResourceListingE2E:
    def test_list_companies(self):
        from cli_anything.rms.core.companies import list_companies
        from cli_anything.rms.utils.rms_backend import get_api_token

        token = get_api_token()
        result = list_companies(token, limit=5)
        assert result["success"] is True

    def test_list_users(self):
        from cli_anything.rms.core.users import list_users
        from cli_anything.rms.utils.rms_backend import get_api_token

        token = get_api_token()
        result = list_users(token, limit=5)
        assert result["success"] is True

    def test_list_tags(self):
        from cli_anything.rms.core.tags import list_tags
        from cli_anything.rms.utils.rms_backend import get_api_token

        token = get_api_token()
        result = list_tags(token, limit=5)
        assert result["success"] is True


class TestCLIIntegrationE2E:
    def _run_cli(self, *args):
        cmd = [sys.executable, "-m", "cli_anything.rms", "--json", *args]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result

    def test_cli_devices_list(self):
        result = self._run_cli("devices", "list", "--limit", "1")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "data" in data or "success" in data

    def test_cli_auth_test(self):
        result = self._run_cli("auth", "test")
        assert result.returncode == 0
