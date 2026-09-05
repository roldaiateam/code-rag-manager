from coderagmanager.domain.tokenizer import expand_query, stem, tokenize


def test_tokenize_splits_camel_case():
    # Comparado vía stem() (no hardcodeando "barcode") porque tokenize()
    # aplica stem() a cada pieza: lo que se comprueba aquí es el split
    # camelCase en sí, no la forma exacta que produce el stemmer.
    assert tokenize("ProductBarcodeType") == {stem("product"), stem("barcode"), stem("type")}


def test_tokenize_splits_acronym_boundary():
    tokens = tokenize("HTTPServerConfig")
    assert {"http", "server", "config"} <= tokens


def test_tokenize_splits_snake_and_kebab_case():
    assert tokenize("user_id-value") == {stem("user"), stem("id"), stem("value")}


def test_tokenize_drops_stopwords_and_short_tokens():
    tokens = tokenize("a of the id")
    assert "a" not in tokens
    assert "of" not in tokens
    assert "the" not in tokens
    assert "id" in tokens


def test_tokenize_empty_text():
    assert tokenize("") == set()
    assert tokenize(None) == set()


def test_tokenize_preserves_spanish_accented_words():
    assert tokenize("código") == {stem("código")}
    assert tokenize("año") == {stem("año")}
    assert tokenize("validación") == {stem("validación")}
    assert tokenize("dónde") == {stem("dónde")}
    # Y explícitamente: ya no queda ningún fragmento roto tipo "digo"/"nde".
    assert "digo" not in tokenize("código")
    assert "nde" not in tokenize("dónde")


def test_stem_ies_rule():
    # snowballstemmer (inglés) trunca a "categori" en vez de "category" —
    # no es un diccionario, es un algoritmo de sufijos; lo que importa es
    # que sigue siendo un token consistente y comparable en ambos lados.
    assert stem("categories") == "categori"


def test_stem_ing_rule():
    # Mejora real frente al stemmer casero anterior: "mapp" (tosco) -> "map"
    # (real), verificado con snowballstemmer==3.1.1 antes de adoptarlo.
    assert stem("mapping") == "map"


def test_stem_plain_s_rule():
    assert stem("endpoints") == stem("endpoint") == "endpoint"


def test_stem_excludes_ss_us_is_endings():
    assert stem("class") == "class"
    assert stem("bonus") == "bonus"
    # A diferencia de nuestra regla casera (que protegía "-is" sin tocarlo),
    # el algoritmo Snowball sí trunca "basis" -> "basi". Sigue siendo
    # consistente consigo mismo; se documenta el valor real, no se asume.
    assert stem("basis") == "basi"


def test_stem_leaves_short_tokens_untouched():
    assert stem("is") == "is"


def test_stem_protects_common_english_words_ending_in_es():
    # El caso que de verdad importa para este corpus (código, mayoritariamente
    # en inglés): singular y plural deben compartir raíz. Se mantiene con
    # snowballstemmer exactamente igual que con el stemmer casero anterior
    # — es el gate de aceptación de todo el cambio de librería (ver plan).
    assert stem("types") == stem("type") == "type"
    assert stem("creates") == stem("create") == "creat"
    assert stem("roles") == stem("role") == "role"


def test_stem_covers_dominant_spanish_plural_pattern():
    assert stem("productos") == stem("producto") == "producto"
    assert stem("clientes") == stem("cliente") == "client"


def test_stem_spanish_consonant_es_plural_now_resolved_by_snowball():
    # Antes (stemmer casero, ver historial de este archivo): limitación
    # documentada, "papeles" -> "papele" != "papel". snowballstemmer sí
    # tiene una regla real para este patrón morfológico español y lo
    # resuelve: comprobado empíricamente antes de adoptar la librería, no
    # es casualidad ni se asume sin más.
    assert stem("papeles") == stem("papel") == "papel"


def test_stem_spanish_short_accented_word_is_a_new_known_limitation():
    # Trade-off aceptado y documentado (ver plan / docstring de stem()):
    # el stemmer casero anterior SÍ unificaba "año"/"años" (regla -s
    # genérica); el algoritmo Snowball español no actúa sobre palabras tan
    # cortas, así que esta regresión puntual es el precio de adoptar la
    # librería. Se fija por escrito a propósito, igual que se hizo con
    # "papeles" antes de resolverse.
    assert stem("año") == "año"
    assert stem("años") == "años"
    assert stem("año") != stem("años")


def test_expand_query_base_synonyms_are_bidirectional():
    # Se compara vía stem() en vez de hardcodear la forma truncada exacta
    # que produce snowballstemmer (p. ej. "creat"): lo que importa es la
    # relación bidireccional, no el string incidental de la librería.
    assert stem("add") in expand_query("create")
    assert stem("create") in expand_query("add")


def test_expand_query_multi_word():
    expanded = expand_query("list users")
    assert {stem("search"), stem("query"), stem("find")} <= expanded


def test_expand_query_no_known_synonym_adds_nothing_extra():
    assert expand_query("banana") == {"banana"}


def test_expand_query_injects_extra_synonyms():
    without_extra = expand_query("stock")
    with_extra = expand_query("stock", extra_synonyms={"stock": ["inventory"]})
    assert stem("inventory") not in without_extra
    assert stem("inventory") in with_extra


def test_expand_query_extra_synonyms_do_not_break_base_table():
    expanded = expand_query("create", extra_synonyms={"stock": ["inventory"]})
    assert "add" in expanded
