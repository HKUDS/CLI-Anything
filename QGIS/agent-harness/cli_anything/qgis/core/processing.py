"""Processing wrappers around qgis_process."""

from __future__ import annotations

from cli_anything.qgis.utils import qgis_backend as backend
from cli_anything.qgis.utils.qgis_backend import QgisBackendError


def parse_param_specs(param_specs: list[str]) -> list[str]:
    """Validate repeated KEY=VALUE parameter specifications."""
    parameters: list[str] = []
    for spec in param_specs:
        key, separator, value = spec.partition("=")
        if not separator or not key.strip():
            raise QgisBackendError(
                f"Invalid parameter specification: {spec}. Use KEY=VALUE."
            )
        parameters.append(f"{key.strip()}={value}")
    return parameters


def list_algorithms() -> dict:
    """Return a flattened view of installed QGIS processing algorithms."""
    payload = backend.list_algorithms()
    algorithms = []

    for provider_id, provider in sorted(payload.get("providers", {}).items()):
        for algorithm_id, details in sorted(provider.get("algorithms", {}).items()):
            algorithms.append(
                {
                    "id": algorithm_id,
                    "name": details.get("name"),
                    "provider": provider_id,
                    "group": details.get("group"),
                    "short_description": details.get("short_description"),
                }
            )

    return {
        "qgis_version": payload.get("qgis_version"),
        "provider_count": len(payload.get("providers", {})),
        "algorithm_count": len(algorithms),
        "algorithms": algorithms,
    }


def help_algorithm(algorithm_id: str) -> dict:
    """Return structured help for a processing algorithm."""
    payload = backend.help_algorithm(algorithm_id)
    return {
        "qgis_version": payload.get("qgis_version"),
        "provider": payload.get("provider_details", {}),
        "algorithm": payload.get("algorithm_details", {}),
        "parameters": payload.get("parameters", []),
        "outputs": payload.get("outputs", []),
    }


def run_algorithm(
    algorithm_id: str,
    *,
    param_specs: list[str],
    project_path: str | None = None,
) -> dict:
    """Run a processing algorithm through qgis_process."""
    payload = backend.run_algorithm(
        algorithm_id,
        parameters=parse_param_specs(param_specs),
        project_path=project_path,
    )
    return {
        "qgis_version": payload.get("qgis_version"),
        "project_path": payload.get("project_path"),
        "algorithm": payload.get("algorithm_details", {}),
        "inputs": payload.get("inputs", {}),
        "results": payload.get("results", {}),
        "log": payload.get("log", []),
    }
