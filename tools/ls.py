from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.dify_client import DifyClient


def _normalize_path(path: str) -> str:
    return path.strip("/") if path else ""


def _build_tree(docs: list[dict], client: DifyClient) -> dict[str, list[str]]:
    """Build pathIndex: dir → immediate children (dirs and files)."""
    all_slugs: list[str] = []
    for doc in docs:
        slug = client.get_slug(doc)
        all_slugs.append(slug)

    tree: dict[str, set] = {}
    for slug in all_slugs:
        parts = slug.split("/")
        for depth in range(len(parts)):
            parent = "/".join(parts[:depth]) if depth > 0 else ""
            child_full = "/".join(parts[: depth + 1])
            is_leaf = depth == len(parts) - 1
            child_name = parts[depth] + ("" if is_leaf else "/")
            tree.setdefault(parent, set()).add(child_name)

    return {k: sorted(v) for k, v in tree.items()}


class LsTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        dataset_id = tool_parameters["dataset_id"].strip()
        path = _normalize_path(tool_parameters.get("path") or "")

        client = DifyClient(
            self.runtime.credentials["service_api_endpoint"],
            self.runtime.credentials["api_key"],
        )

        docs = client.list_documents(dataset_id)
        if not docs:
            yield self.create_text_message("(empty dataset)")
            return

        tree = _build_tree(docs, client)
        children = tree.get(path, [])

        if not children:
            yield self.create_text_message(f"No entries found at path '{path or '/'}'")
            return

        lines = [f"/{path}" if path else "/", ""]
        for child in children:
            lines.append(f"  {child}")

        yield self.create_text_message("\n".join(lines))
        yield self.create_json_message({
            "path": path or "/",
            "entries": children,
            "total": len(children),
        })
