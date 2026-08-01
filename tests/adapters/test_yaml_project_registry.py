import pytest

from coderagmanager.adapters.registry.yaml_project_registry import YamlProjectRegistry
from coderagmanager.domain.errors import ProjectNotFoundError


def make_registry(tmp_path):
    return YamlProjectRegistry(str(tmp_path / "projects.yaml"))


def test_register_get_list_remove(tmp_path):
    registry = make_registry(tmp_path)
    project = registry.register("Mi Backend", str(tmp_path), ["python"])

    assert project.id == "mi-backend"
    assert registry.get("mi-backend").root_path == str(tmp_path)
    assert [p.id for p in registry.list()] == ["mi-backend"]

    registry.remove("mi-backend")
    assert registry.list() == []


def test_get_unknown_raises(tmp_path):
    with pytest.raises(ProjectNotFoundError):
        make_registry(tmp_path).get("nope")


def test_register_invalid_path_raises(tmp_path):
    with pytest.raises(ValueError):
        make_registry(tmp_path).register("x", str(tmp_path / "no-existe"), [])


def test_mark_indexed_updates_fields(tmp_path):
    registry = make_registry(tmp_path)
    registry.register("demo", str(tmp_path), [])
    registry.mark_indexed("demo", "abc1234")

    project = registry.get("demo")
    assert project.last_indexed_commit == "abc1234"
    assert project.last_indexed_at is not None


def test_defaults_roundtrip(tmp_path):
    registry = make_registry(tmp_path)
    assert registry.defaults()["embedding_provider"] == "local"
    registry.set_default("top_k", "10")
    assert registry.defaults()["top_k"] == "10"
