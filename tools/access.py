"""Access control helpers for DifyFS.

Pure functions — no I/O, no HTTP. Determines whether a Dify document is
accessible to a caller based on its is_public and groups metadata fields.

Document metadata contract:
  - is_public: string "true" / "false". Absent → treated as "true".
  - groups:    comma-separated string "eng,legal". Absent → no group access.

Caller contract:
  - groups param is a comma-separated string of group names the caller belongs to.
  - Empty / absent → caller is anonymous; only public docs are visible.

Accessibility rule:
  doc is accessible  ⟺  is_public == True  OR  caller_groups ∩ doc.groups ≠ ∅
"""

from __future__ import annotations


def parse_groups(raw: object) -> list[str]:
    """Parse a comma-separated groups string into a list of group names.

    >>> parse_groups("eng,legal")
    ['eng', 'legal']
    >>> parse_groups(None)
    []
    """
    if not raw:
        return []
    return [g.strip() for g in str(raw).split(",") if g.strip()]


def get_doc_visibility(doc: dict) -> tuple[bool, list[str]]:
    """Extract (is_public, groups) from a Dify document dict.

    Handles both API response shapes:
    - list_documents: doc_metadata = [{"name": "is_public", "value": "true"}, ...]
    - retrieve:       doc_metadata = {"is_public": "true", "groups": "eng"}  (flat dict)

    Returns (True, []) when the fields are absent — permissive default.
    """
    metadata = doc.get("doc_metadata") or []
    is_public = True
    groups: list[str] = []

    if isinstance(metadata, dict):
        raw_public = metadata.get("is_public")
        if raw_public is not None:
            is_public = str(raw_public).lower() not in ("false", "0")
        groups = parse_groups(metadata.get("groups", ""))
    else:
        for m in metadata:
            name = m.get("name")
            val = m.get("value") or ""
            if name == "is_public":
                is_public = str(val).lower() not in ("false", "0")
            elif name == "groups":
                groups = parse_groups(val)

    return is_public, groups


def doc_passes_filter(doc: dict, caller_groups: list[str]) -> bool:
    """Return True if doc is accessible to a caller with the given groups.

    >>> doc_passes_filter({"doc_metadata": []}, [])          # public by default
    True
    >>> doc_passes_filter({"doc_metadata": [{"name": "is_public", "value": "false"},
    ...                                     {"name": "groups", "value": "eng"}]}, ["eng"])
    True
    >>> doc_passes_filter({"doc_metadata": [{"name": "is_public", "value": "false"},
    ...                                     {"name": "groups", "value": "eng"}]}, [])
    False
    """
    is_public, doc_groups = get_doc_visibility(doc)
    if is_public:
        return True
    return bool(set(caller_groups) & set(doc_groups))
