"""Unit tests for ls tree-building logic — the PathTree equivalent."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.ls import _build_tree, _normalize_path
from tools.dify_client import DifyClient
from unittest.mock import MagicMock


def _mock_client(slugs: list[str]) -> DifyClient:
    client = MagicMock(spec=DifyClient)
    client.get_slug = DifyClient.get_slug.__get__(client, DifyClient)
    # Map each slug to a fake doc
    docs = [
        {"id": f"doc{i}", "name": f"doc{i}.pdf",
         "doc_metadata": [{"name": "slug", "value": s}]}
        for i, s in enumerate(slugs)
    ]
    client.get_slug = lambda doc: DifyClient.get_slug(client, doc)
    # Bind real get_slug
    real_client = DifyClient("http://x/v1", "k")
    client.get_slug = real_client.get_slug
    return client, docs


class TestNormalizePath:
    def test_empty_string(self):
        assert _normalize_path("") == ""

    def test_slash_only(self):
        assert _normalize_path("/") == ""

    def test_strips_slashes(self):
        assert _normalize_path("/guides/") == "guides"

    def test_inner_path(self):
        assert _normalize_path("guides/api") == "guides/api"

    def test_none_treated_as_empty(self):
        assert _normalize_path(None or "") == ""


class TestBuildTree:
    def _tree(self, slugs):
        real_client = DifyClient("http://x/v1", "k")
        docs = [
            {"id": f"doc{i}", "name": f"doc{i}",
             "doc_metadata": [{"name": "slug", "value": s}]}
            for i, s in enumerate(slugs)
        ]
        return _build_tree(docs, real_client)

    def test_flat_files_at_root(self):
        tree = self._tree(["readme", "changelog"])
        assert set(tree[""]) == {"readme", "changelog"}

    def test_single_nested(self):
        tree = self._tree(["guides/quickstart"])
        assert "guides/" in tree[""]
        assert "quickstart" in tree["guides"]

    def test_two_files_same_dir(self):
        tree = self._tree(["guides/quickstart", "guides/advanced"])
        assert "guides/" in tree[""]
        assert set(tree["guides"]) == {"quickstart", "advanced"}

    def test_deep_nesting(self):
        tree = self._tree(["api/v2/users/create"])
        assert "api/" in tree[""]
        assert "v2/" in tree["api"]
        assert "users/" in tree["api/v2"]
        assert "create" in tree["api/v2/users"]

    def test_sibling_dirs(self):
        tree = self._tree(["guides/intro", "api/users", "api/payments"])
        assert set(tree[""]) == {"guides/", "api/"}
        assert "intro" in tree["guides"]
        assert set(tree["api"]) == {"users", "payments"}

    def test_file_and_dir_same_prefix(self):
        # "api" as file AND "api/users" as nested
        tree = self._tree(["api", "api/users"])
        root = tree[""]
        assert "api" in root or "api/" in root  # api file at root
        assert "users" in tree.get("api", [])

    def test_fallback_name_used_as_slug(self):
        """Doc without slug uses name as path — should appear at root."""
        real_client = DifyClient("http://x/v1", "k")
        docs = [
            {"id": "d1", "name": "readme.pdf", "doc_metadata": []},
        ]
        tree = _build_tree(docs, real_client)
        assert "readme.pdf" in tree[""]

    def test_mixed_slugged_and_unslugged(self):
        real_client = DifyClient("http://x/v1", "k")
        docs = [
            {"id": "d1", "name": "readme.pdf",
             "doc_metadata": [{"name": "slug", "value": "guides/readme"}]},
            {"id": "d2", "name": "no-slug.pdf", "doc_metadata": []},
        ]
        tree = _build_tree(docs, real_client)
        assert "guides/" in tree[""]
        assert "no-slug.pdf" in tree[""]

    def test_dirs_suffixed_with_slash(self):
        tree = self._tree(["a/b/c"])
        assert "a/" in tree[""]
        assert "b/" in tree["a"]
        assert "c" in tree["a/b"]  # leaf has NO slash

    def test_sorted_entries(self):
        tree = self._tree(["z/file", "a/file", "m/file"])
        assert tree[""] == sorted(tree[""])
