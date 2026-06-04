import json
import os
import subprocess


BAOTA_PANEL_PATH = '/www/server/panel'
BAOTA_CLASS_PATH = os.path.join(BAOTA_PANEL_PATH, 'class')
PANEL_PYTHON = '/www/server/panel/pyenv/bin/python3'
BRIDGE_SCRIPT = '/tmp/baota_bridge.py'


BRIDGE_MODULE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bridge.py')


def _ensure_bridge():
    if not os.path.exists(BRIDGE_MODULE):
        raise RuntimeError(
            f'Bridge script not found at {BRIDGE_MODULE}. '
            'Ensure cli-anything-baota is properly installed.'
        )
    import shutil
    os.makedirs(os.path.dirname(BRIDGE_SCRIPT), exist_ok=True)
    shutil.copy2(BRIDGE_MODULE, BRIDGE_SCRIPT)
    os.chmod(BRIDGE_SCRIPT, 0o644)


def call_bridge(operation, timeout=30, **kwargs):
    _ensure_bridge()
    args_json = json.dumps(kwargs)
    result = subprocess.run(
        ['sudo', PANEL_PYTHON, BRIDGE_SCRIPT, operation, args_json],
        capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f'Bridge exited with code {result.returncode}')
    if not result.stdout.strip():
        raise RuntimeError('Bridge returned empty output')
    return json.loads(result.stdout.strip())


def run_panel_script(script_name, *args):
    cmd = [PANEL_PYTHON]
    cmd.append(os.path.join(BAOTA_PANEL_PATH, script_name))
    cmd.extend(str(a) for a in args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return '', 'Timeout', -1
    except FileNotFoundError:
        return '', 'Panel environment not found', -1


def call_bt_command(command):
    result = subprocess.run(
        ['sudo', '/etc/init.d/bt', command],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout, result.stderr, result.returncode


def output_json(data, status=True, msg=None):
    result = {'status': status, 'data': data}
    if msg:
        result['msg'] = msg
    return json.dumps(result, ensure_ascii=False, indent=2)


def output_text(data, title=None):
    lines = []
    if title:
        lines.append('=' * 60)
        lines.append(f'  {title}')
        lines.append('=' * 60)
    if isinstance(data, dict):
        for k, v in data.items():
            lines.append(f'  {k}: {v}')
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, dict):
                lines.append(f'  --- Item {i + 1} ---')
                for k, v in item.items():
                    lines.append(f'    {k}: {v}')
            else:
                lines.append(f'  {i + 1}. {item}')
    elif isinstance(data, str):
        lines.append(data)
    return '\n'.join(lines)


def format_output(data, use_json=False, title=None):
    if use_json:
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                return output_json(parsed)
            except json.JSONDecodeError:
                return output_json({'raw': data})
        if isinstance(data, dict) and 'status' in data:
            return output_json(data, status=data['status'])
        return output_json(data)
    return output_text(data, title)
