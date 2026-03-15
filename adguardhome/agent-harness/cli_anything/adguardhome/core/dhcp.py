"""DHCP server management for AdGuardHome."""

from cli_anything.adguardhome.utils.adguardhome_backend import AdGuardHomeClient


def get_status(client: AdGuardHomeClient) -> dict:
    return client.get("/dhcp/status")


def get_leases(client: AdGuardHomeClient) -> dict:
    return client.get("/dhcp/leases")


def add_static_lease(client: AdGuardHomeClient, mac: str, ip: str,
                     hostname: str) -> dict:
    return client.post("/dhcp/add_static_lease", {
        "mac": mac, "ip": ip, "hostname": hostname,
    })


def remove_static_lease(client: AdGuardHomeClient, mac: str, ip: str,
                        hostname: str) -> dict:
    return client.post("/dhcp/remove_static_lease", {
        "mac": mac, "ip": ip, "hostname": hostname,
    })
