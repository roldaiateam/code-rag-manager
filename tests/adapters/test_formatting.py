from coderagmanager.adapters.formatting import (
    LOW_CONFIDENCE_NOTICE,
    format_chunks,
    format_search_results,
)
from coderagmanager.domain.models import SearchResult

from tests.domain.test_models import make_chunk


def test_format_search_results_prefixes_notice_when_low_confidence():
    results = [SearchResult(chunk=make_chunk(), score=0.1, match_reason="semantic")]

    output = format_search_results(results, low_confidence=True)

    assert output.startswith(LOW_CONFIDENCE_NOTICE)
    assert "calcular_total" in output


def test_format_search_results_no_notice_by_default():
    results = [SearchResult(chunk=make_chunk(), score=0.9, match_reason="semantic")]

    output = format_search_results(results)

    assert LOW_CONFIDENCE_NOTICE not in output


def test_format_chunks_caps_rows_with_notice():
    chunks = [make_chunk(id=str(i), symbol=f"sym{i}") for i in range(250)]
    result = format_chunks(chunks, max_rows=200)
    lines = result.splitlines()
    assert len(lines) == 201  # 200 filas + aviso
    assert "mostrando 200 de 250" in lines[-1]


def test_format_chunks_no_notice_under_cap():
    chunks = [make_chunk(id=str(i)) for i in range(5)]
    result = format_chunks(chunks)
    assert "mostrando" not in result
