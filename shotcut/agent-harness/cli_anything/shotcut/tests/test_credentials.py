"""Tests for environment and macOS Keychain credential lookup."""

import subprocess

import pytest

from cli_anything.shotcut.core.credentials import (
    CompositeCredentialProvider,
    EnvironmentCredentialProvider,
    MacOSKeychainCredentialProvider,
)


def test_keychain_provider_returns_secret_without_printing_it():
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="secret-value\n", stderr="")

    provider = MacOSKeychainCredentialProvider(executable="security", runner=runner)

    assert provider.get("BRIGHT_DATA_API_KEY") == "secret-value"
    assert calls[0][0][-2:] == ["BRIGHT_DATA_API_KEY", "-w"]
    assert calls[0][1]["capture_output"] is True


def test_composite_provider_prefers_environment(monkeypatch):
    monkeypatch.setenv("BRIGHT_DATA_API_KEY", "environment-value")

    provider = CompositeCredentialProvider([
        EnvironmentCredentialProvider(),
        MacOSKeychainCredentialProvider(executable="/nonexistent/security"),
    ])

    assert provider.get_required("BRIGHT_DATA_API_KEY") == "environment-value"


def test_composite_provider_reports_missing_credential():
    provider = CompositeCredentialProvider([
        EnvironmentCredentialProvider(),
        MacOSKeychainCredentialProvider(executable="/nonexistent/security"),
    ])

    with pytest.raises(RuntimeError, match="BRIGHT_DATA_API_KEY"):
        provider.get_required("BRIGHT_DATA_API_KEY")
