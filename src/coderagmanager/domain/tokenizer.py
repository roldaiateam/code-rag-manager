"""Tokenizer compartido por el scoring léxico multi-campo (US-05) y BM25 (US-11).

Portado en espíritu (no literal) de `code-rag-mcp`'s `Tokenizer.java`: split
de camelCase/snake_case/kebab-case, sinónimos base de ingeniería de software,
y stemming vía `snowballstemmer` (proyecto Snowball oficial, no NLTK/spaCy:
pure Python, sin modelos ni corpus pesados) en vez de una heurística casera.

Dos usos distintos, deliberadamente asimétricos (ver US-04 "Where and when
this runs"): `tokenize()` se aplica tanto a la query como a cada chunk;
`expand_query()` (con sinónimos) solo a la query, nunca al lado indexado —
así un `extra_synonyms` nuevo surte efecto en la siguiente búsqueda sin
necesitar reindexar.
"""

from __future__ import annotations

import re

import snowballstemmer

_LOWER_OR_DIGIT_TO_UPPER = re.compile(r"([a-z0-9])([A-Z])")
_ACRONYM_BOUNDARY = re.compile(r"([A-Z]+)([A-Z][a-z])")
# Incluye vocales acentuadas y ñ/Ü como caracteres de palabra: sin esto,
# `[^A-Za-z0-9]+` (el regex literal de `Tokenizer.java`) trata "código" o
# "año" como separadores y los destroza ("código" -> "digo", "año" -> nada).
# Detectado probando contra chunks e índices REALES (mic-inventory), no solo
# con ejemplos de test — ver plan US-04 / verify_tokenizer_real.py.
_NON_ALNUM = re.compile(r"[^A-Za-z0-9áéíóúüñÁÉÍÓÚÜÑ]+")

STOPWORDS = frozenset({
    # inglés
    "the", "a", "an", "of", "to", "for", "in", "on", "and", "or", "with",
    # español
    "por", "de", "la", "el", "los", "las", "un", "una", "con", "en", "que",
})

# Sinónimos genéricos de ingeniería de software (siempre activos), como
# grupos bidireccionales: cada término de un grupo expande a todos los
# demás. Deliberadamente fuera de aquí: vocabulario de negocio de un
# proyecto concreto (eso es `Project.extra_synonyms`, pasado por el caller).
_SYNONYM_GROUPS: list[list[str]] = [
    ["create", "add", "new", "insert"],
    ["remove", "delete"],
    ["update", "edit", "modify"],
    ["get", "fetch", "retrieve"],
    ["list", "search", "query", "find"],
    ["endpoint", "api", "route", "handler"],
    ["config", "configuration", "settings"],
    ["error", "exception", "failure"],
    ["validate", "check", "verify"],
]


def tokenize(text: str) -> set[str]:
    """Separa `text` en tokens normalizados: camelCase/snake_case/kebab-case
    partidos, en minúsculas, sin stopwords ni tokens de menos de 2 caracteres,
    con stemming aplicado a cada uno.
    """
    if not text:
        return set()
    spaced = _LOWER_OR_DIGIT_TO_UPPER.sub(r"\1 \2", text)
    spaced = _ACRONYM_BOUNDARY.sub(r"\1 \2", spaced)
    spaced = _NON_ALNUM.sub(" ", spaced).lower()
    return {
        stem(raw)
        for raw in spaced.split()
        if len(raw) >= 2 and raw not in STOPWORDS
    }


_EN_STEMMER = snowballstemmer.stemmer("english")
_ES_STEMMER = snowballstemmer.stemmer("spanish")
_SPANISH_ACCENTED_CHARS = frozenset("áéíóúüñÁÉÍÓÚÜÑ")


def stem(token: str) -> str:
    """Stemming vía Snowball (proyecto oficial), no una heurística casera.

    Selección de idioma por heurística simple: si el token contiene alguna
    vocal acentuada o "ñ" propia del español, se stemma con el algoritmo
    Snowball español; si no, con el inglés (una palabra española sin tilde,
    p. ej. "producto", pasa por el algoritmo inglés — en la práctica da el
    mismo resultado correcto porque ambos coinciden en el patrón vocal+s).

    No es una mejora estrictamente superior en todos los casos frente al
    stemmer casero que sustituye — verificado con ejemplos concretos antes
    de adoptarlo, no asumido:
    - **Gana Snowball**: `papel`/`papeles` ahora comparten raíz (antes,
      limitación documentada: `papele` ≠ `papel`).
    - **Gana el heurístico anterior** (regresión aceptada): palabras cortas
      acentuadas como `año`/`años` — Snowball no las reduce
      (`año`→`año`, `años`→`años`, no coinciden) porque su algoritmo
      español no actúa por debajo de cierta longitud; nuestra regla anterior
      sí las unificaba correctamente.
    - **Ninguno de los dos resuelve** palabras españolas largas como
      `validación`/`validaciones` (cada uno falla de una forma distinta).
    El caso que de verdad importa para este corpus (mayoritariamente
    identificadores en inglés) — `type`/`types`, `create`/`creates`,
    `role`/`roles`, `rule`/`rules`, `value`/`values`... — queda protegido
    igual o mejor que antes en todos los ejemplos probados: Snowball nunca
    rompe esa raíz compartida.
    """
    stemmer = _ES_STEMMER if _SPANISH_ACCENTED_CHARS & set(token) else _EN_STEMMER
    return stemmer.stemWord(token)


def _build_synonym_map(groups: list[list[str]]) -> dict[str, set[str]]:
    """Construye un mapa {stem(término): {stem(otros del grupo)}} bidireccional."""
    table: dict[str, set[str]] = {}
    for group in groups:
        stemmed = {stem(word) for word in group}
        for word in stemmed:
            table.setdefault(word, set()).update(stemmed - {word})
    return table


BASE_SYNONYMS = _build_synonym_map(_SYNONYM_GROUPS)


def expand_query(
    query: str, extra_synonyms: dict[str, list[str]] | None = None
) -> set[str]:
    """Tokeniza `query` y expande cada token con sus sinónimos.

    `extra_synonyms` (vocabulario de negocio de un proyecto concreto, p. ej.
    `Project.extra_synonyms`) se trata con la misma semántica de grupo
    bidireccional que la tabla base y se fusiona con ella. Este módulo no
    lee `~/.crm/projects.yaml` ni conoce `Project`: es responsabilidad del
    caller pasar el diccionario ya resuelto (mantiene `domain/` libre de
    E/S).
    """
    tokens = tokenize(query)
    table = BASE_SYNONYMS
    if extra_synonyms:
        extra_groups = [[key, *values] for key, values in extra_synonyms.items()]
        table = dict(BASE_SYNONYMS)
        for word, syns in _build_synonym_map(extra_groups).items():
            table[word] = table.get(word, set()) | syns
    expanded = set(tokens)
    for token in tokens:
        expanded.update(table.get(token, ()))
    return expanded
