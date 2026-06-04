import sys
import json

sys.path.insert(0, '/www/server/panel/class')
sys.path.insert(0, '/www/server/panel')

operation = sys.argv[1]
args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

import os, re, time, uuid, hashlib, hmac, base64, urllib.parse


def _get_dns_config():
    conf_path = '/www/server/panel/config/dns_mager.conf'
    import public
    dns_config = json.loads(public.readFile(conf_path) or '{}')
    for name in ['DNSPodDns', 'AliyunDns', 'CloudFlareDns']:
        creds = dns_config.get(name, [])
        if creds and len(creds) > 0:
            return name, creds[0]
    return None, None


def _dns_dnspod(action, domain, cred, **kw):
    import requests as req
    token = cred.get('ID', '') + ',' + cred.get('Token', '')
    urls = {'add': 'Record.Create', 'list': 'Record.List', 'delete': 'Record.Remove'}
    body = {'login_token': token, 'format': 'json', 'domain': domain}
    if action == 'add':
        body.update({'sub_domain': kw.get('subdomain', ''), 'record_type': kw.get('type_', 'A'), 'value': kw.get('value', ''), 'record_line_id': '0', 'ttl': kw.get('ttl', 600)})
    elif action == 'delete':
        body['record_id'] = kw.get('record_id', '')
    resp = req.post('https://dnsapi.cn/' + urls[action], data=body, timeout=30).json()
    if action == 'list':
        if resp.get('status', {}).get('code') == '1':
            return [{'id': r['id'], 'name': r['name'], 'type': r['type'], 'value': r['value']} for r in resp.get('records', [])]
        return []
    if resp.get('status', {}).get('code') == '1':
        return {'status': True, 'id': str(resp.get('record', {}).get('id', '')), 'msg': 'success'}
    return {'status': False, 'msg': resp.get('status', {}).get('message', 'Unknown error')}


def _aliyun_sign(params, secret):
    sorted_keys = sorted(params.keys())
    query = '&'.join(urllib.parse.quote(str(k), safe='') + '=' + urllib.parse.quote(str(params[k]), safe='') for k in sorted_keys)
    string_to_sign = 'POST&%2F&' + urllib.parse.quote(query, safe='')
    return base64.b64encode(hmac.new((secret + '&').encode(), string_to_sign.encode(), hashlib.sha1).digest()).decode()


def _dns_aliyun(action, domain, cred, **kw):
    import requests as req
    ak_id = cred.get('AccessKeyId', '')
    ak_secret = cred.get('AccessKeySecret', '')
    action_map = {'add': 'AddDomainRecord', 'list': 'DescribeDomainRecords', 'delete': 'DeleteDomainRecord'}
    params = {
        'Action': action_map[action],
        'AccessKeyId': ak_id,
        'Format': 'JSON',
        'SignatureMethod': 'HMAC-SHA1',
        'SignatureNonce': str(uuid.uuid4()),
        'SignatureVersion': '1.0',
        'Timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'Version': '2015-01-09',
        'DomainName': domain,
    }
    if action == 'add':
        params.update({'RR': kw.get('subdomain', ''), 'Type': kw.get('type_', 'A'), 'Value': kw.get('value', ''), 'TTL': kw.get('ttl', 600)})
    elif action == 'delete':
        params['RecordId'] = kw.get('record_id', '')
    params['Signature'] = _aliyun_sign(params, ak_secret)
    resp = req.post('https://alidns.aliyuncs.com/', data=params, timeout=30).json()
    if action == 'list':
        records = resp.get('DomainRecords', {}).get('Record', [])
        return [{'id': r['RecordId'], 'name': r.get('RR', ''), 'type': r['Type'], 'value': r['Value']} for r in records]
    record_id = resp.get('RecordId', '')
    if record_id:
        return {'status': True, 'id': str(record_id), 'msg': 'success'}
    return {'status': False, 'msg': resp.get('Message', 'Unknown error')}


def _dns_cloudflare(action, domain, cred, **kw):
    import requests as req
    email = cred.get('Email', '')
    api_key = cred.get('APIKey', '')
    headers = {'X-Auth-Email': email, 'X-Auth-Key': api_key, 'Content-Type': 'application/json'}
    zones = req.get('https://api.cloudflare.com/client/v4/zones?name=' + urllib.parse.quote(domain), headers=headers, timeout=30).json()
    if not zones.get('success') or not zones.get('result'):
        return {'status': False, 'msg': 'Domain not found in Cloudflare account'}
    zone_id = zones['result'][0]['id']
    if action == 'list':
        resp = req.get('https://api.cloudflare.com/client/v4/zones/' + zone_id + '/dns_records', headers=headers, timeout=30).json()
        if resp.get('success'):
            return [{'id': r['id'], 'name': r['name'], 'type': r['type'], 'value': r['content']} for r in resp.get('result', [])]
        return []
    if action == 'add':
        full_name = kw.get('subdomain', '') + '.' + domain
        resp = req.post('https://api.cloudflare.com/client/v4/zones/' + zone_id + '/dns_records',
                        headers=headers, json={'type': kw.get('type_', 'A'), 'name': full_name, 'content': kw.get('value', ''), 'ttl': int(kw.get('ttl', 600))}, timeout=30).json()
        if resp.get('success') and resp.get('result'):
            return {'status': True, 'id': resp['result']['id'], 'msg': 'success'}
        return {'status': False, 'msg': '; '.join(e.get('message', '') for e in resp.get('errors', [])) or 'Unknown error'}
    if action == 'delete':
        resp = req.delete('https://api.cloudflare.com/client/v4/zones/' + zone_id + '/dns_records/' + kw.get('record_id', ''),
                          headers=headers, timeout=30).json()
        if resp.get('success'):
            return {'status': True, 'id': kw.get('record_id', ''), 'msg': 'success'}
        return {'status': False, 'msg': '; '.join(e.get('message', '') for e in resp.get('errors', [])) or 'Unknown error'}


DNS_PROVIDER_MAP = {
    'DNSPodDns': _dns_dnspod,
    'AliyunDns': _dns_aliyun,
    'CloudFlareDns': _dns_cloudflare,
}


PROVIDER_NAME_TO_INTERNAL = {
    'dnspod': 'DNSPodDns',
    'aliyun': 'AliyunDns',
    'cloudflare': 'CloudFlareDns',
}


def _call_dns_api(action, domain, provider_name=None, **kw):
    name, cred = None, None
    if provider_name:
        internal = PROVIDER_NAME_TO_INTERNAL.get(provider_name.lower(), provider_name)
        import public
        conf_path = '/www/server/panel/config/dns_mager.conf'
        dns_config = json.loads(public.readFile(conf_path) or '{}')
        creds = dns_config.get(internal, [])
        if creds and len(creds) > 0:
            name, cred = internal, creds[0]
    if not name:
        name, cred = _get_dns_config()
    if not name:
        return {'status': False, 'msg': 'No DNS credentials configured. Use `config dns set` first.'}
    handler = DNS_PROVIDER_MAP.get(name)
    if not handler:
        return {'status': False, 'msg': 'Unsupported DNS provider: ' + name}
    return handler(action, domain, cred, **kw)


try:
    if operation == 'list_sites':
        import public
        data = public.M('sites').field('id,name,status,ps,path,addtime').select()
        print(json.dumps(data if isinstance(data, list) else [], ensure_ascii=False))

    elif operation == 'get_site_info':
        import public
        site = public.M('sites').where('id=?', (args['site_id'],)).find()
        if isinstance(site, str):
            print(json.dumps({'error': 'not found'}, ensure_ascii=False))
        else:
            domains = public.M('domain').where('pid=?', (site['id'],)).select()
            site['domains'] = domains if isinstance(domains, list) else []
            print(json.dumps(site, ensure_ascii=False))

    elif operation == 'create_site':
        import public
        from panelSite import panelSite
        domain = args.get('domain', '')
        port = args.get('port', '80')
        path = args['path']
        version = args.get('version', '00')
        domainlist = args.get('domainlist', [])
        if not domainlist:
            domainlist = [f'{domain}:{port}']
        webname_obj = {
            'domain': domain,
            'domainlist': [d for d in domainlist if d.split(':')[0] != domain],
            'count': 1
        }

        check_name = domain.replace('[', '').replace(']', '')
        if not public.is_ipv6(check_name):
            check_name = check_name.strip().split(':')[0].lower()

        existing = public.M('domain').where("name=? and port=?", (check_name, int(port))).getField('pid')
        if existing:
            site_data = public.M('sites').where('id=?', (existing,)).find()
            if site_data and not (isinstance(site_data, str) and 'error' in site_data):
                print(json.dumps({'status': True, 'msg': '站点已存在', 'id': existing}, ensure_ascii=False))
            else:
                print(json.dumps({'status': False, 'msg': '域名已被占用，但站点记录不存在'}, ensure_ascii=False))
        else:
            site = panelSite()
            get = public.dict_obj()
            get.webname = json.dumps(webname_obj)
            get.path = path
            get.port = port
            get.version = version
            get.type_id = args.get('type_id', '0')
            get.type = 'PHP'
            get.ps = args.get('ps', 'Created via CLI')
            get.ftp = 'true' if args.get('ftp') else False
            get.ftp_username = args.get('ftp_username', '')
            get.ftp_password = args.get('ftp_password', '')
            get.sql = 'true' if args.get('sql') else False
            get.datauser = args.get('datauser', '')
            get.datapassword = args.get('datapassword', '')
            get.codeing = 'utf8'
            result = site.AddSite(get)
            print(json.dumps(result, ensure_ascii=False))

    elif operation == 'delete_site':
        import public
        from panelSite import panelSite
        site_data = public.M('sites').where('id=?', (args['site_id'],)).find()
        if not site_data or (isinstance(site_data, str) and 'error' in site_data):
            print(json.dumps({'status': False, 'msg': '指定站点不存在!'}, ensure_ascii=False))
        else:
            site = panelSite()
            get = public.dict_obj()
            get.id = args['site_id']
            get.webname = site_data.get('name', '')
            result = site.DeleteSite(get)
            print(json.dumps(result, ensure_ascii=False))

    elif operation == 'start_site':
        import public
        from panelSite import panelSite
        site = panelSite()
        get = public.dict_obj()
        get.id = args['site_id']
        result = site.SiteStart(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'stop_site':
        import public
        from panelSite import panelSite
        site = panelSite()
        get = public.dict_obj()
        get.id = args['site_id']
        result = site.SiteStop(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'list_domains':
        import public
        domains = public.M('domain').where('pid=?', (args['site_id'],)).select()
        print(json.dumps(domains if isinstance(domains, list) else [], ensure_ascii=False))

    elif operation == 'add_domain':
        import public
        from panelSite import panelSite
        site_data = public.M('sites').where('id=?', (args['site_id'],)).find()
        if not site_data or (isinstance(site_data, str) and 'error' in site_data):
            print(json.dumps({'status': False, 'msg': '指定站点不存在!'}, ensure_ascii=False))
        else:
            site = panelSite()
            get = public.dict_obj()
            get.id = args['site_id']
            get.webname = site_data.get('name', '')
            get.domain = args['domain']
            get.port = args.get('port', '80')
            result = site.AddDomain(get)
            print(json.dumps(result, ensure_ascii=False))

    elif operation == 'list_databases':
        import public
        data = public.M('databases').select()
        print(json.dumps(data if isinstance(data, list) else [], ensure_ascii=False))

    elif operation == 'create_database':
        import public
        from database import database as db_module
        db = db_module()
        get = public.dict_obj()
        get.name = args['name']
        get.username = args['username']
        get.password = args['password']
        get.encoding = args.get('encoding', 'utf8mb4')
        result = db.CreateDatabase(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'delete_database':
        import public
        from database import database as db_module
        db = db_module()
        get = public.dict_obj()
        get.id = args['db_id']
        result = db.DeleteDatabase(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'backup_database':
        import public
        from database import database as db_module
        db = db_module()
        get = public.dict_obj()
        get.id = args['db_id']
        result = db.BackupDatabase(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'list_files':
        import public
        from files import files as files_module
        f = files_module()
        get = public.dict_obj()
        get.path = args['path']
        get.show_sub = '0'
        result = f.GetDir(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'get_file_body':
        import public
        from files import files as files_module
        f = files_module()
        get = public.dict_obj()
        get.path = args['path']
        result = f.GetFileBody(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'set_file_body':
        import public
        from files import files as files_module
        f = files_module()
        get = public.dict_obj()
        get.path = args['path']
        get.data = args['content']
        get.encoding = args.get('encoding', 'utf-8')
        result = f.SetFileBody(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'create_dir':
        import public
        from files import files as files_module
        f = files_module()
        get = public.dict_obj()
        get.path = args['path']
        result = f.CreateDir(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'delete_path':
        import public
        from files import files as files_module
        f = files_module()
        get = public.dict_obj()
        get.path = args['path']
        result = f.DeleteDir(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'set_permissions':
        import public
        from files import files as files_module
        f = files_module()
        get = public.dict_obj()
        get.path = args['path']
        get.mode = args['mode']
        get.user = args['user']
        get.group = args['group']
        result = f.SetPermission(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'get_config':
        import public
        config = public.M('config').where('id=?', (1,)).find()
        if isinstance(config, str) and config.find('error') != -1:
            config = {}
        print(json.dumps(config, ensure_ascii=False))

    elif operation == 'set_panel_port':
        import public
        from config import config as config_module
        c = config_module()
        get = public.dict_obj()
        get.port = args['port']
        result = c.setPanel(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'set_password':
        import public
        from config import config as config_module
        c = config_module()
        get = public.dict_obj()
        get.password = args['password']
        result = c.setPassword(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'set_username':
        import public
        from config import config as config_module
        c = config_module()
        get = public.dict_obj()
        get.username = args['username']
        result = c.setUsername(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'export_sites_json':
        import public
        sites = public.M('sites').select()
        if isinstance(sites, str):
            sites = []
        result = []
        for site in (sites or []):
            domains = public.M('domain').where('pid=?', (site.get('id'),)).select()
            if isinstance(domains, str):
                domains = []
            site['domains'] = domains
            result.append(site)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'generate_report':
        import public
        data = {}
        try:
            sr = public.M('sites').select()
            data['sites'] = len(sr) if isinstance(sr, list) else 0
        except Exception:
            data['sites'] = 0
        try:
            dr = public.M('databases').select()
            data['databases'] = len(dr) if isinstance(dr, list) else 0
        except Exception:
            data['databases'] = 0
        try:
            fr = public.M('ftp').select()
            data['ftp_accounts'] = len(fr) if isinstance(fr, list) else 0
        except Exception:
            data['ftp_accounts'] = 0
        print(json.dumps(data, ensure_ascii=False))

    elif operation == 'export_sites_csv':
        import public
        from panelSite import panelSite
        site = panelSite()
        get = public.dict_obj()
        result = site.export_sites_to_csv(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'read_port':
        port_file = '/www/server/panel/data/port.pl'
        try:
            with open(port_file) as f:
                port = f.read().strip()
            print(json.dumps({'port': port}, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({'port': '8888'}, ensure_ascii=False))

    elif operation == 'read_auth_info':
        auth_file = '/www/server/panel/data/userInfo.json'
        try:
            with open(auth_file) as f:
                data = json.loads(f.read())
            print(json.dumps(data, ensure_ascii=False))
        except Exception:
            print(json.dumps({}, ensure_ascii=False))

    elif operation == 'read_logs':
        log_file = '/www/server/panel/logs/error.log'
        tail_lines = args.get('tail_lines', 100)
        try:
            with open(log_file) as f:
                lines = f.readlines()
            tail = ''.join(lines[-tail_lines:])
            print(json.dumps({'logs': tail}, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({'error': str(e)}, ensure_ascii=False))

    elif operation == 'create_proxy':
        import public
        from panelSite import panelSite
        site = panelSite()
        get = public.dict_obj()
        get.sitename = args['sitename']
        get.proxyname = args.get('proxyname', args['sitename'] + '_proxy')
        get.proxydir = args.get('proxydir', '/')
        get.proxysite = args['proxysite']
        get.todomain = args.get('todomain', args['sitename'])
        get.type = int(args.get('type', 1))
        get.cache = int(args.get('cache', 0))
        get.cachetime = int(args.get('cachetime', 0))
        get.advanced = int(args.get('advanced', 0))
        get.subfilter = json.dumps(args.get('subfilter', [{"sub1": "", "sub2": ""}]))
        get.nocheck = args.get('nocheck', '1')
        result = site.CreateProxy(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'add_dns_api':
        import public, json, uuid, re
        sfile = '/www/server/panel/config/dns_mager.conf'
        dns_name = args['dns_name']
        pdata = args.get('pdata', {})
        ps = args.get('ps', '')
        new_id = uuid.uuid4().hex
        pdata['id'] = new_id
        pdata['ps'] = ps
        try:
            data = json.loads(public.readFile(sfile))
        except:
            data = {}
        type_data = data.get(dns_name, [])
        type_data.append(pdata)
        data[dns_name] = type_data
        public.writeFile(sfile, json.dumps(data))
        # Link root domains from all sites to this DNS API
        sites = public.M('sites').field('name').select()
        root_domains = set()
        for site in sites:
            name = site.get('name', '')
            parts = name.split('.')
            if len(parts) >= 2:
                root = '.'.join(parts[-2:])
                root_domains.add(root)
        for rd in root_domains:
            existing = public.M('ssl_domains').where('domain=?', (rd,)).count()
            if existing:
                public.M('ssl_domains').where('domain=?', (rd,)).setField('dns_id', new_id)
            else:
                public.M('ssl_domains').add('domain,dns_id,type_id,endtime,ps', (rd, new_id, 0, 0, ''))
        print(json.dumps({'status': True, 'msg': '添加成功', 'id': new_id}, ensure_ascii=False))

    elif operation == 'list_dns_api':
        import public, json
        sfile = '/www/server/panel/config/dns_mager.conf'
        try:
            data = json.loads(public.readFile(sfile))
        except:
            data = {}
        print(json.dumps(data, ensure_ascii=False))

    elif operation == 'apply_ssl':
        import public, json
        from acme_v2 import acme_v2
        acme = acme_v2()
        get = public.dict_obj()
        site_id = args['site_id']
        get.id = site_id
        get.domains = json.dumps(args['domains'])
        get.auth_type = args.get('auth_type', 'dns')
        auth_to = args.get('auth_to', '')
        if not auth_to:
            if get.auth_type == 'dns':
                conf_path = '/www/server/panel/config/dns_mager.conf'
                dns_config = json.loads(public.readFile(conf_path) or '{}')
                for name in ['DNSPodDns', 'AliyunDns', 'CloudFlareDns']:
                    creds = dns_config.get(name, [])
                    if creds and len(creds) > 0:
                        c = creds[0]
                        if name == 'DNSPodDns':
                            auth_to = name + '|' + c.get('ID', '') + ',' + c.get('Token', '')
                        elif name == 'AliyunDns':
                            auth_to = name + '|' + c.get('AccessKeyId', '') + ',' + c.get('AccessKeySecret', '')
                        elif name == 'CloudFlareDns':
                            auth_to = name + '|' + c.get('Email', '') + ',' + c.get('APIKey', '')
                        break
                if not auth_to:
                    auth_to = 'dns'
            else:
                auth_to = str(site_id)
        get.auth_to = auth_to
        get.auto_wildcard = args.get('auto_wildcard', '0')
        if 'ca' in args:
            get.ca = args['ca']
        result = acme.apply_cert_api(get)
        if result.get('status') and result.get('private_key'):
            from panelSite import panelSite
            site_data = public.M('sites').where('id=?', (site_id,)).find()
            if site_data:
                deploy_get = public.dict_obj()
                deploy_get.siteName = site_data.get('name', '')
                deploy_get.key = result['private_key']
                deploy_get.csr = result['cert'] + '\n' + result.get('root', '')
                deploy_result = panelSite().SetSSL(deploy_get)
                result['deploy'] = deploy_result
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'get_network_info':
        import subprocess, re
        result = {'ipv4': '', 'ipv6': ''}
        try:
            out = subprocess.check_output(['hostname', '-I'], text=True).strip()
            parts = out.split()
            for p in parts:
                if ':' in p:
                    result['ipv6'] = p
                elif '.' in p:
                    result['ipv4'] = p
        except Exception:
            pass
        if not result['ipv6']:
            try:
                out = subprocess.check_output(['ip', '-6', 'addr', 'show', 'scope', 'global'], text=True)
                m = re.search(r'inet6\s+(\S+)', out)
                if m:
                    result['ipv6'] = m.group(1).split('/')[0]
            except Exception:
                pass
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'add_dns_record':
        result = _call_dns_api('add', args.get('domain', ''), provider_name=args.get('provider'),
                               subdomain=args.get('subdomain', ''), type_=args.get('record_type', 'A'),
                               value=args.get('value', ''), ttl=args.get('ttl', 600))
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'list_dns_records':
        result = _call_dns_api('list', args.get('domain', ''), provider_name=args.get('provider'))
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'delete_dns_record':
        result = _call_dns_api('delete', args.get('domain', ''), provider_name=args.get('provider'),
                               record_id=args.get('record_id', ''))
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'set_site_port':
        import public, re
        site_id = str(args.get('site_id', ''))
        port = str(args.get('port', '80'))
        site = public.M('sites').where('id=?', (site_id,)).find()
        if not site:
            print(json.dumps({'status': False, 'msg': 'Site not found'}))
            sys.exit(0)
        site_name = site['name']
        conf_path = '/www/server/panel/vhost/nginx/' + site_name + '.conf'
        conf = public.readFile(conf_path)
        if not conf:
            print(json.dumps({'status': False, 'msg': 'Config not found'}))
            sys.exit(0)
        old_ports = re.findall(r'listen\s+(?:\[::\]:)?(\d+)', conf)
        old_443 = re.findall(r'listen\s+443\s+ssl', conf)
        old_port = old_ports[0] if old_ports else '80'
        conf = conf.replace('listen ' + old_port, 'listen ' + port)
        conf = conf.replace('listen [::]:' + old_port, 'listen [::]:' + port)
        if old_443:
            has_ssl = conf.find('listen ' + port + ' ssl') != -1 or conf.find('listen [::]:' + port + ' ssl') != -1
            if not has_ssl:
                conf = conf.replace('listen ' + port + ';', 'listen ' + port + ' ssl http2 ;')
                conf = conf.replace('listen [::]:' + port + ';', 'listen [::]:' + port + ' ssl http2 ;')
        public.writeFile(conf_path, conf)
        public.M('domain').where('pid=?', (site_id,)).save('port', port)
        public.ExecShell('/www/server/nginx/sbin/nginx -s reload')
        print(json.dumps({'status': True, 'msg': 'Port updated from ' + old_port + ' to ' + port}))

    elif operation == 'add_firewall_port':
        import public, time
        from firewalls import firewalls
        fw = firewalls()
        get = public.dict_obj()
        get.port = str(args.get('port', ''))
        get.ps = str(args.get('ps', ''))
        result = fw.AddAcceptPort(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'list_firewall_rules':
        import public
        data = public.M('firewall').field('id,port,ps,addtime').select()
        print(json.dumps(data if isinstance(data, list) else [], ensure_ascii=False))

    elif operation == 'delete_firewall_rule':
        import public, time
        from firewalls import firewalls
        fw = firewalls()
        get = public.dict_obj()
        get.id = str(args.get('rule_id', ''))
        result = fw.DelAcceptPort(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'get_ssl_info':
        import public
        from panelSite import panelSite
        site_id = args.get('site_id', '')
        site = public.M('sites').where('id=?', (site_id,)).find()
        if not site:
            print(json.dumps({'status': False, 'msg': 'Site not found'}))
            sys.exit(0)
        ps = panelSite()
        get = public.dict_obj()
        get.siteName = site['name']
        result = ps.GetSSL(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'close_ssl':
        import public
        from panelSite import panelSite
        site_id = args.get('site_id', '')
        site = public.M('sites').where('id=?', (site_id,)).find()
        if not site:
            print(json.dumps({'status': False, 'msg': 'Site not found'}))
            sys.exit(0)
        ps = panelSite()
        get = public.dict_obj()
        get.siteName = site['name']
        result = ps.CloseSSLConf(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'list_cron':
        import public
        data = public.M('crontab').field('id,name,type,where_hour,where_minute,echo,addtime,status,sBody,sType,type_id,second').select()
        if not isinstance(data, list):
            data = []
        print(json.dumps(data, ensure_ascii=False))

    elif operation == 'get_cron':
        import public
        data = public.M('crontab').where('id=?', (args.get('task_id', 0),)).find()
        if isinstance(data, dict) and 'id' in data:
            print(json.dumps(data, ensure_ascii=False))
        else:
            print(json.dumps({'error': 'not found'}, ensure_ascii=False))

    elif operation == 'add_cron':
        import public
        from crontab import crontab as ct
        c = ct()
        get = public.dict_obj()
        get.name = args.get('name', '')
        get.type = args.get('type', 'day')
        get.where1 = int(args.get('where1', 1))
        get.where_hour = int(args.get('where_hour', 3))
        get.where_minute = int(args.get('where_minute', 0))
        get.sBody = args.get('echo_command', '')
        get.sType = 'toShell'
        result = c.AddCrontab(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'delete_cron':
        import public
        from crontab import crontab as ct
        c = ct()
        get = public.dict_obj()
        get.id = str(args.get('task_id', ''))
        result = c.DelCrontab(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'set_cron_status':
        import public
        from crontab import crontab as ct
        c = ct()
        get = public.dict_obj()
        get.id = str(args.get('task_id', ''))
        get.status = str(args.get('status', '1'))
        result = c.set_cron_status(get)
        print(json.dumps(result, ensure_ascii=False))

    elif operation == 'add_le_renewal':
        import public
        from crontab import crontab as ct
        c = ct()
        get = public.dict_obj()
        get.name = "续签Let's Encrypt证书"
        get.type = 'day'
        get.where1 = 1
        get.where_hour = 3
        get.where_minute = 0
        get.sBody = '/www/server/panel/pyenv/bin/python3 -u /www/server/panel/class/acme_v2.py --renew=1'
        get.sType = 'toShell'
        if args.get('site_id'):
            get.site_id = str(args['site_id'])
        result = c.AddCrontab(get)
        print(json.dumps(result, ensure_ascii=False))

    else:
        print(json.dumps({'status': False, 'msg': f'Unknown operation: {operation}'}, ensure_ascii=False))

except Exception as e:
    print(json.dumps({'status': False, 'msg': str(e)}, ensure_ascii=False))
