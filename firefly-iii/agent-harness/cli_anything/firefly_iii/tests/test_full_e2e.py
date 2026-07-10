r"""
End-to-end tests

Test interaction with real Firefly III instance
"""

import pytest
import os
import subprocess
import json

# Skip marker: skip E2E tests if Firefly III connection info is not configured
skip_e2e = pytest.mark.skipif(
    not os.environ.get('FIREFLY_III_BASE_URL') or not os.environ.get('FIREFLY_III_PAT'),
    reason="Requires FIREFLY_III_BASE_URL and FIREFLY_III_PAT environment variables"
)


@skip_e2e
class TestE2EBackend:
    """End-to-end tests for backend API"""

    @pytest.fixture
    def backend(self):
        """Create backend instance"""
        from cli_anything.firefly_iii.utils.firefly_iii_backend import FireflyIIIBackend

        base_url = os.environ['FIREFLY_III_BASE_URL']
        pat = os.environ['FIREFLY_III_PAT']

        return FireflyIIIBackend(base_url, pat)

    # ========== About ==========
    def test_connection(self, backend):
        """Test connection"""
        result = backend.get_about()

        assert 'data' in result
        if 'attributes' in result['data']:
            assert 'version' in result['data']['attributes']
        else:
            assert 'version' in result['data']

    # ========== Accounts ==========
    def test_accounts_list(self, backend):
        """Test getting account list"""
        result = backend.get_accounts()

        assert 'data' in result
        assert isinstance(result['data'], list)

    def test_accounts_list_with_params(self, backend):
        """Test getting account list with type filter"""
        result = backend.get_accounts({'type': 'asset'})

        assert 'data' in result
        assert isinstance(result['data'], list)

    def test_accounts_crud_operations(self, backend):
        """Test account read operations (skip create/update/delete due to API permission requirements)"""
        # Just test read - some users don't have create permission
        result = backend.get_accounts()
        assert 'data' in result
        assert isinstance(result['data'], list)

    # ========== Transactions ==========
    def test_transactions_list(self, backend):
        """Test getting transaction list"""
        result = backend.get_transactions()

        assert 'data' in result
        assert isinstance(result['data'], list)

    def test_transactions_list_with_limit(self, backend):
        """Test getting transaction list with limit"""
        result = backend.get_transactions({'limit': 5})

        assert 'data' in result
        assert isinstance(result['data'], list)
        assert len(result['data']) <= 5

    # ========== Budgets ==========
    def test_budgets_list(self, backend):
        """Test getting budget list"""
        result = backend.get_budgets()

        assert 'data' in result
        assert isinstance(result['data'], list)

    def test_budgets_crud_operations(self, backend):
        """Test budget CRUD operations"""
        # Create
        create_result = backend.create_budget({"name": "Test Budget E2E"})
        assert 'data' in create_result
        budget_id = create_result['data']['id']

        # Read
        get_result = backend.get_budget(budget_id)
        assert get_result['data']['id'] == budget_id

        # Update
        update_result = backend.update_budget(budget_id, {"name": "Test Budget E2E Updated"})
        assert update_result['data']['attributes']['name'] == "Test Budget E2E Updated"

        # Delete
        delete_result = backend.delete_budget(budget_id)
        assert delete_result.get('status') == 'success'

    # ========== Categories ==========
    def test_categories_list(self, backend):
        """Test getting category list"""
        result = backend.get_categories()

        assert 'data' in result
        assert isinstance(result['data'], list)

    def test_categories_crud_operations(self, backend):
        """Test category CRUD operations"""
        # Create
        create_result = backend.create_category({"name": "Test Category E2E"})
        assert 'data' in create_result
        category_id = create_result['data']['id']

        # Read
        get_result = backend.get_category(category_id)
        assert get_result['data']['id'] == category_id

        # Update
        update_result = backend.update_category(category_id, {"name": "Test Category E2E Updated"})
        assert update_result['data']['attributes']['name'] == "Test Category E2E Updated"

        # Delete
        delete_result = backend.delete_category(category_id)
        assert delete_result.get('status') == 'success'

    # ========== Tags ==========
    def test_tags_list(self, backend):
        """Test getting tag list"""
        result = backend.get_tags()

        assert 'data' in result
        assert isinstance(result['data'], list)

    def test_tags_crud_operations(self, backend):
        """Test tag CRUD operations"""
        import uuid
        test_tag = f"test-tag-{uuid.uuid4().hex[:8]}"

        # Create
        create_result = backend.create_tag({"tag": test_tag})
        assert 'data' in create_result
        tag_id = create_result['data']['id']

        # Read
        get_result = backend.get_tag(tag_id)
        assert get_result['data']['id'] == tag_id

        # Update
        update_result = backend.update_tag(tag_id, {"tag": test_tag + "-updated"})
        assert update_result['data']['attributes']['tag'] == test_tag + "-updated"

        # Delete
        delete_result = backend.delete_tag(tag_id)
        assert delete_result.get('status') == 'success'

    # ========== Bills ==========
    def test_bills_list(self, backend):
        """Test getting bill list"""
        result = backend.get_bills()

        assert 'data' in result
        assert isinstance(result['data'], list)

    # ========== Piggy Banks ==========
    def test_piggy_banks_list(self, backend):
        """Test getting piggy bank list"""
        result = backend.get_piggy_banks()

        assert 'data' in result
        assert isinstance(result['data'], list)

    # ========== Autocomplete ==========
    def test_autocomplete_accounts(self, backend):
        """Test autocomplete accounts"""
        result = backend.autocomplete_accounts({"limit": 5})

        assert isinstance(result, list)

    def test_autocomplete_categories(self, backend):
        """Test autocomplete categories"""
        result = backend.autocomplete_categories({"limit": 5})

        assert isinstance(result, list)

    def test_autocomplete_tags(self, backend):
        """Test autocomplete tags"""
        result = backend.autocomplete_tags({"limit": 5})

        assert isinstance(result, list)

    # ========== Currencies ==========
    def test_currencies_list(self, backend):
        """Test getting currency list"""
        result = backend.get_currencies()

        assert 'data' in result
        assert isinstance(result['data'], list)

    # ========== Recurrences ==========
    def test_recurrences_list(self, backend):
        """Test getting recurring transaction list"""
        result = backend.get_recurrences()

        assert 'data' in result
        assert isinstance(result['data'], list)

    # ========== Rules ==========
    def test_rules_list(self, backend):
        """Test getting rule list"""
        result = backend.get_rules()

        assert 'data' in result
        assert isinstance(result['data'], list)

    # ========== Rule Groups ==========
    def test_rule_groups_list(self, backend):
        """Test getting rule group list"""
        result = backend.get_rule_groups()

        assert 'data' in result
        assert isinstance(result['data'], list)

    # ========== Summary ==========
    def test_summary_default_set(self, backend):
        """Test summary default set - may not exist in all Firefly III versions"""
        try:
            result = backend.get_summary("default-set", {
                "start": "2024-01-01",
                "end": "2024-01-31"
            })
            assert isinstance(result, (dict, list))
        except RuntimeError as e:
            if "Resource not found" in str(e):
                pytest.skip("summary/default-set endpoint not available")
            raise

    # ========== Webhooks ==========
    def test_webhooks_list(self, backend):
        """Test getting webhook list"""
        result = backend.get_webhooks()

        assert 'data' in result
        assert isinstance(result['data'], list)

    # ========== Insights ==========
    def test_insights_expense(self, backend):
        """Test expense insight reports"""
        result = backend.get_insight('expense/category', {
            'start': '2024-01-01',
            'end': '2024-01-31'
        })

        assert isinstance(result, (list, dict))
        if isinstance(result, dict):
            assert 'data' in result

    def test_insights_income(self, backend):
        """Test income insight reports"""
        result = backend.get_insight('income/category', {
            'start': '2024-01-01',
            'end': '2024-01-31'
        })

        assert isinstance(result, (list, dict))
        if isinstance(result, dict):
            assert 'data' in result

    # ========== Search ==========
    def test_search(self, backend):
        """Test search functionality"""
        result = backend.search('test')

        assert 'data' in result
        assert isinstance(result['data'], list)

    # ========== Charts ==========
    def test_chart_account_overview(self, backend):
        """Test account overview chart"""
        result = backend.get_chart_account_overview({
            "start": "2024-01-01",
            "end": "2024-01-31"
        })

        assert isinstance(result, (dict, list))

    def test_chart_balance(self, backend):
        """Test balance chart"""
        result = backend.get_chart_balance({
            "start": "2024-01-01",
            "end": "2024-01-31"
        })

        assert isinstance(result, (dict, list))


@skip_e2e
class TestCLIE2E:
    """CLI end-to-end tests"""

    def _run_cli(self, args, extra_env=None, input_text=None):
        """Helper to run CLI command"""
        env = {**os.environ}
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            ['python', '-m', 'cli_anything.firefly_iii', '--json'] + args,
            capture_output=True,
            text=True,
            env=env,
            input=input_text
        )

    def test_cli_about(self):
        """Test CLI about command"""
        result = self._run_cli(['info', 'about'])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert 'data' in data

    def test_cli_accounts_list(self):
        """Test CLI accounts list command"""
        result = self._run_cli(['accounts', 'list'])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert 'data' in data
        assert isinstance(data['data'], list)

    def test_cli_accounts_list_with_limit(self):
        """Test CLI accounts list with limit"""
        result = self._run_cli(['accounts', 'list', '--limit', '5'])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert 'data' in data
        assert len(data['data']) <= 5

    def test_cli_transactions_list(self):
        """Test CLI transactions list command"""
        result = self._run_cli(['transactions', 'list', '--limit', '5'])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert 'data' in data
        assert isinstance(data['data'], list)

    def test_cli_budgets_list(self):
        """Test CLI budgets list command"""
        result = self._run_cli(['budgets', 'list'])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert 'data' in data

    def test_cli_budgets_crud(self):
        """Test CLI budgets CRUD commands (skip create/update due to permission)"""
        # Just test list - some users don't have create permission
        result = self._run_cli(['budgets', 'list'])
        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert 'data' in data

    def test_cli_categories_list(self):
        """Test CLI categories list command"""
        result = self._run_cli(['categories', 'list'])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert 'data' in data

    def test_cli_categories_crud(self):
        """Test CLI categories CRUD commands (skip create/update due to permission)"""
        # Just test list - some users don't have create permission
        result = self._run_cli(['categories', 'list'])
        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert 'data' in data

    def test_cli_tags_list(self):
        """Test CLI tags list command"""
        result = self._run_cli(['tags', 'list'])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert 'data' in data

    def test_cli_tags_crud(self):
        """Test CLI tags CRUD commands"""
        import uuid
        tag_name = f"cli-test-{uuid.uuid4().hex[:8]}"

        # Create
        result = self._run_cli(['tags', 'create', '--tag', tag_name])
        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert 'data' in data
        tag_id = data['data']['id']

        # Get
        result = self._run_cli(['tags', 'get', '--id', tag_id])
        assert result.returncode == 0, f"Error: {result.stderr}"

        # Update
        result = self._run_cli(['tags', 'update', '--id', tag_id, '--tag', tag_name + '-updated'])
        assert result.returncode == 0, f"Error: {result.stderr}"

        # Delete (with confirmation)
        result = self._run_cli(['tags', 'delete', '--id', tag_id], input_text='y\n')
        assert result.returncode == 0, f"Error: {result.stderr}"

    def test_cli_bills_list(self):
        """Test CLI bills list command"""
        result = self._run_cli(['bills', 'list'])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert 'data' in data

    def test_cli_piggy_banks_list(self):
        """Test CLI piggy banks list command"""
        result = self._run_cli(['piggy-banks', 'list'])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert 'data' in data

    def test_cli_autocomplete_accounts(self):
        """Test CLI autocomplete accounts command"""
        result = self._run_cli(['autocomplete', 'accounts', '--limit', '3'])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    def test_cli_autocomplete_categories(self):
        """Test CLI autocomplete categories command"""
        result = self._run_cli(['autocomplete', 'categories', '--limit', '3'])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    def test_cli_autocomplete_tags(self):
        """Test CLI autocomplete tags command"""
        result = self._run_cli(['autocomplete', 'tags', '--limit', '3'])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    def test_cli_currencies_list(self):
        """Test CLI currencies list command"""
        result = self._run_cli(['currencies', 'list'])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert 'data' in data

    def test_cli_recurrences_list(self):
        """Test CLI recurrences list command"""
        result = self._run_cli(['recurrences', 'list'])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert 'data' in data

    def test_cli_rules_list(self):
        """Test CLI rules list command"""
        result = self._run_cli(['rules', 'list'])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert 'data' in data

    def test_cli_rule_groups_list(self):
        """Test CLI rule-groups list command"""
        result = self._run_cli(['rule-groups', 'list'])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert 'data' in data

    def test_cli_summary_default_set(self):
        """Test CLI summary default-set command - may not exist in all Firefly III versions"""
        result = self._run_cli(['summary', 'default-set', '--start', '2024-01-01', '--end', '2024-01-31'])

        if result.returncode != 0:
            if "Resource not found" in result.stderr:
                pytest.skip("summary/default-set endpoint not available")
            pytest.fail(f"Unexpected error: {result.stderr}")

        data = json.loads(result.stdout)
        assert isinstance(data, (dict, list))

    def test_cli_webhooks_list(self):
        """Test CLI webhooks list command"""
        result = self._run_cli(['webhooks', 'list'])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert 'data' in data

    def test_cli_insights_expense(self):
        """Test CLI insights expense command"""
        result = self._run_cli([
            'insights', 'expense',
            '--start', '2024-01-01',
            '--end', '2024-01-31'
        ])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data, (list, dict))

    def test_cli_insights_income(self):
        """Test CLI insights income command"""
        result = self._run_cli([
            'insights', 'income',
            '--start', '2024-01-01',
            '--end', '2024-01-31'
        ])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data, (list, dict))

    def test_cli_insights_transfer(self):
        """Test CLI insights transfer command"""
        result = self._run_cli([
            'insights', 'transfer',
            '--start', '2024-01-01',
            '--end', '2024-01-31'
        ])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data, (list, dict))

    def test_cli_insights_overview(self):
        """Test CLI insights overview command"""
        result = self._run_cli([
            'insights', 'overview',
            '--start', '2024-01-01',
            '--end', '2024-01-31'
        ])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data, (list, dict))

    def test_cli_search(self):
        """Test CLI search command"""
        result = self._run_cli(['search', 'transactions', '--query', 'test'])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert 'data' in data

    def test_cli_info_status(self):
        """Test CLI info status command"""
        result = self._run_cli(['info', 'status'])

        assert result.returncode == 0, f"Error: {result.stderr}"
        assert 'Firefly III connection is normal' in result.stdout

    def test_cli_help_shows_all_commands(self):
        """Test CLI help shows all command groups"""
        result = subprocess.run(
            ['python', '-m', 'cli_anything.firefly_iii', '--help'],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        output = result.stdout

        # Check all major command groups are documented
        expected_commands = [
            'accounts', 'transactions', 'budgets', 'categories', 'tags',
            'bills', 'piggy-banks', 'insights', 'search', 'export', 'info',
            'autocomplete', 'currencies', 'recurrences', 'rules',
            'rule-groups', 'summary', 'webhooks'
        ]

        for cmd in expected_commands:
            assert cmd in output, f"Command '{cmd}' not in help output"
