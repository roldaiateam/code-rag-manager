from coderagmanager.adapters.parsers.skeleton import skeletonize

GENERATED_JAVA = """public class CreateSupplierRequest {

  private String email;
  private String taxId;

  @jakarta.validation.constraints.Email
  public String getEmail() {
    return email;
  }

  @jakarta.validation.constraints.NotNull
  public String getTaxId() {
    if (taxId == null) {
      throw new IllegalStateException("sin taxId");
    }
    return taxId;
  }

  public CreateSupplierRequest(String email) {
    this.email = email;
  }
}
"""


def test_java_skeleton_keeps_annotations_and_signatures_drops_bodies():
    skeleton = skeletonize("java", GENERATED_JAVA)
    assert skeleton is not None
    assert "@jakarta.validation.constraints.Email" in skeleton
    assert "public String getEmail() { ... }" in skeleton
    assert "private String email;" in skeleton
    assert "public CreateSupplierRequest(String email) { ... }" in skeleton
    assert "return email;" not in skeleton
    assert "IllegalStateException" not in skeleton
    assert len(skeleton.splitlines()) < len(GENERATED_JAVA.splitlines())


def test_java_interface_without_bodies_returns_none():
    source = "interface Repositorio {\n    void guardar(String clave);\n}\n"
    assert skeletonize("java", source) is None  # nada que elidir


def test_python_skeleton_keeps_docstring_and_signature():
    source = (
        "class Pedido:\n"
        '    def total(self, items):\n'
        '        """Suma los precios."""\n'
        "        total = 0\n"
        "        return total\n"
        "\n"
        "    def vaciar(self):\n"
        "        self.items = []\n"
    )
    skeleton = skeletonize("python", source)
    assert skeleton is not None
    assert "def total(self, items):" in skeleton
    assert '"""Suma los precios."""' in skeleton
    assert "total = 0" not in skeleton
    assert "self.items = []" not in skeleton
    assert "..." in skeleton


def test_javascript_skeleton_drops_method_bodies():
    source = (
        "class Cesta {\n"
        "  constructor(items) {\n"
        "    this.items = items;\n"
        "  }\n"
        "  total() {\n"
        "    return this.items.length;\n"
        "  }\n"
        "}\n"
    )
    skeleton = skeletonize("javascript", source)
    assert skeleton is not None
    assert "total() { ... }" in skeleton
    assert "return this.items.length;" not in skeleton


def test_unsupported_language_returns_none():
    assert skeletonize("text", "cualquier cosa") is None


def test_unparseable_source_returns_none():
    assert skeletonize("java", "class {{{ esto no es java ]]") is None
