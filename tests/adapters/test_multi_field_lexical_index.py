from coderagmanager.adapters.storage.substring_lexical_index import (
    MultiFieldLexicalIndex,
)
from coderagmanager.domain.models import DependencyEdge, EdgeType

from tests.application.fakes import FakeGraphStore
from tests.domain.test_models import make_chunk


def build_index(chunks, graph_store=None):
    return MultiFieldLexicalIndex(
        chunk_provider=lambda project_id: chunks,
        graph_store=graph_store or FakeGraphStore(),
    )


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


def test_token_overlap_finds_match_without_literal_substring():
    # "validate" no es substring de "Validation failed." — la coincidencia
    # solo aparece por stemming (US-05), no existía con substring puro.
    chunks = [
        make_chunk(
            id="a",
            symbol="handleConstraintViolation",
            file_path="src/errors.py",
            source_text='raise Error("Validation failed.")',
        )
    ]
    results = build_index(chunks).search("p1", "validate", top_k=10)
    assert [r.chunk.id for r in results] == ["a"]


def test_synonym_expansion_finds_match():
    chunks = [make_chunk(id="a", symbol="create_user")]
    results = build_index(chunks).search("p1", "add user", top_k=10)
    assert [r.chunk.id for r in results] == ["a"]


def test_calls_signal_read_from_graph_not_from_chunk():
    caller = make_chunk(id="a", symbol="process_signup", file_path="src/signup.py")
    callee = make_chunk(id="b", symbol="sendEmailNotification", file_path="src/mail.py")
    graph_store = FakeGraphStore()
    graph_store.upsert_nodes("p1", [caller, callee])
    graph_store.upsert_edges("p1", [DependencyEdge("a", "b", EdgeType.CALLS)])

    results = build_index([caller, callee], graph_store).search(
        "p1", "email notification", top_k=10
    )
    result_by_id = {r.chunk.id: r.score for r in results}
    assert "a" in result_by_id  # solo por la señal "calls", no tiene "email" propio
    assert result_by_id["a"] < result_by_id["b"]  # más débil que el match directo


def test_cache_rebuilds_on_index_call():
    index = build_index([make_chunk(id="a", symbol="old_chunk")])
    assert index.search("p1", "old", top_k=10) != []

    # Simula un reindex: el proyecto ya no tiene el chunk viejo.
    index.index("p1", [make_chunk(id="b", symbol="new_chunk")])
    assert index.search("p1", "old", top_k=10) == []
    assert [r.chunk.id for r in index.search("p1", "new", top_k=10)] == ["b"]


def test_lazy_build_without_calling_index_first():
    # Simula un proceso nuevo (p. ej. "crm search") que nunca llama a
    # index() en este proceso, solo lee el índice ya persistido.
    index = MultiFieldLexicalIndex(
        chunk_provider=lambda project_id: [make_chunk(id="a", symbol="calcular_total")],
        graph_store=FakeGraphStore(),
    )
    results = index.search("p1", "calcular", top_k=10)
    assert [r.chunk.id for r in results] == ["a"]
