from ..utils.helpers import call_bridge, format_output
def list_databases(use_json=False):
    try:
        data = call_bridge('list_databases')
        dbs = data if isinstance(data, list) else []
        return format_output(dbs, use_json, 'Databases')
    except Exception as e:
        return format_output({'error': str(e)}, use_json)
def create_database(name, username, password, encoding='utf8mb4', use_json=False):
    try:
        result = call_bridge('create_database', name=name, username=username,
                             password=password, encoding=encoding)
        return format_output(result, use_json, 'Create Database')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)
def delete_database(db_id, use_json=False):
    try:
        result = call_bridge('delete_database', db_id=db_id)
        return format_output(result, use_json, 'Delete Database')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)
def backup_database(db_id, use_json=False):
    try:
        result = call_bridge('backup_database', db_id=db_id)
        return format_output(result, use_json, 'Backup Database')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)
