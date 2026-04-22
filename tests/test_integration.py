"""
Integration tests against live Dify API.
Requires: DIFY_ENDPOINT and DIFY_API_KEY env vars, or uses hardcoded test values.

Run: pytest tests/test_integration.py -v
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.dify_client import DifyClient

ENDPOINT = os.getenv("DIFY_ENDPOINT", "http://127.0.0.1/v1")
API_KEY  = os.getenv("DIFY_API_KEY",  "dataset-uIvjo17wedfNvtWHBOl9gbaM")
DS_ID    = os.getenv("DIFY_DATASET_ID", "6005ef70-64f9-42a4-bdf2-65abbf85577b")


@pytest.fixture(scope="module")
def client():
    return DifyClient(ENDPOINT, API_KEY)


@pytest.fixture(scope="module")
def docs(client):
    return client.list_documents(DS_ID)


# ── list_documents ─────────────────────────────────────────────────────────────

class TestListDocuments:
    def test_returns_list(self, client):
        docs = client.list_documents(DS_ID)
        assert isinstance(docs, list)
        assert len(docs) >= 1

    def test_each_doc_has_required_fields(self, client):
        for doc in client.list_documents(DS_ID):
            assert "id" in doc
            assert "name" in doc

    def test_pagination_returns_all_docs(self, client):
        """Verify paginator collects all docs (even if limit=1 per page)."""
        import unittest.mock as mock
        pages = [
            {"data": [{"id": "d1", "name": "a", "doc_metadata": []}], "has_more": True},
            {"data": [{"id": "d2", "name": "b", "doc_metadata": []}], "has_more": False},
        ]
        c2 = DifyClient(ENDPOINT, API_KEY)
        with mock.patch.object(c2, "_get", side_effect=pages):
            result = c2.list_documents("any")
        assert len(result) == 2
        assert result[0]["id"] == "d1"
        assert result[1]["id"] == "d2"


# ── metadata field management ─────────────────────────────────────────────────

class TestMetadataFields:
    def test_get_metadata_fields_returns_list(self, client):
        fields = client.get_metadata_fields(DS_ID)
        assert isinstance(fields, list)

    def test_ensure_slug_field_idempotent(self, client):
        """Calling ensure_metadata_field twice returns same id."""
        fid1 = client.ensure_metadata_field(DS_ID, "slug")
        fid2 = client.ensure_metadata_field(DS_ID, "slug")
        assert fid1 == fid2

    def test_ensure_creates_new_field(self, client):
        """Create a test field and verify it exists."""
        import time
        field_name = f"test_field_{int(time.time())}"
        fid = client.ensure_metadata_field(DS_ID, field_name)
        assert fid is not None
        fields = client.get_metadata_fields(DS_ID)
        names = [f["name"] for f in fields]
        assert field_name in names


# ── set + read metadata on document ──────────────────────────────────────────

class TestSetDocumentMetadata:
    def test_set_slug_and_read_back(self, client, docs):
        doc = docs[0]
        slug_val = "integration/test-doc"
        fid = client.ensure_metadata_field(DS_ID, "slug")
        client.set_document_metadata(DS_ID, doc["id"], fid, "slug", slug_val)

        updated_docs = client.list_documents(DS_ID)
        target = next(d for d in updated_docs if d["id"] == doc["id"])
        assert client.get_slug(target) == slug_val

    def test_overwrite_slug(self, client, docs):
        doc = docs[0]
        fid = client.ensure_metadata_field(DS_ID, "slug")

        client.set_document_metadata(DS_ID, doc["id"], fid, "slug", "old/path")
        client.set_document_metadata(DS_ID, doc["id"], fid, "slug", "new/path")

        updated_docs = client.list_documents(DS_ID)
        target = next(d for d in updated_docs if d["id"] == doc["id"])
        assert client.get_slug(target) == "new/path"


# ── find_doc_by_slug ───────────────────────────────────────────────────────────

class TestFindDocBySlug:
    def test_finds_doc_after_setting_slug(self, client, docs):
        doc = docs[0]
        slug = "findtest/doc-alpha"
        fid = client.ensure_metadata_field(DS_ID, "slug")
        client.set_document_metadata(DS_ID, doc["id"], fid, "slug", slug)

        found = client.find_doc_by_slug(DS_ID, slug)
        assert found is not None
        assert found["id"] == doc["id"]

    def test_returns_none_for_missing_slug(self, client):
        assert client.find_doc_by_slug(DS_ID, "this/does/not/exist") is None

    def test_finds_with_leading_slash(self, client, docs):
        doc = docs[0]
        slug = "findtest/doc-alpha"
        found = client.find_doc_by_slug(DS_ID, f"/{slug}")
        assert found is not None
        assert found["id"] == doc["id"]


# ── get_segments ──────────────────────────────────────────────────────────────

class TestGetSegments:
    def test_returns_segments_for_real_doc(self, client, docs):
        doc = docs[0]
        segs = client.get_segments(DS_ID, doc["id"])
        assert isinstance(segs, list)
        assert len(segs) >= 1

    def test_segments_have_content(self, client, docs):
        segs = client.get_segments(DS_ID, docs[0]["id"])
        for s in segs:
            assert "content" in s

    def test_segments_sorted_ascending_by_position(self, client, docs):
        segs = client.get_segments(DS_ID, docs[0]["id"])
        positions = [s.get("position", 0) for s in segs]
        assert positions == sorted(positions)

    def test_all_segments_fetched(self, client, docs):
        """Verify total segment count > 1 (confirms pagination works)."""
        segs = client.get_segments(DS_ID, docs[0]["id"])
        assert len(segs) > 1  # ieltsTask2.pdf has 194 segments

    def test_cat_content_is_full_join(self, client, docs):
        """cat = join all segment contents in order."""
        doc = docs[0]
        segs = client.get_segments(DS_ID, doc["id"])
        content = "\n\n".join(s["content"] for s in segs if s.get("content"))
        assert len(content) > 100
        # First chunk content must appear at start
        assert segs[0]["content"][:20] in content[:500]


# ── retrieve / search ─────────────────────────────────────────────────────────

class TestRetrieve:
    def test_full_text_search_returns_records(self, client):
        records = client.retrieve(DS_ID, "writing", "full_text_search", 5)
        assert isinstance(records, list)

    def test_records_have_segment(self, client):
        records = client.retrieve(DS_ID, "writing", "full_text_search", 3)
        for r in records:
            assert "segment" in r
            assert "content" in r["segment"]

    def test_top_k_respected(self, client):
        records = client.retrieve(DS_ID, "writing", "full_text_search", 2)
        assert len(records) <= 2

    def test_semantic_search(self, client):
        records = client.retrieve(DS_ID, "IELTS writing task", "semantic_search", 3)
        assert isinstance(records, list)


# ── ls tree end-to-end ────────────────────────────────────────────────────────

class TestLsEndToEnd:
    def test_ls_root_after_setting_slugs(self, client, docs):
        from tools.ls import _build_tree

        fid = client.ensure_metadata_field(DS_ID, "slug")
        client.set_document_metadata(DS_ID, docs[0]["id"], fid, "slug", "ielts/task2")
        if len(docs) > 1:
            client.set_document_metadata(DS_ID, docs[1]["id"], fid, "slug", "memp/framework")

        updated_docs = client.list_documents(DS_ID)
        tree = _build_tree(updated_docs, client)

        root = tree.get("", [])
        assert "ielts/" in root
        if len(docs) > 1:
            assert "memp/" in root

    def test_ls_subdir(self, client):
        from tools.ls import _build_tree
        updated_docs = client.list_documents(DS_ID)
        tree = _build_tree(updated_docs, client)

        assert "task2" in tree.get("ielts", [])

    def test_ls_nonexistent_path_empty(self, client):
        from tools.ls import _build_tree
        updated_docs = client.list_documents(DS_ID)
        tree = _build_tree(updated_docs, client)

        assert tree.get("nonexistent", []) == []


# ── find end-to-end ───────────────────────────────────────────────────────────

class TestFindEndToEnd:
    def test_find_all_docs(self, client):
        import fnmatch
        docs = client.list_documents(DS_ID)
        matches = []
        for doc in docs:
            slug = client.get_slug(doc)
            filename = slug.split("/")[-1]
            if fnmatch.fnmatch(filename, "*"):
                matches.append(slug)
        assert len(matches) == len(docs)

    def test_find_by_exact_name(self, client):
        import fnmatch
        docs = client.list_documents(DS_ID)
        matches = [
            client.get_slug(d) for d in docs
            if fnmatch.fnmatch(client.get_slug(d).split("/")[-1], "task2")
        ]
        assert len(matches) == 1
        assert matches[0] == "ielts/task2"

    def test_find_with_path_filter(self, client):
        import fnmatch
        docs = client.list_documents(DS_ID)
        path = "ielts"
        matches = [
            client.get_slug(d) for d in docs
            if client.get_slug(d).startswith(path)
            and fnmatch.fnmatch(client.get_slug(d).split("/")[-1], "*")
        ]
        assert all(m.startswith("ielts") for m in matches)


# ── cat end-to-end ────────────────────────────────────────────────────────────

class TestCatEndToEnd:
    def test_cat_returns_non_empty_content(self, client):
        doc = client.find_doc_by_slug(DS_ID, "ielts/task2")
        assert doc is not None
        segs = client.get_segments(DS_ID, doc["id"])
        content = "\n\n".join(s["content"] for s in segs if s.get("content"))
        assert len(content) > 0

    def test_cat_content_ordered(self, client):
        doc = client.find_doc_by_slug(DS_ID, "ielts/task2")
        segs = client.get_segments(DS_ID, doc["id"])
        # Verify first segment is position=1
        assert segs[0]["position"] == 1

    def test_cat_nonexistent_returns_none_doc(self, client):
        doc = client.find_doc_by_slug(DS_ID, "this/does/not/exist")
        assert doc is None
