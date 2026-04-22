"""Integration tests for grep against live Dify API."""
import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from tools.dify_client import DifyClient
from tools.grep import _grep_segments

ENDPOINT = os.getenv("DIFY_ENDPOINT", "http://127.0.0.1/v1")
API_KEY  = os.getenv("DIFY_API_KEY",  "dataset-uIvjo17wedfNvtWHBOl9gbaM")
DS_ID    = os.getenv("DIFY_DATASET_ID", "6005ef70-64f9-42a4-bdf2-65abbf85577b")
SLUG     = "ielts/task2"


@pytest.fixture(scope="module")
def client():
    return DifyClient(ENDPOINT, API_KEY)


# ── Single-file mode ──────────────────────────────────────────────────────────

class TestGrepSingleFile:
    def test_finds_doc_by_slug(self, client):
        doc = client.find_doc_by_slug(DS_ID, SLUG)
        assert doc is not None

    def test_grep_known_word_in_file(self, client):
        doc = client.find_doc_by_slug(DS_ID, SLUG)
        segs = client.get_segments(DS_ID, doc["id"])
        pattern = re.compile("IELTS", re.IGNORECASE)
        results = _grep_segments(segs, pattern, SLUG)
        assert len(results) > 0

    def test_each_result_has_required_fields(self, client):
        doc = client.find_doc_by_slug(DS_ID, SLUG)
        segs = client.get_segments(DS_ID, doc["id"])
        pattern = re.compile("IELTS", re.IGNORECASE)
        results = _grep_segments(segs, pattern, SLUG)
        for r in results:
            assert "path" in r
            assert "line_num" in r
            assert "line" in r
            assert isinstance(r["line_num"], int)
            assert r["line_num"] >= 1

    def test_every_result_line_actually_matches(self, client):
        """Fine filter guarantee: every returned line must match the pattern."""
        doc = client.find_doc_by_slug(DS_ID, SLUG)
        segs = client.get_segments(DS_ID, doc["id"])
        pattern = re.compile("IELTS", re.IGNORECASE)
        results = _grep_segments(segs, pattern, SLUG)
        for r in results:
            assert pattern.search(r["line"]), f"Line does not match: {r['line']}"

    def test_no_match_returns_empty(self, client):
        doc = client.find_doc_by_slug(DS_ID, SLUG)
        segs = client.get_segments(DS_ID, doc["id"])
        pattern = re.compile("xyzzy_never_exists_12345")
        results = _grep_segments(segs, pattern, SLUG)
        assert results == []

    def test_path_format_correct(self, client):
        doc = client.find_doc_by_slug(DS_ID, SLUG)
        segs = client.get_segments(DS_ID, doc["id"])
        pattern = re.compile("IELTS", re.IGNORECASE)
        results = _grep_segments(segs, pattern, SLUG)
        assert all(r["path"].startswith("/") for r in results)
        assert all(SLUG in r["path"] for r in results)

    def test_single_file_more_results_than_directory_mode(self, client):
        """Single-file fetches all segments → more complete than top_k=50 directory mode."""
        doc = client.find_doc_by_slug(DS_ID, SLUG)
        segs_all = client.get_segments(DS_ID, doc["id"])
        pattern = re.compile("IELTS", re.IGNORECASE)

        # Single-file: all segments
        results_full = _grep_segments(segs_all, pattern, SLUG)

        # Directory mode simulation: only top 50 segments from retrieve
        records = client.retrieve(DS_ID, "IELTS", "full_text_search", 50)
        segs_coarse = [r["segment"] for r in records]
        results_coarse = _grep_segments(segs_coarse, pattern, SLUG)

        # Single-file always >= directory mode in terms of results
        assert len(results_full) >= len(results_coarse)


# ── Directory mode ────────────────────────────────────────────────────────────

class TestGrepDirectoryMode:
    def test_retrieve_returns_segments_with_content(self, client):
        records = client.retrieve(DS_ID, "writing", "full_text_search", 10)
        assert len(records) > 0
        for r in records:
            assert "segment" in r
            assert "content" in r["segment"]

    def test_grep_on_retrieve_results(self, client):
        records = client.retrieve(DS_ID, "IELTS", "full_text_search", 20)
        pattern = re.compile("IELTS", re.IGNORECASE)
        all_results = []
        for rec in records:
            seg = rec["segment"]
            slug = SLUG  # we know it's this doc
            all_results.extend(_grep_segments([seg], pattern, slug))
        assert len(all_results) > 0

    def test_every_directory_result_matches_pattern(self, client):
        records = client.retrieve(DS_ID, "writing", "full_text_search", 20)
        pattern = re.compile("writing", re.IGNORECASE)
        for rec in records:
            seg = rec["segment"]
            results = _grep_segments([seg], pattern, "test")
            for r in results:
                assert pattern.search(r["line"]), f"Line does not match: {r['line']}"

    def test_path_prefix_filter(self, client):
        records = client.retrieve(DS_ID, "IELTS", "full_text_search", 20)
        pattern = re.compile("IELTS", re.IGNORECASE)
        path = "ielts"
        results = []
        for rec in records:
            seg = rec["segment"]
            doc_info = seg.get("document", {})
            doc_meta = doc_info.get("doc_metadata") or {}
            # retrieve API returns doc_metadata as flat dict
            slug = doc_meta.get("slug") or doc_info.get("name", "")
            if slug.strip("/").startswith(path):
                results.extend(_grep_segments([seg], pattern, slug))

        assert all(r["path"].startswith("/ielts") for r in results)


# ── Output format ─────────────────────────────────────────────────────────────

class TestGrepOutputFormat:
    def test_output_format_path_linenum_line(self, client):
        """Output must be: /path:lineNum — line"""
        doc = client.find_doc_by_slug(DS_ID, SLUG)
        segs = client.get_segments(DS_ID, doc["id"])
        pattern = re.compile("IELTS", re.IGNORECASE)
        results = _grep_segments(segs, pattern, SLUG)

        for r in results:
            formatted = f"{r['path']}:{r['line_num']} — {r['line']}"
            # Must start with /slug:number —
            assert formatted.startswith(f"/{SLUG}:")
            parts = formatted.split(" — ", 1)
            assert len(parts) == 2
            loc = parts[0]
            assert ":" in loc
            linenum_str = loc.split(":")[-1]
            assert linenum_str.isdigit()
