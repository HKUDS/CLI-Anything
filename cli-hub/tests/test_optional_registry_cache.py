"""Optional discovery caches must not turn usable registry data into errors."""

import json
import os
from unittest.mock import Mock

import pytest
import requests
from cli_hub import registry, matrix


@pytest.mark.parametrize("module", [registry, matrix])
@pytest.mark.parametrize("fault", ["parent_is_file", "cache_is_directory"])
def test_successful_fetch_survives_real_cache_filesystem_fault(
    module, fault, tmp_path, monkeypatch
):
    cache_dir = tmp_path / "cache"
    cache_file = cache_dir / "registry.json"
    if fault == "parent_is_file":
        cache_dir.write_text("unrelated file", encoding="utf-8")
    else:
        cache_file.mkdir(parents=True)
    if module is registry:
        monkeypatch.setattr(module, "CACHE_DIR", cache_dir)
        monkeypatch.setattr(module, "CACHE_FILE", cache_file)
        fetch = module.fetch_registry
    else:
        monkeypatch.setattr(module, "MATRIX_CACHE_FILE", cache_file)
        fetch = module.fetch_matrix_registry
    data = {"clis": []} if module is registry else {"matrices": []}
    response = Mock()
    response.json.return_value = data
    get = Mock(return_value=response)
    monkeypatch.setattr(module.requests, "get", get)
    assert fetch() == data
    get.assert_called_once()
    if fault == "parent_is_file":
        assert cache_dir.read_text(encoding="utf-8") == "unrelated file"
    else:
        assert cache_file.is_dir()


def test_offline_matrix_falls_back_to_checkout_when_cache_parent_is_file(
    tmp_path, monkeypatch
):
    blocked = tmp_path / "cache"
    blocked.write_text("unrelated file", encoding="utf-8")
    monkeypatch.setattr(matrix, "MATRIX_CACHE_FILE", blocked / "registry.json")
    monkeypatch.setattr(
        matrix.requests,
        "get",
        Mock(side_effect=requests.ConnectionError("offline")),
    )
    fallback = {"matrices": [{"name": "local"}]}
    monkeypatch.setattr(matrix, "_load_local_registry", lambda: fallback)
    assert matrix.fetch_matrix_registry() == fallback


def test_offline_registry_preserves_request_failure_when_cache_unreadable(
    tmp_path, monkeypatch
):
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(registry, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(registry, "CACHE_FILE", cache)
    failure = requests.ConnectionError("offline")
    monkeypatch.setattr(registry.requests, "get", Mock(side_effect=failure))
    with pytest.raises(requests.ConnectionError, match="offline"):
        registry.fetch_registry(force_refresh=True)


def test_writable_cache_is_still_saved_and_reused(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(registry, "CACHE_FILE", tmp_path / "registry.json")
    data = {"clis": []}
    response = Mock()
    response.json.return_value = data
    get = Mock(return_value=response)
    monkeypatch.setattr(registry.requests, "get", get)
    assert registry.fetch_registry() == data
    assert json.loads(registry.CACHE_FILE.read_text())["data"] == data
    assert registry.fetch_registry() == data
    get.assert_called_once()


@pytest.mark.skipif(os.name == "nt", reason="POSIX directory mode enforcement")
@pytest.mark.parametrize("module", [registry, matrix])
def test_read_only_cache_directory_does_not_discard_downloaded_registry(
    module, tmp_path, monkeypatch
):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cache_file = cache_dir / "registry.json"
    if module is registry:
        monkeypatch.setattr(module, "CACHE_DIR", cache_dir)
        monkeypatch.setattr(module, "CACHE_FILE", cache_file)
        fetch = module.fetch_registry
    else:
        monkeypatch.setattr(module, "MATRIX_CACHE_FILE", cache_file)
        fetch = module.fetch_matrix_registry
    response = Mock()
    response.json.return_value = {"downloaded": True}
    monkeypatch.setattr(module.requests, "get", Mock(return_value=response))
    cache_dir.chmod(0o500)
    try:
        # Verify a real filesystem denial; don't claim it when running as root.
        try:
            cache_file.write_text("probe")
        except PermissionError:
            pass
        else:
            pytest.skip("Current user can write through the read-only mode")
        assert fetch() == {"downloaded": True}
        assert not cache_file.exists()
    finally:
        cache_dir.chmod(0o700)
