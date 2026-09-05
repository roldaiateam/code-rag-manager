import pytest

from coderagmanager.domain.classification import (
    SEMANTIC_ROLE_PROTOTYPES,
    classify_kind_by_path,
    classify_layer_by_path,
    classify_role_spring_java,
    nearest_role_prototype,
    spring_java_pack_applies,
)
from coderagmanager.domain.models import CodeChunk


@pytest.mark.parametrize(
    "segment,expected_layer",
    [
        ("domain", "domain"),
        ("application", "application"),
        ("services", "application"),
        ("ports", "ports"),
        ("infrastructure", "infrastructure"),
        ("adapters", "infrastructure"),
        ("controllers", "infrastructure"),
        ("repositories", "infrastructure"),
    ],
)
def test_recognized_segment_maps_to_expected_layer(segment, expected_layer):
    assert classify_layer_by_path(f"src/{segment}/Foo.py") == expected_layer


def test_matching_is_case_insensitive():
    assert classify_layer_by_path("Domain/Foo.py") == "domain"


def test_outermost_recognized_segment_wins_when_several_match():
    assert classify_layer_by_path("domain/services/CustomerService.java") == "domain"


def test_flat_path_without_convention_returns_none():
    assert classify_layer_by_path("tests/fixtures/sample_repo/src/pedidos.py") is None


def test_partial_segment_match_is_not_a_false_positive():
    assert classify_layer_by_path("subdomain_utils/foo.py") is None


@pytest.mark.parametrize(
    "file_path,expected_kind",
    [
        ("tests/test_foo.py", "test"),
        ("test/foo.py", "test"),
        ("src/foo_test.py", "test"),
        ("src/foo_spec.js", "test"),
        ("src/foo.py", None),
    ],
)
def test_kind_by_path_follows_test_convention(file_path, expected_kind):
    assert classify_kind_by_path(file_path) == expected_kind


def _java_chunk(
    symbol,
    kind,
    file_path="src/Foo.java",
    annotations=(),
    supertypes=(),
    layer=None,
):
    return CodeChunk(
        id="x",
        project_id="demo",
        language="java",
        symbol=symbol,
        kind=kind,
        file_path=file_path,
        start_line=1,
        end_line=1,
        source_text="",
        metadata={"annotations": list(annotations), "supertypes": list(supertypes)},
        layer=layer,
    )


@pytest.mark.parametrize(
    "annotations,expected_role",
    [
        (["RestController"], "controller"),
        (["Controller"], "controller"),
        (["Entity"], "jpa-entity"),
        (["ControllerAdvice"], "exception-handler"),
        (["RestControllerAdvice"], "exception-handler"),
        (["Mapper"], "mapper"),
    ],
)
def test_class_role_by_annotation(annotations, expected_role):
    chunk = _java_chunk("Foo", "class", annotations=annotations)
    assert classify_role_spring_java(chunk) == expected_role


def test_service_in_application_layer_is_use_case():
    chunk = _java_chunk("Foo", "class", annotations=["Service"], layer="application")
    assert classify_role_spring_java(chunk) == "use-case"


def test_service_outside_application_layer_is_service():
    chunk = _java_chunk("Foo", "class", annotations=["Service"], layer="infrastructure")
    assert classify_role_spring_java(chunk) == "service"


def test_service_without_layer_is_service():
    chunk = _java_chunk("Foo", "class", annotations=["Service"])
    assert classify_role_spring_java(chunk) == "service"


def test_controller_wins_over_service_when_both_present():
    chunk = _java_chunk(
        "Foo", "class", annotations=["RestController", "Service"], layer="application"
    )
    assert classify_role_spring_java(chunk) == "controller"


def test_repository_annotation_alone_has_no_rule():
    chunk = _java_chunk("Foo", "class", annotations=["Repository"])
    assert classify_role_spring_java(chunk) is None


def test_configuration_annotation_alone_has_no_rule():
    chunk = _java_chunk("Foo", "class", annotations=["Configuration"])
    assert classify_role_spring_java(chunk) is None


def test_class_without_recognized_annotation_returns_none():
    chunk = _java_chunk("Foo", "class")
    assert classify_role_spring_java(chunk) is None


@pytest.mark.parametrize(
    "supertype",
    ["JpaRepository", "CrudRepository", "FooRepository"],
)
def test_interface_extending_repository_type_is_repository(supertype):
    chunk = _java_chunk("FooRepository", "interface", supertypes=[supertype])
    assert classify_role_spring_java(chunk) == "repository"


def test_mapper_annotation_wins_over_repository_supertype_on_interface():
    chunk = _java_chunk(
        "FooRepository",
        "interface",
        annotations=["Mapper"],
        supertypes=["JpaRepository"],
    )
    assert classify_role_spring_java(chunk) == "mapper"


def test_interface_ports_in_path_is_port_in():
    chunk = _java_chunk(
        "Foo", "interface", file_path="src/domain/ports/in/Foo.java", layer="domain"
    )
    assert classify_role_spring_java(chunk) == "port-in"


def test_interface_ports_out_path_is_port_out():
    chunk = _java_chunk(
        "Foo", "interface", file_path="src/domain/ports/out/Foo.java", layer="domain"
    )
    assert classify_role_spring_java(chunk) == "port-out"


def test_interface_use_case_suffix_is_port_in():
    chunk = _java_chunk("FooUseCase", "interface", layer="domain")
    assert classify_role_spring_java(chunk) == "port-in"


def test_interface_port_suffix_is_port_out():
    chunk = _java_chunk("FooPort", "interface", layer="domain")
    assert classify_role_spring_java(chunk) == "port-out"


def test_port_rules_require_domain_layer():
    chunk = _java_chunk(
        "Foo", "interface", file_path="src/domain/ports/in/Foo.java", layer=None
    )
    assert classify_role_spring_java(chunk) is None

    chunk = _java_chunk("FooUseCase", "interface", layer="infrastructure")
    assert classify_role_spring_java(chunk) is None


def test_interface_without_recognized_signal_returns_none():
    chunk = _java_chunk("Foo", "interface", layer="domain")
    assert classify_role_spring_java(chunk) is None


def test_record_kind_is_out_of_scope():
    chunk = _java_chunk("Foo", "record", annotations=["Entity"], layer="domain")
    assert classify_role_spring_java(chunk) is None


def test_pack_applies_when_a_java_chunk_has_a_recognized_annotation():
    chunks = [
        _java_chunk("Foo", "class"),
        _java_chunk("Bar", "class", annotations=["RestController"]),
    ]
    assert spring_java_pack_applies(chunks) is True


def test_pack_does_not_apply_without_recognized_annotations():
    chunks = [_java_chunk("Foo", "class"), _java_chunk("Bar", "interface")]
    assert spring_java_pack_applies(chunks) is False


def test_semantic_role_prototypes_has_the_seven_expected_categories():
    assert set(SEMANTIC_ROLE_PROTOTYPES) == {
        "entity",
        "controller",
        "adapter",
        "use_case",
        "mapper",
        "config",
        "utility",
    }


def test_nearest_role_prototype_picks_the_closest_prototype_by_cosine():
    prototypes = {"a": [1.0, 0.0], "b": [0.0, 1.0], "c": [-1.0, 0.0]}
    role, margin = nearest_role_prototype([0.9, 0.1], prototypes)
    assert role == "a"
    assert margin > 0.5


def test_nearest_role_prototype_margin_is_top1_minus_top2_similarity():
    prototypes = {"p1": [1.0, 0.0], "p2": [0.0, 1.0]}
    role, margin = nearest_role_prototype([3.0, 4.0], prototypes)
    assert role == "p2"
    assert margin == pytest.approx(0.2)


def test_nearest_role_prototype_always_assigns_from_the_closed_set():
    prototypes = {"a": [1.0, 0.0, 0.0], "b": [0.0, 1.0, 0.0], "c": [0.0, 0.0, -1.0]}
    role, _ = nearest_role_prototype([0.0, 0.0, 1.0], prototypes)
    assert role in prototypes


def test_nearest_role_prototype_handles_zero_vector_without_crashing():
    prototypes = {"a": [1.0, 0.0], "b": [0.0, 1.0]}
    role, margin = nearest_role_prototype([0.0, 0.0], prototypes)
    assert role == "a"
    assert margin == 0.0


def test_nearest_role_prototype_breaks_ties_deterministically():
    prototypes = {"first": [1.0, 0.0], "second": [2.0, 0.0]}
    role, margin = nearest_role_prototype([1.0, 0.0], prototypes)
    assert role == "first"
    assert margin == 0.0
