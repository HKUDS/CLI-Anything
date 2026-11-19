"""Preserve native access ACLs before publishing a replacement archive.

Only discretionary access permissions are copied, not arbitrary extended
attributes or Windows audit policies. Native errors and read-back differences
abort the export while the original destination is still present.
"""

from __future__ import annotations

import ctypes
import errno
import os
import sys
from functools import lru_cache


_LINUX_ACCESS_ACL = "system.posix_acl_access"


def read_access_acl(path: str, descriptor: int | None = None) -> bytes | None:
    """Snapshot the existing file's native access permissions."""
    if sys.platform.startswith("linux"):
        return _read_linux_acl(descriptor if descriptor is not None else path)
    if sys.platform == "darwin":
        return _read_darwin_acl(descriptor if descriptor is not None else path)
    if os.name == "nt":
        return _read_windows_permissions(path, descriptor)
    raise OSError(errno.ENOTSUP, "Native access ACL preservation is unsupported")


def restore_access_acl(path: str, access_acl: bytes | None) -> None:
    """Restore and verify permissions after ownership and mode restoration."""
    if sys.platform.startswith("linux"):
        if access_acl is None:
            try:
                os.removexattr(path, _LINUX_ACCESS_ACL)
            except OSError as error:
                if error.errno != errno.ENODATA:
                    raise
        else:
            os.setxattr(path, _LINUX_ACCESS_ACL, access_acl)
        actual = _read_linux_acl(path)
    elif sys.platform == "darwin":
        # ACL-granted writes need not be reflected in the POSIX mode bits.
        # These metadata APIs do not require reopening the archive for data I/O.
        _set_darwin_acl(path, access_acl)
        actual = _read_darwin_acl(path)
    elif os.name == "nt":
        _restore_windows_permissions(path, access_acl)
        return
    else:
        raise OSError(errno.ENOTSUP, "Native access ACL preservation is unsupported")
    if actual != access_acl:
        raise OSError(errno.EPERM, "Restored access ACL differs from the destination")


def make_staging_private(path: str) -> None:
    """Keep archive contents private before their final permissions are set."""
    if sys.platform.startswith("linux"):
        # A parent's default ACL can remove owner write/traverse bits even
        # from mkdir(0700). chmod restores them while keeping the ACL mask
        # and all other-user access at zero.
        if os.stat(path).st_mode & 0o7777 != 0o700:
            os.chmod(path, 0o700)
    elif sys.platform == "darwin":
        # macOS inherited allow entries can grant access despite mode 0700.
        _set_darwin_acl(path, None)
        if _read_darwin_acl(path) is not None:
            raise OSError(errno.EPERM, "Could not clear staging directory ACL")
    elif os.name == "nt":
        # Python versions before the mkdir(0700) fix can inherit a broad DACL.
        # Include inheritance flags so the archive itself is private as well.
        _make_windows_staging_private(path)


def _read_linux_acl(path: str | int) -> bytes | None:
    try:
        return os.getxattr(path, _LINUX_ACCESS_ACL)
    except OSError as error:
        if error.errno == errno.ENODATA:
            return None
        raise


@lru_cache(maxsize=1)
def _darwin_libc():
    library = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
    signatures = {
        "acl_get_fd": ([ctypes.c_int], ctypes.c_void_p),
        "acl_set_fd": ([ctypes.c_int, ctypes.c_void_p], ctypes.c_int),
        "acl_get_file": ([ctypes.c_char_p, ctypes.c_int], ctypes.c_void_p),
        "acl_set_file": (
            [ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p], ctypes.c_int,
        ),
        "acl_init": ([ctypes.c_int], ctypes.c_void_p),
        "acl_free": ([ctypes.c_void_p], ctypes.c_int),
        "acl_size": ([ctypes.c_void_p], ctypes.c_ssize_t),
        "acl_copy_ext": (
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ssize_t], ctypes.c_ssize_t,
        ),
        "acl_copy_int": ([ctypes.c_void_p], ctypes.c_void_p),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(library, name)
        function.argtypes = arguments
        function.restype = result
    return library


def _darwin_error() -> OSError:
    code = ctypes.get_errno() or errno.EIO
    return OSError(code, os.strerror(code))


def _read_darwin_acl(target: int | str) -> bytes | None:
    library = _darwin_libc()
    ctypes.set_errno(0)
    acl = (
        library.acl_get_fd(target) if isinstance(target, int)
        else library.acl_get_file(os.fsencode(target), 0x100)
    )
    if not acl:
        if ctypes.get_errno() == errno.ENOENT:
            return None
        raise _darwin_error()
    try:
        contents = _serialize_darwin_acl(acl)
        return None if contents == _empty_darwin_acl() else contents
    finally:
        library.acl_free(acl)


def _serialize_darwin_acl(acl) -> bytes:
    library = _darwin_libc()
    size = library.acl_size(acl)
    if size < 0:
        raise _darwin_error()
    buffer = ctypes.create_string_buffer(size)
    copied = library.acl_copy_ext(buffer, acl, size)
    if copied < 0:
        raise _darwin_error()
    return buffer.raw[:copied]


@lru_cache(maxsize=1)
def _empty_darwin_acl() -> bytes:
    library = _darwin_libc()
    acl = library.acl_init(0)
    if not acl:
        raise _darwin_error()
    try:
        return _serialize_darwin_acl(acl)
    finally:
        library.acl_free(acl)


def _set_darwin_acl(target: int | str, contents: bytes | None) -> None:
    library = _darwin_libc()
    buffer = ctypes.create_string_buffer(contents) if contents is not None else None
    acl = library.acl_copy_int(buffer) if buffer is not None else library.acl_init(0)
    if not acl:
        raise _darwin_error()
    try:
        result = (
            library.acl_set_fd(target, acl) if isinstance(target, int)
            else library.acl_set_file(os.fsencode(target), 0x100, acl)
        )
        if result != 0:
            raise _darwin_error()
    finally:
        library.acl_free(acl)


@lru_cache(maxsize=1)
def _windows_api():
    pointer = ctypes.c_void_p
    dword = ctypes.c_uint32
    boolean = ctypes.c_int32
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    signatures = {
        "GetFileSecurityW": (
            [ctypes.c_wchar_p, dword, pointer, dword, ctypes.POINTER(dword)], boolean,
        ),
        "GetKernelObjectSecurity": (
            [pointer, dword, pointer, dword, ctypes.POINTER(dword)], boolean,
        ),
        "SetFileSecurityW": ([ctypes.c_wchar_p, dword, pointer], boolean),
        "GetSecurityDescriptorDacl": (
            [pointer, ctypes.POINTER(boolean), ctypes.POINTER(pointer),
             ctypes.POINTER(boolean)], boolean,
        ),
        "GetSecurityDescriptorControl": (
            [pointer, ctypes.POINTER(ctypes.c_uint16), ctypes.POINTER(dword)], boolean,
        ),
        "GetSecurityDescriptorOwner": (
            [pointer, ctypes.POINTER(pointer), ctypes.POINTER(boolean)], boolean,
        ),
        "GetSecurityDescriptorGroup": (
            [pointer, ctypes.POINTER(pointer), ctypes.POINTER(boolean)], boolean,
        ),
        "GetLengthSid": ([pointer], dword),
        "GetAclInformation": ([pointer, pointer, dword, ctypes.c_int], boolean),
        "GetAce": ([pointer, dword, ctypes.POINTER(pointer)], boolean),
        "OpenProcessToken": ([pointer, dword, ctypes.POINTER(pointer)], boolean),
        "GetTokenInformation": (
            [pointer, ctypes.c_int, pointer, dword, ctypes.POINTER(dword)], boolean,
        ),
        "ConvertSidToStringSidW": ([pointer, ctypes.POINTER(pointer)], boolean),
        "ConvertStringSecurityDescriptorToSecurityDescriptorW": (
            [ctypes.c_wchar_p, dword, ctypes.POINTER(pointer), ctypes.POINTER(dword)],
            boolean,
        ),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(advapi, name)
        function.argtypes = arguments
        function.restype = result
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = pointer
    kernel.CloseHandle.argtypes = [pointer]
    kernel.CloseHandle.restype = boolean
    kernel.LocalFree.argtypes = [pointer]
    kernel.LocalFree.restype = pointer
    return advapi, kernel


def _windows_checked(result) -> None:
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())


def _read_windows_permissions(path: str, descriptor: int | None = None) -> bytes:
    advapi, _ = _windows_api()
    if descriptor is None:
        function, target = advapi.GetFileSecurityW, path
    else:
        import msvcrt
        function, target = advapi.GetKernelObjectSecurity, msvcrt.get_osfhandle(descriptor)
    needed = ctypes.c_uint32()
    result = function(target, 7, None, 0, ctypes.byref(needed))
    if result or ctypes.get_last_error() != 122 or not needed.value:
        raise ctypes.WinError(ctypes.get_last_error())
    buffer = ctypes.create_string_buffer(needed.value)
    _windows_checked(function(target, 7, buffer, len(buffer), ctypes.byref(needed)))
    return buffer.raw[:needed.value]


def _windows_acl_signature(contents: bytes, *, identity: bool = True):
    advapi, _ = _windows_api()
    buffer = ctypes.create_string_buffer(contents)
    control = ctypes.c_uint16()
    revision = ctypes.c_uint32()
    _windows_checked(advapi.GetSecurityDescriptorControl(
        buffer, ctypes.byref(control), ctypes.byref(revision),
    ))
    present, defaulted = ctypes.c_int32(), ctypes.c_int32()
    acl = ctypes.c_void_p()
    _windows_checked(advapi.GetSecurityDescriptorDacl(
        buffer, ctypes.byref(present), ctypes.byref(acl), ctypes.byref(defaulted),
    ))
    entries = None
    if present.value and acl.value:
        # Compare ACE bytes, not unused ACL allocation space or SD offsets.
        information = (ctypes.c_uint32 * 3)()
        _windows_checked(advapi.GetAclInformation(
            acl, information, ctypes.sizeof(information), 2,
        ))
        entries = []
        for index in range(information[0]):
            entry = ctypes.c_void_p()
            _windows_checked(advapi.GetAce(acl, index, ctypes.byref(entry)))
            size = ctypes.c_uint16.from_address(entry.value + 2).value
            entries.append(ctypes.string_at(entry, size))
        entries = tuple(entries)
    result = (bool(present.value), control.value & 0x1400, entries)
    if identity:
        for function in (advapi.GetSecurityDescriptorOwner, advapi.GetSecurityDescriptorGroup):
            sid = ctypes.c_void_p()
            _windows_checked(function(buffer, ctypes.byref(sid), ctypes.byref(defaulted)))
            result += (ctypes.string_at(sid, advapi.GetLengthSid(sid)) if sid else None,)
    return result


def _restore_windows_permissions(path: str, contents: bytes) -> None:
    advapi, _ = _windows_api()
    expected = _windows_acl_signature(contents)
    current = _windows_acl_signature(_read_windows_permissions(path))
    # OWNER/GROUP restoration may need rights the caller does not have. Never
    # enable privileges; an inability to preserve either identity aborts export.
    information = 4 | (0x80000000 if expected[1] & 0x1000 else 0x20000000)
    if current[3] != expected[3]:
        information |= 1
    if current[4] != expected[4]:
        information |= 2
    buffer = ctypes.create_string_buffer(contents)
    _windows_checked(advapi.SetFileSecurityW(path, information, buffer))
    if _windows_acl_signature(_read_windows_permissions(path)) != expected:
        raise OSError(errno.EPERM, "Restored Windows access permissions differ")


def _make_windows_staging_private(path: str) -> None:
    advapi, kernel = _windows_api()
    token = ctypes.c_void_p()
    _windows_checked(advapi.OpenProcessToken(
        kernel.GetCurrentProcess(), 8, ctypes.byref(token),
    ))
    try:
        needed = ctypes.c_uint32()
        result = advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(needed))
        if result or ctypes.get_last_error() != 122 or not needed.value:
            raise ctypes.WinError(ctypes.get_last_error())
        user = ctypes.create_string_buffer(needed.value)
        _windows_checked(advapi.GetTokenInformation(
            token, 1, user, len(user), ctypes.byref(needed),
        ))
        sid = ctypes.c_void_p.from_buffer(user)
        text = ctypes.c_void_p()
        _windows_checked(advapi.ConvertSidToStringSidW(sid, ctypes.byref(text)))
        try:
            sddl = f"D:P(A;OICI;FA;;;{ctypes.wstring_at(text)})"
        finally:
            kernel.LocalFree(text)
    finally:
        kernel.CloseHandle(token)
    descriptor = ctypes.c_void_p()
    size = ctypes.c_uint32()
    _windows_checked(advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        sddl, 1, ctypes.byref(descriptor), ctypes.byref(size),
    ))
    try:
        expected = _windows_acl_signature(ctypes.string_at(descriptor, size.value), identity=False)
        _windows_checked(advapi.SetFileSecurityW(path, 4 | 0x80000000, descriptor))
        actual = _windows_acl_signature(_read_windows_permissions(path), identity=False)
        # The kernel may mark auto-inheritance complete when setting a new DACL.
        if (actual[0], actual[1] & 0x1000, actual[2]) != (
            expected[0], expected[1] & 0x1000, expected[2],
        ):
            raise OSError(errno.EPERM, "Could not make staging directory private")
    finally:
        kernel.LocalFree(descriptor)
