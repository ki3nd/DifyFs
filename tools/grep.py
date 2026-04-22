import re
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.dify_client import DifyClient


def _grep_segments(segments: list[dict], pattern: re.Pattern, slug: str) -> list[dict]:
    """Fine filter: regex each line of each segment, line by line.

    Line numbers are cumulative across segments to match cat output (segments joined with \\n\\n).
    """
    results = []
    offset = 0
    for seg in segments:
        content = seg.get("content", "") or ""
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if pattern.search(line):
                results.append({
                    "path": f"/{slug.strip('/')}",
                    "line_num": offset + i + 1,
                    "line": line,
                })
        offset += len(lines) + 2  # +2 for the \n\n join between segments in cat
    return results


class GrepTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        dataset_id = tool_parameters["dataset_id"].strip()
        pattern_str = tool_parameters["pattern"].strip()
        path = (tool_parameters.get("path") or "").strip().strip("/")
        top_k = int(tool_parameters.get("top_k") or 50)

        # Validate + compile regex (prevent ReDoS via timeout in re module)
        try:
            pattern = re.compile(pattern_str, re.IGNORECASE)
        except re.error as e:
            yield self.create_text_message(f"grep: invalid pattern '{pattern_str}': {e}")
            return

        client = DifyClient(
            self.runtime.credentials["service_api_endpoint"],
            self.runtime.credentials["api_key"],
        )

        results = []

        # ── Mode detection ────────────────────────────────────────────────────
        # If path matches an exact document slug → single-file mode (100% accurate)
        # Otherwise → directory mode (full_text_search coarse + regex fine)

        doc = client.find_doc_by_slug(dataset_id, path) if path else None

        if doc:
            # ── Single-file mode ──────────────────────────────────────────────
            # Fetch ALL segments → regex → exact, no missed lines
            slug = client.get_slug(doc)
            segments = client.get_segments(dataset_id, doc["id"])
            results = _grep_segments(segments, pattern, slug)

        else:
            # ── Directory mode ────────────────────────────────────────────────
            # Stage 1 (coarse): Dify full_text_search → candidate segments
            # Stage 2 (fine):   regex each segment line by line

            records = client.retrieve(
                dataset_id,
                query=pattern_str,
                search_method="full_text_search",
                top_k=top_k,
            )

            for rec in records:
                segment = rec.get("segment", {})
                doc_info = segment.get("document", {})
                slug = client.get_slug(doc_info)

                # Path prefix filter — exact match OR proper prefix (not partial segment name)
                slug_norm = slug.strip("/")
                if path and not (slug_norm == path or slug_norm.startswith(path + "/")):
                    continue

                # Fake a segment dict so _grep_segments can work uniformly
                results.extend(_grep_segments([segment], pattern, slug))

        # ── Output ────────────────────────────────────────────────────────────
        if not results:
            msg = f"grep: no match for '{pattern_str}'"
            if path:
                msg += f" in '{path}'"
            yield self.create_text_message(msg)
        else:
            # Format: path:lineNum — line
            lines = [f"{r['path']}:{r['line_num']} — {r['line']}" for r in results]
            yield self.create_text_message("\n".join(lines))

        yield self.create_json_message({
            "pattern": pattern_str,
            "path": path or "/",
            "mode": "single-file" if doc else "directory",
            "results": results,
            "total": len(results),
        })
