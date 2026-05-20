import fnmatch
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.access import doc_passes_filter, parse_groups
from tools.dify_client import DifyClient


class FindTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        dataset_id = tool_parameters["dataset_id"].strip()
        path = (tool_parameters.get("path") or "").strip().strip("/")
        name_pattern = tool_parameters["name_pattern"].strip()
        caller_groups = parse_groups(tool_parameters.get("groups") or "")

        client = DifyClient(
            self.runtime.credentials["service_api_endpoint"],
            self.runtime.credentials["api_key"],
        )

        docs = client.list_documents(dataset_id)
        matches = []

        for doc in docs:
            if not doc_passes_filter(doc, caller_groups):
                continue
            slug = client.get_slug(doc)
            if path and not (slug == path or slug.startswith(path + "/")):
                continue
            filename = slug.split("/")[-1]
            if fnmatch.fnmatch(filename, name_pattern):
                matches.append(slug)

        matches.sort()

        if not matches:
            yield self.create_text_message(
                f"No files matching '{name_pattern}' under '{path or '/'}'"
            )
        else:
            lines = [f"/{m}" for m in matches]
            yield self.create_text_message("\n".join(lines))

        yield self.create_json_message({
            "path": path or "/",
            "name_pattern": name_pattern,
            "matches": [f"/{m}" for m in matches],
            "total": len(matches),
        })
