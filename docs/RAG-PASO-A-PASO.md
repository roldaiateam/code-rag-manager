# RAG paso a paso: de código real a respuesta real

Este documento no explica conceptos nuevos — para eso están los capítulos [01](01-fundamentos-rag.md), [02](02-code-rag-particularidades.md) y [06](06-embeddings-vector-store.md), y para las decisiones de diseño está [FINAL-DESIGN.md](FINAL-DESIGN.md). Lo que hace este documento es **seguir un único trozo de código real a través de cada transformación**, mostrando en cada paso el resultado concreto — no "se genera un embedding", sino el embedding mismo (o algo lo bastante parecido para entenderlo).

## El ejemplo que vamos a seguir

Un fichero `carrito.py` real, de 10 líneas, con dos funciones — una que llama a la otra:

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

Este mismo fichero se usa en todo el documento. No cambiamos de ejemplo a mitad de camino.

## Los dos momentos que no hay que mezclar

Hay dos procesos completamente distintos, que ocurren en instantes distintos:

| | Cuándo ocurre | Qué hace |
|---|---|---|
| **A. Indexado** | Una vez (o cada `reindex`) | Convierte `carrito.py` en algo consultable, y lo guarda en disco |
| **B. Consulta** | Cada vez que alguien pregunta | Usa lo ya guardado para encontrar el fragmento relevante y responder |

La confusión más común es pensar que ambas cosas pasan "a la vez". No es así: **A** puede haber ocurrido hace días; **B** ocurre en el momento exacto en que preguntas algo. Los vamos a ver por separado.

---

## Flujo A — Indexado

### Proceso 1: descubrir el fichero

**Entrada:** el repositorio en disco.
**Proceso:** `git ls-files --cached --others --exclude-standard` (ver [FINAL-DESIGN.md §6](FINAL-DESIGN.md#6-indexado--siempre-completo-drop-and-rebuild)).
**Resultado:**

```
carrito.py
```

(y cualquier otro fichero del repo — nos quedamos solo con este para el ejemplo).

### Proceso 2: parsear con tree-sitter y trocear

**Entrada:** el texto de `carrito.py` (arriba).
**Proceso:** tree-sitter construye un AST; el parser recorre ese árbol y extrae un `CodeChunk` por cada nodo `function_definition` (capítulo [05](05-parsing-multilenguaje.md) §2).
**Resultado:** dos `CodeChunk` reales — estos son literalmente los objetos que produce el parser, con valores concretos:

```python
CodeChunk(
    id="88c9c7d99a",              # hash real de "carrito.py:calcular_total:1"
    project_id="carrito-demo",
    language="python",
    symbol="calcular_total",
    kind="function",
    file_path="carrito.py",
    start_line=1, end_line=5,
    source_text='def calcular_total(items):\n    total = 0\n    for item in items:\n        total += item["precio"] * item["cantidad"]\n    return total',
    embedding=None,               # todavía no existe — es el siguiente paso
)

CodeChunk(
    id="6dd0dc7a4b",              # hash real de "carrito.py:aplicar_descuento:7"
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

Nota: los `id` de arriba (`88c9c7d99a`, `6dd0dc7a4b`) son hashes reales, calculados de verdad a partir de `"carrito.py:calcular_total:1"` y `"carrito.py:aplicar_descuento:7"` — no son un ejemplo inventado, es exactamente el cálculo que haría el sistema.

### Proceso 3: generar el embedding — **aquí empieza el RAG**

**Entrada:** `source_text` de cada chunk (el texto de arriba, tal cual).
**Proceso:** el modelo local (`all-MiniLM-L6-v2`, ver [FINAL-DESIGN.md §7](FINAL-DESIGN.md#7-embeddings)) convierte ese texto en un vector de **384 números**.
**Resultado** (valores ilustrativos — la forma exacta depende de una ejecución real del modelo, pero así es como se ve):

```
calcular_total     → [0.041, -0.183, 0.227, 0.009, -0.115, 0.302, ... ]  (384 números en total)
aplicar_descuento  → [0.052, -0.129, 0.198, 0.061, -0.098, 0.281, ... ]  (384 números en total)
```

**Importante:** ningún número individual "significa" algo por sí solo (el número 12 de la posición 40 no representa "tiene un bucle"). Lo único que importa es la **posición relativa** entre vectores — dos vectores parecidos entre sí (como estos dos, que comparten vocabulario y tema: "total", "precio") acaban geométricamente cerca. Eso es exactamente lo que se explota en el Proceso 8.

### Proceso 4: extraer relaciones (capa estructural — no es RAG)

**Entrada:** el mismo AST del Proceso 2.
**Proceso:** el parser detecta que dentro del cuerpo de `aplicar_descuento` hay una llamada (`call`) a `calcular_total`.
**Resultado:**

```python
DependencyEdge(
    source_chunk_id="6dd0dc7a4b",   # aplicar_descuento
    target_chunk_id="88c9c7d99a",   # calcular_total
    edge_type=EdgeType.CALLS,
)
```

Esto responde a "¿quién llama a quién?" — es útil y complementario, pero **no es la parte semántica/RAG del sistema**. Se guarda en un fichero aparte (grafo, no vectores) y se consulta con `get_dependency_chain`, no con `search_code`.

### Proceso 5: persistir

**Entrada:** los dos `CodeChunk` ya con `embedding` relleno + la arista del Proceso 4.
**Proceso:** escritura en disco, en `<repo>/.crm/` (capítulo [06](06-embeddings-vector-store.md) §2, [FINAL-DESIGN.md §8](FINAL-DESIGN.md#8-almacenamiento)).
**Resultado**, tres ficheros reales:

**Tabla LanceDB** (`project_carrito-demo`, una fila por chunk — se muestra como tabla legible):

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

Con esto termina el indexado. Nadie ha preguntado nada todavía — solo se ha convertido código en algo consultable, y se ha guardado.

---

## Flujo B — Consulta (aquí vive el "Retrieval" del RAG)

Días (o segundos) después, alguien usa Claude Code sobre este repo y pregunta:

> **"¿Dónde se aplica el descuento al total del carrito?"**

### Proceso 6: el agente decide usar `search_code`

El LLM del cliente (Claude) lee la descripción de la tool MCP `search_code` (capítulo [08](08-servidor-mcp.md) §2) y decide que esta pregunta encaja con "buscar código relevante por significado" — así que la invoca con `query="¿dónde se aplica el descuento al total del carrito?"`.

### Proceso 7: la pregunta se convierte en embedding

**Entrada:** el texto de la pregunta.
**Proceso:** **exactamente el mismo modelo** (`all-MiniLM-L6-v2`) que se usó en el Proceso 3 — tiene que ser el mismo, si no, los vectores no serían comparables.
**Resultado** (ilustrativo, mismo formato que antes):

```
query → [0.048, -0.151, 0.209, 0.033, -0.107, 0.295, ... ]  (384 números)
```

Fíjate que este vector "cae" numéricamente muy cerca de los dos vectores del Proceso 3 — no por casualidad: la pregunta comparte significado con ambas funciones.

### Proceso 8: búsqueda por similitud — el corazón del RAG

**Entrada:** el vector de la pregunta + todos los vectores guardados en la tabla LanceDB del proyecto.
**Proceso:** similitud coseno entre el vector de consulta y cada vector guardado (capítulo [01](01-fundamentos-rag.md) §2).

Para que el cálculo se vea de verdad (no solo se mencione), aquí va la misma operación pero reducida a **2 dimensiones de juguete** — el mecanismo es idéntico con 384:

```
query               = [0.8, 0.3]
aplicar_descuento   = [0.9, 0.1]
calcular_total      = [0.3, 0.9]
conectar_bd (otro)  = [-0.5, -0.2]   ← función no relacionada, de otro fichero
```

Similitud coseno = (A · B) / (|A| × |B|):

| Comparación | Producto escalar | Magnitudes | Coseno |
|---|---|---|---|
| query vs `aplicar_descuento` | 0.8·0.9 + 0.3·0.1 = 0.75 | 0.854 × 0.906 | **0.97** |
| query vs `calcular_total` | 0.8·0.3 + 0.3·0.9 = 0.51 | 0.854 × 0.949 | **0.63** |
| query vs `conectar_bd` | 0.8·(-0.5) + 0.3·(-0.2) = -0.46 | 0.854 × 0.539 | **-0.99** |

**Resultado (top_k=2):**

```
1. aplicar_descuento   score=0.97
2. calcular_total      score=0.63
```

`conectar_bd` queda descartado — casi opuesto (-0.99), como predice el capítulo 01 (-1 = sin relación, 1 = misma idea). Con los 384 números reales el orden de magnitud de los scores es distinto, pero el mecanismo — y el hecho de que gane `aplicar_descuento`, que es literalmente donde se aplica el descuento — es el mismo.

### Proceso 9: se devuelve el chunk, no solo la puntuación

El vector store no solo sabe la puntuación — cada fila de LanceDB ya tiene `source_text` guardado (Proceso 5, decisión de [FINAL-DESIGN.md §6](FINAL-DESIGN.md#6-indexado--siempre-completo-drop-and-rebuild): no se relee del disco). Así que `search_code` devuelve directamente:

```
symbol: aplicar_descuento
file_path: carrito.py:7-10
source_text: def aplicar_descuento(items, porcentaje):
                 total = calcular_total(items)
                 descuento = total * (porcentaje / 100)
                 return total - descuento
score: 0.97 (semantic)
```

### Proceso 10: el LLM genera la respuesta — esto ya NO es `crm`

Claude Code recibe ese texto como resultado de la tool, y **con eso ya en su contexto** redacta la respuesta final en lenguaje natural: *"El descuento se aplica en `aplicar_descuento` (carrito.py:7-10): calcula el total con `calcular_total`, y le resta el porcentaje indicado."*

Este último paso ocurre **fuera** de todo lo que hemos construido — ni el indexador ni el servidor MCP escriben una palabra de esa frase. Solo entregaron el fragmento correcto.

---

## Dónde está exactamente el RAG

Con el recorrido completo ya visto, la respuesta concreta:

> **El RAG es el par formado por el Proceso 3+7 (embedding, "Retrieval" — la parte de encontrar) y el Proceso 10 (generación, "Generation" — la parte de responder). El Proceso 8 (similitud coseno) es el mecanismo que conecta ambos lados del Retrieval.**

Y lo que **no** es RAG, aunque viva en el mismo sistema:

- El **Proceso 4** (grafo de dependencias `CALLS`/`IMPLEMENTS`/...) es retrieval **estructural**, no semántico — es útil, pero no usa embeddings ni similitud, así que no es "RAG" en sentido estricto. Es la capa que la guía llama estructural (capítulo [02](02-code-rag-particularidades.md) §2).
- El **Proceso 5** (LanceDB, `graph.json`, YAML) es infraestructura de persistencia — el "almacén", no el "RAG" en sí. Guarda lo que el RAG necesita, pero no busca ni genera nada por sí mismo.
- El **Proceso 10** ocurre en el LLM cliente (Claude, GPT...), **no dentro del proyecto que estás construyendo** (`crm`). `crm` es infraestructura de *Retrieval* pura — nunca genera texto de respuesta (esto ya se vio en la sesión anterior: capítulo [00](00-vision-general.md), "Qué NO es este sistema").

Si tuvieras que señalar **un único proceso** como "aquí está el RAG", sería el **Proceso 8**: el momento exacto en que un vector de pregunta se compara, por significado, contra los vectores guardados de código real.

---

## Tabla-resumen (para repasar de un vistazo)

| # | Entrada | Proceso | Resultado |
|---|---|---|---|
| 1 | Repositorio en disco | `git ls-files` | `carrito.py` |
| 2 | Texto de `carrito.py` | tree-sitter → AST → chunking | 2 `CodeChunk` (símbolo, líneas, `source_text`) |
| 3 | `source_text` de cada chunk | modelo local de embeddings | 2 vectores de 384 números |
| 4 | AST del paso 2 | detectar llamadas/herencia | 1 `DependencyEdge` (`CALLS`) |
| 5 | Chunks + embeddings + aristas | escritura en disco | tabla LanceDB + `graph.json` + `manifest.json` |
| — | *(tiempo después, llega una pregunta)* | | |
| 6 | Pregunta en lenguaje natural | el agente elige la tool `search_code` | llamada MCP con `query=...` |
| 7 | Texto de la pregunta | mismo modelo de embeddings | 1 vector de 384 números |
| 8 | Vector de la pregunta + vectores guardados | similitud coseno | ranking: `aplicar_descuento` (0.97), `calcular_total` (0.63) |
| 9 | Chunk ganador | leer `source_text` ya persistido | código fuente real devuelto al agente |
| 10 | Código fuente + pregunta original | el LLM cliente razona y redacta | respuesta en lenguaje natural (fuera de `crm`) |
