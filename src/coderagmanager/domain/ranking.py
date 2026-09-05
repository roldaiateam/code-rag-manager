"""Combinación de rankings semántico y léxico (retrieval híbrido).

Función de dominio pura: normaliza ambas listas a [0, 1], combina con
ponderación fija y deduplica por chunk.id.
"""

from __future__ import annotations

from coderagmanager.domain.models import SearchResult

SEMANTIC_WEIGHT = 0.6
LEXICAL_WEIGHT = 0.4
SEMANTIC_CONFIDENCE_THRESHOLD = 0.35
LEXICAL_CONFIDENCE_THRESHOLD = 0.0


def _normalize(results: list[SearchResult]) -> dict[str, float]:
    if not results:
        return {}
    scores = [r.score for r in results]
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return {r.chunk.id: 1.0 for r in results}
    return {r.chunk.id: (r.score - lo) / (hi - lo) for r in results}


def merge_and_rerank(
    semantic: list[SearchResult],
    lexical: list[SearchResult],
    top_k: int,
) -> list[SearchResult]:
    sem_scores = _normalize(semantic)
    lex_scores = _normalize(lexical)
    chunks = {r.chunk.id: r.chunk for r in [*semantic, *lexical]}

    merged: list[SearchResult] = []
    for chunk_id, chunk in chunks.items():
        in_sem = chunk_id in sem_scores
        in_lex = chunk_id in lex_scores
        score = (
            SEMANTIC_WEIGHT * sem_scores.get(chunk_id, 0.0)
            + LEXICAL_WEIGHT * lex_scores.get(chunk_id, 0.0)
        )
        reason = "hybrid" if (in_sem and in_lex) else ("semantic" if in_sem else "lexical")
        merged.append(SearchResult(chunk=chunk, score=score, match_reason=reason))

    merged.sort(key=lambda r: r.score, reverse=True)
    return merged[:top_k]


def is_low_confidence(
    semantic: list[SearchResult], lexical: list[SearchResult]
) -> bool:
    """True si ningún canal encontró señal real para la consulta (US-02).

    Se evalúa sobre los scores CRUDOS, antes de merge_and_rerank: su
    normalización min-max estira el mejor resultado de cualquier lote no
    vacío hacia 1.0, así que aplicar el umbral después de normalizar nunca
    dispararía. best_lexical == 0.0 equivale en la práctica a "sin hits
    léxicos en absoluto", porque SubstringLexicalIndex solo devuelve
    resultados con score > 0.
    """
    best_semantic = max((r.score for r in semantic), default=0.0)
    best_lexical = max((r.score for r in lexical), default=0.0)
    return (
        best_semantic < SEMANTIC_CONFIDENCE_THRESHOLD
        and best_lexical == LEXICAL_CONFIDENCE_THRESHOLD
    )
