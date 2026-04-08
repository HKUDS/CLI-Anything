from cli_anything.wiremock.utils.client import WireMockClient


class RecordingManager:
    def __init__(self, client: WireMockClient):
        self.client = client

    def start(self, target_url: str, headers_to_match: list = None) -> dict:
        spec = {"targetBaseUrl": target_url}
        if headers_to_match:
            spec["captureHeaders"] = {
                h: {"caseInsensitive": True} for h in headers_to_match
            }
        r = self.client.post("/recordings/start", json=spec)
        r.raise_for_status()
        return r.json()

    def stop(self) -> dict:
        r = self.client.post("/recordings/stop")
        r.raise_for_status()
        return r.json()

    def status(self) -> dict:
        r = self.client.get("/recordings/status")
        r.raise_for_status()
        return r.json()

    def snapshot(self, spec: dict = None) -> dict:
        r = self.client.post("/recordings/snapshot", json=spec or {})
        r.raise_for_status()
        return r.json()
