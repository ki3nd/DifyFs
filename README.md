# DifyFS

Navigate and query your Dify knowledge base like a filesystem: ls, cat, grep, find, and search over documents organized by virtual paths.

**Author:** [ki3nd](https://github.com/ki3nd)  
**Type:** tool  
**Github Repo:** [https://github.com/ki3nd/DifyFs](https://github.com/ki3nd/DifyFs)  
**Github Issues:** [issues](https://github.com/ki3nd/DifyFs/issues)  

## Concept

The idea comes from two sources:

* **[Mintlify ChromaFS](https://mintlify.com)** — treats a vector store as a filesystem, assigning each document a `slug` path (e.g. `guides/quickstart`) and using the vector DB as both a coarse filter and a content store. Grep works in two stages: coarse filter via vector similarity, then fine line-by-line regex.

* **[vkfs](https://github.com/ZeroZ-lab/vkfs)** — a Go implementation of the same idea, supporting SQLite and Zilliz backends. difyfs adapts the same virtual path model and two-stage grep to work on top of the Dify Knowledge Base API.

Each document in your dataset gets a `slug` metadata field — its virtual path in the filesystem. Tools then navigate and read documents by slug.

## Setup

**Credentials required:**

| Field | Description |
|---|---|
| Service API Endpoint | Your Dify instance API base URL, e.g. `https://api.dify.ai/v1` |
| API Key | A dataset-scoped API key from your Dify workspace |

## Tools

### `metadata_set` — Assign a virtual path to a document

Set the `slug` (and any other metadata) on a document. This is the first step before using any other tool.

```
dataset_id: <your-dataset-id>
document_id: <document-id>
key: slug
value: guides/quickstart
```

### `ls` — List directory contents

```
ls /                  → top-level dirs and files
ls guides             → contents of guides/
ls guides/api         → contents of guides/api/
```

Output:
```
/guides

  api/
  quickstart
  reference/
```

### `cat` — Read a file

Returns the full text of a document by its slug path. Content is reconstructed by joining all text chunks in order.

```
cat guides/quickstart
```

> **Note:** difyfs assumes datasets are chunked **without overlap**. If your dataset uses chunk overlap, `cat` output will contain duplicated text at chunk boundaries.

### `stat` — File or directory info

```
stat guides/quickstart    → word count, tokens, indexing status, created_at, metadata
stat guides               → type: directory, child count
```

### `grep` — Search for a pattern

Searches line by line, returns `path:lineNum — line` output.

```
grep dataset_id=<id> pattern=access_token path=guides
```

Two modes:

* **Single-file mode** — when `path` matches an exact slug. Fetches all chunks and applies regex. 100% accurate.
* **Directory mode** — when `path` is a prefix or empty. Uses Dify full-text search as a coarse filter (top_k segments), then applies regex line by line. Best-effort — recall depends on `top_k`.

### `find` — Find files by name pattern

Glob matching on the filename part of each slug. Supports `*` and `?`.

```
find dataset_id=<id> name_pattern=*.md path=guides
```

### `search` — Semantic / full-text / hybrid search

```
search dataset_id=<id> query="authentication flow" search_method=semantic_search path=guides
```

Returns matching chunks with virtual file path, relevance score, and a 300-character preview.

## How slugs work

A slug is a `/`-separated path string stored as document metadata:

```
guides/quickstart       → file at /guides/quickstart
guides/api/endpoints    → file at /guides/api/endpoints
```

Virtual directories are derived automatically — any common prefix becomes a navigable directory. There is no need to create directory entries explicitly.

Use `metadata_set` to assign slugs to documents before navigating the filesystem. Documents without a slug fall back to using their document name as the path, placed at root.

## Limitations

* **No overlap support in `cat`** — chunk overlap produces duplicate text at boundaries. Use overlap = 0 when configuring your dataset chunking.
* **Directory mode grep is best-effort** — Dify's retrieve API returns at most `top_k` chunks. Segments not in the top-k are not searched.
* **No write operations** — difyfs is read-only by design. Document creation and deletion are not supported.

## Future Work

* **Group-based filtering** — a `group` metadata field on documents could be used to scope `ls`, `find`, `grep`, and `search` to a named group (e.g. `group=engineering`).
* **Public/private access control** — a `public` metadata field (`true`/`false`) could let tools filter out private documents, enabling basic visibility control within a shared dataset.
