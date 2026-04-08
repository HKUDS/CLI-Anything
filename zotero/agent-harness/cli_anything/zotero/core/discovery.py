from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any, Optional

from cli_anything.zotero.utils import zotero_http, zotero_paths


@dataclass
class RuntimeContext:
    environment: zotero_paths.ZoteroEnvironment
    backend: str
    connector_available: bool
    connector_message: str
    local_api_available: bool
    local_api_message: str

    def to_status_payload(self) -> dict[str, Any]:
        payload = self.environment.to_dict()
        payload.update(
            {
                "backend": self.backend,
                "connector_available": self.connector_available,
                "connector_message": self.connector_message,
                "local_api_available": self.local_api_available,
                "local_api_message": self.local_api_message,
            }
        )
        return payload


def build_runtime_context(*, backend: str = "auto", data_dir: str | None = None, profile_dir: str | None = None, executable: str | None = None) -> RuntimeContext:
    environment = zotero_paths.build_environment(
        explicit_data_dir=data_dir,
        explicit_profile_dir=profile_dir,
        explicit_executable=executable,
    )
    connector_available, connector_message = zotero_http.connector_is_available(environment.port)
    local_api_available, local_api_message = zotero_http.local_api_is_available(environment.port)
    return RuntimeContext(
        environment=environment,
        backend=backend,
        connector_available=connector_available,
        connector_message=connector_message,
        local_api_available=local_api_available,
        local_api_message=local_api_message,
    )


def launch_zotero(runtime: RuntimeContext, wait_timeout: int = 30) -> dict[str, Any]:
    executable = runtime.environment.executable
    if executable is None:
        raise RuntimeError("Zotero executable could not be resolved")
    if not executable.exists():
        raise FileNotFoundError(f"Zotero executable not found: {executable}")

    process = subprocess.Popen([str(executable)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    connector_ready = zotero_http.wait_for_endpoint(
        runtime.environment.port,
        "/connector/ping",
        timeout=wait_timeout,
        ready_statuses=(200,),
    )
    local_api_ready = False
    if runtime.environment.local_api_enabled_configured:
        local_api_ready = zotero_http.wait_for_endpoint(
            runtime.environment.port,
            "/api/",
            timeout=wait_timeout,
            headers={"Zotero-API-Version": zotero_http.LOCAL_API_VERSION},
            ready_statuses=(200,),
        )
    return {
        "action": "launch",
        "pid": process.pid,
        "connector_ready": connector_ready,
        "local_api_ready": local_api_ready,
        "wait_timeout": wait_timeout,
        "executable": str(executable),
    }


def ensure_live_api_enabled(profile_dir: Optional[str] = None) -> Optional[str]:
    environment = zotero_paths.build_environment(explicit_profile_dir=profile_dir)
    path = zotero_paths.ensure_local_api_enabled(environment.profile_dir)
    return str(path) if path else None
