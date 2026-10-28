"""Backend helpers for Mermaid Live Editor render/share state."""

from __future__ import annotations

import base64
import errno
import http.client
import json
import os
import secrets
import stat
import sys
import urllib.error
import urllib.request
import zlib


RENDER_BASE = os.environ.get("MERMAID_RENDERER_URL", "https://mermaid.ink").rstrip("/")
LIVE_BASE = os.environ.get("MERMAID_LIVE_URL", "https://mermaid.live").rstrip("/")


def serialize_state(state: dict) -> str:
    payload = json.dumps(state, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(payload, level=9)
    encoded = base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")
    return f"pako:{encoded}"


def build_render_url(serialized: str, fmt: str) -> str:
    if fmt == "svg":
        return f"{RENDER_BASE}/svg/{serialized}"
    if fmt == "png":
        return f"{RENDER_BASE}/img/{serialized}?type=png"
    raise ValueError(f"Unsupported format: {fmt}")


def build_live_url(serialized: str, mode: str) -> str:
    if mode not in {"edit", "view"}:
        raise ValueError(f"Unsupported share mode: {mode}")
    return f"{LIVE_BASE}/{mode}#{serialized}"



def _validate_output_path_shape(path: str) -> None:
    """Reject directory syntax before realpath can erase it, also through links."""
    seen = set()
    while True:
        normalized_separators = path.replace(os.altsep, os.sep) if os.altsep else path
        if normalized_separators.split(os.sep)[-1] in {"", ".", ".."}:
            raise OSError("Output path denotes a directory")
        # Only follow the terminal entry: a parent link to "directory/." is
        # valid when the caller still names a file underneath that directory.
        path = os.path.join(os.path.realpath(os.path.dirname(path)), os.path.basename(path))
        if not os.path.islink(path):
            return
        if path in seen:
            raise OSError("Output path contains a symlink loop")
        seen.add(path)
        target = os.readlink(path)
        path = target if os.path.isabs(target) else os.path.join(os.path.dirname(path), target)


def _capture_output_links(path: str) -> dict[str, tuple]:
    """Record named symlink entries, including links in their target paths."""
    references = {}
    pending = [path]
    expanded = set()
    while pending:
        candidate = pending.pop()
        drive, tail = os.path.splitdrive(candidate)
        if os.altsep:
            tail = tail.replace(os.altsep, os.sep)
        cursor = drive + os.sep if tail.startswith(os.sep) else drive
        for component in tail.split(os.sep):
            if not component:
                continue
            if component in {".", ".."}:
                # A lexical collapse must not erase a missing/non-directory
                # traversal component, including in a dangling link target.
                if not stat.S_ISDIR(os.stat(cursor).st_mode):
                    raise OSError("Output traversal component is not a directory")
            cursor = os.path.join(cursor, component)
            try:
                entry = os.lstat(cursor)
            except FileNotFoundError:
                continue
            if not stat.S_ISLNK(entry.st_mode):
                continue
            target = os.readlink(cursor)
            reference = (entry.st_dev, entry.st_ino, entry.st_ctime_ns, target)
            if cursor in references and references[cursor] != reference:
                raise OSError("Requested output path changed while inspecting links")
            references[cursor] = reference
            identity = (entry.st_dev, entry.st_ino, os.path.realpath(os.path.dirname(cursor)))
            if identity not in expanded:
                expanded.add(identity)
                pending.append(target if os.path.isabs(target) else os.path.join(os.path.dirname(cursor), target))
    return references


def _revalidate_output_path(path: str, destination: str, links: dict[str, tuple]) -> None:
    """Refuse known link rotations; the final check/rename is not atomic CAS."""
    try:
        # Repeat traversal validation before realpath can hide a directory
        # removed during the renderer wait or staging/metadata work.
        current_links = _capture_output_links(path)
    except OSError as exc:
        raise OSError("Requested output path changed while rendering") from exc
    if current_links != links or os.path.realpath(path) != destination:
        raise OSError("Requested output path changed while rendering")


def _read_destination(path: str) -> os.stat_result | None:
    try:
        current = os.lstat(path)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(current.st_mode):
        raise OSError("Output destination is not a regular file")
    if current.st_nlink != 1:
        raise OSError("Refusing hard-linked output: replacing one name would leave aliases unchanged")
    return current


def _refresh_destination(path: str, previous: os.stat_result | None) -> os.stat_result | None:
    """Detect a replaced/created destination; re-read access controls after waits.

    This is a best-effort check, not an atomic compare-and-swap with rename.
    """
    current = _read_destination(path)
    if (current is None) != (previous is None) or (
        current is not None and previous is not None
        and (current.st_dev, current.st_ino) != (previous.st_dev, previous.st_ino)
    ):
        raise OSError("Output destination identity changed while rendering")
    return current


def _metadata_version(value: os.stat_result) -> tuple:
    return (value.st_mode, value.st_uid, value.st_gid, value.st_mtime_ns, value.st_ctime_ns)


def _set_macos_acl(source: int | None, staged: int) -> None:
    """Copy the exact ACL, or install an empty ACL for private staging."""
    import ctypes
    native = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
    native.acl_init.argtypes = [ctypes.c_int]
    native.acl_init.restype = ctypes.c_void_p
    native.acl_get_fd_np.argtypes = [ctypes.c_int, ctypes.c_int]
    native.acl_get_fd_np.restype = ctypes.c_void_p
    native.acl_set_fd_np.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
    native.acl_set_fd_np.restype = ctypes.c_int
    native.acl_free.argtypes = [ctypes.c_void_p]
    native.acl_free.restype = ctypes.c_int
    # sys/acl.h: ACL_TYPE_EXTENDED = 0x00000100.
    acl = native.acl_get_fd_np(source, 0x100) if source is not None else native.acl_init(0)
    if not acl and source is not None and ctypes.get_errno() == errno.ENOENT:
        # macOS also returns ENOENT for an existing file with no extended ACL.
        # Require the entry to exist; the caller revalidates its identity later.
        os.fstat(source)
        acl = native.acl_init(0)
    if not acl:
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number))
    try:
        if native.acl_set_fd_np(staged, acl, 0x100) != 0:
            number = ctypes.get_errno()
            raise OSError(number, os.strerror(number))
    finally:
        native.acl_free(acl)


def _make_staging_private(path: int) -> None:
    """Remove inherited reader ACLs before any overwrite content is written."""
    if sys.platform == "darwin":
        _set_macos_acl(None, path)
    elif sys.platform.startswith("linux"):
        if "system.posix_acl_access" in os.listxattr(path):
            os.removexattr(path, "system.posix_acl_access")
    else:
        raise OSError("Private overwrite staging is supported only on macOS and Linux")
    os.chmod(path, 0o600)


def _preserve_destination_metadata(source: str, staged: int, original: os.stat_result) -> None:
    """Keep ordinary access controls, excluding executable-content privileges."""
    current = os.fstat(staged)
    if (current.st_uid, current.st_gid) != (original.st_uid, original.st_gid):
        os.chown(staged, original.st_uid, original.st_gid)
    ordinary_mode = stat.S_IMODE(original.st_mode) & ~(stat.S_ISUID | stat.S_ISGID)
    if sys.platform == "darwin":
        # copyfile.h: COPYFILE_XATTR (1<<2). Copy ACLs explicitly because
        # copyfile merges inherited ACL entries instead of copying them exactly.
        # Python's os xattr APIs are Linux-only; use macOS's metadata copier.
        import ctypes
        native = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        copyfile = native.fcopyfile
        copyfile.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        copyfile.restype = ctypes.c_int
        source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            if copyfile(source_fd, staged, None, 4) != 0:
                number = ctypes.get_errno()
                raise OSError(number, os.strerror(number))
            _set_macos_acl(source_fd, staged)
        finally:
            os.close(source_fd)
    elif sys.platform.startswith("linux"):
        # Linux stores POSIX ACLs and security labels in extended attributes.
        # Unlike shutil.copystat, do not silently ignore access-control errors.
        attributes = {
            name: os.getxattr(source, name) for name in os.listxattr(source)
            # Privileges and integrity attestations bind the previous bytes/inode.
            if name not in {"security.capability", "security.ima", "security.evm"}
        }
        for name in os.listxattr(staged):
            if name not in attributes:
                os.removexattr(staged, name)
        for name, value in attributes.items():
            os.setxattr(staged, name, value)
    else:
        raise OSError("Preserving overwrite access controls is supported only on macOS and Linux")
    # Do not widen the private stage's mode until its destination ACL is in place.
    os.chmod(staged, ordinary_mode)
    if sys.platform.startswith("linux"):
        if {name: os.getxattr(staged, name) for name in os.listxattr(staged)} != attributes:
            raise OSError("Could not preserve destination extended attributes")
    after = os.fstat(staged)
    if (after.st_uid, after.st_gid, stat.S_IMODE(after.st_mode)) != (
        original.st_uid, original.st_gid, ordinary_mode
    ):
        raise OSError("Could not preserve destination ownership and mode")


def _staging_entry_matches(path: str, descriptor: int) -> bool:
    """The descriptor pins our inode; the name may have been replaced."""
    try:
        named = os.lstat(path)
        opened = os.fstat(descriptor)
    except OSError:
        return False
    return (stat.S_ISREG(named.st_mode) and opened.st_nlink == 1
            and (named.st_dev, named.st_ino) == (opened.st_dev, opened.st_ino))


def _validate_staging_entry(path: str, descriptor: int) -> None:
    if not _staging_entry_matches(path, descriptor):
        raise OSError("Staging output identity changed while rendering")


def _windows_set_handle_readonly(handle: int, readonly: bool, attributes: int) -> None:
    """Change only READONLY on the pinned handle, retaining other attributes."""
    import ctypes
    class BasicInfo(ctypes.Structure):
        _fields_ = [("CreationTime", ctypes.c_int64), ("LastAccessTime", ctypes.c_int64),
                    ("LastWriteTime", ctypes.c_int64), ("ChangeTime", ctypes.c_int64),
                    ("FileAttributes", ctypes.c_uint32)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    set_info = kernel.SetFileInformationByHandle
    set_info.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    set_info.restype = ctypes.c_int
    changed = BasicInfo()  # Zero times leave timestamps unchanged.
    changed.FileAttributes = ((attributes | 1) if readonly else (attributes & ~1)) or 0x80
    if not set_info(handle, 0, ctypes.byref(changed), ctypes.sizeof(changed)):
        raise ctypes.WinError()


def _windows_set_readonly(descriptor: int, readonly: bool) -> None:
    import msvcrt
    # CPython fstat obtains attributes without requiring FILE_READ_ATTRIBUTES
    # on the CRT's write handle; FileBasicInfo queries require that extra right.
    attributes = os.fstat(descriptor).st_file_attributes
    _windows_set_handle_readonly(msvcrt.get_osfhandle(descriptor), readonly, attributes)


def _open_staging_file(path: str, mode: int) -> int:
    if sys.platform != "win32":
        return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)

    # Let the CRT apply its own current umask, without reading/changing the
    # process-global mask. ReOpenFile changes sharing on this same pinned inode.
    import ctypes
    import msvcrt
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    reopen = kernel.ReOpenFile
    reopen.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32]
    reopen.restype = ctypes.c_void_p
    close = kernel.CloseHandle
    close.argtypes = [ctypes.c_void_p]
    close.restype = ctypes.c_int
    initial_fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    original = os.fstat(initial_fd)
    readonly = not bool(original.st_mode & stat.S_IWRITE)
    handle = None
    adopted_fd = None
    try:
        if readonly:
            _windows_set_readonly(initial_fd, False)
        # Do not request DELETE while the initial CRT handle still denies it.
        # READ/WRITE sharing must coexist with that original handle's access.
        handle = reopen(msvcrt.get_osfhandle(initial_fd), 0x40000000, 7, 0)
        if handle == ctypes.c_void_p(-1).value:
            handle = None
            raise ctypes.WinError()
        adopted_fd = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY | os.O_NOINHERIT)
        handle = None  # The new CRT descriptor now owns it.
        os.close(initial_fd)
        initial_fd = None
        if readonly:
            _windows_set_readonly(adopted_fd, True)
        return adopted_fd
    except BaseException:
        # Reopening/adoption/restoration failed before the caller owned the
        # stage. Close the original delete-denying descriptor first; compare
        # inode identity before best-effort named cleanup. A reopened handle,
        # when present, still pins that inode until cleanup has finished.
        if initial_fd is not None:
            os.close(initial_fd)
        try:
            if adopted_fd is not None:
                _windows_set_readonly(adopted_fd, False)
            named = os.lstat(path)
            if (stat.S_ISREG(named.st_mode)
                    and (named.st_dev, named.st_ino) == (original.st_dev, original.st_ino)):
                os.unlink(path)
        except OSError:
            pass
        finally:
            if adopted_fd is not None:
                os.close(adopted_fd)
            elif handle is not None:
                close(handle)
        raise


def render_to_file(serialized: str, output_path: str, fmt: str, *, overwrite: bool = True) -> dict:
    output_path = os.fspath(output_path)
    separators = tuple(separator for separator in (os.sep, os.altsep) if separator)
    if output_path.endswith(separators):
        raise RuntimeError(f"Could not write {output_path}: output path denotes a directory")
    try:
        requested_path = output_path if os.path.isabs(output_path) else os.path.join(os.getcwd(), output_path)
        _validate_output_path_shape(requested_path)
        output_links = _capture_output_links(requested_path)
        destination_path = os.path.realpath(requested_path)
        _revalidate_output_path(requested_path, destination_path, output_links)
        original = _read_destination(destination_path)
        if original is not None and not overwrite:
            raise FileExistsError(f"Output already exists: {output_path}")
        if original is not None and not (sys.platform == "darwin" or sys.platform.startswith("linux")):
            raise OSError("Preserving overwrite access controls is supported only on macOS and Linux")
    except OSError as exc:
        raise RuntimeError(f"Could not write {output_path}: {exc}") from exc
    url = build_render_url(serialized, fmt)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"Renderer returned HTTP {exc.code} for {fmt} output "
            "(check the diagram syntax)"
        ) from exc
    except http.client.HTTPException as exc:
        raise RuntimeError(f"Could not read renderer response: {exc}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise RuntimeError(f"Could not reach renderer {RENDER_BASE}: {exc}") from exc
    temporary_path = None
    pending_fd = None
    try:
        # The network wait may outlive a link rotation or destination change.
        _revalidate_output_path(requested_path, destination_path, output_links)
        original = _refresh_destination(destination_path, original)
        parent = os.path.dirname(destination_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        candidate_path = os.path.join(parent, f".mermaid-{secrets.token_hex(16)}")
        creation_mode = 0o600 if original is not None else 0o666
        pending_fd = _open_staging_file(candidate_path, creation_mode)
        temporary_path = candidate_path  # Cleanup only a file we created successfully.
        if original is not None:
            _make_staging_private(pending_fd)
        # Keep the inode pinned through metadata, publication and cleanup.
        output_file = os.fdopen(pending_fd, "wb", closefd=False)
        with output_file as fh:
            if fh.write(data) != len(data):
                raise OSError("Incomplete renderer output write")
        _validate_staging_entry(temporary_path, pending_fd)
        file_size = os.fstat(pending_fd).st_size
        if file_size != len(data):
            raise OSError("Incomplete renderer output file")
        # Re-read once more after staging, so a known newer access-control
        # choice is preserved rather than restoring the pre-write snapshot.
        _revalidate_output_path(requested_path, destination_path, output_links)
        original = _refresh_destination(destination_path, original)
        if original is not None:
            _preserve_destination_metadata(destination_path, pending_fd, original)
        current = _refresh_destination(destination_path, original)
        if current is not None and _metadata_version(current) != _metadata_version(original):
            raise OSError("Output destination metadata changed while staging")
        _revalidate_output_path(requested_path, destination_path, output_links)
        _validate_staging_entry(temporary_path, pending_fd)
        os.replace(temporary_path, destination_path)
        temporary_path = None  # Publication releases ownership of the staging name.
    except OSError as exc:
        raise RuntimeError(f"Could not write {output_path}: {exc}") from exc
    finally:
        # Best-effort cleanup must not hide the original write error.
        if temporary_path is not None and pending_fd is not None:
            if _staging_entry_matches(temporary_path, pending_fd):
                try:
                    if sys.platform == "win32":
                        _windows_set_readonly(pending_fd, False)
                    os.unlink(temporary_path)
                except OSError:
                    pass
        if pending_fd is not None:
            try:
                os.close(pending_fd)
            except OSError:
                pass
    return {
        "output": os.path.abspath(output_path),
        "format": fmt,
        "method": "mermaid-renderer",
        "file_size": file_size,
        "url": url,
    }
