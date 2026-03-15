"""Blocking controls: parental, safebrowsing, safesearch, blocked services."""

from cli_anything.adguardhome.utils.adguardhome_backend import AdGuardHomeClient


def parental_status(client: AdGuardHomeClient) -> dict:
    return client.get("/parental/status")


def parental_enable(client: AdGuardHomeClient) -> dict:
    return client.post("/parental/enable")


def parental_disable(client: AdGuardHomeClient) -> dict:
    return client.post("/parental/disable")


def safebrowsing_status(client: AdGuardHomeClient) -> dict:
    return client.get("/safebrowsing/status")


def safebrowsing_enable(client: AdGuardHomeClient) -> dict:
    return client.post("/safebrowsing/enable")


def safebrowsing_disable(client: AdGuardHomeClient) -> dict:
    return client.post("/safebrowsing/disable")


def safesearch_status(client: AdGuardHomeClient) -> dict:
    return client.get("/safesearch/status")


def safesearch_enable(client: AdGuardHomeClient) -> dict:
    return client.post("/safesearch/enable")


def safesearch_disable(client: AdGuardHomeClient) -> dict:
    return client.post("/safesearch/disable")


def blocked_services_get(client: AdGuardHomeClient) -> dict:
    return client.get("/blocked_services/get")


def blocked_services_set(client: AdGuardHomeClient, services: list[str]) -> dict:
    return client.post("/blocked_services/set", {"ids": services})
