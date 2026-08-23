# Plan de mejora — CodeRagManager (`crm`)

## 0. Propósito y alcance de este documento

Este documento recoge el resultado de una ronda de análisis y diseño conjunta
sobre `code-rag-manager` (`crm`), comparándolo con su proyecto hermano
`code-rag-mcp`, con el objetivo de cerrar la brecha de calidad que un
benchmark real ya midió entre usar `crm` y no usarlo. No sustituye a
`code-rag-manager/docs_en/FINAL-DESIGN.md` (que sigue siendo la referencia de
cómo está construido `crm` hoy) — es su continuación: toma las decisiones que
`FINAL-DESIGN.md §15` dejó explícitamente "fuera de alcance para v1, decidido,
no olvidado" y las revisa una a una con evidencia, además de añadir una
categoría nueva de mejora (clasificación arquitectónica) que ninguno de los
dos proyectos hermanos resuelve todavía de forma genérica.

Vive fuera de ambos repos (`ai/PLAN-MEJORA-CODE-RAG-MANAGER.md`, no dentro de
`code-rag-manager/` ni de `code-rag-mcp/`) porque es un documento de
diseño *sobre* los dos proyectos, no de ninguno de los dos en particular.

Está escrito para dos lectores a la vez: quien vaya a implementar esto en
`crm`, y quien quiera aprender de él **qué es un code-RAG y por qué se toma
cada decisión** — por eso cada capítulo de diseño va precedido de la teoría
que lo justifica, no solo de la conclusión.

**Nada de lo descrito aquí está implementado todavía.** Es un plan para
ejecutar en rondas siguientes, no un changelog.

---

## 1. Los dos proyectos hermanos, en una tabla

| | `code-rag-mcp` | `code-rag-manager` (`crm`) |
|---|---|---|
| Alcance | 1 proyecto, 1 lenguaje (Java) | N proyectos, N lenguajes (Python/JS/Java + fallback texto) |
| Capa semántica (embeddings) | No tiene | `sentence-transformers` local (`all-MiniLM-L6-v2`) + LanceDB |
| Capa léxica | Rica: ~12 señales ponderadas (nombre, métodos, `throws`, anotaciones, `calls`, metadata, campos…) + tokenización camelCase + stemming + sinónimos | Pobre hoy: substring sobre solo `symbol` + `file_path` (2 señales) |
| Capa estructural (grafo) | Edges tipados (`IMPLEMENTS/EXTENDS/FIELD_INJECTION/FOREIGN_KEY/IMPORT`) + BFS con filtro por tipo/dirección | Existe (BFS en `JsonGraphStore`) pero con menos tipos de edge y resolución de referencias más frágil |
| Clasificación layer/role | Sí — pero **cableada a un solo proyecto** (arquitectura hexagonal Java + Spring) | No existe |
| Reindexado | Incremental vía `git diff`, validado en producción | Siempre completo (drop-and-rebuild) — decisión de v1 que este documento **mantiene**, ver §9 |
| Arquitectura | Monolito pragmático | Hexagonal (dominio / puertos / aplicación / adaptadores) — pensado para poder absorber lo anterior sin romperse |

La documentación propia de `crm` (`docs_en/02-code-rag-particularidades.md`,
`docs_en/FINAL-DESIGN.md §15`) ya deja escrito que `code-rag-mcp` es
"el otro medio ya resuelto" (léxico + estructural, sin capa semántica), y
lista layer/role, reindexado incremental, BM25 real y más proveedores de
embedding/vector store como "decidido, no olvidado" para v1. Este documento
revisa esa lista con datos reales en vez de intuición.

---

## 2. Fundamentos: teoría de recuperación de código

*(Si ya conoces embeddings, BM25 y recuperación híbrida en profundidad, puedes
saltar a §3.)*

### 2.1 Tres formas de encontrar código, y para qué sirve cada una

| Tipo | Cómo busca | Fuerte en | Débil en |
|---|---|---|---|
| **Léxico** (palabra/substring) | Coincidencia de texto, con scoring tipo BM25 o ad-hoc | Símbolos exactos: nombres de excepción, de función, de variable | Sinónimos, paráfrasis, "encuéntrame algo que haga X" sin saber el nombre |
| **Semántico** (embeddings) | Similitud de vectores (coseno) | Preguntas conceptuales, código con nombres distintos pero función parecida | Precisión exacta sobre un identificador poco común; puede devolver "casi lo mismo" cuando querías *exactamente eso* |
| **Estructural** (grafo) | Recorrido de aristas explícitas (`implements`, `extends`, `calls`, FK) | "¿Quién implementa esto? ¿Qué depende de esto?" | No captura significado, solo relaciones ya explícitas en el código |

Ninguno sustituye a los otros dos. Un code-RAG serio es **híbrido**: combina
las tres, porque el código tiene identificadores exactos que importan
*y* relaciones de significado que un `grep` no ve *y* relaciones estructurales
explícitas que un embedding no ve.

### 2.2 Las cuatro categorías de consulta (y qué la resuelve mejor)

`crm` ya usa esta taxonomía en su propio banco de benchmarks
(`benchmarks/bank/*.yaml`) — la adoptamos como marco de referencia porque ya
está validada con datos reales (§4):

| Categoría | Ejemplo | Qué la resuelve mejor | Por qué |
|---|---|---|---|
| **Localización** ("¿dónde está X?") | `SecurityConfig`, `ProductsControllerApi` | Léxico (o un índice con scoring por nombre exacto) | Hay un identificador literal que buscar; la semántica no aporta y puede diluir |
| **Conceptual** ("¿cómo se valida X?", sin saber el nombre) | "dónde se guardan las imágenes de producto" → `MinioAdapter` | Semántico | No hay término compartido; hace falta similitud de significado |
| **Estructural** ("¿quién implementa/llama a X?") | "qué usa `ProductsUseCaseImpl`" | Grafo de dependencias | Es una relación explícita del código, no una cuestión de significado |
| **Trampa** (¿existe X? y la respuesta correcta es "no") | "¿dónde están los tests de Cypress?" (usan Playwright) | Grep/glob de todo el filesystem, o un índice que sepa decir "no tengo nada por encima del umbral" | Mide resistencia a alucinar, no recall — un motor que siempre devuelve top-k tiende a inventar que eso es la respuesta |

Corolario práctico: **cuándo no hace falta ningún índice**. En un repo pequeño
(unos pocos miles de líneas), `grep`+`Read` nativos del agente ya son baratos
y completos — un índice empieza a pagar cuando el repo es grande y con mucho
código generado (contratos OpenAPI, monorepos), que es exactamente el caso de
uso que declara el propio `README.md` de `crm`.

### 2.3 BM25 en profundidad

BM25 ("Best Matching 25") es la función de ranking léxico estándar en
recuperación de información desde los años 90 (familia Okapi), y es lo que
cualquier motor de búsqueda de texto serio usa en vez de contar coincidencias
a pelo. La fórmula, para un documento `d` y un término de consulta `q`:

```
score(d, q) = IDF(q) · f(q,d)·(k1+1) / ( f(q,d) + k1·(1 − b + b·|d|/avgdl) )
```

Donde:

- **`f(q,d)`** — cuántas veces aparece el término `q` en el documento `d` (*term frequency*).
- **`|d|`** — longitud del documento `d` (nº de tokens); **`avgdl`** — longitud media de documento en todo el corpus.
- **`k1`** (típicamente 1.2–2.0) — controla la *saturación* de la frecuencia: repetir un término 5 veces no vale 5 veces más que una — la curva se aplana.
- **`b`** (típicamente 0.75) — controla cuánto se penaliza a un documento por ser largo (0 = nada, 1 = normalización completa).
- **`IDF(q) = log((N − n(q) + 0.5) / (n(q) + 0.5) + 1)`** — *inverse document frequency*: `N` = nº total de documentos del corpus, `n(q)` = en cuántos de ellos aparece `q`.

**Intuición, sin la fórmula:**

- **IDF premia lo raro.** Si "playwright" aparece en 2 de 5000 chunks, encontrarlo es muy informativo (IDF alto) — mucho más que encontrar "get" o "response", que aparecen en miles de chunks y por tanto casi no discriminan nada.
- **La frecuencia satura.** Un chunk que menciona "playwright" 5 veces no es 5 veces más relevante que uno que lo menciona 1 vez — el score crece pero se aplana (eso controla `k1`), para que un documento no gane solo por repetir la palabra.
- **La longitud se normaliza.** Un chunk enorme (por ejemplo, una clase larga de código generado) tiene más probabilidad de contener por pura casualidad el término buscado; `b` penaliza a los documentos desproporcionadamente largos para que no ganen solo por ser grandes.

**Por qué importa frente a lo que hace `crm` hoy:** el scorer actual
(`adapters/storage/substring_lexical_index.py:22-41`) suma un bonus **fijo**
(+2 si el término está en `symbol`, +1 si está en `file_path`), sin
importar si ese término es "playwright" (rarísimo, muy informativo) o "get"
(omnipresente, poco informativo), y sin normalizar por longitud. BM25
resuelve ambos problemas automáticamente, con estadísticas del propio corpus,
no con pesos inventados a mano.

Hay una escalera de madurez, y conviene verla como tal en vez de como
alternativas sueltas:

```
substring fijo (hoy)  →  scoring multi-campo ponderado a mano (Nivel 1, de code-rag-mcp)  →  BM25 real (Nivel 2)
```

Cada escalón cambia simplicidad por rigor estadístico. Y hay una dependencia
compartida entre los dos últimos escalones que conviene construir una sola
vez: **BM25 necesita tokenización** (separar texto en términos comparables)
exactamente igual que el scoring multi-campo del Nivel 1 — así que el
`Tokenizer` que se recicla de `code-rag-mcp` (camelCase-split + stemming
ligero + sinónimos, ver §7) no es una pieza de un solo nivel, es una pieza
compartida que paga dos veces.

---

## 3. Evidencia empírica y diagnóstico

`crm` ya tiene un benchmark real: Claude Code respondiendo 12 preguntas por
proyecto (3 proyectos reales) con y sin `crm` conectado por MCP, 93 celdas
registradas en `benchmarks/results/scored.jsonl`. No hace falta inventar
datos — esto es lo que dicen:

| Categoría | `crm` (MCP) | Sin MCP (grep/Read nativos) |
|---|---|---|
| Localización | **100%** (19/19) | 89% (17/19) |
| Conceptual | 100% (9/9) | 100% (10/10) |
| Estructural | 100% (9/9) | 100% (9/9) |
| **Trampa** | **67% (6/9)** ⚠️ | 89% (8/9) |
| Coste medio | $0.138 | $0.170 |
| Turnos medios | 8.4 | 6.8 |

Lectura: `crm` gana claramente en localización (justo donde se espera que
gane un índice léxico+semántico), empata en conceptual/estructural, es más
barato por ejecución — **y pierde justo en la categoría que mide alucinación
por ausencia.** Ese es el hueco real a cerrar, no una lista abstracta.

**Diagnóstico de causa raíz (confirmado leyendo el código, no especulado):**
en `mf-core-platform|tra-02` ("¿tests de Cypress?", verdad = "no, usan
Playwright en `tests/playwright/e2e`"), las 3 repeticiones con `crm`
respondieron "no hay Cypress, usan Vitest" — encontraron la ausencia pero no
el reemplazo real. Sin MCP, `grep` lo encontró en 2 de 3 intentos porque
busca en el **contenido completo** de cada fichero. La causa: `SubstringLexicalIndex.search()`
(`adapters/storage/substring_lexical_index.py:22-41`) compara el término
buscado solo contra `chunk.symbol` y `chunk.file_path` — **nunca contra
`chunk.source_text`**, aunque ese campo ya está guardado en el índice. La
capa semántica sí "ve" el texto completo (se embebe `source_text`), pero
`all-MiniLM-L6-v2` es un modelo pequeño con recall pobre para un token
literal y poco frecuente como "playwright".

Este es el hallazgo que ancla todo el §5 (Nivel 0).

---

## 4. Tabla de decisiones de esta ronda

Al estilo de `FINAL-DESIGN.md §1` — cada fila es una decisión ya tomada en
esta ronda de diseño, no una opción abierta:

| Punto abierto | Decisión tomada | Razón |
|---|---|---|
| Reindexado incremental vía `git diff` (§9) | **No se hace.** Se mantiene "siempre completo" para siempre, no solo como paso intermedio de v1 | Simplicidad operativa deliberada del usuario: el proceso es rápido, no compensa la complejidad de podar aristas colgantes, renombres, etc. |
| Automatización del indexado (§9) | **Disparadores configurables por proyecto** (merge a `main`, merge a `develop`, manual, cron…), pero la acción siempre es la misma reconstrucción completa y limpia | Desacopla "cuándo" de "cómo" — el "cómo" no cambia nunca |
| Léxico: substring → multi-campo → BM25 | Los tres escalones se implementan, en ese orden (Nivel 0 → Nivel 1 → Nivel 2) | Cada uno cierra una brecha medible con el mismo benchmark que ya existe |
| Clasificación layer/role | Se implementa con diseño de 3 capas propio (§7.3), no se copia `Classifiers.java` tal cual | `Classifiers.java` está cableado a un proyecto; `crm` es multi-proyecto y multi-lenguaje por diseño |
| Servidor MCP multi-proyecto (3a: un proceso, muchos `project_id`) | **Aparcado.** No hay evidencia operativa de que haga falta | Es una mejora de eficiencia de despliegue, no de calidad de respuesta |
| Búsqueda federada entre proyectos (3b) | **Confirmada**, mediante grupos explícitos declarados por registro (`--group`), nunca "todos los proyectos" sin acotar | El criterio de esperar evidencia del banco de benchmarks estaba roto (banco anclado a un solo proyecto por diseño); la necesidad ya existe en el sistema real (microservicios + micro-frontend) — ver §9 |
| Proveedores de embedding adicionales / otros vector stores | Se implementan cuando haga falta; son el punto de menor riesgo de todo el plan | Los puertos (`EmbeddingProvider`, `VectorStore`) ya existen y ya hay ejemplo de adaptador Voyage escrito en `docs_en/06` |

---

## 5. Nivel 0 — Cerrar la brecha medida

Objetivo: subir el 67% de la categoría trampa sin tocar arquitectura ni
añadir dependencias nuevas. Dos cambios, ambos acotados a un fichero:

### 5.1 Léxico también sobre `source_text`

**Qué cambia:** `SubstringLexicalIndex.search()` (o su sucesor, ver §7) pasa
de comparar 2 campos (`symbol`, `file_path`) a comparar también
`chunk.source_text`, con un peso menor que `symbol` (para no ahogar el
resultado con coincidencias triviales dentro del cuerpo).

**Ejemplo concreto (antes/después):** consulta `"playwright"` contra un
chunk cuyo `symbol="test_checkout_flow"`, `file_path="tests/playwright/e2e/checkout.spec.ts"`,
`source_text` contiene `import { test } from '@playwright/test'`.

- Hoy: `"playwright"` no está en `symbol` (0 puntos) pero sí en `file_path`
  ("tests/**playwright**/e2e/...") → +1 punto. Score total bajo, fácil de
  quedar por debajo de otros chunks con coincidencias más "gruesas" en
  `symbol`.
- Con el cambio: además +N puntos (peso menor) por la coincidencia en
  `source_text`. Si "playwright" no estuviera ni en la ruta ni en el nombre
  — el caso realmente duro — solo este cambio lo rescata.

**Verificable directamente:** re-correr `benchmarks/runner.py` sobre el
mismo proyecto y comprobar si `tra-02` sube de score.

### 5.2 Umbral de confianza en `search_code`

**Qué cambia:** hoy `search_code` siempre devuelve sus mejores `top_k`
resultados, aunque el mejor tenga una puntuación pésima. Se introduce un
corte: si el score normalizado del mejor resultado queda por debajo de un
umbral, la tool responde explícitamente "sin coincidencia fuerte para esta
consulta" en vez de forzar una respuesta.

**Por qué ataca la categoría entera, no solo este caso:** empuja al agente a
tratar "lo menos malo que encontré" como si fuera la respuesta. El corte
convierte "no encontré nada bueno" en una señal explícita en vez de un
resultado disfrazado de bueno.

### 5.3 De regalo: los 2 bugs ya documentados en `TODO.md`

No compiten conceptualmente con lo anterior, pero son baratos y ya están
diagnosticados con nombre de fichero y línea — barrerlos en la misma pasada:

- `crm mcp install` escribe `"crm"` a pelo en vez de una ruta absoluta
  (`adapters/mcp/client_configs/writers.py:19-20`), rompe clientes cuyo
  proceso no hereda el `PATH` del venv de instalación.
- `crm mcp serve` no imprime nada al arrancar por stdio
  (`adapters/mcp/server.py:123-124`), indistinguible de un cuelgue.

Una vez arreglados estos bugs se debe modificar el TODO.md

---

## 6. Nivel 1 — Recuperación léxica rica + clasificación arquitectónica

### 6.1 Qué se recicla de `code-rag-mcp`, y cómo

| De `code-rag-mcp` | Qué hace | Se recicla como | Dónde en `crm` |
|---|---|---|---|
| `Tokenizer.java` | camelCase-split + stemming + sinónimos (`ProductBarcodeType` → `{product, barcode, type}`) | Casi 1:1 — lógica pura de strings | `domain/tokenizer.py` (nuevo, puro, sin librerías nuevas) |
| `CodeSearcher.score()` | 12 señales ponderadas (nombre, métodos, `throws`, role, metadata, anotaciones, `calls`, campos…) | Se adapta a las señales que existen hoy en `CodeChunk` de `crm` | `domain/lexical_scoring.py` (nuevo, puro) — separado del adaptador de almacenamiento, igual que ya está separado `merge_and_rerank` |
| `SummaryGenerator.java` | Resumen distinto por role (entity/use-case/controller…) | Reciclable en espíritu; necesita `role` ya clasificado (6.3) y algo de estructura que `crm` no extrae hoy | `domain/summary.py` — segunda ola dentro de este nivel, no bloquea el resto |
| `Classifiers.java` | Clasifica layer/role cableado a Spring/hexagonal Java | **No se copia** — sustituido por el diseño de 3 capas (6.3) | `domain/classification.py` |

Señal que ya existe y **no hay que duplicar**: "calls" — ya está modelado
como `DependencyEdge(type=CALLS)` en el grafo; se consulta vía `graph_store`
al puntuar, no hace falta añadirlo como lista aparte en el chunk.

### 6.2 Regla de oro para no romper hexagonal

**Un puerto (`ports/`) existe solo para aislar E/S o una librería externa
intercambiable** (tree-sitter, un modelo de embeddings, LanceDB). **Si algo es
cómputo puro sobre datos que ya están en memoria, va en `domain/`** — igual
que ya están `domain/ranking.py` y `domain/resolution.py` hoy. Con esa regla,
la clasificación (6.3) no necesita **ningún puerto nuevo**.

### 6.3 Clasificación layer/role en 3 capas

El problema que hay que resolver, planteado por quien encargó este análisis:
`code-rag-mcp` clasifica hoy, pero de forma cableada a un solo proyecto
(literalmente `path.contains("/domain/src/")`, `annots.contains("RestController")`).
Copiarlo tal cual a un `crm` multi-proyecto y multi-lenguaje no generaliza.
La solución: tres capas independientes, de más a menos universal, que se
activan en cascada.

**Ejemplo ancla:** `tests/fixtures/sample_repo/src/pedidos.py` (el propio
fixture de test de `crm`) — deliberadamente plano, sin carpetas
`domain/`/`application/`, sin decoradores:

```python
class Pedido:
    def __init__(self, items):
        self.items = items
    def total_con_descuento(self, porcentaje):
        return aplicar_descuento(self.items, porcentaje)

class PedidoUrgente(Pedido):
    ...
```

**Capa 1 — vocabulario de rutas, sin conocer el framework.** Segmentos como
`domain/`, `application/`, `infrastructure/`, `ports/`, `controllers/` son
vocabulario de arquitectura hexagonal/limpia que aparece en Python, Java, JS,
Go… igual, sin que el clasificador sepa nada del lenguaje. Sobre
`pedidos.py`: `file_path = "src/pedidos.py"` no tiene ningún segmento
reconocible → `layer = None`. **No aporta nada aquí, y eso está bien**: es la
señal más barata, calla cuando no hay convención en vez de inventar.

*Dónde vive:* `domain/classification.py`, función pura
`classify_layer_by_path(file_path: str) -> str | None`.

**Capa 2 — packs de convención por framework, autodetectados.** Un registro
de packs (`spring-java`, `fastapi-python`, `express-js`…), cada uno con una
regla barata de "¿aplico aquí?" (¿hay `@RestController`? ¿hay `APIRouter` de
FastAPI?) y, si aplica, sus reglas de rol. Mismo patrón que ya usa `crm` para
otra cosa: la autodetección de código generado (`target/generated-sources`,
`build/generated`) ya es "detectar por convención y activar una regla" — no
es un concepto nuevo para el proyecto.

Sobre `pedidos.py`: no hay decorador, así que daría `role = None` de todos
modos — pero hay un prerrequisito real que hay que resolver antes de que esta
capa pueda funcionar en ningún caso: **hoy los tres parsers de `crm`
(`tree_sitter_python.py`, `tree_sitter_java.py`, `tree_sitter_javascript.py`)
construyen siempre `metadata={}` vacío** — ningún decorador ni anotación se
extrae todavía. Antes de poder activar packs, hay que enriquecer cada parser
para que capture esa señal en el `metadata` del chunk (cambio de
**adaptador**, no de dominio — el puerto `LanguageParser.parse()` sigue
devolviendo `(chunks, edges)` igual que hoy).

*Dónde vive:* la tabla de packs + la función de clasificación, en
`domain/classification.py` también (son datos estáticos + una función pura
sobre `chunk.metadata` ya poblado, cero E/S).

**Capa 3 — prototipos semánticos, usando el embedding que `crm` ya calcula.**
Esta es la que `code-rag-mcp` no puede tener porque no tiene embeddings, y es
la que de verdad generaliza a cualquier proyecto sin convención reconocible.
Se define un puñado fijo de descripciones-prototipo:

```
"entity":     "domain entity holding business data and invariants"
"controller": "HTTP handler that receives requests and returns responses"
"adapter":    "adapter that persists or fetches data from an external system"
"use_case":   "application service orchestrating a business operation"
```

Se embeben una sola vez con el `EmbeddingProvider` que ya existe, y se
compara por coseno contra el embedding de cada chunk (que también ya se
calcula hoy). Sobre `Pedido`/`PedidoUrgente` (guarda `items`, aplica un
descuento, tiene subclase por herencia): queda semánticamente más cerca de
`"entity"` que de `"controller"`/`"adapter"` — sale `role ≈ "entity"` con
confianza media (0.4-0.5 de similitud, no un 0.9 aplastante, porque el texto
es ambiguo). Esa confianza se guarda junto al resultado: si el mejor match da
0.15 (ruido), el sistema puede decidir no clasificar en vez de forzar una
etiqueta poco fiable.

**Regla de combinación entre las 3 capas:** si una capa "dura" (1 o 2) da
resultado, manda ella; la capa 3 solo entra cuando las otras dos vuelven
`None`. Determinista donde se puede, difuso solo cuando no queda otra.

*Dónde vive:* `nearest_role_prototype(chunk_embedding, prototype_embeddings)`
en `domain/classification.py` (coseno es aritmética pura, sin dependencias
nuevas). La parte que sí hace E/S (embeber los prototipos) reutiliza el
puerto `EmbeddingProvider` **ya existente** — cero puertos nuevos también
aquí.

### 6.4 Mapa completo de dónde vive cada pieza

| Pieza | Dónde vive | Nota |
|---|---|---|
| Campos `layer`, `role`, `role_confidence` en `CodeChunk` | `domain/models.py` — nuevos campos opcionales | Igual que `embedding: list[float] \| None` ya es opcional hoy |
| Capas 1, 2 y 3 de clasificación | `domain/classification.py` | Ninguna necesita puerto nuevo |
| Extracción de decoradores/anotaciones | `adapters/parsers/tree_sitter_*.py` | Trabajo 100% específico de lenguaje → adaptador, no dominio |
| Orquestar clasificación tras parsear, antes de embeber | `application/index_project.py` | Mismo patrón que ya existe: `chunks = [replace(c, embedding=e) for ...]` → se añade `layer=l, role=r` igual |
| Filtro `layer`/`role` en `search_code`/`list_chunks` | `domain/models.py` (campos) + `application/search_code.py`/`list_chunks.py` (un `if` más) | Mismo patrón que los filtros `language`/`kind` que ya existen |
| Activar/desactivar | Flag CLI `--no-role-classification` | Mismo patrón UX que `--no-auto-include`, ya existente |

---

## 7. Nivel 2 — BM25 real + proveedores adicionales

### 7.1 De multi-campo a BM25 real

El puerto `LexicalIndex` ya tiene la firma correcta
(`index(project_id, chunks)`, `search(project_id, text, top_k)`). Pasar de
`SubstringLexicalIndex`/su sucesor de 6.1 a BM25 real es **sustituir el
adaptador por otro que implementa el mismo puerto** — cero cambios en
`domain/`, `application/` ni en el puerto mismo.

Lo único nuevo: BM25 necesita estadísticas de todo el corpus (en cuántos
chunks aparece cada término, longitud media de documento) — `index()` deja
de ser un no-op y construye un índice invertido real. Esa estructura
especializada vive en el adaptador (`adapters/storage/bm25_lexical_index.py`),
igual que LanceDB es la estructura especializada que posee `VectorStore`. La
fórmula en sí (aritmética pura dado tf/df/longitud) puede aislarse en
`domain/bm25.py` para poder testearla con números inventados sin montar un
índice real.

**Trade-off asumido explícitamente:** con indexado siempre completo (§9), las
estadísticas idf se recalculan enteras en cada reconstrucción — no hace falta
diseñar actualización incremental de estadísticas, que sería la única parte
realmente compleja de BM25 en un escenario de reindexado parcial. Al no haber
reindexado parcial, este problema directamente no existe.

### 7.2 Proveedores de embedding adicionales / otros vector stores

El punto de menor riesgo de todo el plan. Los puertos `EmbeddingProvider` y
`VectorStore` **ya existen**, y `docs_en/06-embeddings-vector-store.md` ya
trae escrito el código del adaptador Voyage
(`VoyageEmbeddingProvider`, API key por variable de entorno, nunca en
`~/.crm/projects.yaml`). Es escribir la clase, registrarla en
`composition_root.py` detrás de un switch de config
(`crm config set embedding.provider voyage`), y ya.

Consecuencia útil de la decisión de §9 (indexado siempre completo): cambiar
de proveedor de embeddings cambia la dimensión del vector (MiniLM = 384,
Voyage = 1024), lo que en cualquier otro diseño exigiría migrar el esquema de
la tabla LanceDB — aquí no, porque `crm index` ya reconstruye la tabla entera
siempre. Lo que parecía un recorte de v1 es lo que evita tener que diseñar
migración de esquema.

---

## 8. Indexado: por qué se queda completo para siempre

**Decisión de esta ronda:** no se implementa reindexado incremental vía
`git diff`, ni siquiera como mejora futura activa en la hoja de ruta. Se
mantiene "siempre completo" (drop-and-rebuild) de forma permanente. Razón:
es un proceso rápido, y la complejidad de podar aristas colgantes, gestionar
renombres y mantener estadísticas de BM25 al día no compensa frente a
simplemente tirar y reconstruir. Este documento **revierte** lo que en la
ronda de análisis inicial se había explorado como Nivel 2 candidato
(reindexado incremental) — queda descartado, no aparcado con intención de
retomarlo.

**Lo que sí se automatiza: cuándo se dispara, no cómo se indexa.** La mejora
real de este punto es separar dos preguntas distintas:

1. *¿Cómo se reconstruye el índice?* — Siempre igual: `crm index --project <id>`, completo, limpio, idempotente por construcción (`drop()` + rebuild). No cambia nada de código para esto.
2. *¿Cuándo se dispara ese comando?* — Esto sí varía por proyecto, y no tiene que ver con el motor de indexado sino con el flujo de trabajo de cada equipo:

| Ejemplo de disparador | Cuándo tiene sentido |
|---|---|
| Merge a `main` | Proyectos donde el índice debe reflejar solo lo que llega a producción |
| Merge a `develop` | Proyectos con rama de integración continua antes de `main` |
| Manual (`workflow_dispatch` únicamente) | Proyectos pequeños o de baja cadencia de cambio |
| Programado (cron) | Proyectos donde nadie dispara el reindex activamente pero se quiere frescura garantizada |

Lo único que comparten todos: la acción disparada es siempre la reconstrucción
completa y limpia — nunca un diff parcial. Esto es, en la práctica, un
catálogo de plantillas de CI (variaciones sobre
`.github/workflows/reindex.yml`, que ya existe como plantilla a copiar en
cada repo indexado) más una línea de documentación — **no requiere tocar
`domain/`, `application/`, `ports/` ni `adapters/` de `crm`.** Es
deliberadamente el punto de menor superficie de cambio de todo este
documento.

---

## 9. Nivel 3 — Búsqueda federada entre proyectos, por grupos explícitos

El TODO original mezclaba dos capacidades distintas bajo "servidor MCP
multi-proyecto" — conviene mantenerlas separadas porque tienen perfiles de
riesgo/valor muy distintos:

- **3a — Consolidación operativa**: un proceso sirviendo varios `project_id`
  en vez de uno por proyecto. Ahorro de memoria/arranque, ninguna capacidad
  nueva para el agente. **Sigue aparcado** — no hay evidencia operativa
  (arranque lento, exceso de procesos) de que haga falta.
- **3b — Búsqueda federada**: poder preguntar "busca X en los proyectos
  relacionados con este" sin saber de antemano en cuál está. **Confirmado
  para implementar**, con el diseño de esta sección — ya no queda
  condicionado a que aparezca evidencia futura (ver 9.1).

### 9.1 Por qué se confirma, y no se deja "a la espera de evidencia"

La ronda de análisis original dejaba 3b condicionado a que apareciera un
caso en el banco de benchmarks que lo necesitara. Se revisó explícitamente
si el fallo medido de `tra-02` (Cypress/Playwright, §3) era ese caso — no lo
es: las 3 repeticiones sin MCP encontraron Playwright *dentro* del mismo
repo (`mf-core-platform/tests/playwright/e2e`), no en otro proyecto. Ese
fallo sigue atribuido al Nivel 0 (§5.1).

Pero esperar a que el propio banco de benchmarks produjera esa evidencia era
un criterio roto: **el banco (`bank/*.yaml`) está construido con preguntas
ancladas a un único proyecto por diseño** (`project_id: X`, las 12 preguntas
de cada fichero son respondibles dentro de ese repo) — nunca puede generar
un caso que valide una pregunta que cruce dos proyectos, exista o no la
necesidad real. Y la necesidad real existe: `mic-inventory`, `mic-clients`
(microservicios) y `mf-core-platform` (micro-frontend) son **repos
separados de un mismo sistema en producción** — una pregunta como *"¿cómo
fluye la autenticación desde que el usuario hace login en el frontend hasta
que el backend valida el JWT?"* necesita datos de `mf-core-platform` y de
`mic-clients` a la vez, y hoy es estructuralmente imposible de responder vía
MCP (no es un problema de calidad de búsqueda: el dato no está en el índice
al que ninguna sesión individual tiene acceso). Se decide construirlo, con
las salvaguardas de 9.2-9.4.

### 9.2 Grupos explícitos, declarados por una persona — nunca por el LLM

Campo nuevo en el registro global: `Project.group: str | None`, persistido
en `~/.crm/projects.yaml` junto a los campos por proyecto que ya existen
(`extra_index_paths`, `auto_include`) — sin puerto nuevo, mismo
`ProjectRegistry` de siempre.

```bash
crm project add mic-inventory <ruta>     --group sistema-inventario
crm project add mic-clients <ruta>       --group sistema-inventario
crm project add mf-core-platform <ruta>  --group sistema-inventario
```

Dos proyectos sin `group`, o con `group` distinto, **nunca se buscan juntos
bajo ningún flag** — no hay forma de que el agente los cruce por accidente.
La garantía central: **el conjunto de proyectos que se pueden buscar juntos
lo decide una persona por adelantado, al registrar los proyectos — nunca el
LLM en tiempo de ejecución.**

`crm project list` gana una columna `group` para que esa relación se vea de
un vistazo (hoy no muestra ninguna).

### 9.3 La tool nueva: condicional, igual que el patrón ya validado del vault de `code-rag-mcp`

No hace falta un modo de servidor `--workspace` separado (era superficie
nueva de riesgo innecesaria). El mismo `crm mcp serve --project mic-inventory`
de siempre consulta su propio registro al arrancar y, **solo si tiene
`group` asignado**, expone una tool adicional:

```
search_related_projects   ← aparece únicamente si el proyecto activo tiene "group"
```

Es exactamente el patrón que ya usa `code-rag-mcp` para su puente con
Obsidian: *"estas tools aparecen únicamente cuando el servidor arranca con
un vault configurado"* — reutilizado, no inventado.

| Pieza | Dónde vive |
|---|---|
| Etiqueta de qué proyecto es cada resultado | Nada nuevo — `CodeChunk.project_id` ya existe |
| `application/search_related_projects.py` | Nuevo caso de uso: recorre `ProjectRegistry.list()` filtrado por `group == project.group`, instancia el `SearchCode` de cada uno (el almacenamiento sigue aislado por proyecto incluso dentro de un grupo — tablas LanceDB, `graph.json` e índices léxicos separados, nunca una estructura compartida; agrupar es solo una decisión de qué se consulta a la vez, no de dónde se guardan los datos), fusiona con `merge_and_rerank` etiquetando por proyecto |
| `crm search "<query>" --related` | CLI para depuración fuera de MCP — busca también en el grupo del proyecto activo |

### 9.4 Cuando dos proyectos del mismo grupo tienen un símbolo con el mismo nombre

Caso real, no hipotético: tanto `mic-inventory` como `mic-clients` tienen
una clase `GlobalExceptionHandler` (aparece como respuesta esperada en el
banco de benchmarks de ambos), con implementaciones distintas. Etiquetar
cada resultado con su `project_id` ayuda pero no basta — un LLM leyendo
rápido puede pasarlo por alto y mezclar las dos.

**Salvaguarda 1 — aviso activo de colisión, no solo etiqueta pasiva.**
Cuando `search_related_projects` detecta que el mismo `symbol` aparece en
más de un proyecto **dentro del lote de resultados que va a devolver** (no
un escaneo global del índice, solo lo que realmente se muestra junto), la
respuesta antepone un aviso explícito ("'GlobalExceptionHandler' existe en
más de un proyecto de este grupo — mic-clients, mic-inventory — son
implementaciones distintas, no las mezcles") antes de listar los
resultados, cada uno bajo un encabezado `[project_id]` visible en el propio
texto, no solo en metadata.

**Salvaguarda 2 — `get_source`/`get_dependency_chain` no cambian, deliberadamente.**
Se decide explícitamente NO añadirles un parámetro `project_id` para
"seguir" un resultado de otro proyecto — hacerlo reabriría el riesgo real:
resolver un símbolo de nombre ambiguo contra el proyecto equivocado, en
silencio, sin error (el agente vería el `GlobalExceptionHandler` de
`mic-clients` en un resultado federado y, si llamara a `get_source` desde
la sesión de `mic-inventory`, obtendría silenciosamente la versión de
`mic-inventory` sin saberlo). En vez de eso, cuando un resultado federado
viene de un proyecto distinto al activo, la propia tool se lo dice al
agente en el texto de salida: *"este resultado es de `mic-clients`; para
leer su código completo, hazlo en una sesión con
`crm mcp serve --project mic-clients`"* — nunca un intento silencioso de
resolverlo desde donde no toca. Esto acota el radio de todo Nivel 3 a una
sola tool nueva (`search_related_projects`); todo lo demás (`get_source`,
`get_dependency_chain`, el propio `search_code` normal) se queda exactamente
como está hoy, sin ninguna vía nueva de error silencioso.

---

## 10. Bugs ya conocidos (no duplicar, solo referenciar)

`code-rag-manager/TODO.md` ya trackea, con fichero y línea exactos:

- `crm mcp install` escribe `"crm"` sin ruta absoluta (§5.3 de este documento
  lo agrupa dentro del Nivel 0 por ser barato de arrastrar en la misma
  pasada).
- `crm mcp serve` no imprime nada al arrancar por stdio (ídem).
- Falta de `LICENSE`, `SECURITY.md`, CI propia de `crm`, etc. — no son parte
  de la calidad de recuperación y quedan fuera del alcance de este
  documento; siguen viviendo en `TODO.md`.

---

## 11. Hoja de ruta sugerida

```
Nivel 0  →  Nivel 1  →  Nivel 2 (7.1, 7.2)  →  §9 (documentación/CI, sin código)  →  Nivel 3 (condicionado a evidencia)
```

Razón del orden: Nivel 0 y el tokenizer/scoring de Nivel 1 atacan
directamente la brecha medida en §3 y son verificables con el mismo
benchmark que ya existe. La clasificación (resto de Nivel 1) es la pieza de
más diseño nuevo y de la que depende parte del resto (summary por rol,
filtro `--role`). BM25 (Nivel 2) es la maduración natural del léxico una vez
que el tokenizer ya existe. §9 no tiene coste de implementación real. Nivel
3 se deja condicionado a que aparezca evidencia real de necesidad.

---

## 12. Puntos pendientes de concretar antes de implementar

Checklist de decisiones que este documento deja **abiertas a propósito** —
necesitan una decisión concreta antes de poder empezar a escribir código,
no son ambigüedad accidental:

- [x] **Resuelto.** Peso relativo de `source_text` frente a `symbol`/`file_path`
      en el scorer léxico ampliado (§5.1): **`source_text` = 0.5**, manteniendo
      `symbol` = 2.0 y `file_path` = 1.0 (proporción 4:2:1). Cuenta presencia
      del término por campo, no ocurrencias — misma regla que ya usan
      `symbol`/`file_path` hoy. Riesgo aceptado y no mitigado aquí a propósito:
      una consulta de 4 términos podría empatar con un match exacto de
      `symbol` si un chunk grande los contiene los 4 por casualidad en el
      cuerpo; se resuelve de raíz en Nivel 2 (BM25 con IDF + normalización de
      longitud), no merece la pena complicar este parche para cubrirlo.
- [x] **Resuelto.** Umbral de confianza para "sin coincidencia fuerte" (§5.2).
      Se aplica **antes** de la normalización min-max de `merge_and_rerank`
      (aplicarlo después no funcionaría: min-max siempre estira el mejor
      resultado de cualquier lote hacia 1.0, aunque todo el lote sea débil).
      Sobre las magnitudes crudas: **semántico < 0.35** de similitud de
      coseno del mejor resultado, **Y léxico == 0** (ningún término literal
      encontrado) del mejor resultado — dispara solo si fallan **ambas**
      señales a la vez, coherente con que ninguna capa sustituye a la otra
      (§2.1). Formato de respuesta: `search_code` sigue devolviendo los 1-3
      mejores candidatos, pero con un aviso explícito antepuesto ("⚠ Ninguna
      coincidencia supera el umbral de confianza…") en vez de una respuesta
      vacía — evita ocultar información y falsos negativos, a la vez que
      hace explícita la baja confianza en vez de presentarla como una
      respuesta segura.
- [x] **Resuelto.** Tabla de sinónimos y stemming del `Tokenizer` (§6.1). Al
      leer `Tokenizer.java` completo se confirmó que su tabla de sinónimos es
      vocabulario de negocio de un proyecto concreto (`inventario/proveedor/
      lote/caducidad` — glosario de `mic-inventory`), la misma trampa de
      generalización que `Classifiers.java` — no se copia tal cual. Diseño
      adoptado, mismo patrón "base universal + extensión opcional" que la
      clasificación:
      1. **Base siempre activa**, vocabulario genérico de ingeniería de
         software (no de negocio): `create↔add,new,insert` ·
         `remove↔delete` · `update↔edit,modify` · `get↔fetch,retrieve` ·
         `list↔search,query,find` · `endpoint↔api,route,handler` ·
         `config↔configuration,settings` · `error↔exception,failure` ·
         `validate↔check,verify`. Deliberadamente fuera: pares tipo
         `user↔account` que dependen del dominio.
      2. **Extensión opcional por proyecto** para vocabulario de negocio:
         campo nuevo `Project.extra_synonyms: dict[str, list[str]]`,
         persistido en `~/.crm/projects.yaml` junto a `extra_index_paths`/
         `auto_include` ya existentes — sin puerto nuevo, es un campo más en
         `adapters/registry/yaml_project_registry.py`.
      3. **Stemmer**: se porta casi literal el de `code-rag-mcp` (plural
         `-s`, `-ies→y`, gerundio `-ing`, reglas de morfología inglesa
         genéricas) + regla ligera de plural en español (`-es`/`-s` final en
         palabras >4 caracteres), dado que `crm` ya es bilingüe en su propia
         documentación y en los bancos de benchmark.
- [x] **Resuelto.** Lista inicial de packs de convención para la Capa 2
      (§6.3). Se revisaron los 3 proyectos reales del banco de benchmarks:
      `mic-inventory` y `mic-clients` son ambos Java/Maven hexagonal+Spring
      (misma familia para la que ya está validado `Classifiers.java`);
      `mf-core-platform` es un frontend JS/TS (React) sin capas hexagonales
      ni decoradores de ningún framework backend. Decisión: **un único pack
      al lanzamiento, `spring-java`**, portado casi literal de
      `Classifiers.java` (RestController→controller, Service→use-case/
      service, Entity→jpa-entity, extends Repository→repository,
      Mapper→mapper, ControllerAdvice→exception-handler, convención de
      paquete `ports.in`/`ports.out`) — cubre 2 de los 3 proyectos reales
      desde el día uno con reglas ya validadas. No se añade pack para
      JS/React (no hay convención de decoradores dominante en un SPA plano,
      sería trabajo especulativo) ni para Python (ningún proyecto real del
      banco lo usa todavía, no hay contra qué calibrar). El registro de
      packs queda abierto para añadir más sin rediseño. Prerrequisito
      directo: `tree_sitter_java.py` debe empezar a extraer anotaciones a
      `metadata` (hoy no lo hace) antes de que este pack tenga algo que
      clasificar.
- [x] **Resuelto (parcialmente a propósito).** Frases-prototipo y umbral de
      coseno para la Capa 3 semántica (§6.3). Taxonomía reducida de las 14
      de `code-rag-mcp` (pensada para clasificación determinista por
      anotación) a **7 categorías generales**, en inglés (el modelo separa
      mejor ahí, limitación ya conocida): `entity`, `controller`, `adapter`,
      `use_case`, `mapper`, `config`, `utility` — frases exactas en §6.3.
      `test` se excluye de esta capa: se detecta por convención de ruta/
      nombre en la Capa 1 (gratis, determinista), no por similitud semántica.
      Selección: argmax entre las 7 (conjunto cerrado, siempre se asigna
      una). Confianza: **margen entre el 1º y 2º prototipo más cercano**
      (no un umbral absoluto de coseno — la comparación código↔texto de
      MiniLM puede vivir en una banda estrecha y un corte absoluto sería
      frágil). Valor de partida para "confianza baja": margen `< 0.05`.
      **Esto último queda explícitamente marcado como a calibrar** con los 3
      proyectos reales del banco de benchmarks en cuanto exista código que
      ejecutar — es el único número de todo este checklist que no se puede
      cerrar por razonamiento puro.
- [x] **Resuelto.** Implementación de BM25 (§7.1): **a mano, sin dependencia
      nueva** (ni `rank-bm25` ni `bm25s`) — la escala de un proyecto típico
      (miles, no millones, de símbolos; ya validado por `code-rag-mcp` para
      sus propias estructuras en memoria) no justifica tirar de librería, y
      es coherente con el resto del plan: substring-match fue la elección
      deliberada de v1 por la misma razón, y el stemmer del punto 3 también
      se hizo a mano. Fórmula en `domain/bm25.py` (aritmética pura,
      testeable sin índice real). El índice invertido **no tiene fichero de
      persistencia propio** — se reconstruye en memoria en cada arranque del
      servidor MCP a partir de los chunks (`source_text`) ya persistidos por
      `VectorStore`, misma filosofía de "caché reconstruible" que ya usa
      `crm` para el resto de `.crm/`. Vía de escape anotada, no activada:
      si algún proyecto crece lo suficiente para que esto sea lento de
      verdad, `rank-bm25` es un reemplazo directo del adaptador sin tocar el
      puerto `LexicalIndex`.
- [x] **Resuelto — revisado tras el diseño de grupos explícitos (§9.2-9.4);
      sustituye la versión anterior de este punto.** Nombres de los flags de
      CLI, verificados contra el estilo real de `adapters/cli/main.py`
      (`--project`, `--language`, `--kind`, `--top-k`, `--include`,
      `--no-auto-include`):

      | Comando | Flag | Para qué |
      |---|---|---|
      | `crm project add` | `--no-role-classification` | Desactiva clasificación layer/role (§6.3) para ese proyecto |
      | `crm project add` | `--group <nombre>` | Declara el proyecto como parte de un grupo relacionado (§9.2) |
      | `crm search`, `crm chunks` | `--role <valor>` | Filtra por rol |
      | `crm search`, `crm chunks` | `--layer <valor>` | Filtra por capa |
      | `crm search` | `--related` | Busca también en los proyectos del mismo `group` (§9.3) |

      **`--workspace` y `--all-projects` de la versión anterior de este punto
      quedan descartados** — superados por el diseño de grupos: no hace
      falta un modo de servidor separado (la tool `search_related_projects`
      es condicional al `group` del proyecto activo, §9.3), y "todos los
      proyectos" sin acotar era precisamente el riesgo de fuga entre
      proyectos no relacionados que se corrigió en la discusión de §9.

      `crm project list` gana una columna `group` en su salida, para ver la
      relación entre proyectos de un vistazo sin abrir `~/.crm/projects.yaml`.

      Las tools MCP `search_code`/`list_chunks` ganan parámetros `role`/
      `layer` junto a `language`/`kind` ya existentes; `search_related_projects`
      es la tool nueva condicional de §9.3. Sin flag nuevo para
      `extra_synonyms` (punto 3): se edita a mano en `~/.crm/projects.yaml`.

      **Texto de `--help` (obligatorio, no un paso aparte — es el mismo
      `typer.Option(..., help="...")` que define el flag):**
      - `--no-role-classification`: *"No clasificar chunks por capa/rol arquitectónico (domain/controller/entity...)"*
      - `--group`: *"Nombre del grupo de proyectos relacionados (compartir el mismo nombre en varios 'crm project add' los relaciona); habilita búsqueda cruzada solo dentro del grupo"*
      - `--role`: *"Filtrar por rol arquitectónico (controller, entity, use_case, adapter, mapper, config, utility)"*
      - `--layer`: *"Filtrar por capa arquitectónica (domain, application, infrastructure...)"*
      - `--related`: *"Incluir también los proyectos del mismo grupo en la búsqueda (ver 'crm project list' para los grupos)"*

      También hay que actualizar los docstrings de `search`, `chunks`,
      `project_add` y `project_list` (Typer los muestra como descripción del
      comando en `--help`), igual que ya tiene `project_add` hoy.
- [x] **Resuelto.** Nivel 3 (§9): **se confirma 3b (búsqueda federada),
      redefinida como grupos explícitos declarados por registro** en vez de
      quedar condicionada a que apareciera evidencia en el banco de
      benchmarks — ese criterio original estaba roto (el banco está
      construido con preguntas ancladas a un único proyecto por diseño, así
      que nunca podría producir esa evidencia, exista o no la necesidad
      real). La necesidad real ya existe: `mic-inventory`/`mic-clients`/
      `mf-core-platform` son repos separados de un mismo sistema en
      producción (microservicios + micro-frontend). Diseño completo con sus
      salvaguardas en §9.2-9.4: grupos explícitos declarados por una
      persona (nunca por el LLM), tool `search_related_projects` condicional
      al `group` del proyecto activo (mismo patrón que el puente vault de
      `code-rag-mcp`), aviso activo de colisión cuando el mismo símbolo
      aparece en más de un proyecto del lote de resultados (caso real:
      `GlobalExceptionHandler` en `mic-inventory` y `mic-clients`), y
      `get_source`/`get_dependency_chain` sin ningún cambio — se quedan
      atados al proyecto activo para no reabrir el riesgo de resolver un
      símbolo ambiguo contra el proyecto equivocado en silencio. **3a (un
      proceso para varios `project_id`) sigue aparcado** — nada de esta
      discusión lo afecta, no hay evidencia operativa de que haga falta.

---

## 13. Glosario mínimo

- **Chunk** — unidad indexada de código (función, clase, método…), cortada
  por límites del propio lenguaje (parsing estructural), no por tamaño fijo.
- **Embedding** — vector numérico que representa el significado de un texto;
  textos con significado parecido producen vectores cercanos (similitud de
  coseno).
- **Recuperación léxica** — búsqueda por coincidencia de palabra/substring.
- **Recuperación semántica** — búsqueda por similitud de vectores.
- **Recuperación estructural** — recorrido de un grafo de relaciones
  explícitas del código (`implements`, `calls`, claves foráneas…).
- **BM25** — función de ranking léxico que pondera por rareza del término
  (IDF), satura la frecuencia repetida y normaliza por longitud de
  documento — ver §2.3.
- **top-k / recall@k / precisión** — vocabulario mínimo de evaluación: cuántos
  resultados se piden, qué fracción de lo relevante aparece entre ellos, y
  qué fracción de lo devuelto es realmente relevante.
- **Puerto / adaptador (arquitectura hexagonal)** — un puerto es una interfaz
  que aísla una decisión de infraestructura intercambiable (qué parser, qué
  proveedor de embeddings, qué base vectorial); un adaptador es la
  implementación concreta de un puerto. El dominio nunca depende de un
  adaptador, solo de puertos.
