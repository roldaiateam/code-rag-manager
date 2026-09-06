from coderagmanager.application.list_chunks import ListChunks

from tests.application.fakes import FakeVectorStore
from tests.domain.test_models import make_chunk


def test_list_chunks_filters_by_role_and_layer():
    vector_store = FakeVectorStore()
    vector_store.upsert("p1", [
        make_chunk(id="a", role="controller", layer="infrastructure"),
        make_chunk(id="b", role="entity", layer="domain"),
        make_chunk(id="c", role="entity", layer="infrastructure"),
    ])
    use_case = ListChunks("p1", vector_store)

    assert [c.id for c in use_case.execute(role="entity")] == ["b", "c"]
    assert [c.id for c in use_case.execute(layer="infrastructure")] == ["a", "c"]
    assert [c.id for c in use_case.execute(role="entity", layer="infrastructure")] == ["c"]


def test_list_chunks_with_no_matching_role_returns_empty():
    vector_store = FakeVectorStore()
    vector_store.upsert("p1", [make_chunk(id="a")])
    use_case = ListChunks("p1", vector_store)

    assert use_case.execute(role="controller") == []
