from urllib.parse import quote

from cli_anything.wiremock.utils.client import WireMockClient


class ScenariosManager:
    def __init__(self, client: WireMockClient):
        self.client = client

    def list(self) -> dict:
        r = self.client.get("/scenarios")
        r.raise_for_status()
        return r.json()

    def reset_all(self) -> None:
        r = self.client.post("/scenarios/reset")
        r.raise_for_status()

    def set_state(self, name: str, state: str) -> None:
        r = self.client.put(f"/scenarios/{quote(name, safe='')}/state", json={"state": state})
        r.raise_for_status()
