"""Minimal Debug Adapter Protocol server backed by LLDBSession."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shlex
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Callable

from cli_anything.lldb.core.session import LLDBSession


class DAPProtocolError(RuntimeError):
    """Raised when a DAP frame cannot be parsed."""


def encode_message(payload: dict[str, Any]) -> bytes:
    body = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    return header + body


def read_message(stream: BinaryIO) -> dict[str, Any] | None:
    content_length: int | None = None
    saw_header = False

    while True:
        line = stream.readline()
        if line == b"":
            return None if not saw_header else _raise_protocol_error("Unexpected EOF in DAP header")
        saw_header = True
        stripped = line.strip()
        if not stripped:
            break
        name, sep, value = stripped.partition(b":")
        if not sep:
            raise DAPProtocolError(f"Malformed DAP header: {stripped!r}")
        if name.lower() == b"content-length":
            try:
                content_length = int(value.strip())
            except ValueError as exc:
                raise DAPProtocolError(f"Invalid Content-Length: {value!r}") from exc

    if content_length is None:
        raise DAPProtocolError("Missing Content-Length header")

    body = stream.read(content_length)
    if len(body) != content_length:
        raise DAPProtocolError("Unexpected EOF in DAP body")
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise DAPProtocolError(f"Invalid DAP JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise DAPProtocolError("DAP payload must be a JSON object")
    return payload


def _raise_protocol_error(message: str):
    raise DAPProtocolError(message)


@dataclass(frozen=True)
class StopRule:
    """Structured rule used to classify or auto-continue debugger stops."""

    name: str
    action: str = "stop"
    origin: str = "internalTrap"
    reason: str | None = None
    module: str | None = None
    function: str | None = None
    regex: str | None = None
    source: str | None = None

    @classmethod
    def from_mapping(cls, raw: dict[str, Any], *, source: str) -> "StopRule":
        if not isinstance(raw, dict):
            raise RuntimeError("stopRules entries must be objects")
        name = str(raw.get("name") or raw.get("id") or "unnamed-stop-rule")
        action = str(raw.get("action") or "stop")
        if action not in {"stop", "continue"}:
            raise RuntimeError(f"Unsupported stop rule action for {name}: {action}")
        regex = raw.get("regex")
        if regex is not None:
            try:
                re.compile(str(regex))
            except re.error as exc:
                raise RuntimeError(f"Invalid stop rule regex for {name}: {exc}") from exc
        if not any(raw.get(key) is not None for key in ("reason", "module", "function", "regex")):
            raise RuntimeError(f"Stop rule {name} must include reason, module, function, or regex")
        return cls(
            name=name,
            action=action,
            origin=str(raw.get("origin") or "internalTrap"),
            reason=str(raw["reason"]) if raw.get("reason") is not None else None,
            module=str(raw["module"]) if raw.get("module") is not None else None,
            function=str(raw["function"]) if raw.get("function") is not None else None,
            regex=str(regex) if regex is not None else None,
            source=source,
        )

    def matches(self, stop_context: dict[str, Any]) -> bool:
        if self.reason and not _stop_field_matches(self.reason, [stop_context.get("reason"), stop_context.get("lldbReason")]):
            return False
        if self.module and not _stop_field_matches(
            self.module,
            [stop_context.get("module"), stop_context.get("modulePath")],
            allow_basename=True,
        ):
            return False
        if self.function and not _stop_field_matches(
            self.function,
            [stop_context.get("function")],
            allow_symbol_suffix=True,
        ):
            return False
        if self.regex and not re.search(self.regex, _stop_context_text(stop_context), re.IGNORECASE):
            return False
        return True

    def to_dap(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "action": self.action,
            "origin": self.origin,
            "source": self.source,
        }


def _stop_field_matches(
    expected: str,
    values: list[Any],
    *,
    allow_basename: bool = False,
    allow_symbol_suffix: bool = False,
) -> bool:
    expected_norm = expected.casefold()
    for value in values:
        if value is None:
            continue
        text = str(value)
        candidates = [text.casefold()]
        if allow_basename:
            candidates.append(Path(text).name.casefold())
        for candidate in candidates:
            if candidate == expected_norm:
                return True
            if allow_symbol_suffix and (
                candidate.endswith(f"::{expected_norm}") or candidate.endswith(f"`{expected_norm}")
            ):
                return True
    return False


def _stop_context_text(stop_context: dict[str, Any]) -> str:
    fields = [
        stop_context.get("reason"),
        stop_context.get("lldbReason"),
        stop_context.get("description"),
        stop_context.get("module"),
        stop_context.get("modulePath"),
        stop_context.get("function"),
    ]
    frame = stop_context.get("frame")
    if isinstance(frame, dict):
        fields.extend(frame.get(key) for key in ("module", "module_path", "function", "file", "address"))
    return "\n".join(str(field) for field in fields if field)


class LLDBDebugAdapter:
    """Single-session stdio DAP adapter for LLDB."""

    def __init__(
        self,
        session_factory: Callable[[], LLDBSession] = LLDBSession,
        log_file: str | None = None,
        profile_file: str | None = None,
    ):
        self._session_factory = session_factory
        self._session: LLDBSession | None = None
        self._out: BinaryIO | None = None
        self._seq = 1
        self._pending_launch: dict[str, Any] | None = None
        self._pending_attach: dict[str, Any] | None = None
        self._source_breakpoints: dict[str, list[int]] = {}
        self._function_breakpoints: list[int] = []
        self._frame_refs: dict[int, tuple[int, int]] = {}
        self._variable_refs: dict[int, dict[str, Any]] = {}
        self._next_ref = 1
        self._log_file = Path(log_file).expanduser() if log_file else None
        self._protocol_lock = threading.Lock()
        self._lldb_api_lock = threading.RLock()
        self._continue_state = threading.Condition()
        self._continue_active = False
        self._auto_continue_internal_breakpoints = False
        self._base_auto_continue_internal_breakpoints = False
        self._base_stop_rules: list[StopRule] = []
        self._active_stop_rules: list[StopRule] = []
        self._pause_requested = False
        self._mutation_stop_timeout = 10.0
        if profile_file:
            self._base_stop_rules, self._base_auto_continue_internal_breakpoints = self._load_stop_profile_file(
                profile_file
            )
            self._active_stop_rules = list(self._base_stop_rules)

    def run(self, instream: BinaryIO | None = None, outstream: BinaryIO | None = None) -> int:
        instream = instream or sys.stdin.buffer
        outstream = outstream or sys.stdout.buffer
        self._out = outstream
        try:
            while True:
                try:
                    message = read_message(instream)
                except DAPProtocolError as exc:
                    self._log(f"DAP protocol error: {exc}")
                    return 1
                if message is None:
                    return 0
                self.handle_message(message)
        finally:
            self._cleanup_session()

    def handle_message(self, message: dict[str, Any]):
        if message.get("type") != "request":
            return

        request_seq = int(message.get("seq", 0))
        command = str(message.get("command") or "")
        args = message.get("arguments") or {}
        handler = getattr(self, f"_handle_{command}", None)
        if handler is None:
            self._send_response(request_seq, command, success=False, message=f"Unsupported request: {command}")
            return

        try:
            body, post_send = handler(args)
        except Exception as exc:
            self._log(f"{command} failed: {exc}")
            self._send_response(request_seq, command, success=False, message=str(exc))
            return

        self._send_response(request_seq, command, body=body)
        if post_send:
            try:
                post_send()
            except Exception as exc:
                self._log(f"{command} post-response failed: {exc}")
                self._send_event(
                    "output",
                    {"category": "stderr", "output": f"{command} failed after response: {exc}\n"},
                )
                self._send_event("terminated")

    def _handle_initialize(self, _args: dict[str, Any]):
        capabilities = {
            "supportsConfigurationDoneRequest": True,
            "supportsFunctionBreakpoints": True,
            "supportsEvaluateForHovers": True,
            "supportsDisassembleRequest": True,
            "supportsLoadedSourcesRequest": True,
            "supportsReadMemoryRequest": True,
            "supportsSetVariable": True,
            "supportsModulesRequest": True,
            "supportsExceptionInfoRequest": True,
            "supportsSteppingGranularity": False,
            "supportTerminateDebuggee": True,
        }
        return capabilities, lambda: self._send_event("initialized")

    def _handle_launch(self, args: dict[str, Any]):
        program = args.get("program") or args.get("executable")
        if not program:
            raise RuntimeError("launch requires 'program'")
        self._ensure_session().target_create(str(program), arch=args.get("arch"))
        self._pending_launch = {
            "args": self._coerce_args(args.get("args")),
            "env": self._coerce_env(args.get("env")),
            "working_dir": args.get("cwd") or args.get("workingDirectory"),
            "stop_at_entry": bool(args.get("stopOnEntry", False)),
            "suppress_stdio": True,
        }
        self._configure_stop_rules(args)
        self._pending_attach = None
        return {}, None

    def _handle_attach(self, args: dict[str, Any]):
        program = args.get("program") or args.get("executable")
        if not program:
            raise RuntimeError("attach requires 'program' or 'executable' so LLDB can create a target")
        self._ensure_session().target_create(str(program), arch=args.get("arch"))
        pid = args.get("pid", args.get("processId"))
        name = args.get("name", args.get("processName"))
        if pid is None and not name:
            raise RuntimeError("attach requires pid/processId or name/processName")
        self._pending_attach = {
            "pid": int(pid) if pid is not None else None,
            "name": str(name) if name else None,
            "wait_for": bool(args.get("waitFor", False)),
        }
        self._configure_stop_rules(args)
        self._pending_launch = None
        return {}, None

    def _handle_configurationDone(self, _args: dict[str, Any]):
        def post_send():
            default_reason = None
            if self._pending_launch is not None:
                launch_args = self._pending_launch
                self._pending_launch = None
                self._ensure_session().launch(**launch_args)
                self._emit_breakpoint_updates()
                default_reason = "entry" if launch_args.get("stop_at_entry") else "breakpoint"
            elif self._pending_attach is not None:
                attach_args = self._pending_attach
                self._pending_attach = None
                if attach_args["pid"] is not None:
                    self._ensure_session().attach_pid(attach_args["pid"])
                else:
                    self._ensure_session().attach_name(attach_args["name"], wait_for=attach_args["wait_for"])
                default_reason = "pause"
            self._emit_execution_event(default_reason=default_reason)

        return {}, post_send

    def _handle_disconnect(self, args: dict[str, Any]):
        terminate_debuggee = bool(args.get("terminateDebuggee", True))

        def post_send():
            if self._session is not None:
                if not terminate_debuggee and self._session.session_status().get("process_origin") == "launched":
                    try:
                        self._session.detach()
                    except Exception:
                        pass
                self._session.destroy()
                self._session = None
            self._send_event("terminated")

        return {}, post_send

    def _handle_setBreakpoints(self, args: dict[str, Any]):
        source = args.get("source") or {}
        path = source.get("path")
        if not path:
            raise RuntimeError("setBreakpoints requires source.path")

        self._ensure_stopped_for_target_mutation("setBreakpoints")
        session = self._ensure_session()
        source_key = str(Path(path))
        with self._lldb_api_lock:
            for bp_id in self._source_breakpoints.get(source_key, []):
                try:
                    session.breakpoint_delete(bp_id)
                except Exception:
                    pass

            dap_breakpoints = []
            created_ids = []
            for item in args.get("breakpoints") or []:
                line = int(item.get("line"))
                payload = session.breakpoint_set(
                    file=source_key,
                    line=line,
                    condition=item.get("condition"),
                    allow_pending=True,
                )
                created_ids.append(payload["id"])
                dap_breakpoints.append(self._to_dap_breakpoint(payload, source_key, requested_line=line))

        self._source_breakpoints[source_key] = created_ids
        return {"breakpoints": dap_breakpoints}, None

    def _handle_setFunctionBreakpoints(self, args: dict[str, Any]):
        self._ensure_stopped_for_target_mutation("setFunctionBreakpoints")
        session = self._ensure_session()
        with self._lldb_api_lock:
            for bp_id in self._function_breakpoints:
                try:
                    session.breakpoint_delete(bp_id)
                except Exception:
                    pass

            self._function_breakpoints = []
            result = []
            for item in args.get("breakpoints") or []:
                name = item.get("name")
                if not name:
                    continue
                payload = session.breakpoint_set(
                    function=str(name),
                    condition=item.get("condition"),
                    allow_pending=True,
                )
                self._function_breakpoints.append(payload["id"])
                result.append(self._to_dap_breakpoint(payload))
        return {"breakpoints": result}, None

    def _handle_threads(self, _args: dict[str, Any]):
        threads = []
        for item in self._ensure_session().threads().get("threads", []):
            name = item.get("name") or f"Thread {item.get('id')}"
            threads.append({"id": item["id"], "name": name})
        return {"threads": threads}, None

    def _handle_stackTrace(self, args: dict[str, Any]):
        thread_id = int(args.get("threadId"))
        start = int(args.get("startFrame", 0))
        levels = int(args.get("levels", 50) or 50)
        session = self._ensure_session()
        session.thread_select(thread_id)
        backtrace = session.backtrace(limit=start + levels)
        frames = []
        for frame in backtrace.get("frames", [])[start : start + levels]:
            frame_id = self._alloc_frame_ref(thread_id, int(frame["index"]))
            source = self._source_from_path(frame.get("file"))
            frames.append(
                {
                    "id": frame_id,
                    "name": frame.get("function") or "<unknown>",
                    "source": source,
                    "line": frame.get("line") or 0,
                    "column": 0,
                    "instructionPointerReference": frame.get("address"),
                }
            )
        return {"stackFrames": frames, "totalFrames": backtrace.get("total_frames", len(frames))}, None

    def _handle_scopes(self, args: dict[str, Any]):
        frame_id = int(args.get("frameId"))
        if frame_id not in self._frame_refs:
            raise RuntimeError(f"Unknown frameId: {frame_id}")
        ref = self._alloc_variable_ref({"kind": "locals", "frame_ref": frame_id})
        return {"scopes": [{"name": "Locals", "variablesReference": ref, "expensive": False}]}, None

    def _handle_variables(self, args: dict[str, Any]):
        ref = int(args.get("variablesReference"))
        entry = self._variable_refs.get(ref)
        if not entry:
            return {"variables": []}, None
        if entry["kind"] != "locals":
            if entry["kind"] == "children":
                return {"variables": self._dap_variables_from_values(self._child_values(entry["value"]))}, None
            return {"variables": []}, None

        thread_id, frame_index = self._frame_refs[entry["frame_ref"]]
        session = self._ensure_session()
        session.thread_select(thread_id)
        session.frame_select(frame_index)
        return {"variables": self._dap_variables_from_values(session.local_values())}, None

    def _handle_setVariable(self, args: dict[str, Any]):
        ref = int(args.get("variablesReference"))
        name = str(args.get("name") or "")
        value = str(args.get("value") or "")
        entry = self._variable_refs.get(ref)
        if not entry:
            raise RuntimeError(f"Unknown variablesReference: {ref}")

        if entry["kind"] == "locals":
            thread_id, frame_index = self._frame_refs[entry["frame_ref"]]
            updated = self._ensure_session().set_local_variable(thread_id, frame_index, name, value)
        elif entry["kind"] == "children":
            updated = self._ensure_session().set_child_value(entry["value"], name, value)
        else:
            raise RuntimeError(f"Cannot set variable for reference kind: {entry['kind']}")

        return self._dap_variable_from_value(updated), None

    def _handle_evaluate(self, args: dict[str, Any]):
        expression = args.get("expression")
        if not expression:
            raise RuntimeError("evaluate requires expression")
        frame_id = args.get("frameId")
        if frame_id is not None and int(frame_id) in self._frame_refs:
            thread_id, frame_index = self._frame_refs[int(frame_id)]
            self._ensure_session().thread_select(thread_id)
            self._ensure_session().frame_select(frame_index)
        payload = self._ensure_session().evaluate(str(expression))
        if payload.get("error"):
            raise RuntimeError(payload["error"])
        result = payload.get("value") or payload.get("summary") or ""
        return {"result": result, "type": payload.get("type"), "variablesReference": 0}, None

    def _handle_continue(self, _args: dict[str, Any]):
        def post_send():
            self._reset_refs_for_resume()
            self._send_continued_event()
            self._start_continue_thread(
                name="cli-anything-lldb-dap-continue",
                default_reason="breakpoint",
            )

        return {"allThreadsContinued": True}, post_send

    def _handle_pause(self, _args: dict[str, Any]):
        def post_send():
            self._pause_requested = True
            self._request_async_interrupt()
            if not self._is_continue_active():
                with self._lldb_api_lock:
                    self._emit_execution_event(default_reason="pause")

        return {}, post_send

    def _handle_next(self, _args: dict[str, Any]):
        return {}, self._step_post_send(self._ensure_session().step_over)

    def _handle_stepIn(self, _args: dict[str, Any]):
        return {}, self._step_post_send(self._ensure_session().step_into)

    def _handle_stepOut(self, _args: dict[str, Any]):
        return {}, self._step_post_send(self._ensure_session().step_out)

    def _handle_source(self, args: dict[str, Any]):
        source = args.get("source") or {}
        path = source.get("path")
        if not path:
            raise RuntimeError("source request requires source.path")
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        return {"content": text, "mimeType": "text/plain"}, None

    def _handle_loadedSources(self, _args: dict[str, Any]):
        sources = self._ensure_session().loaded_sources().get("sources", [])
        return {"sources": [self._source_from_path(item.get("path")) for item in sources if item.get("path")]}, None

    def _handle_modules(self, _args: dict[str, Any]):
        modules = []
        for item in self._ensure_session().modules().get("modules", []):
            modules.append(
                {
                    "id": item["id"],
                    "name": item.get("name") or "<unknown>",
                    "path": item.get("path"),
                    "isOptimized": False,
                    "isUserCode": True,
                    "symbolStatus": item.get("symbol_status"),
                    "addressRange": item.get("address"),
                    "version": item.get("version"),
                }
            )
        return {"modules": modules}, None

    def _handle_exceptionInfo(self, _args: dict[str, Any]):
        info = self._ensure_session().process_info()
        stop = info.get("stop") or {}
        reason = stop.get("reason") or "unknown"
        description = stop.get("description") or reason
        return {
            "exceptionId": reason,
            "breakMode": "always",
            "description": description,
            "details": {"message": description},
        }, None

    def _handle_readMemory(self, args: dict[str, Any]):
        address = self._parse_address(str(args.get("memoryReference") or "0"))
        address += int(args.get("offset", 0) or 0)
        count = int(args.get("count", 0) or 0)
        if count <= 0:
            raise RuntimeError("readMemory requires a positive count")
        payload = self._ensure_session().read_memory(address, count)
        data = bytes.fromhex(payload["hex"])
        return {
            "address": hex(address),
            "data": base64.b64encode(data).decode("ascii"),
        }, None

    def _handle_disassemble(self, args: dict[str, Any]):
        address = self._parse_address(str(args.get("memoryReference") or "0"))
        address += int(args.get("instructionOffset", 0) or 0)
        count = int(args.get("instructionCount", 8) or 8)
        payload = self._ensure_session().disassemble(address, count=count)
        instructions = [
            {"address": item["address"], "instruction": item["instruction"]}
            for item in payload.get("instructions", [])
        ]
        return {"instructions": instructions}, None

    def _step_post_send(self, step_fn: Callable[[], dict[str, Any]]):
        def post_send():
            self._reset_refs_for_resume()
            self._send_continued_event()
            with self._lldb_api_lock:
                step_fn()
                self._emit_execution_event(default_reason="step")

        return post_send

    def _start_continue_thread(self, *, name: str, default_reason: str):
        with self._continue_state:
            if self._continue_active:
                self._log("continue requested while a continue operation is already active")
                return
            self._continue_active = True
        threading.Thread(
            target=self._continue_until_stop,
            kwargs={"default_reason": default_reason},
            name=name,
            daemon=True,
        ).start()

    def _continue_until_stop(self, *, default_reason: str):
        try:
            self._ensure_session().continue_exec()
        except Exception as exc:
            self._log(f"continue failed: {exc}")
            self._send_event("output", {"category": "stderr", "output": f"continue failed: {exc}\n"})
            self._send_event("terminated")
            return
        finally:
            self._mark_continue_inactive()

        with self._lldb_api_lock:
            self._emit_breakpoint_updates()
            self._emit_execution_event(default_reason=default_reason)

    def _mark_continue_inactive(self):
        with self._continue_state:
            self._continue_active = False
            self._continue_state.notify_all()

    def _is_continue_active(self) -> bool:
        with self._continue_state:
            return self._continue_active

    def _ensure_stopped_for_target_mutation(self, operation: str):
        if not self._is_continue_active():
            return
        self._log(f"{operation}: interrupting running debuggee before target mutation")
        self._request_async_interrupt()
        with self._continue_state:
            stopped = self._continue_state.wait_for(
                lambda: not self._continue_active,
                timeout=self._mutation_stop_timeout,
            )
        if not stopped:
            raise RuntimeError(
                f"Timed out waiting for debuggee to stop before {operation}. "
                "Send a pause request and retry after the stopped event."
            )

    def _request_async_interrupt(self):
        session = self._ensure_session()
        interrupt = getattr(session, "interrupt_async", None)
        if interrupt is not None:
            return interrupt()
        return session.interrupt()

    def _configure_stop_rules(self, args: dict[str, Any]):
        rules = list(self._base_stop_rules)
        auto_continue = self._base_auto_continue_internal_breakpoints or bool(
            args.get("autoContinueInternalBreakpoints", False)
        )
        profile_path = args.get("stopRuleProfile") or args.get("stopProfile") or args.get("profile")
        if profile_path:
            profile_rules, profile_auto_continue = self._load_stop_profile_file(str(profile_path))
            rules.extend(profile_rules)
            auto_continue = auto_continue or profile_auto_continue
        inline_rules = args.get("stopRules")
        if inline_rules:
            rules.extend(self._coerce_stop_rules(inline_rules, source="dap-arguments"))
        if auto_continue:
            rules.extend(self._builtin_internal_stop_rules())
        self._auto_continue_internal_breakpoints = auto_continue
        self._active_stop_rules = rules

    def _load_stop_profile_file(self, profile_file: str) -> tuple[list[StopRule], bool]:
        profile_path = Path(profile_file).expanduser().resolve()
        try:
            payload = json.loads(profile_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise RuntimeError(f"Failed to read stop rule profile {profile_path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid stop rule profile JSON {profile_path}: {exc}") from exc

        auto_continue = False
        if isinstance(payload, list):
            rules_payload = payload
        elif isinstance(payload, dict):
            auto_continue = bool(payload.get("autoContinueInternalBreakpoints", False))
            rules_payload = payload.get("stopRules", [])
        else:
            raise RuntimeError("Stop rule profile must be a JSON object or array")
        return self._coerce_stop_rules(rules_payload, source=str(profile_path)), auto_continue

    def _coerce_stop_rules(self, raw_rules: Any, *, source: str) -> list[StopRule]:
        if not isinstance(raw_rules, list):
            raise RuntimeError("stopRules must be a list")
        return [StopRule.from_mapping(raw_rule, source=source) for raw_rule in raw_rules]

    def _builtin_internal_stop_rules(self) -> list[StopRule]:
        return [
            StopRule(
                name="nvidia-shader-jit-debug-register",
                action="continue",
                origin="internalTrap",
                reason="breakpoint",
                regex=r"(__jit_debug_register_code|jit-debug-register)",
                source="builtin:autoContinueInternalBreakpoints",
            ),
            StopRule(
                name="windows-debugger-startup-breakpoint",
                action="continue",
                origin="internalTrap",
                regex=r"(Exception 0x80000003|ntdll\.dll`DbgBreakPoint|DbgBreakPoint)",
                source="builtin:autoContinueInternalBreakpoints",
            ),
        ]

    def _emit_execution_event(self, default_reason: str | None = None):
        info = self._ensure_session().process_info()
        state = info.get("state")
        if state in {"running", "launching", "stepping"}:
            self._send_continued_event(info.get("selected_thread_id"))
            return
        if state == "exited":
            self._send_event("exited", {"exitCode": info.get("exit_status", 0) or 0})
            self._send_event("terminated")
            return
        if state == "detached":
            self._send_event("terminated")
            return

        stop = info.get("stop") or {}
        lldb_reason = stop.get("reason")
        reason = "entry" if default_reason == "entry" else (lldb_reason or default_reason or "pause")
        if reason in {"signal", "crashed"}:
            reason = "exception"
        stop_origin = "debuggee"
        if self._pause_requested:
            self._pause_requested = False
            reason = "pause"
            stop_origin = "manualPause"

        frame = stop.get("frame") if isinstance(stop.get("frame"), dict) else {}
        stop_context = {
            "reason": reason,
            "lldbReason": lldb_reason,
            "description": stop.get("description"),
            "module": stop.get("module") or frame.get("module"),
            "modulePath": frame.get("module_path"),
            "function": stop.get("function") or frame.get("function"),
            "frame": frame,
        }
        matched_rule = None if stop_origin == "manualPause" else self._match_stop_rule(stop_context)
        if matched_rule is not None:
            stop_origin = matched_rule.origin

        body = {
            "reason": reason,
            "threadId": info.get("selected_thread_id"),
            "allThreadsStopped": True,
            "cliAnythingStop": {
                "origin": stop_origin,
                "lldbReason": lldb_reason,
                "module": stop_context["module"],
                "modulePath": stop_context["modulePath"],
                "function": stop_context["function"],
                "description": stop_context["description"],
            },
        }
        if frame:
            body["cliAnythingStop"]["frame"] = frame
        if matched_rule is not None:
            body["cliAnythingStop"]["matchedRule"] = matched_rule.to_dap()
        hit_ids = stop.get("hit_breakpoint_ids") or []
        if hit_ids:
            body["hitBreakpointIds"] = hit_ids
        if stop.get("description"):
            body["description"] = stop["description"]
            body["text"] = stop["description"]
        if matched_rule is not None and matched_rule.action == "continue":
            self._send_event(
                "output",
                {
                    "category": "console",
                    "output": (
                        f"auto-continued stop rule {matched_rule.name}: "
                        f"{self._summarize_stop(body)}\n"
                    ),
                },
            )
            self._send_continued_event(info.get("selected_thread_id"))
            self._start_continue_thread(
                name="cli-anything-lldb-dap-auto-continue",
                default_reason=default_reason or "breakpoint",
            )
            return
        self._send_event("stopped", body)

    def _match_stop_rule(self, stop_context: dict[str, Any]) -> StopRule | None:
        for rule in self._active_stop_rules:
            if rule.matches(stop_context):
                return rule
        return None

    def _summarize_stop(self, body: dict[str, Any]) -> str:
        text = str(body.get("description") or body.get("text") or body.get("reason") or "unknown")
        return text.splitlines()[0] if text else "unknown"

    def _send_continued_event(self, thread_id: int | None = None):
        body: dict[str, Any] = {"allThreadsContinued": True}
        if thread_id is not None:
            body["threadId"] = thread_id
        self._send_event("continued", body)

    def _cleanup_session(self):
        if self._session is not None:
            try:
                self._session.destroy()
            finally:
                self._session = None

    def _emit_breakpoint_updates(self):
        for bp in self._ensure_session().breakpoint_list().get("breakpoints", []):
            self._send_event(
                "breakpoint",
                {"reason": "changed", "breakpoint": self._to_dap_breakpoint(bp)},
            )

    def _to_dap_breakpoint(
        self,
        payload: dict[str, Any],
        source_path: str | None = None,
        requested_line: int | None = None,
    ) -> dict[str, Any]:
        details = payload.get("location_details") or []
        first = details[0] if details else {}
        path = first.get("file") or source_path
        line = first.get("line") or requested_line or 0
        dap_bp = {
            "id": payload.get("id"),
            "verified": bool(payload.get("resolved")),
            "line": line,
        }
        if path:
            dap_bp["source"] = self._source_from_path(path)
        if first.get("address"):
            dap_bp["instructionReference"] = first["address"]
        if not dap_bp["verified"]:
            dap_bp["message"] = "Breakpoint is pending and has no resolved LLDB locations yet."
        return dap_bp

    def _source_from_path(self, path: str | None) -> dict[str, Any] | None:
        if not path:
            return None
        source_path = str(path)
        return {"name": Path(source_path).name, "path": source_path}

    def _ensure_session(self) -> LLDBSession:
        if self._session is None:
            self._session = self._session_factory()
        return self._session

    def _alloc_frame_ref(self, thread_id: int, frame_index: int) -> int:
        ref = self._next_ref
        self._next_ref += 1
        self._frame_refs[ref] = (thread_id, frame_index)
        return ref

    def _alloc_variable_ref(self, entry: dict[str, Any]) -> int:
        ref = self._next_ref
        self._next_ref += 1
        self._variable_refs[ref] = entry
        return ref

    def _dap_variables_from_values(self, values) -> list[dict[str, Any]]:
        return [self._dap_variable_from_value(value) for value in values if value and value.IsValid()]

    def _dap_variable_from_value(self, value) -> dict[str, Any]:
        variables_ref = 0
        if value.GetNumChildren() > 0:
            variables_ref = self._alloc_variable_ref({"kind": "children", "value": value})
        payload = {
            "name": value.GetName() or "<unnamed>",
            "value": self._value_display(value),
            "type": value.GetTypeName(),
            "variablesReference": variables_ref,
        }
        evaluate_name = self._value_expression_path(value)
        if evaluate_name:
            payload["evaluateName"] = evaluate_name
        return payload

    def _child_values(self, value) -> list[Any]:
        return [value.GetChildAtIndex(index) for index in range(value.GetNumChildren())]

    def _value_display(self, value) -> str:
        raw = value.GetValue()
        summary = value.GetSummary()
        if raw and summary:
            return f"{raw} {summary}"
        return raw or summary or ""

    def _value_expression_path(self, value) -> str | None:
        try:
            stream = self._ensure_session()._lldb.SBStream()
            value.GetExpressionPath(stream)
            text = stream.GetData()
            return text or value.GetName()
        except Exception:
            return value.GetName()

    def _reset_refs_for_resume(self):
        self._frame_refs.clear()
        self._variable_refs.clear()

    def _coerce_args(self, raw: Any) -> list[str] | None:
        if raw is None:
            return None
        if isinstance(raw, str):
            return shlex.split(raw, posix=os.name != "nt")
        return [str(item) for item in raw]

    def _coerce_env(self, raw: Any) -> list[str] | None:
        if raw is None:
            return None
        if isinstance(raw, dict):
            return [f"{key}={value}" for key, value in raw.items()]
        return [str(item) for item in raw]

    def _parse_address(self, value: str) -> int:
        return int(value, 0)

    def _send_response(
        self,
        request_seq: int,
        command: str,
        body: dict[str, Any] | None = None,
        success: bool = True,
        message: str | None = None,
    ):
        with self._protocol_lock:
            payload: dict[str, Any] = {
                "seq": self._next_seq(),
                "type": "response",
                "request_seq": request_seq,
                "success": success,
                "command": command,
            }
            if body is not None:
                payload["body"] = body
            if message:
                payload["message"] = message
            self._write(payload)

    def _send_event(self, event: str, body: dict[str, Any] | None = None):
        with self._protocol_lock:
            payload: dict[str, Any] = {"seq": self._next_seq(), "type": "event", "event": event}
            if body is not None:
                payload["body"] = body
            self._write(payload)

    def _next_seq(self) -> int:
        seq = self._seq
        self._seq += 1
        return seq

    def _write(self, payload: dict[str, Any]):
        if self._out is None:
            raise RuntimeError("DAP output stream is not initialized")
        self._out.write(encode_message(payload))
        self._out.flush()

    def _log(self, message: str):
        if self._log_file:
            with self._log_file.open("a", encoding="utf-8") as handle:
                handle.write(message + "\n")
        else:
            print(message, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run cli-anything-lldb Debug Adapter Protocol server")
    parser.add_argument("--log-file", default=None, help="Optional file for adapter diagnostics")
    parser.add_argument("--profile", default=None, help="Optional stop-rule profile JSON loaded at adapter startup")
    args = parser.parse_args(argv)
    adapter = LLDBDebugAdapter(log_file=args.log_file, profile_file=args.profile)
    return adapter.run()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
