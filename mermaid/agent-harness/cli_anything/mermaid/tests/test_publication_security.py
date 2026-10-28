"""Filesystem publication controls over real loopback renderer requests."""

import http.server
import os
import stat
import sys
import threading

import pytest

from cli_anything.mermaid.utils import mermaid_backend


def _preserve_metadata_with_descriptor(source, staged, attributes):
    # Linux xattr emulation follows the same FD-based API used in production.
    with open(staged, "rb") as file:
        attributes[str(file.fileno())] = attributes[str(staged)]
        mermaid_backend._preserve_destination_metadata(str(source), file.fileno(), source.stat())


def _macos_acl_bytes(path):
    """Compare UUID-based ACL data without transient name-service formatting."""
    import ctypes
    native = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
    native.acl_get_file.argtypes = [ctypes.c_char_p, ctypes.c_int]
    native.acl_get_file.restype = ctypes.c_void_p
    native.acl_size.argtypes = [ctypes.c_void_p]
    native.acl_size.restype = ctypes.c_ssize_t
    native.acl_copy_ext.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ssize_t]
    native.acl_copy_ext.restype = ctypes.c_ssize_t
    native.acl_free.argtypes = [ctypes.c_void_p]
    native.acl_free.restype = ctypes.c_int
    acl = native.acl_get_file(os.fsencode(path), 0x100)
    if not acl:
        raise OSError(ctypes.get_errno(), "Cannot read fixture ACL")
    try:
        size = native.acl_size(acl)
        if size < 0:
            raise OSError(ctypes.get_errno(), "Cannot size fixture ACL")
        buffer = ctypes.create_string_buffer(size)
        written = native.acl_copy_ext(buffer, acl, size)
        if written < 0:
            raise OSError(ctypes.get_errno(), "Cannot serialize fixture ACL")
        return buffer.raw[:written]
    finally:
        native.acl_free(acl)


SUPPORTED = sys.platform == "darwin" or sys.platform.startswith("linux")
pytestmark = pytest.mark.skipif(not SUPPORTED, reason="native overwrite metadata profile")


@pytest.fixture
def renderer(monkeypatch):
    servers = []

    def start(during_request=lambda: None, declared_length=None):
        calls = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append(self.path)
                during_request()
                data = b"<svg>new render</svg>"
                self.send_response(200)
                self.send_header("Content-Length", str(len(data) if declared_length is None else declared_length))
                self.end_headers()
                self.wfile.write(data)
                self.close_connection = True

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        monkeypatch.setattr(mermaid_backend, "RENDER_BASE", f"http://127.0.0.1:{server.server_port}")
        return calls

    yield start
    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


def test_chmod_during_renderer_request_preserves_tightened_mode(renderer, tmp_path):
    target = tmp_path / "out.svg"
    target.write_bytes(b"original")
    target.chmod(0o644)
    calls = renderer(lambda: target.chmod(0o600))
    mermaid_backend.render_to_file("pako:x", str(target), "svg")
    assert calls
    assert target.read_bytes() == b"<svg>new render</svg>"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".mermaid-*"))


def test_replaced_inode_during_renderer_request_is_not_overwritten(renderer, tmp_path):
    target = tmp_path / "out.svg"
    target.write_bytes(b"original")
    previous = tmp_path / "previous.svg"

    def replace():
        target.rename(previous)
        target.write_bytes(b"another writer")

    calls = renderer(replace)
    with pytest.raises(RuntimeError, match="identity changed"):
        mermaid_backend.render_to_file("pako:x", str(target), "svg")
    assert calls
    assert previous.read_bytes() == b"original"
    assert target.read_bytes() == b"another writer"
    assert not list(tmp_path.glob(".mermaid-*"))


def test_destination_created_during_renderer_request_is_not_overwritten(renderer, tmp_path):
    target = tmp_path / "out.svg"
    renderer(lambda: target.write_bytes(b"another writer"))
    with pytest.raises(RuntimeError, match="identity changed"):
        mermaid_backend.render_to_file("pako:x", str(target), "svg")
    assert target.read_bytes() == b"another writer"
    assert not list(tmp_path.glob(".mermaid-*"))


@pytest.mark.parametrize("when", ["before", "during_fetch"])
def test_hard_linked_output_is_explicitly_refused(renderer, tmp_path, when):
    target = tmp_path / "out.svg"
    alias = tmp_path / "alias.svg"
    target.write_bytes(b"original")
    if when == "before":
        os.link(target, alias)
        calls = renderer()
    else:
        calls = renderer(lambda: os.link(target, alias))
    with pytest.raises(RuntimeError, match="hard.link"):
        mermaid_backend.render_to_file("pako:x", str(target), "svg")
    assert bool(calls) is (when == "during_fetch")
    assert target.read_bytes() == alias.read_bytes() == b"original"
    assert target.stat().st_ino == alias.stat().st_ino
    assert target.stat().st_nlink == 2
    assert not list(tmp_path.glob(".mermaid-*"))


@pytest.mark.parametrize("mode", [0o4755, 0o2750, 0o6750])
def test_new_render_bytes_do_not_inherit_setid_privileges(renderer, tmp_path, mode):
    target = tmp_path / "out.svg"
    target.write_bytes(b"original")
    target.chmod(mode)
    if stat.S_IMODE(target.stat().st_mode) != mode:
        pytest.skip("filesystem does not retain the requested set-ID fixture mode")
    renderer()
    mermaid_backend.render_to_file("pako:x", str(target), "svg")
    assert target.read_bytes() == b"<svg>new render</svg>"
    assert stat.S_IMODE(target.stat().st_mode) == mode & ~(stat.S_ISUID | stat.S_ISGID)


@pytest.mark.parametrize("change", ["chmod", "replace", "hard_link"])
def test_change_while_staging_is_detected_before_publication(monkeypatch, renderer, tmp_path, change):
    target = tmp_path / "out.svg"
    target.write_bytes(b"original")
    target.chmod(0o644)
    renderer()
    real_fdopen = os.fdopen

    class Writer:
        def __init__(self, file):
            self.file = file
        def __enter__(self):
            self.file.__enter__()
            return self
        def __exit__(self, *args):
            return self.file.__exit__(*args)
        def write(self, data):
            written = self.file.write(data)
            if change == "chmod":
                target.chmod(0o600)
            elif change == "replace":
                target.rename(tmp_path / "previous.svg")
                target.write_bytes(b"another writer")
            else:
                os.link(target, tmp_path / "alias.svg")
            return written

    monkeypatch.setattr(os, "fdopen", lambda fd, *args, **kwargs: Writer(real_fdopen(fd, *args, **kwargs)))
    if change == "chmod":
        mermaid_backend.render_to_file("pako:x", str(target), "svg")
        assert stat.S_IMODE(target.stat().st_mode) == 0o600
        assert target.read_bytes() == b"<svg>new render</svg>"
    else:
        with pytest.raises(RuntimeError, match="identity changed|hard.link"):
            mermaid_backend.render_to_file("pako:x", str(target), "svg")
        assert target.read_bytes() == (b"another writer" if change == "replace" else b"original")
    assert not list(tmp_path.glob(".mermaid-*"))


def test_linux_attribute_copy_excludes_file_capabilities_but_keeps_labels(monkeypatch, tmp_path):
    """Linux xattr branch emulation; not a native Linux capability qualification."""
    target = tmp_path / "out.svg"
    staged = tmp_path / "stage.svg"
    target.write_bytes(b"original")
    staged.write_bytes(b"new render")
    attributes = {
        str(target): {"security.capability": b"source-privilege", "security.selinux": b"label", "system.posix_acl_access": b"acl"},
        str(staged): {"security.capability": b"inherited-privilege"},
    }
    monkeypatch.setattr(mermaid_backend.sys, "platform", "linux")
    monkeypatch.setattr(os, "listxattr", lambda path: list(attributes[str(path)]), raising=False)
    monkeypatch.setattr(os, "getxattr", lambda path, name: attributes[str(path)][name], raising=False)
    monkeypatch.setattr(os, "setxattr", lambda path, name, value: attributes[str(path)].__setitem__(name, value), raising=False)
    monkeypatch.setattr(os, "removexattr", lambda path, name: attributes[str(path)].pop(name), raising=False)
    _preserve_metadata_with_descriptor(target, staged, attributes)
    assert attributes[str(staged)] == {"security.selinux": b"label", "system.posix_acl_access": b"acl"}
    assert attributes[str(target)]["security.capability"] == b"source-privilege"


def test_access_control_change_during_final_metadata_copy_aborts(monkeypatch, renderer, tmp_path):
    target = tmp_path / "out.svg"
    target.write_bytes(b"original")
    target.chmod(0o644)
    renderer()
    preserve = mermaid_backend._preserve_destination_metadata
    calls = []

    def change_after_copy(*args):
        preserve(*args)
        calls.append(True)
        target.chmod(0o600)

    monkeypatch.setattr(mermaid_backend, "_preserve_destination_metadata", change_after_copy)
    with pytest.raises(RuntimeError, match="metadata changed"):
        mermaid_backend.render_to_file("pako:x", str(target), "svg")
    assert target.read_bytes() == b"original"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".mermaid-*"))


def test_deleted_destination_during_renderer_request_is_not_recreated(renderer, tmp_path):
    target = tmp_path / "out.svg"
    target.write_bytes(b"original")
    renderer(target.unlink)
    with pytest.raises(RuntimeError, match="identity changed"):
        mermaid_backend.render_to_file("pako:x", str(target), "svg")
    assert not target.exists()
    assert not list(tmp_path.glob(".mermaid-*"))


def test_same_inode_reached_through_new_symlink_is_not_published_over(renderer, tmp_path):
    target = tmp_path / "out.svg"
    previous = tmp_path / "previous.svg"
    target.write_bytes(b"original")

    def change_entry():
        target.rename(previous)
        target.symlink_to(previous.name)

    renderer(change_entry)
    with pytest.raises(RuntimeError, match="Requested output path changed"):
        mermaid_backend.render_to_file("pako:x", str(target), "svg")
    assert target.is_symlink()
    assert target.read_bytes() == previous.read_bytes() == b"original"
    assert not list(tmp_path.glob(".mermaid-*"))


@pytest.mark.skipif(sys.platform != "darwin", reason="native macOS inherited ACL fixture")
def test_overwrite_stage_is_private_until_all_bytes_are_written(monkeypatch, renderer, tmp_path):
    import subprocess
    parent = tmp_path / "outputs"
    parent.mkdir()
    subprocess.run(["/bin/chmod", "+a", "everyone allow read,file_inherit", str(parent)], check=True)
    target = parent / "out.svg"
    target.write_bytes(b"original")
    target.chmod(0o644)
    assert subprocess.check_output(["/bin/ls", "-le", str(target)], text=True).splitlines()[1:], "fixture must inherit a real extended ACL"
    original_acl = _macos_acl_bytes(target)
    renderer()
    real_fdopen = os.fdopen
    observations = []

    class Writer:
        def __init__(self, file):
            self.file = file
        def __enter__(self):
            self.file.__enter__()
            return self
        def __exit__(self, *args):
            return self.file.__exit__(*args)
        def write(self, data):
            written = self.file.write(data)
            self.file.flush()
            staged = next(parent.glob(".mermaid-*"))
            observations.append((stat.S_IMODE(staged.stat().st_mode),
                subprocess.check_output(["/bin/ls", "-le", str(staged)], text=True).splitlines()[1:]))
            return written

    monkeypatch.setattr(os, "fdopen", lambda fd, *args, **kwargs: Writer(real_fdopen(fd, *args, **kwargs)))
    mermaid_backend.render_to_file("pako:x", str(target), "svg")
    assert observations == [(0o600, [])]
    assert _macos_acl_bytes(target) == original_acl
    assert target.read_bytes() == b"<svg>new render</svg>"


@pytest.mark.skipif(sys.platform != "darwin", reason="native macOS ACL ordering")
def test_target_acl_is_installed_before_stage_mode_is_widened(monkeypatch, renderer, tmp_path):
    import subprocess
    target = tmp_path / "out.svg"
    target.write_bytes(b"original")
    target.chmod(0o644)
    subprocess.run(["/bin/chmod", "+a", "user:nobody deny read", str(target)], check=True)
    assert subprocess.check_output(["/bin/ls", "-le", str(target)], text=True).splitlines()[1:]
    expected_acl = _macos_acl_bytes(target)
    renderer()
    chmod = os.chmod
    widened = []

    def check_before_widening(path, mode):
        if mode == 0o644 and (isinstance(path, int) or ".mermaid-" in str(path)):
            staged = next(tmp_path.glob(".mermaid-*"))
            if isinstance(path, int):
                assert os.fstat(path).st_ino == staged.stat().st_ino
            observed = _macos_acl_bytes(staged)
            assert observed == expected_acl
            widened.append(True)
        return chmod(path, mode)

    monkeypatch.setattr(os, "chmod", check_before_widening)
    mermaid_backend.render_to_file("pako:x", str(target), "svg")
    assert widened == [True]
    assert stat.S_IMODE(target.stat().st_mode) == 0o644
    assert _macos_acl_bytes(target) == expected_acl


@pytest.mark.parametrize("phase", ["fetch", "staging", "metadata"])
@pytest.mark.parametrize("rotation", ["retarget", "remove", "same_target"])
def test_output_symlink_rotation_refuses_stale_target(monkeypatch, renderer, tmp_path, phase, rotation):
    first = tmp_path / "a.svg"
    second = tmp_path / "b.svg"
    output = tmp_path / "current.svg"
    first.write_bytes(b"first original")
    second.write_bytes(b"second original")
    output.symlink_to(first.name)
    changes = []

    def rotate():
        if changes:
            return
        changes.append(True)
        # Keep the old entry alive for an unambiguous replacement identity.
        output.rename(tmp_path / "previous-link.svg")
        if rotation != "remove":
            output.symlink_to(second.name if rotation == "retarget" else first.name)

    renderer(rotate if phase == "fetch" else lambda: None)
    if phase == "staging":
        fdopen = os.fdopen
        class Writer:
            def __init__(self, file): self.file = file
            def __enter__(self):
                self.file.__enter__()
                return self
            def __exit__(self, *args): return self.file.__exit__(*args)
            def write(self, data):
                written = self.file.write(data)
                rotate()
                return written
        monkeypatch.setattr(os, "fdopen", lambda fd, *a, **k: Writer(fdopen(fd, *a, **k)))
    elif phase == "metadata":
        preserve = mermaid_backend._preserve_destination_metadata
        def change_after_metadata(*args):
            preserve(*args)
            rotate()
        monkeypatch.setattr(mermaid_backend, "_preserve_destination_metadata", change_after_metadata)
    with pytest.raises(RuntimeError, match="output path changed"):
        mermaid_backend.render_to_file("pako:x", str(output), "svg")
    assert changes
    assert first.read_bytes() == b"first original"
    assert second.read_bytes() == b"second original"
    if rotation == "remove":
        assert not output.exists() and not output.is_symlink()
    else:
        assert output.is_symlink()
        assert os.readlink(output) == (second.name if rotation == "retarget" else first.name)
    assert not list(tmp_path.glob(".mermaid-*"))


@pytest.mark.parametrize("same_target", [False, True])
def test_output_link_chain_rotation_is_revalidated(renderer, tmp_path, same_target):
    first = tmp_path / "a.svg"
    second = tmp_path / "b.svg"
    first.write_bytes(b"first original")
    second.write_bytes(b"second original")
    pivot = tmp_path / "release-link.svg"
    pivot.symlink_to(first.name)
    output = tmp_path / "current.svg"
    output.symlink_to(pivot.name)

    def rotate():
        pivot.rename(tmp_path / "previous-release-link.svg")
        pivot.symlink_to(first.name if same_target else second.name)

    renderer(rotate)
    with pytest.raises(RuntimeError, match="output path changed"):
        mermaid_backend.render_to_file("pako:x", str(output), "svg")
    assert output.is_symlink() and pivot.is_symlink()
    assert first.read_bytes() == b"first original"
    assert second.read_bytes() == b"second original"
    assert not list(tmp_path.glob(".mermaid-*"))


def test_linux_content_integrity_metadata_is_not_rebound_to_render_bytes(monkeypatch, tmp_path):
    """Explicit Linux branch emulation, not native IMA/EVM appraisal coverage."""
    source = tmp_path / "out.svg"
    staged = tmp_path / "stage.svg"
    source.write_bytes(b"old bytes")
    staged.write_bytes(b"new bytes")
    content_bound = {"security.ima": b"old-content-signature", "security.evm": b"old-inode-hmac", "security.capability": b"old-privilege"}
    ordinary = {"security.selinux": b"label", "system.posix_acl_access": b"acl", "user.note": b"annotation"}
    attributes = {str(source): dict(content_bound, **ordinary), str(staged): dict(content_bound)}
    monkeypatch.setattr(mermaid_backend.sys, "platform", "linux")
    monkeypatch.setattr(os, "listxattr", lambda path: list(attributes[str(path)]), raising=False)
    monkeypatch.setattr(os, "getxattr", lambda path, name: attributes[str(path)][name], raising=False)
    monkeypatch.setattr(os, "setxattr", lambda path, name, value: attributes[str(path)].__setitem__(name, value), raising=False)
    monkeypatch.setattr(os, "removexattr", lambda path, name: attributes[str(path)].pop(name), raising=False)
    _preserve_metadata_with_descriptor(source, staged, attributes)
    assert attributes[str(staged)] == ordinary
    assert attributes[str(source)] == dict(content_bound, **ordinary)


@pytest.mark.parametrize("suffix", ["/", "/.", "/..", "/./."])
@pytest.mark.parametrize("links", [0, 1, 2])
def test_directory_shaped_outputs_are_rejected_before_normalizing(renderer, tmp_path, suffix, links):
    missing = tmp_path / "missing"
    output = str(missing) + suffix
    for index in range(links):
        link = tmp_path / f"link-{index}.svg"
        link.symlink_to(output)
        output = str(link)
    calls = renderer()
    with pytest.raises(RuntimeError, match="directory"):
        mermaid_backend.render_to_file("pako:x", output, "svg")
    assert not calls
    assert not missing.exists()
    assert not list(tmp_path.glob(".mermaid-*"))
    for index in range(links):
        assert (tmp_path / f"link-{index}.svg").is_symlink()


def test_parent_directory_link_with_dot_target_still_allows_output(renderer, tmp_path):
    directory = tmp_path / "artifacts"
    directory.mkdir()
    link = tmp_path / "parent"
    link.symlink_to(str(directory) + "/.")
    calls = renderer()
    mermaid_backend.render_to_file("pako:x", str(link / "output.svg"), "svg")
    assert calls
    assert (directory / "output.svg").read_bytes() == b"<svg>new render</svg>"
    assert link.is_symlink()


@pytest.mark.parametrize("existing", [False, True])
def test_truncated_http_response_is_a_clean_cli_error(renderer, tmp_path, existing):
    from click.testing import CliRunner
    from cli_anything.mermaid.mermaid_cli import cli

    output = tmp_path / "output.svg"
    if existing:
        output.write_bytes(b"original")
    project = tmp_path / "project.json"
    runner = CliRunner()
    created = runner.invoke(cli, ["project", "new", "-o", str(project)])
    assert created.exit_code == 0, created.output
    calls = renderer(declared_length=1000)
    result = runner.invoke(cli, ["--project", str(project), "export", "render", str(output), "--overwrite"])
    assert calls
    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "renderer" in result.output.lower()
    assert "Traceback" not in result.output
    if existing:
        assert output.read_bytes() == b"original"
    else:
        assert not output.exists()
    assert not list(tmp_path.glob(".mermaid-*"))


@pytest.mark.parametrize("existing", [False, True])
def test_successful_publication_releases_staging_name_ownership(monkeypatch, renderer, tmp_path, existing):
    target = tmp_path / "output.svg"
    if existing:
        target.write_bytes(b"original")
    real_replace = os.replace
    unrelated = []

    def publish_then_reuse_name(source, destination):
        real_replace(source, destination)
        # Another process can now exclusively create this vacated name.
        with open(source, "xb") as fh:
            fh.write(b"another writer")
        unrelated.append(source)

    monkeypatch.setattr(os, "replace", publish_then_reuse_name)
    renderer()
    mermaid_backend.render_to_file("pako:x", str(target), "svg")
    assert target.read_bytes() == b"<svg>new render</svg>"
    assert len(unrelated) == 1
    with open(unrelated[0], "rb") as fh:
        assert fh.read() == b"another writer"


@pytest.mark.parametrize("dot", [".", ".."])
@pytest.mark.parametrize("links", [0, 1, 2])
def test_missing_traversal_is_rejected_without_overwriting(renderer, tmp_path, dot, links):
    from click.testing import CliRunner
    from cli_anything.mermaid.mermaid_cli import cli

    target = tmp_path / "out.svg"
    target.write_bytes(b"original")
    output = str(tmp_path / "missing") + f"/{dot}/"
    output += "../out.svg" if dot == "." else "out.svg"
    for index in range(links):
        link = tmp_path / f"alias-{index}.svg"
        link.symlink_to(output)
        output = str(link)
    project = tmp_path / "project.json"
    runner = CliRunner()
    assert runner.invoke(cli, ["project", "new", "-o", str(project)]).exit_code == 0
    calls = renderer()
    result = runner.invoke(cli, ["--project", str(project), "export", "render", output])
    assert result.exit_code == 1, result.output
    assert "Error:" in result.output
    assert not calls
    assert target.read_bytes() == b"original"
    assert not (tmp_path / "missing").exists()
    assert not list(tmp_path.glob(".mermaid-*"))
    for index in range(links):
        assert (tmp_path / f"alias-{index}.svg").is_symlink()


def test_cli_enforces_no_overwrite_after_initial_existence_check(monkeypatch, renderer, tmp_path):
    from click.testing import CliRunner
    from cli_anything.mermaid.mermaid_cli import cli
    from cli_anything.mermaid.core import export

    target = tmp_path / "out.svg"
    project = tmp_path / "project.json"
    runner = CliRunner()
    assert runner.invoke(cli, ["project", "new", "-o", str(project)]).exit_code == 0
    exists = os.path.exists

    def created_after_check(path):
        if os.fspath(path) == str(target):
            target.write_bytes(b"another writer")
            return False
        return exists(path)

    monkeypatch.setattr(export.os.path, "exists", created_after_check)
    calls = renderer()
    result = runner.invoke(cli, ["--project", str(project), "export", "render", str(target)])
    assert result.exit_code == 1, result.output
    assert "already exists" in result.output
    assert not calls
    assert target.read_bytes() == b"another writer"


@pytest.mark.parametrize("phase", ["after_write", "metadata"])
@pytest.mark.parametrize("replacement", ["symlink", "regular"])
def test_staging_substitution_preserves_unrelated_file_and_destination(monkeypatch, renderer, tmp_path, phase, replacement):
    target = tmp_path / "out.svg"
    target.write_bytes(b"original")
    target.chmod(0o644)
    unrelated = tmp_path / "private.svg"
    data = b"<svg>new render</svg>"
    unrelated.write_bytes(b"x" * len(data))
    unrelated.chmod(0o600)
    original_unrelated = unrelated.stat()
    if sys.platform == "darwin":
        import subprocess
        subprocess.run(["/bin/chmod", "+a", "user:nobody deny read", str(target)], check=True)
        subprocess.run(["/bin/chmod", "+a", "user:nobody deny write", str(unrelated)], check=True)
        subprocess.run(["/usr/bin/xattr", "-w", "com.cli-anything.stage", "source", str(target)], check=True)
        subprocess.run(["/usr/bin/xattr", "-w", "com.cli-anything.stage", "private", str(unrelated)], check=True)
        original_acl = _macos_acl_bytes(unrelated)
    else:
        os.setxattr(target, "user.cli-anything.stage", b"source")
        os.setxattr(unrelated, "user.cli-anything.stage", b"private")
    replaced = []

    def substitute():
        staged = next(tmp_path.glob(".mermaid-*"))
        staged.unlink()
        if replacement == "symlink":
            staged.symlink_to(unrelated.name)
        else:
            staged.write_bytes(b"y" * len(data))
        replaced.append(staged)

    if phase == "after_write":
        fdopen = os.fdopen
        class Writer:
            def __init__(self, file): self.file = file
            def __enter__(self): self.file.__enter__(); return self
            def write(self, data): return self.file.write(data)
            def __exit__(self, *args):
                result = self.file.__exit__(*args)
                substitute()
                return result
        monkeypatch.setattr(os, "fdopen", lambda fd, *a, **k: Writer(fdopen(fd, *a, **k)))
    else:
        preserve = mermaid_backend._preserve_destination_metadata
        def replace_before_metadata(*args):
            substitute()
            preserve(*args)
        monkeypatch.setattr(mermaid_backend, "_preserve_destination_metadata", replace_before_metadata)
    renderer()
    with pytest.raises(RuntimeError, match="[Ss]taging"):
        mermaid_backend.render_to_file("pako:x", str(target), "svg")
    assert target.read_bytes() == b"original"
    assert not target.is_symlink()
    assert unrelated.read_bytes() == b"x" * len(data)
    assert stat.S_IMODE(unrelated.stat().st_mode) == 0o600
    assert unrelated.stat().st_ino == original_unrelated.st_ino
    if sys.platform == "darwin":
        assert _macos_acl_bytes(unrelated) == original_acl
        assert subprocess.check_output(["/usr/bin/xattr", "-p", "com.cli-anything.stage", str(unrelated)]).strip() == b"private"
    else:
        assert os.getxattr(unrelated, "user.cli-anything.stage") == b"private"
    assert len(replaced) == 1
    if replacement == "symlink":
        assert replaced[0].is_symlink()
        assert os.readlink(replaced[0]) == unrelated.name
    else:
        assert replaced[0].read_bytes() == b"y" * len(data)


@pytest.mark.parametrize("phase", ["fetch", "staging", "metadata"])
@pytest.mark.parametrize("linked", [False, True])
def test_removed_dot_traversal_directory_is_rechecked(monkeypatch, renderer, tmp_path, phase, linked):
    traversed = tmp_path / "traversed"
    traversed.mkdir()
    target = tmp_path / "out.svg"
    target.write_bytes(b"original")
    output = str(traversed) + "/../out.svg"
    if linked:
        link = tmp_path / "current.svg"
        link.symlink_to(output)
        output = str(link)
    if phase == "fetch":
        renderer(traversed.rmdir)
    else:
        renderer()
        if phase == "staging":
            fdopen = os.fdopen
            class Writer:
                def __init__(self, file): self.file = file
                def __enter__(self): self.file.__enter__(); return self
                def __exit__(self, *args): return self.file.__exit__(*args)
                def write(self, data):
                    result = self.file.write(data)
                    traversed.rmdir()
                    return result
            monkeypatch.setattr(os, "fdopen", lambda fd, *a, **k: Writer(fdopen(fd, *a, **k)))
        else:
            preserve = mermaid_backend._preserve_destination_metadata
            def remove_after_metadata(*args):
                preserve(*args)
                traversed.rmdir()
            monkeypatch.setattr(mermaid_backend, "_preserve_destination_metadata", remove_after_metadata)
    with pytest.raises(RuntimeError, match="Requested output path changed"):
        mermaid_backend.render_to_file("pako:x", output, "svg")
    assert target.read_bytes() == b"original"
    assert not os.path.exists(output)
    assert not list(tmp_path.glob(".mermaid-*"))
    if linked:
        assert link.is_symlink()


def test_hard_linked_relative_symlinks_capture_each_parent_context(renderer, tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    destination = tmp_path / "dest"
    destination.mkdir()
    first = tmp_path / "a"
    first.symlink_to("sub")
    second = sub / "b"
    os.link(first, second, follow_symlinks=False)
    assert first.lstat().st_ino == second.lstat().st_ino
    inner = sub / "sub"
    inner.symlink_to("../dest")
    target = destination / "out.svg"
    target.write_bytes(b"original")

    def same_target_rotation():
        inner.unlink()
        inner.symlink_to("../dest")

    renderer(same_target_rotation)
    with pytest.raises(RuntimeError, match="Requested output path changed"):
        mermaid_backend.render_to_file("pako:x", str(first / "b" / "out.svg"), "svg")
    assert target.read_bytes() == b"original"
    assert first.is_symlink() and second.is_symlink() and inner.is_symlink()
    assert not list(destination.glob(".mermaid-*"))
