from coderagmanager.domain.models import SearchResult
from coderagmanager.domain.ranking import merge_and_rerank

from tests.domain.test_models import make_chunk


def result(chunk_id: str, score: float, reason: str) -> SearchResult:
    chunk = make_chunk(id=chunk_id, symbol=f"sym_{chunk_id}")
    return SearchResult(chunk=chunk, score=score, match_reason=reason)


def test_merge_deduplicates_by_chunk_id():
    semantic = [result("a", 0.9, "semantic"), result("b", 0.5, "semantic")]
    lexical = [result("a", 3.0, "lexical")]

    merged = merge_and_rerank(semantic, lexical, top_k=10)

    ids = [r.chunk.id for r in merged]
    assert ids.count("a") == 1
    assert merged[0].chunk.id == "a"
    assert merged[0].match_reason == "hybrid"


def test_merge_respects_top_k():
    semantic = [result(str(i), 1.0 - i * 0.1, "semantic") for i in range(5)]
    merged = merge_and_rerank(semantic, [], top_k=3)
    assert len(merged) == 3


def test_lexical_only_results_survive():
    lexical = [result("x", 2.0, "lexical")]
    merged = merge_and_rerank([], lexical, top_k=5)
    assert merged[0].chunk.id == "x"
    assert merged[0].match_reason == "lexical"
