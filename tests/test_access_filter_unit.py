"""Unit tests for tools/access.py — parse_groups, get_doc_visibility, doc_passes_filter."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from tools.access import parse_groups, get_doc_visibility, doc_passes_filter


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _doc(is_public=None, groups=None):
    metadata = []
    if is_public is not None:
        metadata.append({"name": "is_public", "value": str(is_public).lower()})
    if groups is not None:
        metadata.append({"name": "groups", "value": groups})
    return {"id": "d1", "name": "test", "doc_metadata": metadata}


# ---------------------------------------------------------------------------
# parse_groups
# ---------------------------------------------------------------------------

class TestParseGroups:
    def test_none_returns_empty(self):
        assert parse_groups(None) == []

    def test_empty_string_returns_empty(self):
        assert parse_groups("") == []

    def test_single_group(self):
        assert parse_groups("eng") == ["eng"]

    def test_multiple_groups(self):
        assert parse_groups("eng,legal") == ["eng", "legal"]

    def test_whitespace_around_commas(self):
        assert parse_groups("eng , legal") == ["eng", "legal"]

    def test_only_commas_returns_empty(self):
        assert parse_groups(",,") == []


# ---------------------------------------------------------------------------
# get_doc_visibility
# ---------------------------------------------------------------------------

class TestGetDocVisibility:
    def test_empty_metadata_list_defaults_to_public(self):
        doc = {"id": "d1", "name": "test", "doc_metadata": []}
        assert get_doc_visibility(doc) == (True, [])

    def test_list_of_objects_public_true_with_groups(self):
        doc = _doc(is_public="true", groups="eng")
        assert get_doc_visibility(doc) == (True, ["eng"])

    def test_list_of_objects_public_false(self):
        doc = _doc(is_public="false")
        is_public, groups = get_doc_visibility(doc)
        assert is_public is False
        assert groups == []

    def test_flat_dict_public_false_multiple_groups(self):
        doc = {
            "id": "d1",
            "name": "test",
            "doc_metadata": {"is_public": "false", "groups": "eng,admin"},
        }
        assert get_doc_visibility(doc) == (False, ["eng", "admin"])

    def test_flat_dict_missing_is_public_defaults_to_true(self):
        doc = {
            "id": "d1",
            "name": "test",
            "doc_metadata": {"groups": "eng"},
        }
        is_public, _ = get_doc_visibility(doc)
        assert is_public is True

    def test_is_public_zero_string_means_false(self):
        doc = _doc(is_public="0")
        is_public, _ = get_doc_visibility(doc)
        assert is_public is False


# ---------------------------------------------------------------------------
# doc_passes_filter
# ---------------------------------------------------------------------------

class TestDocPassesFilter:
    def test_public_doc_no_caller_groups(self):
        assert doc_passes_filter(_doc(is_public="true"), []) is True

    def test_public_doc_with_caller_groups(self):
        assert doc_passes_filter(_doc(is_public="true"), ["eng", "legal"]) is True

    def test_private_doc_no_caller_groups(self):
        assert doc_passes_filter(_doc(is_public="false", groups="eng"), []) is False

    def test_private_doc_matching_caller_group(self):
        assert doc_passes_filter(_doc(is_public="false", groups="eng"), ["eng"]) is True

    def test_private_doc_non_matching_caller_group(self):
        assert doc_passes_filter(_doc(is_public="false", groups="eng"), ["legal"]) is False

    def test_private_doc_partial_group_match(self):
        assert doc_passes_filter(_doc(is_public="false", groups="eng,admin"), ["admin"]) is True

    def test_doc_with_no_metadata_defaults_to_public(self):
        doc = {"id": "d1", "name": "test"}
        assert doc_passes_filter(doc, []) is True
