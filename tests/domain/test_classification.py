import pytest

from coderagmanager.domain.classification import (
    classify_kind_by_path,
    classify_layer_by_path,
)


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
