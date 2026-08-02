# 06 · Embeddings and vector store

## 1. Choosing an embedding model

There's no single "correct" model — the choice depends on whether you prioritize quality, cost, or working fully offline. The architecture from chapter 03 makes this decision **reversible**: the `EmbeddingProvider` port isolates the choice, so you can start with one option and switch later without touching the rest of the system.

| Option | Type | When to choose it |
|---|---|---|
| **Voyage AI** (`voyage-code-3` / `voyage-4`) | Paid API | Best quality for code and technical documentation among hosted options; low cost per token (on the order of cents per million tokens). Recommended as the default if the API cost is acceptable for the project. |
| **Qwen3-Embedding** (open family) | Open model, runnable locally | Best open-weight option for code retrieval at the time of writing; requires a GPU or a powerful CPU depending on the chosen model size. A good option if you need everything offline and have reasonable hardware. |
| **Lightweight sentence-transformers** (e.g. `all-MiniLM-L6-v2`) | Open model, small | Starts up in seconds on CPU, zero cost, zero network dependency. Notably lower quality than the two options above, but enough to start building and testing the end-to-end pipeline before investing in a better model. |

The practical recommendation of this guide: **start with the lightweight local model** for milestone M2 in chapter 12 (validating that the whole pipeline works), and switch to Voyage or a larger open model when you want to measure quality for real — it's an adapter change, not an architecture change.

```python
# ports/embedding_provider.py
from typing import Protocol

class EmbeddingProvider(Protocol):
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
    def dimensions(self) -> int: ...
```

```python
# adapters/embeddings/local_provider.py
from sentence_transformers import SentenceTransformer

class LocalSentenceTransformerProvider:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model = SentenceTransformer(model_name)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, batch_size=32, show_progress_bar=False).tolist()

    def dimensions(self) -> int:
        return self._model.get_sentence_embedding_dimension()
```

```python
# adapters/embeddings/voyage_provider.py
import voyageai

class VoyageEmbeddingProvider:
    def __init__(self, api_key: str, model: str = "voyage-code-3"):
        self._client = voyageai.Client(api_key=api_key)
        self._model = model

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        result = self._client.embed(texts, model=self._model, input_type="document")
        return result.embeddings

    def dimensions(self) -> int:
        return 1024  # depends on the chosen model
```

Note: the API key never lives in the code or in the versioned project registry — it's read from an environment variable (`VOYAGE_API_KEY`) injected at runtime, both locally and in the GitHub Actions workflow from chapter 10 (where it's stored as a *secret*).

## 2. Choosing a vector store

For a multi-project code-RAG manager meant to be easy to install on a developer's machine, an **embedded** vector store (no external server process to manage) is the choice with the least operational friction — it fits directly with the "easy to spin up" requirement:

| Option | Type | Advantage | When NOT to choose it |
|---|---|---|---|
| **LanceDB** | Embedded, file-based (Lance/Arrow format) | No server; efficient writes; supports metadata filtering combined with vector search (useful for hybrid retrieval) | If you need concurrent access from multiple processes writing intensively at the same time |
| **ChromaDB** | Embedded (local mode) or client-server | Very simple API, good documentation, collections = direct multi-project isolation | Local performance at very large volumes is somewhat lower than LanceDB |
| **Qdrant** (local/embedded mode) | Embedded or server | Very mature engine, advanced filtering | Designed mainly for server mode; adds complexity if you only need a local use case |

This guide's recommendation: **LanceDB** as the default adapter (embedded, one directory per project, no infrastructure to stand up), with `VectorStore` as the port so you can add `ChromaVectorStore` or `QdrantVectorStore` without friction if a specific project needs it.

```python
# adapters/storage/lancedb_vector_store.py
import lancedb

class LanceDbVectorStore:
    def __init__(self, base_dir: str):
        self._db = lancedb.connect(base_dir)

    def _table_name(self, project_id: str) -> str:
        return f"project_{project_id}"

    def upsert(self, project_id: str, chunks: list[CodeChunk]) -> None:
        rows = [{
            "id": c.id, "vector": c.embedding, "symbol": c.symbol,
            "language": c.language, "kind": c.kind, "file_path": c.file_path,
            "start_line": c.start_line, "end_line": c.end_line,
            "source_text": c.source_text,
        } for c in chunks]
        name = self._table_name(project_id)
        if name in self._db.table_names():
            table = self._db.open_table(name)
            table.delete(f"id IN {tuple(r['id'] for r in rows)}")  # avoids duplicates on reindex
            table.add(rows)
        else:
            self._db.create_table(name, data=rows)

    def search(self, project_id: str, query_embedding: list[float], top_k: int) -> list[SearchResult]:
        table = self._db.open_table(self._table_name(project_id))
        results = table.search(query_embedding).limit(top_k).to_list()
        return [self._to_search_result(r) for r in results]
```

The table name derived from `project_id` (`_table_name`) is exactly the multi-project isolation mechanism described in chapter 04, applied specifically to the vector store.

## 3. Hybrid retrieval in practice

Picking up the idea from chapter 02 (semantic + lexical + structural combined), the `SearchCode` use case combines results from two sources:

```python
# application/search_code.py
class SearchCode:
    def __init__(self, embedder: EmbeddingProvider, vector_store: VectorStore,
                 lexical_index: LexicalIndex):
        self._embedder = embedder
        self._vector_store = vector_store
        self._lexical_index = lexical_index

    def execute(self, query: SearchQuery) -> list[SearchResult]:
        query_vector = self._embedder.embed_batch([query.text])[0]
        semantic = self._vector_store.search(query.project_id, query_vector, query.top_k * 2)
        lexical = self._lexical_index.search(query.project_id, query.text, query.top_k * 2)
        return merge_and_rerank(semantic, lexical, top_k=query.top_k)
```

`merge_and_rerank` is a domain function (no external dependencies, hence easy to test): it normalizes the two rankings to the same scale and combines them with a simple weighting (e.g. `score = 0.6 * semantic_score + 0.4 * lexical_score`, adjustable), deduplicating by `chunk.id` if a chunk appears in both result sets. A separate reranker model isn't needed for a first version — that weighted combination already captures most of the value of the hybrid approach; it's left as a future improvement if measured quality (chapter 01, recall@k) justifies it.

## 4. Cost and latency: only embed what changed

Generating embeddings has a cost (money if you use an API, compute time if it's local) proportional to the number of chunks. Re-embedding an entire repository on every change, however small, is an avoidable waste — which is why chapter 07 (incremental indexing) is essential in practice, not a "nice to have": `embed_batch` is only called on chunks that are new or modified since the last index, never on the whole repository except the first time.

## Reusable ideas from the existing projects

Neither of the two sibling projects implements embeddings or a vector store — this is the piece this guide contributes from scratch relative to both. The connection point with `code-rag-mcp` is conceptual: its `search_code` (pure lexical scoring) is exactly the "lexical" source from section 3 — if you already have that keyword-scoring engine working for a language, it converts directly into the `LexicalIndex` adapter without needing to be rebuilt from scratch.

## Next step

[07 · Incremental indexing](07-indexacion-incremental.md): how to avoid reindexing (and re-embedding) the entire repository every time a single file changes.
