import subprocess
import sys
import unittest
from unittest.mock import patch
from click.testing import CliRunner
import cli_anything.intelwatch.intelwatch_cli as intelwatch_cli

class TestE2E(unittest.TestCase):
    def test_e2e_harness(self):
        """E2E test simulation.
        
        This simulates an end-to-end run without actually hitting the network
        or requiring npx installed in the CI environment.
        """
        runner = CliRunner()
        
        with patch('cli_anything.intelwatch.intelwatch_cli.subprocess.call') as mock_call, \
             patch('cli_anything.intelwatch.intelwatch_cli.sys.exit') as mock_exit:
            
            # Simulate a successful call
            mock_call.return_value = 0
            
            # Run a simulated query
            result = runner.invoke(intelwatch_cli.main, ['--domain', 'recognity.fr', '--format', 'json'], standalone_mode=False)
            
            # Verify the integration points
            mock_call.assert_called_once_with(['npx', 'intelwatch', '--domain', 'recognity.fr', '--format', 'json'])
            mock_exit.assert_called_once_with(0)

if __name__ == '__main__':
    unittest.main()
