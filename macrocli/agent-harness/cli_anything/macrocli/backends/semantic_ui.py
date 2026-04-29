"""SemanticUIBackend — drive applications via accessibility APIs and keyboard shortcuts.

Backends by platform:
  Linux:   AT-SPI via python3-pyatspi  (apt install python3-pyatspi)
           Fallback: xdotool for keyboard/shortcuts
  macOS:   ApplicationServices / Quartz via pyobjc
           Fallback: osascript (AppleScript)
  Windows: UI Automation via pywinauto  (pip install pywinauto)

Action space:

  shortcut        — send keyboard shortcut to focused window
  type_text       — type text into focused control
  menu_click      — activate a menu item by path
  button_click    — click a button by label/role
  wait_for_window — wait for a window with given title to appear
  focus_window    — bring a window to foreground
  get_controls    — list interactive controls (for discovery)

Example YAML steps:

    - backend: semantic_ui
      action: menu_click
      params:
        menu_path: [File, Export As, PNG Image]

    - backend: semantic_ui
      action: shortcut
      params:
        keys: ctrl+shift+e

    - backend: semantic_ui
      action: wait_for_window
      params:
        title_contains: Export
        timeout_ms: 5000

    - backend: semantic_ui
      action: button_click
      params:
        label: OK

    - backend: semantic_ui
      action: focus_window
      params:
        title_contains: Inkscape

    - backend: semantic_ui
      action: get_controls
      params:
        window_title: Inkscape
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
from typing import Optional

from cli_anything.macrocli.backends.base import Backend, BackendContext, StepResult
from cli_anything.macrocli.core.macro_model import MacroStep, substitute

_SYSTEM = platform.system()


def _x_env() -> dict:
    """Return env dict with DISPLAY set, for subprocess calls to X tools."""
    env = os.environ.copy()
    if "DISPLAY" not in env:
        env["DISPLAY"] = ":0"
    return env


# ── AT-SPI helpers (Linux) ────────────────────────────────────────────────────

def _atspi_available() -> bool:
    try:
        import pyatspi  # noqa: F401
        return True
    except ImportError:
        return False


def _atspi_find_app(name_fragment: str):
    """Return the first AT-SPI application matching name_fragment."""
    import pyatspi
    desktop = pyatspi.Registry.getDesktop(0)
    for app in desktop:
        if app and name_fragment.lower() in (app.name or "").lower():
            return app
    return None


def _atspi_find_control(root, role_name: str, label_fragment: str, max_depth: int = 20):
    """BFS search for a control by role and label."""
    import pyatspi
    role_map = {
        "button": pyatspi.ROLE_PUSH_BUTTON,
        "menu": pyatspi.ROLE_MENU,
        "menu_item": pyatspi.ROLE_MENU_ITEM,
        "menu_bar": pyatspi.ROLE_MENU_BAR,
        "text": pyatspi.ROLE_TEXT,
        "combo_box": pyatspi.ROLE_COMBO_BOX,
        "check_box": pyatspi.ROLE_CHECK_BOX,
        "radio": pyatspi.ROLE_RADIO_BUTTON,
        "list_item": pyatspi.ROLE_LIST_ITEM,
        "dialog": pyatspi.ROLE_DIALOG,
        "window": pyatspi.ROLE_FRAME,
    }
    target_role = role_map.get(role_name.lower())

    from collections import deque
    queue = deque([(root, 0)])
    while queue:
        node, depth = queue.popleft()
        if depth > max_depth:
            continue
        try:
            node_role = node.getRole()
            node_name = node.name or ""
            if (target_role is None or node_role == target_role):
                if label_fragment.lower() in node_name.lower():
                    return node
            for i in range(node.childCount):
                child = node.getChildAtIndex(i)
                if child:
                    queue.append((child, depth + 1))
        except Exception:
            continue
    return None


def _atspi_menu_path(app, menu_path: list[str]):
    """Navigate a menu path and activate the final item."""
    import pyatspi

    # Find the menu bar
    menu_bar = _atspi_find_control(app, "menu_bar", "", max_depth=3)
    if menu_bar is None:
        raise RuntimeError("AT-SPI: menu bar not found in application.")

    current = menu_bar
    for label in menu_path:
        item = _atspi_find_control(current, "menu", label)
        if item is None:
            item = _atspi_find_control(current, "menu_item", label)
        if item is None:
            raise RuntimeError(f"AT-SPI: menu item '{label}' not found.")
        # Activate / click
        try:
            action = item.queryAction()
            for i in range(action.nActions):
                if action.getName(i).lower() in ("click", "activate", "open"):
                    action.doAction(i)
                    break
        except Exception:
            pass
        current = item
        time.sleep(0.15)

    return True


# ── xdotool helpers (Linux fallback) ─────────────────────────────────────────

def _xdotool_key(keys: str) -> None:
    if not shutil.which("xdotool"):
        raise RuntimeError("xdotool not found. Install with: apt install xdotool")
    # ctrl+shift+e → ctrl+shift+e (xdotool accepts this format directly)
    subprocess.run(["xdotool", "key", "--clearmodifiers", keys], check=True, env=_x_env())


def _xdotool_type(text: str) -> None:
    if not shutil.which("xdotool"):
        raise RuntimeError("xdotool not found. Install with: apt install xdotool")
    subprocess.run(["xdotool", "type", "--clearmodifiers", "--delay", "30", text], check=True, env=_x_env())


def _xdotool_focus(title: str) -> None:
    if not shutil.which("xdotool"):
        raise RuntimeError("xdotool not found. Install with: apt install xdotool")
    subprocess.run(
        ["xdotool", "search", "--name", title, "windowfocus", "--sync"],
        check=True, env=_x_env(),
    )


# ── osascript helpers (macOS) ─────────────────────────────────────────────────

def _osascript(script: str) -> str:
    r = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True
    )
    if r.returncode != 0:
        raise RuntimeError(f"osascript failed: {r.stderr.strip()}")
    return r.stdout.strip()


def _macos_menu_click(app_name: str, menu_path: list[str]) -> None:
    if len(menu_path) < 2:
        raise ValueError("menu_path needs at least 2 elements (menu name + item).")
    menu_name = menu_path[0]
    items = menu_path[1:]
    # Build nested AppleScript path
    item_script = " of menu ".join(
        [f'menu item "{i}"' for i in reversed(items)]
    )
    script = f"""
    tell application "{app_name}"
        activate
    end tell
    tell application "System Events"
        tell process "{app_name}"
            click {item_script} of menu "{menu_name}" of menu bar 1
        end tell
    end tell
    """
    _osascript(script)


# ── pywinauto helpers (Windows) ───────────────────────────────────────────────

def _win_find_app(title_fragment: str):
    from pywinauto import Application, findwindows
    handles = findwindows.find_windows(title_re=f".*{title_fragment}.*")
    if not handles:
        raise RuntimeError(f"Window not found: '{title_fragment}'")
    app = Application().connect(handle=handles[0])
    return app.window(handle=handles[0])


# ── Backend ───────────────────────────────────────────────────────────────────

class SemanticUIBackend(Backend):
    """Drive applications through semantic (accessibility) controls."""

    name = "semantic_ui"
    priority = 50

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
            "shortcut":        self._shortcut,
            "type_text":       self._type_text,
            "menu_click":      self._menu_click,
            "button_click":    self._button_click,
            "wait_for_window": self._wait_for_window,
            "focus_window":    self._focus_window,
            "get_controls":    self._get_controls,
        }

        handler = dispatch.get(action)
        if handler is None:
            return StepResult(
                success=False,
                error=f"SemanticUIBackend: unknown action '{action}'. "
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
                error=f"SemanticUIBackend.{action}: {exc}",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

    def is_available(self) -> bool:
        if _SYSTEM == "Linux":
            return _atspi_available() or bool(shutil.which("xdotool"))
        elif _SYSTEM == "Darwin":
            return bool(shutil.which("osascript"))
        elif _SYSTEM == "Windows":
            try:
                import pywinauto  # noqa: F401
                return True
            except ImportError:
                return False
        return False

    # ── shortcut ─────────────────────────────────────────────────────────────

    def _shortcut(self, p: dict, context: BackendContext) -> dict:
        keys: str = p.get("keys", "")
        if not keys:
            raise ValueError("shortcut requires 'keys' param.")

        if _SYSTEM == "Linux":
            _xdotool_key(keys)
            return {"keys": keys, "method": "xdotool"}

        elif _SYSTEM == "Darwin":
            # Use pynput (cross-platform) or AppleScript key code
            from cli_anything.macrocli.backends.visual_anchor import VisualAnchorBackend
            from cli_anything.macrocli.core.macro_model import MacroStep as MS
            va = VisualAnchorBackend()
            step = MS(id="x", backend="visual_anchor", action="hotkey", params={"keys": keys})
            result = va._hotkey({"keys": keys}, context)
            return result

        elif _SYSTEM == "Windows":
            import pywinauto.keyboard as kb
            # Convert ctrl+s → {VK_CONTROL}s
            kb.send_keys(keys.replace("+", ""))
            return {"keys": keys, "method": "pywinauto"}

        raise NotImplementedError(f"shortcut not implemented for {_SYSTEM}")

    # ── type_text ─────────────────────────────────────────────────────────────

    def _type_text(self, p: dict, context: BackendContext) -> dict:
        text: str = p.get("text", "")
        if not text:
            raise ValueError("type_text requires 'text' param.")

        if _SYSTEM == "Linux":
            _xdotool_type(text)
            return {"typed": len(text), "method": "xdotool"}

        # macOS / Windows: fall through to visual_anchor type_text
        from cli_anything.macrocli.backends.visual_anchor import VisualAnchorBackend
        va = VisualAnchorBackend()
        return va._type_text(p, context)

    # ── menu_click ────────────────────────────────────────────────────────────

    def _menu_click(self, p: dict, context: BackendContext) -> dict:
        menu_path: list = p.get("menu_path", [])
        app_name: str = p.get("app_name", "")

        if not menu_path:
            raise ValueError("menu_click requires 'menu_path' param (list of strings).")

        if _SYSTEM == "Linux":
            if _atspi_available():
                if not app_name:
                    raise ValueError(
                        "menu_click on Linux AT-SPI requires 'app_name' param."
                    )
                app = _atspi_find_app(app_name)
                if app is None:
                    raise RuntimeError(f"AT-SPI: application '{app_name}' not found.")
                _atspi_menu_path(app, menu_path)
                return {"menu_path": menu_path, "method": "at-spi"}
            else:
                raise RuntimeError(
                    "menu_click on Linux requires AT-SPI.\n"
                    "  apt install python3-pyatspi\n"
                    "  Or use visual_anchor backend instead."
                )

        elif _SYSTEM == "Darwin":
            if not app_name:
                raise ValueError("menu_click on macOS requires 'app_name' param.")
            _macos_menu_click(app_name, menu_path)
            return {"menu_path": menu_path, "method": "osascript"}

        elif _SYSTEM == "Windows":
            if not app_name:
                raise ValueError("menu_click on Windows requires 'app_name' param.")
            win = _win_find_app(app_name)
            # pywinauto menu navigation
            menu = win.menu()
            for item in menu_path:
                menu = menu.item_by_path(item)
            menu.click_input()
            return {"menu_path": menu_path, "method": "pywinauto"}

        raise NotImplementedError(f"menu_click not implemented for {_SYSTEM}")

    # ── button_click ──────────────────────────────────────────────────────────

    def _button_click(self, p: dict, context: BackendContext) -> dict:
        label: str = p.get("label", "")
        app_name: str = p.get("app_name", "")

        if not label:
            raise ValueError("button_click requires 'label' param.")

        if _SYSTEM == "Linux" and _atspi_available():
            if not app_name:
                raise ValueError("button_click on Linux AT-SPI requires 'app_name'.")
            app = _atspi_find_app(app_name)
            if app is None:
                raise RuntimeError(f"AT-SPI: application '{app_name}' not found.")
            btn = _atspi_find_control(app, "button", label)
            if btn is None:
                raise RuntimeError(f"AT-SPI: button '{label}' not found in '{app_name}'.")
            action = btn.queryAction()
            for i in range(action.nActions):
                if action.getName(i).lower() == "click":
                    action.doAction(i)
                    return {"clicked": label, "method": "at-spi"}
            raise RuntimeError(f"AT-SPI: no click action on button '{label}'.")

        elif _SYSTEM == "Darwin":
            script = f"""
            tell application "System Events"
                click button "{label}" of front window of (first process whose frontmost is true)
            end tell
            """
            _osascript(script)
            return {"clicked": label, "method": "osascript"}

        elif _SYSTEM == "Windows":
            win = _win_find_app(app_name or "")
            win.child_window(title=label, control_type="Button").click_input()
            return {"clicked": label, "method": "pywinauto"}

        raise NotImplementedError(
            f"button_click not fully implemented for {_SYSTEM} without AT-SPI.\n"
            "Use visual_anchor backend as fallback."
        )

    # ── wait_for_window ───────────────────────────────────────────────────────

    def _wait_for_window(self, p: dict, context: BackendContext) -> dict:
        title: str = p.get("title_contains", "")
        timeout_ms: int = int(p.get("timeout_ms", 5000))
        poll_ms: int = int(p.get("poll_ms", 300))

        if not title:
            raise ValueError("wait_for_window requires 'title_contains' param.")

        deadline = time.time() + timeout_ms / 1000.0

        if _SYSTEM == "Linux":
            while time.time() < deadline:
                if shutil.which("wmctrl"):
                    r = subprocess.run(
                        ["wmctrl", "-l"], capture_output=True, text=True, env=_x_env()
                    )
                    if title.lower() in r.stdout.lower():
                        return {"found": title, "method": "wmctrl"}
                elif shutil.which("xdotool"):
                    r = subprocess.run(
                        ["xdotool", "search", "--name", title],
                        capture_output=True, text=True, env=_x_env(),
                    )
                    if r.returncode == 0 and r.stdout.strip():
                        return {"found": title, "method": "xdotool"}
                time.sleep(poll_ms / 1000.0)

        elif _SYSTEM == "Darwin":
            while time.time() < deadline:
                script = f"""
                tell application "System Events"
                    set ws to name of every window of every process
                    set found to false
                    repeat with wlist in ws
                        repeat with wname in wlist
                            if "{title}" is in (wname as text) then
                                set found to true
                            end if
                        end repeat
                    end repeat
                    return found
                end tell
                """
                result = _osascript(script)
                if result.lower() == "true":
                    return {"found": title, "method": "osascript"}
                time.sleep(poll_ms / 1000.0)

        elif _SYSTEM == "Windows":
            import pywinauto.findwindows as fw
            while time.time() < deadline:
                try:
                    handles = fw.find_windows(title_re=f".*{title}.*")
                    if handles:
                        return {"found": title, "method": "pywinauto"}
                except Exception:
                    pass
                time.sleep(poll_ms / 1000.0)

        raise TimeoutError(
            f"wait_for_window: window containing '{title}' did not appear "
            f"within {timeout_ms}ms."
        )

    # ── focus_window ──────────────────────────────────────────────────────────

    def _focus_window(self, p: dict, context: BackendContext) -> dict:
        title: str = p.get("title_contains", "")
        if not title:
            raise ValueError("focus_window requires 'title_contains' param.")

        if _SYSTEM == "Linux":
            if shutil.which("wmctrl"):
                subprocess.run(["wmctrl", "-a", title], check=True, env=_x_env())
                return {"focused": title, "method": "wmctrl"}
            _xdotool_focus(title)
            return {"focused": title, "method": "xdotool"}

        elif _SYSTEM == "Darwin":
            _osascript(f'tell application "{title}" to activate')
            return {"focused": title, "method": "osascript"}

        elif _SYSTEM == "Windows":
            win = _win_find_app(title)
            win.set_focus()
            return {"focused": title, "method": "pywinauto"}

        raise NotImplementedError(f"focus_window not implemented for {_SYSTEM}")

    # ── get_controls ──────────────────────────────────────────────────────────

    def _get_controls(self, p: dict, context: BackendContext) -> dict:
        """List interactive controls in a window (for macro authoring / discovery)."""
        window_title: str = p.get("window_title", "")
        max_depth: int = int(p.get("max_depth", 5))

        if _SYSTEM == "Linux" and _atspi_available():
            import pyatspi
            app = _atspi_find_app(window_title) if window_title else None
            root = app or pyatspi.Registry.getDesktop(0)
            controls = []
            interactive_roles = {
                pyatspi.ROLE_PUSH_BUTTON,
                pyatspi.ROLE_MENU,
                pyatspi.ROLE_MENU_ITEM,
                pyatspi.ROLE_TEXT,
                pyatspi.ROLE_COMBO_BOX,
                pyatspi.ROLE_CHECK_BOX,
                pyatspi.ROLE_RADIO_BUTTON,
                pyatspi.ROLE_TOGGLE_BUTTON,
            }
            from collections import deque
            queue = deque([(root, 0)])
            while queue:
                node, depth = queue.popleft()
                if depth > max_depth:
                    continue
                try:
                    if node.getRole() in interactive_roles:
                        controls.append({
                            "role": node.getRoleName(),
                            "name": node.name,
                        })
                    for i in range(node.childCount):
                        child = node.getChildAtIndex(i)
                        if child:
                            queue.append((child, depth + 1))
                except Exception:
                    continue
            return {"controls": controls, "count": len(controls)}

        elif _SYSTEM == "Windows":
            win = _win_find_app(window_title)
            controls = []
            for ctrl in win.descendants():
                try:
                    controls.append({
                        "role": ctrl.element_info.control_type,
                        "name": ctrl.element_info.name,
                    })
                except Exception:
                    pass
            return {"controls": controls, "count": len(controls)}

        raise NotImplementedError(
            f"get_controls not implemented for {_SYSTEM} without AT-SPI / pywinauto."
        )
