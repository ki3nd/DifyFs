import re
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def _fetch_doc_segments(client: DifyClient, dataset_id: str, doc: dict) -> tuple[str, list[dict]]:
    slug = client.get_slug(doc)
    segments = client.get_segments(dataset_id, doc["id"])
    return slug, segments


class GrepTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        dataset_id = tool_parameters["dataset_id"].strip()
        pattern_str = tool_parameters["pattern"].strip()
        path = (tool_parameters.get("path") or "").strip().strip("/")

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

        # If path matches an exact document slug → single-file mode (100% accurate)
        # Otherwise → directory mode: fetch all matching docs in parallel → regex
        doc = client.find_doc_by_slug(dataset_id, path) if path else None

        if doc:
            # ── Single-file mode ──────────────────────────────────────────────
            slug = client.get_slug(doc)
            segments = client.get_segments(dataset_id, doc["id"])
            results = _grep_segments(segments, pattern, slug)

        else:
            # ── Directory mode ────────────────────────────────────────────────
            # Fetch ALL segments for matching docs in parallel → 100% accurate
            all_docs = client.list_documents(dataset_id)
            matching_docs = [
                d for d in all_docs
                if not path or (
                    lambda s: s == path or s.startswith(path + "/")
                )(client.get_slug(d).strip("/"))
            ]

            with ThreadPoolExecutor(max_workers=5) as pool:
                futures = {
                    pool.submit(_fetch_doc_segments, client, dataset_id, d): d
                    for d in matching_docs
                }
                for future in as_completed(futures):
                    slug, segments = future.result()
                    results.extend(_grep_segments(segments, pattern, slug))

        # ── Output ────────────────────────────────────────────────────────────
        if not results:
            msg = f"grep: no match for '{pattern_str}'"
            if path:
                msg += f" in '{path}'"
            yield self.create_text_message(msg)
        else:
            lines = [f"{r['path']}:{r['line_num']} — {r['line']}" for r in results]
            yield self.create_text_message("\n".join(lines))

        yield self.create_json_message({
            "pattern": pattern_str,
            "path": path or "/",
            "mode": "single-file" if doc else "directory",
            "results": results,
            "total": len(results),
        })
