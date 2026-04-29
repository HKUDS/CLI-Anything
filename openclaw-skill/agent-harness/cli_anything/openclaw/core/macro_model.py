"""Macro data model — parse and validate YAML macro definitions.

A macro definition file (YAML) describes a reusable, parameterized workflow
that the MacroRuntime can execute against any backend.

Example (minimal):

    name: export_file
    version: "1.0"
    description: Export a file using the target app's CLI.

    parameters:
      output:
        type: string
        required: true
        example: /tmp/out.png

    steps:
      - backend: native_api
        action: run_command
        params:
          command: [echo, "exported", "${output}"]

    postconditions:
      - file_exists: ${output}
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError as e:
    raise ImportError("PyYAML is required: pip install PyYAML") from e


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class MacroParameter:
    name: str
    type: str = "string"            # string | integer | boolean | list | dict
    required: bool = False
    default: Any = None
    description: str = ""
    example: Any = None
    enum: Optional[list] = None
    min: Optional[float] = None
    max: Optional[float] = None

    def validate_value(self, value: Any) -> list[str]:
        """Return list of validation error strings (empty if valid)."""
        errors: list[str] = []
        if value is None:
            if self.required:
                errors.append(f"Parameter '{self.name}' is required.")
            return errors

        if self.type == "integer":
            if not isinstance(value, int):
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    errors.append(f"Parameter '{self.name}' must be an integer.")
                    return errors
            if self.min is not None and value < self.min:
                errors.append(f"Parameter '{self.name}' must be >= {self.min}.")
            if self.max is not None and value > self.max:
                errors.append(f"Parameter '{self.name}' must be <= {self.max}.")

        if self.enum and value not in self.enum:
            errors.append(
                f"Parameter '{self.name}' must be one of {self.enum}, got {value!r}."
            )
        return errors


@dataclass
class MacroStep:
    backend: str                    # native_api | file_transform | semantic_ui | gui_macro | recovery
    action: str                     # backend-specific action name
    id: str = ""
    params: dict = field(default_factory=dict)
    timeout_ms: int = 30_000
    on_failure: str = "fail"        # fail | skip | continue
    retry_max: int = 0
    retry_backoff_ms: list[int] = field(default_factory=lambda: [1000])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "backend": self.backend,
            "action": self.action,
            "params": self.params,
            "timeout_ms": self.timeout_ms,
            "on_failure": self.on_failure,
            "retry_max": self.retry_max,
            "retry_backoff_ms": self.retry_backoff_ms,
        }


@dataclass
class MacroCondition:
    """A single pre- or post-condition check.

    Supported types (derived from the YAML key):
      file_exists: <path>
      file_size_gt: [<path>, <bytes>]
      process_running: <name>
      env_var: <name>
      always: true | false
    """
    type: str
    args: Any           # depends on type

    def to_dict(self) -> dict:
        return {"type": self.type, "args": self.args}

    @classmethod
    def from_dict(cls, d: dict) -> "MacroCondition":
        """Parse a condition dict like {file_exists: /tmp/out.png}."""
        if not isinstance(d, dict) or len(d) != 1:
            raise ValueError(f"Condition must be a single-key dict, got: {d!r}")
        ctype, args = next(iter(d.items()))
        return cls(type=ctype, args=args)


@dataclass
class MacroOutput:
    name: str
    description: str = ""
    path: Optional[str] = None      # raw template string (may contain ${...})
    value: Optional[Any] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "path": self.path,
            "value": self.value,
        }


@dataclass
class MacroDefinition:
    name: str
    version: str = "1.0"
    description: str = ""
    parameters: dict[str, MacroParameter] = field(default_factory=dict)
    preconditions: list[MacroCondition] = field(default_factory=list)
    steps: list[MacroStep] = field(default_factory=list)
    postconditions: list[MacroCondition] = field(default_factory=list)
    outputs: list[MacroOutput] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    composable: bool = False
    agent_hints: dict = field(default_factory=dict)
    source_path: str = ""           # absolute path to the .yaml file

    # ── Validation ────────────────────────────────────────────────────

    def validate(self) -> list[str]:
        """Structural validation — returns list of error strings."""
        errors: list[str] = []
        if not self.name:
            errors.append("Macro name is required.")
        if not self.steps:
            errors.append(f"Macro '{self.name}' has no steps.")
        valid_backends = {"native_api", "file_transform", "semantic_ui", "gui_macro", "recovery"}
        for i, step in enumerate(self.steps):
            if step.backend not in valid_backends:
                errors.append(
                    f"Step {i} has unknown backend '{step.backend}'. "
                    f"Valid: {sorted(valid_backends)}"
                )
            if not step.action:
                errors.append(f"Step {i} (backend={step.backend}) is missing 'action'.")
        for pname, pspec in self.parameters.items():
            if pspec.type not in ("string", "integer", "boolean", "list", "dict", "float"):
                errors.append(f"Parameter '{pname}' has unknown type '{pspec.type}'.")
        return errors

    def validate_params(self, params: dict) -> list[str]:
        """Validate runtime parameter values against schema."""
        errors: list[str] = []
        for pname, pspec in self.parameters.items():
            value = params.get(pname, pspec.default)
            errors.extend(pspec.validate_value(value))
        return errors

    def resolve_params(self, params: dict) -> dict:
        """Return params with defaults filled in."""
        resolved = {}
        for pname, pspec in self.parameters.items():
            resolved[pname] = params.get(pname, pspec.default)
        # Pass through any extra params not in schema
        for k, v in params.items():
            if k not in resolved:
                resolved[k] = v
        return resolved

    # ── Serialisation ─────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "parameters": {
                n: {
                    "type": p.type,
                    "required": p.required,
                    "default": p.default,
                    "description": p.description,
                    "example": p.example,
                    "enum": p.enum,
                }
                for n, p in self.parameters.items()
            },
            "preconditions": [c.to_dict() for c in self.preconditions],
            "steps": [s.to_dict() for s in self.steps],
            "postconditions": [c.to_dict() for c in self.postconditions],
            "outputs": [o.to_dict() for o in self.outputs],
            "tags": self.tags,
            "composable": self.composable,
            "agent_hints": self.agent_hints,
            "source_path": self.source_path,
        }


# ── Substitution ─────────────────────────────────────────────────────────────

_SUBST_RE = re.compile(r"\$\{([^}]+)\}")


def substitute(template: Any, params: dict) -> Any:
    """Replace ${key} placeholders in strings (and nested structures).

    Works recursively on strings, lists, and dicts.
    Leaves non-string types (int, bool, None) untouched.
    """
    if isinstance(template, str):
        def _replace(m: re.Match) -> str:
            key = m.group(1).strip()
            val = params.get(key)
            return str(val) if val is not None else m.group(0)
        return _SUBST_RE.sub(_replace, template)
    if isinstance(template, list):
        return [substitute(item, params) for item in template]
    if isinstance(template, dict):
        return {k: substitute(v, params) for k, v in template.items()}
    return template


# ── YAML loader ───────────────────────────────────────────────────────────────

def _parse_parameter(name: str, raw: dict) -> MacroParameter:
    return MacroParameter(
        name=name,
        type=raw.get("type", "string"),
        required=raw.get("required", False),
        default=raw.get("default"),
        description=raw.get("description", ""),
        example=raw.get("example"),
        enum=raw.get("enum"),
        min=raw.get("min"),
        max=raw.get("max"),
    )


def _parse_step(i: int, raw: dict) -> MacroStep:
    retry = raw.get("retry_policy", {}) or {}
    return MacroStep(
        id=raw.get("id", f"step_{i}"),
        backend=raw.get("backend", "native_api"),
        action=raw.get("action", ""),
        params=raw.get("params", {}),
        timeout_ms=int(raw.get("timeout_ms", raw.get("timeout", "30s")
                                .replace("s", "000") if isinstance(raw.get("timeout"), str)
                                else raw.get("timeout_ms", 30_000))),
        on_failure=raw.get("on_failure", "fail"),
        retry_max=retry.get("max_retries", raw.get("retry_max", 0)),
        retry_backoff_ms=retry.get("backoff_ms", [1000]),
    )


def _parse_condition(raw: Any) -> MacroCondition:
    if isinstance(raw, dict):
        return MacroCondition.from_dict(raw)
    raise ValueError(f"Cannot parse condition from {raw!r}")


def _parse_output(raw: dict) -> MacroOutput:
    return MacroOutput(
        name=raw.get("name", ""),
        description=raw.get("description", ""),
        path=raw.get("path"),
        value=raw.get("value"),
    )


def load_from_yaml(path: str) -> MacroDefinition:
    """Load and parse a macro definition from a YAML file."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Macro file not found: {path}")
    with open(p, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"Macro YAML must be a mapping, got {type(raw).__name__}: {path}")

    parameters: dict[str, MacroParameter] = {}
    for pname, praw in (raw.get("parameters") or {}).items():
        if isinstance(praw, dict):
            parameters[pname] = _parse_parameter(pname, praw)
        else:
            # shorthand: parameter_name: string
            parameters[pname] = MacroParameter(name=pname, type=str(praw))

    steps = [_parse_step(i, s) for i, s in enumerate(raw.get("steps") or [])]
    preconditions = [_parse_condition(c) for c in (raw.get("preconditions") or [])]
    postconditions = [_parse_condition(c) for c in (raw.get("postconditions") or [])]
    outputs = [_parse_output(o) for o in (raw.get("outputs") or [])]

    macro = MacroDefinition(
        name=raw.get("name", p.stem),
        version=str(raw.get("version", "1.0")),
        description=raw.get("description", ""),
        parameters=parameters,
        preconditions=preconditions,
        steps=steps,
        postconditions=postconditions,
        outputs=outputs,
        tags=raw.get("tags", []),
        composable=raw.get("composable", False),
        agent_hints=raw.get("agent_hints", {}),
        source_path=str(p.resolve()),
    )
    return macro
