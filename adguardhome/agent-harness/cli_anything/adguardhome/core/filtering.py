"""Filtering rules management for AdGuardHome."""

from cli_anything.adguardhome.utils.adguardhome_backend import AdGuardHomeClient


def get_status(client: AdGuardHomeClient) -> dict:
    return client.get("/filtering/status")


def set_enabled(client: AdGuardHomeClient, enabled: bool) -> dict:
    current = get_status(client)
    interval = current.get("interval", 24)
    return client.post("/filtering/config", {"enabled": enabled, "interval": interval})


def add_filter(client: AdGuardHomeClient, url: str, name: str,
               whitelist: bool = False) -> dict:
    return client.post("/filtering/add_url", {
        "name": name,
        "url": url,
        "whitelist": whitelist,
    })


def remove_filter(client: AdGuardHomeClient, url: str, whitelist: bool = False) -> dict:
    return client.post("/filtering/remove_url", {"url": url, "whitelist": whitelist})


def set_filter_url(client: AdGuardHomeClient, url: str, name: str,
                   enabled: bool, whitelist: bool = False) -> dict:
    return client.post("/filtering/set_url", {
        "url": url,
        "data": {"name": name, "url": url, "enabled": enabled},
        "whitelist": whitelist,
    })


def refresh(client: AdGuardHomeClient, whitelist: bool = False) -> dict:
    return client.post("/filtering/refresh", {"whitelist": whitelist})
