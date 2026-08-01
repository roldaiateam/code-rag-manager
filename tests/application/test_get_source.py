import pytest

from coderagmanager.application.get_source import (
    MAX_EXPLICIT_LINES,
    MAX_SOURCE_LINES,
    GetSource,
)
from coderagmanager.domain.errors import ChunkNotFoundError

from tests.application.fakes import FakeVectorStore
from tests.domain.test_models import make_chunk


def long_chunk(n_lines=400, kind="function", start_line=50, **overrides):
    source = "\n".join(f"linea {i}" for i in range(1, n_lines + 1))
    return make_chunk(
        kind=kind,
        start_line=start_line,
        end_line=start_line + n_lines - 1,
        source_text=source,
        **overrides,
    )


def build(chunks, skeletonizer=None):
    store = FakeVectorStore()
    store.upsert("p1", chunks)
    return GetSource("p1", store, skeletonizer=skeletonizer)


def test_short_chunk_returned_whole_without_notices():
    result = build([make_chunk()]).execute(symbol="calcular_total")
    assert "TRUNCADO" not in result and "ESQUELETO" not in result
    assert "def calcular_total" in result


def test_long_chunk_truncated_with_actionable_notice():
    chunk = long_chunk(n_lines=400, start_line=50)
    result = build([chunk]).execute(symbol=chunk.symbol)

    assert f"linea {MAX_SOURCE_LINES}" in result
    assert f"linea {MAX_SOURCE_LINES + 1}" not in result
    # el aviso usa líneas ABSOLUTAS del fichero (chunk empieza en la 50)
    shown_to = 50 + MAX_SOURCE_LINES - 1          # 169
    assert f"mostradas líneas 50-{shown_to}" in result
    assert (
        f'get_source(file_path="{chunk.file_path}", '
        f"start_line={shown_to + 1}, end_line={shown_to + MAX_SOURCE_LINES})"
    ) in result


def test_explicit_range_returns_only_that_slice():
    chunk = long_chunk(n_lines=400, start_line=50)
    result = build([chunk]).execute(
        file_path=chunk.file_path, start_line=170, end_line=180
    )
    # línea absoluta 170 = línea relativa 121 del chunk
    assert "linea 121" in result and "linea 131" in result
    assert "linea 120" not in result and "linea 132" not in result
    assert "TRUNCADO" not in result


def test_explicit_range_above_cap_paginates():
    chunk = long_chunk(n_lines=800, start_line=1)
    result = build([chunk]).execute(
        file_path=chunk.file_path, start_line=1, end_line=700
    )
    assert f"linea {MAX_EXPLICIT_LINES}" in result
    assert f"linea {MAX_EXPLICIT_LINES + 1}" not in result
    assert f"start_line={MAX_EXPLICIT_LINES + 1}" in result


def test_long_class_uses_skeleton_when_available():
    chunk = long_chunk(n_lines=400, kind="class", symbol="Grande")
    fake_skeleton = "class Grande {\n  metodo() { ... }\n}"
    result = build([chunk], skeletonizer=lambda lang, src: fake_skeleton).execute(
        symbol="Grande"
    )
    assert "metodo() { ... }" in result
    assert "ESQUELETO" in result
    assert 'get_source(file_path="' in result  # afordancia de continuación


def test_long_function_never_skeletonized():
    chunk = long_chunk(n_lines=400, kind="function")
    result = build([chunk], skeletonizer=lambda lang, src: "NO DEBERÍA USARSE").execute(
        symbol=chunk.symbol
    )
    assert "NO DEBERÍA USARSE" not in result
    assert "TRUNCADO" in result


def test_skeleton_failure_falls_back_to_truncation():
    chunk = long_chunk(n_lines=400, kind="class")
    result = build([chunk], skeletonizer=lambda lang, src: None).execute(
        symbol=chunk.symbol
    )
    assert "TRUNCADO" in result


def test_missing_chunk_raises():
    with pytest.raises(ChunkNotFoundError):
        build([make_chunk()]).execute(symbol="inexistente")
