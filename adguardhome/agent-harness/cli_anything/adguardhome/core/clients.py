"""Client management for AdGuardHome."""

from cli_anything.adguardhome.utils.adguardhome_backend import AdGuardHomeClient


def list_clients(client: AdGuardHomeClient) -> dict:
    return client.get("/clients")


def add_client(client: AdGuardHomeClient, name: str, ids: list[str],
               use_global_settings: bool = True,
               filtering_enabled: bool = True) -> dict:
    return client.post("/clients/add", {
        "name": name,
        "ids": ids,
        "use_global_settings": use_global_settings,
        "filtering_enabled": filtering_enabled,
        "parental_enabled": False,
        "safebrowsing_enabled": False,
        "safesearch_enabled": False,
        "use_global_blocked_services": True,
    })


def delete_client(client: AdGuardHomeClient, name: str) -> dict:
    return client.post("/clients/delete", {"name": name})


def update_client(client: AdGuardHomeClient, name: str, data: dict) -> dict:
    return client.post("/clients/update", {"name": name, "data": data})
