import sys
import subprocess
from unittest.mock import patch
from click.testing import CliRunner
import cli_anything.intelwatch.intelwatch_cli as intelwatch_cli
import unittest

class TestIntelwatchCli(unittest.TestCase):
    def test_argument_forwarding(self):
        """Test that arguments are correctly forwarded to subprocess.call."""
        runner = CliRunner()
        
        with patch('cli_anything.intelwatch.intelwatch_cli.subprocess.call') as mock_call, \
             patch('cli_anything.intelwatch.intelwatch_cli.sys.exit') as mock_exit:
            
            mock_call.return_value = 0
            
            # Use standalone_mode=False to avoid click's internal sys.exit() catching
            result = runner.invoke(intelwatch_cli.main, ['--query', 'recognity', '--format', 'json'], standalone_mode=False)
            
            mock_call.assert_called_once_with(['npx', 'intelwatch', '--query', 'recognity', '--format', 'json'])
            mock_exit.assert_called_once_with(0)

    def test_exit_code_propagation(self):
        """Test that non-zero exit codes are correctly propagated."""
        runner = CliRunner()
        
        with patch('cli_anything.intelwatch.intelwatch_cli.subprocess.call') as mock_call, \
             patch('cli_anything.intelwatch.intelwatch_cli.sys.exit') as mock_exit:
            
            mock_call.return_value = 2
            
            runner.invoke(intelwatch_cli.main, ['invalid-command'], standalone_mode=False)
            
            mock_exit.assert_called_once_with(2)

    def test_npx_not_found(self):
        """Test behavior when npx is not installed (FileNotFoundError)."""
        runner = CliRunner()
        
        with patch('cli_anything.intelwatch.intelwatch_cli.subprocess.call') as mock_call, \
             patch('cli_anything.intelwatch.intelwatch_cli.sys.exit') as mock_exit:
            
            mock_call.side_effect = FileNotFoundError()
            
            result = runner.invoke(intelwatch_cli.main, [], standalone_mode=False)
            
            self.assertIn("Error: 'npx' command not found", result.output)
            mock_exit.assert_called_once_with(1)

if __name__ == '__main__':
    unittest.main()
