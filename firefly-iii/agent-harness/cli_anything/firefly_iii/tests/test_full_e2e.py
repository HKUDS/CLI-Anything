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
class TestE2E:
    """End-to-end tests"""

    @pytest.fixture
    def backend(self):
        """Create backend instance"""
        from cli_anything.firefly_iii.utils.firefly_iii_backend import FireflyIIIBackend

        base_url = os.environ['FIREFLY_III_BASE_URL']
        pat = os.environ['FIREFLY_III_PAT']

        return FireflyIIIBackend(base_url, pat)

    def test_connection(self, backend):
        """Test connection"""
        result = backend.get_about()

        assert 'data' in result
        # Firefly III API returns data directly or nested in attributes
        if 'attributes' in result['data']:
            assert 'version' in result['data']['attributes']
        else:
            assert 'version' in result['data']

    def test_accounts_list(self, backend):
        """Test getting account list"""
        result = backend.get_accounts()

        assert 'data' in result
        assert isinstance(result['data'], list)
        if len(result['data']) > 0:
            assert 'attributes' in result['data'][0]

    def test_accounts_list_with_params(self, backend):
        """Test getting account list with type filter"""
        result = backend.get_accounts({'type': 'asset'})

        assert 'data' in result
        assert isinstance(result['data'], list)

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

    def test_budgets_list(self, backend):
        """Test getting budget list"""
        result = backend.get_budgets()

        assert 'data' in result
        assert isinstance(result['data'], list)

    def test_categories_list(self, backend):
        """Test getting category list"""
        result = backend.get_categories()

        assert 'data' in result
        assert isinstance(result['data'], list)

    def test_tags_list(self, backend):
        """Test getting tag list"""
        result = backend.get_tags()

        assert 'data' in result
        assert isinstance(result['data'], list)

    def test_bills_list(self, backend):
        """Test getting bill list"""
        result = backend.get_bills()

        assert 'data' in result
        assert isinstance(result['data'], list)

    def test_piggy_banks_list(self, backend):
        """Test getting piggy bank list"""
        result = backend.get_piggy_banks()

        assert 'data' in result
        assert isinstance(result['data'], list)

    def test_insights_expense(self, backend):
        """Test expense insight reports"""
        result = backend.get_insight('expense/category', {
            'start': '2024-01-01',
            'end': '2024-01-31'
        })

        # Insights API may return empty list or {data: [...]}
        assert isinstance(result, (list, dict))
        if isinstance(result, dict):
            assert 'data' in result

    def test_insights_income(self, backend):
        """Test income insight reports"""
        result = backend.get_insight('income/category', {
            'start': '2024-01-01',
            'end': '2024-01-31'
        })

        # Insights API may return empty list or {data: [...]}
        assert isinstance(result, (list, dict))
        if isinstance(result, dict):
            assert 'data' in result

    def test_search(self, backend):
        """Test search functionality"""
        result = backend.search('test')

        assert 'data' in result
        assert isinstance(result['data'], list)


@skip_e2e
class TestCLIE2E:
    """CLI end-to-end tests"""

    def _run_cli(self, args):
        """Helper to run CLI command"""
        return subprocess.run(
            ['python', '-m', 'cli_anything.firefly_iii', '--json'] + args,
            capture_output=True,
            text=True,
            env={**os.environ}
        )

    def test_cli_about(self):
        """Test CLI about command"""
        result = self._run_cli(['info', 'about'])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        assert 'data' in data
        # Firefly III API returns data directly or nested in attributes
        if 'attributes' in data['data']:
            assert 'version' in data['data']['attributes']
        else:
            assert 'version' in data['data']

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

    def test_cli_categories_list(self):
        """Test CLI categories list command"""
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

    def test_cli_insights_expense(self):
        """Test CLI insights expense command"""
        result = self._run_cli([
            'insights', 'expense',
            '--start', '2024-01-01',
            '--end', '2024-01-31'
        ])

        assert result.returncode == 0, f"Error: {result.stderr}"
        data = json.loads(result.stdout)
        # Insights API may return empty list or {data: [...]}
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert 'data' in data

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
