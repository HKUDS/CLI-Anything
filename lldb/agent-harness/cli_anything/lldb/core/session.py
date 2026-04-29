"""
Stateful LLDB session wrapper built on LLDB Python API.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from cli_anything.lldb.utils.lldb_backend import ensure_lldb_importable

MEMORY_FIND_MAX_SCAN_SIZE = 1024 * 1024
MEMORY_FIND_CHUNK_SIZE = 64 * 1024


class LLDBSession:
    """Encapsulates one LLDB debugger session using Python API only."""

    _STATE_NAMES = {
        0: "invalid",
        1: "unloaded",
        2: "connected",
        3: "attaching",
        4: "launching",
        5: "stopped",
        6: "running",
        7: "stepping",
        8: "crashed",
        9: "detached",
        10: "exited",
        11: "suspended",
    }

    def __init__(self):
        self._lldb = ensure_lldb_importable()
        self._lldb.SBDebugger.Initialize()
        self.debugger = self._lldb.SBDebugger.Create()
        self.debugger.SetAsync(False)
        self.target = None
        self.process = None
        self._process_origin: str | None = None

    def target_create(self, exe_path: str, arch: Optional[str] = None) -> Dict[str, Any]:
        arch = arch or self._lldb.LLDB_ARCH_DEFAULT
        self.target = self.debugger.CreateTargetWithFileAndArch(exe_path, arch)
        if not self.target or not self.target.IsValid():
            raise RuntimeError(f"Failed to create target: {exe_path}")
        return {
            "executable": exe_path,
            "arch": arch,
            "triple": self.target.GetTriple(),
        }

    def target_info(self) -> Dict[str, Any]:
        self._require_target()
        exe = self.target.GetExecutable()
        return {
            "triple": self.target.GetTriple(),
            "executable": str(exe) if exe else None,
            "byte_order": str(self.target.GetByteOrder()),
            "address_byte_size": self.target.GetAddressByteSize(),
            "num_modules": self.target.GetNumModules(),
            "num_breakpoints": self.target.GetNumBreakpoints(),
        }

    def attach_pid(self, pid: int) -> Dict[str, Any]:
        self._require_target()
        attach_info = self._lldb.SBAttachInfo()
        attach_info.SetProcessID(pid)
        return self._attach(attach_info)

    def attach_name(self, name: str, wait_for: bool = False) -> Dict[str, Any]:
        self._require_target()
        attach_info = self._lldb.SBAttachInfo()
        attach_info.SetExecutable(name)
        if wait_for:
            attach_info.SetWaitForLaunch(True, False)
        return self._attach(attach_info)

    def _attach(self, attach_info) -> Dict[str, Any]:
        error = self._lldb.SBError()
        self.process = self.target.Attach(attach_info, error)
        if not error.Success():
            raise RuntimeError(f"Attach failed: {error}")
        self._process_origin = "attached"
        return self.process_info()

    def launch(
        self,
        args: Optional[List[str]] = None,
        env: Optional[List[str]] = None,
        working_dir: Optional[str] = None,
        stop_at_entry: bool = False,
        suppress_stdio: bool = False,
    ) -> Dict[str, Any]:
        self._require_target()
        error = self._lldb.SBError()
        launch_info = self._lldb.SBLaunchInfo(args or [])
        launch_info.SetWorkingDirectory(working_dir or os.getcwd())
        if env:
            launch_info.SetEnvironmentEntries(env, True)
        if stop_at_entry:
            launch_info.SetLaunchFlags(self._lldb.eLaunchFlagStopAtEntry)
        if suppress_stdio:
            launch_info.AddSuppressFileAction(1, False, True)
            launch_info.AddSuppressFileAction(2, False, True)
        self.process = self.target.Launch(launch_info, error)
        if not error.Success():
            raise RuntimeError(f"Launch failed: {error}")
        if not self.process or not self.process.IsValid():
            raise RuntimeError("Launch failed")
        self._process_origin = "launched"
        return self.process_info()

    def detach(self) -> Dict[str, Any]:
        self._require_process()
        error = self.process.Detach()
        if not error.Success():
            raise RuntimeError(f"Detach failed: {error}")
        self.process = None
        self._process_origin = None
        return {"status": "detached"}

    def breakpoint_set(
        self,
        file: Optional[str] = None,
        line: Optional[int] = None,
        function: Optional[str] = None,
        condition: Optional[str] = None,
        allow_pending: bool = False,
    ) -> Dict[str, Any]:
        self._require_target()
        if function:
            bp = self.target.BreakpointCreateByName(function)
        elif file and line:
            bp = self.target.BreakpointCreateByLocation(file, line)
        else:
            raise ValueError("Specify --file/--line or --function")
        if not bp or not bp.IsValid():
            raise RuntimeError("Failed to create breakpoint")
        if condition:
            bp.SetCondition(condition)
        details = self._breakpoint_payload(bp)
        if not details["resolved"] and not allow_pending:
            bp_id = bp.GetID()
            self.target.BreakpointDelete(bp_id)
            raise RuntimeError(
                "Breakpoint is unresolved. Pass allow_pending=True or use "
                "the CLI --allow-pending flag if a pending breakpoint is intended."
            )
        return details

    def breakpoint_list(self) -> Dict[str, Any]:
        self._require_target()
        bps = []
        for i in range(self.target.GetNumBreakpoints()):
            bp = self.target.GetBreakpointAtIndex(i)
            bps.append(self._breakpoint_payload(bp))
        return {"breakpoints": bps}

    def breakpoint_delete(self, bp_id: int) -> Dict[str, Any]:
        self._require_target()
        deleted = self.target.BreakpointDelete(bp_id)
        if not deleted:
            raise RuntimeError(f"Failed to delete breakpoint: {bp_id}")
        return {"deleted": bp_id}

    def breakpoint_enable(self, bp_id: int, enabled: bool = True) -> Dict[str, Any]:
        self._require_target()
        bp = self.target.FindBreakpointByID(bp_id)
        if not bp or not bp.IsValid():
            raise RuntimeError(f"Breakpoint not found: {bp_id}")
        bp.SetEnabled(enabled)
        return {"id": bp_id, "enabled": bool(enabled)}

    def step_over(self) -> Dict[str, Any]:
        self._current_thread().StepOver()
        return self._frame_info()

    def step_into(self) -> Dict[str, Any]:
        self._current_thread().StepInto()
        return self._frame_info()

    def step_out(self) -> Dict[str, Any]:
        self._current_thread().StepOut()
        return self._frame_info()

    def continue_exec(self) -> Dict[str, Any]:
        self._require_process()
        error = self.process.Continue()
        if error is not None and not error.Success():
            raise RuntimeError(f"Continue failed: {error}")
        return self._process_info()

    def interrupt(self) -> Dict[str, Any]:
        self._require_process()
        error = self.process.Stop()
        if error is not None and not error.Success():
            raise RuntimeError(f"Interrupt failed: {error}")
        return self._process_info()

    def interrupt_async(self) -> Dict[str, Any]:
        self._require_process()
        error = self.process.SendAsyncInterrupt()
        if error is not None and not error.Success():
            raise RuntimeError(f"Async interrupt failed: {error}")
        return {"status": "interrupt_requested"}

    def backtrace(self, limit: int = 50) -> Dict[str, Any]:
        thread = self._current_thread()
        frames = []
        for i in range(min(thread.GetNumFrames(), limit)):
            f = thread.GetFrameAtIndex(i)
            line_entry = f.GetLineEntry()
            frames.append(
                {
                    "index": i,
                    "function": f.GetFunctionName(),
                    "file": str(line_entry.GetFileSpec()) if line_entry.IsValid() else None,
                    "line": line_entry.GetLine() if line_entry.IsValid() else None,
                    "address": hex(f.GetPC()),
                }
            )
        return {"thread_id": thread.GetThreadID(), "frames": frames, "total_frames": thread.GetNumFrames()}

    def locals(self) -> Dict[str, Any]:
        frame = self._current_frame()
        variables = frame.GetVariables(True, True, False, True)
        result = []
        for v in variables:
            result.append(
                {
                    "name": v.GetName(),
                    "type": v.GetTypeName(),
                    "value": v.GetValue(),
                    "summary": v.GetSummary(),
                    "num_children": v.GetNumChildren(),
                }
            )
        return {"variables": result}

    def local_values(self):
        """Return raw SBValue locals for in-process adapters such as DAP."""
        frame = self._current_frame()
        variables = frame.GetVariables(True, True, False, True)
        return [variables.GetValueAtIndex(i) for i in range(variables.GetSize())]

    def set_local_variable(self, thread_id: int, frame_index: int, name: str, value: str):
        self.thread_select(thread_id)
        self.frame_select(frame_index)
        frame = self._current_frame()
        variable = frame.FindVariable(name)
        if not variable or not variable.IsValid():
            raise RuntimeError(f"Variable not found: {name}")
        self._set_value(variable, value)
        return variable

    def set_child_value(self, parent, name: str, value: str):
        child = parent.GetChildMemberWithName(name)
        if not child or not child.IsValid():
            for index in range(parent.GetNumChildren()):
                candidate = parent.GetChildAtIndex(index)
                if candidate.GetName() == name:
                    child = candidate
                    break
        if not child or not child.IsValid():
            raise RuntimeError(f"Child variable not found: {name}")
        self._set_value(child, value)
        return child

    def evaluate(self, expr: str) -> Dict[str, Any]:
        frame = self._current_frame()
        val = frame.EvaluateExpression(expr)
        return {
            "expression": expr,
            "type": val.GetTypeName(),
            "value": val.GetValue(),
            "summary": val.GetSummary(),
            "error": str(val.GetError()) if not val.GetError().Success() else None,
        }

    def threads(self) -> Dict[str, Any]:
        self._require_process()
        result = []
        for i in range(self.process.GetNumThreads()):
            t = self.process.GetThreadAtIndex(i)
            desc = self._lldb.SBStream()
            t.GetStatus(desc)
            result.append(
                {
                    "index": i,
                    "id": t.GetThreadID(),
                    "name": t.GetName(),
                    "stop_reason": desc.GetData().strip(),
                    "num_frames": t.GetNumFrames(),
                    "selected": t.GetThreadID() == self.process.GetSelectedThread().GetThreadID(),
                }
            )
        return {"threads": result}

    def thread_select(self, thread_id: int) -> Dict[str, Any]:
        self._require_process()
        thread = self.process.GetThreadByID(thread_id)
        if not thread or not thread.IsValid():
            raise RuntimeError(f"Thread not found: {thread_id}")
        self.process.SetSelectedThread(thread)
        return {"selected_thread_id": thread_id}

    def frame_select(self, index: int) -> Dict[str, Any]:
        thread = self._current_thread()
        if index < 0 or index >= thread.GetNumFrames():
            raise RuntimeError(f"Frame index out of range: {index}")
        frame = thread.GetFrameAtIndex(index)
        thread.SetSelectedFrame(index)
        line_entry = frame.GetLineEntry()
        return {
            "selected_frame_index": index,
            "function": frame.GetFunctionName(),
            "file": str(line_entry.GetFileSpec()) if line_entry.IsValid() else None,
            "line": line_entry.GetLine() if line_entry.IsValid() else None,
        }

    def frame_info(self) -> Dict[str, Any]:
        return self._frame_info()

    def read_memory(self, address: int, size: int) -> Dict[str, Any]:
        self._require_process()
        error = self._lldb.SBError()
        data = self.process.ReadMemory(address, size, error)
        if not error.Success():
            raise RuntimeError(f"Read memory failed: {error}")
        return {
            "address": hex(address),
            "size": size,
            "hex": data.hex(),
        }

    def find_memory(
        self,
        needle: str,
        start_address: int,
        size: int,
        *,
        chunk_size: int = MEMORY_FIND_CHUNK_SIZE,
        max_scan_size: int = MEMORY_FIND_MAX_SCAN_SIZE,
    ) -> Dict[str, Any]:
        self._require_process()
        if not needle:
            raise ValueError("Needle must not be empty")
        if size <= 0:
            raise ValueError("Scan size must be positive")
        if size > max_scan_size:
            raise ValueError(
                f"Scan size exceeds max supported scan size ({max_scan_size} bytes)"
            )
        if chunk_size <= 0:
            raise ValueError("Chunk size must be positive")

        needle_bytes = needle.encode("utf-8")
        overlap = max(0, len(needle_bytes) - 1)
        remaining = size
        current = start_address
        trailing = b""

        while remaining > 0:
            read_size = min(chunk_size, remaining)
            chunk = bytes.fromhex(self.read_memory(current, read_size)["hex"])
            haystack = trailing + chunk
            idx = haystack.find(needle_bytes)
            if idx >= 0:
                base = current - len(trailing)
                return {
                    "needle": needle,
                    "start": hex(start_address),
                    "size": size,
                    "found": True,
                    "address": hex(base + idx),
                    "chunk_size": chunk_size,
                    "max_scan_size": max_scan_size,
                }

            trailing = haystack[-overlap:] if overlap else b""
            current += read_size
            remaining -= read_size

        return {
            "needle": needle,
            "start": hex(start_address),
            "size": size,
            "found": False,
            "address": None,
            "chunk_size": chunk_size,
            "max_scan_size": max_scan_size,
        }

    def disassemble(self, address: int, count: int = 8) -> Dict[str, Any]:
        self._require_target()
        sb_address = self.target.ResolveLoadAddress(address)
        if not sb_address or not sb_address.IsValid():
            raise RuntimeError(f"Could not resolve address: {hex(address)}")
        instructions = self.target.ReadInstructions(sb_address, max(1, count))
        result = []
        for i in range(instructions.GetSize()):
            inst = instructions.GetInstructionAtIndex(i)
            stream = self._lldb.SBStream()
            inst.GetDescription(stream)
            inst_address = inst.GetAddress().GetLoadAddress(self.target)
            result.append(
                {
                    "address": hex(inst_address),
                    "instruction": stream.GetData().strip(),
                }
            )
        return {"instructions": result}

    def loaded_sources(self) -> Dict[str, Any]:
        self._require_target()
        seen = set()
        sources = []
        for module_index in range(self.target.GetNumModules()):
            module = self.target.GetModuleAtIndex(module_index)
            for unit_index in range(module.GetNumCompileUnits()):
                unit = module.GetCompileUnitAtIndex(unit_index)
                file_spec = unit.GetFileSpec()
                path = self._filespec_path(file_spec)
                if not path or path in seen:
                    continue
                seen.add(path)
                sources.append({"name": os.path.basename(path), "path": path})
        return {"sources": sources}

    def modules(self) -> Dict[str, Any]:
        self._require_target()
        modules = []
        for index in range(self.target.GetNumModules()):
            module = self.target.GetModuleAtIndex(index)
            file_spec = module.GetFileSpec()
            path = self._filespec_path(file_spec)
            header_addr = module.GetObjectFileHeaderAddress()
            load_addr = header_addr.GetLoadAddress(self.target) if header_addr and header_addr.IsValid() else None
            modules.append(
                {
                    "id": index + 1,
                    "name": os.path.basename(path) if path else str(file_spec),
                    "path": path,
                    "symbol_status": "loaded" if module.GetNumCompileUnits() > 0 else "unknown",
                    "address": hex(load_addr) if load_addr and load_addr != self._lldb.LLDB_INVALID_ADDRESS else None,
                    "version": module.GetVersion(),
                }
            )
        return {"modules": modules}

    def load_core(self, core_path: str) -> Dict[str, Any]:
        self._require_target()
        self.process = self.target.LoadCore(core_path)
        if not self.process or not self.process.IsValid():
            raise RuntimeError(f"Failed to load core: {core_path}")
        self._process_origin = "core"
        return self.process_info()

    def destroy(self):
        if self.process and self.process.IsValid():
            try:
                if self._process_origin == "attached":
                    self.process.Detach()
                elif self._process_origin == "launched":
                    state = self.process.GetState()
                    if state not in (
                        self._lldb.eStateDetached,
                        self._lldb.eStateExited,
                    ):
                        self.process.Kill()
            except Exception:
                pass
            finally:
                self.process = None
                self._process_origin = None
        self._lldb.SBDebugger.Destroy(self.debugger)
        self._lldb.SBDebugger.Terminate()

    def session_status(self) -> Dict[str, Any]:
        has_target = bool(self.target and self.target.IsValid())
        has_process = bool(self.process and self.process.IsValid())
        return {
            "has_target": has_target,
            "has_process": has_process,
            "process_origin": self._process_origin if has_process else None,
        }

    def process_info(self) -> Dict[str, Any]:
        return self._process_info()

    def _require_target(self):
        if self.target is None or not self.target.IsValid():
            raise RuntimeError("No target. Create target first.")

    def _require_process(self):
        if self.process is None or not self.process.IsValid():
            raise RuntimeError("No process. Launch/attach or load core first.")

    def _current_thread(self):
        self._require_process()
        thread = self.process.GetSelectedThread()
        if not thread or not thread.IsValid():
            if self.process.GetNumThreads() > 0:
                thread = self.process.GetThreadAtIndex(0)
                self.process.SetSelectedThread(thread)
            else:
                raise RuntimeError("No thread available.")
        return thread

    def _current_frame(self):
        thread = self._current_thread()
        frame = thread.GetSelectedFrame()
        if not frame or not frame.IsValid():
            if thread.GetNumFrames() > 0:
                frame = thread.GetFrameAtIndex(0)
                thread.SetSelectedFrame(0)
            else:
                raise RuntimeError("No frame available.")
        return frame

    def _process_info(self) -> Dict[str, Any]:
        self._require_process()
        state = self.process.GetState()
        selected = self.process.GetSelectedThread()
        selected_thread_id = selected.GetThreadID() if selected and selected.IsValid() else None
        return {
            "pid": self.process.GetProcessID(),
            "state": self._STATE_NAMES.get(state, str(state)),
            "num_threads": self.process.GetNumThreads(),
            "selected_thread_id": selected_thread_id,
            "stop": self._stop_info(selected) if selected_thread_id is not None else None,
            "exit_status": self.process.GetExitStatus(),
        }

    def _frame_info(self) -> Dict[str, Any]:
        f = self._current_frame()
        line_entry = f.GetLineEntry()
        return {
            "function": f.GetFunctionName(),
            "file": str(line_entry.GetFileSpec()) if line_entry.IsValid() else None,
            "line": line_entry.GetLine() if line_entry.IsValid() else None,
            "address": hex(f.GetPC()),
        }

    def _breakpoint_payload(self, bp) -> Dict[str, Any]:
        locations = self._breakpoint_locations(bp)
        return {
            "id": bp.GetID(),
            "hits": bp.GetHitCount(),
            "locations": len(locations),
            "resolved": len(locations) > 0,
            "location_details": locations,
            "enabled": bp.IsEnabled(),
            "condition": bp.GetCondition() or None,
        }

    def _breakpoint_locations(self, bp) -> List[Dict[str, Any]]:
        result = []
        for i in range(bp.GetNumLocations()):
            loc = bp.GetLocationAtIndex(i)
            address = loc.GetAddress()
            line_entry = address.GetLineEntry()
            load_addr = address.GetLoadAddress(self.target)
            function = address.GetFunction()
            result.append(
                {
                    "id": loc.GetID(),
                    "address": hex(load_addr) if load_addr != self._lldb.LLDB_INVALID_ADDRESS else None,
                    "file": str(line_entry.GetFileSpec()) if line_entry.IsValid() else None,
                    "line": line_entry.GetLine() if line_entry.IsValid() else None,
                    "column": line_entry.GetColumn() if line_entry.IsValid() else None,
                    "function": function.GetName() if function and function.IsValid() else None,
                    "enabled": loc.IsEnabled(),
                    "hit_count": loc.GetHitCount(),
                }
            )
        return result

    def _stop_info(self, thread) -> Dict[str, Any]:
        if thread is None or not thread.IsValid():
            return {"reason": None, "description": None, "hit_breakpoint_ids": [], "frame": None}

        reason = thread.GetStopReason()
        reason_name = self._stop_reason_name(reason)
        frame = self._thread_frame_summary(thread)
        return {
            "reason": reason_name,
            "description": self._thread_stop_description(thread),
            "hit_breakpoint_ids": self._hit_breakpoint_ids(thread) if reason_name == "breakpoint" else [],
            "frame": frame,
            "module": frame.get("module") if frame else None,
            "function": frame.get("function") if frame else None,
        }

    def _stop_reason_name(self, reason: int) -> str | None:
        lldb = self._lldb
        mapping = {
            getattr(lldb, "eStopReasonBreakpoint", object()): "breakpoint",
            getattr(lldb, "eStopReasonWatchpoint", object()): "watchpoint",
            getattr(lldb, "eStopReasonSignal", object()): "signal",
            getattr(lldb, "eStopReasonException", object()): "exception",
            getattr(lldb, "eStopReasonTrace", object()): "step",
            getattr(lldb, "eStopReasonPlanComplete", object()): "step",
            getattr(lldb, "eStopReasonExec", object()): "entry",
            getattr(lldb, "eStopReasonThreadExiting", object()): "thread-exiting",
            getattr(lldb, "eStopReasonNone", object()): None,
            getattr(lldb, "eStopReasonInvalid", object()): None,
        }
        return mapping.get(reason, str(reason))

    def _thread_stop_description(self, thread) -> str | None:
        stream = self._lldb.SBStream()
        thread.GetStatus(stream)
        text = stream.GetData().strip()
        return text or None

    def _thread_frame_summary(self, thread) -> Dict[str, Any] | None:
        frame = thread.GetSelectedFrame()
        if not frame or not frame.IsValid():
            if thread.GetNumFrames() <= 0:
                return None
            frame = thread.GetFrameAtIndex(0)
        line_entry = frame.GetLineEntry()
        module = frame.GetModule()
        module_path = self._filespec_path(module.GetFileSpec()) if module and module.IsValid() else None
        return {
            "function": frame.GetFunctionName(),
            "module": os.path.basename(module_path) if module_path else None,
            "module_path": module_path,
            "file": str(line_entry.GetFileSpec()) if line_entry.IsValid() else None,
            "line": line_entry.GetLine() if line_entry.IsValid() else None,
            "address": hex(frame.GetPC()),
        }

    def _hit_breakpoint_ids(self, thread) -> List[int]:
        ids = []
        data_count = thread.GetStopReasonDataCount()
        for index in range(0, data_count, 2):
            bp_id = thread.GetStopReasonDataAtIndex(index)
            if bp_id:
                ids.append(int(bp_id))
        return ids

    def _filespec_path(self, file_spec) -> str | None:
        if not file_spec or not file_spec.IsValid():
            return None
        directory = file_spec.GetDirectory()
        filename = file_spec.GetFilename()
        if directory and filename:
            return os.path.normpath(os.path.join(directory, filename))
        if filename:
            return os.path.normpath(filename)
        text = str(file_spec)
        return os.path.normpath(text) if text else None

    def _set_value(self, variable, value: str):
        error = self._lldb.SBError()
        ok = variable.SetValueFromCString(value, error)
        if not ok or not error.Success():
            raise RuntimeError(f"Set variable failed: {error}")
