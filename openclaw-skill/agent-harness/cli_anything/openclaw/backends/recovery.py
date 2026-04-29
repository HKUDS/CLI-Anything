"""RecoveryBackend — retry and fallback orchestration.

This backend wraps another backend and retries failed steps with exponential
backoff. It can also fall back to an alternative backend on exhausted retries.

Example macro step using recovery explicitly:

    - backend: recovery
      action: retry_with_fallback
      params:
        primary_backend: native_api
        fallback_backend: file_transform
        max_retries: 3
        backoff_ms: [1000, 2000, 5000]
        step:
          action: run_command
          params:
            command: [inkscape, --export-filename, ${output}, input.svg]

The MacroRuntime also uses the RecoveryBackend automatically when a step
specifies retry_max > 0 in the macro definition.
"""

from __future__ import annotations

import time

from cli_anything.openclaw.backends.base import Backend, BackendContext, StepResult
from cli_anything.openclaw.core.macro_model import MacroStep, substitute


class RecoveryBackend(Backend):
    """Retry and fallback orchestration backend."""

    name = "recovery"
    priority = 10   # lowest — last resort

    def __init__(self, backends: dict[str, "Backend"] | None = None):
        """
        Args:
            backends: Dict of backend_name -> Backend instance.
                      Injected by the RoutingEngine at runtime.
        """
        self._backends = backends or {}

    def register_backend(self, backend: "Backend") -> None:
        self._backends[backend.name] = backend

    def execute(self, step: MacroStep, params: dict, context: BackendContext) -> StepResult:
        t0 = time.time()
        action = step.action

        if action not in ("retry", "retry_with_fallback"):
            return StepResult(
                success=False,
                error=f"RecoveryBackend: unknown action '{action}'. "
                      "Use 'retry' or 'retry_with_fallback'.",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        step_params = substitute(step.params, params)
        inner_step_raw = step_params.get("step", {})
        if not inner_step_raw:
            return StepResult(
                success=False,
                error="RecoveryBackend: 'step' param is required.",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        # Build an inner MacroStep from the nested definition
        inner_step = MacroStep(
            id=inner_step_raw.get("id", "recovery_inner"),
            backend=step_params.get("primary_backend", inner_step_raw.get("backend", "native_api")),
            action=inner_step_raw.get("action", ""),
            params=inner_step_raw.get("params", {}),
            timeout_ms=context.timeout_ms,
        )

        max_retries: int = int(step_params.get("max_retries", step.retry_max or 2))
        backoff_ms: list[int] = step_params.get("backoff_ms", [1000, 2000, 5000])
        fallback_name: str = step_params.get("fallback_backend", "")

        last_result = None
        for attempt in range(max_retries + 1):
            backend = self._backends.get(inner_step.backend)
            if backend is None:
                return StepResult(
                    success=False,
                    error=f"RecoveryBackend: backend '{inner_step.backend}' not registered.",
                    backend_used=self.name,
                    duration_ms=(time.time() - t0) * 1000,
                )

            last_result = backend.execute(inner_step, params, context)
            if last_result.success:
                last_result.backend_used = f"{self.name}({inner_step.backend}, attempt={attempt + 1})"
                return last_result

            # Failed — decide whether to retry or fall back
            if attempt < max_retries:
                wait = backoff_ms[min(attempt, len(backoff_ms) - 1)] / 1000.0
                time.sleep(wait)
            elif fallback_name and fallback_name in self._backends:
                # Switch to fallback backend for one final attempt
                inner_step = MacroStep(
                    id=inner_step.id,
                    backend=fallback_name,
                    action=inner_step.action,
                    params=inner_step.params,
                    timeout_ms=inner_step.timeout_ms,
                )
                fallback_result = self._backends[fallback_name].execute(inner_step, params, context)
                if fallback_result.success:
                    fallback_result.backend_used = f"{self.name}(fallback={fallback_name})"
                    return fallback_result
                last_result = fallback_result

        if last_result is None:
            last_result = StepResult(
                success=False,
                error="RecoveryBackend: no attempts made.",
                backend_used=self.name,
            )
        last_result.duration_ms = (time.time() - t0) * 1000
        last_result.backend_used = self.name
        return last_result
