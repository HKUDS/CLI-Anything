r"""
Unit tests

Test core functionality with synthetic data, no external dependencies
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
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

    @patch('cli_anything.firefly_iii.utils.firefly_iii_backend.requests.get')
    @patch('cli_anything.firefly_iii.utils.firefly_iii_backend.requests.request')
    def test_delete_request_returns_204(self, mock_request, mock_get):
        """Test DELETE request with 204 response"""
        mock_init_response = Mock()
        mock_init_response.status_code = 200
        mock_init_response.json.return_value = {"data": {"version": "6.0.0"}}
        mock_get.return_value = mock_init_response

        mock_response = Mock()
        mock_response.status_code = 204
        mock_request.return_value = mock_response

        backend = FireflyIIIBackend("https://firefly.example.com", "test-pat")
        result = backend.delete("/accounts/1")

        assert result["status"] == "success"
        assert result["code"] == 204


class TestFireflyIIIBackendMethods:
    """Test all backend API methods exist and are callable"""

    @pytest.fixture
    def backend(self):
        """Create backend with mocked connection"""
        with patch('cli_anything.firefly_iii.utils.firefly_iii_backend.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"version": "6.0.0"}}
            mock_get.return_value = mock_response
            return FireflyIIIBackend("https://firefly.example.com", "test-pat")

    def test_accounts_crud(self, backend):
        """Test account CRUD methods exist"""
        assert hasattr(backend, 'get_accounts')
        assert hasattr(backend, 'get_account')
        assert hasattr(backend, 'create_account')
        assert hasattr(backend, 'update_account')
        assert hasattr(backend, 'delete_account')

    def test_transactions_crud(self, backend):
        """Test transaction CRUD methods exist"""
        assert hasattr(backend, 'get_transactions')
        assert hasattr(backend, 'get_transaction')
        assert hasattr(backend, 'create_transaction')
        assert hasattr(backend, 'update_transaction')
        assert hasattr(backend, 'delete_transaction')

    def test_budgets_crud(self, backend):
        """Test budget CRUD methods exist"""
        assert hasattr(backend, 'get_budgets')
        assert hasattr(backend, 'get_budget')
        assert hasattr(backend, 'create_budget')
        assert hasattr(backend, 'update_budget')
        assert hasattr(backend, 'delete_budget')
        assert hasattr(backend, 'get_budget_limits')
        assert hasattr(backend, 'create_budget_limit')
        assert hasattr(backend, 'update_budget_limit')
        assert hasattr(backend, 'delete_budget_limit')

    def test_categories_crud(self, backend):
        """Test category CRUD methods exist"""
        assert hasattr(backend, 'get_categories')
        assert hasattr(backend, 'get_category')
        assert hasattr(backend, 'create_category')
        assert hasattr(backend, 'update_category')
        assert hasattr(backend, 'delete_category')

    def test_tags_crud(self, backend):
        """Test tag CRUD methods exist"""
        assert hasattr(backend, 'get_tags')
        assert hasattr(backend, 'get_tag')
        assert hasattr(backend, 'create_tag')
        assert hasattr(backend, 'update_tag')
        assert hasattr(backend, 'delete_tag')

    def test_bills_crud(self, backend):
        """Test bill CRUD methods exist"""
        assert hasattr(backend, 'get_bills')
        assert hasattr(backend, 'get_bill')
        assert hasattr(backend, 'create_bill')
        assert hasattr(backend, 'update_bill')
        assert hasattr(backend, 'delete_bill')

    def test_piggy_banks_crud(self, backend):
        """Test piggy bank CRUD methods exist"""
        assert hasattr(backend, 'get_piggy_banks')
        assert hasattr(backend, 'get_piggy_bank')
        assert hasattr(backend, 'create_piggy_bank')
        assert hasattr(backend, 'update_piggy_bank')
        assert hasattr(backend, 'delete_piggy_bank')
        assert hasattr(backend, 'get_piggy_bank_events')
        assert hasattr(backend, 'create_piggy_bank_event')

    def test_autocomplete_methods(self, backend):
        """Test autocomplete methods exist"""
        assert hasattr(backend, 'autocomplete_accounts')
        assert hasattr(backend, 'autocomplete_bills')
        assert hasattr(backend, 'autocomplete_budgets')
        assert hasattr(backend, 'autocomplete_categories')
        assert hasattr(backend, 'autocomplete_currencies')
        assert hasattr(backend, 'autocomplete_piggy_banks')
        assert hasattr(backend, 'autocomplete_tags')
        assert hasattr(backend, 'autocomplete_transactions')
        assert hasattr(backend, 'autocomplete_rule_groups')
        assert hasattr(backend, 'autocomplete_rules')
        assert hasattr(backend, 'autocomplete_recurring')
        assert hasattr(backend, 'autocomplete_object_groups')
        assert hasattr(backend, 'autocomplete_transaction_types')

    def test_currencies_crud(self, backend):
        """Test currency CRUD methods exist"""
        assert hasattr(backend, 'get_currencies')
        assert hasattr(backend, 'get_currency')
        assert hasattr(backend, 'create_currency')
        assert hasattr(backend, 'update_currency')
        assert hasattr(backend, 'delete_currency')
        assert hasattr(backend, 'get_currency_exchange_rates')

    def test_recurrences_crud(self, backend):
        """Test recurrence CRUD methods exist"""
        assert hasattr(backend, 'get_recurrences')
        assert hasattr(backend, 'get_recurrence')
        assert hasattr(backend, 'create_recurrence')
        assert hasattr(backend, 'update_recurrence')
        assert hasattr(backend, 'delete_recurrence')

    def test_rules_crud(self, backend):
        """Test rule CRUD methods exist"""
        assert hasattr(backend, 'get_rules')
        assert hasattr(backend, 'get_rule')
        assert hasattr(backend, 'create_rule')
        assert hasattr(backend, 'update_rule')
        assert hasattr(backend, 'delete_rule')
        assert hasattr(backend, 'test_rule')
        assert hasattr(backend, 'execute_rule')

    def test_rule_groups_crud(self, backend):
        """Test rule group CRUD methods exist"""
        assert hasattr(backend, 'get_rule_groups')
        assert hasattr(backend, 'get_rule_group')
        assert hasattr(backend, 'create_rule_group')
        assert hasattr(backend, 'update_rule_group')
        assert hasattr(backend, 'delete_rule_group')
        assert hasattr(backend, 'execute_rule_group')

    def test_summary_methods(self, backend):
        """Test summary methods exist"""
        assert hasattr(backend, 'get_summary')

    def test_webhooks_crud(self, backend):
        """Test webhook CRUD methods exist"""
        assert hasattr(backend, 'get_webhooks')
        assert hasattr(backend, 'get_webhook')
        assert hasattr(backend, 'create_webhook')
        assert hasattr(backend, 'update_webhook')
        assert hasattr(backend, 'delete_webhook')
        assert hasattr(backend, 'trigger_webhook')

    def test_chart_methods(self, backend):
        """Test chart methods exist"""
        assert hasattr(backend, 'get_chart_account_overview')
        assert hasattr(backend, 'get_chart_balance')
        assert hasattr(backend, 'get_chart_budget_overview')
        assert hasattr(backend, 'get_chart_category_overview')

    def test_other_methods(self, backend):
        """Test other utility methods exist"""
        assert hasattr(backend, 'get_insight')
        assert hasattr(backend, 'search')
        assert hasattr(backend, 'export_data')
        assert hasattr(backend, 'get_available_budgets')
        assert hasattr(backend, 'create_available_budget')
        assert hasattr(backend, 'get_object_groups')
        assert hasattr(backend, 'get_links')
        assert hasattr(backend, 'get_attachments')
        assert hasattr(backend, 'get_configuration')
        assert hasattr(backend, 'get_preferences')
        assert hasattr(backend, 'get_users')
        assert hasattr(backend, 'get_user_groups')


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

    def test_human_readable_list_output(self, capsys):
        """Test human-readable list output"""
        from cli_anything.firefly_iii.firefly_iii_cli import output
        import cli_anything.firefly_iii.firefly_iii_cli as cli_module

        cli_module._json_output = False
        test_data = [{"name": "Item 1"}, {"name": "Item 2"}]

        output(test_data)

        captured = capsys.readouterr()
        assert "Item 1" in captured.out
        assert "Item 2" in captured.out

    def test_human_readable_plain_dict(self, capsys):
        """Test human-readable output with plain dict"""
        from cli_anything.firefly_iii.firefly_iii_cli import output
        import cli_anything.firefly_iii.firefly_iii_cli as cli_module

        cli_module._json_output = False
        test_data = {"key": "value", "count": 42}

        output(test_data)

        captured = capsys.readouterr()
        assert "key" in captured.out
        assert "value" in captured.out


class TestCommandGroups:
    """Test CLI command groups are registered"""

    def test_all_command_groups_importable(self):
        """Test all command groups can be imported"""
        from cli_anything.firefly_iii.core import (
            accounts, transactions, budgets, categories, tags,
            bills, piggy_banks, insights, search, export, info,
            autocomplete, currencies, recurrences, rules,
            rule_groups, summary, webhooks
        )

        assert accounts is not None
        assert transactions is not None
        assert budgets is not None
        assert categories is not None
        assert tags is not None
        assert bills is not None
        assert piggy_banks is not None
        assert insights is not None
        assert search is not None
        assert export is not None
        assert info is not None
        assert autocomplete is not None
        assert currencies is not None
        assert recurrences is not None
        assert rules is not None
        assert rule_groups is not None
        assert summary is not None
        assert webhooks is not None

    def test_cli_has_all_commands(self):
        """Test CLI has all expected commands registered"""
        from cli_anything.firefly_iii.firefly_iii_cli import cli

        expected_commands = [
            'accounts', 'transactions', 'budgets', 'categories', 'tags',
            'bills', 'piggy-banks', 'insights', 'search', 'export', 'info',
            'autocomplete', 'currencies', 'recurrences', 'rules',
            'rule-groups', 'summary', 'webhooks'
        ]

        for cmd in expected_commands:
            assert cmd in cli.commands, f"Command '{cmd}' not registered"


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


class TestCLIClick:
    """Test CLI structure with Click"""

    def test_cli_is_click_group(self):
        """Test CLI is a Click group"""
        from click import Group
        from cli_anything.firefly_iii.firefly_iii_cli import cli

        assert isinstance(cli, Group)

    def test_subcommands_are_click_groups(self):
        """Test subcommands are Click groups"""
        from click import Group
        from cli_anything.firefly_iii.firefly_iii_cli import cli

        # Get commands from the CLI group
        accounts = cli.commands.get('accounts')
        transactions = cli.commands.get('transactions')
        budgets = cli.commands.get('budgets')

        assert accounts is not None
        assert transactions is not None
        assert budgets is not None
        assert isinstance(accounts, Group)
        assert isinstance(transactions, Group)
        assert isinstance(budgets, Group)

    def test_accounts_subcommands(self):
        """Test accounts has expected subcommands"""
        from cli_anything.firefly_iii.core.accounts import accounts

        expected = ['list', 'get', 'create', 'update', 'delete']
        for cmd in expected:
            assert cmd in accounts.commands, f"accounts.{cmd} not found"

    def test_transactions_subcommands(self):
        """Test transactions has expected subcommands"""
        from cli_anything.firefly_iii.core.transactions import transactions

        expected = ['list', 'get', 'create', 'update', 'delete']
        for cmd in expected:
            assert cmd in transactions.commands, f"transactions.{cmd} not found"

    def test_budgets_subcommands(self):
        """Test budgets has expected subcommands"""
        from cli_anything.firefly_iii.core.budgets import budgets

        expected = ['list', 'get', 'create', 'update', 'delete', 'limits', 'limit-create', 'limit-update', 'limit-delete']
        for cmd in expected:
            assert cmd in budgets.commands, f"budgets.{cmd} not found"

    def test_autocomplete_subcommands(self):
        """Test autocomplete has expected subcommands"""
        from cli_anything.firefly_iii.core.autocomplete import autocomplete

        expected = [
            'accounts', 'bills', 'budgets', 'categories', 'currencies',
            'piggy-banks', 'tags', 'transactions', 'rule-groups', 'rules',
            'recurring', 'object-groups', 'transaction-types'
        ]
        for cmd in expected:
            assert cmd in autocomplete.commands, f"autocomplete.{cmd} not found"

    def test_rules_subcommands(self):
        """Test rules has expected subcommands"""
        from cli_anything.firefly_iii.core.rules import rules

        expected = ['list', 'get', 'create', 'update', 'delete', 'test', 'execute']
        for cmd in expected:
            assert cmd in rules.commands, f"rules.{cmd} not found"

    def test_webhooks_subcommands(self):
        """Test webhooks has expected subcommands"""
        from cli_anything.firefly_iii.core.webhooks import webhooks

        expected = ['list', 'get', 'create', 'update', 'delete', 'trigger']
        for cmd in expected:
            assert cmd in webhooks.commands, f"webhooks.{cmd} not found"
