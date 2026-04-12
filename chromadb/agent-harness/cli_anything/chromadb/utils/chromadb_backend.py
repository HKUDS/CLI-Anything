"""ChromaDB HTTP API client.

Talks to ChromaDB server via its v2 REST API.
Default: http://localhost:8000
Tenant: default_tenant, Database: default_database
"""

import json
import requests


class ChromaDBBackend:
    """HTTP client for ChromaDB v2 API."""

    def __init__(self, base_url: str = "http://localhost:8000",
                 tenant: str = "default_tenant",
                 database: str = "default_database"):
        self.base_url = base_url.rstrip("/")
        self.tenant = tenant
        self.database = database
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    @property
    def _tenant_db_prefix(self) -> str:
        return f"{self.base_url}/api/v2/tenants/{self.tenant}/databases/{self.database}"

    # ── Server ────────────────────────────────────────────────────────

    def heartbeat(self) -> dict:
        """Check server health."""
        r = self._session.get(f"{self.base_url}/api/v2/heartbeat")
        r.raise_for_status()
        return r.json()

    def version(self) -> str:
        """Get server version."""
        r = self._session.get(f"{self.base_url}/api/v2/version")
        r.raise_for_status()
        return r.json()

    # ── Collections ───────────────────────────────────────────────────

    def list_collections(self) -> list[dict]:
        """List all collections."""
        r = self._session.get(f"{self._tenant_db_prefix}/collections")
        r.raise_for_status()
        return r.json()

    def create_collection(self, name: str, metadata: dict | None = None) -> dict:
        """Create a new collection."""
        body = {"name": name}
        if metadata:
            body["metadata"] = metadata
        r = self._session.post(
            f"{self._tenant_db_prefix}/collections",
            json=body,
        )
        r.raise_for_status()
        return r.json()

    def get_collection(self, name: str) -> dict:
        """Get collection info by name."""
        r = self._session.get(f"{self._tenant_db_prefix}/collections/{name}")
        r.raise_for_status()
        return r.json()

    def delete_collection(self, name: str) -> bool:
        """Delete a collection by name."""
        r = self._session.delete(f"{self._tenant_db_prefix}/collections/{name}")
        r.raise_for_status()
        return True

    # ── Documents ─────────────────────────────────────────────────────

    def add_documents(self, collection_id: str, ids: list[str],
                      documents: list[str],
                      metadatas: list[dict] | None = None,
                      embeddings: list[list[float]] | None = None) -> dict:
        """Add documents to a collection."""
        body: dict = {"ids": ids, "documents": documents}
        if metadatas:
            body["metadatas"] = metadatas
        if embeddings:
            body["embeddings"] = embeddings
        r = self._session.post(
            f"{self._tenant_db_prefix}/collections/{collection_id}/add",
            json=body,
        )
        r.raise_for_status()
        return r.json() if r.text else {"status": "ok"}

    def get_documents(self, collection_id: str, ids: list[str] | None = None,
                      limit: int | None = None,
                      offset: int | None = None) -> dict:
        """Get documents from a collection."""
        body: dict = {}
        if ids:
            body["ids"] = ids
        if limit is not None:
            body["limit"] = limit
        if offset is not None:
            body["offset"] = offset
        r = self._session.post(
            f"{self._tenant_db_prefix}/collections/{collection_id}/get",
            json=body,
        )
        r.raise_for_status()
        return r.json()

    def delete_documents(self, collection_id: str, ids: list[str]) -> dict:
        """Delete documents from a collection by IDs."""
        body = {"ids": ids}
        r = self._session.post(
            f"{self._tenant_db_prefix}/collections/{collection_id}/delete",
            json=body,
        )
        r.raise_for_status()
        return r.json() if r.text else {"status": "ok"}

    def count_documents(self, collection_id: str) -> int:
        """Count documents in a collection."""
        r = self._session.post(
            f"{self._tenant_db_prefix}/collections/{collection_id}/count",
            json={},
        )
        r.raise_for_status()
        return r.json()

    # ── Query ─────────────────────────────────────────────────────────

    def query(self, collection_id: str, query_texts: list[str],
              n_results: int = 5) -> dict:
        """Semantic search query against a collection."""
        body = {
            "query_texts": query_texts,
            "n_results": n_results,
        }
        r = self._session.post(
            f"{self._tenant_db_prefix}/collections/{collection_id}/query",
            json=body,
        )
        r.raise_for_status()
        return r.json()
