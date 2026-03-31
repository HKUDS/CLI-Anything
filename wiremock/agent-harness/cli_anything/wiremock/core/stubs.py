from cli_anything.wiremock.utils.client import WireMockClient
from typing import Optional


class StubsManager:
    def __init__(self, client: WireMockClient):
        self.client = client

    def list(self, limit: int = None, offset: int = None) -> dict:
        params = {}
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
        r = self.client.get("/mappings", params=params)
        r.raise_for_status()
        return r.json()

    def get(self, stub_id: str) -> dict:
        r = self.client.get(f"/mappings/{stub_id}")
        r.raise_for_status()
        return r.json()

    def create(self, mapping: dict) -> dict:
        r = self.client.post("/mappings", json=mapping)
        r.raise_for_status()
        return r.json()

    def update(self, stub_id: str, mapping: dict) -> dict:
        r = self.client.put(f"/mappings/{stub_id}", json=mapping)
        r.raise_for_status()
        return r.json()

    def delete(self, stub_id: str) -> None:
        r = self.client.delete(f"/mappings/{stub_id}")
        r.raise_for_status()

    def reset(self) -> None:
        r = self.client.post("/mappings/reset")
        r.raise_for_status()

    def save(self) -> None:
        r = self.client.post("/mappings/save")
        r.raise_for_status()

    def import_stubs(self, stubs: dict) -> dict:
        r = self.client.post("/mappings/import", json=stubs)
        r.raise_for_status()
        return r.json()

    def find_by_metadata(self, pattern: dict) -> dict:
        r = self.client.post("/mappings/find-by-metadata", json=pattern)
        r.raise_for_status()
        return r.json()

    def quick_stub(
        self,
        method: str,
        url: str,
        status: int,
        body: str = None,
        content_type: str = "application/json",
    ) -> dict:
        """Helper: create a simple stub quickly."""
        response = {"status": status}
        if body:
            response["body"] = body
            response["headers"] = {"Content-Type": content_type}
        mapping = {
            "request": {"method": method.upper(), "url": url},
            "response": response,
        }
        return self.create(mapping)
