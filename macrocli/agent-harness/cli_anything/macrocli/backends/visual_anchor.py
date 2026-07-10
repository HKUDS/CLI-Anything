"""VisualAnchorBackend — find UI elements by image template and interact.

Approach:
  1. Capture full screen with mss (pure Python, cross-platform)
  2. Find the template image inside the screenshot using numpy correlation
  3. Use pynput to click / type / scroll at the discovered coordinates

This backend never uses hardcoded absolute coordinates in macro definitions.
Instead, macros store small PNG templates of the UI elements they want to
interact with, and coordinates are computed at runtime.

Supported actions:

  click_image     — find template on screen and click its center
  click_relative  — click at (x_pct, y_pct) relative to a named window bounds
  wait_image      — wait until template appears on screen
  type_text       — type a string (keyboard injection, no coordinates needed)
  hotkey          — send a keyboard shortcut
  scroll          — scroll at the position of a template image
  capture_region  — screenshot a region and save it (for template creation)

Example YAML steps:

    - backend: visual_anchor
      action: click_image
      params:
        template: templates/export_button.png
        confidence: 0.85          # 0..1, lower = more tolerant
        timeout_ms: 5000          # wait this long for the image to appear

    - backend: visual_anchor
      action: click_relative
      params:
        window_title: "Draw.io"   # partial window title match
        x_pct: 0.5                # 50% across the window
        y_pct: 0.1                # 10% down the window

    - backend: visual_anchor
      action: type_text
      params:
        text: "output.png"
        interval_ms: 30           # delay between key presses

    - backend: visual_anchor
      action: hotkey
      params:
        keys: ctrl+shift+e        # + separated

    - backend: visual_anchor
      action: wait_image
      params:
        template: templates/dialog_ok.png
        timeout_ms: 10000

    - backend: visual_anchor
      action: capture_region
      params:
        output: templates/my_button.png
        x: 100
        y: 200
        width: 80
        height: 30
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

from cli_anything.macrocli.backends.base import Backend, BackendContext, StepResult
from cli_anything.macrocli.core.macro_model import MacroStep, substitute


def _x_env() -> dict:
    """Return env dict with DISPLAY set, for subprocess calls to X tools."""
    env = os.environ.copy()
    if "DISPLAY" not in env:
        env["DISPLAY"] = ":0"
    return env


# ── lazy imports (only needed when backend is actually used) ──────────────────

def _require_numpy():
    try:
        import numpy as np
        return np
    except ImportError:
        raise ImportError(
            "numpy is required for the visual_anchor backend.\n"
            "  pip install numpy"
        )


def _require_pil():
    try:
        from PIL import Image
        return Image
    except ImportError:
        raise ImportError(
            "Pillow is required for the visual_anchor backend.\n"
            "  pip install Pillow"
        )


def _require_mss():
    try:
        import mss
        return mss
    except ImportError:
        raise ImportError(
            "mss is required for screen capture.\n"
            "  pip install mss"
        )


def _require_pynput():
    try:
        from pynput import mouse as _m, keyboard as _k
        return _m, _k
    except ImportError:
        raise ImportError(
            "pynput is required for mouse/keyboard control.\n"
            "  pip install pynput"
        )


# ── template matching ─────────────────────────────────────────────────────────

def _load_image_as_array(path: str):
    """Load an image file as a numpy uint8 RGB array."""
    np = _require_numpy()
    Image = _require_pil()
    img = Image.open(path).convert("RGB")
    return np.array(img, dtype=np.uint8)


def _screenshot_as_array():
    """Capture the full screen and return as numpy RGB array."""
    np = _require_numpy()
    mss = _require_mss()
    Image = _require_pil()
    with mss.mss() as sct:
        # Monitor 1 = first physical monitor (index 0 = all monitors combined)
        monitor = sct.monitors[1]
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return np.array(img, dtype=np.uint8), monitor


def _find_template(
    screen: "np.ndarray",
    template: "np.ndarray",
    confidence: float = 0.85,
    step: int = 1,
) -> Optional[tuple[int, int, float]]:
    """Find template in screen.  Returns (center_x, center_y, score) or None.

    score is 0..1 where 1 = perfect match.
    Confidence threshold: only return match if score >= confidence.
    """
    np = _require_numpy()

    sh, sw = screen.shape[:2]
    th, tw = template.shape[:2]

    if th > sh or tw > sw:
        return None

    screen_f = screen.astype(np.float32)
    tmpl_f = template.astype(np.float32)
    tmpl_norm = tmpl_f - tmpl_f.mean()
    tmpl_std = tmpl_f.std()
    if tmpl_std < 1e-6:
        return None  # blank template

    best_score = -1.0
    best_pos: Optional[tuple[int, int]] = None

    for y in range(0, sh - th + 1, step):
        for x in range(0, sw - tw + 1, step):
            region = screen_f[y:y + th, x:x + tw]
            region_norm = region - region.mean()
            region_std = region.std()
            if region_std < 1e-6:
                continue
            score = float(
                (region_norm * tmpl_norm).sum()
                / (th * tw * region_std * tmpl_std)
            )
            if score > best_score:
                best_score = score
                best_pos = (x + tw // 2, y + th // 2)

    if best_pos is None or best_score < confidence:
        return None

    return (best_pos[0], best_pos[1], best_score)


def _wait_for_template(
    template_array: "np.ndarray",
    confidence: float,
    timeout_ms: int,
    poll_ms: int = 300,
) -> Optional[tuple[int, int, float]]:
    """Poll until template found on screen or timeout. Returns match or None."""
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        screen, _ = _screenshot_as_array()
        result = _find_template(screen, template_array, confidence)
        if result is not None:
            return result
        time.sleep(poll_ms / 1000.0)
    return None


# ── window bounds helper ──────────────────────────────────────────────────────

def _get_window_bounds(title_fragment: str) -> Optional[dict]:
    """Return {x, y, width, height} of the first window whose title contains
    title_fragment.  Works on Linux (xwininfo + wmctrl) and macOS (AppleScript).
    Returns None if not found or not available.
    """
    import subprocess
    import shutil
    import platform

    system = platform.system()

    if system == "Linux":
        # Try wmctrl first (most reliable)
        if shutil.which("wmctrl"):
            r = subprocess.run(
                ["wmctrl", "-lG"], capture_output=True, text=True, env=_x_env()
            )
            for line in r.stdout.splitlines():
                parts = line.split(None, 9)
                if len(parts) >= 9 and title_fragment.lower() in parts[-1].lower():
                    try:
                        # wmctrl -lG: wid desktop x y w h host title
                        x, y, w, h = int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5])
                        return {"x": x, "y": y, "width": w, "height": h}
                    except ValueError:
                        pass
        # Fallback: xwininfo
        if shutil.which("xwininfo"):
            r = subprocess.run(
                ["xwininfo", "-name", title_fragment],
                capture_output=True, text=True, env=_x_env()
            )
            bounds = {}
            for line in r.stdout.splitlines():
                line = line.strip()
                if "Absolute upper-left X:" in line:
                    bounds["x"] = int(line.split()[-1])
                elif "Absolute upper-left Y:" in line:
                    bounds["y"] = int(line.split()[-1])
                elif "Width:" in line:
                    bounds["width"] = int(line.split()[-1])
                elif "Height:" in line:
                    bounds["height"] = int(line.split()[-1])
            if len(bounds) == 4:
                return bounds

    elif system == "Darwin":
        # macOS: use AppleScript to get window position
        script = f"""
        tell application "System Events"
            set ws to every window of every process whose name contains "{title_fragment}"
            if ws is not {{}} then
                set w to item 1 of item 1 of ws
                set p to position of w
                set s to size of w
                return (item 1 of p as text) & "," & (item 2 of p as text) & "," & (item 1 of s as text) & "," & (item 2 of s as text)
            end if
        end tell
        """
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            parts = r.stdout.strip().split(",")
            if len(parts) == 4:
                try:
                    return {
                        "x": int(parts[0]), "y": int(parts[1]),
                        "width": int(parts[2]), "height": int(parts[3])
                    }
                except ValueError:
                    pass

    return None


# ── Backend ───────────────────────────────────────────────────────────────────

class VisualAnchorBackend(Backend):
    """Find UI elements by image template and interact with them."""

    name = "visual_anchor"
    priority = 75  # between file_transform(70) and gui_macro(80)

    def execute(self, step: MacroStep, params: dict, context: BackendContext) -> StepResult:
        t0 = time.time()
        action = step.action
        p = substitute(step.params, params)

        if context.dry_run:
            return StepResult(
                success=True,
                output={"dry_run": True, "action": action},
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        dispatch = {
            "click_image":    self._click_image,
            "click_relative": self._click_relative,
            "wait_image":     self._wait_image,
            "type_text":      self._type_text,
            "hotkey":         self._hotkey,
            "scroll":         self._scroll,
            "drag":           self._drag,
            "drag_relative":  self._drag_relative,
            "capture_region": self._capture_region,
        }

        handler = dispatch.get(action)
        if handler is None:
            return StepResult(
                success=False,
                error=f"VisualAnchorBackend: unknown action '{action}'. "
                      f"Available: {sorted(dispatch)}",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        try:
            output = handler(p, context)
            return StepResult(
                success=True,
                output=output or {},
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )
        except Exception as exc:
            return StepResult(
                success=False,
                error=f"VisualAnchorBackend.{action}: {exc}",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

    def is_available(self) -> bool:
        for pkg in ("mss", "numpy", "PIL", "pynput"):
            try:
                __import__(pkg if pkg != "PIL" else "PIL.Image")
            except ImportError:
                return False
        return True

    # ── Actions ──────────────────────────────────────────────────────────────

    def _click_image(self, p: dict, context: BackendContext) -> dict:
        """Find template on screen and click its center."""
        template_path = p.get("template", "")
        if not template_path or not Path(template_path).is_file():
            raise FileNotFoundError(
                f"Template image not found: '{template_path}'. "
                "Use 'macro record' or 'capture_region' to create one."
            )

        confidence = float(p.get("confidence", 0.85))
        timeout_ms = int(p.get("timeout_ms", 5000))
        button = p.get("button", "left")   # left | right | middle
        double = bool(p.get("double", False))

        template_arr = _load_image_as_array(template_path)
        match = _wait_for_template(template_arr, confidence, timeout_ms)

        if match is None:
            raise RuntimeError(
                f"Template not found on screen after {timeout_ms}ms: {template_path} "
                f"(confidence={confidence})"
            )

        cx, cy, score = match
        _mouse_click(cx, cy, button=button, double=double)

        return {
            "clicked_at": [cx, cy],
            "match_score": round(score, 4),
            "template": template_path,
        }

    def _click_relative(self, p: dict, context: BackendContext) -> dict:
        """Click at a fractional position within a named window."""
        title = p.get("window_title", "")
        x_pct = float(p.get("x_pct", 0.5))
        y_pct = float(p.get("y_pct", 0.5))
        button = p.get("button", "left")
        double = bool(p.get("double", False))

        if title:
            bounds = _get_window_bounds(title)
            if bounds is None:
                raise RuntimeError(
                    f"Window not found: '{title}'. "
                    "Make sure the application is open and the title matches."
                )
            cx = int(bounds["x"] + bounds["width"] * x_pct)
            cy = int(bounds["y"] + bounds["height"] * y_pct)
        else:
            # Relative to full screen
            _, monitor = _screenshot_as_array()
            cx = int(monitor["width"] * x_pct)
            cy = int(monitor["height"] * y_pct)

        _mouse_click(cx, cy, button=button, double=double)
        return {"clicked_at": [cx, cy], "x_pct": x_pct, "y_pct": y_pct}

    def _wait_image(self, p: dict, context: BackendContext) -> dict:
        """Wait until a template image appears on screen."""
        template_path = p.get("template", "")
        if not template_path or not Path(template_path).is_file():
            raise FileNotFoundError(f"Template image not found: '{template_path}'")

        confidence = float(p.get("confidence", 0.85))
        timeout_ms = int(p.get("timeout_ms", 10000))

        template_arr = _load_image_as_array(template_path)
        match = _wait_for_template(template_arr, confidence, timeout_ms)

        if match is None:
            raise RuntimeError(
                f"Template never appeared within {timeout_ms}ms: {template_path}"
            )

        cx, cy, score = match
        return {"found_at": [cx, cy], "match_score": round(score, 4)}

    def _type_text(self, p: dict, context: BackendContext) -> dict:
        """Type a string using keyboard injection."""
        text = p.get("text", "")
        interval_ms = int(p.get("interval_ms", 30))
        if not text:
            raise ValueError("type_text requires 'text' param.")

        _, keyboard_mod = _require_pynput()
        ctrl = keyboard_mod.Controller()

        import time as _time
        for char in text:
            ctrl.press(char)
            ctrl.release(char)
            if interval_ms > 0:
                _time.sleep(interval_ms / 1000.0)

        return {"typed": len(text), "text_preview": text[:40]}

    def _hotkey(self, p: dict, context: BackendContext) -> dict:
        """Send a keyboard shortcut (e.g. ctrl+shift+e)."""
        keys_str = p.get("keys", "")
        if not keys_str:
            raise ValueError("hotkey requires 'keys' param (e.g. 'ctrl+s').")

        _, keyboard_mod = _require_pynput()
        Key = keyboard_mod.Key
        ctrl = keyboard_mod.Controller()

        # Parse keys: ctrl+shift+e → [Key.ctrl, Key.shift, 'e']
        key_objects = []
        for k in keys_str.split("+"):
            k = k.strip().lower()
            # Map common names to pynput Key enum
            mapping = {
                "ctrl": Key.ctrl, "control": Key.ctrl,
                "shift": Key.shift,
                "alt": Key.alt,
                "cmd": Key.cmd, "super": Key.cmd, "win": Key.cmd,
                "enter": Key.enter, "return": Key.enter,
                "tab": Key.tab,
                "esc": Key.esc, "escape": Key.esc,
                "space": Key.space,
                "backspace": Key.backspace,
                "delete": Key.delete,
                "up": Key.up, "down": Key.down,
                "left": Key.left, "right": Key.right,
                "home": Key.home, "end": Key.end,
                "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4,
                "f5": Key.f5, "f6": Key.f6, "f7": Key.f7, "f8": Key.f8,
                "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
            }
            if k in mapping:
                key_objects.append(mapping[k])
            elif len(k) == 1:
                key_objects.append(k)
            else:
                raise ValueError(f"Unknown key name: '{k}'")

        # Press all, then release all in reverse
        for k in key_objects:
            ctrl.press(k)
        for k in reversed(key_objects):
            ctrl.release(k)

        return {"hotkey": keys_str}

    def _scroll(self, p: dict, context: BackendContext) -> dict:
        """Scroll at the position of a template image."""
        template_path = p.get("template", "")
        dx = int(p.get("dx", 0))
        dy = int(p.get("dy", -3))   # negative = scroll down
        timeout_ms = int(p.get("timeout_ms", 5000))
        confidence = float(p.get("confidence", 0.85))

        if template_path and Path(template_path).is_file():
            template_arr = _load_image_as_array(template_path)
            match = _wait_for_template(template_arr, confidence, timeout_ms)
            if match is None:
                raise RuntimeError(f"Template not found: {template_path}")
            cx, cy, _ = match
        else:
            # Scroll at current mouse position
            mouse_mod, _ = _require_pynput()
            pos = mouse_mod.Controller().position
            cx, cy = int(pos[0]), int(pos[1])

        mouse_mod, _ = _require_pynput()
        mouse_ctrl = mouse_mod.Controller()
        mouse_ctrl.position = (cx, cy)
        mouse_ctrl.scroll(dx, dy)

        return {"scrolled_at": [cx, cy], "dx": dx, "dy": dy}

    def _drag(self, p: dict, context: BackendContext) -> dict:
        """Drag from one template image to another (or to absolute coords).

        Params:
          from_template:  path to template image for drag start (optional)
          to_template:    path to template image for drag end (optional)
          from_x / from_y: fallback absolute coords if no from_template
          to_x   / to_y:   fallback absolute coords if no to_template
          button:          left | right | middle (default left)
          duration_ms:     how long to hold during drag (default 200)
          confidence:      template match threshold (default 0.85)
          timeout_ms:      how long to wait for templates (default 5000)
        """
        button = p.get("button", "left")
        duration_ms = int(p.get("duration_ms", 200))
        confidence = float(p.get("confidence", 0.85))
        timeout_ms = int(p.get("timeout_ms", 5000))

        # Resolve start position
        from_tmpl = p.get("from_template", "")
        if from_tmpl and Path(from_tmpl).is_file():
            tmpl = _load_image_as_array(from_tmpl)
            match = _wait_for_template(tmpl, confidence, timeout_ms)
            if match is None:
                raise RuntimeError(f"drag: from_template not found: {from_tmpl}")
            fx, fy = match[0], match[1]
        else:
            fx = int(p.get("from_x", 0))
            fy = int(p.get("from_y", 0))

        # Resolve end position
        to_tmpl = p.get("to_template", "")
        if to_tmpl and Path(to_tmpl).is_file():
            tmpl = _load_image_as_array(to_tmpl)
            match = _wait_for_template(tmpl, confidence, timeout_ms)
            if match is None:
                raise RuntimeError(f"drag: to_template not found: {to_tmpl}")
            tx, ty = match[0], match[1]
        else:
            tx = int(p.get("to_x", fx))
            ty = int(p.get("to_y", fy))

        _mouse_drag(fx, fy, tx, ty, button=button, duration_ms=duration_ms)
        return {"dragged_from": [fx, fy], "dragged_to": [tx, ty]}

    def _drag_relative(self, p: dict, context: BackendContext) -> dict:
        """Drag within a window using fractional coordinates.

        Params:
          window_title:     partial window title (uses focused window if empty)
          from_x_pct:       drag start x as fraction of window width
          from_y_pct:       drag start y as fraction of window height
          to_x_pct:         drag end x as fraction of window width
          to_y_pct:         drag end y as fraction of window height
          button:           left | right | middle (default left)
          duration_ms:      hold duration in ms (default 200)
        """
        title = p.get("window_title", "")
        button = p.get("button", "left")
        duration_ms = int(p.get("duration_ms", 200))

        if title:
            bounds = _get_window_bounds(title)
            if bounds is None:
                raise RuntimeError(f"drag_relative: window not found: '{title}'")
            wx, wy = bounds["x"], bounds["y"]
            ww, wh = bounds["width"], bounds["height"]
        else:
            _, monitor = _screenshot_as_array()
            wx, wy = 0, 0
            ww, wh = monitor["width"], monitor["height"]

        fx = int(wx + ww * float(p.get("from_x_pct", 0.0)))
        fy = int(wy + wh * float(p.get("from_y_pct", 0.0)))
        tx = int(wx + ww * float(p.get("to_x_pct", 1.0)))
        ty = int(wy + wh * float(p.get("to_y_pct", 1.0)))

        _mouse_drag(fx, fy, tx, ty, button=button, duration_ms=duration_ms)
        return {
            "dragged_from": [fx, fy],
            "dragged_to": [tx, ty],
            "from_pct": [p.get("from_x_pct"), p.get("from_y_pct")],
            "to_pct": [p.get("to_x_pct"), p.get("to_y_pct")],
        }

    def _capture_region(self, p: dict, context: BackendContext) -> dict:
        """Screenshot a region of the screen and save as a template."""
        output_path = p.get("output", "")
        if not output_path:
            raise ValueError("capture_region requires 'output' param.")

        x = int(p.get("x", 0))
        y = int(p.get("y", 0))
        width = int(p.get("width", 100))
        height = int(p.get("height", 50))

        mss = _require_mss()
        Image = _require_pil()

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with mss.mss() as sct:
            region = {"left": x, "top": y, "width": width, "height": height}
            raw = sct.grab(region)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            img.save(output_path)

        size = Path(output_path).stat().st_size
        return {
            "saved": output_path,
            "region": [x, y, width, height],
            "file_size": size,
        }


# ── pynput mouse helpers ──────────────────────────────────────────────────────

def _mouse_click(x: int, y: int, button: str = "left", double: bool = False):
    """Move mouse to (x, y) and click."""
    mouse_mod, _ = _require_pynput()
    Button = mouse_mod.Button
    ctrl = mouse_mod.Controller()

    btn_map = {
        "left": Button.left,
        "right": Button.right,
        "middle": Button.middle,
    }
    btn = btn_map.get(button.lower(), Button.left)

    ctrl.position = (x, y)
    time.sleep(0.05)
    ctrl.press(btn)
    ctrl.release(btn)
    if double:
        time.sleep(0.08)
        ctrl.press(btn)
        ctrl.release(btn)


def _mouse_drag(
    fx: int, fy: int, tx: int, ty: int,
    button: str = "left", duration_ms: int = 200
):
    """Press at (fx, fy), move to (tx, ty) over duration_ms, release.

    Tries xdotool first (works with Qt5/KDE apps), falls back to pynput.
    """
    import shutil, subprocess, os

    env = os.environ.copy()
    if "DISPLAY" not in env:
        env["DISPLAY"] = ":0"

    if shutil.which("xdotool"):
        # xdotool is more reliable with Qt5 apps
        steps = max(5, duration_ms // 30)
        subprocess.run(["xdotool", "mousemove", str(fx), str(fy)], env=env)
        time.sleep(0.05)
        subprocess.run(["xdotool", "mousedown", "1"], env=env)
        time.sleep(0.05)
        for i in range(1, steps + 1):
            ix = int(fx + (tx - fx) * i / steps)
            iy = int(fy + (ty - fy) * i / steps)
            subprocess.run(["xdotool", "mousemove", str(ix), str(iy)], env=env)
            time.sleep(duration_ms / 1000.0 / steps)
        subprocess.run(["xdotool", "mousemove", str(tx), str(ty)], env=env)
        time.sleep(0.05)
        subprocess.run(["xdotool", "mouseup", "1"], env=env)
        return

    # Fallback: pynput
    mouse_mod, _ = _require_pynput()
    Button = mouse_mod.Button
    ctrl = mouse_mod.Controller()
    btn_map = {"left": Button.left, "right": Button.right, "middle": Button.middle}
    btn = btn_map.get(button.lower(), Button.left)

    ctrl.position = (fx, fy)
    time.sleep(0.05)
    ctrl.press(btn)
    time.sleep(0.05)

    steps = max(10, duration_ms // 20)
    step_sleep = duration_ms / 1000.0 / steps
    for i in range(1, steps + 1):
        ix = int(fx + (tx - fx) * i / steps)
        iy = int(fy + (ty - fy) * i / steps)
        ctrl.position = (ix, iy)
        time.sleep(step_sleep)

    ctrl.position = (tx, ty)
    time.sleep(0.05)
    ctrl.release(btn)
