"""GUIMacroBackend — replay precompiled coordinate-based macro sequences.

A compiled macro is a JSON blob describing an exact sequence of mouse clicks,
key presses, and wait conditions. These are fast to execute but fragile to
layout changes.

Compiled macro format (stored separately, referenced by step params):

    {
      "version": 1,
      "screen_resolution": "1920x1080",
      "layout_hash": "abc123",
      "steps": [
        {"type": "click", "x": 100, "y": 200, "button": "left", "delay_ms": 200},
        {"type": "key", "keys": "ctrl+s", "delay_ms": 100},
        {"type": "type", "text": "output.png", "delay_ms": 50},
        {"type": "wait_file", "path": "/tmp/out.png", "timeout_ms": 5000},
        {"type": "sleep", "ms": 500}
      ]
    }

Example macro step:

    - backend: gui_macro
      action: replay
      params:
        macro_file: macros/compiled/export_png.json
        layout_strict: false   # if true, fail when screen res changes
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from cli_anything.openclaw.backends.base import Backend, BackendContext, StepResult
from cli_anything.openclaw.core.macro_model import MacroStep, substitute


class GUIMacroBackend(Backend):
    """Replay precompiled GUI automation sequences."""

    name = "gui_macro"
    priority = 80

    def execute(self, step: MacroStep, params: dict, context: BackendContext) -> StepResult:
        t0 = time.time()
        action = step.action
        step_params = substitute(step.params, params)

        if context.dry_run:
            return StepResult(
                success=True,
                output={"dry_run": True, "action": action},
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        if action != "replay":
            return StepResult(
                success=False,
                error=f"GUIMacroBackend: unknown action '{action}'. Expected 'replay'.",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        return self._replay(step_params, context, t0)

    def is_available(self) -> bool:
        """Available when at least one automation library is present."""
        for lib in ("pyautogui", "pynput"):
            try:
                __import__(lib)
                return True
            except ImportError:
                pass
        return False

    def _replay(self, p: dict, context: BackendContext, t0: float) -> StepResult:
        """Load and replay a compiled macro file."""
        macro_file = p.get("macro_file", "")
        if not macro_file:
            return StepResult(
                success=False,
                error="GUIMacroBackend.replay: 'macro_file' param is required.",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        macro_path = Path(macro_file)
        if not macro_path.is_file():
            return StepResult(
                success=False,
                error=f"GUIMacroBackend: compiled macro not found: {macro_file}",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        try:
            with open(macro_path, encoding="utf-8") as f:
                macro_blob = json.load(f)
        except Exception as exc:
            return StepResult(
                success=False,
                error=f"GUIMacroBackend: failed to load macro file: {exc}",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        layout_strict: bool = p.get("layout_strict", False)
        if layout_strict:
            check = self._check_layout(macro_blob)
            if check:
                return StepResult(
                    success=False,
                    error=f"GUIMacroBackend: layout mismatch — {check}",
                    backend_used=self.name,
                    duration_ms=(time.time() - t0) * 1000,
                )

        try:
            steps_run = self._execute_steps(macro_blob.get("steps", []), context)
            return StepResult(
                success=True,
                output={"steps_executed": steps_run, "macro_file": macro_file},
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )
        except Exception as exc:
            return StepResult(
                success=False,
                error=f"GUIMacroBackend.replay: {exc}",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

    def _check_layout(self, macro_blob: dict) -> str:
        """Return error string if current screen doesn't match expected."""
        expected_res = macro_blob.get("screen_resolution", "")
        if not expected_res:
            return ""
        try:
            import pyautogui
            w, h = pyautogui.size()
            current_res = f"{w}x{h}"
            if current_res != expected_res:
                return f"screen is {current_res}, macro expects {expected_res}"
        except ImportError:
            pass  # Can't verify — allow through
        return ""

    def _execute_steps(self, steps: list, context: BackendContext) -> int:
        """Execute each step in the compiled macro."""
        try:
            import pyautogui
            has_pyautogui = True
        except ImportError:
            has_pyautogui = False

        count = 0
        for s in steps:
            stype = s.get("type", "")
            delay = s.get("delay_ms", 100) / 1000.0

            if stype == "click":
                if not has_pyautogui:
                    raise ImportError("pyautogui required for click steps. pip install pyautogui")
                button = s.get("button", "left")
                pyautogui.click(s["x"], s["y"], button=button)

            elif stype == "key":
                if not has_pyautogui:
                    raise ImportError("pyautogui required for key steps. pip install pyautogui")
                keys = s.get("keys", "").split("+")
                if len(keys) == 1:
                    pyautogui.press(keys[0])
                else:
                    pyautogui.hotkey(*keys)

            elif stype == "type":
                if not has_pyautogui:
                    raise ImportError("pyautogui required for type steps. pip install pyautogui")
                pyautogui.typewrite(s.get("text", ""), interval=0.03)

            elif stype == "wait_file":
                deadline = time.time() + s.get("timeout_ms", 5000) / 1000.0
                path = s.get("path", "")
                while time.time() < deadline:
                    if Path(path).exists():
                        break
                    time.sleep(0.1)
                else:
                    raise TimeoutError(f"wait_file timed out: {path}")
                delay = 0  # no additional delay after file wait

            elif stype == "sleep":
                time.sleep(s.get("ms", 500) / 1000.0)
                delay = 0

            if delay > 0:
                time.sleep(delay)
            count += 1

        return count
