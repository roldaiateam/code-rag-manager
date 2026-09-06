from coderagmanager.application.search_code import SearchCode
from coderagmanager.domain.models import SearchQuery

from tests.application.fakes import FakeEmbedder, FakeLexicalIndex, FakeVectorStore
from tests.domain.test_models import make_chunk


def test_search_combines_semantic_and_lexical():
    vector_store = FakeVectorStore()
    lexical = FakeLexicalIndex()
    semantic_chunk = make_chunk(id="s1", symbol="validar_correo")
    lexical_chunk = make_chunk(id="l1", symbol="EmailValidator")
    vector_store.upsert("p1", [semantic_chunk])
    lexical.index("p1", [lexical_chunk])

    use_case = SearchCode("p1", FakeEmbedder(), vector_store, lexical)
    outcome = use_case.execute(SearchQuery(text="emailvalidator", top_k=5))

    ids = {r.chunk.id for r in outcome.results}
    assert {"s1", "l1"} <= ids
    # FakeVectorStore siempre da score >= 0.9 al primer resultado: nunca
    # debería marcarse como baja confianza cuando hay señal real.
    assert outcome.low_confidence is False


def test_search_filters_by_language_and_kind():
    vector_store = FakeVectorStore()
    vector_store.upsert("p1", [
        make_chunk(id="a", language="python", kind="function"),
        make_chunk(id="b", language="java", kind="class"),
    ])
    use_case = SearchCode("p1", FakeEmbedder(), vector_store, FakeLexicalIndex())

    outcome = use_case.execute(SearchQuery(text="algo", language="java"))
    assert [r.chunk.id for r in outcome.results] == ["b"]

    outcome = use_case.execute(SearchQuery(text="algo", kind="function"))
    assert [r.chunk.id for r in outcome.results] == ["a"]


def test_search_filters_by_role_and_layer():
    vector_store = FakeVectorStore()
    vector_store.upsert("p1", [
        make_chunk(id="a", role="controller", layer="infrastructure"),
        make_chunk(id="b", role="entity", layer="domain"),
    ])
    use_case = SearchCode("p1", FakeEmbedder(), vector_store, FakeLexicalIndex())

    outcome = use_case.execute(SearchQuery(text="algo", role="controller"))
    assert [r.chunk.id for r in outcome.results] == ["a"]

    outcome = use_case.execute(SearchQuery(text="algo", layer="domain"))
    assert [r.chunk.id for r in outcome.results] == ["b"]


def test_search_flags_low_confidence_when_nothing_indexed():
    # Sin chunks en absoluto: mejor semántico crudo = 0.0 (< 0.35) y mejor
    # léxico crudo = 0.0 (sin hits) -> baja confianza, resultados vacíos.
    use_case = SearchCode("p1", FakeEmbedder(), FakeVectorStore(), FakeLexicalIndex())

    outcome = use_case.execute(SearchQuery(text="algo que no existe"))

    assert outcome.results == []
    assert outcome.low_confidence is True
