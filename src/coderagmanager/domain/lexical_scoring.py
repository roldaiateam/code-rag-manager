"""Scoring léxico multi-campo (US-05): mismo estilo heurístico ponderado que
ya usaba `SubstringLexicalIndex` (symbol > file_path > source_text), pero
comparando conjuntos de tokens (vía `domain/tokenizer.py`) en vez de
substrings, y sumando dos señales que antes se ignoraban: `calls` (leído del
grafo de dependencias, no de una lista nueva en `CodeChunk`) y `role`/`layer`
(usados solo si el chunk ya los trae puestos).

Separado del adaptador de almacenamiento igual que ya está separado
`domain/ranking.py::merge_and_rerank` de `VectorStore`/`LexicalIndex`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from coderagmanager.domain.models import CodeChunk, SearchResult
from coderagmanager.domain.tokenizer import tokenize

SYMBOL_WEIGHT = 2.0
FILE_PATH_WEIGHT = 1.0
SOURCE_TEXT_WEIGHT = 0.5
CALLS_WEIGHT = 0.5
ROLE_WEIGHT = 1.0
LAYER_WEIGHT = 1.0

@dataclass(frozen=True)
class ChunkTokens:
    """Tokens de un chunk, calculados una vez y cacheados por el adaptador
    (ver `MultiFieldLexicalIndex`) — nunca recalculados en cada búsqueda."""

    chunk: CodeChunk
    symbol: set[str]
    file_path: set[str]
    source_text: set[str]
    calls: set[str] = field(default_factory=set)
    role: set[str] = field(default_factory=set)
    layer: set[str] = field(default_factory=set)


def tokenize_chunk(
    chunk: CodeChunk,
    *,
    called_symbols: Iterable[str] = (),
    role: str | None = None,
    layer: str | None = None,
) -> ChunkTokens:
    """`role`/`layer` llegan resueltos por el llamador, no leídos aquí:
    `CodeChunk` todavía no tiene esos campos (los añade US-06) y este módulo
    no necesita saberlo — el adaptador decide cómo obtenerlos hoy
    (`getattr(chunk, "role", None)`, siempre `None` por ahora)."""
    return ChunkTokens(
        chunk=chunk,
        symbol=tokenize(chunk.symbol),
        file_path=tokenize(chunk.file_path),
        source_text=tokenize(chunk.source_text),
        calls=tokenize(" ".join(called_symbols)),
        role=tokenize(role) if role else set(),
        layer=tokenize(layer) if layer else set(),
    )


def score_chunk(query_tokens: set[str], chunk_tokens: ChunkTokens) -> float:
    """Por cada token de la consulta presente en un campo, suma el peso de
    ese campo — una vez por token distinto, no por ocurrencias (misma regla
    que ya fijó US-01 para `source_text`), ahora aplicada a los seis campos."""
    score = 0.0
    for term in query_tokens:
        if term in chunk_tokens.symbol:
            score += SYMBOL_WEIGHT
        if term in chunk_tokens.file_path:
            score += FILE_PATH_WEIGHT
        if term in chunk_tokens.source_text:
            score += SOURCE_TEXT_WEIGHT
        if term in chunk_tokens.calls:
            score += CALLS_WEIGHT
        if term in chunk_tokens.role:
            score += ROLE_WEIGHT
        if term in chunk_tokens.layer:
            score += LAYER_WEIGHT
    return score


def rank(
    query_tokens: set[str], indexed: list[ChunkTokens], top_k: int
) -> list[SearchResult]:
    scored = [
        SearchResult(chunk=ct.chunk, score=s, match_reason="lexical")
        for ct in indexed
        if (s := score_chunk(query_tokens, ct)) > 0
    ]
    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:top_k]
