"""Unit tests for the Tigris CLI harness.

`subprocess.run` is fully mocked so these tests run without the `tigris` CLI
installed or any network access. End-to-end tests against a real Tigris CLI
live in `test_full_e2e.py`.
"""

import json as json_mod
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

# Patch shutil.which BEFORE the backend is constructed so the resolver
# always claims `tigris` is available.
_WHICH_PATCH = patch(
    "cli_anything.tigris.utils.tigris_backend.shutil.which",
    return_value="/usr/local/bin/tigris",
)
_WHICH_PATCH.start()

from cli_anything.tigris.tigris_cli import cli  # noqa: E402
from cli_anything.tigris.utils.tigris_backend import (   # noqa: E402
    TigrisBackend,
    TigrisCliError,
    _path_to_t3,
)
from cli_anything.tigris.core.object import _parse_tigris_uri  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────


def _mock_run(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Build a mock subprocess.run that returns the given completed-process."""
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def _patch_run(json_out=None, text_out="", returncode=0):
    """Convenience: patch subprocess.run inside the backend module."""
    if json_out is not None:
        stdout = json_mod.dumps(json_out)
    else:
        stdout = text_out
    return patch(
        "cli_anything.tigris.utils.tigris_backend.subprocess.run",
        return_value=_mock_run(stdout=stdout, returncode=returncode),
    )


# ── URI / path helpers ────────────────────────────────────────────────


def test_path_to_t3_normalizes_schemes():
    assert _path_to_t3("t3://b/k") == "t3://b/k"
    assert _path_to_t3("tigris://b/k") == "t3://b/k"
    assert _path_to_t3("b/k") == "t3://b/k"
    assert _path_to_t3("/b/k") == "t3://b/k"


def test_parse_tigris_uri_happy():
    assert _parse_tigris_uri("t3://b/k") == ("b", "k")
    assert _parse_tigris_uri("tigris://b/a/b/c") == ("b", "a/b/c")


def test_parse_tigris_uri_rejects_bad():
    import click as _click
    for bad in ("s3://b/k", "tigris://nokey", "t3:///nobucket", "plainpath"):
        with pytest.raises(_click.UsageError):
            _parse_tigris_uri(bad)


# ── Backend init ──────────────────────────────────────────────────────


def test_backend_init_resolves_tigris_path():
    # _WHICH_PATCH at module scope makes this succeed.
    b = TigrisBackend()
    assert b.cli_path == "/usr/local/bin/tigris"


def test_backend_init_raises_when_tigris_missing():
    with patch(
        "cli_anything.tigris.utils.tigris_backend.shutil.which",
        return_value=None,
    ):
        with pytest.raises(TigrisCliError, match="not found on PATH"):
            TigrisBackend()


def test_backend_extra_env_set_when_credentials_passed():
    b = TigrisBackend(access_key="ak", secret_key="sk")
    assert b._extra_env["TIGRIS_STORAGE_ACCESS_KEY_ID"] == "ak"
    assert b._extra_env["AWS_ACCESS_KEY_ID"] == "ak"
    assert b._extra_env["TIGRIS_STORAGE_SECRET_ACCESS_KEY"] == "sk"
    assert b._extra_env["AWS_SECRET_ACCESS_KEY"] == "sk"


# ── Backend method invocations (verify the args passed to subprocess) ──


def _run_call_args(mock_run) -> list[str]:
    """Extract the argv list passed to subprocess.run."""
    args, _ = mock_run.call_args
    return args[0]


def test_list_buckets_invokes_correct_args():
    with _patch_run(json_out=[{"name": "alpha"}]) as m:
        b = TigrisBackend()
        result = b.list_buckets()
        assert result == [{"name": "alpha"}]
        argv = _run_call_args(m)
        assert argv[1:] == ["buckets", "list", "--format", "json"]


def test_create_bucket_invokes_correct_args():
    with _patch_run(json_out={"name": "x", "status": "created"}) as m:
        b = TigrisBackend()
        b.create_bucket("x")
        assert _run_call_args(m)[1:] == ["buckets", "create", "x", "--format", "json"]


def test_delete_bucket_defaults_to_confirmation():
    with _patch_run(json_out={"status": "deleted"}) as m:
        b = TigrisBackend()
        b.delete_bucket("x")
        argv = _run_call_args(m)
        assert "--yes" not in argv
        assert "buckets" in argv and "delete" in argv and "x" in argv


def test_delete_bucket_includes_yes_flag_when_requested():
    with _patch_run(json_out={"status": "deleted"}) as m:
        b = TigrisBackend()
        b.delete_bucket("x", yes=True)
        argv = _run_call_args(m)
        assert "--yes" in argv
        assert "buckets" in argv and "delete" in argv and "x" in argv


def test_head_bucket_uses_get():
    with _patch_run(json_out={"name": "x"}) as m:
        b = TigrisBackend()
        b.head_bucket("x")
        assert _run_call_args(m)[1:] == ["buckets", "get", "x", "--format", "json"]


def test_list_objects_with_prefix_and_limit():
    payload = [{"key": "foo"}, {"key": "bar"}, {"key": "baz"}]
    with _patch_run(json_out=payload) as m:
        b = TigrisBackend()
        result = b.list_objects("my-bucket", prefix="dir/", limit=2)
        argv = _run_call_args(m)
        assert argv[1:] == ["ls", "t3://my-bucket/dir", "--format", "json"]
        assert result == payload[:2]  # client-side limit applied


def test_cp_uses_recursive_flag_when_set():
    with _patch_run(text_out="ok") as m:
        b = TigrisBackend()
        b.cp("./local/", "t3://my-bucket/dst/", recursive=True)
        argv = _run_call_args(m)
        assert "--recursive" in argv
        # JSON-mode is OFF for cp (no --format json appended)
        assert "--format" not in argv


def test_put_object_from_file_uses_cp():
    with _patch_run(text_out="") as m:
        b = TigrisBackend()
        b.put_object_from_file("my-bucket", "k", "./local.txt")
        argv = _run_call_args(m)
        assert argv[1] == "cp"
        assert argv[2] == "./local.txt"
        assert argv[3] == "t3://my-bucket/k"


def test_put_object_inline_writes_tempfile_then_cleans_up():
    with _patch_run(text_out="") as m:
        b = TigrisBackend()
        b.put_object_inline("my-bucket", "k", "hello body")
        argv = _run_call_args(m)
        assert argv[1] == "cp"
        # tmp path -> t3 url
        assert argv[3] == "t3://my-bucket/k"


def test_delete_object_uses_rm_with_yes():
    with _patch_run(text_out="") as m:
        b = TigrisBackend()
        b.delete_object("my-bucket", "k")
        argv = _run_call_args(m)
        assert argv[1] == "rm"
        assert argv[2] == "t3://my-bucket/k"
        assert "--yes" in argv


def test_head_object_uses_stat():
    with _patch_run(json_out={"size": 42}) as m:
        b = TigrisBackend()
        info = b.head_object("my-bucket", "k")
        argv = _run_call_args(m)
        assert argv[1:] == ["stat", "t3://my-bucket/k", "--format", "json"]
        assert info == {"size": 42}


def test_presign_returns_url_from_dict():
    with _patch_run(json_out={"url": "https://signed/url"}) as m:
        b = TigrisBackend()
        url = b.presign("my-bucket", "k", method="get", expires_in=600)
        argv = _run_call_args(m)
        assert "presign" in argv
        assert "t3://my-bucket/k" in argv
        assert "--method" in argv and "get" in argv
        assert "--expires-in" in argv and "600" in argv
        assert url == "https://signed/url"


def test_presign_falls_back_to_string():
    with _patch_run(text_out="https://signed/url\n") as m:
        b = TigrisBackend()
        # text_out is returned through JSONDecodeError fallback
        url = b.presign("my-bucket", "k")
        assert url == "https://signed/url"


# ── Snapshots ─────────────────────────────────────────────────────────


def test_list_snapshots_invokes_correct_args():
    with _patch_run(json_out=[]) as m:
        b = TigrisBackend()
        b.list_snapshots("my-bucket")
        assert _run_call_args(m)[1:] == ["snapshots", "list", "my-bucket", "--format", "json"]


def test_take_snapshot_with_name():
    with _patch_run(json_out={"status": "ok"}) as m:
        b = TigrisBackend()
        b.take_snapshot("my-bucket", name="v1")
        argv = _run_call_args(m)
        assert "snapshots" in argv and "take" in argv
        assert "--name" in argv and "v1" in argv


# ── Access keys ───────────────────────────────────────────────────────


def test_list_access_keys():
    with _patch_run(json_out=[]) as m:
        b = TigrisBackend()
        b.list_access_keys()
        assert _run_call_args(m)[1:] == ["access-keys", "list", "--format", "json"]


def test_delete_access_key_defaults_to_confirmation():
    with _patch_run(json_out={"status": "deleted"}) as m:
        b = TigrisBackend()
        b.delete_access_key("tid_AaBb")
        argv = _run_call_args(m)
        assert "--yes" not in argv
        assert "access-keys" in argv and "delete" in argv and "tid_AaBb" in argv


def test_delete_access_key_includes_yes_flag_when_requested():
    with _patch_run(json_out={"status": "deleted"}) as m:
        b = TigrisBackend()
        b.delete_access_key("tid_AaBb", yes=True)
        argv = _run_call_args(m)
        assert "--yes" in argv
        assert "access-keys" in argv and "delete" in argv and "tid_AaBb" in argv


def test_assign_access_key_uses_role_and_bucket():
    with _patch_run(json_out={"status": "assigned"}) as m:
        b = TigrisBackend()
        b.assign_access_key("tid_AaBb", bucket="my-bucket", role="Editor")
        argv = _run_call_args(m)
        assert "access-keys" in argv and "assign" in argv and "tid_AaBb" in argv
        assert "--bucket" in argv and "my-bucket" in argv
        assert "--role" in argv and "Editor" in argv


def test_rotate_access_key_defaults_to_confirmation():
    with _patch_run(json_out={"status": "rotated"}) as m:
        b = TigrisBackend()
        b.rotate_access_key("tid_AaBb")
        argv = _run_call_args(m)
        assert "--yes" not in argv
        assert "access-keys" in argv and "rotate" in argv and "tid_AaBb" in argv


def test_rotate_access_key_includes_yes_flag_when_requested():
    with _patch_run(json_out={"status": "rotated"}) as m:
        b = TigrisBackend()
        b.rotate_access_key("tid_AaBb", yes=True)
        argv = _run_call_args(m)
        assert "--yes" in argv
        assert "access-keys" in argv and "rotate" in argv and "tid_AaBb" in argv


# ── IAM ───────────────────────────────────────────────────────────────


def test_list_iam_policies():
    with _patch_run(json_out=[]) as m:
        b = TigrisBackend()
        b.list_iam_policies()
        assert _run_call_args(m)[1:] == ["iam", "policies", "list", "--format", "json"]


def test_invite_iam_user():
    with _patch_run(json_out={"status": "invited"}) as m:
        b = TigrisBackend()
        b.invite_iam_user("user@example.com", role="admin")
        argv = _run_call_args(m)
        assert "iam" in argv and "users" in argv and "invite" in argv
        assert "user@example.com" in argv
        assert "--role" in argv and "admin" in argv


# ── Error handling ────────────────────────────────────────────────────


def test_nonzero_exit_raises_tigris_cli_error():
    with patch(
        "cli_anything.tigris.utils.tigris_backend.subprocess.run",
        return_value=_mock_run(stderr="boom", returncode=1),
    ):
        b = TigrisBackend()
        with pytest.raises(TigrisCliError, match="boom"):
            b.list_buckets()


# ── CLI integration tests (backend uses mocked subprocess) ────────────


def test_cli_bucket_list_json():
    with _patch_run(json_out=[{"name": "demo"}]):
        runner = CliRunner()
        r = runner.invoke(cli, ["--json", "bucket", "list"])
        assert r.exit_code == 0, r.output
        assert "demo" in r.output


def test_cli_bucket_delete_requires_yes():
    with patch("cli_anything.tigris.utils.tigris_backend.subprocess.run") as m:
        runner = CliRunner()
        r = runner.invoke(cli, ["--json", "bucket", "delete", "--name", "b"])
        assert r.exit_code != 0
        assert "without --yes" in r.output
        m.assert_not_called()


def test_cli_bucket_delete_with_yes_passes_yes_flag():
    with _patch_run(json_out={"status": "deleted"}) as m:
        runner = CliRunner()
        r = runner.invoke(cli, ["--json", "bucket", "delete", "--name", "b", "--yes"])
        assert r.exit_code == 0, r.output
        assert "--yes" in _run_call_args(m)


def test_cli_object_put_requires_file_or_text():
    runner = CliRunner()
    r = runner.invoke(cli, ["--json", "object", "put", "--bucket", "b", "--key", "k"])
    assert r.exit_code != 0


def test_cli_object_cp_requires_one_remote():
    runner = CliRunner()
    r = runner.invoke(cli, ["--json", "object", "cp", "./a", "./b"])
    assert r.exit_code != 0


def test_cli_presign_get_json():
    with _patch_run(json_out={"url": "https://signed"}):
        runner = CliRunner()
        r = runner.invoke(cli, ["--json", "presign", "get", "--bucket", "b", "--key", "k"])
        assert r.exit_code == 0, r.output
        assert "https://signed" in r.output


def test_cli_snapshot_take_json():
    with _patch_run(json_out={"status": "ok"}):
        runner = CliRunner()
        r = runner.invoke(cli, ["--json", "snapshot", "take", "my-bucket", "--name", "v1"])
        assert r.exit_code == 0, r.output


def test_cli_access_key_assign_json():
    with _patch_run(json_out={"status": "assigned"}):
        runner = CliRunner()
        r = runner.invoke(cli, [
            "--json", "access-key", "assign", "tid_x",
            "--bucket", "b", "--role", "Editor",
        ])
        assert r.exit_code == 0, r.output


def test_cli_access_key_delete_requires_yes():
    with patch("cli_anything.tigris.utils.tigris_backend.subprocess.run") as m:
        runner = CliRunner()
        r = runner.invoke(cli, ["--json", "access-key", "delete", "tid_x"])
        assert r.exit_code != 0
        assert "without --yes" in r.output
        m.assert_not_called()


def test_cli_access_key_delete_with_yes_passes_yes_flag():
    with _patch_run(json_out={"status": "deleted"}) as m:
        runner = CliRunner()
        r = runner.invoke(cli, ["--json", "access-key", "delete", "tid_x", "--yes"])
        assert r.exit_code == 0, r.output
        assert "--yes" in _run_call_args(m)


def test_cli_access_key_rotate_requires_yes():
    with patch("cli_anything.tigris.utils.tigris_backend.subprocess.run") as m:
        runner = CliRunner()
        r = runner.invoke(cli, ["--json", "access-key", "rotate", "tid_x"])
        assert r.exit_code != 0
        assert "without --yes" in r.output
        m.assert_not_called()


def test_cli_access_key_rotate_with_yes_passes_yes_flag():
    with _patch_run(json_out={"status": "rotated"}) as m:
        runner = CliRunner()
        r = runner.invoke(cli, ["--json", "access-key", "rotate", "tid_x", "--yes"])
        assert r.exit_code == 0, r.output
        assert "--yes" in _run_call_args(m)


def test_cli_auth_whoami_json():
    with _patch_run(json_out={"user": "dave", "org": "tigris"}):
        runner = CliRunner()
        r = runner.invoke(cli, ["--json", "auth", "whoami"])
        assert r.exit_code == 0, r.output
        assert "dave" in r.output
