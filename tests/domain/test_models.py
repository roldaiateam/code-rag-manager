from coderagmanager.domain.models import CodeChunk, EdgeType, DependencyEdge, stable_id


def make_chunk(**overrides) -> CodeChunk:
    defaults = dict(
        id=stable_id("carrito.py", "calcular_total", 1),
        project_id="demo",
        language="python",
        symbol="calcular_total",
        kind="function",
        file_path="carrito.py",
        start_line=1,
        end_line=5,
        source_text="def calcular_total(items):\n    return sum(items)",
    )
    defaults.update(overrides)
    return CodeChunk(**defaults)


def test_code_chunk_fields():
    chunk = make_chunk()
    assert chunk.symbol == "calcular_total"
    assert chunk.language == "python"
    assert chunk.embedding is None
    assert chunk.start_line == 1 and chunk.end_line == 5


def test_stable_id_is_deterministic():
    assert stable_id("a.py", "f", 3) == stable_id("a.py", "f", 3)
    assert stable_id("a.py", "f", 3) != stable_id("a.py", "f", 4)


def test_dependency_edge():
    edge = DependencyEdge("abc", "def", EdgeType.CALLS)
    assert edge.edge_type == EdgeType.CALLS
    assert edge.edge_type.value == "calls"
