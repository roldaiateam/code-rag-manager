# Guide: how to build your own code-RAG manager

This is a didactic and reference guide for designing and building, **from scratch**, a system that:

1. Indexes code projects (Python, JavaScript, Java, and any other language you add) so an LLM agent can understand them without reading every file.
2. Keeps that index automatically up to date, triggering reindexing from GitHub Actions.
3. Exposes the index through an **MCP** (Model Context Protocol) server that can connect to Claude Code, Codex CLI, GitHub Copilot CLI, and, in the future, any other MCP-speaking client.
4. Manages **several projects at once** from a single installation.
5. Is built with **hexagonal architecture** (ports and adapters), so that supporting a new language, a new embedding provider, a new vector store, or a new client means adding an adapter, not rewriting the core.

This is not the project's code. It's the guide that lets you build it yourself, understanding every design decision and every AI concept behind it.

## Who this guide is for

For someone with **basic AI knowledge**: you know what an LLM is, you've heard of embeddings and RAG, but you haven't gone into the detail of how a real retrieval system is built, or how to design an architecture that sustains it in production over time (new languages, new projects, new clients). Each technical chapter starts by explaining the concept before showing how it's applied.

## How it's organized

The guide has two kinds of chapters:

- **Fundamentals chapters** (`01`, `02`): AI/RAG concepts you need before designing anything. If you already have a solid grasp of embeddings, vectors, and chunking, you can skim these quickly.
- **Design and build chapters** (`03` to `12`): architecture decisions and how to implement them, in dependency order — each one builds on the previous ones.

| # | Chapter | What it answers |
|---|----------|---------------|
| [00](00-vision-general.md) | Overview | What exactly am I going to build and how do the pieces fit together? |
| [01](01-fundamentos-rag.md) | RAG fundamentals | What is a RAG, what is an embedding, what actually gets persisted? |
| [02](02-code-rag-particularidades.md) | Code-RAG particularities | Why isn't code indexed the same way as a PDF? |
| [03](03-arquitectura-hexagonal.md) | Hexagonal architecture | How do I organize the project so it's genuinely extensible? |
| [04](04-diseno-multi-proyecto.md) | Multi-project design | How do I manage several indexed repos at once? |
| [05](05-parsing-multilenguaje.md) | Multi-language parsing | How do I split code into meaningful units, in any language? |
| [06](06-embeddings-vector-store.md) | Embeddings and vector store | Which model do I use, where do I store the vectors, how do I search? |
| [07](07-indexacion-incremental.md) | Incremental indexing | How do I reindex only what changed, without redoing everything each time? |
| [08](08-servidor-mcp.md) | MCP server | How do I expose the index as tools for an LLM agent? |
| [09](09-integracion-clientes.md) | Client integration | How do I connect it to Claude Code, Codex CLI, and Copilot CLI? |
| [10](10-github-actions.md) | GitHub Actions | How does it reindex itself automatically on every push? |
| [11](11-cli-y-empaquetado.md) | CLI and packaging | How do I distribute it as an installable tool? |
| [12](12-guia-paso-a-paso.md) | Step-by-step guide | Where do I start building, in what order, how do I know I'm on track? |
| [13](13-glosario-y-referencias.md) | Glossary and references | What does this term I don't know mean? |

**[FINAL-DESIGN.md](FINAL-DESIGN.md)** — all of the guide's open decisions, already made and settled (the project's real name `CodeRagManager`/`crm`, always-full reindexing, one MCP server per project, etc.). Read it when you want to stop deciding and start building.

**[RAG-PASO-A-PASO.md](RAG-PASO-A-PASO.md)** — a single real example (`carrito.py`) followed step by step from source code to the agent's answer: chunking, embedding, persistence, and similarity search, with concrete values at each step and a final section answering "where exactly is the RAG?".

## Recommended reading order

If this is your first time with RAG: start to finish, in order. Each chapter assumes you've already read the previous ones.

If you already know the fundamentals well: read `00` for the general map, jump to `03` (architecture), and use the rest as reference as you build, leaning on `12` as a checklist.

If you just want to know "how do I connect this to Claude Code?": go straight to `09`, but you'll need to have built what's in `08` first.

## Starting point: what already exists in this repository

Before writing a single line, it's worth looking at the two sibling projects in this same folder (`ai/`), because they solve parts of the problem and their decisions (good and limited) inform the design of this guide:

- **`code-rag-mcp`**: an MCP server in Java that already indexes code (Java only) and exposes search and dependency navigation. It doesn't use embeddings — it's a lexical and structural index. It's the reference for chapter `02` (why code needs something more than "chunk and vectorize") and for the incremental reindexing algorithm in chapter `07`.
- **`kairosai`**: a multi-workspace configuration manager for Claude Code, in Python. It doesn't do RAG, but it already solves "manage several repos at once" with a per-workspace registry — the basis for chapter `04`.

Each technical chapter closes with a **"Reusable ideas from existing projects"** section citing the concrete pattern from one of the two, when applicable.

## Example name used in the guide

Throughout the chapters, `codehex` is used as the example project name (Python package, CLI command, `.codehex/` config folder). It's a placeholder — pick whatever name you prefer for your real project; just replace the occurrences of `codehex` consistently.
