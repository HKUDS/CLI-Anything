from ..utils.helpers import call_bridge, format_output


def list_cron_tasks(use_json=False):
    try:
        data = call_bridge('list_cron')
        tasks = data if isinstance(data, list) else []
        return format_output(tasks, use_json, 'Scheduled Tasks')
    except Exception as e:
        return format_output({'error': str(e)}, use_json)


def get_cron_task(task_id, use_json=False):
    try:
        data = call_bridge('get_cron', task_id=task_id)
        return format_output(data, use_json, f'Scheduled Task: {task_id}')
    except Exception as e:
        return format_output({'error': str(e)}, use_json)


def add_cron_task(name, type_, time_config, echo_command='', use_json=False):
    try:
        parts = time_config.split()
        def _cron_int(val, default):
            if val == '*':
                return default
            return int(val)
        where_minute = _cron_int(parts[0], 0) if len(parts) > 0 else 0
        where_hour = _cron_int(parts[1], 3) if len(parts) > 1 else 3
        where1 = _cron_int(parts[2], 1) if len(parts) > 2 else 1
        result = call_bridge('add_cron', name=name, type=type_,
                             where_minute=where_minute, where_hour=where_hour,
                             where1=where1, echo_command=echo_command)
        return format_output(result, use_json, 'Add Scheduled Task')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)


def delete_cron_task(task_id, use_json=False):
    try:
        result = call_bridge('delete_cron', task_id=task_id)
        return format_output(result, use_json, 'Delete Scheduled Task')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)


def set_cron_task_status(task_id, status, use_json=False):
    try:
        result = call_bridge('set_cron_status', task_id=task_id, status=status)
        return format_output(result, use_json, 'Set Task Status')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)


def check_le_renewal(use_json=False):
    try:
        data = call_bridge('list_cron')
        tasks = data if isinstance(data, list) else []
        le_tasks = [
            t for t in tasks
            if 'letsencrypt' in str(t.get('type', '')).lower()
            or 'let' in str(t.get('name', '')).lower()
            or '续签' in str(t.get('name', ''))
            or 'ssl' in str(t.get('name', '')).lower()
        ]
        found = len(le_tasks) > 0
        active = any(str(t.get('status', '')) == '1' for t in le_tasks) if le_tasks else False
        result = {
            'found': found,
            'active': active,
            'task_count': len(le_tasks),
            'tasks': le_tasks
        }
        return format_output(result, use_json, "Let's Encrypt Renewal Check")
    except Exception as e:
        return format_output({'error': str(e)}, use_json)


def ensure_le_renewal(site_id=None, use_json=False):
    try:
        check = call_bridge('list_cron')
        tasks = check if isinstance(check, list) else []
        le_tasks = [
            t for t in tasks
            if 'letsencrypt' in str(t.get('type', '')).lower()
            or 'let' in str(t.get('name', '')).lower()
            or '续签' in str(t.get('name', ''))
            or 'ssl' in str(t.get('name', '')).lower()
        ]
        if le_tasks:
            active_tasks = [t for t in le_tasks if str(t.get('status', '')) == '1']
            if active_tasks:
                return format_output({
                    'status': True,
                    'msg': "Let's Encrypt renewal task already exists and is active",
                    'task_id': active_tasks[0].get('id'),
                    'tasks': active_tasks
                }, use_json, "Let's Encrypt Renewal - OK")
            else:
                task_id = le_tasks[0].get('id')
                result = call_bridge('set_cron_status', task_id=task_id, status='1')
                return format_output({
                    'status': True,
                    'msg': "Let's Encrypt renewal task was stopped, now restarted",
                    'task_id': task_id
                }, use_json, "Let's Encrypt Renewal - Restarted")
        else:
            result = call_bridge('add_le_renewal', site_id=site_id)
            return format_output(result, use_json, "Let's Encrypt Renewal - Created")
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)
