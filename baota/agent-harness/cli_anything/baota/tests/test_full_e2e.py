import os
import sys
import json
import subprocess
import unittest


HARNESS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..')
CLI_MODULE = '-m cli_anything.baota.baota_cli'


def _resolve_cli(name):
    if os.environ.get('CLI_ANYTHING_FORCE_INSTALLED') == '1':
        result = subprocess.run(['which', name], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    return sys.executable + ' ' + CLI_MODULE


class TestCLISubprocess(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cli_cmd = _resolve_cli('cli-anything-baota')
        cls.env = os.environ.copy()
        cls.env['CLI_ANYTHING_FORCE_INSTALLED'] = '1'
        cls.env['PYTHONPATH'] = HARNESS_DIR

    def _run_cli(self, *args):
        if self.cli_cmd.startswith('/') or ' ' in self.cli_cmd:
            full_cmd = self.cli_cmd.split() + list(args)
        else:
            full_cmd = [self.cli_cmd] + list(args)
        result = subprocess.run(full_cmd, capture_output=True, text=True, env=self.env, timeout=30)
        return result

    def test_help(self):
        result = self._run_cli('--help')
        self.assertEqual(result.returncode, 0)
        self.assertIn('Usage:', result.stdout)

    def test_subcommand_help(self):
        result = self._run_cli('sites', '--help')
        self.assertEqual(result.returncode, 0)
        self.assertIn('Usage:', result.stdout)

    def test_system_help(self):
        result = self._run_cli('system', '--help')
        self.assertEqual(result.returncode, 0)
        self.assertIn('Usage:', result.stdout)

    def test_json_version_enabled(self):
        result = self._run_cli('--json', 'sites', 'list')
        self.assertEqual(result.returncode, 0)

    def test_json_output_flag(self):
        result = self._run_cli('--json', 'config', 'show')
        self.assertEqual(result.returncode, 0)

    def test_json_with_system_status(self):
        result = self._run_cli('--json', 'system', 'status')
        self.assertEqual(result.returncode, 0)

    def test_invalid_command(self):
        result = self._run_cli('nonexistent')
        self.assertNotEqual(result.returncode, 0)

    def test_invalid_option(self):
        result = self._run_cli('sites', 'list', '--bogus')
        self.assertNotEqual(result.returncode, 0)

    def test_help_output_contains_sites(self):
        result = self._run_cli('--help')
        self.assertIn('sites', result.stdout)

    def test_help_output_contains_system(self):
        result = self._run_cli('--help')
        self.assertIn('system', result.stdout)

    def test_json_flag_on_help(self):
        result = self._run_cli('--json', '--help')
        self.assertEqual(result.returncode, 0)
        self.assertIn('Usage:', result.stdout)


class TestE2EFull(unittest.TestCase):

    def _run_as_module(self, *args):
        env = os.environ.copy()
        env['PYTHONPATH'] = HARNESS_DIR
        return subprocess.run(
            [sys.executable, '-m', 'cli_anything.baota.baota_cli'] + list(args),
            capture_output=True, text=True, env=env, timeout=30
        )

    def test_help_output(self):
        result = self._run_as_module('--help')
        self.assertIn('Usage:', result.stdout)

    def test_json_output_parses(self):
        result = self._run_as_module('--json', 'system', 'status')
        if result.stdout.strip():
            try:
                parsed = json.loads(result.stdout.strip())
                self.assertIn('data', parsed)
            except json.JSONDecodeError:
                self.fail('JSON output did not parse')

    def test_help_contains_json_flag(self):
        result = self._run_as_module('--help')
        self.assertIn('--json', result.stdout)

    def test_databases_help(self):
        result = self._run_as_module('databases', '--help')
        self.assertIn('Usage:', result.stdout)

    def test_files_help(self):
        result = self._run_as_module('files', '--help')
        self.assertIn('Usage:', result.stdout)

    def test_export_help(self):
        result = self._run_as_module('export', '--help')
        self.assertIn('Usage:', result.stdout)

    def test_sites_help(self):
        result = self._run_as_module('sites', '--help')
        self.assertIn('Usage:', result.stdout)

    def test_config_help(self):
        result = self._run_as_module('config', '--help')
        self.assertIn('Usage:', result.stdout)

    def test_cron_help(self):
        result = self._run_as_module('cron', '--help')
        self.assertIn('Usage:', result.stdout)

    def test_cron_check_le_help(self):
        result = self._run_as_module('cron', 'check-le', '--help')
        self.assertIn('Usage:', result.stdout)

    def test_cron_ensure_le_help(self):
        result = self._run_as_module('cron', 'ensure-le', '--help')
        self.assertIn('Usage:', result.stdout)

    def test_ssl_deploy_help(self):
        result = self._run_as_module('sites', 'ssl', 'deploy', '--help')
        self.assertIn('Usage:', result.stdout)

    def test_sites_set_port_help(self):
        result = self._run_as_module('sites', 'set-port', '--help')
        self.assertIn('Usage:', result.stdout)

    def test_dns_record_help(self):
        result = self._run_as_module('config', 'dns', 'record', '--help')
        self.assertIn('Usage:', result.stdout)

    def test_dns_record_add_help(self):
        result = self._run_as_module('config', 'dns', 'record', 'add', '--help')
        self.assertIn('Usage:', result.stdout)

    def test_dns_record_list_help(self):
        result = self._run_as_module('config', 'dns', 'record', 'list', '--help')
        self.assertIn('Usage:', result.stdout)

    def test_dns_record_delete_help(self):
        result = self._run_as_module('config', 'dns', 'record', 'delete', '--help')
        self.assertIn('Usage:', result.stdout)

    def test_system_network_help(self):
        result = self._run_as_module('system', 'network', '--help')
        self.assertIn('Usage:', result.stdout)

    def test_system_firewall_list_help(self):
        result = self._run_as_module('system', 'firewall-list', '--help')
        self.assertIn('Usage:', result.stdout)

    def test_system_firewall_delete_help(self):
        result = self._run_as_module('system', 'firewall-delete', '--help')
        self.assertIn('Usage:', result.stdout)

    def test_ssl_info_help(self):
        result = self._run_as_module('sites', 'ssl', 'info', '--help')
        self.assertIn('Usage:', result.stdout)

    def test_ssl_close_help(self):
        result = self._run_as_module('sites', 'ssl', 'close', '--help')
        self.assertIn('Usage:', result.stdout)

    def test_bt_help(self):
        result = self._run_as_module('bt', '--help')
        self.assertIn('Usage:', result.stdout)
        self.assertIn('重启面板', result.stdout)

    def test_bt_14(self):
        result = self._run_as_module('bt', '14')
        self.assertIn('BT-Panel', result.stdout)

    def test_bt_raw_help(self):
        result = self._run_as_module('bt', 'raw', '--help')
        self.assertIn('Usage:', result.stdout)


if __name__ == '__main__':
    unittest.main()
