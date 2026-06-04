import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from cli_anything.baota.core import project, session, database, files, config as config_module, export, cron as cron_module, bt as bt_module
from cli_anything.baota.utils.helpers import format_output, output_json, output_text


class TestHelpers(unittest.TestCase):

    def test_output_json_dict(self):
        result = output_json({'name': 'test', 'value': 123})
        parsed = json.loads(result)
        self.assertTrue(parsed['status'])
        self.assertEqual(parsed['data']['name'], 'test')

    def test_output_json_with_msg(self):
        result = output_json({'ok': True}, msg='Success')
        parsed = json.loads(result)
        self.assertEqual(parsed['msg'], 'Success')

    def test_output_text_dict(self):
        result = output_text({'key': 'value'}, 'Title')
        self.assertIn('Title', result)
        self.assertIn('key: value', result)

    def test_output_text_list(self):
        result = output_text([{'a': 1}, {'b': 2}], 'List')
        self.assertIn('List', result)
        self.assertIn('a: 1', result)

    def test_format_output_json(self):
        result = format_output({'status': True}, use_json=True)
        parsed = json.loads(result)
        self.assertTrue(parsed['status'])

    def test_format_output_text(self):
        result = format_output({'key': 'val'}, use_json=False)
        self.assertIn('key: val', result)


class TestProject(unittest.TestCase):

    @patch('cli_anything.baota.core.project.call_bridge')
    def test_list_sites(self, mock_bridge):
        mock_bridge.return_value = [{'id': 1, 'name': 'test.com'}]
        result = project.list_sites(use_json=True)
        parsed = json.loads(result)
        self.assertTrue(parsed['status'])
        self.assertEqual(len(parsed['data']), 1)

    @patch('cli_anything.baota.core.project.call_bridge')
    def test_set_site_port(self, mock_bridge):
        mock_bridge.return_value = {'status': True, 'msg': 'port updated'}
        result = project.set_site_port(1, '802', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)
        mock_bridge.assert_called_with('set_site_port', site_id=1, port='802')

    @patch('cli_anything.baota.core.project.call_bridge')
    def test_set_site_port_error(self, mock_bridge):
        mock_bridge.side_effect = RuntimeError('fail')
        result = project.set_site_port(999, '999', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.project.call_bridge')
    def test_list_sites_error(self, mock_bridge):
        mock_bridge.side_effect = RuntimeError('Bridge error')
        result = project.list_sites(use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.project.call_bridge')
    def test_get_site_info(self, mock_bridge):
        mock_bridge.return_value = {'id': 1, 'name': 'test.com', 'domains': []}
        result = project.get_site_info(1, use_json=True)
        parsed = json.loads(result)
        self.assertTrue(parsed['status'])

    @patch('cli_anything.baota.core.project.call_bridge')
    def test_create_site(self, mock_bridge):
        mock_bridge.return_value = {'status': True, 'msg': 'created'}
        result = project.create_site('test.com', '/tmp/test', use_json=True)
        parsed = json.loads(result)
        self.assertTrue(parsed['status'])

    @patch('cli_anything.baota.core.project.call_bridge')
    def test_create_site_error(self, mock_bridge):
        mock_bridge.side_effect = RuntimeError('fail')
        result = project.create_site('test.com', '/tmp/test', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.project.call_bridge')
    def test_delete_site(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = project.delete_site(999, use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.project.call_bridge')
    def test_apply_ssl(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = project.apply_ssl(1, use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.project.call_bridge')
    def test_get_ssl_info(self, mock_bridge):
        mock_bridge.return_value = {'status': True, 'domain': ['test.com']}
        result = project.get_ssl_info(1, use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)
        self.assertEqual(parsed['data']['domain'][0], 'test.com')

    @patch('cli_anything.baota.core.project.call_bridge')
    def test_get_ssl_info_error(self, mock_bridge):
        mock_bridge.side_effect = RuntimeError('fail')
        result = project.get_ssl_info(99, use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.project.call_bridge')
    def test_close_ssl(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = project.close_ssl(1, use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.project.call_bridge')
    def test_close_ssl_error(self, mock_bridge):
        mock_bridge.side_effect = RuntimeError('fail')
        result = project.close_ssl(99, use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.project.call_bridge')
    def test_stop_site(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = project.stop_site(1, use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.project.call_bridge')
    def test_list_domains(self, mock_bridge):
        mock_bridge.return_value = [{'id': 1, 'name': 'sub.test.com'}]
        result = project.list_domains(1, use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.project.call_bridge')
    def test_add_domain(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = project.add_domain(1, 'sub.test.com', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)


class TestSession(unittest.TestCase):

    @patch('cli_anything.baota.core.session.call_bt_command')
    def test_get_status(self, mock_call):
        mock_call.return_value = ('Bt-Panel already running', '', 0)
        result = session.get_status(use_json=True)
        parsed = json.loads(result)
        self.assertTrue(parsed['data']['running'])

    @patch('cli_anything.baota.core.session.call_bt_command')
    def test_get_status_not_running(self, mock_call):
        mock_call.return_value = ('Bt-Panel not running', '', 0)
        result = session.get_status(use_json=True)
        parsed = json.loads(result)
        self.assertFalse(parsed['data']['running'])

    @patch('cli_anything.baota.core.session.call_bt_command')
    def test_restart(self, mock_call):
        mock_call.return_value = ('Restarted', '', 0)
        result = session.restart(use_json=True)
        parsed = json.loads(result)
        self.assertTrue(parsed['data']['restarted'])

    @patch('cli_anything.baota.core.session.call_bt_command')
    def test_stop(self, mock_call):
        mock_call.return_value = ('Stopped', '', 0)
        result = session.stop(use_json=True)
        parsed = json.loads(result)
        self.assertTrue(parsed['data']['stopped'])

    @patch('cli_anything.baota.core.session.call_bt_command')
    def test_start(self, mock_call):
        mock_call.return_value = ('Started', '', 0)
        result = session.start(use_json=True)
        parsed = json.loads(result)
        self.assertTrue(parsed['data']['started'])

    @patch('cli_anything.baota.core.session.call_bridge')
    def test_get_auth_info(self, mock_bridge):
        mock_bridge.return_value = {'username': 'admin'}
        result = session.get_auth_info(use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.session.call_bt_command')
    def test_get_default_info(self, mock_call):
        mock_call.return_value = ('Panel info output', '', 0)
        result = session.get_default_info(use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.session.call_bridge')
    def test_get_network_info(self, mock_bridge):
        mock_bridge.return_value = {'ipv4': '198.51.100.1', 'ipv6': '2001:db8::1'}
        result = session.get_network_info(use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)
        self.assertEqual(parsed['data']['ipv6'], '2001:db8::1')

    @patch('cli_anything.baota.core.session.call_bridge')
    def test_get_network_info_error(self, mock_bridge):
        mock_bridge.side_effect = RuntimeError('fail')
        result = session.get_network_info(use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.session.call_bridge')
    def test_list_firewall_rules(self, mock_bridge):
        mock_bridge.return_value = [{'id': 1, 'port': '8002', 'ps': 'test'}]
        result = session.list_firewall_rules(use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)
        self.assertEqual(len(parsed['data']), 1)

    @patch('cli_anything.baota.core.session.call_bridge')
    def test_list_firewall_rules_error(self, mock_bridge):
        mock_bridge.side_effect = RuntimeError('fail')
        result = session.list_firewall_rules(use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.session.call_bridge')
    def test_delete_firewall_rule(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = session.delete_firewall_rule(1, use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.session.call_bridge')
    def test_delete_firewall_rule_error(self, mock_bridge):
        mock_bridge.side_effect = RuntimeError('fail')
        result = session.delete_firewall_rule(99, use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)


class TestDatabase(unittest.TestCase):

    @patch('cli_anything.baota.core.database.call_bridge')
    def test_list_databases(self, mock_bridge):
        mock_bridge.return_value = [{'id': 1, 'name': 'test_db'}]
        result = database.list_databases(use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.database.call_bridge')
    def test_create_database(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = database.create_database('test_db', 'test_user', 'test_pass', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.database.call_bridge')
    def test_delete_database(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = database.delete_database(999, use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.database.call_bridge')
    def test_backup_database(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = database.backup_database(999, use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.database.call_bridge')
    def test_list_databases_error(self, mock_bridge):
        mock_bridge.side_effect = RuntimeError('fail')
        result = database.list_databases(use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.database.call_bridge')
    def test_create_database_error(self, mock_bridge):
        mock_bridge.side_effect = RuntimeError('fail')
        result = database.create_database('x', 'y', 'z', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)


class TestFiles(unittest.TestCase):

    @patch('cli_anything.baota.core.files.call_bridge')
    def test_list_files(self, mock_bridge):
        mock_bridge.return_value = {'list': []}
        result = files.list_files('/tmp', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.files.call_bridge')
    def test_get_file_body(self, mock_bridge):
        mock_bridge.return_value = {'body': 'content'}
        result = files.get_file_body('/tmp/test.txt', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.files.call_bridge')
    def test_set_file_body(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = files.set_file_body('/tmp/test.txt', 'content', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.files.call_bridge')
    def test_create_dir(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = files.create_dir('/tmp/newdir', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.files.call_bridge')
    def test_delete_path(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = files.delete_path('/tmp/todelete', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.files.call_bridge')
    def test_set_permissions(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = files.set_permissions('/tmp', '755', 'www', 'www', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.files.call_bridge')
    def test_list_files_error(self, mock_bridge):
        mock_bridge.side_effect = RuntimeError('fail')
        result = files.list_files('/tmp', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)


class TestConfig(unittest.TestCase):

    @patch('cli_anything.baota.core.config.call_bridge')
    def test_get_config(self, mock_bridge):
        mock_bridge.return_value = {'port': '8888'}
        result = config_module.get_config(use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.config.call_bridge')
    def test_add_dns_record(self, mock_bridge):
        mock_bridge.return_value = {'status': True, 'id': '123'}
        result = config_module.add_dns_record('example.org', 'www', 'AAAA', '2001:db8::1', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)
        mock_bridge.assert_called_with('add_dns_record', domain='example.org', provider=None,
                               subdomain='www', record_type='AAAA',
                               value='2001:db8::1', ttl=600)

    @patch('cli_anything.baota.core.config.call_bridge')
    def test_set_dns_api_dnspod_cli_keys(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = config_module.set_dns_api('dnspod', use_json=True, ID='myid', Token='mytoken')
        parsed = json.loads(result)
        self.assertIn('data', parsed)
        pdata = mock_bridge.call_args.kwargs['pdata']
        self.assertEqual(pdata, {'ID': 'myid', 'Token': 'mytoken'})

    @patch('cli_anything.baota.core.config.call_bridge')
    def test_set_dns_api_aliyun_cli_keys(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = config_module.set_dns_api('aliyun', use_json=True,
                                           AccessKeyId='AKID', AccessKeySecret='SECRET')
        parsed = json.loads(result)
        self.assertIn('data', parsed)
        pdata = mock_bridge.call_args.kwargs['pdata']
        self.assertEqual(pdata, {'AccessKeyId': 'AKID', 'AccessKeySecret': 'SECRET'})

    @patch('cli_anything.baota.core.config.call_bridge')
    def test_set_dns_api_cloudflare_cli_keys(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = config_module.set_dns_api('cloudflare', use_json=True,
                                           Email='user@example.org', APIKey='cfkey')
        parsed = json.loads(result)
        self.assertIn('data', parsed)
        pdata = mock_bridge.call_args.kwargs['pdata']
        self.assertEqual(pdata, {'Email': 'user@example.org', 'APIKey': 'cfkey'})

    @patch('cli_anything.baota.core.config.call_bridge')
    def test_set_dns_api_no_credentials(self, mock_bridge):
        with patch.dict('os.environ', {}, clear=True):
            result = config_module.set_dns_api('dnspod', use_json=True)
        parsed = json.loads(result)
        self.assertEqual(parsed['status'], False)
        self.assertIn('No credentials', parsed['data'].get('msg', ''))

    @patch('cli_anything.baota.core.config.call_bridge')
    def test_add_dns_record_error(self, mock_bridge):
        mock_bridge.side_effect = RuntimeError('fail')
        result = config_module.add_dns_record('x.com', 'a', 'A', '1.2.3.4', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.config.call_bridge')
    def test_list_dns_records(self, mock_bridge):
        mock_bridge.return_value = [{'id': '1', 'name': 'test.example.org', 'type': 'AAAA'}]
        result = config_module.list_dns_records('example.org', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.config.call_bridge')
    def test_list_dns_records_bridge_error(self, mock_bridge):
        mock_bridge.return_value = {'status': False, 'msg': 'No DNS credentials configured'}
        result = config_module.list_dns_records('example.org', use_json=True)
        parsed = json.loads(result)
        self.assertEqual(parsed['status'], False)
        self.assertIn('No DNS credentials', parsed['data'].get('msg', ''))

    @patch('cli_anything.baota.core.config.call_bridge')
    def test_list_dns_records_error(self, mock_bridge):
        mock_bridge.side_effect = RuntimeError('fail')
        result = config_module.list_dns_records('x.com', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.config.call_bridge')
    def test_delete_dns_record(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = config_module.delete_dns_record('example.org', '123', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.config.call_bridge')
    def test_delete_dns_record_error(self, mock_bridge):
        mock_bridge.return_value = {'status': False}
        result = config_module.delete_dns_record('example.org', '999', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.config.call_bridge')
    def test_get_panel_port(self, mock_bridge):
        mock_bridge.return_value = {'port': '8888'}
        result = config_module.get_panel_port(use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.config.call_bridge')
    def test_set_panel_port(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = config_module.set_panel_port('8888', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.config.call_bridge')
    def test_get_logs(self, mock_bridge):
        mock_bridge.return_value = {'logs': 'line1\nline2\n'}
        result = config_module.get_logs(use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.config.call_bridge')
    def test_set_password(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = config_module.set_password('newpass', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.config.call_bridge')
    def test_set_username(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = config_module.set_username('newadmin', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)


class TestExport(unittest.TestCase):

    @patch('cli_anything.baota.core.export.call_bridge')
    def test_export_sites_csv(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = export.export_sites_csv(use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.export.call_bridge')
    def test_export_sites_json(self, mock_bridge):
        mock_bridge.return_value = [{'id': 1, 'name': 'test.com'}]
        result = export.export_sites_json(use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.export.call_bridge')
    def test_generate_report(self, mock_bridge):
        mock_bridge.return_value = {'sites': 5, 'databases': 3}
        result = export.generate_report(use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.export.call_bridge')
    def test_export_sites_csv_error(self, mock_bridge):
        mock_bridge.side_effect = RuntimeError('fail')
        result = export.export_sites_csv(use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)


class TestCron(unittest.TestCase):

    @patch('cli_anything.baota.core.cron.call_bridge')
    def test_list_cron_tasks(self, mock_bridge):
        mock_bridge.return_value = [{'id': 1, 'name': 'test', 'type': 'shell'}]
        result = cron_module.list_cron_tasks(use_json=True)
        parsed = json.loads(result)
        self.assertTrue(parsed['status'])
        self.assertEqual(len(parsed['data']), 1)

    @patch('cli_anything.baota.core.cron.call_bridge')
    def test_list_cron_tasks_error(self, mock_bridge):
        mock_bridge.side_effect = RuntimeError('Bridge error')
        result = cron_module.list_cron_tasks(use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.cron.call_bridge')
    def test_get_cron_task(self, mock_bridge):
        mock_bridge.return_value = {'id': 1, 'name': 'backup', 'type': 'shell'}
        result = cron_module.get_cron_task(1, use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.cron.call_bridge')
    def test_get_cron_task_error(self, mock_bridge):
        mock_bridge.side_effect = RuntimeError('not found')
        result = cron_module.get_cron_task(999, use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.cron.call_bridge')
    def test_add_cron_task(self, mock_bridge):
        mock_bridge.return_value = {'status': True, 'id': 10}
        result = cron_module.add_cron_task('test', 'shell', '0 3 * * *', 'echo hi', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.cron.call_bridge')
    def test_add_cron_task_error(self, mock_bridge):
        mock_bridge.side_effect = RuntimeError('fail')
        result = cron_module.add_cron_task('x', 'shell', '* * * * *', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.cron.call_bridge')
    def test_delete_cron_task(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = cron_module.delete_cron_task(1, use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.cron.call_bridge')
    def test_set_cron_task_status(self, mock_bridge):
        mock_bridge.return_value = {'status': True}
        result = cron_module.set_cron_task_status(1, '1', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.cron.call_bridge')
    def test_set_cron_task_status_error(self, mock_bridge):
        mock_bridge.side_effect = RuntimeError('fail')
        result = cron_module.set_cron_task_status(999, '1', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.cron.call_bridge')
    def test_check_le_renewal_found_active(self, mock_bridge):
        mock_bridge.return_value = [
            {'id': 1, 'name': 'Let\'s Encrypt Renewal', 'type': 'letsencrypt', 'status': '1'}
        ]
        result = cron_module.check_le_renewal(use_json=True)
        parsed = json.loads(result)
        self.assertTrue(parsed['data']['found'])
        self.assertTrue(parsed['data']['active'])

    @patch('cli_anything.baota.core.cron.call_bridge')
    def test_check_le_renewal_found_inactive(self, mock_bridge):
        mock_bridge.return_value = [
            {'id': 2, 'name': 'Let\'s Encrypt Renewal', 'type': 'letsencrypt', 'status': '0'}
        ]
        result = cron_module.check_le_renewal(use_json=True)
        parsed = json.loads(result)
        self.assertTrue(parsed['data']['found'])
        self.assertFalse(parsed['data']['active'])

    @patch('cli_anything.baota.core.cron.call_bridge')
    def test_check_le_renewal_not_found(self, mock_bridge):
        mock_bridge.return_value = [{'id': 3, 'name': 'backup', 'type': 'shell'}]
        result = cron_module.check_le_renewal(use_json=True)
        parsed = json.loads(result)
        self.assertFalse(parsed['data']['found'])
        self.assertFalse(parsed['data']['active'])

    @patch('cli_anything.baota.core.cron.call_bridge')
    def test_check_le_renewal_error(self, mock_bridge):
        mock_bridge.side_effect = RuntimeError('fail')
        result = cron_module.check_le_renewal(use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.cron.call_bridge')
    def test_ensure_le_renewal_already_active(self, mock_bridge):
        mock_bridge.return_value = [
            {'id': 1, 'name': 'LE Renewal', 'type': 'letsencrypt', 'status': '1'}
        ]
        result = cron_module.ensure_le_renewal(use_json=True)
        parsed = json.loads(result)
        self.assertTrue(parsed['data']['status'])
        self.assertIn('already exists and is active', parsed['data']['msg'])

    @patch('cli_anything.baota.core.cron.call_bridge')
    def test_ensure_le_renewal_restart_stopped(self, mock_bridge):
        mock_bridge.side_effect = [
            [{'id': 5, 'name': 'LE Renewal', 'type': 'letsencrypt', 'status': '0'}],
            {'status': True}
        ]
        result = cron_module.ensure_le_renewal(use_json=True)
        parsed = json.loads(result)
        self.assertTrue(parsed['data']['status'])
        self.assertIn('restarted', parsed['data']['msg'])

    @patch('cli_anything.baota.core.cron.call_bridge')
    def test_ensure_le_renewal_create_new(self, mock_bridge):
        mock_bridge.side_effect = [
            [{'id': 3, 'name': 'backup', 'type': 'shell'}],
            {'status': True, 'id': 10, 'msg': 'created'}
        ]
        result = cron_module.ensure_le_renewal(site_id=1, use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.cron.call_bridge')
    def test_ensure_le_renewal_error(self, mock_bridge):
        mock_bridge.side_effect = RuntimeError('fail')
        result = cron_module.ensure_le_renewal(use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)


class TestBt(unittest.TestCase):

    @patch('cli_anything.baota.core.bt.call_bt_command')
    def test_run_bt(self, mock_bt):
        mock_bt.return_value = ('output ok', '', 0)
        result = bt_module.run_bt('14', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    @patch('cli_anything.baota.core.bt.call_bt_command')
    def test_run_bt_text(self, mock_bt):
        mock_bt.return_value = ('面板信息输出', '', 0)
        result = bt_module.run_bt('1', use_json=False)
        self.assertIn('面板信息输出', result)

    @patch('cli_anything.baota.core.bt.call_bt_command')
    def test_run_bt_with_err(self, mock_bt):
        mock_bt.return_value = ('', 'error msg', 1)
        result = bt_module.run_bt('99', use_json=True)
        parsed = json.loads(result)
        self.assertIn('data', parsed)

    def test_bt_menu_has_keys(self):
        self.assertGreater(len(bt_module.BT_MENU), 20)
        self.assertIn('1', bt_module.BT_MENU)
        self.assertIn('22', bt_module.BT_MENU)
        self.assertIn('36', bt_module.BT_MENU)


if __name__ == '__main__':
    unittest.main()
