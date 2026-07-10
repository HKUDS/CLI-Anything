"""RoutingEngine — select the best backend for each macro step.

Priority order (higher = preferred):
  native_api     100
  gui_macro       80
  visual_anchor   75
  file_transform  70
  gui_agent       60
  semantic_ui     50
  recovery        10  (only via explicit backend: recovery, or auto-retry)

The router respects the step's explicit `backend:` field.
It then checks availability; if the primary is unavailable it walks down
the priority list.
"""

from __future__ import annotations

from cli_anything.macrocli.backends.base import Backend, BackendContext, StepResult
from cli_anything.macrocli.backends.native_api import NativeAPIBackend
from cli_anything.macrocli.backends.file_transform import FileTransformBackend
from cli_anything.macrocli.backends.semantic_ui import SemanticUIBackend
from cli_anything.macrocli.backends.gui_macro import GUIMacroBackend
from cli_anything.macrocli.backends.visual_anchor import VisualAnchorBackend
from cli_anything.macrocli.backends.recovery import RecoveryBackend
from cli_anything.macrocli.backends.gui_agent import GUIAgentBackend
from cli_anything.macrocli.core.macro_model import MacroStep


_BACKEND_PRIORITY: dict[str, int] = {
    "native_api":     100,
    "gui_macro":       80,
    "visual_anchor":   75,
    "file_transform":  70,
    "gui_agent":       60,
    "semantic_ui":     50,
    "recovery":        10,
}


class RoutingEngine:
    """Selects and manages execution backends for macro steps."""

    def __init__(self):
        self._recovery = RecoveryBackend()
        self._backends: dict[str, Backend] = {
            "native_api":     NativeAPIBackend(),
            "file_transform": FileTransformBackend(),
            "semantic_ui":    SemanticUIBackend(),
            "gui_macro":      GUIMacroBackend(),
            "visual_anchor":  VisualAnchorBackend(),
            "gui_agent":      GUIAgentBackend(),
            "recovery":       self._recovery,
        }
        # Wire recovery with all other backends so it can delegate
        for b in self._backends.values():
            self._recovery.register_backend(b)

    def select(self, step: MacroStep) -> Backend:
        """Return the best available backend for the given step.

        Respects step.backend if set; falls back down the priority list
        if that backend is unavailable.

        Raises:
            RuntimeError: if no backend is available.
        """
        requested = step.backend
        # Try the requested backend first
        if requested in self._backends:
            b = self._backends[requested]
            if b.is_available():
                return b

        # Walk by priority (descending) for a fallback
        for name in sorted(_BACKEND_PRIORITY, key=lambda k: -_BACKEND_PRIORITY[k]):
            if name == "recovery":
                continue  # Never auto-fall-through to recovery
            b = self._backends.get(name)
            if b and b.is_available():
                return b

        raise RuntimeError(
            f"No backend available for step '{step.id}' "
            f"(requested: '{requested}'). "
            "Check that required tools are installed."
        )

    def execute_step(
        self,
        step: MacroStep,
        params: dict,
        context: BackendContext,
    ) -> StepResult:
        """Route and execute a step, applying retry logic if configured."""
        backend = self.select(step)

        if step.retry_max <= 0:
            return backend.execute(step, params, context)

        # Retry with backoff
        last_result: StepResult | None = None
        backoff = step.retry_backoff_ms or [1000]
        for attempt in range(step.retry_max + 1):
            last_result = backend.execute(step, params, context)
            if last_result.success:
                return last_result
            if attempt < step.retry_max:
                import time
                wait = backoff[min(attempt, len(backoff) - 1)] / 1000.0
                time.sleep(wait)

        assert last_result is not None
        return last_result

    def describe(self) -> dict:
        """Return a description of all registered backends and their status."""
        return {
            name: b.describe()
            for name, b in self._backends.items()
        }
