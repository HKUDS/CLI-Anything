"""Server/global management for AdGuardHome."""

from cli_anything.adguardhome.utils.adguardhome_backend import AdGuardHomeClient


def get_status(client: AdGuardHomeClient) -> dict:
    return client.get("/status")


def get_version(client: AdGuardHomeClient) -> dict:
    return client.get("/version")


def restart(client: AdGuardHomeClient) -> dict:
    return client.post("/restart")


def get_tls_status(client: AdGuardHomeClient) -> dict:
    return client.get("/tls/status")
