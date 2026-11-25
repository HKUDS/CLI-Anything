"""HTTP operations for the Flowise workflows API."""

import json
import math
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

import requests


class FlowiseError(RuntimeError):
    """A Flowise request or input could not be processed."""


def flow_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as error:
        raise FlowiseError("Use the UUID returned by the Flowise server.") from error


class Flowise:
    def __init__(self, url: str, api_key: str | None, prediction_key: str | None):
        error_message = "Use an HTTP or HTTPS server URL without credentials, query, or fragment."
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError as error:
            raise FlowiseError(error_message) from error
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.query
            or parsed.fragment
            or port == 0
        ):
            raise FlowiseError(error_message)
        root = url.rstrip("/")
        self.api_url = root if root.endswith("/api/v1") else f"{root}/api/v1"
        self.api_key = api_key
        self.prediction_key = prediction_key

    def _request(
        self, method: str, route: str, *, payload: dict | None = None,
        prediction: bool = False,
    ):
        key = self.prediction_key if prediction else self.api_key
        headers = {"Accept": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"

        try:
            response = requests.request(
                method, f"{self.api_url}/{route}", headers=headers, json=payload,
                timeout=(5, 120) if prediction else (5, 30), allow_redirects=False,
            )
        except requests.RequestException as error:
            raise FlowiseError(f"Could not reach the Flowise API ({type(error).__name__}).") from error

        if not 200 <= response.status_code < 300:
            raise FlowiseError(f"Flowise rejected {method} {route} (HTTP {response.status_code}).")
        try:
            return response.json()
        except ValueError as error:
            raise FlowiseError(f"Flowise returned a non-JSON response for {method} {route}.") from error

    @staticmethod
    def _flow_route(flow_id: str) -> str:
        return f"chatflows/{flow_uuid(flow_id)}"

    def list_flows(self):
        return self._request("GET", "chatflows")

    def get_flow(self, flow_id: str):
        return self._request("GET", self._flow_route(flow_id))

    def create_flow(self, name: str, graph: dict, flow_type: str):
        return self._request(
            "POST", "chatflows",
            payload={"name": name, "type": flow_type, "flowData": json.dumps(graph)},
        )

    def update_flow(self, flow_id: str, changes: dict):
        return self._request("PUT", self._flow_route(flow_id), payload=changes)

    def predict(self, flow_id: str, question: str):
        return self._request(
            "POST", f"prediction/{flow_uuid(flow_id)}",
            payload={"question": question, "streaming": False}, prediction=True,
        )


def _finite_number(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise FlowiseError("Graph numbers must be finite.")
    return number


def parse_graph(contents: str) -> dict:
    try:
        graph = json.loads(contents, parse_float=_finite_number, parse_constant=_finite_number)
    except (TypeError, ValueError) as error:
        raise FlowiseError("Expected valid Flowise graph JSON.") from error
    if not isinstance(graph, dict) or not all(isinstance(graph.get(key), list) for key in ("nodes", "edges")):
        raise FlowiseError("Expected an exported Flowise graph with nodes and edges arrays.")
    return graph


def read_graph(path: Path) -> dict:
    try:
        contents = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise FlowiseError(f"Could not read graph JSON from {path}.") from error
    return parse_graph(contents)
