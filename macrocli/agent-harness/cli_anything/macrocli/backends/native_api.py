"""NativeAPIBackend — executes macro steps via subprocess.

Supports these action types (configured in macro step params):

    action: run_command
    params:
      command: [inkscape, --export-filename, /tmp/out.png, input.svg]
      cwd: /optional/working/dir      # optional
      env: {KEY: value}               # optional extra env vars
      capture_stdout: true            # store stdout in output.stdout

    action: find_executable
    params:
      name: inkscape
      candidates: [inkscape, inkscape-1.0, /usr/bin/inkscape]
      install_hint: "apt install inkscape"
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import Any

from cli_anything.macrocli.backends.base import Backend, BackendContext, StepResult
from cli_anything.macrocli.core.macro_model import MacroStep, substitute


class NativeAPIBackend(Backend):
    """Execute a macro step by running an external command."""

    name = "native_api"
    priority = 100

    def execute(self, step: MacroStep, params: dict, context: BackendContext) -> StepResult:
        t0 = time.time()
        action = step.action

        if action == "find_executable":
            return self._find_executable(step, params, context, t0)
        elif action == "run_command":
            return self._run_command(step, params, context, t0)
        elif action == "start_process":
            return self._start_process(step, params, context, t0)
        else:
            return StepResult(
                success=False,
                error=f"NativeAPIBackend: unknown action '{action}'.",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

    # ── Actions ──────────────────────────────────────────────────────────

    def _find_executable(
        self, step: MacroStep, params: dict, context: BackendContext, t0: float
    ) -> StepResult:
        """Check that an executable exists; return its path."""
        step_params = substitute(step.params, params)
        exe_name = step_params.get("name", "")
        candidates: list[str] = step_params.get("candidates", [exe_name] if exe_name else [])
        install_hint: str = step_params.get("install_hint", f"Install {exe_name}")

        for candidate in candidates:
            found = shutil.which(candidate)
            if found:
                return StepResult(
                    success=True,
                    output={"executable": found, "name": candidate},
                    backend_used=self.name,
                    duration_ms=(time.time() - t0) * 1000,
                )

        return StepResult(
            success=False,
            error=(
                f"Executable not found: {exe_name}. "
                f"Tried: {candidates}. "
                f"Install with: {install_hint}"
            ),
            backend_used=self.name,
            duration_ms=(time.time() - t0) * 1000,
        )

    def _run_command(
        self, step: MacroStep, params: dict, context: BackendContext, t0: float
    ) -> StepResult:
        """Run an external command."""
        step_params = substitute(step.params, params)
        command: list[str] = step_params.get("command", [])
        if not command:
            return StepResult(
                success=False,
                error="NativeAPIBackend.run_command: 'command' param is required.",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        if isinstance(command, str):
            import shlex
            command = shlex.split(command)
        command = [str(c) for c in command]

        cwd: str = step_params.get("cwd", "")
        extra_env: dict = step_params.get("env", {})
        capture_stdout: bool = step_params.get("capture_stdout", False)

        env = os.environ.copy()
        if extra_env:
            env.update({k: str(v) for k, v in extra_env.items()})

        timeout_s = context.timeout_ms / 1000.0

        if context.dry_run:
            return StepResult(
                success=True,
                output={"dry_run": True, "command": command},
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                cwd=cwd or None,
                env=env,
            )
        except FileNotFoundError as exc:
            return StepResult(
                success=False,
                error=f"Command not found: {command[0]}. {exc}",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )
        except subprocess.TimeoutExpired:
            return StepResult(
                success=False,
                error=f"Command timed out after {timeout_s:.0f}s: {command}",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        duration = (time.time() - t0) * 1000
        if result.returncode != 0:
            return StepResult(
                success=False,
                error=(
                    f"Command failed (exit {result.returncode}): {command}\n"
                    f"stderr: {result.stderr.strip()}"
                ),
                output={"returncode": result.returncode, "stderr": result.stderr},
                backend_used=self.name,
                duration_ms=duration,
            )

        output: dict[str, Any] = {"returncode": 0}
        if capture_stdout:
            output["stdout"] = result.stdout
        return StepResult(
            success=True,
            output=output,
            backend_used=self.name,
            duration_ms=duration,
        )

    def _start_process(
        self, step: MacroStep, params: dict, context: BackendContext, t0: float
    ) -> StepResult:
        """Launch a GUI application in the background without waiting for it to exit.

        Use this instead of run_command for GUI apps like gedit, inkscape, etc.
        The process is detached immediately after launch.

        Params:
          command:    list[str] — the command to run
          cwd:        str       — working directory (optional)
          env:        dict      — extra environment variables (optional)
          log_file:   str       — redirect stdout+stderr here (default /dev/null)
        """
        import subprocess
        step_params = substitute(step.params, params)
        command: list[str] = step_params.get("command", [])
        if not command:
            return StepResult(
                success=False,
                error="NativeAPIBackend.start_process: 'command' param is required.",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        if isinstance(command, str):
            import shlex
            command = shlex.split(command)
        command = [str(c) for c in command]

        cwd: str = step_params.get("cwd", "")
        extra_env: dict = step_params.get("env", {})
        log_file: str = step_params.get("log_file", "/dev/null")

        env = os.environ.copy()
        if extra_env:
            env.update({k: str(v) for k, v in extra_env.items()})

        if context.dry_run:
            return StepResult(
                success=True,
                output={"dry_run": True, "command": command},
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        try:
            with open(log_file, "a") as log:
                proc = subprocess.Popen(
                    command,
                    stdout=log,
                    stderr=log,
                    cwd=cwd or None,
                    env=env,
                    start_new_session=True,   # detach from current process group
                )
            return StepResult(
                success=True,
                output={"pid": proc.pid, "command": command},
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )
        except FileNotFoundError as exc:
            return StepResult(
                success=False,
                error=f"Command not found: {command[0]}. {exc}",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )
        except Exception as exc:
            return StepResult(
                success=False,
                error=f"start_process failed: {exc}",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )
