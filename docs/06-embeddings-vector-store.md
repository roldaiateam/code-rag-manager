# 06 · Embeddings y vector store

## 1. Elegir un modelo de embeddings

No hay un único modelo "correcto" — la elección depende de si priorizas calidad, coste, o funcionar completamente offline. La arquitectura del capítulo 03 hace que esta decisión sea **reversible**: el puerto `EmbeddingProvider` aísla la elección, así que puedes empezar con una opción y cambiar después sin tocar el resto del sistema.

| Opción | Tipo | Cuándo elegirla |
|---|---|---|
| **Voyage AI** (`voyage-code-3` / `voyage-4`) | API de pago | Mejor calidad para código y documentación técnica de las opciones hospedadas; coste bajo por token (del orden de céntimos por millón de tokens). Recomendado como default si el coste de API es aceptable para el proyecto. |
| **Qwen3-Embedding** (familia abierta) | Modelo abierto, ejecutable localmente | Mejor opción de peso abierto para retrieval de código a fecha de escritura; requiere GPU o CPU potente según el tamaño del modelo elegido. Buena opción si necesitas todo offline y tienes hardware razonable. |
| **sentence-transformers ligero** (p.ej. `all-MiniLM-L6-v2`) | Modelo abierto, pequeño | Arranca en segundos en CPU, cero coste, cero dependencia de red. Calidad notablemente inferior a las dos opciones anteriores, pero suficiente para empezar a construir y probar el pipeline end-to-end antes de invertir en un modelo mejor. |

La recomendación práctica de esta guía: **empieza con el modelo ligero local** para el milestone M2 del capítulo 12 (validar que todo el pipeline funciona), y cambia a Voyage o a un modelo abierto más grande cuando quieras medir calidad de verdad — es un cambio de adaptador, no un cambio de arquitectura.

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
        return 1024  # según el modelo elegido
```

Nota: la clave de API nunca vive en el código ni en el registro de proyectos versionado — se lee de una variable de entorno (`VOYAGE_API_KEY`) inyectada en tiempo de ejecución, tanto en local como en el workflow de GitHub Actions del capítulo 10 (donde se guarda como *secret*).

## 2. Elegir un vector store

Para un gestor de code-RAGs multi-proyecto que se instala fácilmente en la máquina de un desarrollador, un vector store **embebido** (sin proceso servidor externo que gestionar) es la elección con menos fricción operativa — encaja directamente con el requisito de "levantar fácilmente":

| Opción | Tipo | Ventaja | Cuándo NO elegirla |
|---|---|---|---|
| **LanceDB** | Embebido, basado en ficheros (formato Lance/Arrow) | Sin servidor; escritura eficiente; soporta filtrado por metadatos combinado con búsqueda vectorial (útil para el retrieval híbrido) | Si necesitas acceso concurrente desde múltiples procesos escribiendo a la vez de forma intensiva |
| **ChromaDB** | Embebido (modo local) o cliente-servidor | API muy simple, buena documentación, colecciones = aislamiento multi-proyecto directo | Rendimiento en local a partir de volúmenes muy grandes es algo inferior a LanceDB |
| **Qdrant** (modo local/embedded) | Embebido o servidor | Motor muy maduro, filtrado avanzado | Pensado sobre todo para modo servidor; añade complejidad si solo necesitas un caso de uso local |

Recomendación de esta guía: **LanceDB** como adaptador por defecto (embebido, un directorio por proyecto, sin infraestructura que levantar), con `VectorStore` como puerto para poder añadir `ChromaVectorStore` o `QdrantVectorStore` sin fricción si un proyecto concreto lo necesita.

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
            table.delete(f"id IN {tuple(r['id'] for r in rows)}")  # evita duplicados en reindex
            table.add(rows)
        else:
            self._db.create_table(name, data=rows)

    def search(self, project_id: str, query_embedding: list[float], top_k: int) -> list[SearchResult]:
        table = self._db.open_table(self._table_name(project_id))
        results = table.search(query_embedding).limit(top_k).to_list()
        return [self._to_search_result(r) for r in results]
```

El nombre de tabla derivado de `project_id` (`_table_name`) es exactamente el mecanismo de aislamiento multi-proyecto descrito en el capítulo 04, aplicado al vector store en concreto.

## 3. Retrieval híbrido en la práctica

Recuperando la idea del capítulo 02 (semántica + léxica + estructural combinadas), el caso de uso `SearchCode` combina resultados de dos fuentes:

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

`merge_and_rerank` es una función de dominio (sin dependencias externas, por tanto fácil de testear): normaliza los dos rankings a una misma escala y combina con una ponderación simple (p.ej. `score = 0.6 * score_semantico + 0.4 * score_lexico`, ajustable), deduplicando por `chunk.id` si un chunk aparece en ambos resultados. No hace falta un reranker con modelo aparte para una primera versión — esa combinación ponderada ya captura la mayor parte del valor del enfoque híbrido; queda como mejora futura si la calidad medida (capítulo 01, recall@k) lo justifica.

## 4. Coste y latencia: solo embeber lo que cambió

Generar embeddings tiene coste (dinero si usas una API, tiempo de cómputo si es local) proporcional al número de chunks. Reembeber un repositorio entero en cada cambio, por pequeño que sea, es un desperdicio evitable — de ahí que el capítulo 07 (indexación incremental) sea imprescindible en la práctica, no un "nice to have": solo se llama a `embed_batch` sobre los chunks nuevos o modificados desde el último índice, nunca sobre el repositorio completo salvo la primera vez.

## Ideas reutilizables de los proyectos existentes

Ninguno de los dos proyectos hermanos implementa embeddings o vector store — es la pieza que esta guía aporta de cero frente a ambos. El punto de conexión con `code-rag-mcp` es conceptual: su `search_code` (scoring léxico puro) es exactamente la fuente "lexical" de la sección 3 — si ya tienes ese motor de scoring por keywords funcionando para un lenguaje, se convierte directamente en el adaptador `LexicalIndex` sin necesidad de rehacerlo desde cero.

## Siguiente paso

[07 · Indexación incremental](07-indexacion-incremental.md): cómo evitar reindexar (y reembeber) todo el repositorio cada vez que cambia un solo fichero.
