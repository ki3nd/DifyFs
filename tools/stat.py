from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.dify_client import DifyClient


class StatTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        dataset_id = tool_parameters["dataset_id"].strip()
        path = tool_parameters["path"].strip().strip("/")

        client = DifyClient(
            self.runtime.credentials["service_api_endpoint"],
            self.runtime.credentials["api_key"],
        )

        doc = client.find_doc_by_slug(dataset_id, path)
        if not doc:
            # Check if path is a virtual directory (prefix of any slug)
            path_norm = path.strip("/")
            all_docs = client.list_documents(dataset_id)
            children = [
                d for d in all_docs
                if client.get_slug(d).startswith(path_norm + "/") or
                (not path_norm and "/" in client.get_slug(d))
            ]
            if path_norm == "" or children:
                child_count = len(children)
                display = f"/{path_norm}" if path_norm else "/"
                yield self.create_text_message(
                    f"File: {display}\nType: directory\nChildren: {child_count}"
                )
                yield self.create_json_message({
                    "path": display,
                    "type": "directory",
                    "children": child_count,
                })
                return
            yield self.create_text_message(f"stat: {path}: No such file or directory")
            return

        created_at = doc.get("created_at")
        created_str = (
            datetime.fromtimestamp(created_at, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            if created_at
            else "unknown"
        )

        metadata = doc.get("doc_metadata") or []
        meta_dict = {m["name"]: m.get("value") for m in metadata if m.get("name")}

        lines = [
            f"File: {path}",
            f"Name: {doc.get('name', '')}",
            f"ID:   {doc['id']}",
            f"Words:  {doc.get('word_count', 0)}",
            f"Tokens: {doc.get('tokens', 0)}",
            f"Status: {doc.get('indexing_status', 'unknown')}",
            f"Created: {created_str}",
        ]
        if meta_dict:
            lines.append("Metadata:")
            for k, v in meta_dict.items():
                lines.append(f"  {k}: {v}")

        yield self.create_text_message("\n".join(lines))
        yield self.create_json_message({
            "id": doc["id"],
            "name": doc.get("name"),
            "slug": path,
            "word_count": doc.get("word_count", 0),
            "tokens": doc.get("tokens", 0),
            "indexing_status": doc.get("indexing_status"),
            "created_at": created_str,
            "metadata": meta_dict,
        })
