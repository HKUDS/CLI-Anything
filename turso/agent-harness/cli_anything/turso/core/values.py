"""Typed JSON values and the small, parameterized CRUD command language."""
import json
import math


class TursoError(RuntimeError):
    def __init__(self, message, *, operation_index=None):
        super().__init__(message)
        self.operation_index = operation_index


def parse_json(text):
    try:
        return json.loads(text, parse_constant=lambda value: _invalid(value))
    except (ValueError, TypeError) as exc:
        raise TursoError(f"Invalid JSON: {exc}") from exc


def _invalid(value):
    raise ValueError(f"non-finite number: {value}")


def bind_value(value):
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int) and -(2**63) <= value < 2**63:
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    if isinstance(value, dict) and set(value) == {"$blob"}:
        try:
            return bytes.fromhex(value["$blob"])
        except (ValueError, TypeError) as exc:
            raise TursoError("$blob must contain a hexadecimal string") from exc
    raise TursoError("Values must be NULL, text, boolean, finite float, signed 64-bit integer, or {$blob: hex}")


def parameters(value):
    if isinstance(value, list):
        return [bind_value(v) for v in value]
    if isinstance(value, dict):
        return {k: bind_value(v) for k, v in value.items()}
    raise TursoError("Parameters must be a JSON array or object")


def json_value(value):
    if isinstance(value, bytes):
        return {"$blob": value.hex()}
    if isinstance(value, float) and not math.isfinite(value):
        return {"$float": str(value)}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    if isinstance(value, dict):
        return {k: json_value(v) for k, v in value.items()}
    return value


def identifier(name):
    if not isinstance(name, str) or not name or "\x00" in name:
        raise TursoError("Identifier must be nonempty text without NUL")
    return '"' + name.replace('"', '""') + '"'


def object_values(value, label, *, allow_empty=False):
    if not isinstance(value, dict) or (not value and not allow_empty):
        raise TursoError(f"{label} must be a {'possibly empty' if allow_empty else 'nonempty'} JSON object")
    for key, val in value.items():
        identifier(key)
        bind_value(val)
    return value


def predicate(where):
    object_values(where, "where", allow_empty=True)
    parts, values = [], []
    for key, val in where.items():
        if val is None:
            parts.append(f"{identifier(key)} IS NULL")
        else:
            parts.append(f"{identifier(key)} = ?")
            values.append(bind_value(val))
    return (" WHERE " + " AND ".join(parts) if parts else ""), values


def compile_operation(op):
    if not isinstance(op, dict):
        raise TursoError("Each operation must be a JSON object")
    kind = op.get("op")
    allowed = {"insert": {"op", "table", "values"},
               "update": {"op", "table", "values", "where", "all"},
               "delete": {"op", "table", "where", "all"}}
    if kind not in allowed or set(op) - allowed[kind]:
        raise TursoError("Operation requires op=insert/update/delete and only its documented fields")
    table = identifier(op.get("table"))
    values = []
    if kind in {"insert", "update"}:
        fields = object_values(op.get("values"), "values")
        values = [bind_value(v) for v in fields.values()]
        if kind == "insert":
            columns = ", ".join(identifier(k) for k in fields)
            return f"INSERT INTO {table} ({columns}) VALUES ({', '.join('?' for _ in fields)})", values
        sql = f"UPDATE {table} SET " + ", ".join(f"{identifier(k)} = ?" for k in fields)
    else:
        sql = f"DELETE FROM {table}"
    where = op.get("where", {})
    if not isinstance(op.get("all", False), bool):
        raise TursoError("all must be a boolean")
    if where and op.get("all"):
        raise TursoError("Use either where or all=true")
    if not where and op.get("all") is not True:
        raise TursoError("Update/delete require nonempty where or explicit all=true")
    suffix, bound = predicate(where)
    return sql + suffix, values + bound


def sql_parameters(sql, supplied):
    """Validate/resolve supported placeholders, ignoring SQL literals/comments.

    pyturso 0.8.3 leaves missing binds NULL and only binds one prefix per mapping
    key. Normalize to positional slots instead. This is parameter handling only,
    not a SQL parser, permission check, or confinement mechanism. Extended Tcl
    $parameter forms are intentionally unsupported.
    """
    slots, named, highest, i = {}, {}, 0, 0
    while i < len(sql):
        ch = sql[i]
        if sql.startswith("--", i):
            end = sql.find("\n", i + 2)
            i = len(sql) if end < 0 else end + 1
            continue
        if sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = len(sql) if end < 0 else end + 2
            continue
        if ch in "'\"`[":
            closing = "]" if ch == "[" else ch
            i += 1
            while i < len(sql):
                if sql[i] == closing:
                    i += 1
                    if closing != "]" and i < len(sql) and sql[i] == closing:
                        i += 1
                        continue
                    break
                i += 1
            continue
        if ch == "?":
            end = i + 1
            while end < len(sql) and sql[end].isascii() and sql[end].isdigit():
                end += 1
            key = sql[i + 1:end] or None
            index = int(key) if key else highest + 1
            if not 1 <= index <= 32766:
                raise TursoError("Parameter index must be between 1 and 32766")
            highest = max(highest, index)
            slots.setdefault(index, key)
            i = end
            continue
        if ch in ":@$" and i + 1 < len(sql) and (sql[i + 1].isalnum() or sql[i + 1] == "_"):
            end = i + 1
            while end < len(sql) and (sql[end].isalnum() or sql[end] == "_"):
                end += 1
            if end < len(sql) and (sql[end] == "$" or (ch == "$" and (sql.startswith("::", end) or sql[end] == "("))):
                raise TursoError("Extended parameter names are unsupported; use simple names or positional ?")
            token = sql[i:end]
            if token not in named:
                highest += 1
                named[token] = highest
            slots[named[token]] = token[1:]
            i = end
            continue
        i += 1
    if isinstance(supplied, dict):
        if any(key is None for key in slots.values()):
            raise TursoError("Anonymous ? parameters require a positional JSON array")
        missing = set(slots.values()) - set(supplied)
        if missing:
            raise TursoError(f"Missing named parameters: {', '.join(sorted(missing))}")
        values = [None] * highest
        for index, key in slots.items():
            values[index - 1] = supplied[key]
        return values
    if len(supplied) != highest:
        raise TursoError(f"Expected {highest} positional parameters; received {len(supplied)}")
    return supplied
