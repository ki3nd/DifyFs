"""Unit tests for DifyClient helper methods (no network calls)."""
import pytest
from unittest.mock import MagicMock, patch
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.dify_client import DifyClient


ENDPOINT = "http://127.0.0.1/v1"
API_KEY  = "dataset-test"


def make_client():
    return DifyClient(ENDPOINT, API_KEY)


# ── get_slug ───────────────────────────────────────────────────────────────────

class TestGetSlug:
    def test_returns_slug_from_doc_metadata(self):
        client = make_client()
        doc = {
            "id": "doc1",
            "name": "readme.pdf",
            "doc_metadata": [{"name": "slug", "value": "guides/readme"}],
        }
        assert client.get_slug(doc) == "guides/readme"

    def test_strips_leading_slash_from_slug(self):
        client = make_client()
        doc = {
            "id": "doc1",
            "name": "readme.pdf",
            "doc_metadata": [{"name": "slug", "value": "/guides/readme"}],
        }
        assert client.get_slug(doc) == "guides/readme"

    def test_falls_back_to_name_when_no_metadata(self):
        client = make_client()
        doc = {"id": "doc1", "name": "readme.pdf", "doc_metadata": None}
        assert client.get_slug(doc) == "readme.pdf"

    def test_falls_back_to_name_when_metadata_empty(self):
        client = make_client()
        doc = {"id": "doc1", "name": "readme.pdf", "doc_metadata": []}
        assert client.get_slug(doc) == "readme.pdf"

    def test_falls_back_to_name_when_slug_value_empty(self):
        client = make_client()
        doc = {
            "id": "doc1",
            "name": "readme.pdf",
            "doc_metadata": [{"name": "slug", "value": ""}],
        }
        assert client.get_slug(doc) == "readme.pdf"

    def test_falls_back_to_id_when_no_name(self):
        client = make_client()
        doc = {"id": "doc-xyz", "doc_metadata": []}
        assert client.get_slug(doc) == "doc-xyz"

    def test_ignores_other_metadata_keys(self):
        client = make_client()
        doc = {
            "id": "doc1",
            "name": "readme.pdf",
            "doc_metadata": [
                {"name": "isPublic", "value": "true"},
                {"name": "groups", "value": "[]"},
            ],
        }
        assert client.get_slug(doc) == "readme.pdf"

    def test_picks_slug_among_multiple_metadata(self):
        client = make_client()
        doc = {
            "id": "doc1",
            "name": "readme.pdf",
            "doc_metadata": [
                {"name": "isPublic", "value": "true"},
                {"name": "slug", "value": "api/reference"},
                {"name": "groups", "value": "[]"},
            ],
        }
        assert client.get_slug(doc) == "api/reference"


# ── find_doc_by_slug (mocked list_documents) ──────────────────────────────────

class TestFindDocBySlug:
    def _make_docs(self):
        return [
            {"id": "doc1", "name": "task2.pdf",
             "doc_metadata": [{"name": "slug", "value": "ielts/task2"}]},
            {"id": "doc2", "name": "framework.pdf",
             "doc_metadata": [{"name": "slug", "value": "memp/framework"}]},
            {"id": "doc3", "name": "no-slug.pdf", "doc_metadata": []},
        ]

    def test_finds_by_exact_slug(self):
        client = make_client()
        client.list_documents = MagicMock(return_value=self._make_docs())
        doc = client.find_doc_by_slug("ds1", "ielts/task2")
        assert doc["id"] == "doc1"

    def test_finds_by_slug_with_leading_slash(self):
        client = make_client()
        client.list_documents = MagicMock(return_value=self._make_docs())
        doc = client.find_doc_by_slug("ds1", "/ielts/task2")
        assert doc["id"] == "doc1"

    def test_returns_none_when_not_found(self):
        client = make_client()
        client.list_documents = MagicMock(return_value=self._make_docs())
        assert client.find_doc_by_slug("ds1", "nonexistent/path") is None

    def test_finds_doc_that_falls_back_to_name(self):
        client = make_client()
        client.list_documents = MagicMock(return_value=self._make_docs())
        doc = client.find_doc_by_slug("ds1", "no-slug.pdf")
        assert doc["id"] == "doc3"

    def test_slug_normalization_trailing_slash(self):
        client = make_client()
        client.list_documents = MagicMock(return_value=self._make_docs())
        doc = client.find_doc_by_slug("ds1", "ielts/task2/")
        assert doc["id"] == "doc1"


# ── ensure_metadata_field ─────────────────────────────────────────────────────

class TestEnsureMetadataField:
    def test_returns_existing_field_id_without_creating(self):
        client = make_client()
        client.get_metadata_fields = MagicMock(return_value=[
            {"id": "field-1", "name": "slug"},
            {"id": "field-2", "name": "isPublic"},
        ])
        client._post = MagicMock()

        fid = client.ensure_metadata_field("ds1", "slug")
        assert fid == "field-1"
        client._post.assert_not_called()

    def test_creates_field_when_not_exists(self):
        client = make_client()
        client.get_metadata_fields = MagicMock(return_value=[])
        client._post = MagicMock(return_value={"id": "new-field-id", "name": "slug"})

        fid = client.ensure_metadata_field("ds1", "slug")
        assert fid == "new-field-id"
        client._post.assert_called_once_with(
            "/datasets/ds1/metadata",
            {"type": "string", "name": "slug"},
        )

    def test_creates_field_when_other_fields_exist(self):
        client = make_client()
        client.get_metadata_fields = MagicMock(return_value=[
            {"id": "field-2", "name": "isPublic"},
        ])
        client._post = MagicMock(return_value={"id": "new-id", "name": "groups"})

        fid = client.ensure_metadata_field("ds1", "groups")
        assert fid == "new-id"


# ── get_segments ordering ─────────────────────────────────────────────────────

class TestGetSegments:
    def test_segments_sorted_by_position(self):
        client = make_client()
        client._get = MagicMock(return_value={
            "data": [
                {"id": "s3", "position": 3, "content": "C"},
                {"id": "s1", "position": 1, "content": "A"},
                {"id": "s2", "position": 2, "content": "B"},
            ],
            "has_more": False,
        })
        segs = client.get_segments("ds1", "doc1")
        assert [s["content"] for s in segs] == ["A", "B", "C"]

    def test_paginates_until_has_more_false(self):
        client = make_client()
        calls = [
            {"data": [{"id": "s1", "position": 1, "content": "A"}], "has_more": True},
            {"data": [{"id": "s2", "position": 2, "content": "B"}], "has_more": False},
        ]
        client._get = MagicMock(side_effect=calls)
        segs = client.get_segments("ds1", "doc1")
        assert len(segs) == 2
        assert client._get.call_count == 2
