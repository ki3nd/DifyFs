from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.dify_client import DifyClient

KNOWN_FIELDS = ("slug", "is_public", "groups")


def validate_metadata(data: dict) -> tuple[dict | None, str | None]:
    """Validate a metadata dict.

    Returns ``(filtered_dict, None)`` on success, or ``(None, error_message)``
    on failure.  Only the three recognised fields (slug, is_public, groups) are
    kept; all other keys are silently stripped.
    """
    if not isinstance(data, dict):
        return None, "metadata must be a dict object"

    # Strip unknown keys — keep only recognised fields
    parsed: dict = {k: v for k, v in data.items() if k in KNOWN_FIELDS}

    # Validation: is_public=false requires groups to be provided
    is_public = parsed.get("is_public")
    if is_public is False or is_public == "false":
        groups = parsed.get("groups")
        if not groups:
            return None, (
                'Validation error: is_public="false" requires groups to be set'
            )

    return parsed, None


class MetadataSetTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        dataset_id = tool_parameters["dataset_id"].strip()
        document_id = tool_parameters["document_id"].strip()
        metadata = tool_parameters["metadata"]

        parsed, error = validate_metadata(metadata)
        if error:
            yield self.create_text_message(f"Error: {error}")
            return

        client = DifyClient(
            self.runtime.credentials["service_api_endpoint"],
            self.runtime.credentials["api_key"],
        )

        # Build name→id map from all existing dataset-level fields.
        field_id_map: dict[str, str] = {
            f["name"]: f["id"] for f in client.get_metadata_fields(dataset_id)
        }

        # All fields we intend to set must already exist at the dataset level.
        missing = [name for name in parsed if name not in field_id_map]
        if missing:
            yield self.create_text_message(
                f"Error: metadata field(s) {missing} do not exist in dataset '{dataset_id}'. "
                "Please create them first."
            )
            return

        # Get the document's current metadata values (name → value).
        doc = client.get_document_info(dataset_id, document_id)
        current_values: dict[str, str] = {
            entry["name"]: entry.get("value", "")
            for entry in (doc.get("doc_metadata") or [])
            if entry.get("name")
        }

        # Merge: apply new values on top of current.
        merged = {**current_values, **{k: str(v) for k, v in parsed.items()}}

        # Build the final list with id+name+value as the server expects.
        metadata_list = [
            {"id": field_id_map[name], "name": name, "value": value}
            for name, value in merged.items()
            if name in field_id_map
        ]

        # Single call with fully merged metadata.
        client.update_document_metadata(dataset_id, document_id, metadata_list)

        fields_set = list(parsed.keys())
        yield self.create_text_message(
            f"Set metadata fields {fields_set} on document {document_id}"
        )
        yield self.create_json_message({"success": True, "fields_set": fields_set})
