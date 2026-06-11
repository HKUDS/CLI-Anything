"""Subprocess wrapper around the official Tigris CLI (`tigris`).

This harness shells out to the Tigris CLI rather than reimplementing the S3
protocol, so:

  * snapshots, IAM, access-keys, and organization primitives — features
    unique to Tigris — are surfaced for agents.
  * the harness inherits new commands automatically as the upstream CLI ships
    them.
  * authentication uses Tigris's OAuth flow (`tigris login`) by default.

Install the underlying CLI with one of:

    npm install -g @tigrisdata/cli
    brew install tigrisdata/tap/tigris

Then `tigris login` once, and this harness can call any operation as the
authenticated user.
"""

import json as json_mod
import os
import shutil
import subprocess
from typing import Any


class TigrisCliError(RuntimeError):
    """Raised when the tigris CLI returns a non-zero exit code."""


def _path_to_t3(path: str) -> str:
    """Normalize 'tigris://...', 't3://...', or bare 'bucket/key' to t3://..."""
    if path.startswith("t3://"):
        return path
    if path.startswith("tigris://"):
        return "t3://" + path[len("tigris://"):]
    return "t3://" + path.lstrip("/")


class TigrisBackend:
    """Subprocess wrapper for the `tigris` CLI."""

    def __init__(self, cli_path: str = "tigris", access_key: str | None = None,
                 secret_key: str | None = None):
        """Resolve the CLI binary; verify it's on PATH.

        Args:
            cli_path: Name or absolute path of the tigris binary. Default
                `tigris`; the binary's alias `t3` also works.
            access_key, secret_key: Optional explicit credentials. When set,
                exported into env for child processes so commands that honor
                AWS_* env vars pick them up. Most users should `tigris login`
                instead.
        """
        resolved = shutil.which(cli_path)
        if not resolved:
            raise TigrisCliError(
                f"`{cli_path}` not found on PATH. Install with "
                "`npm install -g @tigrisdata/cli` or "
                "`brew install tigrisdata/tap/tigris`, then `tigris login`."
            )
        self.cli_path = resolved
        self._extra_env: dict[str, str] = {}
        if access_key:
            self._extra_env["TIGRIS_STORAGE_ACCESS_KEY_ID"] = access_key
            self._extra_env["AWS_ACCESS_KEY_ID"] = access_key
        if secret_key:
            self._extra_env["TIGRIS_STORAGE_SECRET_ACCESS_KEY"] = secret_key
            self._extra_env["AWS_SECRET_ACCESS_KEY"] = secret_key

    # ── core invoker ──────────────────────────────────────────────────

    def _run(
        self,
        args: list[str],
        json: bool = True,
        check: bool = True,
        capture: bool = True,
    ) -> Any:
        """Run `tigris <args>` and return parsed JSON when possible.

        Args:
            args: CLI subcommand + flags, excluding the binary name itself.
            json: If True, append `--format json` and parse stdout as JSON.
                Falls back to raw stdout on parse failure.
            check: If True, raise TigrisCliError on non-zero exit.
            capture: If True, capture stdout/stderr; if False, stream to the
                caller's TTY (used for `login` / interactive flows).

        Returns:
            Parsed JSON object on success when json=True, raw string when
            json=False or parse fails, or None when capture=False.
        """
        cmd = [self.cli_path] + list(args)
        if json:
            # Append at the end so it doesn't fight with subcommand parsing.
            cmd.extend(["--format", "json"])

        env = {**os.environ, **self._extra_env}
        if not capture:
            result = subprocess.run(cmd, env=env, check=False)
            if check and result.returncode != 0:
                raise TigrisCliError(
                    f"`{' '.join(cmd)}` exited with code {result.returncode}"
                )
            return None

        result = subprocess.run(
            cmd, env=env, check=False, capture_output=True, text=True
        )
        if check and result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip()
            raise TigrisCliError(
                f"`{' '.join(cmd)}` failed: {stderr or 'no output'}"
            )
        if json:
            stdout = result.stdout.strip()
            if not stdout:
                return None
            try:
                return json_mod.loads(stdout)
            except json_mod.JSONDecodeError:
                # Not all commands support --format json; return raw text.
                return stdout
        return result.stdout

    # ── version / auth ────────────────────────────────────────────────

    def version(self) -> str:
        """Return the tigris CLI version string."""
        return (self._run(["--version"], json=False) or "").strip()

    def whoami(self) -> Any:
        """Return the currently authenticated user/org."""
        return self._run(["whoami"])

    def login(self) -> None:
        """Trigger the interactive `tigris login` flow (browser OAuth).

        Streams to the caller's TTY; no return value. Use --json=False since
        the flow prompts and prints progress.
        """
        self._run(["login"], json=False, capture=False)

    def logout(self) -> None:
        """Log out of the currently authenticated session."""
        self._run(["logout"], json=False, capture=False)

    # ── buckets ───────────────────────────────────────────────────────

    def list_buckets(self) -> Any:
        return self._run(["buckets", "list"])

    def create_bucket(self, name: str) -> Any:
        return self._run(["buckets", "create", name])

    def delete_bucket(self, name: str, yes: bool = False) -> Any:
        args = ["buckets", "delete", name]
        if yes:
            args.append("--yes")
        return self._run(args)

    def head_bucket(self, name: str) -> Any:
        """Get bucket info via `buckets get` (falls back to `stat`)."""
        # The CLI exposes `tigris buckets get <name>` as the head equivalent.
        return self._run(["buckets", "get", name])

    # ── objects ───────────────────────────────────────────────────────

    def list_objects(
        self,
        bucket: str,
        prefix: str | None = None,
        limit: int | None = None,
    ) -> Any:
        """`tigris ls <bucket[/prefix]>` — limit handled client-side if set."""
        path = bucket if not prefix else f"{bucket}/{prefix}".rstrip("/")
        result = self._run(["ls", _path_to_t3(path)])
        if isinstance(result, list) and limit:
            return result[:limit]
        return result

    def cp(self, src: str, dst: str, recursive: bool = False) -> Any:
        """Server-side or local↔remote copy.

        `src` and `dst` may be local paths or t3:// / tigris:// URIs.
        At least one side must be remote (enforced by the underlying CLI).
        """
        src_norm = _path_to_t3(src) if src.startswith(("t3://", "tigris://")) else src
        dst_norm = _path_to_t3(dst) if dst.startswith(("t3://", "tigris://")) else dst
        args = ["cp", src_norm, dst_norm]
        if recursive:
            args.append("--recursive")
        return self._run(args, json=False)

    def put_object_from_file(self, bucket: str, key: str, file_path: str) -> Any:
        """Upload a local file via `tigris cp <file> t3://bucket/key`."""
        return self.cp(file_path, f"t3://{bucket}/{key}")

    def put_object_inline(self, bucket: str, key: str, text: str) -> Any:
        """Upload inline text by staging to a tempfile and `tigris cp`-ing it."""
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".txt", delete=False
        ) as f:
            f.write(text)
            tmp_path = f.name
        try:
            return self.cp(tmp_path, f"t3://{bucket}/{key}")
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def get_object_to_file(self, bucket: str, key: str, file_path: str) -> Any:
        """Download an object via `tigris cp t3://bucket/key <file>`."""
        return self.cp(f"t3://{bucket}/{key}", file_path)

    def delete_object(self, bucket: str, key: str) -> Any:
        return self._run(["rm", _path_to_t3(f"{bucket}/{key}"), "--yes"], json=False)

    def head_object(self, bucket: str, key: str) -> Any:
        """`tigris stat t3://bucket/key`."""
        return self._run(["stat", _path_to_t3(f"{bucket}/{key}")])

    # ── presign ───────────────────────────────────────────────────────

    def presign(
        self,
        bucket: str,
        key: str,
        method: str = "get",
        expires_in: int = 3600,
        access_key: str | None = None,
    ) -> str:
        """Generate a presigned URL via `tigris presign`."""
        args = [
            "presign",
            _path_to_t3(f"{bucket}/{key}"),
            "--method", method,
            "--expires-in", str(expires_in),
        ]
        if access_key:
            args.extend(["--access-key", access_key])
        result = self._run(args)
        # The CLI returns either {"url": "..."} (json mode) or the bare URL.
        if isinstance(result, dict) and "url" in result:
            return result["url"]
        if isinstance(result, str):
            return result.strip()
        return str(result)

    # ── snapshots ─────────────────────────────────────────────────────

    def list_snapshots(self, bucket: str) -> Any:
        return self._run(["snapshots", "list", bucket])

    def take_snapshot(self, bucket: str, name: str | None = None) -> Any:
        args = ["snapshots", "take", bucket]
        if name:
            args.extend(["--name", name])
        return self._run(args)

    # ── access keys ───────────────────────────────────────────────────

    def list_access_keys(self) -> Any:
        return self._run(["access-keys", "list"])

    def create_access_key(self, name: str) -> Any:
        return self._run(["access-keys", "create", name])

    def get_access_key(self, key_id: str) -> Any:
        return self._run(["access-keys", "get", key_id])

    def delete_access_key(self, key_id: str, yes: bool = False) -> Any:
        args = ["access-keys", "delete", key_id]
        if yes:
            args.append("--yes")
        return self._run(args)

    def assign_access_key(
        self, key_id: str, bucket: str, role: str
    ) -> Any:
        """`tigris access-keys assign <id> --bucket <b> --role <r>`."""
        return self._run([
            "access-keys", "assign", key_id,
            "--bucket", bucket, "--role", role,
        ])

    def rotate_access_key(self, key_id: str, yes: bool = False) -> Any:
        args = ["access-keys", "rotate", key_id]
        if yes:
            args.append("--yes")
        return self._run(args)

    # ── IAM ───────────────────────────────────────────────────────────

    def list_iam_policies(self) -> Any:
        return self._run(["iam", "policies", "list"])

    def create_iam_policy(self, name: str, document_path: str) -> Any:
        return self._run([
            "iam", "policies", "create", name,
            "--document", document_path,
        ])

    def list_iam_users(self) -> Any:
        return self._run(["iam", "users", "list"])

    def invite_iam_user(self, email: str, role: str = "member") -> Any:
        return self._run([
            "iam", "users", "invite", email, "--role", role,
        ])
