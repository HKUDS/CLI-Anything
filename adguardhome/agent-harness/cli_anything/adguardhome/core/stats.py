"""Statistics for AdGuardHome."""

from cli_anything.adguardhome.utils.adguardhome_backend import AdGuardHomeClient


def get_stats(client: AdGuardHomeClient) -> dict:
    return client.get("/stats")


def reset_stats(client: AdGuardHomeClient) -> dict:
    return client.post("/stats_reset")


def get_stats_config(client: AdGuardHomeClient) -> dict:
    return client.get("/stats_config")


def set_stats_config(client: AdGuardHomeClient, interval: int) -> dict:
    return client.post("/stats_config", {"interval": interval})
