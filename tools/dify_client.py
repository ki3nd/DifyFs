from __future__ import annotations

from typing import Any

import requests


class DifyClient:
    def __init__(self, endpoint: str, api_key: str, timeout: int = 30):
        self.base = endpoint.rstrip("/")
        self.headers = {"Authorization": f"Bearer {api_key}"}
        self.timeout = timeout

    def _get(self, path: str, params: dict | None = None) -> Any:
        resp = requests.get(
            f"{self.base}{path}",
            headers=self.headers,
            params=params or {},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict) -> Any:
        resp = requests.post(
            f"{self.base}{path}",
            headers={**self.headers, "Content-Type": "application/json"},
            json=body,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Documents ──────────────────────────────────────────────────────────────

    def list_documents(self, dataset_id: str) -> list[dict]:
        """Paginate through all documents in a dataset."""
        docs = []
        page = 1
        while True:
            data = self._get(
                f"/datasets/{dataset_id}/documents",
                {"page": page, "limit": 100},
            )
            docs.extend(data.get("data", []))
            if not data.get("has_more", False):
                break
            page += 1
        return docs

    def get_segments(self, dataset_id: str, document_id: str) -> list[dict]:
        """Paginate through all segments of a document, sorted by position."""
        segments = []
        page = 1
        while True:
            data = self._get(
                f"/datasets/{dataset_id}/documents/{document_id}/segments",
                {"page": page, "limit": 100},
            )
            segments.extend(data.get("data", []))
            if not data.get("has_more", False):
                break
            page += 1
        segments.sort(key=lambda s: s.get("position", 0))
        return segments

    def retrieve(
        self,
        dataset_id: str,
        query: str,
        search_method: str = "semantic_search",
        top_k: int = 5,
        metadata_filtering_conditions: dict | None = None,
    ) -> list[dict]:
        """Call the retrieve endpoint and return records.

        metadata_filtering_conditions is passed as-is inside retrieval_model.
        """
        retrieval_model: dict = {
            "search_method": search_method,
            "top_k": top_k,
            "reranking_enable": False,
            "score_threshold_enabled": False,
        }
        if metadata_filtering_conditions:
            retrieval_model["metadata_filtering_conditions"] = metadata_filtering_conditions
        data = self._post(
            f"/datasets/{dataset_id}/retrieve",
            {"query": query, "retrieval_model": retrieval_model},
        )
        return data.get("records", [])

    # ── Metadata ───────────────────────────────────────────────────────────────

    def get_metadata_fields(self, dataset_id: str) -> list[dict]:
        data = self._get(f"/datasets/{dataset_id}/metadata")
        return data.get("doc_metadata", [])

    def ensure_metadata_field(self, dataset_id: str, key: str) -> str:
        """Return field id for key, creating it if it doesn't exist."""
        fields = self.get_metadata_fields(dataset_id)
        for f in fields:
            if f["name"] == key:
                return f["id"]
        created = self._post(
            f"/datasets/{dataset_id}/metadata",
            {"type": "string", "name": key},
        )
        return created["id"]

    def get_document_info(self, dataset_id: str, document_id: str) -> dict:
        """Fetch a single document including its current metadata entries."""
        return self._get(f"/datasets/{dataset_id}/documents/{document_id}")

    def update_document_metadata(
        self, dataset_id: str, document_id: str, metadata_list: list[dict]
    ) -> None:
        """Replace the full metadata of a document in one call.

        Each entry in ``metadata_list`` should be ``{"id": ..., "name": ..., "value": ...}``.
        Dify will auto-create any field that does not yet have an id.
        """
        self._post(
            f"/datasets/{dataset_id}/documents/metadata",
            {
                "operation_data": [
                    {
                        "document_id": document_id,
                        "metadata_list": metadata_list,
                    }
                ]
            },
        )

    # ── Helpers ────────────────────────────────────────────────────────────────

    def get_slug(self, doc: dict) -> str:
        """Extract slug from doc_metadata, fallback to document name.

        Handles both API response formats:
        - list_documents: doc_metadata = [{name, value}, ...]
        - retrieve:       doc_metadata = {"slug": "...", ...}  (flat dict)
        """
        metadata = doc.get("doc_metadata") or []
        if isinstance(metadata, dict):
            slug = metadata.get("slug")
            if slug:
                return slug.strip("/")
        else:
            for m in metadata:
                if m.get("name") == "slug" and m.get("value"):
                    return m["value"].strip("/")
        return doc.get("name", doc["id"])

    def find_doc_by_slug(self, dataset_id: str, slug: str) -> dict | None:
        """Find a document whose slug matches (exact, normalized)."""
        slug = slug.strip("/")
        for doc in self.list_documents(dataset_id):
            if self.get_slug(doc) == slug:
                return doc
        return None
