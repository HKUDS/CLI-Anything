"""MacroRuntime — orchestrates the full macro execution lifecycle.

Lifecycle for execute(macro_name, params):

  1. Load macro definition from registry
  2. Resolve + validate parameters (fill defaults, type-check)
  3. Check preconditions
  4. For each step:
       a. substitute ${params} into step.params
       b. route to backend
       c. execute (with retry if configured)
       d. handle on_failure = fail | skip | continue
  5. Check postconditions
  6. Collect declared outputs
  7. Record telemetry in session
  8. Return ExecutionResult
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from cli_anything.openclaw.core.macro_model import (
    MacroCondition,
    MacroDefinition,
    MacroStep,
    substitute,
)
from cli_anything.openclaw.core.registry import MacroRegistry
from cli_anything.openclaw.core.routing import RoutingEngine
from cli_anything.openclaw.core.session import ExecutionSession, RunRecord
from cli_anything.openclaw.backends.base import BackendContext, StepResult


# ── Result types ─────────────────────────────────────────────────────────────

@dataclass
class ExecutionResult:
    success: bool
    macro_name: str
    output: dict = field(default_factory=dict)
    error: str = ""
    step_results: list[StepResult] = field(default_factory=list)
    telemetry: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "macro_name": self.macro_name,
            "output": self.output,
            "error": self.error,
            "telemetry": self.telemetry,
            "steps": [s.to_dict() for s in self.step_results],
        }


# ── Condition checker ────────────────────────────────────────────────────────

def _check_condition(cond: MacroCondition, resolved_params: dict) -> Optional[str]:
    """Evaluate one condition.

    Returns None if the condition passes, or an error string if it fails.
    """
    ctype = cond.type
    args = substitute(cond.args, resolved_params)

    if ctype == "file_exists":
        path = str(args)
        if not os.path.exists(path):
            return f"file_exists: '{path}' not found."
        return None

    elif ctype == "file_size_gt":
        if not isinstance(args, (list, tuple)) or len(args) < 2:
            return f"file_size_gt: expected [path, min_bytes], got {args!r}"
        path, min_bytes = str(args[0]), int(args[1])
        if not os.path.exists(path):
            return f"file_size_gt: '{path}' not found."
        size = os.path.getsize(path)
        if size <= min_bytes:
            return f"file_size_gt: '{path}' is {size} bytes, expected > {min_bytes}."
        return None

    elif ctype == "process_running":
        name = str(args)
        # Try pgrep first, then psutil
        import shutil
        import subprocess
        if shutil.which("pgrep"):
            r = subprocess.run(["pgrep", "-x", name], capture_output=True)
            if r.returncode == 0:
                return None
            return f"process_running: '{name}' not found (pgrep)."
        try:
            import psutil
            for proc in psutil.process_iter(["name"]):
                if proc.info["name"] == name:
                    return None
            return f"process_running: '{name}' not found."
        except ImportError:
            # Can't verify — let it pass with a warning
            return None

    elif ctype == "env_var":
        name = str(args)
        if name not in os.environ:
            return f"env_var: '{name}' is not set in the environment."
        return None

    elif ctype == "always":
        if str(args).lower() in ("false", "0", "no"):
            return "always: false condition."
        return None

    else:
        # Unknown condition type — warn but don't block
        return None


# ── Runtime ──────────────────────────────────────────────────────────────────

class MacroRuntime:
    """Executes macros end-to-end."""

    def __init__(
        self,
        registry: Optional[MacroRegistry] = None,
        routing_engine: Optional[RoutingEngine] = None,
        session: Optional[ExecutionSession] = None,
    ):
        self.registry = registry or MacroRegistry()
        self.routing = routing_engine or RoutingEngine()
        self.session = session or ExecutionSession()

    # ── Public API ───────────────────────────────────────────────────────

    def execute(
        self,
        macro_name: str,
        params: dict,
        dry_run: bool = False,
    ) -> ExecutionResult:
        """Execute a macro by name with the given parameters.

        Args:
            macro_name: Name of the macro to execute.
            params: Input parameters (raw, may be strings from CLI).
            dry_run: If True, skip all side effects and return simulated success.

        Returns:
            ExecutionResult with success status, outputs, and telemetry.
        """
        t0 = time.time()

        # 1. Load macro
        try:
            macro = self.registry.load(macro_name)
        except KeyError as exc:
            return ExecutionResult(
                success=False, macro_name=macro_name, error=str(exc)
            )

        # 2. Resolve + validate params
        resolved = macro.resolve_params(params)
        param_errors = macro.validate_params(resolved)
        if param_errors:
            return ExecutionResult(
                success=False,
                macro_name=macro_name,
                error="Parameter validation failed:\n" + "\n".join(f"  - {e}" for e in param_errors),
            )

        # 3. Check preconditions
        precond_errors = self.check_conditions(macro.preconditions, resolved)
        if precond_errors:
            return ExecutionResult(
                success=False,
                macro_name=macro_name,
                error="Preconditions not met:\n" + "\n".join(f"  - {e}" for e in precond_errors),
            )

        # 4. Execute steps
        step_results: list[StepResult] = []
        context = BackendContext(
            params=resolved,
            previous_results=step_results,
            dry_run=dry_run,
        )

        aborted = False
        abort_error = ""
        for step in macro.steps:
            context.timeout_ms = step.timeout_ms
            try:
                result = self.routing.execute_step(step, resolved, context)
            except Exception as exc:
                result = StepResult(
                    success=False,
                    error=f"Unhandled exception in step '{step.id}': {exc}",
                    backend_used=step.backend,
                )

            step_results.append(result)

            if not result.success:
                if step.on_failure == "fail":
                    aborted = True
                    abort_error = f"Step '{step.id}' failed: {result.error}"
                    break
                elif step.on_failure == "skip":
                    continue
                # on_failure == "continue" — keep going regardless

        # 5. Check postconditions (skip if already failed)
        postcond_errors: list[str] = []
        if not aborted:
            postcond_errors = self.check_conditions(macro.postconditions, resolved)

        success = not aborted and not postcond_errors

        # 6. Collect outputs
        output = self._collect_outputs(macro, resolved, step_results) if success else {}

        # 7. Build error string
        error = ""
        if aborted:
            error = abort_error
        elif postcond_errors:
            error = "Postconditions failed:\n" + "\n".join(f"  - {e}" for e in postcond_errors)

        # 8. Telemetry
        duration_ms = (time.time() - t0) * 1000
        backends_used = list({r.backend_used for r in step_results if r.backend_used})
        telemetry = {
            "duration_ms": duration_ms,
            "steps_total": len(macro.steps),
            "steps_run": len(step_results),
            "backends_used": backends_used,
            "dry_run": dry_run,
        }

        # 9. Record in session
        record = RunRecord(
            macro_name=macro_name,
            params=params,
            success=success,
            output=output,
            error=error,
            duration_ms=duration_ms,
            backends_used=backends_used,
            steps_run=len(step_results),
        )
        self.session.record(record)

        return ExecutionResult(
            success=success,
            macro_name=macro_name,
            output=output,
            error=error,
            step_results=step_results,
            telemetry=telemetry,
        )

    def check_conditions(
        self,
        conditions: list[MacroCondition],
        params: dict,
    ) -> list[str]:
        """Evaluate a list of conditions; return list of failure messages."""
        errors: list[str] = []
        for cond in conditions:
            err = _check_condition(cond, params)
            if err:
                errors.append(err)
        return errors

    def validate_macro(self, macro_name: str) -> list[str]:
        """Load and structurally validate a macro; return error list."""
        try:
            macro = self.registry.load(macro_name)
        except KeyError as exc:
            return [str(exc)]
        return macro.validate()

    # ── Helpers ──────────────────────────────────────────────────────────

    def _collect_outputs(
        self,
        macro: MacroDefinition,
        params: dict,
        step_results: list[StepResult],
    ) -> dict:
        """Resolve declared macro outputs into a concrete dict."""
        out: dict[str, Any] = {}
        for output_spec in macro.outputs:
            name = output_spec.name
            if output_spec.path:
                out[name] = substitute(output_spec.path, params)
            elif output_spec.value is not None:
                out[name] = substitute(output_spec.value, params)
        # Always include combined step outputs under 'steps'
        out["_steps"] = [r.output for r in step_results]
        return out
