"""SemanticUIBackend — drive applications via accessibility and keyboard shortcuts.

This backend provides stubs for AT-SPI (Linux), Windows UIA, and macOS
accessibility APIs. Full implementations require platform-specific libraries
(pyatspi2, pywinauto, pyobjc-framework-Accessibility).

Example macro step:

    - backend: semantic_ui
      action: menu_click
      params:
        menu_path: [File, Export As, PNG]

    - backend: semantic_ui
      action: shortcut
      params:
        keys: ctrl+shift+e

    - backend: semantic_ui
      action: wait_for_window
      params:
        title_contains: Export
        timeout_ms: 5000
"""

from __future__ import annotations

import platform
import time

from cli_anything.openclaw.backends.base import Backend, BackendContext, StepResult
from cli_anything.openclaw.core.macro_model import MacroStep, substitute


class SemanticUIBackend(Backend):
    """Drive applications through semantic (accessibility) controls."""

    name = "semantic_ui"
    priority = 50

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

        dispatch = {
            "shortcut": self._shortcut,
            "menu_click": self._menu_click,
            "wait_for_window": self._wait_for_window,
            "button_click": self._button_click,
            "type_text": self._type_text,
        }

        handler = dispatch.get(action)
        if handler is None:
            return StepResult(
                success=False,
                error=f"SemanticUIBackend: unknown action '{action}'.",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        try:
            output = handler(step_params)
            return StepResult(
                success=True,
                output=output or {},
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )
        except NotImplementedError as exc:
            return StepResult(
                success=False,
                error=str(exc),
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
        # Available when at least one accessibility library can be found
        if platform.system() == "Linux":
            try:
                import pyatspi  # noqa: F401
                return True
            except ImportError:
                pass
        elif platform.system() == "Windows":
            try:
                import pywinauto  # noqa: F401
                return True
            except ImportError:
                pass
        elif platform.system() == "Darwin":
            try:
                import ApplicationServices  # noqa: F401
                return True
            except ImportError:
                pass
        return False

    # ── Actions ──────────────────────────────────────────────────────────

    def _shortcut(self, p: dict) -> dict:
        """Send a keyboard shortcut to the focused window."""
        keys: str = p.get("keys", "")
        if not keys:
            raise ValueError("shortcut action requires 'keys' param.")

        sys = platform.system()
        if sys == "Linux":
            return self._shortcut_xdotool(keys)
        elif sys == "Windows":
            return self._shortcut_win32(keys)
        elif sys == "Darwin":
            return self._shortcut_macos(keys)
        raise NotImplementedError(
            f"SemanticUIBackend.shortcut: not yet implemented for platform {sys}. "
            "Consider using native_api backend instead."
        )

    def _shortcut_xdotool(self, keys: str) -> dict:
        """Use xdotool to send keys on Linux."""
        import shutil
        if not shutil.which("xdotool"):
            raise NotImplementedError(
                "xdotool not found. Install with: apt install xdotool"
            )
        import subprocess
        # Convert from ctrl+shift+e → ctrl+shift+e (xdotool format)
        xdg_keys = keys.replace("+", " ")
        subprocess.run(["xdotool", "key", xdg_keys], check=True)
        return {"keys": keys, "method": "xdotool"}

    def _shortcut_win32(self, keys: str) -> dict:
        raise NotImplementedError(
            "SemanticUIBackend.shortcut: Windows requires pywinauto. "
            "pip install pywinauto"
        )

    def _shortcut_macos(self, keys: str) -> dict:
        raise NotImplementedError(
            "SemanticUIBackend.shortcut: macOS requires pyobjc. "
            "pip install pyobjc-framework-Quartz"
        )

    def _menu_click(self, p: dict) -> dict:
        """Click a menu item by path."""
        menu_path: list = p.get("menu_path", [])
        raise NotImplementedError(
            f"SemanticUIBackend.menu_click: not yet implemented. "
            f"Menu path: {menu_path}. "
            "Use native_api or file_transform backends instead when possible."
        )

    def _wait_for_window(self, p: dict) -> dict:
        """Wait for a window matching title criteria."""
        title_contains: str = p.get("title_contains", "")
        timeout_ms: int = int(p.get("timeout_ms", 5000))
        raise NotImplementedError(
            f"SemanticUIBackend.wait_for_window: not yet implemented. "
            f"Looking for: '{title_contains}'. "
            "Consider using postconditions (file_exists) to detect completion."
        )

    def _button_click(self, p: dict) -> dict:
        """Click a UI button by label."""
        raise NotImplementedError(
            f"SemanticUIBackend.button_click: not yet implemented. "
            "Use native_api or file_transform backends instead when possible."
        )

    def _type_text(self, p: dict) -> dict:
        """Type text into the focused input field."""
        text: str = p.get("text", "")
        if not text:
            raise ValueError("type_text action requires 'text' param.")
        sys = platform.system()
        if sys == "Linux":
            import shutil
            if not shutil.which("xdotool"):
                raise NotImplementedError("xdotool not found. apt install xdotool")
            import subprocess
            subprocess.run(["xdotool", "type", "--clearmodifiers", text], check=True)
            return {"text": text, "method": "xdotool"}
        raise NotImplementedError(
            f"SemanticUIBackend.type_text: not yet implemented for {sys}."
        )
