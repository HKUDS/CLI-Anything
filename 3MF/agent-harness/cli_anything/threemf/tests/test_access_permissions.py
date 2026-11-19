"""Exercise actual filesystem ACLs through complete archive replacement."""

from __future__ import annotations

import csv
import ctypes
import errno
import os
import stat
import struct
import subprocess
import sys
import zipfile

import pytest

from cli_anything.threemf.core import access_permissions, parser
from cli_anything.threemf.tests.test_atomic_write import model_data


linux = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux POSIX ACLs")
darwin = pytest.mark.skipif(sys.platform != "darwin", reason="macOS extended ACLs")
windows = pytest.mark.skipif(os.name != "nt", reason="Windows DACLs")


def linux_acl(permission=0, other=4):
    undefined = 0xffffffff
    entries = [(1, 6, undefined), (2, permission, 65534),
               (4, 4, undefined), (16, 4, undefined), (32, other, undefined)]
    return struct.pack("<I", 2) + b"".join(struct.pack("<HHI", *entry) for entry in entries)


@linux
@pytest.mark.parametrize("permission,other", [(0, 4), (4, 0)], ids=["deny", "grant"])
@pytest.mark.parametrize("via_symlink", [False, True])
def test_linux_named_acl_survives_export(tmp_path, permission, other, via_symlink):
    output = tmp_path / "output.3mf"
    output.write_bytes(b"previous archive")
    os.setxattr(output, "system.posix_acl_access", linux_acl(permission, other))
    expected = os.getxattr(output, "system.posix_acl_access")
    mode = stat.S_IMODE(output.stat().st_mode)
    target = output
    if via_symlink:
        target = tmp_path / "linked.3mf"
        target.symlink_to(output.name)
    parser.write_3mf(model_data(), str(target))
    assert os.getxattr(output, "system.posix_acl_access") == expected
    assert stat.S_IMODE(output.stat().st_mode) == mode
    assert parser.parse_3mf(str(output)).meshes[0].name == "tetrahedron"
    if via_symlink:
        assert target.is_symlink()
    assert set(tmp_path.iterdir()) == {output, target}


@linux
def test_linux_absent_acl_clears_staging_inheritance(tmp_path):
    output = tmp_path / "output.3mf"
    output.write_bytes(b"previous archive")
    output.chmod(0o640)
    with pytest.raises(OSError) as absent:
        os.getxattr(output, "system.posix_acl_access")
    assert absent.value.errno == errno.ENODATA
    os.setxattr(tmp_path, "system.posix_acl_default", linux_acl(4, 0))
    parser.write_3mf(model_data(), str(output))
    with pytest.raises(OSError) as absent:
        os.getxattr(output, "system.posix_acl_access")
    assert absent.value.errno == errno.ENODATA
    assert stat.S_IMODE(output.stat().st_mode) == 0o640
    assert list(tmp_path.iterdir()) == [output]


@linux
def test_linux_new_export_inherits_actual_parent_acl(tmp_path):
    os.setxattr(tmp_path, "system.posix_acl_default", linux_acl(0, 4))
    control = tmp_path / "control"
    control.write_bytes(b"")
    expected = os.getxattr(control, "system.posix_acl_access")
    mode = stat.S_IMODE(control.stat().st_mode)
    control.unlink()
    output = tmp_path / "new.3mf"
    parser.write_3mf(model_data(), str(output))
    assert os.getxattr(output, "system.posix_acl_access") == expected
    assert stat.S_IMODE(output.stat().st_mode) == mode
    assert list(tmp_path.iterdir()) == [output]


@linux
@pytest.mark.parametrize("failure", ["error", "ignored"])
def test_linux_acl_restore_failure_keeps_original(tmp_path, monkeypatch, failure):
    output = tmp_path / "output.3mf"
    output.write_bytes(b"preserve original archive")
    os.setxattr(output, "system.posix_acl_access", linux_acl())
    expected = os.getxattr(output, "system.posix_acl_access")

    def failed_restore(path, attribute, value, *args, **kwargs):
        assert attribute == "system.posix_acl_access"
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
        if failure == "error":
            raise PermissionError(errno.EPERM, "injected ACL restoration failure")

    monkeypatch.setattr(os, "setxattr", failed_restore)
    with pytest.raises(OSError):
        parser.write_3mf(model_data(), str(output))
    assert output.read_bytes() == b"preserve original archive"
    assert os.getxattr(output, "system.posix_acl_access") == expected
    assert list(tmp_path.iterdir()) == [output]


def mac_acl(path):
    result = subprocess.run(["ls", "-lde", str(path)], check=True, capture_output=True, text=True)
    return tuple(line.strip() for line in result.stdout.splitlines()[1:])


def mac_add_acl(path, rule):
    subprocess.run(["chmod", "+a", rule, str(path)], check=True, capture_output=True)


@darwin
@pytest.mark.parametrize("rule", ["user:nobody deny read", "user:nobody allow read"])
@pytest.mark.parametrize("inherited", [False, True])
def test_darwin_named_acl_survives_export(tmp_path, rule, inherited):
    output = tmp_path / "output.3mf"
    if inherited:
        mac_add_acl(tmp_path, rule + ",file_inherit,directory_inherit")
    output.write_bytes(b"previous archive")
    if inherited:
        subprocess.run(["chmod", "-N", str(tmp_path)], check=True, capture_output=True)
    else:
        mac_add_acl(output, rule)
    expected = mac_acl(output)
    assert expected
    assert any("inherited" in entry for entry in expected) == inherited
    parser.write_3mf(model_data(), str(output))
    assert mac_acl(output) == expected
    assert parser.parse_3mf(str(output)).meshes[0].name == "tetrahedron"
    assert list(tmp_path.iterdir()) == [output]


@darwin
def test_darwin_acl_only_write_grant_survives_export(tmp_path):
    output = tmp_path / "output.3mf"
    output.write_bytes(b"previous archive")
    user = subprocess.run(["id", "-un"], check=True, capture_output=True, text=True).stdout.strip()
    output.chmod(0o400)
    mac_add_acl(output, f"user:{user} allow write,append")
    expected = mac_acl(output)
    parser.write_3mf(model_data(), str(output))
    assert stat.S_IMODE(output.stat().st_mode) == 0o400
    assert mac_acl(output) == expected
    assert parser.parse_3mf(str(output)).meshes[0].name == "tetrahedron"


@darwin
def test_darwin_absent_acl_clears_staging_inheritance(tmp_path):
    output = tmp_path / "output.3mf"
    output.write_bytes(b"previous archive")
    assert not mac_acl(output)
    mac_add_acl(tmp_path, "user:nobody allow read,file_inherit,directory_inherit")
    parser.write_3mf(model_data(), str(output))
    assert not mac_acl(output)
    assert list(tmp_path.iterdir()) == [output]


@darwin
def test_darwin_new_export_inherits_actual_parent_acl(tmp_path):
    mac_add_acl(tmp_path, "user:nobody deny read,file_inherit,directory_inherit")
    control = tmp_path / "control"
    control.write_bytes(b"")
    expected = mac_acl(control)
    assert expected and any("inherited" in entry for entry in expected)
    control.unlink()
    output = tmp_path / "new.3mf"
    parser.write_3mf(model_data(), str(output))
    assert mac_acl(output) == expected
    assert list(tmp_path.iterdir()) == [output]


@darwin
def test_darwin_native_acl_error_keeps_original(tmp_path, monkeypatch):
    output = tmp_path / "output.3mf"
    output.write_bytes(b"preserve original archive")
    mac_add_acl(output, "user:nobody deny read")
    expected = mac_acl(output)
    library = access_permissions._darwin_libc()
    original = library.acl_set_file

    def denied(path, kind, acl):
        if path.endswith(b"model.3mf"):
            ctypes.set_errno(errno.EPERM)
            return -1
        return original(path, kind, acl)

    monkeypatch.setattr(library, "acl_set_file", denied)
    with pytest.raises(PermissionError):
        parser.write_3mf(model_data(), str(output))
    assert output.read_bytes() == b"preserve original archive"
    assert mac_acl(output) == expected
    assert list(tmp_path.iterdir()) == [output]


def windows_sid():
    result = subprocess.run(
        ["whoami", "/user", "/fo", "csv", "/nh"],
        check=True, capture_output=True, text=True,
    )
    sid = next(csv.reader(result.stdout.splitlines()))[-1]
    assert sid.startswith("S-1-")
    return sid


def windows_acl(path, sddl=None):
    """Use native SDDL independently of the production ACE comparison."""
    api = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    pointer, dword = ctypes.c_void_p, ctypes.c_uint32
    api.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        ctypes.c_wchar_p, dword, ctypes.POINTER(pointer), ctypes.POINTER(dword),
    ]
    api.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = ctypes.c_int32
    api.SetFileSecurityW.argtypes = [ctypes.c_wchar_p, dword, pointer]
    api.SetFileSecurityW.restype = ctypes.c_int32
    api.GetFileSecurityW.argtypes = [ctypes.c_wchar_p, dword, pointer, dword, ctypes.POINTER(dword)]
    api.GetFileSecurityW.restype = ctypes.c_int32
    api.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
        pointer, dword, dword, ctypes.POINTER(pointer), ctypes.POINTER(dword),
    ]
    api.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = ctypes.c_int32
    kernel.LocalFree.argtypes = [pointer]
    kernel.LocalFree.restype = pointer
    if sddl is not None:
        descriptor, size = pointer(), dword()
        assert api.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, 1, ctypes.byref(descriptor), ctypes.byref(size),
        ), ctypes.WinError(ctypes.get_last_error())
        try:
            flags = 4 | (0x80000000 if sddl.startswith("D:P") else 0x20000000)
            assert api.SetFileSecurityW(str(path), flags, descriptor), ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel.LocalFree(descriptor)
    needed = dword()
    assert not api.GetFileSecurityW(str(path), 4, None, 0, ctypes.byref(needed))
    assert ctypes.get_last_error() == 122
    buffer = ctypes.create_string_buffer(needed.value)
    assert api.GetFileSecurityW(str(path), 4, buffer, len(buffer), ctypes.byref(needed))
    text = pointer()
    assert api.ConvertSecurityDescriptorToStringSecurityDescriptorW(
        buffer, 1, 4, ctypes.byref(text), None,
    )
    try:
        return ctypes.wstring_at(text)
    finally:
        kernel.LocalFree(text)


def windows_can_execute(path):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
    ]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateFileW(str(path), 0x20, 7, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        assert ctypes.get_last_error() == 5
        return False
    assert handle
    kernel.CloseHandle(handle)
    return True


@windows
@pytest.mark.parametrize("deny", [False, True], ids=["grant", "deny"])
@pytest.mark.parametrize("protected", [False, True])
def test_windows_named_acl_survives_export(tmp_path, deny, protected):
    output = tmp_path / "output.3mf"
    output.write_bytes(b"previous archive")
    sid = windows_sid()
    rule = f"(D;;0x20;;;{sid})" if deny else f"(A;;0x20;;;{sid})"
    # FILE_EXECUTE is checked by a handle request; no program is executed.
    mask = "FA" if deny else "0x1f01df"
    expected = windows_acl(output, f"D:{'P' if protected else ''}{rule}(A;;{mask};;;{sid})")
    assert windows_can_execute(output) is not deny
    parser.write_3mf(model_data(), str(output))
    assert windows_acl(output) == expected
    assert windows_can_execute(output) is not deny
    assert parser.parse_3mf(str(output)).meshes[0].name == "tetrahedron"
    assert list(tmp_path.iterdir()) == [output]


@windows
@pytest.mark.parametrize("existing", [False, True])
def test_windows_export_preserves_parent_inherited_acl(tmp_path, existing):
    sid = windows_sid()
    windows_acl(tmp_path, f"D:P(D;OICI;0x20;;;{sid})(A;OICI;FA;;;{sid})")
    control = tmp_path / "control"
    control.write_bytes(b"")
    expected = windows_acl(control)
    assert "ID" in expected
    control.unlink()
    output = tmp_path / "output.3mf"
    if existing:
        output.write_bytes(b"previous archive")
    parser.write_3mf(model_data(), str(output))
    assert windows_acl(output) == expected
    assert not windows_can_execute(output)
    assert parser.parse_3mf(str(output)).meshes[0].name == "tetrahedron"
    assert list(tmp_path.iterdir()) == [output]


@windows
def test_windows_null_dacl_survives_export(tmp_path):
    output = tmp_path / "output.3mf"
    output.write_bytes(b"previous archive")
    expected = windows_acl(output, "D:NO_ACCESS_CONTROL")
    assert "NO_ACCESS_CONTROL" in expected
    parser.write_3mf(model_data(), str(output))
    assert windows_acl(output) == expected
    assert parser.parse_3mf(str(output)).meshes[0].name == "tetrahedron"


@windows
def test_windows_empty_dacl_is_not_null_or_replaced(tmp_path):
    output = tmp_path / "output.3mf"
    output.write_bytes(b"preserve original archive")
    sid = windows_sid()
    expected = windows_acl(output, "D:P")
    try:
        assert "NO_ACCESS_CONTROL" not in expected
        with pytest.raises(PermissionError):
            parser.write_3mf(model_data(), str(output))
        assert windows_acl(output) == expected
    finally:
        windows_acl(output, f"D:P(A;;FA;;;{sid})")
    assert output.read_bytes() == b"preserve original archive"
    assert list(tmp_path.iterdir()) == [output]


@windows
def test_windows_native_acl_error_keeps_original(tmp_path, monkeypatch):
    output = tmp_path / "output.3mf"
    output.write_bytes(b"preserve original archive")
    sid = windows_sid()
    expected = windows_acl(output, f"D:P(D;;0x20;;;{sid})(A;;FA;;;{sid})")
    api, _ = access_permissions._windows_api()
    original = api.SetFileSecurityW

    def denied(path, flags, descriptor):
        if path.endswith("model.3mf"):
            ctypes.set_last_error(5)
            return 0
        return original(path, flags, descriptor)

    monkeypatch.setattr(api, "SetFileSecurityW", denied)
    with pytest.raises(PermissionError):
        parser.write_3mf(model_data(), str(output))
    assert output.read_bytes() == b"preserve original archive"
    assert windows_acl(output) == expected
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("phase", ["read", "restore"])
@pytest.mark.parametrize("existing", [False, True])
def test_acl_errors_preserve_previous_destination(tmp_path, monkeypatch, phase, existing):
    output = tmp_path / "output.3mf"
    if existing:
        output.write_bytes(b"preserve original archive")
    expected = access_permissions.read_access_acl(str(output)) if existing else None
    read_acl = access_permissions.read_access_acl

    def fail(*args, **kwargs):
        raise PermissionError(errno.EPERM, "injected native ACL error")

    monkeypatch.setattr(access_permissions, f"{phase}_access_acl", fail)
    with pytest.raises(PermissionError, match="injected native ACL error"):
        parser.write_3mf(model_data(), str(output))
    if existing:
        assert output.read_bytes() == b"preserve original archive"
        assert read_acl(str(output)) == expected
        assert list(tmp_path.iterdir()) == [output]
    else:
        assert not output.exists()
        assert list(tmp_path.iterdir()) == []
