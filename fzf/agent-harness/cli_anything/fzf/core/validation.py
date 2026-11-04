"""Validation for fzf's declarative option and binding grammar."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from cli_anything.fzf.core.capabilities import (
    all_action_names,
    load_capabilities,
    resolve_option,
    subprocess_actions,
)
from cli_anything.fzf.core.errors import PolicyError, ValidationError


MAX_VALUE_LENGTH = 65_536
_FIELD = re.compile(r"(?:-?[1-9]\d*|(?:-?[1-9]\d*)?\.\.(?:-?[1-9]\d*)?)\Z")
_LABEL_POS = re.compile(r"(?:center|-?\d+)(?::(?:top|bottom))?\Z")
_HEIGHT = re.compile(r"~?-?(?:\d+|\d+%)\Z")
_MIN_HEIGHT = re.compile(r"\d+\+?\Z")
_DIMENSION = re.compile(r"\d+(?:\.\d+)?%?\Z")
_DURATION = re.compile(r"(?:\d+(?:\.\d+)?)(?:ns|us|ms|s|m|h)\Z")
_BORDER = {
    "rounded", "sharp", "bold", "block", "thinblock", "double", "dashed",
    "horizontal", "vertical", "top", "up", "bottom", "down", "left", "right",
    "line", "none",
}
_COLOR_NAMES = {
    "fg", "list-fg", "selected-fg", "preview-fg", "bg", "list-bg", "selected-bg",
    "preview-bg", "input-bg", "header-bg", "footer-bg", "hl", "selected-hl",
    "current-fg", "fg+", "current-bg", "bg+", "gutter", "current-hl", "hl+",
    "alt-bg", "alt-gutter", "query", "input-fg", "ghost", "disabled", "info",
    "border", "list-border", "scrollbar", "separator", "gap-line", "preview-border",
    "preview-scrollbar", "input-border", "header-border", "footer-border", "label",
    "list-label", "preview-label", "input-label", "header-label", "footer-label",
    "prompt", "pointer", "marker", "spinner", "header", "header-fg", "footer",
    "footer-fg", "nth", "nomatch",
}
_COLOR_ATTRIBUTES = {
    "regular", "strip", "bold", "underline", "underline-double", "underline-curly",
    "underline-dotted", "underline-dashed", "reverse", "dim", "italic", "strikethrough",
}
_TRIGGERS = set(load_capabilities()["events"])
_NAMED_KEYS = set(load_capabilities()["key_grammar"]["named"])
_ACTION_NAME = re.compile(r"[a-z][a-z0-9]*(?:[/-][a-z0-9]+)*")
_ACTION_PAIRS = {"(": ")", "[": "]", "{": "}", "<": ">"}
_ACTION_DELIMITERS = set(_ACTION_PAIRS) | set("~!@#$%^&*;/|")


@dataclass(frozen=True)
class Policy:
    """Explicit grants for effects that are denied by default."""

    allow_command_actions: bool = False
    allow_filesystem_write: bool = False
    allow_walker: bool = False
    allow_broad_walker: bool = False
    allow_network_listener: bool = False
    allow_unsafe_listener: bool = False
    allow_env_inherit: bool = False
    allow_default_opts_file: bool = False
    allow_unknown_options: bool = False

    def grants(self) -> list[str]:
        return [
            name.replace("_", "-")
            for name, enabled in self.__dict__.items()
            if enabled
        ]


@dataclass(frozen=True)
class OptionValue:
    """A resolved fzf option and its optional value."""

    name: str
    value: str | None
    spec: dict
    source: str = "command-line"

    def argv_token(self) -> str:
        if self.value is None:
            return f"--{self.name}"
        return f"--{self.name}={self.value}"


def _text(value: str) -> None:
    if "\x00" in value:
        raise ValidationError("option_value_invalid", "Option values cannot contain NUL bytes")
    if len(value) > MAX_VALUE_LENGTH:
        raise ValidationError(
            "option_value_too_large",
            f"Option value exceeds {MAX_VALUE_LENGTH} characters",
        )


def _integer(value: str, *, minimum: int) -> None:
    if not re.fullmatch(r"\d+", value) or int(value) < minimum:
        kind = "positive" if minimum == 1 else "non-negative"
        raise ValidationError("option_value_invalid", f"Expected a {kind} integer, got {value!r}")


def _field_expression_list(value: str) -> None:
    if not value:
        raise ValidationError("option_value_invalid", "Field expression cannot be empty")
    for part in value.split(","):
        if not _FIELD.fullmatch(part.strip()):
            raise ValidationError("option_value_invalid", f"Malformed field expression: {part!r}")


def _field_template(value: str) -> None:
    _text(value)
    if "{" not in value:
        _field_expression_list(value)
        return
    if value.count("{") != value.count("}"):
        raise ValidationError("option_value_invalid", "Unbalanced field-template braces")
    for expression in re.findall(r"\{([^{}]+)\}", value):
        if expression == "n":
            continue
        _field_expression_list(expression)


def _regex(value: str) -> None:
    _text(value)
    unsupported = ("(?<=", "(?<!", "(?P", "\\1", "\\2", "\\k")
    if any(token in value for token in unsupported):
        raise ValidationError(
            "option_value_invalid",
            "Delimiter uses constructs unsupported by fzf's regular-expression engine",
        )
    try:
        re.compile(value)
    except re.error as exc:
        raise ValidationError("option_value_invalid", f"Invalid delimiter regex: {exc}") from exc


def _box_dimensions(value: str) -> None:
    parts = value.split(",")
    if len(parts) not in {1, 2, 3, 4} or not all(_DIMENSION.fullmatch(part) for part in parts):
        raise ValidationError("option_value_invalid", f"Malformed box dimensions: {value!r}")


def _color(value: str) -> None:
    _text(value)
    if not value.strip() or any(ord(ch) < 32 for ch in value):
        raise ValidationError("option_value_invalid", "Color specification is empty or contains control characters")
    bases = {"dark", "light", "base16", "16", "bw", "no"}
    ansi_color = re.compile(r"(?:#[0-9a-fA-F]{6}|-?\d+|[a-z-]+)?\Z")
    for index, item in enumerate(re.split(r"[,\s]+", value.strip())):
        if not item:
            continue
        if index == 0 and item in bases:
            continue
        fields = item.split(":")
        if fields[0] not in _COLOR_NAMES or len(fields) < 2:
            raise ValidationError("option_value_invalid", f"Malformed color entry: {item!r}")
        if not ansi_color.fullmatch(fields[1]):
            raise ValidationError("option_value_invalid", f"Malformed ANSI color: {fields[1]!r}")
        if any(attribute not in _COLOR_ATTRIBUTES for attribute in fields[2:]):
            raise ValidationError("option_value_invalid", f"Malformed ANSI attributes: {item!r}")


def _key(value: str) -> bool:
    if value in _NAMED_KEYS or len(value) == 1:
        return True
    if value.startswith("alt-") and len(value.removeprefix("alt-")) == 1:
        return value[-1].isprintable()
    return bool(
        re.fullmatch(r"(?:ctrl|alt|shift)(?:-(?:ctrl|alt|shift))*-(?:[a-z]|6|\\|\]|\^|/|_|delete|backspace|"
                     r"up|down|left|right|home|end|page-up|page-down)", value)
        or re.fullmatch(r"f(?:[1-9]|1[0-2])", value)
    )


def _event(value: str) -> bool:
    if value in _TRIGGERS:
        return True
    match = re.fullmatch(r"every\((\d+(?:\.\d+)?)\)", value)
    return bool(match and float(match.group(1)) >= 0.01)


def _find_top_level_colon(value: str) -> int:
    pairs = {"(": ")", "[": "]", "{": "}", "<": ">"}
    stack: list[str] = []
    for index, char in enumerate(value):
        if char in pairs:
            stack.append(pairs[char])
        elif stack and char == stack[-1]:
            stack.pop()
        elif char == ":" and not stack:
            return index
    return -1


def binding_actions(binding: str) -> list[str]:
    """Return action names from one structured binding expression."""

    _text(binding)
    colon = _find_top_level_colon(binding)
    if colon <= 0 or colon == len(binding) - 1:
        raise ValidationError(
            "binding_invalid",
            "Binding must be one KEY[,KEY...]:ACTION expression; repeat --bind for more",
        )
    triggers = [part.strip() for part in binding[:colon].split(",")]
    if not all(_key(trigger) or _event(trigger) for trigger in triggers):
        bad = [trigger for trigger in triggers if not (_key(trigger) or _event(trigger))]
        raise ValidationError("binding_invalid", "Unknown binding key or event", details={"values": bad})

    action_text = binding[colon + 1 :]
    actions: list[str] = []
    index = 0
    if action_text.startswith("+"):
        # fzf accepts `KEY:+ACTION` to append to an existing binding.
        index = 1
    while index < len(action_text):
        match = _ACTION_NAME.match(action_text, index)
        if match is None:
            raise ValidationError(
                "binding_invalid",
                "Malformed action composition",
                details={"offset": index},
            )
        actions.append(match.group())
        index = match.end()
        if index < len(action_text) and action_text[index] in _ACTION_DELIMITERS:
            opener = action_text[index]
            closer = _ACTION_PAIRS.get(opener, opener)
            depth = 1
            index += 1
            while index < len(action_text) and depth:
                char = action_text[index]
                if opener in _ACTION_PAIRS and char == opener:
                    depth += 1
                elif char == closer:
                    depth -= 1
                index += 1
            if depth:
                raise ValidationError("binding_invalid", f"Unclosed action delimiter {opener!r}")
        elif index < len(action_text) and action_text[index] == ":":
            # The colon form consumes the remainder and must be last.
            index = len(action_text)
        if index == len(action_text):
            break
        if action_text[index] != "+":
            raise ValidationError(
                "binding_invalid",
                "Actions must be joined with '+'",
                details={"offset": index},
            )
        index += 1
        if index == len(action_text):
            raise ValidationError("binding_invalid", "Binding cannot end with '+'")
    known = all_action_names()
    unknown = [name for name in actions if name not in known and not name.startswith("bg-transform")]
    if unknown:
        raise ValidationError("binding_invalid", "Unknown fzf action", details={"actions": unknown})
    return actions


def binding_is_hazardous(binding: str) -> bool:
    """Return whether a binding can start or indirectly trigger a command."""

    actions = binding_actions(binding)
    return any(action in subprocess_actions() or action.startswith("bg-transform") for action in actions)


def validate_value(validator: str, value: str) -> None:
    """Validate one option value using a named capability validator."""

    _text(value)
    if validator.startswith("enum:"):
        choices = validator.removeprefix("enum:").split(",")
        if value not in choices:
            raise ValidationError(
                "option_value_invalid", f"Expected one of {', '.join(choices)}, got {value!r}"
            )
    elif validator == "positive-integer":
        _integer(value, minimum=1)
    elif validator == "nonnegative-integer":
        _integer(value, minimum=0)
    elif validator == "field-expression-list":
        _field_expression_list(value)
    elif validator == "field-template":
        _field_template(value)
    elif validator == "regex":
        _regex(value)
    elif validator == "tiebreak":
        values = value.split(",")
        allowed = {"length", "chunk", "pathname", "begin", "end", "index"}
        if not values or set(values) - allowed or len(values) != len(set(values)):
            raise ValidationError("option_value_invalid", f"Malformed tiebreak list: {value!r}")
        if "index" in values and values[-1] != "index":
            raise ValidationError("option_value_invalid", "tiebreak 'index' is only allowed last")
    elif validator == "height":
        if not _HEIGHT.fullmatch(value):
            raise ValidationError("option_value_invalid", f"Malformed height: {value!r}")
    elif validator == "min-height":
        if not _MIN_HEIGHT.fullmatch(value):
            raise ValidationError("option_value_invalid", f"Malformed minimum height: {value!r}")
    elif validator == "box-dimensions":
        _box_dimensions(value)
    elif validator in {"border-style", "border-style-inline", "border-style-no-line"}:
        allowed = set(_BORDER)
        if validator == "border-style-inline":
            allowed.add("inline")
        if validator == "border-style-no-line":
            allowed.discard("line")
        if value not in allowed:
            raise ValidationError("option_value_invalid", f"Unknown border style: {value!r}")
    elif validator == "label-position":
        if not _LABEL_POS.fullmatch(value):
            raise ValidationError("option_value_invalid", f"Malformed label position: {value!r}")
    elif validator == "style":
        if not re.fullmatch(r"(?:default|minimal|full(?::[a-z]+)?)", value):
            raise ValidationError("option_value_invalid", f"Malformed style preset: {value!r}")
    elif validator == "color":
        _color(value)
    elif validator == "info-style":
        if not re.fullmatch(r"(?:default|right|hidden|inline(?:-right)?(?::[^\x00\r\n]*)?)", value):
            raise ValidationError("option_value_invalid", f"Malformed info style: {value!r}")
    elif validator == "popup":
        if not re.fullmatch(
            r"(?:center|top|bottom|left|right)?(?:,?\d+%?){0,2}(?:,border-native)?", value
        ):
            raise ValidationError("option_value_invalid", f"Malformed popup layout: {value!r}")
    elif validator == "preview-window":
        if not value or any(ord(ch) < 32 for ch in value) or value.count("(") != value.count(")"):
            raise ValidationError("option_value_invalid", f"Malformed preview window: {value!r}")
    elif validator == "duration":
        if not _DURATION.fullmatch(value):
            raise ValidationError("option_value_invalid", f"Malformed duration: {value!r}")
    elif validator == "walker":
        parts = value.split(",")
        if not parts or set(parts) - {"file", "dir", "follow", "hidden"} or len(parts) != len(set(parts)):
            raise ValidationError("option_value_invalid", f"Malformed walker options: {value!r}")
    elif validator == "key-list":
        if not value or not all(_key(part) for part in value.split(",")):
            raise ValidationError("option_value_invalid", f"Malformed key list: {value!r}")
    elif validator == "bindings":
        binding_actions(value)
    elif validator == "name-list":
        if not value or any(not part or "/" in part or "\\" in part for part in value.split(",")):
            raise ValidationError("option_value_invalid", f"Malformed directory-name list: {value!r}")
    elif validator == "characters":
        if not value or len(set(value)) != len(value):
            raise ValidationError("option_value_invalid", "Character list must be non-empty and unique")
    elif validator in {"path", "text", "command"}:
        pass
    elif validator == "listen-address":
        validate_listen_address(value)
    elif validator != "flag":
        raise ValidationError("capability_schema_invalid", f"Unknown validator: {validator}")


def parse_option(raw: str, *, source: str = "command-line") -> OptionValue:
    """Parse one `NAME[=VALUE]` declarative option."""

    _text(raw)
    name, separator, value = raw.partition("=")
    spec = resolve_option(name)
    if spec is None:
        raise ValidationError("option_unknown", f"Unknown fzf option: {name!r}")
    arity = spec["arity"]
    if arity == "none" and separator:
        raise ValidationError("option_value_unexpected", f"--{spec['name']} does not take a value")
    if arity == "required" and not separator:
        raise ValidationError("option_value_required", f"--{spec['name']} requires a value")
    parsed_value = value if separator else None
    if parsed_value is not None:
        validate_value(spec["validator"], parsed_value)
    return OptionValue(spec["name"], parsed_value, spec, source)


def parse_expert_option(raw: str, policy: Policy) -> OptionValue:
    """Parse one explicitly authorized, unknown long-option token.

    The escape hatch cannot express positional arguments, short-option bundles,
    separate argument tokens, listener flags, or known options that should have
    gone through their normal validator.
    """

    if not policy.allow_unknown_options:
        raise PolicyError(
            "unknown_options_denied",
            "Unknown backend options require --allow-unknown-options",
        )
    _text(raw)
    if not re.fullmatch(r"--[a-z][a-z0-9-]*(?:=[^\x00\r\n]*)?", raw):
        raise ValidationError(
            "expert_option_invalid",
            "Expert options must be one --long-name or --long-name=value token",
        )
    name, separator, value = raw[2:].partition("=")
    if resolve_option(name):
        raise ValidationError("expert_option_known", f"Use --option for known option --{name}")
    if name in {"listen", "listen-unsafe"}:
        raise PolicyError("managed_listener_required", "Listener options require the listener command group")
    spec = {
        "name": name,
        "aliases": [],
        "category": "forward-compatibility",
        "arity": "optional",
        "validator": "unverified",
        "repeatable": True,
        "effects": ["subprocess_capable"],
        "policy": "allow-unknown-options",
        "coverage": "refused-with-rationale",
        "surface": "expert-option",
    }
    return OptionValue(name, value if separator else None, spec, "expert-option")


def validate_listen_address(value: str) -> dict[str, str | int | bool]:
    """Parse a socket path or TCP listen address without opening it."""

    _text(value)
    if value.endswith(".sock"):
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise ValidationError("listener_address_invalid", "Unix socket path must be absolute")
        # Keep the lexical path so callers can detect an existing or dangling
        # symlink before containment resolution follows it.
        return {"kind": "unix", "path": str(path.absolute()), "loopback": True}
    host = "127.0.0.1"
    port_text = value
    if value.startswith("["):
        match = re.fullmatch(r"\[([^]]+)]:(\d+)", value)
        if not match:
            raise ValidationError("listener_address_invalid", f"Malformed IPv6 address: {value!r}")
        host, port_text = match.groups()
    elif ":" in value:
        host, port_text = value.rsplit(":", 1)
    if not re.fullmatch(r"\d+", port_text):
        raise ValidationError("listener_address_invalid", f"Malformed TCP port: {port_text!r}")
    port = int(port_text)
    if not 0 <= port <= 65535:
        raise ValidationError("listener_address_invalid", "TCP port must be between 0 and 65535")
    loopback = host in {"", "localhost", "127.0.0.1", "::1"}
    return {"kind": "tcp", "host": host or "127.0.0.1", "port": port, "loopback": loopback}


def validate_option_set(options: Iterable[OptionValue], policy: Policy, *, surface: str) -> dict:
    """Validate duplicates, surfaces, and default-deny policies."""

    seen: dict[str, str] = {}
    effects: set[str] = set()
    hazards: list[dict[str, str]] = []
    refusals: list[dict[str, str]] = []
    for option in options:
        spec = option.spec
        if (
            option.name in seen
            and seen[option.name] == option.source
            and not spec.get("repeatable", False)
        ):
            raise ValidationError("option_duplicate", f"--{option.name} cannot be repeated")
        seen[option.name] = option.source
        effects.update(spec.get("effects", ["pure"]))
        required_surface = spec.get("surface", "declarative")
        if required_surface not in {"declarative", surface} and not (
            required_surface == "expert-option" and option.source == "expert-option"
        ):
            refusals.append({
                "option": f"--{option.name}",
                "reason": f"available only through the {required_surface} command surface",
            })
        requirement = spec.get("policy", "none")
        granted = True
        if requirement == "allow-command-actions":
            granted = policy.allow_command_actions
        elif requirement == "allow-filesystem-write":
            granted = policy.allow_filesystem_write
        elif requirement == "allow-walker":
            granted = policy.allow_walker
        elif requirement == "allow-unknown-options":
            granted = policy.allow_unknown_options
        elif requirement == "allow-unsafe-listener":
            granted = policy.allow_unsafe_listener
        elif requirement == "managed-listener-only":
            granted = surface == "listener"
        elif requirement == "binding-analysis" and option.value is not None:
            hazardous = binding_is_hazardous(option.value)
            granted = not hazardous or policy.allow_command_actions
            if hazardous:
                effects.add("subprocess_capable")
                hazards.append({"option": "--bind", "reason": "command-capable action"})
        if requirement != "none" and requirement != "binding-analysis":
            hazards.append({"option": f"--{option.name}", "reason": requirement})
        if not granted:
            refusals.append({"option": f"--{option.name}", "reason": f"requires {requirement}"})
    return {
        "effects": sorted(effects),
        "hazards": hazards,
        "refusals": refusals,
    }


def require_no_refusals(analysis: dict) -> None:
    """Raise one deterministic policy error for a refused plan."""

    if analysis["refusals"]:
        raise PolicyError(
            "plan_refused",
            "The requested fzf plan violates default-deny policy",
            details={"refusals": analysis["refusals"]},
        )


def ensure_contained(path: Path, root: Path) -> Path:
    """Resolve `path` and require it to remain under `root`."""

    resolved_root = root.expanduser().resolve(strict=False)
    resolved = path.expanduser().resolve(strict=False)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise PolicyError(
            "path_outside_boundary",
            f"Path {resolved} is outside allowed root {resolved_root}",
        ) from exc
    return resolved


def process_start_time(pid: int) -> int | None:
    """Read the Linux process start-time tick used to detect PID reuse."""

    try:
        fields = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()
        # A detached worker can briefly remain as a zombie while its parent is
        # reaping it. Treating that state as live makes stop wait unnecessarily
        # and can send SIGKILL while the worker is atomically writing its final
        # state record.
        if fields[2] == "Z":
            return None
        return int(fields[21])
    except (FileNotFoundError, PermissionError, IndexError, ValueError, OSError):
        return None


def pid_matches(pid: int, start_time: int | None) -> bool:
    """Return true only when the recorded process still owns the PID."""

    if pid <= 1 or start_time is None:
        return False
    return process_start_time(pid) == start_time
