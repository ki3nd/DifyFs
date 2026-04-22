from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.dify_client import DifyClient

PREVIEW_LENGTH = 300


class SearchTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        dataset_id = tool_parameters["dataset_id"].strip()
        query = tool_parameters["query"].strip()
        path = (tool_parameters.get("path") or "").strip().strip("/")
        top_k = int(tool_parameters.get("top_k") or 5)
        search_method = tool_parameters.get("search_method") or "semantic_search"

        client = DifyClient(
            self.runtime.credentials["service_api_endpoint"],
            self.runtime.credentials["api_key"],
        )

        records = client.retrieve(dataset_id, query, search_method, top_k)

        if not records:
            yield self.create_text_message(f"No results found for '{query}'")
            yield self.create_json_message({"query": query, "results": [], "total": 0})
            return

        results = []
        for rec in records:
            segment = rec.get("segment", {})
            doc_info = segment.get("document", {})
            doc_id = doc_info.get("id") or segment.get("document_id", "")
            doc_name = doc_info.get("name", "")
            doc_meta = doc_info.get("doc_metadata") or {}

            # retrieve API returns doc_metadata as flat dict {"slug": "...", ...}
            if isinstance(doc_meta, dict):
                slug = doc_meta.get("slug") or doc_name
            else:
                slug = next(
                    (m["value"] for m in doc_meta if m.get("name") == "slug" and m.get("value")),
                    None,
                ) or doc_name

            slug_norm = slug.strip("/")
            if path and not (slug_norm == path or slug_norm.startswith(path + "/")):
                continue

            content = segment.get("content", "")
            preview = content[:PREVIEW_LENGTH] + ("..." if len(content) > PREVIEW_LENGTH else "")
            score = rec.get("score", 0.0)

            results.append({
                "path": f"/{slug.strip('/')}",
                "document_id": doc_id,
                "score": score,
                "preview": preview,
            })

        if not results:
            yield self.create_text_message(
                f"No results found for '{query}'" + (f" under path '{path}'" if path else "")
            )
        else:
            lines = [f"Search results for: {query}\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"[{i}] {r['path']}  (score: {r['score']:.4f})")
                lines.append(f"    {r['preview']}")
                lines.append("")
            yield self.create_text_message("\n".join(lines))

        yield self.create_json_message({
            "query": query,
            "search_method": search_method,
            "path_filter": path or None,
            "results": results,
            "total": len(results),
        })
