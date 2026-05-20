from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.access import doc_passes_filter, parse_groups
from tools.dify_client import DifyClient


class CatTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        dataset_id = tool_parameters["dataset_id"].strip()
        path = tool_parameters["path"].strip().strip("/")
        caller_groups = parse_groups(tool_parameters.get("groups") or "")

        client = DifyClient(
            self.runtime.credentials["service_api_endpoint"],
            self.runtime.credentials["api_key"],
        )

        doc = client.find_doc_by_slug(dataset_id, path)
        if not doc:
            yield self.create_text_message(f"cat: {path}: No such file")
            return

        if not doc_passes_filter(doc, caller_groups):
            yield self.create_text_message(f"cat: {path}: No such file")
            return

        segments = client.get_segments(dataset_id, doc["id"])
        if not segments:
            yield self.create_text_message(f"cat: {path}: File is empty")
            return

        content = "\n\n".join(s["content"] for s in segments if s.get("content"))
        if not content:
            yield self.create_text_message(f"cat: {path}: File is empty")
            return

        yield self.create_text_message(content)
        yield self.create_json_message({
            "path": path,
            "document_id": doc["id"],
            "document_name": doc.get("name"),
            "segments": len(segments),
            "content": content,
        })
