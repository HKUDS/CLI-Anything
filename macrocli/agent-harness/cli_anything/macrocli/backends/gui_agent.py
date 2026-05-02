"""GUIAgentBackend — execute a macro step by letting a vision model
look at the screen and decide what to do.

This backend is used for steps that cannot be expressed as fixed
coordinates or hotkeys because the interface state is unpredictable.
The macro author provides:
  - description:           what needs to be accomplished in this step
  - end_state_description: text description of the desired end state
  - end_state_snapshot:    screenshot of the desired end state (taken
                           by the macro author at recording time)

At runtime the backend:
  1. Takes a screenshot of the current screen
  2. Sends current screenshot + end_state_snapshot + description to the model
  3. Model returns the next action (click x,y / type text / hotkey)
  4. Executes the action
  5. Takes another screenshot
  6. Asks model: "have we reached the end state?"
  7. Loops until end state reached or max_steps exceeded

The backend uses the OpenAI SDK, which is compatible with any
OpenAI-compatible API provider (OpenAI, Azure, local vLLM, Ollama,
LiteLLM, etc.).  Configure model and endpoint via environment
variables or per-step YAML params:

  Environment variables:
    MACROCLI_MODEL    — model name (required, no default)
    MACROCLI_API_KEY  — API key
    MACROCLI_BASE_URL — base URL for non-OpenAI providers

Example YAML step:

    - id: select_png_format
      backend: gui_agent
      action: instruct
      params:
        description: >
          The export dialog is open. Find the Format dropdown and
          select PNG. Then ensure Resolution shows 300.
        end_state_description: >
          Format dropdown shows PNG, Resolution input shows 300.
        end_state_snapshot: snapshots/step_003_end_state.png
        max_steps: 8
        model: ${MACROCLI_MODEL}
        api_key: ${MACROCLI_API_KEY}
        base_url: ${MACROCLI_BASE_URL}
"""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Optional

from cli_anything.macrocli.backends.base import Backend, BackendContext, StepResult
from cli_anything.macrocli.core.macro_model import MacroStep, substitute

# ── Strict action space prompt ────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a GUI automation agent. You will be shown:
1. A screenshot of the CURRENT screen state
2. A screenshot of the TARGET end state (optional)
3. A description of what needs to be accomplished

Your job is to figure out what single action to take next.

OUTPUT FORMAT: Respond with ONLY a JSON object, one of:

  {"action": "click", "x": <int>, "y": <int>, "button": "left"}
  {"action": "double_click", "x": <int>, "y": <int>}
  {"action": "right_click", "x": <int>, "y": <int>}
  {"action": "drag", "from_x": <int>, "from_y": <int>, "to_x": <int>, "to_y": <int>, "duration_ms": 300}
  {"action": "type", "text": "<string>"}
  {"action": "hotkey", "keys": "<key1+key2+...>"}
  {"action": "scroll", "x": <int>, "y": <int>, "dy": <int>}
  {"action": "done"}

Use {"action": "done"} ONLY when the current state matches the target state.

RULES:
- Output RAW JSON ONLY. No markdown, no explanation.
- Use pixel coordinates from the CURRENT screenshot.
- For drag: from_x/from_y is where you start pressing, to_x/to_y is where you release.
- Prefer clicking on visible labeled controls over guessing coordinates.
- If the target state is already achieved, output {"action": "done"}.
- Never output any action not listed above.
"""

_CHECK_PROMPT = """\
Compare these two screenshots:
1. CURRENT state
2. TARGET end state

Has the current state reached the target end state?
Answer with ONLY: {"reached": true} or {"reached": false, "reason": "<brief reason>"}
"""


# ── Image helpers ─────────────────────────────────────────────────────────────

def _screenshot_b64() -> str:
    """Take a screenshot and return as base64 PNG string."""
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
            return base64.b64encode(buf.getvalue()).decode("utf-8")
    except ImportError:
        raise ImportError("mss and Pillow required: pip install mss Pillow")


def _file_to_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ── Action executor ───────────────────────────────────────────────────────────

def _execute_action(action_dict: dict, context: BackendContext) -> None:
    """Execute a single action returned by the model."""
    from cli_anything.macrocli.backends.visual_anchor import (
        _mouse_click, _mouse_drag, _require_pynput
    )

    action = action_dict.get("action", "")

    if action == "click":
        x, y = int(action_dict["x"]), int(action_dict["y"])
        _mouse_click(x, y, button=action_dict.get("button", "left"))

    elif action == "double_click":
        x, y = int(action_dict["x"]), int(action_dict["y"])
        _mouse_click(x, y, double=True)

    elif action == "right_click":
        x, y = int(action_dict["x"]), int(action_dict["y"])
        _mouse_click(x, y, button="right")

    elif action == "type":
        text = action_dict.get("text", "")
        _, keyboard_mod = _require_pynput()
        ctrl = keyboard_mod.Controller()
        for char in text:
            ctrl.press(char)
            ctrl.release(char)
            time.sleep(0.03)

    elif action == "hotkey":
        keys_str = action_dict.get("keys", "")
        _, keyboard_mod = _require_pynput()
        Key = keyboard_mod.Key
        ctrl = keyboard_mod.Controller()
        _KEY_MAP = {
            "ctrl": Key.ctrl, "shift": Key.shift, "alt": Key.alt,
            "enter": Key.enter, "tab": Key.tab, "esc": Key.esc,
            "escape": Key.esc, "space": Key.space, "backspace": Key.backspace,
        }
        keys = [_KEY_MAP.get(k.lower(), k) for k in keys_str.split("+")]
        for k in keys:
            ctrl.press(k)
        for k in reversed(keys):
            ctrl.release(k)

    elif action == "scroll":
        x, y = int(action_dict["x"]), int(action_dict["y"])
        dy = int(action_dict.get("dy", -3))
        mouse_mod, _ = _require_pynput()
        ctrl = mouse_mod.Controller()
        ctrl.position = (x, y)
        ctrl.scroll(0, dy)

    elif action == "drag":
        fx, fy = int(action_dict["from_x"]), int(action_dict["from_y"])
        tx, ty = int(action_dict["to_x"]), int(action_dict["to_y"])
        duration_ms = int(action_dict.get("duration_ms", 300))
        from cli_anything.macrocli.backends.visual_anchor import _mouse_drag
        _mouse_drag(fx, fy, tx, ty, duration_ms=duration_ms)

    elif action == "done":
        pass  # caller checks for done

    else:
        raise ValueError(f"GUIAgentBackend: unknown action '{action}'")


# ── Backend ───────────────────────────────────────────────────────────────────

class GUIAgentBackend(Backend):
    """Execute GUI steps using a vision model (OpenAI-compatible API) to decide actions."""

    name = "gui_agent"
    priority = 60  # between semantic_ui(50) and file_transform(70)

    def execute(
        self, step: MacroStep, params: dict, context: BackendContext
    ) -> StepResult:
        t0 = time.time()
        p = substitute(step.params, params)

        if context.dry_run:
            return StepResult(
                success=True,
                output={"dry_run": True, "action": step.action},
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        if step.action == "instruct":
            return self._instruct(p, context, t0)
        elif step.action == "instruct_with_refine":
            return self._instruct_with_refine(p, context, t0)
        else:
            return StepResult(
                success=False,
                error=f"GUIAgentBackend: unknown action '{step.action}'. "
                      "Supported: 'instruct', 'instruct_with_refine'.",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

    def is_available(self) -> bool:
        try:
            import openai  # noqa: F401
            import mss  # noqa: F401
            return True
        except ImportError:
            return False

    def _instruct(
        self, p: dict, context: BackendContext, t0: float
    ) -> StepResult:
        """Execute exactly ONE action decided by the vision model.

        The macro author is responsible for:
        - focusing the target window before calling gui_agent
        - writing multiple gui_agent steps if multiple actions are needed
        - verifying the outcome via postconditions or subsequent steps

        This step:
          1. Takes a screenshot
          2. Sends it + description + end_state_snapshot to the model
          3. Model returns one action (click/type/hotkey/scroll/done)
          4. Executes that action
          5. Returns success with the action taken
        """
        description: str = p.get("description", "")
        end_state_desc: str = p.get("end_state_description", "")
        snapshot_path: str = p.get("end_state_snapshot", "")
        window_title: str = p.get("window_title", "")  # focus this window first
        model_name: str = p.get("model", os.environ.get("MACROCLI_MODEL", ""))
        api_key: str = p.get("api_key", os.environ.get("MACROCLI_API_KEY", ""))
        base_url: str = p.get("base_url", os.environ.get("MACROCLI_BASE_URL", ""))

        if not model_name:
            return StepResult(
                success=False,
                error="GUIAgentBackend: model required. Set MACROCLI_MODEL env var or pass model in step params.",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        if not api_key:
            return StepResult(
                success=False,
                error="GUIAgentBackend: api_key required. Set MACROCLI_API_KEY env var.",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        try:
            from openai import OpenAI
        except ImportError:
            return StepResult(
                success=False,
                error="openai required: pip install openai",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        client = OpenAI(**client_kwargs)

        def _call_model(messages: list, max_tokens: int = 1024) -> str:
            resp = client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content.strip()

        def _extract_json(raw: str) -> dict:
            """Extract JSON from model output robustly."""
            if raw.startswith("```"):
                raw = "\n".join(
                    l for l in raw.split("\n") if not l.startswith("```")
                ).strip()
            start = raw.find('{')
            end = raw.rfind('}')
            if start != -1 and end != -1:
                raw = raw[start:end+1]
            return json.loads(raw)

        # Step 1: Focus the target window if specified
        if window_title and not context.dry_run:
            import shutil, subprocess
            env = os.environ.copy()
            if "DISPLAY" not in env:
                env["DISPLAY"] = ":0"
            if shutil.which("wmctrl"):
                subprocess.run(["wmctrl", "-a", window_title],
                               capture_output=True, env=env)
            elif shutil.which("xdotool"):
                subprocess.run(
                    ["xdotool", "search", "--name", window_title,
                     "windowfocus", "--sync"],
                    capture_output=True, env=env
                )
            time.sleep(0.3)

        if context.dry_run:
            return StepResult(
                success=True,
                output={"dry_run": True, "description": description},
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        # Step 2: Take screenshot
        current_b64 = _screenshot_b64()

        # Step 3: Load end state snapshot if provided
        end_state_b64: Optional[str] = None
        if snapshot_path and Path(snapshot_path).is_file():
            end_state_b64 = _file_to_b64(snapshot_path)

        # Step 4: Build prompt
        content = []
        content.append({"type": "text", "text": "CURRENT SCREEN STATE:"})
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{current_b64}"}
        })
        if end_state_b64:
            content.append({"type": "text", "text": "TARGET END STATE:"})
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{end_state_b64}"}
            })
        task_text = f"TASK: {description}"
        if end_state_desc:
            task_text += f"\nTARGET: {end_state_desc}"
        task_text += "\nOutput ONE action as JSON only."
        content.append({"type": "text", "text": task_text})

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]

        # Step 5: Ask model for one action
        try:
            raw = _call_model(messages)
        except Exception as exc:
            return StepResult(
                success=False,
                error=f"GUIAgentBackend: model error: {exc}",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        try:
            action_dict = _extract_json(raw)
        except json.JSONDecodeError:
            return StepResult(
                success=False,
                error=f"GUIAgentBackend: invalid JSON from model: {raw[:200]}",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        action_name = action_dict.get("action", "")
        print(f"[gui_agent] action: {action_dict}", flush=True)

        # Step 6: Execute the action (unless model says done)
        if action_name != "done":
            try:
                _execute_action(action_dict, context)
            except Exception as exc:
                return StepResult(
                    success=False,
                    error=f"GUIAgentBackend: action execution failed: {exc}",
                    backend_used=self.name,
                    duration_ms=(time.time() - t0) * 1000,
                )
            time.sleep(0.5)

        return StepResult(
            success=True,
            output={
                "action": action_dict,
                "done": action_name == "done",
            },
            backend_used=self.name,
            duration_ms=(time.time() - t0) * 1000,
        )

    def _instruct_with_refine(
        self, p: dict, context: BackendContext, t0: float
    ) -> StepResult:
        """Execute one action, then compare result vs end_state_snapshot,
        and if needed undo and re-execute with a refined action.

        Sends to model on refine:
          - Screenshot BEFORE first action (original state)
          - The first action that was taken
          - Screenshot AFTER first action (current result)
          - end_state_snapshot (target state)
          - Request for corrected action

        This allows the model to see exactly what went wrong and correct it.
        """
        snapshot_path: str = p.get("end_state_snapshot", "")

        if not snapshot_path or not Path(snapshot_path).is_file():
            # No end state snapshot → fall back to single instruct
            return self._instruct(p, context, t0)

        # ── Round 1: initial action ───────────────────────────────────────────
        before_b64 = _screenshot_b64()
        result1 = self._instruct(p, context, t0)

        if not result1.success:
            return result1

        first_action = result1.output.get("action", {})
        if first_action.get("action") == "done":
            return result1

        time.sleep(0.5)
        after_b64 = _screenshot_b64()
        end_state_b64 = _file_to_b64(snapshot_path)

        # ── Round 2: compare and refine ───────────────────────────────────────
        description: str = p.get("description", "")
        end_state_desc: str = p.get("end_state_description", "")
        model_name: str = p.get("model", os.environ.get("MACROCLI_MODEL", ""))
        api_key: str = p.get("api_key", os.environ.get("MACROCLI_API_KEY", ""))
        base_url: str = p.get("base_url", os.environ.get("MACROCLI_BASE_URL", ""))

        from openai import OpenAI
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        client = OpenAI(**client_kwargs)

        def _call(messages):
            resp = client.chat.completions.create(
                model=model_name, messages=messages, max_tokens=1024,
            )
            return resp.choices[0].message.content.strip()

        def _extract_json(raw):
            if raw.startswith("```"):
                raw = "\n".join(l for l in raw.split("\n") if not l.startswith("```")).strip()
            s, e = raw.find('{'), raw.rfind('}')
            if s != -1 and e != -1:
                raw = raw[s:e+1]
            return json.loads(raw)

        refine_prompt = f"""You are refining a GUI automation action.

ORIGINAL TASK: {description}
TARGET STATE: {end_state_desc}

WHAT HAPPENED:
- First action taken: {json.dumps(first_action)}

Now compare these three screenshots:

1. BEFORE (original state before any action):
2. AFTER FIRST ACTION (current result):
3. TARGET END STATE (what it should look like):

The first action was not quite right. Looking at:
- Where the rectangle was drawn vs where it should be
- The difference between AFTER and TARGET

Provide a corrected drag action with better coordinates.
Output ONE JSON action only."""

        content = [
            {"type": "text", "text": refine_prompt},
            {"type": "text", "text": "BEFORE:"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{before_b64}"}},
            {"type": "text", "text": "AFTER FIRST ACTION:"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{after_b64}"}},
            {"type": "text", "text": "TARGET END STATE:"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{end_state_b64}"}},
        ]

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]

        try:
            raw = _call(messages)
            refined_action = _extract_json(raw)
            print(f"[gui_agent] refined action: {refined_action}", flush=True)
        except Exception as exc:
            # Refine failed, return original result
            print(f"[gui_agent] refine failed: {exc}, keeping original", flush=True)
            return result1

        if refined_action.get("action") == "done":
            return result1

        # Undo the first action, then execute the refined one
        import shutil, subprocess as sp
        env = os.environ.copy()
        if "DISPLAY" not in env:
            env["DISPLAY"] = ":0"
        if shutil.which("xdotool"):
            sp.run(["xdotool", "key", "ctrl+z"], env=env)
            time.sleep(0.3)

        try:
            _execute_action(refined_action, context)
        except Exception as exc:
            return StepResult(
                success=False,
                error=f"GUIAgentBackend: refine action failed: {exc}",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        time.sleep(0.5)

        return StepResult(
            success=True,
            output={
                "action": refined_action,
                "first_action": first_action,
                "refined": True,
                "done": False,
            },
            backend_used=self.name,
            duration_ms=(time.time() - t0) * 1000,
        )
