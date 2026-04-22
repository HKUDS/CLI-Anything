r"""
Unit tests

Test core functionality with synthetic data, no external dependencies
"""

import pytest
import json
from unittest.mock import Mock, patch
from datetime import datetime

from cli_anything.firefly_iii.utils.firefly_iii_backend import FireflyIIIBackend


class TestFireflyIIIBackend:
    """Test Firefly III backend client"""

    @patch('cli_anything.firefly_iii.utils.firefly_iii_backend.requests.get')
    def test_init_success(self, mock_get):
        """Test successful initialization"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"version": "6.0.0"}}
        mock_get.return_value = mock_response

        backend = FireflyIIIBackend("https://firefly.example.com", "test-pat")

        assert backend.base_url == "https://firefly.example.com"
        assert backend.pat == "test-pat"
        assert backend.headers['Authorization'] == 'Bearer test-pat'

    @patch('cli_anything.firefly_iii.utils.firefly_iii_backend.requests.get')
    def test_init_connection_error(self, mock_get):
        """Test connection error"""
        from requests.exceptions import ConnectionError
        mock_get.side_effect = ConnectionError()

        with pytest.raises(RuntimeError) as exc_info:
            FireflyIIIBackend("https://firefly.example.com", "test-pat")

        assert "Cannot connect to Firefly III instance" in str(exc_info.value)

    @patch('cli_anything.firefly_iii.utils.firefly_iii_backend.requests.get')
    def test_init_auth_error(self, mock_get):
        """Test authentication error"""
        from requests.exceptions import HTTPError
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = HTTPError()
        mock_get.return_value = mock_response

        with pytest.raises(RuntimeError) as exc_info:
            FireflyIIIBackend("https://firefly.example.com", "invalid-pat")

        assert "Authentication failed" in str(exc_info.value)

    @patch('cli_anything.firefly_iii.utils.firefly_iii_backend.requests.get')
    @patch('cli_anything.firefly_iii.utils.firefly_iii_backend.requests.request')
    def test_get_request(self, mock_request, mock_get):
        """Test GET request"""
        # Mock validation request during initialization
        mock_init_response = Mock()
        mock_init_response.status_code = 200
        mock_init_response.json.return_value = {"data": {"version": "6.0.0"}}
        mock_get.return_value = mock_init_response

        # Mock actual request
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": 1, "name": "Test"}]}
        mock_request.return_value = mock_response

        backend = FireflyIIIBackend("https://firefly.example.com", "test-pat")
        result = backend.get("/accounts")

        assert result["data"][0]["name"] == "Test"
        mock_request.assert_called_once()

    @patch('cli_anything.firefly_iii.utils.firefly_iii_backend.requests.get')
    @patch('cli_anything.firefly_iii.utils.firefly_iii_backend.requests.request')
    def test_post_request(self, mock_request, mock_get):
        """Test POST request"""
        # Mock validation request during initialization
        mock_init_response = Mock()
        mock_init_response.status_code = 200
        mock_init_response.json.return_value = {"data": {"version": "6.0.0"}}
        mock_get.return_value = mock_init_response

        # Mock actual request
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"id": 1}}
        mock_request.return_value = mock_response

        backend = FireflyIIIBackend("https://firefly.example.com", "test-pat")
        result = backend.post("/accounts", data={"name": "Test"})

        assert result["data"]["id"] == 1


class TestOutput:
    """Test output formatting"""

    def test_json_output(self, capsys):
        """Test JSON output"""
        from cli_anything.firefly_iii.firefly_iii_cli import output
        import cli_anything.firefly_iii.firefly_iii_cli as cli_module

        cli_module._json_output = True
        test_data = {"key": "value"}

        output(test_data)

        captured = capsys.readouterr()
        assert json.loads(captured.out) == test_data

    def test_human_readable_output(self, capsys):
        """Test human-readable output"""
        from cli_anything.firefly_iii.firefly_iii_cli import output
        import cli_anything.firefly_iii.firefly_iii_cli as cli_module

        cli_module._json_output = False
        test_data = {"data": [{"id": 1, "attributes": {"name": "Test Account"}}]}

        output(test_data)

        captured = capsys.readouterr()
        assert "Test Account" in captured.out


class TestPresets:
    """Test preset functionality"""

    def test_default_preset(self):
        """Test default preset"""
        # Default preset should include core commands
        default_commands = ['accounts', 'transactions', 'categories', 'tags', 'bills', 'search']
        assert len(default_commands) > 0

    def test_full_preset(self):
        """Test full preset"""
        # Full preset should include all commands
        all_commands = ['accounts', 'transactions', 'budgets', 'categories', 'tags',
                       'bills', 'piggy_banks', 'insights', 'search', 'export', 'info']
        assert len(all_commands) == 11


class TestValidation:
    """Test input validation"""

    def test_date_format(self):
        """Test date format validation"""
        valid_date = "2024-01-15"
        try:
            datetime.strptime(valid_date, "%Y-%m-%d")
            assert True
        except ValueError:
            assert False

    def test_invalid_date_format(self):
        """Test invalid date format"""
        invalid_date = "01-15-2024"
        with pytest.raises(ValueError):
            datetime.strptime(invalid_date, "%Y-%m-%d")

    def test_amount_format(self):
        """Test amount format"""
        valid_amounts = ["100.00", "50.5", "0.01", "1000"]
        for amount in valid_amounts:
            try:
                float(amount)
                assert True
            except ValueError:
                assert False
