import subprocess

import pytest

from coderagmanager.application.file_discovery import discover_files


@pytest.fixture
def git_repo(tmp_path):
    """Repo git real con target/ gitignorado y código generado dentro."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("target/\nbuild/\ndocs-privadas/\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("def f():\n    return 1\n")

    generated = tmp_path / "modulo" / "target" / "generated-sources" / "openapi"
    generated.mkdir(parents=True)
    (generated / "Dto.java").write_text(
        "class Dto {\n    void get() {}\n}\n"
    )
    # el resto de target/ (compilados) no debe entrar
    classes = tmp_path / "modulo" / "target" / "classes"
    classes.mkdir(parents=True)
    (classes / "Dto.txt").write_text("compilado")

    private_docs = tmp_path / "docs-privadas"
    private_docs.mkdir()
    (private_docs / "notas.md").write_text("# notas gitignoradas\n")
    return tmp_path


def paths(results):
    return {rel_path for rel_path, _, _ in results}


def origins(results):
    return {rel_path: origin for rel_path, _, origin in results}


def test_auto_include_finds_generated_sources_by_default(git_repo):
    results = list(discover_files(str(git_repo)))
    assert "modulo/target/generated-sources/openapi/Dto.java" in paths(results)
    assert origins(results)["modulo/target/generated-sources/openapi/Dto.java"] == "auto"
    # el resto de target/ sigue fuera
    assert "modulo/target/classes/Dto.txt" not in paths(results)


def test_auto_include_can_be_disabled(git_repo):
    results = list(discover_files(str(git_repo), auto_include=False))
    assert not any("generated-sources" in p for p in paths(results))


def test_git_files_keep_git_origin(git_repo):
    results = list(discover_files(str(git_repo)))
    assert origins(results)["src/a.py"] == "git"


def test_extra_pattern_includes_gitignored_dir(git_repo):
    results = list(discover_files(str(git_repo), extra_index_paths=["docs-privadas"]))
    assert origins(results)["docs-privadas/notas.md"] == "extra"


def test_no_duplicates_when_pattern_overlaps_git(git_repo):
    results = list(discover_files(str(git_repo), extra_index_paths=["src/**/*.py"]))
    listed = [p for p, _, _ in results if p == "src/a.py"]
    assert listed == ["src/a.py"]  # una sola vez, con prioridad del origen git


def test_gradle_convention_detected(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("build/\n")
    generated = tmp_path / "build" / "generated" / "sources"
    generated.mkdir(parents=True)
    (generated / "Gen.java").write_text("class Gen {}\n")

    results = list(discover_files(str(tmp_path)))
    assert "build/generated/sources/Gen.java" in paths(results)
