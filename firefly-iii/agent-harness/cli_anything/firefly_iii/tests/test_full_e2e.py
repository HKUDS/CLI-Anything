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
        assert 'attributes' in result['data']

    def test_accounts_list(self, backend):
        """Test getting account list"""
        result = backend.get_accounts()

        assert 'data' in result
        assert isinstance(result['data'], list)

    def test_transactions_list(self, backend):
        """Test getting transaction list"""
        result = backend.get_transactions()

        assert 'data' in result
        assert isinstance(result['data'], list)

    def test_budgets_list(self, backend):
        """Test getting budget list"""
        result = backend.get_budgets()

        assert 'data' in result
        assert isinstance(result['data'], list)

    def test_insights(self, backend):
        """Test insight reports"""
        result = backend.get_insight('expense/category', {
            'start': '2024-01-01',
            'end': '2024-01-31'
        })

        assert 'data' in result


@skip_e2e
class TestCLIE2E:
    """CLI end-to-end tests"""

    def test_cli_about(self):
        """Test CLI about command"""
        result = subprocess.run(
            ['cli-anything-firefly-iii', '--json', 'info', 'about'],
            capture_output=True,
            text=True,
            env={**os.environ, 'FIREFLY_III_BASE_URL': os.environ.get('FIREFLY_III_BASE_URL', ''),
                 'FIREFLY_III_PAT': os.environ.get('FIREFLY_III_PAT', '')}
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)
            assert 'data' in data

    def test_cli_accounts_list(self):
        """Test CLI accounts list command"""
        result = subprocess.run(
            ['cli-anything-firefly-iii', '--json', 'accounts', 'list'],
            capture_output=True,
            text=True,
            env={**os.environ, 'FIREFLY_III_BASE_URL': os.environ.get('FIREFLY_III_BASE_URL', ''),
                 'FIREFLY_III_PAT': os.environ.get('FIREFLY_III_PAT', '')}
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)
            assert 'data' in data

    def test_cli_transactions_list(self):
        """Test CLI transactions list command"""
        result = subprocess.run(
            ['cli-anything-firefly-iii', '--json', 'transactions', 'list', '--limit', '5'],
            capture_output=True,
            text=True,
            env={**os.environ, 'FIREFLY_III_BASE_URL': os.environ.get('FIREFLY_III_BASE_URL', ''),
                 'FIREFLY_III_PAT': os.environ.get('FIREFLY_III_PAT', '')}
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)
            assert 'data' in data
