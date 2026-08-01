from coderagmanager.adapters.storage.substring_lexical_index import (
    SubstringLexicalIndex,
)

from tests.domain.test_models import make_chunk


def build_index(chunks):
    return SubstringLexicalIndex(chunk_provider=lambda project_id: chunks)


def test_symbol_match_scores_higher_than_path_match():
    chunks = [
        make_chunk(id="a", symbol="validar_email", file_path="src/usuarios.py"),
        make_chunk(id="b", symbol="guardar", file_path="src/email_utils.py"),
    ]
    results = build_index(chunks).search("p1", "email", top_k=10)
    assert [r.chunk.id for r in results] == ["a", "b"]
    assert results[0].score > results[1].score


def test_no_match_returns_empty():
    chunks = [make_chunk(id="a", symbol="calcular_total")]
    assert build_index(chunks).search("p1", "inexistente", top_k=10) == []


def test_multiple_terms_accumulate():
    chunks = [
        make_chunk(id="a", symbol="validar_email_usuario"),
        make_chunk(id="b", symbol="validar_telefono"),
    ]
    results = build_index(chunks).search("p1", "validar email", top_k=10)
    assert results[0].chunk.id == "a"
