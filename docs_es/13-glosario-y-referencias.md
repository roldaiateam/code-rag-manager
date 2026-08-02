# 13 · Glosario y referencias

## Glosario

**Adaptador** — En arquitectura hexagonal, la implementación concreta de un puerto (p.ej. `LanceDbVectorStore` implementa el puerto `VectorStore`). Vive fuera del dominio y sabe de librerías externas.

**AST (Abstract Syntax Tree)** — Árbol de sintaxis abstracta: representación estructurada del código fuente producida por un parser, donde cada nodo es una construcción del lenguaje (función, clase, llamada...).

**Chunk** — Unidad más pequeña en la que se divide el código (o texto) para indexar; idealmente respeta límites sintácticos (función, clase) en vez de cortar por tamaño fijo. Ver capítulo 02.

**Chunking** — El proceso de dividir un documento o repositorio en chunks.

**Cosine similarity (similitud coseno)** — Medida de cercanía entre dos vectores basada en el ángulo entre ellos; va de -1 (opuestos) a 1 (misma dirección). Es la métrica típica para comparar embeddings.

**Dominio** — En arquitectura hexagonal, el núcleo de reglas y entidades propias del problema, sin dependencias de infraestructura externa.

**Embedding** — Vector numérico que representa el significado de un texto, generado por un modelo entrenado para ello. Textos con significado parecido producen vectores cercanos.

**Grafo de dependencias** — Estructura de nodos (chunks) y aristas (relaciones: implementa, extiende, llama a, importa) extraída del código, que permite responder preguntas de navegación estructural.

**Hexagonal (arquitectura) / Ports & adapters** — Patrón que separa el dominio de la infraestructura mediante interfaces (puertos) implementadas por adaptadores intercambiables. Ver capítulo 03.

**Indexación incremental** — Reindexar solo lo que cambió desde la última vez (normalmente vía `git diff`), en vez de reprocesar el repositorio completo. Ver capítulo 07.

**JSON-RPC 2.0** — Formato de mensajes usado por MCP: peticiones y respuestas como objetos JSON con `method`/`params`/`id` y `result`/`error`.

**k-NN / ANN (k-nearest neighbors / approximate nearest neighbors)** — El problema que resuelve un vector store: encontrar los k vectores más cercanos a uno dado. "Approximate" porque, a gran escala, se sacrifica algo de precisión exacta por velocidad.

**MCP (Model Context Protocol)** — Protocolo abierto para que un agente LLM descubra y use herramientas externas (tools) de forma estandarizada, independientemente del cliente (Claude Code, Codex CLI, Copilot CLI...). Ver capítulo 08.

**Puerto** — En arquitectura hexagonal, una interfaz que el dominio/aplicación necesita, sin especificar cómo se implementa. Ver capítulo 03.

**RAG (Retrieval-Augmented Generation)** — Técnica que combina recuperación de información relevante (retrieval) con generación de texto por un LLM, en vez de depender solo de lo que el modelo "recuerda" de su entrenamiento. Ver capítulo 01.

**Recall@k** — Métrica de calidad de retrieval: de todos los resultados realmente relevantes para una consulta, qué fracción aparece entre los primeros k resultados devueltos.

**Retrieval híbrido** — Combinación de búsqueda semántica (embeddings), léxica (coincidencia de texto/keywords) y, en el caso de código, estructural (grafo de dependencias) para mejorar sobre cualquiera de las tres por separado. Ver capítulo 02.

**Stdio (transporte)** — Forma de comunicación de un servidor MCP local: el cliente escribe peticiones en la entrada estándar del proceso servidor y lee respuestas de su salida estándar. No requiere red ni puertos.

**Token** — Unidad mínima de texto que procesa un modelo de lenguaje (aproximadamente una palabra o fragmento de palabra). Relevante para el límite de contexto de un LLM y, en algunos proveedores, para el coste de generar embeddings (facturado por token).

**Tool (en MCP)** — Una función expuesta por un servidor MCP, con nombre, descripción e `inputSchema`, que un cliente LLM puede decidir invocar según su descripción.

**Top-k** — Número de resultados que devuelve una búsqueda (p.ej. "los 10 chunks más relevantes").

**tree-sitter** — Generador de parsers incremental con gramáticas para múltiples lenguajes, usado para producir el AST del que se extraen los chunks. Ver capítulo 05.

**Vector store** — Almacén especializado en guardar vectores (embeddings) junto a sus metadatos y responder eficientemente a consultas de similitud (k-NN/ANN). Ver capítulo 06.

## Referencias para profundizar

Al ser un campo que evoluciona rápido (modelos de embeddings, SDKs de MCP, formatos de configuración de clientes), prioriza siempre la documentación oficial vigente sobre lo escrito aquí si detectas una discrepancia:

- **Especificación de MCP**: sitio oficial del Model Context Protocol (`modelcontextprotocol.io`) — la fuente de verdad del protocolo en sí, independiente de cualquier cliente concreto.
- **Documentación de Claude Code sobre MCP**: sección de MCP en la documentación oficial de Claude Code (`code.claude.com/docs`).
- **Documentación de Codex CLI sobre MCP**: sección de extensibilidad/MCP en la documentación oficial de Codex (bajo `developers.openai.com` / `learn.chatgpt.com`, según la organización de la documentación en el momento de consulta).
- **Documentación de GitHub Copilot CLI sobre MCP**: sección "Adding MCP servers" en `docs.github.com`, bajo Copilot CLI.
- **tree-sitter**: documentación oficial del proyecto y de los bindings de Python (`tree-sitter`, más los paquetes de gramática por lenguaje, p.ej. `tree-sitter-python`).
- **LanceDB / ChromaDB**: documentación oficial de cada proyecto para la API concreta de creación de tablas/colecciones y búsqueda.

## Vuelve a empezar

[README](README.md) — índice completo de la guía.
