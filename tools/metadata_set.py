from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.dify_client import DifyClient


class MetadataSetTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        dataset_id = tool_parameters["dataset_id"].strip()
        document_id = tool_parameters["document_id"].strip()
        key = tool_parameters["key"].strip()
        value = tool_parameters["value"].strip()

        client = DifyClient(
            self.runtime.credentials["service_api_endpoint"],
            self.runtime.credentials["api_key"],
        )

        field_id = client.ensure_metadata_field(dataset_id, key)
        client.set_document_metadata(dataset_id, document_id, field_id, key, value)

        yield self.create_text_message(f"Set '{key}' = '{value}' on document {document_id}")
        yield self.create_json_message({
            "success": True,
            "dataset_id": dataset_id,
            "document_id": document_id,
            "key": key,
            "value": value,
            "message": f"Metadata '{key}' set to '{value}' on document {document_id}",
        })
