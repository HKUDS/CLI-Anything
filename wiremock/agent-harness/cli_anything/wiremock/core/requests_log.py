from cli_anything.wiremock.utils.client import WireMockClient


class RequestsLog:
    def __init__(self, client: WireMockClient):
        self.client = client

    def list(self, limit: int = None, since: str = None) -> dict:
        params = {}
        if limit is not None:
            params["limit"] = limit
        if since is not None:
            params["since"] = since
        r = self.client.get("/requests", params=params)
        r.raise_for_status()
        return r.json()

    def get(self, request_id: str) -> dict:
        r = self.client.get(f"/requests/{request_id}")
        r.raise_for_status()
        return r.json()

    def reset(self) -> None:
        r = self.client.delete("/requests")
        r.raise_for_status()

    def find(self, pattern: dict) -> dict:
        r = self.client.post("/requests/find", json=pattern)
        r.raise_for_status()
        return r.json()

    def count(self, pattern: dict) -> dict:
        r = self.client.post("/requests/count", json=pattern)
        r.raise_for_status()
        return r.json()

    def unmatched(self) -> dict:
        r = self.client.get("/requests/unmatched")
        r.raise_for_status()
        return r.json()

    def near_misses_unmatched(self) -> dict:
        r = self.client.get("/requests/unmatched/near-misses")
        r.raise_for_status()
        return r.json()
