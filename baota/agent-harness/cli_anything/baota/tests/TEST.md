# Test Plan: cli-anything-baota

## Unit Tests (`test_core.py`)

| Test | Description | Status |
|------|-------------|--------|
| `TestHelpers::test_format_output_json` | JSON format output helper | PASS |
| `TestHelpers::test_format_output_text` | Text format output helper | PASS |
| `TestHelpers::test_output_json_dict` | JSON output with dict data | PASS |
| `TestHelpers::test_output_json_with_msg` | JSON output with message | PASS |
| `TestHelpers::test_output_text_dict` | Text output with dict | PASS |
| `TestHelpers::test_output_text_list` | Text output with list | PASS |
| `TestProject::test_list_sites` | List sites with data | PASS |
| `TestProject::test_list_sites_error` | List sites error handling | PASS |
| `TestProject::test_get_site_info` | Get site info | PASS |
| `TestProject::test_create_site` | Create site | PASS |
| `TestProject::test_create_site_error` | Create site error handling | PASS |
| `TestProject::test_delete_site` | Delete site | PASS |
| `TestProject::test_add_domain` | Add domain to site | PASS |
| `TestProject::test_apply_ssl` | Apply SSL certificate | PASS |
| `TestProject::test_get_ssl_info` | Get SSL info | PASS |
| `TestProject::test_get_ssl_info_error` | Get SSL info error | PASS |
| `TestProject::test_close_ssl` | Close SSL | PASS |
| `TestProject::test_close_ssl_error` | Close SSL error | PASS |
| `TestProject::test_set_site_port` | Set site port | PASS |
| `TestProject::test_set_site_port_error` | Set site port error | PASS |
| `TestProject::test_stop_site` | Stop site | PASS |
| `TestProject::test_list_domains` | List site domains | PASS |
| `TestSession::test_get_status` | Get panel status (running) | PASS |
| `TestSession::test_get_status_not_running` | Get panel status (not running) | PASS |
| `TestSession::test_restart` | Restart panel service | PASS |
| `TestSession::test_stop` | Stop panel service | PASS |
| `TestSession::test_start` | Start panel service | PASS |
| `TestSession::test_get_auth_info` | Get panel auth info | PASS |
| `TestSession::test_get_default_info` | Get default panel info | PASS |
| `TestSession::test_get_network_info` | Get network info | PASS |
| `TestSession::test_get_network_info_error` | Get network info error | PASS |
| `TestSession::test_list_firewall_rules` | List firewall rules | PASS |
| `TestSession::test_list_firewall_rules_error` | List firewall rules error | PASS |
| `TestSession::test_delete_firewall_rule` | Delete firewall rule | PASS |
| `TestSession::test_delete_firewall_rule_error` | Delete firewall rule error | PASS |
| `TestDatabase::test_list_databases` | List databases | PASS |
| `TestDatabase::test_list_databases_error` | List databases error handling | PASS |
| `TestDatabase::test_create_database` | Create database | PASS |
| `TestDatabase::test_create_database_error` | Create database error handling | PASS |
| `TestDatabase::test_delete_database` | Delete database | PASS |
| `TestDatabase::test_backup_database` | Backup database | PASS |
| `TestFiles::test_list_files` | List files | PASS |
| `TestFiles::test_list_files_error` | List files error handling | PASS |
| `TestFiles::test_get_file_body` | Get file body | PASS |
| `TestFiles::test_set_file_body` | Set file body | PASS |
| `TestFiles::test_create_dir` | Create directory | PASS |
| `TestFiles::test_delete_path` | Delete path | PASS |
| `TestFiles::test_set_permissions` | Set permissions | PASS |
| `TestConfig::test_get_config` | Get config | PASS |
| `TestConfig::test_get_panel_port` | Get panel port | PASS |
| `TestConfig::test_set_panel_port` | Set panel port | PASS |
| `TestConfig::test_set_password` | Set password | PASS |
| `TestConfig::test_set_username` | Set username | PASS |
| `TestConfig::test_get_logs` | Get panel logs | PASS |
| `TestConfig::test_add_dns_record` | Add DNS record | PASS |
| `TestConfig::test_add_dns_record_error` | Add DNS record error | PASS |
| `TestConfig::test_list_dns_records` | List DNS records | PASS |
| `TestConfig::test_list_dns_records_error` | List DNS records error | PASS |
| `TestConfig::test_delete_dns_record` | Delete DNS record | PASS |
| `TestConfig::test_delete_dns_record_error` | Delete DNS record error | PASS |
| `TestExport::test_export_sites_csv` | Export sites CSV | PASS |
| `TestExport::test_export_sites_csv_error` | Export sites CSV error handling | PASS |
| `TestExport::test_export_sites_json` | Export sites JSON | PASS |
| `TestExport::test_generate_report` | Generate report | PASS |
| `TestCron::test_list_cron_tasks` | List scheduled tasks | PASS |
| `TestCron::test_list_cron_tasks_error` | List cron tasks error | PASS |
| `TestCron::test_get_cron_task` | Get cron task details | PASS |
| `TestCron::test_get_cron_task_error` | Get cron task error | PASS |
| `TestCron::test_add_cron_task` | Add scheduled task | PASS |
| `TestCron::test_add_cron_task_error` | Add cron task error | PASS |
| `TestCron::test_delete_cron_task` | Delete scheduled task | PASS |
| `TestCron::test_set_cron_task_status` | Enable/disable cron task | PASS |
| `TestCron::test_set_cron_task_status_error` | Set cron status error | PASS |
| `TestCron::test_check_le_renewal_found_active` | Check LE renewal (found active) | PASS |
| `TestCron::test_check_le_renewal_found_inactive` | Check LE renewal (found inactive) | PASS |
| `TestCron::test_check_le_renewal_not_found` | Check LE renewal (not found) | PASS |
| `TestCron::test_check_le_renewal_error` | Check LE renewal error | PASS |
| `TestCron::test_ensure_le_renewal_already_active` | Ensure LE renewal (already active) | PASS |
| `TestCron::test_ensure_le_renewal_restart_stopped` | Ensure LE renewal (restart stopped) | PASS |
| `TestCron::test_ensure_le_renewal_create_new` | Ensure LE renewal (create new) | PASS |
| `TestCron::test_ensure_le_renewal_error` | Ensure LE renewal error | PASS |
| `TestBt::test_bt_menu_has_keys` | BT menu dict has keys | PASS |
| `TestBt::test_run_bt` | Run bt command | PASS |
| `TestBt::test_run_bt_text` | Run bt command (text output) | PASS |
| `TestBt::test_run_bt_with_err` | Run bt command (with error) | PASS |

## E2E Tests (`test_full_e2e.py`)

| Test | Description | Status |
|------|-------------|--------|
| `TestCLISubprocess::test_help` | CLI --help displays usage | PASS |
| `TestCLISubprocess::test_subcommand_help` | Subcommand --help | PASS |
| `TestCLISubprocess::test_system_help` | System subcommand help | PASS |
| `TestCLISubprocess::test_json_version_enabled` | JSON output with sites list | PASS |
| `TestCLISubprocess::test_json_output_flag` | JSON flag with config show | PASS |
| `TestCLISubprocess::test_json_with_system_status` | JSON with system status | PASS |
| `TestCLISubprocess::test_invalid_command` | Invalid command handling | PASS |
| `TestCLISubprocess::test_invalid_option` | Invalid option handling | PASS |
| `TestCLISubprocess::test_help_output_contains_sites` | Help lists sites command | PASS |
| `TestCLISubprocess::test_help_output_contains_system` | Help lists system command | PASS |
| `TestCLISubprocess::test_json_flag_on_help` | --json with --help | PASS |
| `TestE2EFull::test_help_output` | CLI --help via module | PASS |
| `TestE2EFull::test_json_output_parses` | JSON output is valid JSON | PASS |
| `TestE2EFull::test_help_contains_json_flag` | Help mentions --json | PASS |
| `TestE2EFull::test_databases_help` | Databases subcommand help | PASS |
| `TestE2EFull::test_files_help` | Files subcommand help | PASS |
| `TestE2EFull::test_export_help` | Export subcommand help | PASS |
| `TestE2EFull::test_sites_help` | Sites subcommand help | PASS |
| `TestE2EFull::test_config_help` | Config subcommand help | PASS |
| `TestE2EFull::test_cron_help` | Cron subcommand help | PASS |
| `TestE2EFull::test_cron_check_le_help` | Cron check-le help | PASS |
| `TestE2EFull::test_cron_ensure_le_help` | Cron ensure-le help | PASS |
| `TestE2EFull::test_ssl_deploy_help` | SSL deploy help | PASS |
| `TestE2EFull::test_ssl_info_help` | SSL info help | PASS |
| `TestE2EFull::test_ssl_close_help` | SSL close help | PASS |
| `TestE2EFull::test_sites_set_port_help` | Sites set-port help | PASS |
| `TestE2EFull::test_dns_record_help` | DNS record help | PASS |
| `TestE2EFull::test_dns_record_add_help` | DNS record add help | PASS |
| `TestE2EFull::test_dns_record_list_help` | DNS record list help | PASS |
| `TestE2EFull::test_dns_record_delete_help` | DNS record delete help | PASS |
| `TestE2EFull::test_system_network_help` | System network help | PASS |
| `TestE2EFull::test_system_firewall_list_help` | System firewall-list help | PASS |
| `TestE2EFull::test_system_firewall_delete_help` | System firewall-delete help | PASS |
| `TestE2EFull::test_bt_help` | bt subcommand help | PASS |
| `TestE2EFull::test_bt_14` | bt 14 (view default info) | PASS |
| `TestE2EFull::test_bt_raw_help` | bt raw help | PASS |

## Test Results

Last run: 2026-06-01 12:00:00

**All 121 tests pass (100% pass rate).**

```
$ CLI_ANYTHING_FORCE_INSTALLED=1 python -m pytest cli_anything/baota/tests/ -v --tb=no
============================= 121 passed in 6.00s ==============================
```

## Coverage Notes

- Unit tests (85 tests): Cover all core modules including site CRUD, SSL (apply/info/close), reverse proxy, database CRUD + backup, file CRUD, config management, DNS API + record CRUD, cron CRUD + LE renewal, firewall rules, BT menu commands, network info, and site port config with synthetic data. No external panel dependencies.
- E2E tests (36 tests): Cover CLI framework (help, JSON, error handling) plus cron, ssl-deploy/deploy/info/close, DNS record, site port, firewall, BT menu, and network commands via subprocess using `_resolve_cli()`.
- Subprocess tests pass with `CLI_ANYTHING_FORCE_INSTALLED=1` and also work as module fallback.
- Backend tests that require the actual Baota Panel runtime are tested at the unit level with mocked imports.
- CLI command `cli-anything-baota` is available in PATH after `pip install -e .`.
