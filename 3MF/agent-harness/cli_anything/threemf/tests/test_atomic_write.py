"""Exercise failed exports against real ZIP files and destination paths."""

from __future__ import annotations

import errno
import os
import stat
import zipfile
from dataclasses import replace

import numpy as np
import pytest

from cli_anything.threemf.core import parser


def model_data() -> parser.ThreeMFData:
    mesh = parser.MeshData(
        object_id="1",
        name="tetrahedron",
        vertices=np.array(
            [[0., 0., 0.], [1., 0., 0.], [0., 1., 0.], [0., 0., 1.]],
        ),
        triangles=np.array(
            [[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]], dtype=np.int32,
        ),
    )
    return parser.ThreeMFData(
        meshes=(mesh,), unit="millimeter", model_path="3D/3dmodel.model",
        metadata={"Title": "atomic export"},
        raw_entries={"Metadata/settings.json": b'{"quality":"fine"}'},
        source_path="",
    )


def destination(tmp_path, kind):
    output = tmp_path / "output.3mf"
    data = model_data()
    if kind == "inplace":
        parser.write_3mf(data, str(output))
        data = parser.parse_3mf(str(output))
        resized = replace(data.meshes[0], vertices=data.meshes[0].vertices * 2)
        data = replace(data, meshes=(resized,))
    elif kind == "existing":
        output.write_bytes(b"previous valuable export")
    previous = output.read_bytes() if output.exists() else None
    return output, data, previous


def assert_preserved(tmp_path, output, previous):
    if previous is None:
        assert not output.exists()
        assert list(tmp_path.iterdir()) == []
    else:
        assert output.read_bytes() == previous
        assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("kind", ["existing", "missing", "inplace"])
@pytest.mark.parametrize("phase", ["member", "close"])
def test_failed_zip_keeps_previous_destination(
    tmp_path, monkeypatch, kind, phase,
):
    output, data, previous = destination(tmp_path, kind)
    if phase == "member":
        original = zipfile.ZipFile.writestr

        def fail_model(archive, member, contents, *args, **kwargs):
            if member == data.model_path:
                raise OSError(errno.ENOSPC, "injected full device during model write")
            return original(archive, member, contents, *args, **kwargs)

        monkeypatch.setattr(zipfile.ZipFile, "writestr", fail_model)
    else:
        original = zipfile.ZipFile.close

        def fail_close(archive):
            writing = archive.mode == "w" and archive.fp is not None
            original(archive)
            if writing:
                raise OSError(errno.ENOSPC, "injected full device during ZIP close")

        monkeypatch.setattr(zipfile.ZipFile, "close", fail_close)

    with pytest.raises(OSError, match="injected full device"):
        parser.write_3mf(data, str(output))
    assert_preserved(tmp_path, output, previous)


@pytest.mark.parametrize("kind", ["existing", "missing", "inplace"])
def test_successful_write_replaces_complete_archive(tmp_path, kind):
    output, data, _ = destination(tmp_path, kind)
    parser.write_3mf(data, str(output))
    actual = parser.parse_3mf(str(output))
    np.testing.assert_array_equal(
        actual.meshes[0].vertices, data.meshes[0].vertices,
    )
    np.testing.assert_array_equal(
        actual.meshes[0].triangles, data.meshes[0].triangles,
    )
    assert actual.raw_entries == data.raw_entries
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("kind", ["existing", "missing", "inplace"])
def test_failed_replace_keeps_destination_and_cleans_stage(
    tmp_path, monkeypatch, kind,
):
    output, data, previous = destination(tmp_path, kind)

    def deny_replace(source, target):
        with zipfile.ZipFile(source) as archive:
            assert archive.testzip() is None
        raise PermissionError(errno.EACCES, "injected replacement failure")

    monkeypatch.setattr(os, "replace", deny_replace)
    with pytest.raises(PermissionError, match="injected replacement failure"):
        parser.write_3mf(data, str(output))
    assert_preserved(tmp_path, output, previous)


@pytest.mark.skipif(os.name != "posix", reason="POSIX mode and symlink semantics")
def test_existing_mode_and_symlink_target_survive_export(tmp_path):
    output = tmp_path / "actual.3mf"
    output.write_bytes(b"old")
    output.chmod(0o640)
    link = tmp_path / "linked.3mf"
    link.symlink_to(output.name)
    parser.write_3mf(model_data(), str(link))
    assert link.is_symlink()
    assert stat.S_IMODE(output.stat().st_mode) == 0o640
    assert parser.parse_3mf(str(link)).meshes[0].name == "tetrahedron"
    assert set(tmp_path.iterdir()) == {output, link}


@pytest.mark.skipif(os.name != "posix", reason="POSIX write permissions")
def test_existing_readonly_file_is_not_replaced(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root bypasses POSIX file write permissions")
    output = tmp_path / "readonly.3mf"
    output.write_bytes(b"preserve read-only export")
    output.chmod(0o400)
    try:
        with pytest.raises(PermissionError):
            parser.write_3mf(model_data(), str(output))
        assert output.read_bytes() == b"preserve read-only export"
        assert list(tmp_path.iterdir()) == [output]
    finally:
        output.chmod(0o600)


def test_failed_repair_cli_keeps_inplace_source(tmp_path, monkeypatch):
    from click.testing import CliRunner
    from cli_anything.threemf.threemf_cli import cli

    output, _, previous = destination(tmp_path, "inplace")
    original = zipfile.ZipFile.writestr

    def fail_model(archive, member, contents, *args, **kwargs):
        if member == "3D/3dmodel.model":
            raise OSError(errno.ENOSPC, "injected full device")
        return original(archive, member, contents, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "writestr", fail_model)
    result = CliRunner().invoke(
        cli, ["--json", "repair", str(output), "-o", str(output), "--overwrite"],
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, OSError)
    assert_preserved(tmp_path, output, previous)
