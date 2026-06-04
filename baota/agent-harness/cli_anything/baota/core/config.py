from ..utils.helpers import call_bridge, format_output


def get_config(use_json=False):
    try:
        config = call_bridge('get_config')
        if not isinstance(config, dict):
            config = {}
        return format_output(config, use_json, 'Panel Configuration')
    except Exception as e:
        return format_output({'error': str(e)}, use_json)


def get_panel_port(use_json=False):
    try:
        data = call_bridge('read_port')
        return format_output(data, use_json, 'Panel Port')
    except Exception as e:
        return format_output({'port': '8888'}, use_json, 'Panel Port')


def set_panel_port(port, use_json=False):
    try:
        result = call_bridge('set_panel_port', port=port)
        return format_output(result, use_json, 'Set Panel Port')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)


def set_password(password, use_json=False):
    try:
        result = call_bridge('set_password', password=password)
        return format_output(result, use_json, 'Set Password')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)


def set_username(username, use_json=False):
    try:
        result = call_bridge('set_username', username=username)
        return format_output(result, use_json, 'Set Username')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)


def get_logs(tail_lines=100, use_json=False):
    try:
        data = call_bridge('read_logs', tail_lines=tail_lines)
        return format_output(data.get('logs', ''), use_json, f'Panel Logs (last {tail_lines} lines)')
    except Exception as e:
        return format_output({'error': str(e)}, use_json)


DNS_PROVIDERS = {
    'dnspod': {'dns_name': 'DNSPodDns', 'fields': ['ID', 'Token'],
               'env_map': {'ID': 'BAOTA_DNSPOD_ID', 'Token': 'BAOTA_DNSPOD_TOKEN'}},
    'aliyun': {'dns_name': 'AliyunDns', 'fields': ['AccessKeyId', 'AccessKeySecret'],
               'env_map': {'AccessKeyId': 'BAOTA_ALIYUN_KEY', 'AccessKeySecret': 'BAOTA_ALIYUN_SECRET'}},
    'cloudflare': {'dns_name': 'CloudFlareDns', 'fields': ['Email', 'APIKey'],
                   'env_map': {'Email': 'BAOTA_CF_EMAIL', 'APIKey': 'BAOTA_CF_KEY'}},
}


def set_dns_api(provider, use_json=False, **kwargs):
    try:
        import os
        prov = DNS_PROVIDERS.get(provider)
        if not prov:
            return format_output({'status': False, 'msg': f'Unsupported provider: {provider}'}, use_json)
        lookup = {k.lower(): v for k, v in kwargs.items() if v}
        pdata = {}
        for f in prov['fields']:
            val = lookup.get(f.lower()) or kwargs.get(f)
            if not val:
                env_var = prov['env_map'].get(f, '')
                val = os.environ.get(env_var, '')
            if val:
                pdata[f] = val
        if not pdata:
            env_hints = ', '.join(prov['env_map'].values())
            return format_output({'status': False, 'msg': f'No credentials. Set via --{f.lower()} or env: {env_hints}'}, use_json)
        result = call_bridge('add_dns_api', dns_name=prov['dns_name'], pdata=pdata, ps='Configured via CLI')
        return format_output(result, use_json, f'Set {provider} DNS API')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)


def list_dns_api(use_json=False):
    try:
        data = call_bridge('list_dns_api')
        return format_output(data, use_json, 'DNS API Providers')
    except Exception as e:
        return format_output({'error': str(e)}, use_json)


def add_dns_record(domain, subdomain, record_type, value, ttl=600, use_json=False, provider=None):
    try:
        result = call_bridge('add_dns_record', domain=domain, provider=provider,
                             subdomain=subdomain, record_type=record_type,
                             value=value, ttl=ttl)
        return format_output(result, use_json, 'Add DNS Record')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)


def list_dns_records(domain, use_json=False, provider=None):
    try:
        data = call_bridge('list_dns_records', domain=domain, provider=provider)
        if isinstance(data, dict) and data.get('status') is False:
            return format_output(data, use_json, f'DNS Records for {domain}')
        records = data if isinstance(data, list) else []
        return format_output(records, use_json, f'DNS Records for {domain}')
    except Exception as e:
        return format_output({'error': str(e)}, use_json)


def delete_dns_record(domain, record_id, use_json=False, provider=None):
    try:
        result = call_bridge('delete_dns_record', domain=domain, record_id=record_id, provider=provider)
        return format_output(result, use_json, 'Delete DNS Record')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)
