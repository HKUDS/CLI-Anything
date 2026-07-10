"""
Code generator: Mailchimp Swagger 2.0 spec → Click command modules.

Usage:
    python -m cli_anything.mailchimp._codegen.generate

Downloads the Mailchimp Marketing API spec and emits one Python module per
tag into cli_anything/mailchimp/commands/. The generated files are committed
to the repository so end-users do not need to run the generator.
"""

from __future__ import annotations

import builtins
import json
import keyword
import os
import re
import sys
import textwrap
from collections import defaultdict
from pathlib import Path

import requests

SPEC_URL = (
    "https://raw.githubusercontent.com/mailchimp/mailchimp-client-lib-codegen"
    "/main/spec/marketing.json"
)

OUT_DIR = Path(__file__).resolve().parents[1] / "commands"

# Tags that should be skipped (internal/meta).
_SKIP_TAGS: set[str] = set()

# Names that must not appear as Python function/param names even if technically
# valid identifiers (builtins + common shadowing traps).
_BUILTIN_NAMES: frozenset[str] = frozenset(dir(builtins))


def _slugify(name: str) -> str:
    """Convert camelCase or PascalCase or space-separated to kebab-case."""
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1-\2", name)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1-\2", s)
    s = s.replace(" ", "-").replace("_", "-").lower()
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def _safe_name(name: str) -> str:
    """Convert a string to a safe Python identifier (keywords and builtins get underscore suffix)."""
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if name and name[0].isdigit():
        name = "_" + name
    if keyword.iskeyword(name) or name in _BUILTIN_NAMES:
        name += "_"
    return name


def _tag_to_module(tag: str) -> str:
    return _slugify(tag).replace("-", "_")


def _tag_to_group(tag: str) -> str:
    return _slugify(tag)


def _infer_command_name(method: str, path: str, operation_id: str) -> str:
    """Derive a clean command name from the HTTP method and path."""
    # Action endpoints (POST to .../actions/xxx)
    action_match = re.search(r"/actions/([^/]+)$", path)
    if action_match:
        return _slugify(action_match.group(1))

    # Determine if this is a collection endpoint or single-resource by checking
    # whether the path ends with a path parameter.
    ends_with_param = bool(re.search(r"\{[^}]+\}$", path))

    if method == "get":
        return "get" if ends_with_param else "list"
    elif method == "post":
        return "create"
    elif method in ("patch", "put"):
        return "update"
    elif method == "delete":
        return "delete"
    else:
        return _slugify(operation_id)


def _dedup_suffix(cmd_name: str, path: str, operation_id: str, count: int) -> str:
    """Return a unique suffix for a colliding command name.

    Prefers a slug derived from the operationId over a raw path segment,
    because path segments are often path-param shaped ({list_id}) which
    produces confusing names like 'create-list-id'.
    """
    # Try a meaningful suffix from the operationId (strip the HTTP verb prefix)
    op_slug = _slugify(re.sub(r"^(get|post|patch|put|delete)", "", operation_id))
    if op_slug and op_slug != cmd_name:
        return f"{cmd_name}-{op_slug}"

    # Fall back to the last non-param path segment
    segments = [s for s in path.rstrip("/").split("/") if s and not s.startswith("{")]
    if segments:
        suffix = _slugify(segments[-1])
        if suffix and suffix != cmd_name:
            return f"{cmd_name}-{suffix}"

    return f"{cmd_name}-{count}"


def _param_type_to_click(param: dict) -> str:
    t = param.get("type", "string")
    if t == "integer":
        return "int"
    if t == "boolean":
        return "bool"
    return "str"


def _click_help_text(description: str) -> str:
    """Return a single-line Click help string without truncating useful API context."""
    first_line = description.split("\n")[0]
    return " ".join(first_line.replace('"', '\\"').split())


def _collect_params(operation: dict, path: str) -> tuple[list[dict], list[dict], dict | None]:
    """Return (path_params, query_params, body_param) from operation."""
    params = operation.get("parameters", [])
    path_params = [p for p in params if p.get("in") == "path"]
    query_params = [p for p in params if p.get("in") == "query"]
    body_params = [p for p in params if p.get("in") == "body"]
    body = body_params[0] if body_params else None
    return path_params, query_params, body


def _generate_command_func(
    cmd_name: str,
    method: str,
    path: str,
    operation: dict,
    path_params: list,
    query_params: list,
    body_param: dict | None,
) -> str:
    summary = operation.get("summary", "").replace('"', '\\"')
    # C1: prefix with _cmd_ so no builtin shadowing (list, get, delete, etc.)
    func_name = "_cmd_" + _safe_name(cmd_name.replace("-", "_"))

    lines: list[str] = []

    group_var = f"{_tag_to_module(operation['tags'][0])}_group"
    decorators = [f'@{group_var}.command("{cmd_name}")']

    # Path params as Click arguments (positional)
    for p in path_params:
        py_arg = _safe_name(p["name"]).upper()
        decorators.append(f'@click.argument("{py_arg}")')

    # Body option
    if body_param is not None:
        decorators.append(
            '@click.option("--data", default=None, '
            'help="Request body as JSON string.")'
        )

    # I3: All query params (no arbitrary cap); --extra-params escape hatch
    for p in query_params:
        flag = _slugify(p["name"])
        py_name = _safe_name(p["name"]).lower()
        ptype = _param_type_to_click(p)
        desc = _click_help_text(p.get("description", ""))
        if ptype == "int":
            type_clause = "type=int, "
        elif ptype == "bool":
            type_clause = "type=bool, "
        else:
            type_clause = ""
        decorators.append(
            f'@click.option("--{flag}", "{py_name}", default=None, {type_clause}help="{desc}")'
        )

    # Escape hatch for extra/future query params
    decorators.append(
        '@click.option("--extra-params", default=None, '
        'help="Extra query params as JSON object, e.g. \'{\\"key\\":\\"val\\"}\'")'
    )

    decorators.append("@click.pass_context")

    for d in decorators:
        lines.append(d)

    # Function signature — M4: no module-level USE_JSON import needed
    sig_parts = ["ctx"]
    for p in path_params:
        sig_parts.append(_safe_name(p["name"]).lower())
    if body_param is not None:
        sig_parts.append("data")
    for p in query_params:
        sig_parts.append(_safe_name(p["name"]).lower())
    sig_parts.append("extra_params")

    lines.append(f'def {func_name}({", ".join(sig_parts)}):')
    lines.append(f'    """{summary}"""')

    lines.append("    from cli_anything.mailchimp.core.client import get_client, MailchimpError")
    lines.append("    from cli_anything.mailchimp.utils.output import _out, _out_ok, _out_err")

    # Build path with lowercased path params
    url_parts = re.sub(
        r"\{([^}]+)\}",
        lambda m: "{" + _safe_name(m.group(1)).lower() + "}",
        path,
    )
    lines.append(f'    path = f"{url_parts}"')

    # Build query params dict
    if query_params:
        lines.append("    params = {k: v for k, v in {")
        for p in query_params:
            py_name = _safe_name(p["name"]).lower()
            lines.append(f'        "{p["name"]}": {py_name},')
        lines.append("    }.items() if v is not None}")
    else:
        lines.append("    params = {}")

    # Merge --extra-params
    lines.append("    if extra_params:")
    lines.append('        params.update(_parse_json_option(extra_params, "--extra-params", require_object=True))')

    # Parse body
    if body_param is not None:
        lines.append('    body = _parse_json_option(data, "--data") if data else None')

    # Make the request
    lines.append("    client = get_client()")
    lines.append("    try:")
    if method == "get":
        lines.append("        result = client.get(path, params=params or None)")
    elif method == "post":
        body_arg = "body" if body_param else "None"
        lines.append(f"        result = client.post(path, json={body_arg}, params=params or None)")
    elif method == "patch":
        body_arg = "body" if body_param else "None"
        lines.append(f"        result = client.patch(path, json={body_arg}, params=params or None)")
    elif method == "put":
        body_arg = "body" if body_param else "None"
        lines.append(f"        result = client.put(path, json={body_arg}, params=params or None)")
    elif method == "delete":
        lines.append("        result = client.delete(path, params=params or None)")
    else:
        lines.append("        result = client.get(path, params=params or None)")

    lines.append("    except MailchimpError as e:")
    lines.append("        _out_err(e.status, e.title, e.detail, e.raw)")
    lines.append("        return")

    if method == "delete":
        lines.append('    _out_ok("Deleted.")')
    else:
        lines.append("    _out(result)")

    lines.append("")
    return "\n".join(lines)


def _generate_module(tag: str, operations: list[tuple[str, str, dict]]) -> str:
    """Generate a complete Python module for a given tag."""
    module_name = _tag_to_module(tag)
    group_name = _tag_to_group(tag)
    group_var = f"{module_name}_group"

    group_decorator = f'@click.group("{group_name}")'
    group_signature = f"def {group_var}(ctx):"
    if tag.lower() == "ping":
        group_decorator = f'@click.group("{group_name}", invoke_without_command=True)'
    group_lines = [
        f'    """{_slugify(tag)} resource commands."""',
    ]
    if tag.lower() == "ping":
        group_lines.extend(
            [
                "    if ctx.invoked_subcommand is None:",
                "        ctx.invoke(_cmd_list_)",
            ]
        )

    header_lines = [
        f'"""Commands for the Mailchimp /{group_name} API resource.',
        "",
        "Auto-generated by cli_anything/mailchimp/_codegen/generate.py.",
        "Do not edit manually — re-run the generator to update.",
        '"""',
        "",
        "import json",
        "",
        "import click",
        "",
        "",
        "def _parse_json_option(value, option_name, require_object=False):",
        "    try:",
        "        parsed = json.loads(value)",
        "    except json.JSONDecodeError as exc:",
        "        raise click.BadParameter(",
        '            f"must be valid JSON ({exc.msg})",',
        "            param_hint=option_name,",
        "        ) from exc",
        "    if require_object and not isinstance(parsed, dict):",
        '        raise click.BadParameter("must be a JSON object", param_hint=option_name)',
        "    return parsed",
        "",
        "",
        group_decorator,
        "@click.pass_context",
        group_signature,
        *group_lines,
        "",
        "",
    ]
    header = "\n".join(header_lines)

    body_parts: list[str] = []
    # Track ALL assigned names (base + deduped) to guarantee uniqueness.
    assigned: set[str] = set()

    for method, path, operation in sorted(operations, key=lambda x: (x[1], x[0])):
        op_id = operation.get("operationId", "")
        cmd_name = _infer_command_name(method, path, op_id)

        # I4: De-duplicate using operationId slug; fall back to counter if still collides.
        if cmd_name in assigned:
            candidate = _dedup_suffix(cmd_name, path, op_id, 2)
            counter = 2
            while candidate in assigned:
                counter += 1
                candidate = f"{cmd_name}-{counter}"
            cmd_name = candidate

        assigned.add(cmd_name)

        operation = dict(operation)
        operation.setdefault("tags", [tag])

        path_params, query_params, body_param = _collect_params(operation, path)
        func_code = _generate_command_func(
            cmd_name, method, path, operation, path_params, query_params, body_param
        )
        body_parts.append(func_code)
        if tag.lower() == "campaigns" and cmd_name == "list-campaigns-id-content":
            body_parts.append('campaigns_group.add_command(_cmd_list_campaigns_id_content, "list-content")\n')
        if tag.lower() == "campaigns" and cmd_name == "list-campaigns-id-send-checklist":
            body_parts.append('campaigns_group.add_command(_cmd_list_campaigns_id_send_checklist, "list-send-checklist")\n')
        if tag.lower() == "reports" and cmd_name == "list-reports-id-click-details":
            body_parts.append('reports_group.add_command(_cmd_list_reports_id_click_details, "list-click-details")\n')
        if tag.lower() == "reports" and cmd_name == "list-reports-id-domain-performance":
            body_parts.append('reports_group.add_command(_cmd_list_reports_id_domain_performance, "list-domain-performance")\n')
        if tag.lower() == "reports" and cmd_name == "list-reports-id-email-activity":
            body_parts.append('reports_group.add_command(_cmd_list_reports_id_email_activity, "list-email-activity")\n')
        if tag.lower() == "reports" and cmd_name == "list-reports-id-locations":
            body_parts.append('reports_group.add_command(_cmd_list_reports_id_locations, "list-locations")\n')
        if tag.lower() == "reports" and cmd_name == "list-reports-id-open-details":
            body_parts.append('reports_group.add_command(_cmd_list_reports_id_open_details, "list-open-details")\n')
        if tag.lower() == "reports" and cmd_name == "list-reports-id-unsubscribed":
            body_parts.append('reports_group.add_command(_cmd_list_reports_id_unsubscribed, "list-unsubscribed")\n')
        if tag.lower() == "automations" and cmd_name == "list-automations-id-emails":
            body_parts.append('automations_group.add_command(_cmd_list_automations_id_emails, "list-emails")\n')
        if tag.lower() == "lists" and cmd_name == "create-lists-id-members":
            body_parts.append('lists_group.add_command(_cmd_create_lists_id_members, "create-members")\n')
        if tag.lower() == "lists" and cmd_name == "list-preview-a-segment":
            body_parts.append('lists_group.add_command(_cmd_list_preview_a_segment, "list-lists-id-segments")\n')

    return header + "\n".join(body_parts)


def load_spec(url: str = SPEC_URL) -> dict:
    print(f"Fetching spec from {url} ...", file=sys.stderr)
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


def generate(spec: dict, out_dir: Path = OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    by_tag: dict[str, list[tuple[str, str, dict]]] = defaultdict(list)

    for path, path_item in spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if method not in ("get", "post", "patch", "put", "delete"):
                continue
            if not isinstance(operation, dict):
                continue
            tags = operation.get("tags", ["misc"])
            tag = tags[0]
            if tag in _SKIP_TAGS:
                continue
            by_tag[tag].append((method, path, operation))

    generated: list[str] = []
    for tag, operations in sorted(by_tag.items()):
        module_name = _tag_to_module(tag)
        out_path = out_dir / f"{module_name}.py"
        code = _generate_module(tag, operations)
        out_path.write_text(code, encoding="utf-8")
        generated.append(module_name)
        print(f"  Generated {out_path.name} ({len(operations)} commands)", file=sys.stderr)

    # Write __init__.py that imports all groups
    init_lines = ['"""Auto-generated command groups for cli-anything-mailchimp."""', ""]
    for mod in sorted(generated):
        group_var = f"{mod}_group"
        init_lines.append(f"from cli_anything.mailchimp.commands.{mod} import {group_var}")
    init_lines.append("")
    init_lines.append("ALL_GROUPS = [")
    for mod in sorted(generated):
        group_var = f"{mod}_group"
        init_lines.append(f"    {group_var},")
    init_lines.append("]")
    init_lines.append("")

    (out_dir / "__init__.py").write_text("\n".join(init_lines), encoding="utf-8")
    print(f"\nDone — {len(generated)} modules written to {out_dir}", file=sys.stderr)


if __name__ == "__main__":
    spec = load_spec()
    generate(spec)
