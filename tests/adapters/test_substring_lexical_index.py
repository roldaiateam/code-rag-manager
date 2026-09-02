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


def test_term_only_in_source_text_is_still_found():
    chunks = [
        make_chunk(
            id="a",
            symbol="run_e2e_suite",
            file_path="ci/pipeline.py",
            source_text="def run_e2e_suite():\n    return playwright.launch()",
        )
    ]
    results = build_index(chunks).search("p1", "playwright", top_k=10)
    assert [r.chunk.id for r in results] == ["a"]
    assert results[0].score > 0


def test_source_text_match_does_not_change_symbol_or_path_scoring():
    chunks = [
        make_chunk(
            id="a",
            symbol="validar_email",
            file_path="src/usuarios.py",
            source_text="def validar_email(value):\n    return '@' in value",
        ),
        make_chunk(
            id="b",
            symbol="guardar",
            file_path="src/email_utils.py",
            source_text="def guardar(value):\n    return value",
        ),
    ]
    before = build_index(chunks).search("p1", "email", top_k=10)
    # ahora un tercer chunk que solo tiene el término en source_text, con peso
    # menor: no debe alterar el orden ni la puntuación de los dos anteriores.
    chunks_with_extra = chunks + [
        make_chunk(
            id="c",
            symbol="calcular_total",
            file_path="src/carrito.py",
            source_text="# nota: revisar tema email más adelante",
        )
    ]
    after = build_index(chunks_with_extra).search("p1", "email", top_k=10)
    after_by_id = {r.chunk.id: r.score for r in after}
    assert after_by_id["a"] == before[0].score
    assert after_by_id["b"] == before[1].score
    assert [r.chunk.id for r in after[:2]] == ["a", "b"]
