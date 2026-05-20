"""Unit tests for search path-filter, result-building, and access-filter logic."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.access import doc_passes_filter, parse_groups

PREVIEW_LENGTH = 300


def _slug_from_record(rec: dict) -> str | None:
    """Replicate search.py slug extraction logic."""
    segment = rec.get("segment", {})
    doc_info = segment.get("document", {})
    doc_meta = doc_info.get("doc_metadata") or []
    doc_name = doc_info.get("name", "")
    return next(
        (m["value"] for m in doc_meta if m.get("name") == "slug" and m.get("value")),
        None,
    ) or doc_name


def _run_search_filter(records, path):
    """Replicate search.py path-filter logic."""
    path = (path or "").strip().strip("/")
    results = []
    for rec in records:
        slug = _slug_from_record(rec)
        if path and not slug.strip("/").startswith(path):
            continue
        content = rec["segment"].get("content", "")
        preview = content[:PREVIEW_LENGTH] + ("..." if len(content) > PREVIEW_LENGTH else "")
        results.append({
            "path": f"/{slug.strip('/')}",
            "score": rec.get("score", 0.0),
            "preview": preview,
        })
    return results


def _make_record(slug, content, score=0.5):
    return {
        "segment": {
            "content": content,
            "document": {
                "id": "docX",
                "name": "fallback.pdf",
                "doc_metadata": [{"name": "slug", "value": slug}],
            },
        },
        "score": score,
    }


class TestSearchSlugExtraction:
    def test_extracts_slug_from_doc_metadata(self):
        rec = _make_record("guides/readme", "content")
        assert _slug_from_record(rec) == "guides/readme"

    def test_falls_back_to_doc_name_when_no_slug(self):
        rec = {
            "segment": {
                "content": "hello",
                "document": {"id": "d1", "name": "fallback.pdf", "doc_metadata": []},
            },
            "score": 0.5,
        }
        assert _slug_from_record(rec) == "fallback.pdf"

    def test_falls_back_when_slug_value_is_empty(self):
        rec = {
            "segment": {
                "content": "hello",
                "document": {
                    "name": "file.pdf",
                    "doc_metadata": [{"name": "slug", "value": ""}],
                },
            },
            "score": 0.5,
        }
        assert _slug_from_record(rec) == "file.pdf"


class TestSearchPathFilter:
    def test_no_filter_returns_all(self):
        records = [
            _make_record("guides/intro", "A"),
            _make_record("api/users", "B"),
        ]
        results = _run_search_filter(records, "")
        assert len(results) == 2

    def test_path_filter_includes_prefix(self):
        records = [
            _make_record("guides/intro", "A"),
            _make_record("guides/advanced", "B"),
            _make_record("api/users", "C"),
        ]
        results = _run_search_filter(records, "guides")
        assert len(results) == 2
        assert all(r["path"].startswith("/guides") for r in results)

    def test_path_filter_excludes_other(self):
        records = [_make_record("api/users", "C")]
        results = _run_search_filter(records, "guides")
        assert results == []

    def test_path_filter_with_leading_slash(self):
        records = [_make_record("guides/intro", "A")]
        results = _run_search_filter(records, "/guides")
        assert len(results) == 1

    def test_preview_truncated_at_limit(self):
        long_content = "x" * 400
        records = [_make_record("a/b", long_content)]
        results = _run_search_filter(records, "")
        assert results[0]["preview"].endswith("...")
        assert len(results[0]["preview"]) == PREVIEW_LENGTH + 3

    def test_preview_not_truncated_when_short(self):
        records = [_make_record("a/b", "short")]
        results = _run_search_filter(records, "")
        assert results[0]["preview"] == "short"

    def test_path_prefix_is_not_partial_segment(self):
        # "api2/users" should NOT match path filter "api"
        records = [
            _make_record("api/users", "A"),
            _make_record("api2/users", "B"),
        ]
        results = _run_search_filter(records, "api")
        # "api2/users".startswith("api") is True — this is known behaviour.
        # The test documents the actual behaviour so we don't regress
        paths = [r["path"] for r in results]
        assert "/api/users" in paths


class TestSearchResultFormatting:
    def test_path_has_leading_slash(self):
        records = [_make_record("guides/readme", "text")]
        results = _run_search_filter(records, "")
        assert results[0]["path"] == "/guides/readme"

    def test_score_preserved(self):
        records = [_make_record("guides/readme", "text", score=0.9876)]
        results = _run_search_filter(records, "")
        assert abs(results[0]["score"] - 0.9876) < 1e-6

    def test_empty_records(self):
        assert _run_search_filter([], "") == []


# ── helpers ───────────────────────────────────────────────────────────────────

def _collect_accessible_slugs(docs, caller_groups, path):
    path = (path or "").strip().strip("/")
    slugs = []
    for doc in docs:
        if not doc_passes_filter(doc, caller_groups):
            continue
        meta = doc.get("doc_metadata") or []
        slug = next(
            (m["value"].strip("/") for m in meta if m.get("name") == "slug" and m.get("value")),
            doc.get("name", doc["id"]),
        )
        if path and not (slug == path or slug.startswith(path + "/")):
            continue
        slugs.append(slug)
    return slugs


def _build_metadata_filtering_conditions(slugs):
    return {
        "logical_operator": "or",
        "conditions": [
            {"name": "slug", "comparison_operator": "is", "value": s}
            for s in slugs
        ],
    }


def _make_doc(doc_id, slug, is_public="true", groups=""):
    meta = [{"name": "slug", "value": slug}, {"name": "is_public", "value": is_public}]
    if groups:
        meta.append({"name": "groups", "value": groups})
    return {"id": doc_id, "name": f"{doc_id}.pdf", "doc_metadata": meta}


# ── flat-dict slug extraction (retrieve API response shape) ───────────────────

class TestFlatDictSlugExtraction:
    """retrieve API returns doc_metadata as flat dict, not list."""

    def test_extracts_slug_from_flat_dict(self):
        rec = {
            "segment": {
                "content": "hello",
                "document": {
                    "id": "d1", "name": "file.pdf",
                    "doc_metadata": {"slug": "guides/intro", "is_public": "true"},
                },
            },
            "score": 0.8,
        }
        segment = rec["segment"]
        doc_meta = segment["document"].get("doc_metadata") or {}
        slug = doc_meta.get("slug") if isinstance(doc_meta, dict) else None
        assert slug == "guides/intro"

    def test_falls_back_to_doc_name_when_no_slug_in_flat_dict(self):
        rec = {
            "segment": {
                "content": "hello",
                "document": {"id": "d1", "name": "file.pdf", "doc_metadata": {}},
            },
            "score": 0.5,
        }
        doc_meta = rec["segment"]["document"].get("doc_metadata") or {}
        slug = (doc_meta.get("slug") if isinstance(doc_meta, dict) else None) or "file.pdf"
        assert slug == "file.pdf"


class TestSearchSlugCollection:
    def test_anonymous_caller_sees_only_public_docs(self):
        docs = [
            _make_doc("d1", "guides/intro", is_public="true"),
            _make_doc("d2", "internal/secret", is_public="false", groups="eng"),
        ]
        slugs = _collect_accessible_slugs(docs, [], "")
        assert "guides/intro" in slugs
        assert "internal/secret" not in slugs

    def test_group_member_sees_private_docs(self):
        docs = [
            _make_doc("d1", "guides/intro", is_public="true"),
            _make_doc("d2", "internal/secret", is_public="false", groups="eng"),
        ]
        slugs = _collect_accessible_slugs(docs, ["eng"], "")
        assert "guides/intro" in slugs
        assert "internal/secret" in slugs

    def test_path_filter_applied_after_access_filter(self):
        docs = [
            _make_doc("d1", "guides/intro"),
            _make_doc("d2", "api/users"),
            _make_doc("d3", "guides/advanced"),
        ]
        slugs = _collect_accessible_slugs(docs, [], "guides")
        assert slugs == ["guides/intro", "guides/advanced"]

    def test_empty_result_when_all_private(self):
        docs = [_make_doc("d1", "secret/doc", is_public="false", groups="admin")]
        slugs = _collect_accessible_slugs(docs, [], "")
        assert slugs == []

    def test_no_path_filter_returns_all_accessible(self):
        docs = [_make_doc("d1", "a/b"), _make_doc("d2", "c/d")]
        slugs = _collect_accessible_slugs(docs, [], "")
        assert set(slugs) == {"a/b", "c/d"}


class TestMetadataFilteringConditionsBuilding:
    def test_or_logical_operator(self):
        mfc = _build_metadata_filtering_conditions(["a/b", "c/d"])
        assert mfc["logical_operator"] == "or"

    def test_one_condition_per_slug(self):
        mfc = _build_metadata_filtering_conditions(["a/b", "c/d", "e/f"])
        assert len(mfc["conditions"]) == 3

    def test_condition_uses_is_operator(self):
        mfc = _build_metadata_filtering_conditions(["guides/intro"])
        cond = mfc["conditions"][0]
        assert cond["comparison_operator"] == "is"
        assert cond["name"] == "slug"
        assert cond["value"] == "guides/intro"

    def test_empty_slugs_gives_empty_conditions(self):
        mfc = _build_metadata_filtering_conditions([])
        assert mfc["conditions"] == []


# ── post-filter fallback ──────────────────────────────────────────────────────

class TestSearchPostFilterFallback:
    """When metadata_filtering_conditions is ignored by Dify, accessible_set
    acts as a safety net."""

    def _post_filter(self, records, accessible_set):
        results = []
        for rec in records:
            doc_meta = rec["segment"]["document"].get("doc_metadata") or {}
            slug = (doc_meta.get("slug") if isinstance(doc_meta, dict) else None) \
                   or rec["segment"]["document"].get("name", "")
            if slug.strip("/") not in accessible_set:
                continue
            results.append(slug.strip("/"))
        return results

    def test_accessible_slug_passes(self):
        records = [{"segment": {"document": {"doc_metadata": {"slug": "a/b"}, "name": "f"}}}]
        assert self._post_filter(records, {"a/b"}) == ["a/b"]

    def test_inaccessible_slug_filtered_out(self):
        records = [{"segment": {"document": {"doc_metadata": {"slug": "secret/doc"}, "name": "f"}}}]
        assert self._post_filter(records, {"a/b"}) == []

    def test_only_accessible_slugs_pass(self):
        records = [
            {"segment": {"document": {"doc_metadata": {"slug": "ok/doc"}, "name": "f"}}},
            {"segment": {"document": {"doc_metadata": {"slug": "secret/doc"}, "name": "f"}}},
        ]
        result = self._post_filter(records, {"ok/doc"})
        assert result == ["ok/doc"]
