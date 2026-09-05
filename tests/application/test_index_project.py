import json
from pathlib import Path

from coderagmanager.adapters.parsers.tree_sitter_python import TreeSitterPythonParser
from coderagmanager.application.index_project import IndexProject
from coderagmanager.domain.models import EdgeType

from tests.application.fakes import (
    FakeEmbedder,
    FakeGit,
    FakeGraphStore,
    FakeLexicalIndex,
    FakeVectorStore,
)

FIXTURE_REPO = Path(__file__).parent.parent / "fixtures" / "sample_repo"


def build(root: str, vector_store=None, graph_store=None):
    return IndexProject(
        project_id="demo",
        root_path=root,
        parser=TreeSitterPythonParser(),
        embedder=FakeEmbedder(),
        vector_store=vector_store or FakeVectorStore(),
        graph_store=graph_store or FakeGraphStore(),
        lexical_index=FakeLexicalIndex(),
        git=FakeGit(),
    )


def test_index_is_drop_and_rebuild(tmp_path):
    (tmp_path / "a.py").write_text("def f():\n    return 1\n")
    vector_store, graph_store = FakeVectorStore(), FakeGraphStore()
    use_case = build(str(tmp_path), vector_store, graph_store)

    use_case.execute()
    use_case.execute()  # reindexar no debe duplicar: drop antes de rebuild

    assert vector_store.drops == ["demo", "demo"]
    assert graph_store.drops == ["demo", "demo"]
    assert len(vector_store.data["demo"]) == 1


def test_index_fixture_produces_chunks_edges_and_manifest(tmp_path):
    import shutil

    root = tmp_path / "repo"
    shutil.copytree(FIXTURE_REPO, root)
    vector_store, graph_store = FakeVectorStore(), FakeGraphStore()
    stats = build(str(root), vector_store, graph_store).execute()

    symbols = {c.symbol for c in vector_store.data["demo"]}
    assert {"calcular_total", "aplicar_descuento", "Pedido", "PedidoUrgente"} <= symbols
    assert stats.total_chunks == len(vector_store.data["demo"])

    edge_types = {e.edge_type for e in graph_store.edges_by_project["demo"]}
    assert EdgeType.CALLS in edge_types
    assert EdgeType.EXTENDS in edge_types

    manifest = json.loads((root / ".crm" / "manifest.json").read_text())
    assert manifest["project_id"] == "demo"
    assert manifest["total_chunks"] == stats.total_chunks
    assert manifest["last_indexed_commit"] == "abc1234"


def test_chunks_receive_embeddings(tmp_path):
    (tmp_path / "a.py").write_text("def f():\n    return 1\n")
    vector_store = FakeVectorStore()
    build(str(tmp_path), vector_store).execute()
    assert all(c.embedding is not None for c in vector_store.data["demo"])


def test_chunks_are_classified_by_path_convention(tmp_path):
    (tmp_path / "domain").mkdir()
    (tmp_path / "domain" / "entity.py").write_text("def f():\n    return 1\n")
    (tmp_path / "infrastructure").mkdir()
    (tmp_path / "infrastructure" / "adapter.py").write_text("def g():\n    return 2\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_entity.py").write_text("def test_f():\n    return 3\n")
    (tmp_path / "loose.py").write_text("def h():\n    return 4\n")

    vector_store = FakeVectorStore()
    build(str(tmp_path), vector_store).execute()

    by_symbol = {c.symbol: c for c in vector_store.data["demo"]}
    assert by_symbol["f"].layer == "domain"
    assert by_symbol["g"].layer == "infrastructure"
    assert by_symbol["test_f"].layer is None
    assert by_symbol["test_f"].kind == "test"
    assert by_symbol["h"].layer is None
    assert by_symbol["h"].kind != "test"


def test_auto_included_generated_code_is_indexed_and_reported(tmp_path):
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("target/\n")
    (tmp_path / "a.py").write_text("def visible():\n    return 1\n")
    generated = tmp_path / "target" / "generated-sources" / "openapi"
    generated.mkdir(parents=True)
    (generated / "gen.py").write_text("def generado():\n    return 2\n")

    vector_store = FakeVectorStore()
    stats = build(str(tmp_path), vector_store).execute()

    symbols = {c.symbol for c in vector_store.data["demo"]}
    assert {"visible", "generado"} <= symbols
    assert stats.included == {"auto": 1}
