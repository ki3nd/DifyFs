"""Unit tests for find glob logic."""
import fnmatch
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.dify_client import DifyClient


def _make_docs(slug_map: dict[str, str]) -> list[dict]:
    return [
        {"id": did, "name": f"{did}.pdf",
         "doc_metadata": [{"name": "slug", "value": slug}]}
        for did, slug in slug_map.items()
    ]


def _run_find(docs, path, pattern):
    """Replicate find.py logic."""
    client = DifyClient("http://x/v1", "k")
    path = (path or "").strip().strip("/")
    matches = []
    for doc in docs:
        slug = client.get_slug(doc)
        if path and not slug.startswith(path):
            continue
        filename = slug.split("/")[-1]
        if fnmatch.fnmatch(filename, pattern):
            matches.append(slug)
    return sorted(matches)


class TestFindLogic:
    def test_match_all_pdf(self):
        docs = _make_docs({"d1": "guides/readme.pdf", "d2": "api/users.pdf", "d3": "changelog.txt"})
        result = _run_find(docs, "/", "*.pdf")
        assert result == ["api/users.pdf", "guides/readme.pdf"]

    def test_match_in_subdir(self):
        docs = _make_docs({"d1": "guides/readme.pdf", "d2": "api/users.pdf"})
        result = _run_find(docs, "guides", "*.pdf")
        assert result == ["guides/readme.pdf"]

    def test_wildcard_prefix(self):
        docs = _make_docs({"d1": "guides/quickstart", "d2": "guides/advanced", "d3": "api/quickstart"})
        result = _run_find(docs, "/", "*quick*")
        assert result == ["api/quickstart", "guides/quickstart"]

    def test_no_match(self):
        docs = _make_docs({"d1": "guides/readme.md"})
        result = _run_find(docs, "/", "*.pdf")
        assert result == []

    def test_path_filter_excludes_other_dirs(self):
        docs = _make_docs({"d1": "guides/intro", "d2": "api/intro"})
        result = _run_find(docs, "guides", "*")
        assert result == ["guides/intro"]

    def test_exact_filename_match(self):
        docs = _make_docs({"d1": "guides/readme", "d2": "guides/other"})
        result = _run_find(docs, "/", "readme")
        assert result == ["guides/readme"]

    def test_deep_nested_match(self):
        docs = _make_docs({"d1": "a/b/c/deep.md", "d2": "a/b/shallow.md"})
        result = _run_find(docs, "a/b", "*.md")
        assert result == ["a/b/c/deep.md", "a/b/shallow.md"]

    def test_empty_dataset(self):
        result = _run_find([], "/", "*.pdf")
        assert result == []

    def test_no_path_filter_matches_all_dirs(self):
        docs = _make_docs({"d1": "x/file.md", "d2": "y/file.md"})
        result = _run_find(docs, "", "*.md")
        assert result == ["x/file.md", "y/file.md"]
