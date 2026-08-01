# Guía: cómo construir tu propio gestor de code-RAGs

Esta es una guía didáctica y de referencia para diseñar y construir, **desde cero**, un sistema que:

1. Indexa proyectos de código (Python, JavaScript, Java, y cualquier otro lenguaje que le añadas) para que un agente LLM pueda entenderlos sin leer todos los ficheros.
2. Mantiene ese índice actualizado automáticamente, disparando el reindexado desde GitHub Actions.
3. Expone el índice a través de un servidor **MCP** (Model Context Protocol) que puede conectarse a Claude Code, Codex CLI, GitHub Copilot CLI y, en el futuro, a cualquier otro cliente que hable MCP.
4. Gestiona **varios proyectos a la vez** desde una única instalación.
5. Está construido con **arquitectura hexagonal** (puertos y adaptadores), para que soportar un lenguaje nuevo, un proveedor de embeddings nuevo, un vector store nuevo o un cliente nuevo sea añadir un adaptador, no reescribir el núcleo.

No es el código del proyecto. Es la guía que te permite construirlo tú mismo, entendiendo cada decisión de diseño y cada concepto de IA que hay detrás.

## Para quién es esta guía

Para alguien con **conocimientos básicos de IA**: sabes qué es un LLM, has oído hablar de embeddings y de RAG, pero no has entrado en el detalle de cómo se construye un sistema de recuperación real, ni de cómo se diseña una arquitectura que lo sostenga en producción a lo largo del tiempo (nuevos lenguajes, nuevos proyectos, nuevos clientes). Cada capítulo técnico empieza explicando el concepto antes de mostrar cómo se aplica.

## Cómo está organizada

La guía tiene dos tipos de capítulos:

- **Capítulos de fundamentos** (`01`, `02`): conceptos de IA/RAG que necesitas antes de diseñar nada. Si ya dominas embeddings, vectores y chunking, puedes hojearlos rápido.
- **Capítulos de diseño y construcción** (`03` a `12`): decisiones de arquitectura y cómo implementarlas, en orden de dependencia — cada uno se apoya en los anteriores.

| # | Capítulo | Qué responde |
|---|----------|---------------|
| [00](00-vision-general.md) | Visión general | ¿Qué voy a construir exactamente y cómo encajan las piezas? |
| [01](01-fundamentos-rag.md) | Fundamentos de RAG | ¿Qué es un RAG, qué es un embedding, qué se persiste realmente? |
| [02](02-code-rag-particularidades.md) | Particularidades del code-RAG | ¿Por qué el código no se indexa como si fuera un PDF? |
| [03](03-arquitectura-hexagonal.md) | Arquitectura hexagonal | ¿Cómo organizo el proyecto para que sea extensible de verdad? |
| [04](04-diseno-multi-proyecto.md) | Diseño multi-proyecto | ¿Cómo gestiono varios repos indexados a la vez? |
| [05](05-parsing-multilenguaje.md) | Parsing multi-lenguaje | ¿Cómo trocea el código en unidades con sentido, en cualquier lenguaje? |
| [06](06-embeddings-vector-store.md) | Embeddings y vector store | ¿Qué modelo uso, dónde guardo los vectores, cómo busco? |
| [07](07-indexacion-incremental.md) | Indexación incremental | ¿Cómo reindexo solo lo que cambió, sin rehacer todo cada vez? |
| [08](08-servidor-mcp.md) | Servidor MCP | ¿Cómo expongo el índice como herramientas para un agente LLM? |
| [09](09-integracion-clientes.md) | Integración con clientes | ¿Cómo lo conecto a Claude Code, Codex CLI y Copilot CLI? |
| [10](10-github-actions.md) | GitHub Actions | ¿Cómo se reindexa solo, automáticamente, en cada push? |
| [11](11-cli-y-empaquetado.md) | CLI y empaquetado | ¿Cómo lo distribuyo como una herramienta instalable? |
| [12](12-guia-paso-a-paso.md) | Guía paso a paso | ¿Por dónde empiezo a construir, en qué orden, cómo sé que voy bien? |
| [13](13-glosario-y-referencias.md) | Glosario y referencias | ¿Qué significa este término que no conozco? |

**[FINAL-DESIGN.md](FINAL-DESIGN.md)** — todas las decisiones abiertas de la guía, ya tomadas y concretadas (nombre real del proyecto `CodeRagManager`/`crm`, reindexado siempre completo, un servidor MCP por proyecto, etc.). Léelo cuando quieras dejar de decidir y empezar a construir.

**[RAG-PASO-A-PASO.md](RAG-PASO-A-PASO.md)** — un único ejemplo real (`carrito.py`) seguido paso a paso desde el código fuente hasta la respuesta del agente: chunking, embedding, persistencia y búsqueda por similitud, con valores concretos en cada paso y una sección final que responde "¿dónde está exactamente el RAG?".

## Orden de lectura recomendado

Si es tu primera vez con RAG: de principio a fin, en orden. Cada capítulo asume que ya leíste los anteriores.

Si ya conoces bien los fundamentos: lee `00` para el mapa general, salta a `03` (arquitectura) y usa el resto como referencia según construyes, apoyándote en `12` como checklist.

Si solo quieres saber "¿cómo conecto esto a Claude Code?": ve directo a `09`, pero necesitarás haber construido lo de `08` primero.

## Punto de partida: qué ya existe en este repositorio

Antes de escribir una sola línea, merece la pena mirar los dos proyectos hermanos de esta misma carpeta (`ai/`), porque resuelven partes del problema y sus decisiones (buenas y limitadas) informan el diseño de esta guía:

- **`code-rag-mcp`**: un servidor MCP en Java que ya indexa código (solo Java) y expone búsqueda y navegación de dependencias. No usa embeddings — es un índice léxico y estructural. Es la referencia para el capítulo `02` (por qué el código necesita algo más que "trocear y vectorizar") y para el algoritmo de reindexado incremental del capítulo `07`.
- **`kairosai`**: un gestor de configuración multi-workspace para Claude Code, en Python. No hace RAG, pero ya resuelve "gestionar varios repos a la vez" con un registro por workspace — la base del capítulo `04`.

Cada capítulo técnico cierra con una sección **"Ideas reutilizables de los proyectos existentes"** citando el patrón concreto de uno de los dos cuando aplica.

## Nombre de ejemplo usado en la guía

A lo largo de los capítulos se usa `codehex` como nombre de ejemplo del proyecto (paquete Python, comando CLI, carpeta de configuración `.codehex/`). Es un placeholder — elige el nombre que prefieras para tu proyecto real; solo sustituye las apariciones de `codehex` de forma consistente.
