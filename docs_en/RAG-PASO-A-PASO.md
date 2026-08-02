# RAG step by step: from real code to a real answer

This document doesn't explain new concepts — that's what chapters [01](01-fundamentos-rag.md), [02](02-code-rag-particularidades.md), and [06](06-embeddings-vector-store.md) are for, and for design decisions there's [FINAL-DESIGN.md](FINAL-DESIGN.md). What this document does is **follow a single piece of real code through every transformation**, showing the concrete result at each step — not "an embedding is generated", but the embedding itself (or something close enough to understand it).

## The example we'll follow

A real `carrito.py` file, 10 lines long, with two functions — one calling the other:

```python
1  def calcular_total(items):
2      total = 0
3      for item in items:
4          total += item["precio"] * item["cantidad"]
5      return total
6
7  def aplicar_descuento(items, porcentaje):
8      total = calcular_total(items)
9      descuento = total * (porcentaje / 100)
10     return total - descuento
```

This same file is used throughout the document. We don't switch examples halfway through.

## The two moments not to mix up

There are two completely different processes, which happen at different times:

| | When it happens | What it does |
|---|---|---|
| **A. Indexing** | Once (or on every `reindex`) | Converts `carrito.py` into something queryable, and saves it to disk |
| **B. Query** | Every time someone asks a question | Uses what's already saved to find the relevant fragment and respond |

The most common confusion is thinking both things happen "at the same time". They don't: **A** may have happened days ago; **B** happens at the exact moment you ask something. We'll look at them separately.

---

## Flow A — Indexing

### Process 1: discovering the file

**Input:** the repository on disk.
**Process:** `git ls-files --cached --others --exclude-standard` (see [FINAL-DESIGN.md §6](FINAL-DESIGN.md#6-indexing--always-full-drop-and-rebuild)).
**Result:**

```
carrito.py
```

(and any other file in the repo — we'll stick to just this one for the example).

### Process 2: parsing with tree-sitter and chunking

**Input:** the text of `carrito.py` (above).
**Process:** tree-sitter builds an AST; the parser walks that tree and extracts a `CodeChunk` for every `function_definition` node (chapter [05](05-parsing-multilenguaje.md) §2).
**Result:** two real `CodeChunk` objects — these are literally the objects the parser produces, with concrete values:

```python
CodeChunk(
    id="88c9c7d99a",              # real hash of "carrito.py:calcular_total:1"
    project_id="carrito-demo",
    language="python",
    symbol="calcular_total",
    kind="function",
    file_path="carrito.py",
    start_line=1, end_line=5,
    source_text='def calcular_total(items):\n    total = 0\n    for item in items:\n        total += item["precio"] * item["cantidad"]\n    return total',
    embedding=None,               # doesn't exist yet — that's the next step
)

CodeChunk(
    id="6dd0dc7a4b",              # real hash of "carrito.py:aplicar_descuento:7"
    project_id="carrito-demo",
    language="python",
    symbol="aplicar_descuento",
    kind="function",
    file_path="carrito.py",
    start_line=7, end_line=10,
    source_text='def aplicar_descuento(items, porcentaje):\n    total = calcular_total(items)\n    descuento = total * (porcentaje / 100)\n    return total - descuento',
    embedding=None,
)
```

Note: the `id` values above (`88c9c7d99a`, `6dd0dc7a4b`) are real hashes, actually computed from `"carrito.py:calcular_total:1"` and `"carrito.py:aplicar_descuento:7"` — this isn't a made-up example, it's exactly the calculation the system would perform.

### Process 3: generating the embedding — **this is where RAG begins**

**Input:** the `source_text` of each chunk (the text above, as-is).
**Process:** the local model (`all-MiniLM-L6-v2`, see [FINAL-DESIGN.md §7](FINAL-DESIGN.md#7-embeddings)) converts that text into a vector of **384 numbers**.
**Result** (illustrative values — the exact shape depends on an actual run of the model, but this is what it looks like):

```
calcular_total     → [0.041, -0.183, 0.227, 0.009, -0.115, 0.302, ... ]  (384 numbers total)
aplicar_descuento  → [0.052, -0.129, 0.198, 0.061, -0.098, 0.281, ... ]  (384 numbers total)
```

**Important:** no individual number "means" anything on its own (the number 12 at position 40 doesn't represent "has a loop"). The only thing that matters is the **relative position** between vectors — two vectors similar to each other (like these two, which share vocabulary and topic: "total", "precio") end up geometrically close. That's exactly what gets exploited in Process 8.

### Process 4: extracting relationships (structural layer — not RAG)

**Input:** the same AST from Process 2.
**Process:** the parser detects that inside the body of `aplicar_descuento` there's a call (`call`) to `calcular_total`.
**Result:**

```python
DependencyEdge(
    source_chunk_id="6dd0dc7a4b",   # aplicar_descuento
    target_chunk_id="88c9c7d99a",   # calcular_total
    edge_type=EdgeType.CALLS,
)
```

This answers "who calls whom?" — it's useful and complementary, but **it's not the semantic/RAG part of the system**. It's stored in a separate file (graph, not vectors) and queried with `get_dependency_chain`, not `search_code`.

### Process 5: persisting

**Input:** the two `CodeChunk` objects now with `embedding` filled in + the edge from Process 4.
**Process:** writing to disk, in `<repo>/.crm/` (chapter [06](06-embeddings-vector-store.md) §2, [FINAL-DESIGN.md §8](FINAL-DESIGN.md#8-storage)).
**Result**, three real files:

**LanceDB table** (`project_carrito-demo`, one row per chunk — shown here as a readable table):

| id | symbol | language | file_path | start_line | end_line | source_text | vector |
|---|---|---|---|---|---|---|---|
| `88c9c7d99a` | `calcular_total` | python | `carrito.py` | 1 | 5 | `def calcular_total(items):...` | `[0.041, -0.183, ...]` |
| `6dd0dc7a4b` | `aplicar_descuento` | python | `carrito.py` | 7 | 10 | `def aplicar_descuento(items, porcentaje):...` | `[0.052, -0.129, ...]` |

**`graph.json`:**
```json
{
  "edges": [
    {"source_chunk_id": "6dd0dc7a4b", "target_chunk_id": "88c9c7d99a", "edge_type": "calls"}
  ]
}
```

**`manifest.json`:**
```json
{
  "project_id": "carrito-demo",
  "last_indexed_commit": "f3a1c02",
  "last_indexed_at": "2026-08-01T10:00:00Z",
  "total_chunks": 2,
  "total_edges": 1
}
```

With this, indexing is done. No one has asked anything yet — code has simply been converted into something queryable, and saved.

---

## Flow B — Query (this is where the "Retrieval" in RAG lives)

Days (or seconds) later, someone uses Claude Code on this repo and asks:

> **"Where is the discount applied to the cart total?"**

### Process 6: the agent decides to use `search_code`

The client's LLM (Claude) reads the description of the `search_code` MCP tool (chapter [08](08-servidor-mcp.md) §2) and decides this question fits "search for relevant code by meaning" — so it invokes it with `query="where is the discount applied to the cart total?"`.

### Process 7: the question becomes an embedding

**Input:** the text of the question.
**Process:** **exactly the same model** (`all-MiniLM-L6-v2`) used in Process 3 — it has to be the same one, otherwise the vectors wouldn't be comparable.
**Result** (illustrative, same format as before):

```
query → [0.048, -0.151, 0.209, 0.033, -0.107, 0.295, ... ]  (384 numbers)
```

Notice that this vector numerically "lands" very close to the two vectors from Process 3 — not by coincidence: the question shares meaning with both functions.

### Process 8: similarity search — the heart of RAG

**Input:** the question's vector + all the vectors stored in the project's LanceDB table.
**Process:** cosine similarity between the query vector and each stored vector (chapter [01](01-fundamentos-rag.md) §2).

So the calculation is actually shown (not just mentioned), here's the same operation but reduced to **2 toy dimensions** — the mechanism is identical with 384:

```
query               = [0.8, 0.3]
aplicar_descuento   = [0.9, 0.1]
calcular_total      = [0.3, 0.9]
conectar_bd (other) = [-0.5, -0.2]   ← unrelated function, from another file
```

Cosine similarity = (A · B) / (|A| × |B|):

| Comparison | Dot product | Magnitudes | Cosine |
|---|---|---|---|
| query vs `aplicar_descuento` | 0.8·0.9 + 0.3·0.1 = 0.75 | 0.854 × 0.906 | **0.97** |
| query vs `calcular_total` | 0.8·0.3 + 0.3·0.9 = 0.51 | 0.854 × 0.949 | **0.63** |
| query vs `conectar_bd` | 0.8·(-0.5) + 0.3·(-0.2) = -0.46 | 0.854 × 0.539 | **-0.99** |

**Result (top_k=2):**

```
1. aplicar_descuento   score=0.97
2. calcular_total      score=0.63
```

`conectar_bd` is discarded — nearly opposite (-0.99), as chapter 01 predicts (-1 = unrelated, 1 = same idea). With the real 384 numbers the order of magnitude of the scores is different, but the mechanism — and the fact that `aplicar_descuento`, which is literally where the discount is applied, wins — is the same.

### Process 9: the chunk is returned, not just the score

The vector store doesn't just know the score — every LanceDB row already has `source_text` stored (Process 5, decision from [FINAL-DESIGN.md §6](FINAL-DESIGN.md#6-indexing--always-full-drop-and-rebuild): it isn't re-read from disk). So `search_code` returns directly:

```
symbol: aplicar_descuento
file_path: carrito.py:7-10
source_text: def aplicar_descuento(items, porcentaje):
                 total = calcular_total(items)
                 descuento = total * (porcentaje / 100)
                 return total - descuento
score: 0.97 (semantic)
```

### Process 10: the LLM generates the answer — this is NO longer `crm`

Claude Code receives that text as the tool's result, and **with that already in its context** it drafts the final natural-language answer: *"The discount is applied in `aplicar_descuento` (carrito.py:7-10): it calculates the total with `calcular_total`, and subtracts the indicated percentage from it."*

This last step happens **outside** everything we've built — neither the indexer nor the MCP server writes a single word of that sentence. They only delivered the correct fragment.

---

## Where exactly RAG is

With the full walkthrough now covered, the concrete answer:

> **RAG is the pair formed by Process 3+7 (embedding, "Retrieval" — the finding part) and Process 10 (generation, "Generation" — the answering part). Process 8 (cosine similarity) is the mechanism that connects both sides of the Retrieval.**

And what is **not** RAG, even though it lives in the same system:

- **Process 4** (the dependency graph `CALLS`/`IMPLEMENTS`/...) is **structural** retrieval, not semantic — it's useful, but doesn't use embeddings or similarity, so it isn't "RAG" in the strict sense. It's the layer the guide calls structural (chapter [02](02-code-rag-particularidades.md) §2).
- **Process 5** (LanceDB, `graph.json`, YAML) is persistence infrastructure — the "storage", not the "RAG" itself. It stores what RAG needs, but doesn't search or generate anything on its own.
- **Process 10** happens in the client LLM (Claude, GPT...), **not inside the project you're building** (`crm`). `crm` is pure *Retrieval* infrastructure — it never generates response text (this was already covered in the previous session: chapter [00](00-vision-general.md), "What this system is NOT").

If you had to point at **a single process** as "here's where RAG is", it would be **Process 8**: the exact moment a question vector is compared, by meaning, against the stored vectors of real code.

---

## Summary table (for a quick review)

| # | Input | Process | Result |
|---|---|---|---|
| 1 | Repository on disk | `git ls-files` | `carrito.py` |
| 2 | Text of `carrito.py` | tree-sitter → AST → chunking | 2 `CodeChunk` objects (symbol, lines, `source_text`) |
| 3 | `source_text` of each chunk | local embedding model | 2 vectors of 384 numbers |
| 4 | AST from step 2 | detecting calls/inheritance | 1 `DependencyEdge` (`CALLS`) |
| 5 | Chunks + embeddings + edges | writing to disk | LanceDB table + `graph.json` + `manifest.json` |
| — | *(time later, a question arrives)* | | |
| 6 | Natural-language question | the agent chooses the `search_code` tool | MCP call with `query=...` |
| 7 | Text of the question | same embedding model | 1 vector of 384 numbers |
| 8 | Question vector + stored vectors | cosine similarity | ranking: `aplicar_descuento` (0.97), `calcular_total` (0.63) |
| 9 | Winning chunk | reading the already-persisted `source_text` | actual source code returned to the agent |
| 10 | Source code + original question | the client LLM reasons and drafts | natural-language answer (outside `crm`) |
