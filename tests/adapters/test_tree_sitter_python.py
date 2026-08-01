from pathlib import Path

from coderagmanager.adapters.parsers.tree_sitter_python import TreeSitterPythonParser
from coderagmanager.domain.models import EdgeType
from coderagmanager.domain.resolution import resolve_edges

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_repo" / "src"


def parse(filename: str):
    parser = TreeSitterPythonParser()
    source = (FIXTURE / filename).read_text()
    return parser.parse("demo", f"src/{filename}", source)


def test_supports_only_python():
    parser = TreeSitterPythonParser()
    assert parser.supports("a/b.py")
    assert not parser.supports("a/b.js")


def test_extracts_function_chunks_with_lines_and_source():
    chunks, _ = parse("carrito.py")
    symbols = {c.symbol: c for c in chunks}
    assert set(symbols) == {"calcular_total", "aplicar_descuento"}
    total = symbols["calcular_total"]
    assert total.kind == "function"
    assert total.start_line == 1
    assert total.source_text.startswith("def calcular_total(items):")


def test_extracts_classes_and_methods():
    chunks, _ = parse("pedidos.py")
    kinds = {c.symbol: c.kind for c in chunks}
    assert kinds["Pedido"] == "class"
    assert kinds["PedidoUrgente"] == "class"
    assert kinds["total_con_descuento"] == "method"
    assert kinds["__init__"] == "method"


def test_call_edge_resolved_within_file():
    chunks, edges = parse("carrito.py")
    resolved = resolve_edges(chunks, edges)
    by_symbol = {c.symbol: c.id for c in chunks}
    assert any(
        e.edge_type == EdgeType.CALLS
        and e.source_chunk_id == by_symbol["aplicar_descuento"]
        and e.target_chunk_id == by_symbol["calcular_total"]
        for e in resolved
    )


def test_extends_edge_resolved():
    chunks, edges = parse("pedidos.py")
    resolved = resolve_edges(chunks, edges)
    by_symbol = {c.symbol: c.id for c in chunks}
    assert any(
        e.edge_type == EdgeType.EXTENDS
        and e.source_chunk_id == by_symbol["PedidoUrgente"]
        and e.target_chunk_id == by_symbol["Pedido"]
        for e in resolved
    )


def test_import_edge_resolves_across_files():
    parser = TreeSitterPythonParser()
    all_chunks, all_edges = [], []
    for name in ("carrito.py", "pedidos.py"):
        chunks, edges = parser.parse(
            "demo", f"src/{name}", (FIXTURE / name).read_text()
        )
        all_chunks.extend(chunks)
        all_edges.extend(edges)
    resolved = resolve_edges(all_chunks, all_edges)
    by_symbol = {c.symbol: c.id for c in all_chunks}
    assert any(
        e.edge_type == EdgeType.IMPORTS
        and e.target_chunk_id == by_symbol["aplicar_descuento"]
        for e in resolved
    )
