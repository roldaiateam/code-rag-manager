from pathlib import Path

from coderagmanager.adapters.parsers.tree_sitter_java import TreeSitterJavaParser

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_repo" / "src"


def parse():
    parser = TreeSitterJavaParser()
    source = (FIXTURE / "SpringExamples.java").read_text()
    return parser.parse("demo", "src/SpringExamples.java", source)


def test_class_annotations_are_extracted():
    chunks, _ = parse()
    by_symbol = {c.symbol: c for c in chunks}
    assert by_symbol["ProductsController"].metadata["annotations"] == [
        "RestController",
        "RequiredArgsConstructor",
    ]
    assert by_symbol["ProductsUseCaseImpl"].metadata["annotations"] == ["Service"]
    assert by_symbol["ProductDb"].metadata["annotations"] == ["Entity"]
    assert by_symbol["GlobalExceptionHandler"].metadata["annotations"] == [
        "RestControllerAdvice"
    ]


def test_interface_annotations_are_extracted():
    chunks, _ = parse()
    by_symbol = {c.symbol: c for c in chunks}
    assert by_symbol["ProductsMapper"].metadata["annotations"] == ["Mapper"]


def test_class_without_annotations_gets_empty_list():
    chunks, _ = parse()
    by_symbol = {c.symbol: c for c in chunks}
    assert by_symbol["PlainClass"].metadata["annotations"] == []
    assert by_symbol["PlainClass"].metadata["supertypes"] == []


def test_supertypes_are_extracted_without_generic_type_arguments():
    chunks, _ = parse()
    by_symbol = {c.symbol: c for c in chunks}
    assert by_symbol["ProductsRepository"].metadata["supertypes"] == [
        "JpaRepository",
        "JpaSpecificationExecutor",
    ]


def test_method_chunks_keep_empty_metadata():
    chunks, _ = parse()
    by_symbol = {c.symbol: c for c in chunks}
    assert by_symbol["listar"].kind == "method"
    assert by_symbol["listar"].metadata == {}
