"""GeminiAssist — use Gemini Vision to generate macro steps from screenshots.

This module is OPTIONAL. It requires:
    pip install google-generativeai

How it works:
  1. Capture a screenshot of the current screen (or use a provided image)
  2. Send the image + user goal to Gemini Vision with a strict system prompt
  3. Gemini returns a JSON array of steps (constrained action space)
  4. Steps are validated and written as a macro YAML file

The action space Gemini is allowed to produce:

    {"type": "click_image",    "description": "...", "confidence": 0.85}
    {"type": "click_relative", "window_title": "...", "x_pct": 0.5, "y_pct": 0.1}
    {"type": "type_text",      "text": "..."}
    {"type": "hotkey",         "keys": "ctrl+s"}
    {"type": "wait_image",     "description": "...", "timeout_ms": 5000}
    {"type": "wait_for_window","title_contains": "...", "timeout_ms": 5000}
    {"type": "menu_click",     "app_name": "...", "menu_path": ["File", "Export"]}
    {"type": "scroll",         "description": "...", "dy": -3}

Gemini is NOT allowed to:
  - Produce shell commands, Python code, or arbitrary actions
  - Use absolute pixel coordinates
  - Output anything other than the JSON array

The "description" field in click_image / wait_image / scroll tells the user
what template image to capture with 'macro record' or 'capture_region'.

Usage:
    cli-anything-macrocli macro define my_export --assist \
        --goal "Export the current diagram as PNG to /tmp/out.png" \
        --screenshot current         # takes a fresh screenshot
        --screenshot /path/to/img.png   # use existing image
        --api-key $GEMINI_API_KEY
"""

from __future__ import annotations


import json
import os
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    raise ImportError("PyYAML required: pip install PyYAML")


# ── Strict system prompt ──────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a GUI macro step generator. Given a screenshot and a user goal, \
output ONLY a valid JSON array of macro steps.

ALLOWED step types (use EXACTLY these schemas):

1. Click a UI element by visual description (template matching will be used):
   {"type": "click_image", "description": "<what the element looks like>", \
"confidence": 0.85, "timeout_ms": 5000}

2. Click at a fractional position within a named window:
   {"type": "click_relative", "window_title": "<partial title>", \
"x_pct": 0.0-1.0, "y_pct": 0.0-1.0}

3. Type text into the focused field:
   {"type": "type_text", "text": "<text to type>"}

4. Send a keyboard shortcut:
   {"type": "hotkey", "keys": "<key1+key2+...>"}

5. Wait for a visual element to appear:
   {"type": "wait_image", "description": "<what to wait for>", \
"timeout_ms": 5000}

6. Wait for a window with a certain title:
   {"type": "wait_for_window", "title_contains": "<partial title>", \
"timeout_ms": 5000}

7. Click a menu item by path:
   {"type": "menu_click", "app_name": "<app name>", \
"menu_path": ["Menu", "Submenu", "Item"]}

8. Scroll near a visual element:
   {"type": "scroll", "description": "<near what element>", "dy": -3}

STRICT RULES:
- Output RAW JSON ONLY. No markdown, no explanation, no code blocks.
- The output must be a JSON array: [step1, step2, ...]
- NEVER use absolute pixel coordinates (x, y numbers).
- NEVER output shell commands, Python, or any non-JSON content.
- NEVER invent step types not listed above.
- Prefer menu_click and hotkey over click_image when possible.
- For click_image: describe the element clearly so a human can find and \
photograph it.
- Keep the plan minimal: use the fewest steps that achieve the goal.
"""


# ── Screenshot helpers ────────────────────────────────────────────────────────

def _take_screenshot() -> bytes:
    """Capture the current screen and return as PNG bytes."""
    try:
        import mss
        from PIL import Image
        import io
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
    except ImportError:
        raise ImportError("mss and Pillow required: pip install mss Pillow")


def _load_image_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


# ── Step validation ───────────────────────────────────────────────────────────

_ALLOWED_TYPES = {
    "click_image", "click_relative", "type_text", "hotkey",
    "wait_image", "wait_for_window", "menu_click", "scroll",
}

_REQUIRED_FIELDS = {
    "click_image":     {"type", "description"},
    "click_relative":  {"type", "window_title", "x_pct", "y_pct"},
    "type_text":       {"type", "text"},
    "hotkey":          {"type", "keys"},
    "wait_image":      {"type", "description"},
    "wait_for_window": {"type", "title_contains"},
    "menu_click":      {"type", "app_name", "menu_path"},
    "scroll":          {"type"},
}


def _validate_steps(raw_steps: list) -> tuple[list[dict], list[str]]:
    """Validate and sanitize steps from Gemini output.

    Returns (valid_steps, error_messages).
    """
    valid = []
    errors = []

    for i, step in enumerate(raw_steps):
        if not isinstance(step, dict):
            errors.append(f"Step {i}: not a dict, skipped.")
            continue

        stype = step.get("type", "")
        if stype not in _ALLOWED_TYPES:
            errors.append(f"Step {i}: unknown type '{stype}', skipped.")
            continue

        required = _REQUIRED_FIELDS.get(stype, {"type"})
        missing = required - set(step.keys())
        if missing:
            errors.append(f"Step {i} ({stype}): missing fields {missing}, skipped.")
            continue

        # Reject any absolute coordinate fields
        for bad_field in ("x", "y", "px", "pixels"):
            if bad_field in step:
                errors.append(
                    f"Step {i} ({stype}): absolute coordinate field '{bad_field}' rejected."
                )
                step.pop(bad_field)

        valid.append(step)

    return valid, errors


# ── Step → YAML step dict conversion ─────────────────────────────────────────

def _gemini_step_to_yaml_step(step: dict, index: int) -> dict:
    """Convert a validated Gemini step to a macro YAML step dict."""
    stype = step["type"]
    sid = f"step_{index:03d}_{stype}"

    if stype == "click_image":
        return {
            "id": sid,
            "backend": "visual_anchor",
            "action": "click_image",
            "params": {
                "template": f"templates/{index:03d}_{stype}.png",
                "confidence": step.get("confidence", 0.85),
                "timeout_ms": step.get("timeout_ms", 5000),
                "_template_description": step.get("description", ""),
            },
            "on_failure": "fail",
            "_gemini_description": step.get("description", ""),
        }
    elif stype == "click_relative":
        return {
            "id": sid,
            "backend": "visual_anchor",
            "action": "click_relative",
            "params": {
                "window_title": step["window_title"],
                "x_pct": step["x_pct"],
                "y_pct": step["y_pct"],
            },
            "on_failure": "fail",
        }
    elif stype == "type_text":
        return {
            "id": sid,
            "backend": "visual_anchor",
            "action": "type_text",
            "params": {"text": step["text"]},
            "on_failure": "fail",
        }
    elif stype == "hotkey":
        return {
            "id": sid,
            "backend": "visual_anchor",
            "action": "hotkey",
            "params": {"keys": step["keys"]},
            "on_failure": "fail",
        }
    elif stype == "wait_image":
        return {
            "id": sid,
            "backend": "visual_anchor",
            "action": "wait_image",
            "params": {
                "template": f"templates/{index:03d}_{stype}.png",
                "confidence": step.get("confidence", 0.85),
                "timeout_ms": step.get("timeout_ms", 10000),
                "_template_description": step.get("description", ""),
            },
            "on_failure": "fail",
            "_gemini_description": step.get("description", ""),
        }
    elif stype == "wait_for_window":
        return {
            "id": sid,
            "backend": "semantic_ui",
            "action": "wait_for_window",
            "params": {
                "title_contains": step["title_contains"],
                "timeout_ms": step.get("timeout_ms", 5000),
            },
            "on_failure": "fail",
        }
    elif stype == "menu_click":
        return {
            "id": sid,
            "backend": "semantic_ui",
            "action": "menu_click",
            "params": {
                "app_name": step["app_name"],
                "menu_path": step["menu_path"],
            },
            "on_failure": "fail",
        }
    elif stype == "scroll":
        return {
            "id": sid,
            "backend": "visual_anchor",
            "action": "scroll",
            "params": {
                "template": f"templates/{index:03d}_{stype}.png"
                            if step.get("description") else "",
                "dy": step.get("dy", -3),
                "dx": step.get("dx", 0),
                "_template_description": step.get("description", ""),
            },
            "on_failure": "fail",
        }
    return {}


# ── Main API ──────────────────────────────────────────────────────────────────

def generate_macro(
    goal: str,
    macro_name: str,
    screenshot_source: str = "current",   # "current" | path to image file
    api_key: Optional[str] = None,
    model: str = "gemini-1.5-flash",
    output_path: Optional[str] = None,
) -> dict:
    """Generate a macro YAML from a user goal and screenshot using Gemini.

    Args:
        goal: Natural language description of what the macro should do.
        macro_name: Name for the generated macro.
        screenshot_source: "current" to take a fresh screenshot, or a
                           file path to use an existing image.
        api_key: Gemini API key. Falls back to GEMINI_API_KEY env var.
        model: Gemini model to use.
        output_path: Where to write the YAML file. Defaults to
                     <macro_name>.yaml in the current directory.

    Returns:
        dict with keys: yaml_path, steps_count, warnings, raw_steps
    """
    try:
        import google.generativeai as genai
    except ImportError:
        raise ImportError(
            "google-generativeai is required for Gemini assist.\n"
            "  pip install google-generativeai"
        )

    # Resolve API key
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise ValueError(
            "Gemini API key required. Pass --api-key or set GEMINI_API_KEY env var.\n"
            "Get a key at: https://aistudio.google.com/app/apikey"
        )

    genai.configure(api_key=key)

    # Get screenshot
    if screenshot_source == "current":
        image_bytes = _take_screenshot()
    else:
        if not Path(screenshot_source).is_file():
            raise FileNotFoundError(f"Screenshot not found: {screenshot_source}")
        image_bytes = _load_image_bytes(screenshot_source)

    # Build prompt
    user_prompt = (
        f"Goal: {goal}\n\n"
        "Generate the minimal sequence of steps to achieve this goal. "
        "Output ONLY the JSON array, nothing else."
    )

    # Call Gemini
    gemini_model = genai.GenerativeModel(
        model_name=model,
        system_instruction=_SYSTEM_PROMPT,
    )

    import PIL.Image
    import io
    img = PIL.Image.open(io.BytesIO(image_bytes))

    response = gemini_model.generate_content([user_prompt, img])
    raw_text = response.text.strip()

    # Strip markdown code fences if model added them despite instructions
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(
            line for line in lines
            if not line.startswith("```")
        ).strip()

    # Parse JSON
    try:
        raw_steps = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Gemini returned invalid JSON: {e}\n"
            f"Raw response (first 500 chars):\n{raw_text[:500]}"
        )

    if not isinstance(raw_steps, list):
        raise ValueError(
            f"Gemini returned non-array JSON (expected list): {type(raw_steps)}"
        )

    # Validate
    valid_steps, warnings = _validate_steps(raw_steps)

    # Convert to YAML step dicts
    yaml_steps = [
        _gemini_step_to_yaml_step(s, i + 1)
        for i, s in enumerate(valid_steps)
    ]

    # Build macro dict
    macro = {
        "name": macro_name,
        "version": "1.0",
        "description": goal,
        "tags": ["generated", "gemini-assist"],
        "parameters": {},
        "preconditions": [],
        "steps": yaml_steps,
        "postconditions": [],
        "outputs": [],
        "agent_hints": {
            "danger_level": "moderate",
            "side_effects": ["gui_interaction"],
            "reversible": False,
            "generated_by": "gemini-assist",
            "model": model,
        },
    }

    # Add note about templates that need to be captured
    templates_needed = [
        {
            "step_id": s["id"],
            "template_path": s["params"].get("template", ""),
            "description": s.get("_gemini_description", ""),
        }
        for s in yaml_steps
        if s.get("params", {}).get("template") and s.get("_gemini_description")
    ]

    if templates_needed:
        macro["_templates_to_capture"] = templates_needed

    # Write YAML
    if output_path is None:
        output_path = f"{macro_name}.yaml"

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(
        yaml.dump(macro, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )

    return {
        "yaml_path": str(Path(output_path).resolve()),
        "steps_count": len(yaml_steps),
        "warnings": warnings,
        "raw_steps": raw_steps,
        "templates_to_capture": templates_needed,
    }
