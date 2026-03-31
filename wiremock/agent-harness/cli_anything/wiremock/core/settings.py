from cli_anything.wiremock.utils.client import WireMockClient


class SettingsManager:
    def __init__(self, client: WireMockClient):
        self.client = client

    def get(self) -> dict:
        r = self.client.get("/settings")
        r.raise_for_status()
        return r.json()

    def update(self, settings: dict) -> dict:
        r = self.client.put("/settings", json=settings)
        r.raise_for_status()
        return r.json()

    def get_version(self) -> dict:
        r = self.client.get("/version")
        r.raise_for_status()
        return r.json()
