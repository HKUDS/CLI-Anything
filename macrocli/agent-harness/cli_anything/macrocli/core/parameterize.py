"""Parameterization helpers — interactive and Gemini-assisted.

Interactive flow (no external deps):
    assignments = interactive_parameterize(type_steps)
    parameters  = recorder.apply_parameterization(assignments)
    recorder.save(parameters=parameters)

Post-hoc flow on an existing YAML file:
    parameterize_yaml_file(yaml_path)   # modifies in-place

Gemini-assisted flow (optional, requires google-generativeai):
    assignments = gemini_suggest_parameters(type_steps, api_key=...)
    # returns same shape as interactive_parameterize, can be passed directly
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    raise ImportError("PyYAML required: pip install PyYAML")


# ── Parameter name validation ─────────────────────────────────────────────────

_PARAM_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _valid_param_name(name: str) -> bool:
    return bool(_PARAM_NAME_RE.match(name))


def _prompt_param_name(prompt: str) -> Optional[str]:
    """Prompt user for a parameter name. Return None if skipped (empty input)."""
    while True:
        try:
            raw = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None

        if not raw:
            return None  # skip

        if _valid_param_name(raw):
            return raw

        print(f"  ✗ '{raw}' is not valid. Use lowercase letters, digits, "
              f"underscores only (must start with a letter). "
              f"Press Enter to skip.")


# ── Interactive parameterization ──────────────────────────────────────────────

def interactive_parameterize(
    type_steps: list[tuple[int, object]],
    existing_params: Optional[set[str]] = None,
) -> dict[int, str]:
    """Interactively ask the user which type_text steps to parameterize.

    Args:
        type_steps: List of (list_index, RecordedStep) from recorder.get_type_steps().
        existing_params: Already-used parameter names (to avoid duplicates).

    Returns:
        {list_index: param_name} — only for steps the user chose to parameterize.
    """
    if not type_steps:
        print("  No type_text steps found to parameterize.")
        return {}

    used_names: set[str] = set(existing_params or [])
    assignments: dict[int, str] = {}

    print()
    print("─" * 60)
    print("  Parameterization — press Enter to keep a value hardcoded,")
    print("  or type a parameter name (e.g. output_path) to make it dynamic.")
    print("─" * 60)

    for n, (idx, step) in enumerate(type_steps, 1):
        value = step.text  # type: ignore[attr-defined]
        # Truncate long values for display
        display = value if len(value) <= 50 else value[:47] + "..."

        print(f"\n  [{n}/{len(type_steps)}] step typed: {display!r}")

        while True:
            name = _prompt_param_name("  → Parameter name (Enter to skip): ")
            if name is None:
                break  # skip
            if name in used_names:
                print(f"  ✗ '{name}' already used. Choose a different name.")
                continue
            used_names.add(name)
            assignments[idx] = name
            print(f"  ✓ Will become: ${{{{name}}}}")
            break

    print()
    if assignments:
        print(f"  Parameterized {len(assignments)} step(s): "
              f"{', '.join(assignments.values())}")
    else:
        print("  No steps parameterized — macro will use hardcoded values.")
    print("─" * 60)

    return assignments


# ── Post-hoc YAML parameterization ───────────────────────────────────────────

class _YamlTypeStep:
    """Lightweight wrapper for a type_text step found inside a YAML dict."""
    def __init__(self, step_idx: int, step_dict: dict):
        self.list_index = step_idx
        self._step = step_dict
        self.text: str = step_dict["params"]["text"]

    def apply(self, param_name: str) -> None:
        self._step["params"]["text"] = f"${{{param_name}}}"


def parameterize_yaml_file(yaml_path: str) -> bool:
    """Interactively parameterize an existing macro YAML file in-place.

    Finds all steps with action=type_text, runs the interactive flow,
    updates the file, and returns True if any changes were made.
    """
    p = Path(yaml_path)
    if not p.is_file():
        raise FileNotFoundError(f"Macro file not found: {yaml_path}")

    with open(p, encoding="utf-8") as f:
        macro = yaml.safe_load(f)

    if not isinstance(macro, dict):
        raise ValueError("Invalid macro YAML: expected a mapping at top level.")

    steps: list[dict] = macro.get("steps") or []
    type_steps_raw = [
        (i, s) for i, s in enumerate(steps)
        if isinstance(s, dict)
        and s.get("action") == "type_text"
        and s.get("params", {}).get("text", "").strip()
        # Skip already-parameterized steps
        and not s["params"]["text"].startswith("${")
    ]

    if not type_steps_raw:
        print("  No hardcoded type_text steps found to parameterize.")
        return False

    # Wrap in lightweight objects for interactive_parameterize
    wrapped = [
        (i, _YamlTypeStep(i, s))
        for i, s in type_steps_raw
    ]

    existing_params = set((macro.get("parameters") or {}).keys())
    assignments = interactive_parameterize(wrapped, existing_params)

    if not assignments:
        return False

    # Apply in-place and collect parameter specs
    parameters: dict = dict(macro.get("parameters") or {})
    for idx, param_name in assignments.items():
        yw = next(w for i, w in wrapped if i == idx)
        original = yw.text
        yw.apply(param_name)

        # Infer type
        ptype = "string"
        try:
            int(original); ptype = "integer"
        except ValueError:
            try:
                float(original); ptype = "float"
            except ValueError:
                pass

        parameters[param_name] = {
            "type": ptype,
            "required": True,
            "description": f"Value typed at step {idx + 1}",
            "example": original,
        }

    macro["parameters"] = parameters

    with open(p, "w", encoding="utf-8") as f:
        yaml.dump(macro, f, allow_unicode=True, sort_keys=False,
                  default_flow_style=False)

    print(f"\n  ✓ Updated: {p.resolve()}")
    return True


# ── Gemini-assisted parameterization ─────────────────────────────────────────

def gemini_suggest_parameters(
    type_steps: list[tuple[int, object]],
    api_key: Optional[str] = None,
    model: str = "gemini-1.5-flash",
) -> dict[int, str]:
    """Use Gemini to suggest which type_text steps should be parameterized
    and what to name the parameters.

    Args:
        type_steps: Same format as interactive_parameterize input.
        api_key: Gemini API key. Falls back to GEMINI_API_KEY env var.
        model: Gemini model name.

    Returns:
        {list_index: suggested_param_name} — same shape as interactive output.
        The caller can pass this directly to recorder.apply_parameterization()
        or show it to the user for confirmation first.
    """
    import json
    import os

    try:
        import google.generativeai as genai
    except ImportError:
        raise ImportError(
            "google-generativeai required for auto-parameterization.\n"
            "  pip install google-generativeai"
        )

    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise ValueError(
            "Gemini API key required. Pass --api-key or set GEMINI_API_KEY.\n"
            "  https://aistudio.google.com/app/apikey"
        )

    genai.configure(api_key=key)

    _SYSTEM = """\
You are a macro parameterization assistant. Given a list of text values
that a user typed during a GUI recording session, decide which ones should
become CLI parameters (so the macro can be reused with different values)
and suggest a snake_case parameter name for each.

Rules:
- File paths, URLs, usernames, numeric sizes/counts → ALWAYS parameterize
- Generic user content (e.g. document body text) → parameterize if variable
- Fixed UI inputs that never change (e.g. "OK", "yes", "1") → do NOT parameterize
- Parameter names: lowercase, snake_case, descriptive (e.g. output_path, width)

Output ONLY a JSON object mapping the step index (as a string) to the
parameter name, for steps that SHOULD be parameterized.
Steps that should NOT be parameterized must be omitted entirely.
Example: {"0": "output_path", "2": "export_width"}
"""

    items = "\n".join(
        f'  index {idx}: {step.text!r}'  # type: ignore[attr-defined]
        for idx, step in type_steps
    )
    prompt = f"Typed values from the recording:\n{items}\n\nOutput JSON only."

    gem = genai.GenerativeModel(model_name=model, system_instruction=_SYSTEM)
    response = gem.generate_content(prompt)
    raw = response.text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = "\n".join(
            line for line in raw.split("\n")
            if not line.startswith("```")
        ).strip()

    try:
        raw_dict: dict = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Gemini returned invalid JSON: {e}\nRaw: {raw[:300]}"
        )

    # Convert string keys to int, validate names
    result: dict[int, str] = {}
    for k, v in raw_dict.items():
        try:
            idx = int(k)
        except ValueError:
            continue
        if not isinstance(v, str) or not _valid_param_name(v):
            continue
        # Check the index is actually in the provided steps
        if any(i == idx for i, _ in type_steps):
            result[idx] = v

    return result
