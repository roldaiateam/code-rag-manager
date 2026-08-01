from pathlib import Path

from coderagmanager.adapters.mcp.client_configs.claude_md import (
    BEGIN_MARKER,
    END_MARKER,
    upsert_claude_md_block,
)


def test_creates_file_when_missing(tmp_path):
    upsert_claude_md_block(str(tmp_path), "backend")
    content = (tmp_path / "CLAUDE.md").read_text()
    assert BEGIN_MARKER in content and END_MARKER in content
    assert "mcp__crm-backend__" in content
    assert "search_code" in content


def test_appends_without_touching_existing_content(tmp_path):
    existing = "# Mi proyecto\n\nConvenciones importantes del equipo.\n"
    (tmp_path / "CLAUDE.md").write_text(existing)
    upsert_claude_md_block(str(tmp_path), "backend")
    content = (tmp_path / "CLAUDE.md").read_text()
    assert content.startswith(existing.rstrip("\n"))
    assert "Convenciones importantes" in content
    assert BEGIN_MARKER in content


def test_upsert_is_idempotent(tmp_path):
    upsert_claude_md_block(str(tmp_path), "backend")
    first = (tmp_path / "CLAUDE.md").read_text()
    upsert_claude_md_block(str(tmp_path), "backend")
    second = (tmp_path / "CLAUDE.md").read_text()
    assert first == second
    assert second.count(BEGIN_MARKER) == 1


def test_replaces_old_block_preserving_surroundings(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(
        f"# Cabecera\n\n{BEGIN_MARKER}\ncontenido viejo\n{END_MARKER}\n\n## Pie\n"
    )
    upsert_claude_md_block(str(tmp_path), "nuevo-id")
    content = (tmp_path / "CLAUDE.md").read_text()
    assert "contenido viejo" not in content
    assert "mcp__crm-nuevo-id__" in content
    assert content.startswith("# Cabecera")
    assert "## Pie" in content
    assert content.count(BEGIN_MARKER) == 1
