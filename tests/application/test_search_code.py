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
    results = use_case.execute(SearchQuery(text="emailvalidator", top_k=5))

    ids = {r.chunk.id for r in results}
    assert {"s1", "l1"} <= ids


def test_search_filters_by_language_and_kind():
    vector_store = FakeVectorStore()
    vector_store.upsert("p1", [
        make_chunk(id="a", language="python", kind="function"),
        make_chunk(id="b", language="java", kind="class"),
    ])
    use_case = SearchCode("p1", FakeEmbedder(), vector_store, FakeLexicalIndex())

    results = use_case.execute(SearchQuery(text="algo", language="java"))
    assert [r.chunk.id for r in results] == ["b"]

    results = use_case.execute(SearchQuery(text="algo", kind="function"))
    assert [r.chunk.id for r in results] == ["a"]
