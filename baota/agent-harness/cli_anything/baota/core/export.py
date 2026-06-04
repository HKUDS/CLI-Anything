from ..utils.helpers import call_bridge, format_output


def export_sites_csv(use_json=False):
    try:
        result = call_bridge('export_sites_csv')
        return format_output(result, use_json, 'Export Sites CSV')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)


def export_sites_json(use_json=False):
    try:
        result = call_bridge('export_sites_json')
        return format_output(result, use_json, 'Export Sites JSON')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)


def generate_report(use_json=False):
    try:
        data = call_bridge('generate_report')
        return format_output(data, use_json, 'Panel Report')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)
