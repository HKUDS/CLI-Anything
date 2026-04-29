"""Macro recorder — record GUI interactions and generate macro YAML.

Usage:
    cli-anything-macrocli macro record my_workflow

What it does:
  1. Starts listening for mouse clicks and keyboard events (pynput)
  2. On each click: captures a small screenshot region around the click
     point and saves it as a template image
  3. On each hotkey / type event: records the keystroke
  4. When the user presses Ctrl+Alt+S (or sends SIGINT): stops recording
     and writes a macro YAML file

The generated macro uses the `visual_anchor` backend for click steps
(template images, not hardcoded coordinates) so it is robust to window
movement and minor layout changes.

Output layout:
    <macro_name>.yaml
    <macro_name>_templates/
        step_001_click.png
        step_002_click.png
        ...
"""

from __future__ import annotations

import os
import sys
import time
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    raise ImportError("PyYAML required: pip install PyYAML")


# ── Step data classes ─────────────────────────────────────────────────────────

@dataclass
class RecordedStep:
    index: int
    kind: str           # click | type | hotkey | scroll
    # click fields
    x: int = 0
    y: int = 0
    button: str = "left"
    double: bool = False
    template_path: str = ""       # relative path to saved template png (may be empty)
    window_title: str = ""        # title of window under click
    x_pct: float = 0.5           # click x as fraction of window width
    y_pct: float = 0.5           # click y as fraction of window height
    # type fields
    text: str = ""
    # hotkey fields
    keys: str = ""
    # scroll fields
    dx: int = 0
    dy: int = 0
    # timing
    timestamp: float = field(default_factory=time.time)
    # agent step fields (set during post-recording review)
    is_agent_step: bool = False
    agent_description: str = ""
    agent_end_state_description: str = ""
    agent_end_state_snapshot: str = ""  # relative path to snapshot png

    def to_step_dict(self) -> dict:
        """Convert to a macro YAML step dict.

        If marked as agent step, emits a gui_agent/instruct step.
        Otherwise uses visual_anchor with window-relative coords or template.
        """
        # Agent step overrides everything
        if self.is_agent_step:
            params: dict = {
                "description": self.agent_description,
                "end_state_description": self.agent_end_state_description,
                "max_steps": 8,
            }
            if self.agent_end_state_snapshot:
                params["end_state_snapshot"] = self.agent_end_state_snapshot
            return {
                "id": f"step_{self.index:03d}_agent",
                "backend": "gui_agent",
                "action": "instruct",
                "params": params,
                "on_failure": "fail",
            }
        if self.kind == "click":
            if self.window_title:
                # Best case: window-relative fractional coordinates
                params: dict = {
                    "window_title": self.window_title,
                    "x_pct": self.x_pct,
                    "y_pct": self.y_pct,
                }
                if self.button != "left":
                    params["button"] = self.button
                if self.double:
                    params["double"] = True
                step = {
                    "id": f"step_{self.index:03d}_click",
                    "backend": "visual_anchor",
                    "action": "click_relative",
                    "params": params,
                    "on_failure": "fail",
                }
                # Attach template as a comment if available (for debugging)
                if self.template_path:
                    step["_template"] = self.template_path
                return step

            elif self.template_path:
                # Has a usable template image
                params = {
                    "template": self.template_path,
                    "confidence": 0.85,
                    "timeout_ms": 5000,
                }
                if self.button != "left":
                    params["button"] = self.button
                if self.double:
                    params["double"] = True
                return {
                    "id": f"step_{self.index:03d}_click",
                    "backend": "visual_anchor",
                    "action": "click_image",
                    "params": params,
                    "on_failure": "fail",
                }

            else:
                # Fallback: screen-relative fractional coordinates
                return {
                    "id": f"step_{self.index:03d}_click",
                    "backend": "visual_anchor",
                    "action": "click_relative",
                    "params": {
                        "x_pct": self.x_pct,
                        "y_pct": self.y_pct,
                    },
                    "on_failure": "fail",
                }
        elif self.kind == "type":
            return {
                "id": f"step_{self.index:03d}_type",
                "backend": "visual_anchor",
                "action": "type_text",
                "params": {"text": self.text},
                "on_failure": "fail",
            }
        elif self.kind == "hotkey":
            return {
                "id": f"step_{self.index:03d}_hotkey",
                "backend": "visual_anchor",
                "action": "hotkey",
                "params": {"keys": self.keys},
                "on_failure": "fail",
            }
        elif self.kind == "scroll":
            return {
                "id": f"step_{self.index:03d}_scroll",
                "backend": "visual_anchor",
                "action": "scroll",
                "params": {
                    "template": self.template_path or "",
                    "dx": self.dx,
                    "dy": self.dy,
                },
                "on_failure": "fail",
            }
        return {}


# ── Window detection ──────────────────────────────────────────────────────────

def _get_active_window_at(x: int, y: int) -> tuple[str, Optional[dict]]:
    """Return (app_name, bounds) of the currently focused window.

    Uses xdotool getwindowfocus — reliable, no text parsing of hostnames,
    works regardless of hostname format.
    """
    import shutil
    import subprocess
    import os

    env = os.environ.copy()
    if "DISPLAY" not in env:
        env["DISPLAY"] = ":0"

    if not shutil.which("xdotool"):
        return "", None

    try:
        # Get geometry of focused window
        gr = subprocess.run(
            ["xdotool", "getwindowfocus", "getwindowgeometry", "--shell"],
            capture_output=True, text=True, env=env, timeout=2
        )
        geo = {}
        for line in gr.stdout.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                geo[k.strip()] = v.strip()

        wx = int(geo.get("X", 0))
        wy = int(geo.get("Y", 0))
        ww = int(geo.get("WIDTH", 0))
        wh = int(geo.get("HEIGHT", 0))
        wid = geo.get("WINDOW", "")

        if not wid or ww == 0 or wh == 0:
            return "", None

        # Get window title
        nr = subprocess.run(
            ["xdotool", "getwindowname", wid],
            capture_output=True, text=True, env=env, timeout=2
        )
        full_title = nr.stdout.strip()

        # Extract app name: last segment after " - "
        # e.g. "macrocli.txt (/tmp) - gedit" → "gedit"
        # Plain titles (e.g. "Terminal") are returned as-is
        if " - " in full_title:
            app_name = full_title.split(" - ")[-1].strip()
        else:
            app_name = full_title.strip()

        bounds = {"x": wx, "y": wy, "width": ww, "height": wh}
        return app_name, bounds

    except Exception:
        return "", None


# ── Template capture ──────────────────────────────────────────────────────────

_TEMPLATE_PADDING = 60   # pixels around click point to capture


def _capture_template(x: int, y: int, output_path: str) -> bool:
    """Capture a small region around (x, y) and save as PNG template.

    Returns False if the region has too little variance (blank/featureless)
    to be useful as a template.
    """
    try:
        import mss
        from PIL import Image
        import numpy as np

        pad = _TEMPLATE_PADDING
        region = {
            "left": max(0, x - pad),
            "top": max(0, y - pad),
            "width": pad * 2,
            "height": pad * 2,
        }
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with mss.mss() as sct:
            raw = sct.grab(region)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

            # Check variance — featureless templates are useless
            arr = np.array(img, dtype=np.float32)
            if arr.std() < 8.0:
                return False  # blank region, skip

            img.save(output_path)
        return True
    except Exception as e:
        print(f"[recorder] Warning: could not capture template: {e}", file=sys.stderr)
        return False


# ── Key accumulation helper ───────────────────────────────────────────────────

_MODIFIER_KEYS = frozenset([
    "ctrl_l", "ctrl_r", "shift", "shift_r", "alt_l", "alt_r",
    "alt_gr", "cmd", "cmd_r", "super_l", "super_r",
])

_KEY_NAME_MAP = {
    "ctrl_l": "ctrl", "ctrl_r": "ctrl",
    "shift_r": "shift",
    "alt_l": "alt", "alt_r": "alt", "alt_gr": "alt",
    "cmd_r": "cmd",
    "super_l": "super", "super_r": "super",
}


def _key_to_str(key) -> str:
    """Convert a pynput Key or KeyCode to a string."""
    try:
        from pynput.keyboard import Key
        if isinstance(key, Key):
            name = key.name  # e.g. "ctrl_l", "shift", "f5"
            return _KEY_NAME_MAP.get(name, name)
        # KeyCode
        if hasattr(key, "char") and key.char:
            return key.char
        if hasattr(key, "vk") and key.vk:
            return f"vk{key.vk}"
    except Exception:
        pass
    return str(key)


# ── Recorder ─────────────────────────────────────────────────────────────────

class MacroRecorder:
    """Records mouse and keyboard events and converts them to macro steps."""

    STOP_HOTKEY = frozenset(["ctrl", "alt", "s"])   # Ctrl+Alt+S to stop

    def __init__(self, macro_name: str, output_dir: str = "."):
        self.macro_name = macro_name
        self.output_dir = Path(output_dir)
        self.templates_dir = self.output_dir / f"{macro_name}_templates"

        self._steps: list[RecordedStep] = []
        self._step_index = 0
        self._pressed_modifiers: set[str] = set()
        self._pending_chars: list[str] = []
        self._last_event_time = time.time()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        # Double-click detection
        self._last_click_pos: Optional[tuple[int, int]] = None
        self._last_click_time: float = 0.0
        self._DOUBLE_CLICK_MS = 400

    def _next_index(self) -> int:
        self._step_index += 1
        return self._step_index

    def _flush_pending_chars(self):
        """Accumulate consecutive character presses into a single type step."""
        if self._pending_chars:
            text = "".join(self._pending_chars)
            step = RecordedStep(
                index=self._next_index(),
                kind="type",
                text=text,
            )
            self._steps.append(step)
            self._pending_chars.clear()

    # ── Mouse callbacks ───────────────────────────────────────────────────────

    def on_click(self, x: int, y: int, button, pressed: bool):
        if not pressed:
            return  # only record press events

        with self._lock:
            self._flush_pending_chars()

            btn_str = button.name if hasattr(button, "name") else str(button)

            # Detect double click
            now = time.time()
            is_double = (
                self._last_click_pos == (x, y)
                and (now - self._last_click_time) * 1000 < self._DOUBLE_CLICK_MS
            )
            if is_double:
                # Upgrade last click step to double=True
                if self._steps and self._steps[-1].kind == "click":
                    self._steps[-1].double = True
                self._last_click_pos = None
                return

            self._last_click_pos = (x, y)
            self._last_click_time = now

            # Try to find the window under the click point
            window_title, window_bounds = _get_active_window_at(x, y)

            # Compute relative coords within window (fallback to screen pct)
            if window_bounds:
                wx, wy = window_bounds["x"], window_bounds["y"]
                ww, wh = window_bounds["width"], window_bounds["height"]
                x_pct = round((x - wx) / ww, 4) if ww > 0 else 0.5
                y_pct = round((y - wy) / wh, 4) if wh > 0 else 0.5
            else:
                window_title = ""
                x_pct = round(x / 1920, 4)
                y_pct = round(y / 1080, 4)

            # Also try to capture a template (useful when region has features)
            idx = self._next_index()
            template_file = str(
                self.templates_dir / f"step_{idx:03d}_click.png"
            )
            captured = _capture_template(x, y, template_file)

            step = RecordedStep(
                index=idx,
                kind="click",
                x=x,
                y=y,
                button=btn_str,
                template_path=template_file if captured else "",
                window_title=window_title,
                x_pct=x_pct,
                y_pct=y_pct,
            )
            self._steps.append(step)
            print(
                f"[recorder] click #{idx} at ({x},{y}) "
                f"window='{window_title}' rel=({x_pct},{y_pct})",
                flush=True
            )

    def on_scroll(self, x: int, y: int, dx: int, dy: int):
        with self._lock:
            self._flush_pending_chars()
            idx = self._next_index()
            # Capture template near scroll position
            template_file = str(
                self.templates_dir / f"step_{idx:03d}_scroll.png"
            )
            captured = _capture_template(x, y, template_file)

            step = RecordedStep(
                index=idx,
                kind="scroll",
                x=x, y=y,
                dx=dx, dy=dy,
                template_path=template_file if captured else "",
            )
            self._steps.append(step)

    # ── Keyboard callbacks ────────────────────────────────────────────────────

    def on_key_press(self, key):
        key_str = _key_to_str(key)

        # Check stop hotkey
        if key_str.lower() in ("ctrl", "alt"):
            self._pressed_modifiers.add(key_str.lower())
        elif key_str.lower() == "s" and self._pressed_modifiers >= {"ctrl", "alt"}:
            print("\n[recorder] Stop hotkey detected (Ctrl+Alt+S). Stopping...", flush=True)
            self._stop_event.set()
            return False  # stop listener

        if key_str in _MODIFIER_KEYS or _KEY_NAME_MAP.get(key_str, key_str) in _MODIFIER_KEYS:
            self._pressed_modifiers.add(_KEY_NAME_MAP.get(key_str, key_str))
            return

        # If modifiers are pressed, it's a hotkey combination
        # But only if the key itself is NOT a modifier
        normalized_key = _KEY_NAME_MAP.get(key_str, key_str)
        is_modifier = normalized_key in {"ctrl", "shift", "alt", "cmd", "super"}
        active_mods = {_KEY_NAME_MAP.get(m, m) for m in self._pressed_modifiers}

        if active_mods and not is_modifier:
            with self._lock:
                self._flush_pending_chars()
                combo = "+".join(sorted(active_mods) + [key_str])
                idx = self._next_index()
                step = RecordedStep(index=idx, kind="hotkey", keys=combo)
                self._steps.append(step)
                print(f"[recorder] hotkey #{idx}: {combo}", flush=True)
        elif not is_modifier:
            # Regular character or special key
            # space key comes as Key.space (len > 1), treat as printable
            is_space = (key_str == "space")
            if len(key_str) == 1 or is_space:
                char = " " if is_space else key_str
                with self._lock:
                    self._pending_chars.append(char)
            else:
                # Special key alone (enter, tab, backspace, etc.)
                with self._lock:
                    self._flush_pending_chars()
                    idx = self._next_index()
                    step = RecordedStep(index=idx, kind="hotkey", keys=key_str)
                    self._steps.append(step)

    def on_key_release(self, key):
        key_str = _key_to_str(key)
        normalized = _KEY_NAME_MAP.get(key_str, key_str)
        self._pressed_modifiers.discard(normalized)

    # ── Main record loop ──────────────────────────────────────────────────────

    def record(self, timeout_s: Optional[float] = None) -> list[RecordedStep]:
        """Start recording. Blocks until Ctrl+Alt+S or timeout_s seconds."""
        try:
            from pynput import mouse as mouse_mod, keyboard as kb_mod
        except ImportError:
            raise ImportError(
                "pynput is required for recording.\n"
                "  pip install pynput"
            )

        self.templates_dir.mkdir(parents=True, exist_ok=True)

        print(
            f"[recorder] Recording '{self.macro_name}'. "
            "Press Ctrl+Alt+S to stop.",
            flush=True,
        )

        mouse_listener = mouse_mod.Listener(
            on_click=self.on_click,
            on_scroll=self.on_scroll,
        )
        kb_listener = kb_mod.Listener(
            on_press=self.on_key_press,
            on_release=self.on_key_release,
        )

        mouse_listener.start()
        kb_listener.start()

        try:
            self._stop_event.wait(timeout=timeout_s)
        except KeyboardInterrupt:
            pass
        finally:
            mouse_listener.stop()
            kb_listener.stop()

        with self._lock:
            self._flush_pending_chars()

        print(f"[recorder] Recorded {len(self._steps)} steps.", flush=True)
        return self._steps

    # ── YAML output ───────────────────────────────────────────────────────────

    def to_yaml(self, parameters: Optional[dict] = None) -> str:
        """Generate macro YAML from recorded steps.

        Args:
            parameters: Dict of {param_name: spec} built by
                        apply_parameterization(). If None, all type_text
                        values remain hardcoded.
        """
        steps = [s.to_step_dict() for s in self._steps if s.to_step_dict()]

        macro = {
            "name": self.macro_name,
            "version": "1.0",
            "description": f"Recorded macro: {self.macro_name}",
            "tags": ["recorded", "visual_anchor"],
            "parameters": parameters or {},
            "preconditions": [],
            "steps": steps,
            "postconditions": [],
            "outputs": [],
            "agent_hints": {
                "danger_level": "moderate",
                "side_effects": ["gui_interaction"],
                "reversible": False,
                "recorded": True,
            },
        }
        return yaml.dump(macro, allow_unicode=True, sort_keys=False,
                         default_flow_style=False)

    def save(self, output_path: Optional[str] = None,
             parameters: Optional[dict] = None) -> str:
        """Write the generated YAML to a file. Returns the path."""
        if output_path is None:
            output_path = str(self.output_dir / f"{self.macro_name}.yaml")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(
            self.to_yaml(parameters=parameters), encoding="utf-8"
        )
        print(f"[recorder] Saved macro to: {output_path}", flush=True)
        return output_path

    def save_as_package(
        self,
        output_dir: Optional[str] = None,
        parameters: Optional[dict] = None,
    ) -> str:
        """Save as a macro package folder:
            <macro_name>/
              macro.yaml
              snapshots/
                step_XXX_end_state.png  (copied from recorded locations)

        Returns path to macro.yaml.
        """
        pkg_dir = Path(output_dir or self.output_dir) / self.macro_name
        pkg_dir.mkdir(parents=True, exist_ok=True)
        snapshots_dir = pkg_dir / "snapshots"
        snapshots_dir.mkdir(exist_ok=True)

        # Copy any end_state snapshots into the package and update paths
        for step in self._steps:
            if step.is_agent_step and step.agent_end_state_snapshot:
                src = Path(step.agent_end_state_snapshot)
                if src.is_file():
                    dst = snapshots_dir / src.name
                    import shutil
                    if src.resolve() != dst.resolve():
                        shutil.copy2(src, dst)
                    # Update path to be relative to macro.yaml
                    step.agent_end_state_snapshot = f"snapshots/{src.name}"

        yaml_path = str(pkg_dir / "macro.yaml")
        Path(yaml_path).write_text(
            self.to_yaml(parameters=parameters), encoding="utf-8"
        )
        print(f"[recorder] Saved macro package to: {pkg_dir}/", flush=True)
        return yaml_path

    # ── Agent step review ─────────────────────────────────────────────────────

    def interactive_agent_review(self, snapshots_dir: Optional[str] = None) -> None:
        """Interactively review all steps and mark some as agent steps.

        For each step the user can:
          - Press Enter → keep as fixed step
          - Type 'a'   → mark as agent step, then provide description,
                         end_state_description, and take a snapshot

        snapshots_dir: where to save end_state snapshots (default: output_dir/snapshots)
        """
        snap_dir = Path(snapshots_dir or self.output_dir / "snapshots")
        snap_dir.mkdir(parents=True, exist_ok=True)

        print()
        print("─" * 60)
        print("  Step Review — mark steps as 'fixed' or 'agent'")
        print("  Enter = fixed (fast, deterministic)")
        print("  a     = agent step (Gemini decides at runtime)")
        print("─" * 60)

        for i, step in enumerate(self._steps):
            # Build a human-readable description of the step
            if step.kind == "click":
                step_desc = f"click {step.window_title or 'screen'} ({step.x_pct:.2f}, {step.y_pct:.2f})"
            elif step.kind == "type":
                preview = step.text[:40] + "..." if len(step.text) > 40 else step.text
                step_desc = f"type_text {preview!r}"
            elif step.kind == "hotkey":
                step_desc = f"hotkey {step.keys}"
            elif step.kind == "scroll":
                step_desc = f"scroll dy={step.dy}"
            else:
                step_desc = step.kind

            print(f"\n  [{i+1}/{len(self._steps)}] {step_desc}")

            try:
                choice = input("  → fixed or agent? [Enter=fixed / a=agent]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if choice != "a":
                continue

            # Mark as agent step
            step.is_agent_step = True

            try:
                step.agent_description = input(
                    "  → Describe what this step needs to do:\n    "
                ).strip()
                step.agent_end_state_description = input(
                    "  → Describe the target end state (what should the screen show):\n    "
                ).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            # Capture end-state snapshot
            print("  → Now manually operate the UI to reach the end state.")
            try:
                input("    Press Enter when ready to take snapshot...")
            except (EOFError, KeyboardInterrupt):
                print()
                continue

            snapshot_path = str(snap_dir / f"step_{step.index:03d}_end_state.png")
            if self._capture_end_state_snapshot(snapshot_path):
                step.agent_end_state_snapshot = snapshot_path
                print(f"  ✓ Snapshot saved: {snapshot_path}")
            else:
                print("  ⚠ Snapshot failed — no snapshot will be used for this step.")

        print()
        print("─" * 60)
        agent_count = sum(1 for s in self._steps if s.is_agent_step)
        fixed_count = len(self._steps) - agent_count
        print(f"  Review complete: {fixed_count} fixed, {agent_count} agent steps")
        print("─" * 60)

    def _capture_end_state_snapshot(self, output_path: str) -> bool:
        """Capture the current screen and save as end-state snapshot."""
        try:
            import mss
            from PIL import Image
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                raw = sct.grab(monitor)
                img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
                img.save(output_path)
            return True
        except Exception as e:
            print(f"[recorder] Snapshot failed: {e}", file=sys.stderr)
            return False

    # ── Parameterization ──────────────────────────────────────────────────────

    def get_type_steps(self) -> list[tuple[int, "RecordedStep"]]:
        """Return (list_index, step) for every non-empty type_text step."""
        return [
            (i, s) for i, s in enumerate(self._steps)
            if s.kind == "type" and s.text.strip()
        ]

    def apply_parameterization(
        self, assignments: dict[int, str]
    ) -> dict[str, dict]:
        """Replace type_text values with ${param} placeholders in-place.

        Args:
            assignments: {list_index: param_name} for steps to parameterize.
                         Steps not present keep their hardcoded value.

        Returns:
            parameters block ready to pass into to_yaml().
        """
        parameters: dict[str, dict] = {}
        for idx, param_name in assignments.items():
            step = self._steps[idx]
            original = step.text
            step.text = f"${{{param_name}}}"

            # Infer type from the original value
            ptype = "string"
            try:
                int(original)
                ptype = "integer"
            except ValueError:
                try:
                    float(original)
                    ptype = "float"
                except ValueError:
                    pass

            parameters[param_name] = {
                "type": ptype,
                "required": True,
                "description": f"Value typed at step {idx + 1}",
                "example": original,
            }
        return parameters
