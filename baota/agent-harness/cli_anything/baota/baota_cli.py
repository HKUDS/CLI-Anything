import sys
import click
import shlex

from .core import project, session, database, files as files_module, config as config_module, export as export_module, cron as cron_module, bt as bt_module
from .utils.helpers import format_output


@click.group(invoke_without_command=True)
@click.option('--json', 'use_json', is_flag=True, help='Output in JSON format')
@click.pass_context
def cli(ctx, use_json):
    ctx.ensure_object(dict)
    ctx.obj['use_json'] = use_json
    if ctx.invoked_subcommand is None:
        repl(ctx)


@cli.group()
@click.pass_context
def sites(ctx):
    pass


@sites.command('list')
@click.pass_context
def sites_list(ctx):
    click.echo(project.list_sites(ctx.obj['use_json']))


@sites.command('info')
@click.argument('site_id', type=int)
@click.pass_context
def sites_info(ctx, site_id):
    click.echo(project.get_site_info(site_id, ctx.obj['use_json']))


@sites.command('create')
@click.option('--domain', required=True, help='Site domain name')
@click.option('--path', required=True, help='Site root path')
@click.option('--port', default='80', help='Site port')
@click.option('--php-version', default='00', help='PHP version (00=纯静态, 56=PHP 5.6, etc.)')
@click.option('--type-ids', default='', help='Site type IDs')
@click.pass_context
def sites_create(ctx, domain, path, port, php_version, type_ids):
    click.echo(project.create_site(domain, path, port, php_version, type_ids, ctx.obj['use_json']))


@sites.command('delete')
@click.argument('site_id', type=int)
@click.pass_context
def sites_delete(ctx, site_id):
    click.echo(project.delete_site(site_id, ctx.obj['use_json']))


@sites.command('start')
@click.argument('site_id', type=int)
@click.pass_context
def sites_start(ctx, site_id):
    click.echo(project.start_site(site_id, ctx.obj['use_json']))


@sites.command('stop')
@click.argument('site_id', type=int)
@click.pass_context
def sites_stop(ctx, site_id):
    click.echo(project.stop_site(site_id, ctx.obj['use_json']))


@sites.command('domains')
@click.argument('site_id', type=int)
@click.pass_context
def sites_domains(ctx, site_id):
    click.echo(project.list_domains(site_id, ctx.obj['use_json']))


@sites.command('add-domain')
@click.argument('site_id', type=int)
@click.argument('domain')
@click.option('--port', default='80')
@click.pass_context
def sites_add_domain(ctx, site_id, domain, port):
    click.echo(project.add_domain(site_id, domain, port, ctx.obj['use_json']))


@sites.command('set-port')
@click.argument('site_id', type=int)
@click.argument('port')
@click.pass_context
def sites_set_port(ctx, site_id, port):
    click.echo(project.set_site_port(site_id, port, ctx.obj['use_json']))


@sites.group()
@click.pass_context
def proxy(ctx):
    pass


@proxy.command('create')
@click.argument('site_id', type=int)
@click.option('--target', required=True, help='Target URL, e.g. http://127.0.0.1:3000')
@click.option('--dir', 'proxydir', default='/', help='Proxy directory path')
@click.option('--name', 'proxyname', help='Proxy name')
@click.pass_context
def proxy_create(ctx, site_id, target, proxydir, proxyname):
    click.echo(project.create_proxy(site_id, target, proxydir, proxyname, ctx.obj['use_json']))


@sites.group()
@click.pass_context
def ssl(ctx):
    pass


@ssl.command('apply')
@click.argument('site_id', type=int)
@click.option('--domains', help='Comma-separated domains (default: all site domains)')
@click.option('--auth', type=click.Choice(['dns', 'http']), default='dns', help='Auth type')
@click.pass_context
def ssl_apply(ctx, site_id, domains, auth):
    if domains:
        domain_list = [d.strip() for d in domains.split(',')]
    else:
        domain_list = []
    click.echo(project.apply_ssl(site_id, domain_list, auth, ctx.obj['use_json']))


@ssl.command('info')
@click.argument('site_id', type=int)
@click.pass_context
def ssl_info(ctx, site_id):
    click.echo(project.get_ssl_info(site_id, ctx.obj['use_json']))


@ssl.command('close')
@click.argument('site_id', type=int)
@click.pass_context
def ssl_close(ctx, site_id):
    click.echo(project.close_ssl(site_id, ctx.obj['use_json']))


@cli.group()
@click.pass_context
def databases(ctx):
    pass


@databases.command('list')
@click.pass_context
def databases_list(ctx):
    click.echo(database.list_databases(ctx.obj['use_json']))


@databases.command('create')
@click.option('--name', required=True, help='Database name')
@click.option('--username', required=True, help='Database username')
@click.option('--password', required=True, help='Database password')
@click.option('--encoding', default='utf8mb4', help='Character encoding')
@click.pass_context
def databases_create(ctx, name, username, password, encoding):
    click.echo(database.create_database(name, username, password, encoding, ctx.obj['use_json']))


@databases.command('delete')
@click.argument('db_id', type=int)
@click.pass_context
def databases_delete(ctx, db_id):
    click.echo(database.delete_database(db_id, ctx.obj['use_json']))


@databases.command('backup')
@click.argument('db_id', type=int)
@click.pass_context
def databases_backup(ctx, db_id):
    click.echo(database.backup_database(db_id, ctx.obj['use_json']))


@cli.group()
@click.pass_context
def files(ctx):
    pass


@files.command('list')
@click.argument('path')
@click.pass_context
def files_list(ctx, path):
    click.echo(files_module.list_files(path, ctx.obj['use_json']))


@files.command('read')
@click.argument('path')
@click.pass_context
def files_read(ctx, path):
    click.echo(files_module.get_file_body(path, ctx.obj['use_json']))


@files.command('write')
@click.argument('path')
@click.argument('content')
@click.option('--encoding', default='utf-8')
@click.pass_context
def files_write(ctx, path, content, encoding):
    click.echo(files_module.set_file_body(path, content, encoding, ctx.obj['use_json']))


@files.command('mkdir')
@click.argument('path')
@click.pass_context
def files_mkdir(ctx, path):
    click.echo(files_module.create_dir(path, ctx.obj['use_json']))


@files.command('delete')
@click.argument('path')
@click.pass_context
def files_delete(ctx, path):
    click.echo(files_module.delete_path(path, ctx.obj['use_json']))


@cli.group()
@click.pass_context
def config(ctx):
    pass


@config.command('show')
@click.pass_context
def config_show(ctx):
    click.echo(config_module.get_config(ctx.obj['use_json']))


@config.command('port')
@click.argument('port', required=False)
@click.pass_context
def config_port(ctx, port):
    if port:
        click.echo(config_module.set_panel_port(port, ctx.obj['use_json']))
    else:
        click.echo(config_module.get_panel_port(ctx.obj['use_json']))


@config.command('password')
@click.argument('password')
@click.pass_context
def config_password(ctx, password):
    click.echo(config_module.set_password(password, ctx.obj['use_json']))


@config.command('username')
@click.argument('username')
@click.pass_context
def config_username(ctx, username):
    click.echo(config_module.set_username(username, ctx.obj['use_json']))


@config.command('logs')
@click.option('--lines', default=100, help='Number of log lines')
@click.pass_context
def config_logs(ctx, lines):
    click.echo(config_module.get_logs(lines, ctx.obj['use_json']))


@config.group()
@click.pass_context
def dns(ctx):
    pass


@dns.command('set')
@click.argument('provider', type=click.Choice(['dnspod', 'aliyun', 'cloudflare']))
@click.option('--id', 'api_id', help='API ID / AccessKeyId / Email')
@click.option('--token', 'api_token', help='API Token / AccessKeySecret / APIKey')
@click.pass_context
def dns_set(ctx, provider, api_id, api_token):
    field_map = {
        'dnspod': {'ID': api_id, 'Token': api_token},
        'aliyun': {'AccessKeyId': api_id, 'AccessKeySecret': api_token},
        'cloudflare': {'Email': api_id, 'APIKey': api_token},
    }
    click.echo(config_module.set_dns_api(provider, ctx.obj['use_json'], **field_map[provider]))


@dns.command('list')
@click.pass_context
def dns_list(ctx):
    click.echo(config_module.list_dns_api(ctx.obj['use_json']))


@dns.group()
@click.pass_context
def record(ctx):
    pass


@record.command('add')
@click.argument('domain')
@click.argument('subdomain')
@click.argument('type_')
@click.argument('value')
@click.option('--ttl', default=600, help='DNS TTL in seconds')
@click.option('--provider', type=click.Choice(['dnspod', 'aliyun', 'cloudflare']),
              help='DNS provider to use (default: first configured)')
@click.pass_context
def dns_record_add(ctx, domain, subdomain, type_, value, ttl, provider):
    click.echo(config_module.add_dns_record(domain, subdomain, type_, value, ttl, ctx.obj['use_json'], provider=provider))


@record.command('list')
@click.argument('domain')
@click.option('--provider', type=click.Choice(['dnspod', 'aliyun', 'cloudflare']),
              help='DNS provider to use (default: first configured)')
@click.pass_context
def dns_record_list(ctx, domain, provider):
    click.echo(config_module.list_dns_records(domain, ctx.obj['use_json'], provider=provider))


@record.command('delete')
@click.argument('domain')
@click.argument('record_id')
@click.option('--provider', type=click.Choice(['dnspod', 'aliyun', 'cloudflare']),
              help='DNS provider to use (default: first configured)')
@click.pass_context
def dns_record_delete(ctx, domain, record_id, provider):
    click.echo(config_module.delete_dns_record(domain, record_id, ctx.obj['use_json'], provider=provider))


@cli.group()
@click.pass_context
def system(ctx):
    pass


@system.command('status')
@click.pass_context
def system_status(ctx):
    click.echo(session.get_status(ctx.obj['use_json']))


@system.command('restart')
@click.pass_context
def system_restart(ctx):
    click.echo(session.restart(ctx.obj['use_json']))


@system.command('stop')
@click.pass_context
def system_stop(ctx):
    click.echo(session.stop(ctx.obj['use_json']))


@system.command('start')
@click.pass_context
def system_start(ctx):
    click.echo(session.start(ctx.obj['use_json']))


@system.command('auth')
@click.pass_context
def system_auth(ctx):
    click.echo(session.get_auth_info(ctx.obj['use_json']))


@system.command('info')
@click.pass_context
def system_info(ctx):
    click.echo(session.get_default_info(ctx.obj['use_json']))


@system.command('network')
@click.pass_context
def system_network(ctx):
    click.echo(session.get_network_info(ctx.obj['use_json']))


@system.command('firewall-open')
@click.argument('port')
@click.option('--desc', default='', help='Description')
@click.pass_context
def system_firewall_open(ctx, port, desc):
    click.echo(session.add_firewall_port(port, desc, ctx.obj['use_json']))


@system.command('firewall-list')
@click.pass_context
def system_firewall_list(ctx):
    click.echo(session.list_firewall_rules(ctx.obj['use_json']))


@system.command('firewall-delete')
@click.argument('rule_id', type=int)
@click.pass_context
def system_firewall_delete(ctx, rule_id):
    click.echo(session.delete_firewall_rule(rule_id, ctx.obj['use_json']))


@cli.group()
@click.pass_context
def bt(ctx):
    pass


for _num, _desc in bt_module.BT_MENU.items():

    def _make_bt_cmd(num):
        @click.pass_context
        def _cmd(ctx):
            click.echo(bt_module.run_bt(num, ctx.obj['use_json']))
        _cmd.__name__ = f'bt_{num}'
        _cmd.__doc__ = f'bt {num} — {_desc}'
        return _cmd

    bt.command(name=str(_num), help=_desc)(_make_bt_cmd(_num))


@bt.command('raw')
@click.argument('number')
@click.pass_context
def bt_raw(ctx, number):
    """Run any bt menu option by number (raw passthrough)"""
    click.echo(bt_module.run_bt(number, ctx.obj['use_json']))


@cli.group()
@click.pass_context
def export(ctx):
    pass


@export.command('sites')
@click.option('--format', 'fmt', type=click.Choice(['json', 'csv']), default='json')
@click.pass_context
def export_sites(ctx, fmt):
    if fmt == 'csv':
        click.echo(export_module.export_sites_csv(ctx.obj['use_json']))
    else:
        click.echo(export_module.export_sites_json(ctx.obj['use_json']))


@export.command('report')
@click.pass_context
def export_report(ctx):
    click.echo(export_module.generate_report(ctx.obj['use_json']))


@cli.group()
@click.pass_context
def cron(ctx):
    pass


@cron.command('list')
@click.pass_context
def cron_list(ctx):
    click.echo(cron_module.list_cron_tasks(ctx.obj['use_json']))


@cron.command('info')
@click.argument('task_id', type=int)
@click.pass_context
def cron_info(ctx, task_id):
    click.echo(cron_module.get_cron_task(task_id, ctx.obj['use_json']))


@cron.command('add')
@click.option('--name', required=True, help='Task name')
@click.option('--type', 'type_', required=True, help='Task type (e.g. letsencrypt, shell)')
@click.option('--time', 'time_config', required=True, help='Cron time config, e.g. "0 3 * * *"')
@click.option('--command', 'echo_command', default='', help='Shell command to execute')
@click.pass_context
def cron_add(ctx, name, type_, time_config, echo_command):
    click.echo(cron_module.add_cron_task(name, type_, time_config, echo_command, ctx.obj['use_json']))


@cron.command('delete')
@click.argument('task_id', type=int)
@click.pass_context
def cron_delete(ctx, task_id):
    click.echo(cron_module.delete_cron_task(task_id, ctx.obj['use_json']))


@cron.command('start')
@click.argument('task_id', type=int)
@click.pass_context
def cron_start(ctx, task_id):
    click.echo(cron_module.set_cron_task_status(task_id, '1', ctx.obj['use_json']))


@cron.command('stop')
@click.argument('task_id', type=int)
@click.pass_context
def cron_stop(ctx, task_id):
    click.echo(cron_module.set_cron_task_status(task_id, '0', ctx.obj['use_json']))


@cron.command('check-le')
@click.pass_context
def cron_check_le(ctx):
    click.echo(cron_module.check_le_renewal(ctx.obj['use_json']))


@cron.command('ensure-le')
@click.option('--site-id', type=int, help='Site ID for new renewal task (if creating)')
@click.pass_context
def cron_ensure_le(ctx, site_id):
    click.echo(cron_module.ensure_le_renewal(site_id, ctx.obj['use_json']))


@ssl.command('deploy')
@click.argument('site_id', type=int)
@click.option('--domains', help='Comma-separated domain list')
@click.option('--auth', type=click.Choice(['dns', 'http']), default='dns')
@click.option('--skip-ssl', is_flag=True, help='Skip SSL apply, only ensure renewal cron')
@click.pass_context
def ssl_deploy(ctx, site_id, domains, auth, skip_ssl):
    results = []
    if not skip_ssl:
        domain_list = domains.split(',') if domains else None
        ssl_result = project.apply_ssl(site_id, domain_list, auth, ctx.obj['use_json'])
        results.append(('Apply SSL', ssl_result))
    cron_result = cron_module.ensure_le_renewal(site_id, ctx.obj['use_json'])
    results.append(('Ensure LE Renewal', cron_result))
    for label, output in results:
        click.echo(f'--- {label} ---')
        click.echo(output)


def repl(ctx):
    click.echo('Baota CLI - Interactive Mode')
    click.echo('Type "help" for commands, "exit" to quit.')
    while True:
        try:
            cmd = click.prompt('Baota CLI', prompt_suffix=' > ')
        except (EOFError, KeyboardInterrupt):
            click.echo()
            break
        if cmd in ('exit', 'quit', 'q'):
            break
        if cmd in ('help', '?'):
            click.echo('Commands: sites, databases, files, config, system, export, cron, ssl deploy')
            click.echo('  sites set-port <site_id> <port>')
            click.echo('  config dns record add/list/delete')
            click.echo('  system network')
            click.echo('Run any command with --help for details')
            click.echo('Add --json for JSON output')
            continue
        if not cmd.strip():
            continue
        try:
            old_argv = sys.argv
            sys.argv = ['cli-anything-baota'] + shlex.split(cmd)
            try:
                cli(obj={'use_json': '--json' in sys.argv}, standalone_mode=False)
            except SystemExit:
                pass
            finally:
                sys.argv = old_argv
        except Exception as e:
            click.echo(f'Error: {e}')


if __name__ == '__main__':
    cli(obj={})

main = cli
