"""n8n expression validator — check expression syntax offline.

Based on n8n expression syntax rules from documentation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ExpressionResult:
    valid: bool
    expression: str
    issues: list[str]
    warnings: list[str]


MAX_EXPR_LENGTH = 100_000


def validate_expression(expr: str) -> ExpressionResult:
    """Validate an n8n expression string."""
    if len(expr) > MAX_EXPR_LENGTH:
        return ExpressionResult(False, expr[:100], [f"Expression too long ({len(expr)} chars, max {MAX_EXPR_LENGTH})"], [])

    issues: list[str] = []
    warnings: list[str] = []

    # Must start with = for dynamic expressions in n8n fields
    if not expr.startswith("="):
        if "{{" in expr:
            warnings.append("Expression should start with '=' prefix for n8n fields (e.g., ={{$json.name}})")

    # Check brace matching
    inner = expr.lstrip("=")
    open_count = inner.count("{{")
    close_count = inner.count("}}")
    if open_count != close_count:
        issues.append(f"Mismatched braces: {open_count} opening '{{{{' vs {close_count} closing '}}}}'")

    # Check for single braces (common mistake)
    single_open = inner.count("{") - inner.count("{{") * 2
    single_close = inner.count("}") - inner.count("}}") * 2
    if single_open > 0 or single_close > 0:
        warnings.append("Found single braces {{ or }} — n8n expressions use double braces {{}}")

    # Extract expressions inside {{ }}
    expressions = re.findall(r"\{\{(.*?)\}\}", inner, re.DOTALL)

    for i, exp in enumerate(expressions):
        exp = exp.strip()

        # Check for common n8n variables and valid JS globals
        valid_prefixes = ("$json", "$node", "$input", "$binary", "$env", "$now", "$today",
                         "$workflow", "$execution", "$prevNode", "$runIndex", "$itemIndex",
                         "$parameter", "$position", "$fromAI", "$if", "$ifEmpty",
                         "Math.", "Date.", "Object.", "Array.", "JSON.", "String.",
                         "Number.", "parseInt", "parseFloat", "encodeURI", "decodeURI",
                         "btoa", "atob", "DateTime", "true", "false", "null", "undefined",
                         "new ", "typeof ", "instanceof ")

        # Check for common mistakes
        if "$json[" in exp and "'" not in exp and '"' not in exp:
            issues.append(f"$json[] needs quotes around key: $json['key'] not $json[key]")

        if '$node["' in exp and '"].json' not in exp and '"].first()' not in exp:
            warnings.append(f"$node reference may be incomplete — usually needs .json.field or .first().json.field")

        # Check $fromAI usage
        if "$fromAI" in exp:
            if "(" not in exp:
                issues.append("$fromAI needs parentheses: $fromAI('fieldName', 'description', 'type')")

    return ExpressionResult(
        valid=len(issues) == 0,
        expression=expr,
        issues=issues,
        warnings=warnings,
    )
