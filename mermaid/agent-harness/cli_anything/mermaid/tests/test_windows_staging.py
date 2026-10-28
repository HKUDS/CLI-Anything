"""Win32 API/sharing emulation; these controls are not native Windows proof."""
import ctypes
import io
import os
import stat
import sys
import types

import pytest

from cli_anything.mermaid.utils import mermaid_backend


class Function:
    def __init__(self, call): self.call = call
    def __call__(self, *args): return self.call(*args)


@pytest.fixture
def windows_handles(monkeypatch):
    if os.name == "nt":
        pytest.skip("POSIX-backed API emulation; use native Windows lifecycle controls")
    real_open, real_close, real_dup, real_fstat = os.open, os.close, os.dup, os.fstat
    real_replace, real_unlink, real_fchmod = os.replace, os.unlink, os.fchmod
    handles, events = {}, []
    state = {"adoption_fails": False, "reopen_fails": False, "restore_fails": False, "mask": 0}

    def register(fd, inode, share):
        handle = (1 << 40) + len(handles)
        handles[handle] = {"fd": fd, "inode": inode, "share": share, "closed": False}
        return handle

    def crt_open(path, flags, mode=0o777, **kwargs):
        fd = real_open(path, flags, mode, **kwargs)
        if ".mermaid-" in os.fspath(path):
            readonly = not bool(mode & ~state["mask"] & stat.S_IWRITE)
            real_fchmod(fd, 0o444 if readonly else 0o666)
            inode = {"path": path, "attributes": 0x20 | int(readonly)}
            register(fd, inode, 0)
            events.append(("crt_create", mode, state["mask"]))
        return fd

    def get_handle(fd):
        return next(h for h, entry in handles.items() if entry["fd"] == fd and not entry["closed"])

    def reopen(original, access, share, flags):
        old = handles[original]
        events.append(("reopen", original, access, share, flags))
        assert access == 0x40000000 and share == 7 and flags == 0
        if state["reopen_fails"] or old["inode"]["attributes"] & 1:
            return ctypes.c_void_p(-1).value
        return register(real_dup(old["fd"]), old["inode"], share)

    def get_info(handle, kind, value, size):
        assert kind == 0 and size == 40
        value._obj.FileAttributes = handles[handle]["inode"]["attributes"]
        return 1

    def set_info(handle, kind, value, size):
        assert kind == 0 and size == 40
        attrs = value._obj.FileAttributes
        events.append(("attributes", handle, attrs))
        if state["restore_fails"] and attrs & 1:
            return 0
        entry = handles[handle]
        entry["inode"]["attributes"] = attrs
        real_fchmod(entry["fd"], 0o444 if attrs & 1 else 0o666)
        return 1

    def close_handle(handle):
        entry = handles[handle]
        real_close(entry["fd"])
        entry["closed"] = True
        return 1

    def adopt(handle, flags):
        events.append(("adopt", handle, flags))
        if state["adoption_fails"]:
            raise OSError("CRT descriptor allocation failed")
        return handles[handle]["fd"]

    def fstat(fd):
        value = real_fstat(fd)
        try:
            entry = handles[get_handle(fd)]
        except StopIteration:
            return value
        class WithAttributes:
            st_file_attributes = entry["inode"]["attributes"]
            def __getattr__(self, name): return getattr(value, name)
        return WithAttributes()

    def close_fd(fd):
        for entry in handles.values():
            if entry["fd"] == fd and not entry["closed"]:
                entry["closed"] = True
        return real_close(fd)

    def check_delete(path, deleting=False):
        for entry in handles.values():
            if not entry["closed"] and entry["inode"]["path"] == path:
                if not entry["share"] & 4:
                    raise PermissionError("Windows sharing violation")
                if deleting and entry["inode"]["attributes"] & 1:
                    raise PermissionError("Windows readonly deletion denied")

    def replace(source, destination):
        check_delete(source)
        return real_replace(source, destination)

    def unlink(path, *args, **kwargs):
        check_delete(path, deleting=True)
        return real_unlink(path, *args, **kwargs)

    def legacy_create(path, access, share, security, disposition, attributes, template):
        # Failure-before adapter: CreateFileW does not apply CRT mode/umask.
        fd = real_open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        return register(fd, {"path": path, "attributes": attributes}, share)

    kernel = types.SimpleNamespace(CreateFileW=Function(legacy_create), ReOpenFile=Function(reopen), CloseHandle=Function(close_handle),
                                  GetFileInformationByHandleEx=Function(get_info),
                                  SetFileInformationByHandle=Function(set_info))
    monkeypatch.setattr(mermaid_backend.sys, "platform", "win32")
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: kernel, raising=False)
    monkeypatch.setattr(ctypes, "WinError", lambda: OSError("Win32 operation failed"), raising=False)
    monkeypatch.setitem(sys.modules, "msvcrt", types.SimpleNamespace(open_osfhandle=adopt, get_osfhandle=get_handle))
    monkeypatch.setattr(os, "O_BINARY", 0x8000, raising=False)
    monkeypatch.setattr(os, "O_NOINHERIT", 0x80, raising=False)
    monkeypatch.setattr(os, "open", crt_open)
    monkeypatch.setattr(os, "close", close_fd)
    monkeypatch.setattr(os, "fstat", fstat)
    monkeypatch.setattr(os, "replace", replace)
    monkeypatch.setattr(os, "unlink", unlink)
    monkeypatch.setattr(mermaid_backend.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"<svg/>"))
    return handles, events, state


@pytest.mark.parametrize("mask", [0, 0o200])
@pytest.mark.parametrize("failure", [None, "write", "publish"])
def test_windows_crt_umask_preserved_through_publication(windows_handles, monkeypatch, tmp_path, mask, failure):
    handles, events, state = windows_handles
    state["mask"] = mask
    output = tmp_path / "out.svg"
    if failure == "write":
        fdopen = os.fdopen
        class ShortWriter:
            def __init__(self, file): self.file = file
            def __enter__(self): self.file.__enter__(); return self
            def __exit__(self, *args): return self.file.__exit__(*args)
            def write(self, data): self.file.write(data[:1]); return 1
        monkeypatch.setattr(os, "fdopen", lambda fd, *a, **k: ShortWriter(fdopen(fd, *a, **k)))
    elif failure == "publish":
        def fail_publish(*args): raise OSError("publication denied")
        monkeypatch.setattr(os, "replace", fail_publish)
    if failure:
        with pytest.raises(RuntimeError, match="Incomplete|publication denied"):
            mermaid_backend.render_to_file("pako:x", str(output), "svg")
        assert not output.exists()
    else:
        mermaid_backend.render_to_file("pako:x", str(output), "svg")
        assert output.read_bytes() == b"<svg/>"
        assert bool(output.stat().st_mode & stat.S_IWRITE) is (mask == 0)
    assert not list(tmp_path.glob(".mermaid-*"))
    assert all(entry["closed"] for entry in handles.values())
    assert events[0] == ("crt_create", 0o666, mask)
    assert any(event[0] == "reopen" for event in events)


@pytest.mark.parametrize("mode", [0o444, 0o666])
def test_windows_explicit_creation_mode_preserved(windows_handles, tmp_path, mode):
    handles, _, _ = windows_handles
    path = tmp_path / ".mermaid-stage"
    fd = mermaid_backend._open_staging_file(str(path), mode)
    try:
        assert bool(os.fstat(fd).st_mode & stat.S_IWRITE) is bool(mode & stat.S_IWRITE)
        mermaid_backend._windows_set_readonly(fd, False)
        os.unlink(str(path))
    finally:
        os.close(fd)
    assert all(entry["closed"] for entry in handles.values())


@pytest.mark.parametrize("mode,mask", [(0o444, 0), (0o666, 0o200)])
def test_windows_readonly_contract_independent_of_factory_strategy(windows_handles, tmp_path, mode, mask):
    _, _, state = windows_handles
    state["mask"] = mask
    path = tmp_path / ".mermaid-stage"
    fd = mermaid_backend._open_staging_file(str(path), mode)
    try:
        assert not os.fstat(fd).st_mode & stat.S_IWRITE
    finally:
        os.close(fd)
        path.unlink()


@pytest.mark.parametrize("failure", ["reopen_fails", "adoption_fails", "restore_fails"])
def test_windows_handle_transition_failure_preserves_ownership(windows_handles, tmp_path, failure):
    handles, _, state = windows_handles
    state["mask"] = 0o200
    state[failure] = True
    with pytest.raises(OSError, match="failed"):
        mermaid_backend._open_staging_file(str(tmp_path / ".mermaid-stage"), 0o666)
    assert not list(tmp_path.iterdir())
    assert all(entry["closed"] for entry in handles.values())


def test_windows_exclusive_creation_preserves_collision(windows_handles, tmp_path):
    handles, events, _ = windows_handles
    collision = tmp_path / ".mermaid-stage"
    collision.write_bytes(b"another writer")
    with pytest.raises(FileExistsError):
        mermaid_backend._open_staging_file(str(collision), 0o666)
    assert collision.read_bytes() == b"another writer"
    assert not handles and not events


@pytest.mark.skipif(sys.platform != "win32", reason="requires native Win32 sharing, CRT mask and deletion semantics")
@pytest.mark.parametrize("mask", [0, 0o200])
@pytest.mark.parametrize("failure", [None, "write", "publish"])
def test_native_windows_new_output_handle_lifecycle(monkeypatch, tmp_path, mask, failure):
    monkeypatch.setattr(mermaid_backend.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"<svg/>"))
    output = tmp_path / "out.svg"
    descriptors = []
    fdopen = os.fdopen

    def observe_descriptor(fd, *args, **kwargs):
        descriptors.append(fd)
        if failure == "write": raise OSError("injected write setup failure")
        return fdopen(fd, *args, **kwargs)

    monkeypatch.setattr(os, "fdopen", observe_descriptor)
    if failure == "publish":
        def fail_publish(*args): raise OSError("injected publication failure")
        monkeypatch.setattr(os, "replace", fail_publish)
    previous = os.umask(mask)
    try:
        if failure:
            with pytest.raises(RuntimeError, match="injected"):
                mermaid_backend.render_to_file("pako:x", str(output), "svg")
            assert not output.exists()
        else:
            mermaid_backend.render_to_file("pako:x", str(output), "svg")
            assert output.read_bytes() == b"<svg/>"
            assert bool(output.stat().st_mode & stat.S_IWRITE) is (mask == 0)
        assert descriptors
        assert not list(tmp_path.glob(".mermaid-*"))
        for fd in descriptors:
            with pytest.raises(OSError): os.fstat(fd)
    finally:
        os.umask(previous)
        if output.exists(): os.chmod(output, 0o666)
