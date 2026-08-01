from coderagmanager.adapters.formatting import format_chunks

from tests.domain.test_models import make_chunk


def test_format_chunks_caps_rows_with_notice():
    chunks = [make_chunk(id=str(i), symbol=f"sym{i}") for i in range(250)]
    result = format_chunks(chunks, max_rows=200)
    lines = result.splitlines()
    assert len(lines) == 201  # 200 filas + aviso
    assert "mostrando 200 de 250" in lines[-1]


def test_format_chunks_no_notice_under_cap():
    chunks = [make_chunk(id=str(i)) for i in range(5)]
    result = format_chunks(chunks)
    assert "mostrando" not in result
