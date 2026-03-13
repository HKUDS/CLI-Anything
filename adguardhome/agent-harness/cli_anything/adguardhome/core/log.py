"""Query log for AdGuardHome."""

from cli_anything.adguardhome.utils.adguardhome_backend import AdGuardHomeClient


def get_log(client: AdGuardHomeClient, limit: int = 100, offset: int = 0) -> dict:
    return client.get("/querylog", params={"limit": limit, "offset": offset})


def get_log_config(client: AdGuardHomeClient) -> dict:
    return client.get("/querylog_config")


def set_log_config(client: AdGuardHomeClient, enabled: bool,
                   interval: int = 90) -> dict:
    return client.post("/querylog_config", {
        "enabled": enabled,
        "interval": interval,
        "anonymize_client_ip": False,
    })


def clear_log(client: AdGuardHomeClient) -> dict:
    return client.post("/querylog_clear")
