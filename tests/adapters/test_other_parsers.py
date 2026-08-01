from pathlib import Path

from coderagmanager.adapters.parsers.composite import CompositeLanguageParser
from coderagmanager.adapters.parsers.generic_text import GenericTextParser
from coderagmanager.adapters.parsers.tree_sitter_java import TreeSitterJavaParser
from coderagmanager.adapters.parsers.tree_sitter_javascript import (
    TreeSitterJavaScriptParser,
)
from coderagmanager.adapters.parsers.tree_sitter_python import TreeSitterPythonParser
from coderagmanager.domain.models import EdgeType
from coderagmanager.domain.resolution import resolve_edges

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_repo"


def test_javascript_chunks_and_edges():
    parser = TreeSitterJavaScriptParser()
    source = (FIXTURE / "src" / "checkout.js").read_text()
    chunks, edges = parser.parse("demo", "src/checkout.js", source)

    by_symbol = {c.symbol: c for c in chunks}
    assert by_symbol["calcularEnvio"].kind == "function"
    assert by_symbol["resumenPedido"].kind == "function"  # arrow asignada a const
    assert by_symbol["Cesta"].kind == "class"
    assert by_symbol["CestaRegalo"].kind == "class"

    resolved = resolve_edges(chunks, edges)
    assert any(
        e.edge_type == EdgeType.EXTENDS
        and e.source_chunk_id == by_symbol["CestaRegalo"].id
        and e.target_chunk_id == by_symbol["Cesta"].id
        for e in resolved
    )
    assert any(
        e.edge_type == EdgeType.CALLS
        and e.target_chunk_id == by_symbol["calcularEnvio"].id
        for e in resolved
    )


def test_java_chunks_and_implements_edge():
    parser = TreeSitterJavaParser()
    source = (FIXTURE / "src" / "Almacen.java").read_text()
    chunks, edges = parser.parse("demo", "src/Almacen.java", source)

    by_symbol = {c.symbol: c for c in chunks}
    assert by_symbol["Repositorio"].kind == "interface"
    assert by_symbol["AlmacenMemoria"].kind == "class"
    assert by_symbol["guardar"].kind == "method"

    resolved = resolve_edges(chunks, edges)
    assert any(
        e.edge_type == EdgeType.IMPLEMENTS
        and e.source_chunk_id == by_symbol["AlmacenMemoria"].id
        and e.target_chunk_id == by_symbol["Repositorio"].id
        for e in resolved
    )


def test_generic_text_windows_with_overlap():
    parser = GenericTextParser(window_lines=10, overlap_lines=2)
    source = "\n".join(f"linea {i}" for i in range(1, 26))
    chunks, edges = parser.parse("demo", "docs/notas.md", source)

    assert edges == []
    assert chunks[0].start_line == 1 and chunks[0].end_line == 10
    assert chunks[1].start_line == 9  # solapamiento de 2 líneas
    assert all(c.kind == "block" and c.language == "text" for c in chunks)
    assert chunks[-1].end_line == 25


def test_composite_prefers_dedicated_parser_and_falls_back():
    composite = CompositeLanguageParser([
        TreeSitterPythonParser(),
        TreeSitterJavaScriptParser(),
        TreeSitterJavaParser(),
        GenericTextParser(),
    ])
    py_chunks, _ = composite.parse("demo", "a.py", "def f():\n    return 1\n")
    assert py_chunks[0].language == "python"

    md_chunks, _ = composite.parse("demo", "notas.md", "# titulo\ntexto\n")
    assert md_chunks[0].language == "text"

    assert composite.supports("cualquier.cosa")
