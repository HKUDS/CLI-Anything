from ..utils.helpers import call_bt_command, call_bridge, format_output


def get_status(use_json=False):
    out, err, code = call_bt_command('status')
    status_data = {
        'running': 'already running' in out,
        'output': out.strip()
    }
    return format_output(status_data, use_json, 'Panel Status')


def restart(use_json=False):
    out, err, code = call_bt_command('restart')
    return format_output({'restarted': code == 0, 'output': out.strip()}, use_json, 'Restart Panel')


def stop(use_json=False):
    out, err, code = call_bt_command('stop')
    return format_output({'stopped': code == 0, 'output': out.strip()}, use_json, 'Stop Panel')


def start(use_json=False):
    out, err, code = call_bt_command('start')
    return format_output({'started': code == 0, 'output': out.strip()}, use_json, 'Start Panel')


def get_auth_info(use_json=False):
    try:
        data = call_bridge('read_auth_info')
        return format_output(data, use_json, 'Auth Info')
    except Exception as e:
        return format_output({'error': str(e)}, use_json)


def get_default_info(use_json=False):
    out, err, code = call_bt_command('default')
    return format_output({'output': out.strip()}, use_json, 'Default Info')


def add_firewall_port(port, ps='', use_json=False):
    try:
        result = call_bridge('add_firewall_port', port=port, ps=ps)
        return format_output(result, use_json, 'Add Firewall Port')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)


def list_firewall_rules(use_json=False):
    try:
        data = call_bridge('list_firewall_rules')
        rules = data if isinstance(data, list) else []
        return format_output(rules, use_json, 'Firewall Rules')
    except Exception as e:
        return format_output({'error': str(e)}, use_json)


def delete_firewall_rule(rule_id, use_json=False):
    try:
        result = call_bridge('delete_firewall_rule', rule_id=rule_id)
        return format_output(result, use_json, 'Delete Firewall Rule')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)


def get_network_info(use_json=False):
    try:
        data = call_bridge('get_network_info')
        return format_output(data, use_json, 'Network Info')
    except Exception as e:
        return format_output({'error': str(e)}, use_json)
