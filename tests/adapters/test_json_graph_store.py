from coderagmanager.adapters.storage.json_graph_store import JsonGraphStore
from coderagmanager.domain.models import DependencyEdge, EdgeType

from tests.domain.test_models import make_chunk


def build_store(tmp_path):
    store = JsonGraphStore(str(tmp_path / ".crm"))
    chunks = [
        make_chunk(id="a", symbol="aplicar_descuento"),
        make_chunk(id="b", symbol="calcular_total"),
        make_chunk(id="c", symbol="notificar"),
    ]
    store.upsert_nodes("p1", chunks)
    store.upsert_edges("p1", [
        DependencyEdge("a", "b", EdgeType.CALLS),
        DependencyEdge("b", "c", EdgeType.CALLS),
    ])
    return store


def test_bfs_outgoing_respects_max_depth(tmp_path):
    store = build_store(tmp_path)
    depth1 = store.dependency_chain("p1", "aplicar_descuento", max_depth=1, direction="out")
    assert [(e.source_chunk_id, e.target_chunk_id) for e in depth1] == [("a", "b")]

    depth2 = store.dependency_chain("p1", "aplicar_descuento", max_depth=2, direction="out")
    assert len(depth2) == 2


def test_bfs_incoming(tmp_path):
    store = build_store(tmp_path)
    incoming = store.dependency_chain("p1", "calcular_total", max_depth=1, direction="in")
    assert [(e.source_chunk_id, e.target_chunk_id) for e in incoming] == [("a", "b")]


def test_drop_empties_graph(tmp_path):
    store = build_store(tmp_path)
    store.drop("p1")
    assert store.nodes("p1") == {}
    assert store.dependency_chain("p1", "aplicar_descuento", 3, "both") == []


def test_persists_across_instances(tmp_path):
    build_store(tmp_path)
    reopened = JsonGraphStore(str(tmp_path / ".crm"))
    assert len(reopened.nodes("p1")) == 3
