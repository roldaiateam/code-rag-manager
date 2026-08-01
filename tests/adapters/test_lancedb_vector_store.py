from dataclasses import replace

from coderagmanager.adapters.storage.lancedb_vector_store import LanceDbVectorStore

from tests.domain.test_models import make_chunk


def chunk_with_vector(chunk_id, symbol, vector, **overrides):
    return replace(make_chunk(id=chunk_id, symbol=symbol, **overrides), embedding=vector)


def test_upsert_search_and_list(tmp_path):
    store = LanceDbVectorStore(str(tmp_path))
    store.upsert("p1", [
        chunk_with_vector("a", "validar_email", [1.0, 0.0]),
        chunk_with_vector("b", "conectar_bd", [0.0, 1.0]),
    ])

    results = store.search("p1", [0.9, 0.1], top_k=2)
    assert results[0].chunk.symbol == "validar_email"
    assert results[0].score > results[1].score
    assert results[0].match_reason == "semantic"
    assert results[0].chunk.source_text  # source_text viaja en el índice

    listed = store.list("p1")
    assert {c.id for c in listed} == {"a", "b"}


def test_drop_and_rebuild_removes_stale_chunks(tmp_path):
    store = LanceDbVectorStore(str(tmp_path))
    store.upsert("p1", [chunk_with_vector("viejo", "borrado", [1.0, 0.0])])
    store.drop("p1")
    store.upsert("p1", [chunk_with_vector("nuevo", "vigente", [0.0, 1.0])])

    assert [c.id for c in store.list("p1")] == ["nuevo"]


def test_projects_are_isolated(tmp_path):
    store = LanceDbVectorStore(str(tmp_path))
    store.upsert("p1", [chunk_with_vector("a", "solo_p1", [1.0, 0.0])])
    store.upsert("p2", [chunk_with_vector("b", "solo_p2", [0.0, 1.0])])

    assert [c.symbol for c in store.list("p1")] == ["solo_p1"]
    assert [c.symbol for c in store.list("p2")] == ["solo_p2"]
    assert all(r.chunk.symbol == "solo_p1" for r in store.search("p1", [1.0, 0.0], 10))


def test_search_on_missing_project_returns_empty(tmp_path):
    store = LanceDbVectorStore(str(tmp_path))
    assert store.search("nada", [1.0, 0.0], 5) == []
    assert store.list("nada") == []
