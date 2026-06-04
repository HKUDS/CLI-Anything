from ..utils.helpers import call_bridge, format_output
def list_files(path, use_json=False):
    try:
        result = call_bridge('list_files', path=path)
        return format_output(result, use_json, f'Files: {path}')
    except Exception as e:
        return format_output({'error': str(e)}, use_json)
def get_file_body(path, use_json=False):
    try:
        result = call_bridge('get_file_body', path=path)
        return format_output(result, use_json, f'File: {path}')
    except Exception as e:
        return format_output({'error': str(e)}, use_json)
def set_file_body(path, content, encoding='utf-8', use_json=False):
    try:
        result = call_bridge('set_file_body', path=path, content=content, encoding=encoding)
        return format_output(result, use_json, f'Save: {path}')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)
def create_dir(path, use_json=False):
    try:
        result = call_bridge('create_dir', path=path)
        return format_output(result, use_json, f'Create Dir: {path}')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)
def delete_path(path, use_json=False):
    try:
        result = call_bridge('delete_path', path=path)
        return format_output(result, use_json, f'Delete: {path}')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)
def set_permissions(path, mode, user, group, use_json=False):
    try:
        result = call_bridge('set_permissions', path=path, mode=mode, user=user, group=group)
        return format_output(result, use_json, f'Set Permissions: {path}')
    except Exception as e:
        return format_output({'status': False, 'msg': str(e)}, use_json)
