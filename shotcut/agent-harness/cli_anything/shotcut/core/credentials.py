"""Credential providers for secrets that must stay outside the repository."""

import os
import shutil
import subprocess
from typing import Callable, Protocol


class CredentialProvider(Protocol):
    def get(self, name: str) -> str | None:
        """Return a credential without displaying it."""


class EnvironmentCredentialProvider:
    def get(self, name: str) -> str | None:
        value = os.getenv(name)
        return value or None


class MacOSKeychainCredentialProvider:
    ACCOUNT = "cli-anything-shotcut"

    def __init__(
        self,
        account: str = ACCOUNT,
        executable: str | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self._account = account
        self._executable = executable or shutil.which("security")
        self._runner = runner

    def get(self, name: str) -> str | None:
        if self._executable is None:
            return None
        try:
            result = self._runner(
                [
                    self._executable,
                    "find-generic-password",
                    "-a",
                    self._account,
                    "-s",
                    name,
                    "-w",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None
        if result.returncode != 0:
            return None
        value = result.stdout.strip()
        return value or None


class CompositeCredentialProvider:
    def __init__(self, providers: list[CredentialProvider]) -> None:
        self._providers = providers

    def get_required(self, name: str) -> str:
        for provider in self._providers:
            value = provider.get(name)
            if value:
                return value
        raise RuntimeError(
            f"Credential {name} was not found in the environment or macOS Keychain"
        )
