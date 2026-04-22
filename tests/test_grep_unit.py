"""Unit tests for grep fine-filter logic."""
import re
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.grep import _grep_segments


def _pattern(s: str) -> re.Pattern:
    return re.compile(s, re.IGNORECASE)


def _seg(content: str) -> dict:
    return {"content": content}


class TestGrepSegments:
    def test_single_match(self):
        segs = [_seg("hello world\nno match here\naccess_token found")]
        r = _grep_segments(segs, _pattern("access_token"), "auth/oauth")
        assert len(r) == 1
        assert r[0]["line"] == "access_token found"
        assert r[0]["line_num"] == 3
        assert r[0]["path"] == "/auth/oauth"

    def test_multiple_lines_match(self):
        segs = [_seg("use access_token here\nno\naccess_token again")]
        r = _grep_segments(segs, _pattern("access_token"), "auth/oauth")
        assert len(r) == 2
        assert r[0]["line_num"] == 1
        assert r[1]["line_num"] == 3

    def test_multiple_segments(self):
        segs = [
            _seg("chunk one\naccess_token in chunk 1"),
            _seg("chunk two no match"),
            _seg("access_token in chunk 3\nend"),
        ]
        r = _grep_segments(segs, _pattern("access_token"), "auth/oauth")
        assert len(r) == 2

    def test_case_insensitive(self):
        segs = [_seg("ACCESS_TOKEN here\nAccess_Token here")]
        r = _grep_segments(segs, _pattern("access_token"), "p")
        assert len(r) == 2

    def test_no_match(self):
        segs = [_seg("no relevant content\nnothing here")]
        r = _grep_segments(segs, _pattern("access_token"), "p")
        assert r == []

    def test_empty_segment_skipped(self):
        segs = [{"content": ""}, _seg("access_token here")]
        r = _grep_segments(segs, _pattern("access_token"), "p")
        assert len(r) == 1

    def test_none_content_skipped(self):
        segs = [{"content": None}, _seg("access_token here")]
        r = _grep_segments(segs, _pattern("access_token"), "p")
        assert len(r) == 1

    def test_path_prefixed_with_slash(self):
        segs = [_seg("access_token")]
        r = _grep_segments(segs, _pattern("access_token"), "/auth/oauth")
        assert r[0]["path"] == "/auth/oauth"

    def test_path_without_slash_normalized(self):
        segs = [_seg("access_token")]
        r = _grep_segments(segs, _pattern("access_token"), "auth/oauth")
        assert r[0]["path"] == "/auth/oauth"

    def test_regex_pattern(self):
        segs = [_seg("date: 2026-04-22\nother line\ndate: 2025-01-01")]
        r = _grep_segments(segs, re.compile(r"\d{4}-\d{2}-\d{2}"), "doc")
        assert len(r) == 2

    def test_line_numbers_cumulative_across_segments(self):
        """Line numbers are cumulative across segments to match cat output (joined with \\n\\n)."""
        segs = [
            _seg("line1\naccess_token\nline3"),   # 3 lines + 2 blank = offset 5
            _seg("line1\nline2\naccess_token"),    # match at local line 3 → global line 5+3=8
        ]
        r = _grep_segments(segs, _pattern("access_token"), "p")
        assert r[0]["line_num"] == 2   # line 2 in seg 0
        assert r[1]["line_num"] == 8   # 3 lines + 2 (blank join) + 3 = line 8

    def test_empty_segments_list(self):
        assert _grep_segments([], _pattern("x"), "p") == []


class TestGrepDirectoryModeFilter:
    """Test path prefix filter logic used in directory mode."""

    def _filter(self, slug: str, path: str) -> bool:
        return not path or slug.strip("/").startswith(path)

    def test_no_path_matches_all(self):
        assert self._filter("guides/readme", "") is True
        assert self._filter("api/users", "") is True

    def test_path_prefix_matches(self):
        assert self._filter("guides/readme", "guides") is True
        assert self._filter("guides/api/v2", "guides") is True

    def test_path_prefix_excludes_other(self):
        assert self._filter("api/users", "guides") is False

    def test_exact_path_matches(self):
        assert self._filter("guides/readme", "guides/readme") is True

    def test_leading_slash_stripped(self):
        assert self._filter("/guides/readme", "guides") is True
