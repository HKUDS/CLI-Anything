"""DNS rewrite rules for AdGuardHome."""

from cli_anything.adguardhome.utils.adguardhome_backend import AdGuardHomeClient


def list_rewrites(client: AdGuardHomeClient) -> list:
    return client.get("/rewrite/list")


def add_rewrite(client: AdGuardHomeClient, domain: str, answer: str) -> dict:
    return client.post("/rewrite/add", {"domain": domain, "answer": answer})


def delete_rewrite(client: AdGuardHomeClient, domain: str, answer: str) -> dict:
    return client.post("/rewrite/delete", {"domain": domain, "answer": answer})
