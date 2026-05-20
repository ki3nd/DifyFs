"""Unit tests for validate_metadata in tools/metadata_set.py.

DifyClient is never instantiated — only the pure validation helper is
exercised here.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from tools.metadata_set import validate_metadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(data: dict) -> dict:
    """Assert success and return the filtered dict."""
    parsed, err = validate_metadata(data)
    assert err is None, f"Expected success but got error: {err}"
    assert parsed is not None
    return parsed


def _err(data) -> str:
    """Assert failure and return the error message."""
    parsed, err = validate_metadata(data)
    assert err is not None, "Expected an error but got success"
    assert parsed is None
    return err


# ---------------------------------------------------------------------------
# Valid inputs
# ---------------------------------------------------------------------------

class TestValidInputs:
    def test_all_three_fields_present(self):
        result = _ok({"slug": "guides/quickstart", "is_public": "true", "groups": "eng,legal"})
        assert result == {"slug": "guides/quickstart", "is_public": "true", "groups": "eng,legal"}

    def test_empty_dict_is_valid(self):
        result = _ok({})
        assert result == {}

    def test_only_slug(self):
        result = _ok({"slug": "api/reference"})
        assert result == {"slug": "api/reference"}

    def test_is_public_false_with_groups(self):
        result = _ok({"is_public": "false", "groups": "eng"})
        assert result["is_public"] == "false"
        assert result["groups"] == "eng"

    def test_is_public_true_without_groups(self):
        """is_public=true does not require groups."""
        result = _ok({"is_public": "true"})
        assert result == {"is_public": "true"}

    def test_only_groups(self):
        result = _ok({"groups": "eng,legal"})
        assert result == {"groups": "eng,legal"}


# ---------------------------------------------------------------------------
# Unknown-key stripping
# ---------------------------------------------------------------------------

class TestUnknownKeyStripping:
    def test_unknown_keys_are_stripped(self):
        result = _ok({
            "slug": "guides/intro",
            "is_public": "true",
            "groups": "eng",
            "customField": "should be gone",
            "anotherExtra": 42,
        })
        assert set(result.keys()) == {"slug", "is_public", "groups"}
        assert "customField" not in result
        assert "anotherExtra" not in result

    def test_only_unknown_keys_yields_empty_dict(self):
        result = _ok({"foo": "bar", "baz": 123})
        assert result == {}


# ---------------------------------------------------------------------------
# Validation failures
# ---------------------------------------------------------------------------

class TestValidationFailures:
    def test_is_public_string_false_without_groups_is_error(self):
        err = _err({"is_public": "false"})
        assert "groups" in err.lower() or "is_public" in err

    def test_is_public_string_false_with_empty_string_groups_is_error(self):
        err = _err({"is_public": "false", "groups": ""})
        assert err  # any non-empty error message

    def test_is_public_bool_False_without_groups_is_error(self):
        err = _err({"is_public": False})
        assert err

    def test_is_public_bool_False_with_empty_string_groups_is_error(self):
        err = _err({"is_public": False, "groups": ""})
        assert err

    def test_is_public_bool_False_without_groups_key_is_error(self):
        """Bool False, groups key entirely absent."""
        err = _err({"is_public": False, "slug": "guides/intro"})
        assert err

    def test_non_dict_input_is_error(self):
        err = _err("not-a-dict")
        assert "dict" in err.lower()

    def test_list_input_is_error(self):
        err = _err(["slug", "is_public"])
        assert err

    def test_none_input_is_error(self):
        err = _err(None)
        assert err
