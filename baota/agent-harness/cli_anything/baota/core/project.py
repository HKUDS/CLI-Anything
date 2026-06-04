import json
from ..utils.helpers import call_bridge, format_output


def list_sites(use_json=False):
    try:
        data = call_bridge('list_sites')
        sites = data if isinstance(data, list) else []
        return format_output(sites, use_json, 'Sites List')
    except Exception as e:
        return format_output({'error': str(e)}, use_json)


def get_site_info(site_id, use_json=False):
    try:
        data = call_bridge('get_site_info', site_id=site_id)
        if isinstance(data, dict) and 'error' in data:
            return format_output({'error': f'Site {site_id} not found'}, use_json)
        return format_output(data, use_json, f'Site: {data.get("name", site_id)}')
    except Exception as e:
        return format_output({'error': str(e)}, use_json)


def create_site(domain, path, port='80', php_version='00', type_ids='', use_json=False):
    try:
        result = call_bridge('create_site', domain=domain, path=path,
                             port=port, version=php_version, type_id=type_ids)
        return format_output(result, use_json, 'Create Site')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)


def delete_site(site_id, use_json=False):
    try:
        result = call_bridge('delete_site', site_id=site_id)
        return format_output(result, use_json, 'Delete Site')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)


def start_site(site_id, use_json=False):
    try:
        result = call_bridge('start_site', site_id=site_id)
        return format_output(result, use_json, 'Start Site')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)


def stop_site(site_id, use_json=False):
    try:
        result = call_bridge('stop_site', site_id=site_id)
        return format_output(result, use_json, 'Stop Site')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)


def list_domains(site_id, use_json=False):
    try:
        data = call_bridge('list_domains', site_id=site_id)
        domains = data if isinstance(data, list) else []
        return format_output(domains, use_json, f'Domains for site {site_id}')
    except Exception as e:
        return format_output({'error': str(e)}, use_json)


def add_domain(site_id, domain, port='80', use_json=False):
    try:
        result = call_bridge('add_domain', site_id=site_id, domain=domain, port=port)
        return format_output(result, use_json, 'Add Domain')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)


def create_proxy(site_id, proxysite, proxydir='/', proxyname=None, use_json=False):
    try:
        data = call_bridge('get_site_info', site_id=site_id)
        if isinstance(data, dict) and 'error' in data:
            return format_output({'error': f'Site {site_id} not found'}, use_json)
        sitename = data.get('name', '')
        if not sitename:
            return format_output({'error': 'Site name not found'}, use_json)
        result = call_bridge('create_proxy', sitename=sitename,
                             proxyname=proxyname or sitename + '_proxy',
                             proxydir=proxydir, proxysite=proxysite)
        return format_output(result, use_json, 'Create Proxy')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)


def set_site_port(site_id, port, use_json=False):
    try:
        result = call_bridge('set_site_port', site_id=site_id, port=str(port))
        return format_output(result, use_json, 'Set Site Port')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)


def get_ssl_info(site_id, use_json=False):
    try:
        result = call_bridge('get_ssl_info', site_id=site_id)
        return format_output(result, use_json, 'SSL Info')
    except Exception as e:
        return format_output({'error': str(e)}, use_json)


def close_ssl(site_id, use_json=False):
    try:
        result = call_bridge('close_ssl', site_id=site_id)
        return format_output(result, use_json, 'Close SSL')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)


def apply_ssl(site_id, domains=None, auth_type='dns', use_json=False):
    try:
        if not domains:
            data = call_bridge('get_site_info', site_id=site_id)
            if isinstance(data, dict) and 'error' in data:
                return format_output({'error': f'Site {site_id} not found'}, use_json)
            domain_list = [d['name'] for d in data.get('domains', [])]
        else:
            domain_list = domains if isinstance(domains, list) else [domains]
        if not domain_list:
            return format_output({'status': False, 'msg': 'No domains found for this site'}, use_json)
        result = call_bridge('apply_ssl', timeout=120, site_id=site_id, domains=domain_list,
                             auth_type=auth_type, auth_to='')
        return format_output(result, use_json, 'Apply SSL')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)
